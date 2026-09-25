from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from learning.events import emit
from learning.store import LearningStore
from learning.style_lessons import remember_style

from .studio_adapter import StudioAdapter

THUMBNAIL_MAX = 8 * 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class RevisionConflict(RuntimeError):
    def __init__(self, current: dict, proposal: dict):
        super().__init__("Paczka zmieniła się od chwili otwarcia")
        self.current, self.proposal = current, proposal


def normalize_hashtags(value: str) -> str:
    """Jedna spacja między tagami, każdy z #, bez duplikatów (wielkość liter ignorowana)."""
    seen, out = set(), []
    for token in value.replace(",", " ").split():
        tag = "#" + token.lstrip("#").strip()
        if len(tag) < 2 or tag.lower() in seen:
            continue
        seen.add(tag.lower()); out.append(tag)
    return " ".join(out)


class ContentService:
    def __init__(self, adapter: StudioAdapter, learning: LearningStore):
        self.adapter, self.learning = adapter, learning

    def _transaction(self, post_id: str, folder: Path, names: tuple[str, ...], expected_revision: str) -> Path:
        tx_root = self.adapter.settings.data_dir / "transactions" / f"{post_id}-{int(time.time() * 1000)}"
        backup = tx_root / "backup"
        backup.mkdir(parents=True)
        for name in names:
            if (folder / name).is_file():
                shutil.copy2(folder / name, backup / name)
        (tx_root / "journal.json").write_text(json.dumps(
            {"phase": "prepared", "post_id": post_id, "expected_revision": expected_revision}, ensure_ascii=False, indent=2), encoding="utf-8")
        return tx_root

    @staticmethod
    def _commit(tx_root: Path, post_id: str) -> None:
        (tx_root / "journal.json").write_text(json.dumps({"phase": "committed", "post_id": post_id}, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _rollback(tx_root: Path, folder: Path) -> None:
        for file in (tx_root / "backup").iterdir():
            shutil.copy2(file, folder / file.name)
        (tx_root / "journal.json").write_text(json.dumps({"phase": "rolled_back"}, ensure_ascii=False), encoding="utf-8")

    def save(self, post_id: str, *, expected_revision: str, description: str, hashtags: str, location: str, approve: bool = False) -> dict:
        folder = self.adapter.folder_for(post_id)
        current = self.adapter.get(post_id)
        proposal = {"description": description, "hashtags": hashtags, "location": location, "approve": approve}
        if current["revision"] != expected_revision:
            raise RevisionConflict(current, proposal)
        self.adapter.ensure_writes("Zapis treści")
        before = current["content"]
        tx = self._transaction(post_id, folder, ("post.json", "opis.txt"), expected_revision)
        try:
            _, package = self.adapter.read_package(post_id)
            package.opis = description.strip()
            package.hashtagi = normalize_hashtags(hashtags)
            package.lokalizacja = location.strip()
            package.historia.append({"kiedy": time.strftime("%Y-%m-%d %H:%M:%S"),
                                     "co": "content_approved" if approve else "content_edited",
                                     "szczegol": "BYKU.PUBLIKACJE DESKTOP"})
            self.adapter.require_core().save_content(folder, package)
        except Exception:
            self._rollback(tx, folder)
            raise
        self._commit(tx, post_id)
        result = self.adapter.get(post_id)
        emit(self.learning, "caption_approved" if approve else "caption_edited", post_id=post_id,
             brand=result["brand"], before=before, after=result["content"], result="ok")
        if approve and before.get("description", "").strip() != result["content"]["description"].strip():
            # Świadoma akceptacja zmienionego tekstu = jawna lekcja stylu tej marki.
            remember_style(self.learning, brand=result["brand"], post_id=post_id, revision=result["revision"],
                           before=before.get("description", ""), after=result["content"]["description"])
        return result

    def replace_thumbnail(self, post_id: str, *, expected_revision: str, data: bytes) -> dict:
        folder = self.adapter.folder_for(post_id)
        current = self.adapter.get(post_id)
        if current["revision"] != expected_revision:
            raise RevisionConflict(current, {"thumbnail": True})
        if not data.startswith(PNG_MAGIC) or len(data) > THUMBNAIL_MAX:
            raise ValueError("Miniatura musi być plikiem PNG do 8 MB")
        self.adapter.ensure_writes("Zmiana miniatury")
        tx = self._transaction(post_id, folder, ("miniaturka.png",), expected_revision)
        tmp = folder / "miniaturka.png.byku-tmp"
        tmp.write_bytes(data)
        tmp.replace(folder / "miniaturka.png")
        self._commit(tx, post_id)
        emit(self.learning, "thumbnail_replaced", post_id=post_id, brand=current["brand"], result="ok")
        return self.adapter.get(post_id)
