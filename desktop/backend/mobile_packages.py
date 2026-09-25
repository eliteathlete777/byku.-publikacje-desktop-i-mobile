from __future__ import annotations

import hashlib
import json
import shutil
import time
import zipfile
from pathlib import Path

from .studio_adapter import StudioAdapter


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
        manifest = {"schema_version": 1, "post_id": post_id, "brand": card["brand"], "content_revision": card["content"]["revision"], "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "channel": channel, "source_state":{"tiktok":card["channels"]["tiktok"]["platform_evidence"],"instagram":card["channels"]["instagram"]["platform_evidence"]}, "files": [{"name": p.name, "sha256": self.digest(p)} for p in package_dir.iterdir() if p.is_file() and p.name!="manifest.json"]}
        (package_dir/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
        if not target.exists():
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
                for p in files: z.write(p, p.name)
                z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        return {"path": str(target), "name": target.name, "manifest": manifest, "url": f"/api/mobile-packages/{target.name}"}

    def candidates(self, brand: str = "all") -> list[dict]:
        cards = self.adapter.list_cards(brand=brand, include_archive=False, selected_channel="instagram")["items"]
        return [card for card in cards if card.get("phone_ready")]

    def import_events(self, payload: dict) -> dict:
        """Importuje wyłącznie zdarzenia transportowe; nie zmienia paczki ani haczyków."""
        allowed = {"downloaded", "caption_copied", "instagram_opened", "sent", "manual_check"}
        events = payload.get("events", [])
        if not isinstance(events, list): raise ValueError("events musi być listą")
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
                if not event_id or kind not in allowed or event_id in seen:
                    skipped.append(event_id or "brak-id"); continue
                event = {"event_id": event_id, "type": kind, "post_id": str(raw.get("post_id", "")), "brand": str(raw.get("brand", "")), "occurred_at": raw.get("occurred_at"), "source": "mobile"}
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                seen.add(event_id); accepted.append(event_id)
        return {"accepted": len(accepted), "skipped": len(skipped), "event_ids": accepted}
