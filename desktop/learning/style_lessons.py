from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from .store import LearningStore


def remember_style(store: LearningStore, *, brand: str, post_id: str, revision: str, before: str, after: str) -> str:
    if brand not in {"atlet", "rigger"}:
        raise ValueError("Nieznana marka")
    lesson_id = str(uuid.uuid4())
    with store.connect() as con:
        version = con.execute("SELECT COALESCE(MAX(version),0)+1 FROM lessons WHERE kind='style' AND brand=?", (brand,)).fetchone()[0]
        con.execute("INSERT INTO lessons VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            lesson_id, "style", brand, None, "Świadomie zatwierdzona preferencja stylu",
            json.dumps({"post_id": post_id, "revision": revision, "before": before, "after": after}, ensure_ascii=False),
            after, "brand", 1.0, json.dumps({"type": "explicit_approval"}), version, "active", datetime.now(timezone.utc).isoformat()
        ))
    return lesson_id


def active_rules(store: LearningStore, brand: str) -> list[dict]:
    return [x for x in store.lessons("style") if x["brand"] == brand and x["status"] == "active"]

