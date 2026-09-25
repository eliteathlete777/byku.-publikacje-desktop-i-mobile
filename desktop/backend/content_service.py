from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from learning.events import emit
from learning.store import LearningStore

from .studio_adapter import StudioAdapter


class RevisionConflict(RuntimeError):
    def __init__(self, current: dict, proposal: dict):
        super().__init__("Paczka zmieniła się od chwili otwarcia")
        self.current, self.proposal = current, proposal


class ContentService:
    def __init__(self, adapter: StudioAdapter, learning: LearningStore):
        self.adapter, self.learning = adapter, learning

    def save(self, post_id: str, *, expected_revision: str, description: str, hashtags: str, location: str, approve: bool = False) -> dict:
        folder = self.adapter.folder_for(post_id)
        current = self.adapter.get(post_id)
        proposal = {"description": description, "hashtags": hashtags, "location": location, "approve": approve}
        if current["revision"] != expected_revision:
            raise RevisionConflict(current, proposal)
        if self.adapter.settings.mode == "production" and not self.adapter.settings.allow_production_writes:
            raise PermissionError("Zapis produkcyjny nie został jawnie włączony")
        before = current["content"]
        tx_root = self.adapter.settings.data_dir / "transactions" / f"{post_id}-{int(time.time()*1000)}"
        stage = tx_root / "stage"
        backup = tx_root / "backup"
        stage.mkdir(parents=True)
        backup.mkdir(parents=True)
        journal = tx_root / "journal.json"
        journal.write_text(json.dumps({"phase": "prepared", "post_id": post_id, "expected_revision": expected_revision}, ensure_ascii=False, indent=2), encoding="utf-8")
        for name in ("post.json", "opis.txt"):
            if (folder / name).is_file():
                shutil.copy2(folder / name, backup / name)
        from studio.rdzen.magazyn import wczytaj_paczke, zapisz_paczke
        from studio.rdzen.model import rozdziel_opis
        paczka = wczytaj_paczke(folder, sprawdz_sumy=False)
        paczka.opis = description.strip()
        paczka.hashtagi = hashtags.strip()
        paczka.lokalizacja = location.strip()
        paczka.historia.append({"kiedy": time.strftime("%Y-%m-%d %H:%M:%S"), "co": "content_approved" if approve else "content_edited", "szczegol": "BYKU.PUBLIKACJE DESKTOP"})
        # Rdzeń zapisuje pełny, zgodny format i sumy; uczenie globalne glos.py nie jest wywoływane.
        zapisz_paczke(folder, paczka, przelicz_sumy=True)
        if not hashtags.strip():
            # Rdzeń historyczny przy pustej wartości dopisuje domyślne hashtagi.
            # Jawne wyczyszczenie jest osobną operacją nowego kontraktu.
            paczka.hashtagi = ""
            paczka.opis = description.strip()
            self._atomic_text(folder / "opis.txt", paczka.opis + ("\n" if paczka.opis else ""))
            self._atomic_text(folder / "post.json", paczka.do_json())
        journal.write_text(json.dumps({"phase": "committed", "post_id": post_id}, ensure_ascii=False, indent=2), encoding="utf-8")
        result = self.adapter.get(post_id)
        emit(self.learning, "caption_approved" if approve else "caption_edited", post_id=post_id, brand=result["brand"], before=before, after=result["content"], result="ok")
        return result

    @staticmethod
    def _atomic_text(path: Path, value: str) -> None:
        tmp = path.with_suffix(path.suffix + ".byku-tmp")
        tmp.write_text(value, encoding="utf-8")
        os.replace(tmp, path)
