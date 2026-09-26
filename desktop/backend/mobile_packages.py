from __future__ import annotations

import hashlib
import json
import shutil
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .studio_adapter import StudioAdapter


# Wspólny słownik zdarzeń telefonu (kontrakt v1). Stare nazwy desktopu są aliasami.
EVENT_TYPES = {"downloaded", "description_copied", "hashtags_copied", "instagram_opened", "sent", "manual_hook"}
EVENT_ALIASES = {"caption_copied": "description_copied", "manual_check": "manual_hook"}


class MobilePackages:
    def __init__(self, adapter: StudioAdapter):
        self.adapter = adapter
        self.root = adapter.settings.data_dir / "mobile-packages"
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def digest(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
        return h.hexdigest()

    def export(self, post_id: str, channel: str = "instagram") -> dict:
        card, source = self.adapter.get(post_id, channel), self.adapter.folder_for(post_id)
        if channel == "instagram" and not card.get("phone_ready"):
            raise ValueError("Ta paczka nie spełnia warunku: TikTok gotowy, Instagram czeka")
        version = card["content"]["revision"][:16]
        package_dir = self.root / card["brand"] / "do-instagrama" / f"{post_id}-{version}"
        package_dir.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{post_id}-{version}.zip"
        files = [p for p in source.iterdir() if p.is_file() and p.name not in {"post.json"}]
        for p in files: shutil.copy2(p,package_dir/p.name)
        (package_dir/"opis-do-skopiowania.txt").write_text(card["content"]["description"].strip()+"\n",encoding="utf-8")
        (package_dir/"hashtagi.txt").write_text(card["content"]["hashtags"].strip()+"\n",encoding="utf-8")
        manifest = {"schema_version": 1, "post_id": post_id, "brand": card["brand"], "content_revision": card["content"]["revision"], "exported_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"), "channel": channel, "source_state":{"tiktok":card["channels"]["tiktok"]["platform_evidence"],"instagram":card["channels"]["instagram"]["platform_evidence"]}, "files": [{"name": p.name, "sha256": self.digest(p)} for p in package_dir.iterdir() if p.is_file() and p.name!="manifest.json"]}
        (package_dir/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
        if not target.exists():
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
                for p in files: z.write(p, p.name)
                z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        index = self.write_index()
        return {"path": str(target), "name": target.name, "manifest": manifest, "url": f"/api/mobile-packages/{target.name}", "index_packages": len(index["packages"])}

    def write_index(self) -> dict:
        """Buduje index.json czytany przez Mobile: najnowsza rewizja na post_id + marka, adresy względne."""
        newest: dict[tuple[str, str], tuple[dict, Path]] = {}
        order = lambda m, f: (str(m.get("exported_at", "")), f.stat().st_mtime_ns)
        for file in sorted(self.root.glob("*/do-instagrama/*/manifest.json")):
            try: manifest = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, ValueError): continue
            key = (str(manifest.get("post_id", "")), str(manifest.get("brand", "")))
            if not all(key): continue
            if key not in newest or order(manifest, file) > order(*newest[key]):
                newest[key] = (manifest, file)
        packages = [{"post_id": m["post_id"], "brand": m["brand"], "content_revision": m.get("content_revision", ""), "exported_at": m.get("exported_at", ""), "manifest_url": f.relative_to(self.root).as_posix()} for m, f in newest.values()]
        packages.sort(key=lambda x: (x["brand"], x["exported_at"]), reverse=True)
        index = {"schema_version": 1, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "packages": packages}
        (self.root / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        return index

    def candidates(self, brand: str = "all") -> list[dict]:
        cards = self.adapter.list_cards(brand=brand, include_archive=False, selected_channel="instagram")["items"]
        return [card for card in cards if card.get("phone_ready")]

    def import_events(self, payload: dict) -> dict:
        """Importuje wyłącznie zdarzenia transportowe; nie zmienia paczki ani haczyków."""
        events = payload.get("events", [])
        if not isinstance(events, list): raise ValueError("events musi być listą")
        if payload.get("schema_version", 1) != 1: raise ValueError(f"Nieobsługiwany schema_version eksportu: {payload.get('schema_version')}")
        accepted, skipped = [], []
        out = self.root / "mobile-events.jsonl"
        seen = set()
        if out.exists():
            for line in out.read_text(encoding="utf-8", errors="replace").splitlines():
                try: seen.add(json.loads(line)["event_id"])
                except Exception: pass
        with out.open("a", encoding="utf-8") as stream:
            for raw in events:
                event_id, kind = str(raw.get("event_id", "")).strip(), str(raw.get("type", "")).strip()
                kind = EVENT_ALIASES.get(kind, kind)
                if not event_id or kind not in EVENT_TYPES or event_id in seen:
                    skipped.append(event_id or "brak-id"); continue
                event = {"event_id": event_id, "type": kind, "post_id": str(raw.get("post_id", "")), "brand": str(raw.get("brand", "")), "channel": str(raw.get("channel", "instagram")), "occurred_at": raw.get("occurred_at"), "source": "mobile"}
                if "value" in raw: event["value"] = bool(raw["value"])
                if isinstance(raw.get("files"), list): event["files"] = [str(x) for x in raw["files"]]
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                seen.add(event_id); accepted.append(event_id)
        return {"accepted": len(accepted), "skipped": len(skipped), "event_ids": accepted}
