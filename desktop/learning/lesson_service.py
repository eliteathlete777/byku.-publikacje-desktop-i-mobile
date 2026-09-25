from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from .store import LearningStore


class LessonService:
    KINDS = {"style", "process", "code"}

    def __init__(self, store: LearningStore): self.store = store

    def create(self, data: dict) -> dict:
        kind = str(data.get("kind", "process"))
        if kind not in self.KINDS: raise ValueError("Nieprawidłowy typ lekcji")
        brand = data.get("brand")
        with self.store.connect() as con:
            version = con.execute("SELECT COALESCE(MAX(version),0)+1 FROM lessons WHERE kind=? AND brand IS ?", (kind, brand)).fetchone()[0]
            lesson_id = str(uuid.uuid4())
            con.execute("INSERT INTO lessons VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                lesson_id, kind, brand, data.get("channel"), str(data.get("problem", "")).strip(),
                json.dumps(data.get("evidence", []), ensure_ascii=False), str(data.get("solution", "")).strip(),
                str(data.get("scope", "brand")), float(data.get("confidence", 1.0)),
                json.dumps(data.get("test", {}), ensure_ascii=False), version, "draft",
                datetime.now(timezone.utc).isoformat()))
        return self.get(lesson_id)

    def get(self, lesson_id: str) -> dict:
        with self.store.connect() as con:
            row = con.execute("SELECT * FROM lessons WHERE lesson_id=?", (lesson_id,)).fetchone()
        if not row: raise FileNotFoundError(lesson_id)
        return dict(row)

    def set_status(self, lesson_id: str, status: str) -> dict:
        if status not in {"draft", "active", "reverted", "rejected"}: raise ValueError("Nieprawidłowy status")
        lesson = self.get(lesson_id)
        if status == "active" and (not lesson["solution"] or not lesson["test_json"]):
            raise ValueError("Aktywacja wymaga rozwiązania i dowodu testu")
        with self.store.connect() as con:
            con.execute("UPDATE lessons SET status=? WHERE lesson_id=?", (status, lesson_id))
        return self.get(lesson_id)
