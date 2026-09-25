"""Paczki telefonu (kontrakt v2) i transfer: Google Drive (folder synchronizowany) + serwer mobilny."""
from __future__ import annotations

import hashlib
import json
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from . import contract
from .studio_adapter import StudioAdapter

MOBILE_EVENT_TYPES = {"downloaded", "caption_copied", "hashtags_copied", "instagram_opened", "manual_check"}
PRIORITY = {"published": 0, "scheduled": 1, "manual_checked": 2}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TransferError(RuntimeError):
    pass


class MobilePackages:
    def __init__(self, adapter: StudioAdapter, opener=None):
        self.adapter = adapter
        self.settings = adapter.settings
        self.root = self.settings.data_dir / "mobile-packages"
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_file = self.root / "transfer-state.json"
        self.opener = opener or urllib.request.urlopen

    # ---------- eksport ----------
    def build_manifest(self, card: dict, files: list[dict]) -> dict:
        ch = card["channels"]
        return {
            "schema_version": contract.SCHEMA_VERSION,
            "package_id": contract.package_id(card["brand"], card["post_id"]),
            "post_id": card["post_id"], "brand": card["brand"], "title": card["name"],
            "type": card["assets"]["type"], "content_revision": card["content"]["revision"],
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "channel": "instagram",
            "caption": card["content"]["description"].strip(),
            "hashtags": card["content"]["hashtags"].strip(),
            "location": card["content"]["location"].strip(),
            "platforms": {k: {"evidence": v["platform_evidence"], "manual_checked": bool(v["manual_checked"])} for k, v in ch.items()},
            "transfer": {"from": "tiktok", "to": "instagram", "tiktok": card["tiktok_transfer"], "instagram": "pending"},
            "files": files,
        }

    def export(self, post_id: str, channel: str = "instagram") -> dict:
        if channel != "instagram":
            raise ValueError("Paczka telefonu dotyczy transferu TikTok → Instagram")
        card = self.adapter.get(post_id, channel)
        folder = self.adapter.folder_for(post_id)
        if not card.get("phone_ready"):
            raise ValueError("Ta paczka nie spełnia warunku: TikTok gotowy, Instagram czeka, komplet plików")
        revision = card["content"]["revision"]
        package_dir = self.root / card["brand"] / post_id / revision[:16]
        if package_dir.exists():
            shutil.rmtree(package_dir)  # czysty katalog tej rewizji — bez starych plików
        package_dir.mkdir(parents=True)
        entries: list[tuple[str, str, int | None]] = []
        for order, name in enumerate(card["assets"]["files"], start=1):
            shutil.copy2(folder / name, package_dir / name)
            entries.append((name, "slide" if card["assets"]["type"] == "carousel" else "video", order))
        shutil.copy2(folder / "miniaturka.png", package_dir / "miniaturka.png")
        entries.append(("miniaturka.png", "thumbnail", None))
        caption = card["content"]["description"].strip()
        hashtags = card["content"]["hashtags"].strip()
        (package_dir / "opis-do-skopiowania.txt").write_text(caption + ("\n" if caption else ""), encoding="utf-8")
        (package_dir / "hashtagi.txt").write_text(hashtags + ("\n" if hashtags else ""), encoding="utf-8")
        entries += [("opis-do-skopiowania.txt", "caption", None), ("hashtagi.txt", "hashtags", None)]
        files = []
        for name, role, order in entries:
            item: dict[str, Any] = {"name": name, "role": role, "sha256": digest(package_dir / name), "size": (package_dir / name).stat().st_size}
            if role == "slide":
                item["order"] = order
            files.append(item)
        manifest = self.build_manifest(card, files)
        errors = contract.validate(manifest)
        if errors:
            raise ValueError("Paczka niezgodna z kontraktem: " + "; ".join(e["message"] for e in errors))
        (package_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        zip_path = self.root / f"{card['brand']}-{post_id}-{revision[:16]}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(package_dir.iterdir()):
                z.write(p, p.name)
        self._set_state(manifest["package_id"], {"revision": revision, "exported_at": manifest["exported_at"], "dir": str(package_dir), "zip": zip_path.name})
        return {"path": str(zip_path), "name": zip_path.name, "dir": str(package_dir), "manifest": manifest,
                "url": f"/api/mobile-packages/{zip_path.name}", "transfer": self.transfer_state(manifest["package_id"])}

    def verify_dir(self, package_dir: Path) -> dict:
        manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
        errors = [e["message"] for e in contract.validate(manifest)]
        for item in manifest.get("files", []):
            p = package_dir / item["name"]
            if not p.is_file():
                errors.append(f"Brak pliku {item['name']}")
            elif digest(p) != item["sha256"]:
                errors.append(f"Niezgodna suma SHA-256: {item['name']}")
        return {"ok": not errors, "errors": errors, "manifest": manifest}

    def candidates(self, brand: str = "all") -> list[dict]:
        cards = self.adapter.list_cards(brand=brand, include_archive=False, selected_channel="instagram")["items"]
        ready = [c for c in cards if c.get("phone_ready")]
        for card in ready:
            card["transfer"] = self.transfer_state(contract.package_id(card["brand"], card["post_id"]))
        ready.sort(key=lambda c: (PRIORITY.get(c["tiktok_transfer"], 9), c.get("local_target_at") or "9999"))
        return ready

    # ---------- stan transferu (lokalny, poza kolejką) ----------
    def _states(self) -> dict:
        return json.loads(self.state_file.read_text(encoding="utf-8")) if self.state_file.exists() else {}

    def _set_state(self, package_id: str, patch: dict) -> None:
        states = self._states()
        entry = states.get(package_id, {})
        if patch.get("revision") and entry.get("revision") != patch["revision"]:
            entry = {}  # nowa rewizja: poprzednie wysyłki jej nie dotyczą
        entry.update(patch)
        states[package_id] = entry
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(states, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.state_file)

    def transfer_state(self, package_id: str) -> dict:
        return self._states().get(package_id, {})

    def _latest_dir(self, post_id: str) -> Path:
        card = self.adapter.get(post_id)
        state = self.transfer_state(contract.package_id(card["brand"], post_id))
        if not state.get("dir") or state.get("revision") != card["content"]["revision"]:
            raise ValueError("Najpierw przygotuj paczkę dla aktualnej wersji treści")
        return Path(state["dir"])

    # ---------- Google Drive (lokalny folder synchronizowany) ----------
    def drive_status(self) -> dict:
        target = self.settings.drive_sync_dir
        return {"configured": bool(target), "available": bool(target and target.is_dir()), "path": str(target or ""),
                "folder_ids": self.settings.drive_folder_ids}

    def to_drive(self, post_id: str) -> dict:
        status = self.drive_status()
        if not status["available"]:
            raise TransferError("Folder Google Drive nie jest ustawiony albo nie istnieje (google_drive.local_sync_dir)")
        source = self._latest_dir(post_id)
        check = self.verify_dir(source)
        if not check["ok"]:
            raise TransferError("; ".join(check["errors"]))
        manifest = check["manifest"]
        target = self.settings.drive_sync_dir / manifest["brand"] / "do-instagrama" / post_id
        existing = target / "manifest.json"
        if existing.is_file():
            old = json.loads(existing.read_text(encoding="utf-8"))
            if old.get("exported_at", "") > manifest["exported_at"]:
                raise TransferError("Na Dysku jest nowsza wersja tej paczki — nie nadpisuję")
        staging = target.with_name(target.name + ".byku-tmp")
        if staging.exists():
            shutil.rmtree(staging)
        shutil.copytree(source, staging)
        if target.exists():
            shutil.rmtree(target)
        staging.rename(target)
        self._set_state(manifest["package_id"], {"drive_at": time.strftime("%Y-%m-%d %H:%M:%S"), "drive_path": str(target)})
        return {"ok": True, "path": str(target)}

    # ---------- serwer mobilny (Hostinger) ----------
    def server_status(self) -> dict:
        return {"configured": bool(self.settings.mobile_server_url), "url": self.settings.mobile_server_url,
                "token": bool(self.settings.mobile_upload_token)}

    def _request(self, method: str, path: str, *, data: bytes | None = None, headers: dict | None = None, timeout: int = 600) -> dict:
        if not self.settings.mobile_server_url or not self.settings.mobile_upload_token:
            raise TransferError("Serwer mobilny nie jest skonfigurowany (mobile_server.url i BYKU_MOBILE_UPLOAD_TOKEN w .env)")
        request = urllib.request.Request(self.settings.mobile_server_url + path, data=data, method=method)
        request.add_header("Authorization", f"Bearer {self.settings.mobile_upload_token}")
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        try:
            with self.opener(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            try:
                message = json.loads(exc.read().decode("utf-8")).get("error", "")
            except Exception:
                message = ""
            raise TransferError(f"Serwer: HTTP {exc.code} {message}".strip()) from exc
        except urllib.error.URLError as exc:
            raise TransferError(f"Brak połączenia z serwerem mobilnym: {exc.reason}") from exc

    def to_server(self, post_id: str) -> dict:
        source = self._latest_dir(post_id)
        check = self.verify_dir(source)
        if not check["ok"]:
            raise TransferError("; ".join(check["errors"]))
        manifest = check["manifest"]
        query = {"package": manifest["package_id"], "rev": manifest["content_revision"]}
        for item in manifest["files"]:
            q = urllib.parse.urlencode({**query, "name": item["name"]})
            self._request("PUT", f"/api/upload/file?{q}", data=(source / item["name"]).read_bytes(),
                          headers={"X-Sha256": item["sha256"], "Content-Type": "application/octet-stream"})
        result = self._request("POST", "/api/upload/commit", data=json.dumps(manifest, ensure_ascii=False).encode("utf-8"),
                               headers={"Content-Type": "application/json"})
        self._set_state(manifest["package_id"], {"server_at": time.strftime("%Y-%m-%d %H:%M:%S"), "server_result": result.get("state", "ok")})
        return {"ok": True, **result}

    def pull_server_events(self) -> dict:
        data = self._request("GET", "/api/events/export", timeout=60)
        return self.import_events({"events": data.get("events", [])})

    # ---------- zdarzenia telefonu ----------
    def import_events(self, payload: dict) -> dict:
        """Importuje wyłącznie zdarzenia transportowe; nie zmienia paczki ani haczyków."""
        events = payload.get("events", [])
        if not isinstance(events, list):
            raise ValueError("events musi być listą")
        accepted, skipped = [], []
        out = self.root / "mobile-events.jsonl"
        seen = set()
        if out.exists():
            for line in out.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    seen.add(json.loads(line)["event_id"])
                except Exception:
                    pass
        with out.open("a", encoding="utf-8") as stream:
            for raw in events:
                raw = raw if isinstance(raw, dict) else {}
                event_id, kind = str(raw.get("event_id", "")).strip(), str(raw.get("type", "")).strip()
                if not event_id or kind not in MOBILE_EVENT_TYPES or event_id in seen:
                    skipped.append(event_id or "brak-id")
                    continue
                event = {"event_id": event_id, "type": kind, "package_id": str(raw.get("package_id", "")),
                         "post_id": str(raw.get("post_id", "")), "brand": str(raw.get("brand", "")),
                         "occurred_at": raw.get("occurred_at"), "source": "mobile"}
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                seen.add(event_id)
                accepted.append(event_id)
        return {"accepted": len(accepted), "skipped": len(skipped), "event_ids": accepted}

    def mobile_events(self, post_id: str | None = None) -> list[dict]:
        out = self.root / "mobile-events.jsonl"
        if not out.exists():
            return []
        rows = []
        for line in out.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            if post_id is None or row.get("post_id") == post_id:
                rows.append(row)
        return rows
