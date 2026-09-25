from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .config import Settings
from .core import CoreUnavailable, load_core
from .publication_view import CHANNELS, channel_view, counts, next_action

VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


class StudioAdapter:
    def __init__(self, settings: Settings, core: Any | None = None):
        self.settings = settings
        self.core_error = ""
        if core is not None:
            self.core = core
        else:
            try:
                self.core = load_core(settings.source_root, settings.mode, settings.core)
            except CoreUnavailable as exc:
                self.core, self.core_error = None, str(exc)

    def require_core(self):
        if self.core is None:
            raise CoreUnavailable(self.core_error or "Rdzeń magazynu jest niedostępny")
        return self.core

    @staticmethod
    def revision(folder: Path) -> str:
        h = hashlib.sha256()
        for name in ("post.json", "opis.txt", "miniaturka.png"):
            p = folder / name
            h.update(name.encode())
            if p.is_file():
                h.update(p.read_bytes())
        return h.hexdigest()

    def _media(self, folder: Path, package: Any) -> list[Path]:
        if getattr(package, "jest_karuzela", False):
            return [folder / x for x in (getattr(package, "slajdy", []) or [])]
        videos = sorted(p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXT and not p.stem.endswith("-hd"))
        preferred = getattr(package, "nazwa_wideo", "")
        if preferred and (folder / preferred).is_file():
            videos = [folder / preferred] + [p for p in videos if p.name != preferred]
        return videos[:1]

    def _assets(self, folder: Path, package: Any) -> dict[str, Any]:
        missing: list[str] = []
        thumb = folder / "miniaturka.png"
        if not thumb.is_file():
            missing.append("brak miniaturki")
        media = self._media(folder, package)
        if not media or any(not p.is_file() for p in media):
            missing.append("brak materiału")
        carousel = bool(getattr(package, "jest_karuzela", False))
        if carousel and len(media) < 2:
            missing.append("karuzela ma mniej niż 2 slajdy")
        base = f"/api/publications/{package.post_id}"
        return {
            "type": "carousel" if carousel else "reel",
            "files": [p.name for p in media],
            "media_urls": [f"{base}/media/{p.name}" for p in media if p.is_file()],
            "missing": missing,
            "thumbnail_url": f"{base}/thumbnail?v={int(thumb.stat().st_mtime)}" if thumb.is_file() else "",
        }

    def card(self, folder: Path, package: Any, *, selected_channel: str = "instagram") -> dict[str, Any]:
        core = self.require_core()
        raw_channels = getattr(package, "platformy_stan", {}) or {}
        channels = {c: channel_view(raw_channels.get(c), manual_checked=core.manual_hook(package, c)) for c in CHANNELS}
        active_channels = list(getattr(package, "platformy", CHANNELS) or CHANNELS)
        for name, channel in channels.items():
            channel["local_target_at"] = getattr(package, "termin", "") or ""
            channel["enabled"] = name in active_channels
        content_revision = self.revision(folder)
        history = [x for x in (getattr(package, "historia", []) or []) if isinstance(x, dict)]
        content = {
            "description": getattr(package, "opis", "") or "",
            "hashtags": getattr(package, "hashtagi", "") or "",
            "location": getattr(package, "lokalizacja", "") or "",
            "revision": content_revision,
            "approved": _approved(history),
        }
        card = {
            "post_id": package.post_id, "brand": getattr(package, "marka", "atlet"),
            "name": getattr(package, "etykieta_mediow", "") or getattr(package, "nazwa_wideo", "") or package.post_id,
            "revision": content_revision, "legacy_status": getattr(package, "status", ""),
            "archived": getattr(package, "status", "") == "archiwum",
            "local_target_at": getattr(package, "termin", "") or "", "content": content,
            "assets": self._assets(folder, package), "channels": channels, "history": history,
            "folder": str(folder),
        }
        tt, ig = channels["tiktok"], channels["instagram"]
        tiktok_ready = tt["platform_evidence"] in {"scheduled", "published"} or tt["manual_checked"]
        card["phone_ready"] = (
            tiktok_ready and ig["platform_evidence"] != "published" and not ig["manual_checked"]
            and not card["archived"] and not card["assets"]["missing"]
        )
        card["tiktok_transfer"] = (
            "published" if tt["platform_evidence"] == "published"
            else "scheduled" if tt["platform_evidence"] == "scheduled"
            else "manual_checked" if tt["manual_checked"] else ""
        )
        card["next_action"] = next_action(card, selected_channel)
        return card

    def list_cards(self, *, brand: str = "atlet", include_archive: bool = False, selected_channel: str = "instagram") -> dict[str, Any]:
        core = self.require_core()
        cards, errors = [], []
        for folder, package, error in core.list(self.settings.queue):
            if package is None:
                errors.append({"post_id": folder.name, "error": error})
                continue
            if brand not in {"all", "obie"} and getattr(package, "marka", "") != brand:
                continue
            try:
                card = self.card(folder, package, selected_channel=selected_channel)
            except Exception as exc:
                errors.append({"post_id": folder.name, "error": str(exc)})
                continue
            if include_archive or not card["archived"]:
                cards.append(card)
        cards.sort(key=lambda x: (x.get("local_target_at") or "9999", x["post_id"]))
        return {"items": cards, "counts": counts(cards), "errors": errors, "mode": self.settings.mode, "queue": str(self.settings.queue)}

    def folder_for(self, post_id: str) -> Path:
        if not post_id or any(x in post_id for x in ("/", "\\", "..")) or post_id.startswith("."):
            raise ValueError("Nieprawidłowy identyfikator paczki")
        root = self.settings.queue.resolve()
        folder = (root / post_id).resolve()
        folder.relative_to(root)
        if not folder.is_dir():
            raise FileNotFoundError(post_id)
        return folder

    def file_for(self, post_id: str, name: str) -> Path:
        folder = self.folder_for(post_id)
        if not name or "/" in name or "\\" in name or ".." in name or name.startswith("."):
            raise ValueError("Nieprawidłowa nazwa pliku")
        file = folder / name
        if not file.is_file() or file.suffix.lower() not in VIDEO_EXT | IMAGE_EXT:
            raise FileNotFoundError(name)
        return file

    def read_package(self, post_id: str) -> tuple[Path, Any]:
        folder = self.folder_for(post_id)
        return folder, self.require_core().read(folder)

    def get(self, post_id: str, selected_channel: str = "instagram") -> dict[str, Any]:
        folder, package = self.read_package(post_id)
        return self.card(folder, package, selected_channel=selected_channel)

    def ensure_writes(self, what: str = "Zapis produkcyjny") -> None:
        if not self.settings.writes_allowed:
            raise PermissionError(f"{what} jest zablokowany: allow_production_writes=false (bezpieczny podgląd)")

    def set_manual_check(self, post_id: str, channel: str, checked: bool, expected_revision: str) -> dict[str, Any]:
        if channel not in CHANNELS:
            raise ValueError("Nieprawidłowy kanał")
        current = self.get(post_id, channel)
        if current["revision"] != expected_revision:
            raise RuntimeError("Paczka zmieniła się od chwili otwarcia. Odśwież kartę.")
        self.ensure_writes("Ręczne potwierdzenie")
        # Zachowujemy dokładnie oryginalne pole haczyka. Dowód platformy nie jest tu zmieniany.
        folder, package = self.read_package(post_id)
        if channel not in package.platformy:
            raise ValueError(f"Kanał {channel} nie należy do tej paczki")
        entry = package.platformy_stan.setdefault(channel, {"stan": "czeka", "proby": 0, "url": "", "info": ""})
        entry["haczyk"] = bool(checked)
        entry["info"] = ("Użytkownik potwierdził wykonanie w BYKU.PUBLIKACJE DESKTOP" if checked
                         else "Użytkownik cofnął potwierdzenie w BYKU.PUBLIKACJE DESKTOP")
        if checked:
            entry["stan"] = "potwierdzony"
        elif entry.get("stan") == "potwierdzony":
            entry["stan"], entry["url"] = "czeka", ""
        package.dopisz_historie(f"{channel}:haczyk", entry["info"])
        self.require_core().recalc_status(package)
        self.require_core().save(folder, package, recompute=False)
        return self.get(post_id, channel)


def _approved(history: list[dict]) -> bool:
    """Akceptacja dotyczy ostatniej wersji: późniejsza edycja ją unieważnia."""
    for entry in reversed(history):
        what = str(entry.get("co", ""))
        if what.startswith("content_approved"):
            return True
        if what.startswith("content_edited"):
            return False
    return False
