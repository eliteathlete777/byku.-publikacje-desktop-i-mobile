from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from .config import Settings
from .publication_view import CHANNELS, channel_view, counts, headline, next_action


class StudioAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings
        if str(settings.source_root) not in sys.path:
            sys.path.insert(0, str(settings.source_root))

    @staticmethod
    def revision(folder: Path) -> str:
        h = hashlib.sha256()
        for name in ("post.json", "opis.txt", "miniaturka.png"):
            p = folder / name
            h.update(name.encode())
            if p.is_file():
                h.update(p.read_bytes())
        return h.hexdigest()

    def _manual(self, paczka: Any, channel: str) -> bool:
        try:
            from studio.rdzen.most_publikacji import haczyk_reczny
            return bool(haczyk_reczny(paczka, channel))
        except Exception:
            raw = getattr(paczka, "platformy_stan", {}).get(channel, {})
            return bool(raw.get("haczyk")) if isinstance(raw, dict) else False

    def _assets(self, folder: Path, paczka: Any) -> dict[str, Any]:
        missing: list[str] = []
        thumb = folder / "miniaturka.png"
        if not thumb.is_file():
            missing.append("brak miniaturki")
        media = []
        if getattr(paczka, "jest_karuzela", False):
            media = [folder / x for x in (getattr(paczka, "slajdy", []) or [])]
        else:
            candidates = [p for p in folder.iterdir() if p.suffix.lower() in {".mp4", ".mov", ".webm"} and not p.stem.endswith("-hd")]
            media = candidates[:1]
        if not media or any(not p.is_file() for p in media):
            missing.append("brak materiału")
        return {"type": "carousel" if getattr(paczka, "jest_karuzela", False) else "reel", "files": [p.name for p in media], "missing": missing, "thumbnail_url": f"/api/publications/{paczka.post_id}/thumbnail" if thumb.is_file() else ""}

    def live_snapshots(self) -> dict[str, dict | None]:
        """Ostatni zrzut kalendarzy LIVE każdej marki (status/kalendarz-live-*.json); stary (>12 h) pomijamy."""
        try:
            from studio.rdzen.kalendarz_live import wczytaj_zrzut_live, zrzut_jest_stary
        except Exception:
            return {}
        out: dict[str, dict | None] = {}
        for brand in ("atlet", "rigger"):
            try:
                snap = wczytaj_zrzut_live(brand)
                out[brand] = None if zrzut_jest_stary(snap, 12.0) else snap
            except Exception:
                out[brand] = None
        return out

    def overlay(self, paczka: Any, snaps: dict[str, dict | None]) -> None:
        """Nakłada w pamięci to samo co „Odśwież weryfikację” w Studio (status/*.jsonl + zrzut LIVE),
        bez zapisu do post.json — dzięki temu tryb podglądu widzi aktualne kalendarze i platformy."""
        try:
            from studio.rdzen.kalendarz_live import zastosuj_live_do_paczki
            from studio.rdzen.weryfikacja_statusu import _klucze_do_zapisu, raport_paczki
        except Exception:
            return
        try:
            if getattr(paczka, "status", "") not in ("szkic", "gotowy", "archiwum"):
                for rap in raport_paczki(paczka):
                    stan = rap["stan_paczki"]
                    if stan == "czeka" and rap["werdykt"] in ("brak", "w_toku", "czeka_na_cta"):
                        continue
                    for klucz in _klucze_do_zapisu(rap["kanal"], paczka):
                        przed = paczka.platformy_stan.get(klucz) or {}
                        if przed.get("stan") == "potwierdzony" and stan != "potwierdzony" and rap["werdykt"] != "klikniete_niepewne":
                            continue
                        paczka.ustaw_stan_platformy(klucz, stan, info=rap["tekst"][:500], licz_probe=False)
            snap = snaps.get(getattr(paczka, "marka", ""))
            if snap:
                zastosuj_live_do_paczki(paczka, snap)
        except Exception:
            pass  # nakładka jest pomocnicza — surowy post.json zawsze zostaje źródłem prawdy

    def card(self, folder: Path, paczka: Any, *, selected_channel: str = "instagram") -> dict[str, Any]:
        raw_channels = getattr(paczka, "platformy_stan", {}) or {}
        channels = {c: channel_view(raw_channels.get(c), manual_checked=self._manual(paczka, c)) for c in CHANNELS}
        for channel in channels.values():
            channel["local_target_at"] = getattr(paczka, "termin", "") or ""
        content_revision = self.revision(folder)
        history = list(getattr(paczka, "historia", []) or [])
        content = {
            "description": getattr(paczka, "opis", "") or "",
            "hashtags": getattr(paczka, "hashtagi", "") or "",
            "location": getattr(paczka, "lokalizacja", "") or "",
            "revision": content_revision,
            "approved": any(str(x.get("co", "")).startswith("content_approved") for x in history if isinstance(x, dict)),
        }
        card = {
            "post_id": paczka.post_id, "brand": getattr(paczka, "marka", "atlet"),
            "name": getattr(paczka, "etykieta_mediow", "") or getattr(paczka, "nazwa_wideo", "") or paczka.post_id,
            "headline": headline(content["description"]),
            "revision": content_revision, "legacy_status": getattr(paczka, "status", ""),
            "archived": getattr(paczka, "status", "") == "archiwum",
            "local_target_at": getattr(paczka, "termin", "") or "", "content": content,
            "assets": self._assets(folder, paczka), "channels": channels, "history": history,
            "observed_at": "", "stale": False, "folder": str(folder),
        }
        tt, ig = channels["tiktok"], channels["instagram"]
        card["phone_ready"] = (
            (tt["platform_evidence"] in {"scheduled", "published"} or tt["manual_checked"])
            and ig["platform_evidence"] != "published" and not ig["manual_checked"]
            and not card["archived"] and not card["assets"]["missing"]
        )
        card["next_action"] = next_action(card, selected_channel)
        return card

    def list_cards(self, *, brand: str = "atlet", include_archive: bool = False, selected_channel: str = "instagram") -> dict[str, Any]:
        from studio.rdzen.magazyn import lista_paczek
        rows = lista_paczek(root=self.settings.queue)
        cards, errors, snaps = [], [], self.live_snapshots()
        for folder, paczka, error in rows:
            if paczka is None:
                errors.append({"post_id": folder.name, "error": error})
                continue
            if brand not in {"all", "obie"} and paczka.marka != brand:
                continue
            self.overlay(paczka, snaps)
            card = self.card(folder, paczka, selected_channel=selected_channel)
            if include_archive or not card["archived"]:
                cards.append(card)
        cards.sort(key=lambda x: (x.get("local_target_at") or "9999", x["post_id"]))
        return {"items": cards, "counts": counts(cards), "errors": errors, "mode": self.settings.mode, "queue": str(self.settings.queue)}

    def folder_for(self, post_id: str) -> Path:
        if not post_id or any(x in post_id for x in ("/", "\\", "..")):
            raise ValueError("Nieprawidłowy identyfikator paczki")
        folder = (self.settings.queue / post_id).resolve()
        folder.relative_to(self.settings.queue.resolve())
        if not folder.is_dir():
            raise FileNotFoundError(post_id)
        return folder

    def get(self, post_id: str, selected_channel: str = "instagram") -> dict[str, Any]:
        from studio.rdzen.magazyn import wczytaj_paczke
        folder = self.folder_for(post_id)
        paczka = wczytaj_paczke(folder, sprawdz_sumy=False)
        self.overlay(paczka, self.live_snapshots())
        return self.card(folder, paczka, selected_channel=selected_channel)

    def set_manual_check(self, post_id: str, channel: str, checked: bool, expected_revision: str) -> dict[str, Any]:
        if channel not in CHANNELS:
            raise ValueError("Nieprawidłowy kanał")
        current = self.get(post_id, channel)
        if current["revision"] != expected_revision:
            raise RuntimeError("Paczka zmieniła się od chwili otwarcia")
        if self.settings.mode == "production" and not self.settings.allow_production_writes:
            raise PermissionError("Ręczne potwierdzenia produkcyjne są zablokowane w trybie podglądu")
        # Zachowujemy dokładnie oryginalne pole haczyka, ale nie wywołujemy
        # starego automatycznego zbierania „złota” przy publikacji. W nowym
        # desktopie wzorzec stylu powstaje wyłącznie po świadomej akcji.
        from studio.rdzen.magazyn import wczytaj_paczke, zapisz_paczke
        folder = self.folder_for(post_id)
        paczka = wczytaj_paczke(folder, sprawdz_sumy=False)
        if channel not in paczka.platformy:
            raise ValueError(f"Kanał {channel} nie należy do tej paczki")
        entry = paczka.platformy_stan.setdefault(channel, {"stan": "czeka", "proby": 0, "url": "", "info": ""})
        entry["haczyk"] = bool(checked)
        entry["info"] = "Użytkownik potwierdził wykonanie w BYKU.PUBLIKACJE DESKTOP" if checked else "Użytkownik cofnął potwierdzenie w BYKU.PUBLIKACJE DESKTOP"
        if checked:
            entry["stan"] = "potwierdzony"
        elif entry.get("stan") == "potwierdzony":
            entry["stan"], entry["url"] = "czeka", ""
        paczka.dopisz_historie(f"{channel}:haczyk", entry["info"])
        paczka._przelicz_status()
        zapisz_paczke(folder, paczka, przelicz_sumy=False)
        return self.get(post_id, channel)
