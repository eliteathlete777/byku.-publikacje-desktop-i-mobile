from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class LearningStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def migrate(self):
        with self.connect() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS events(
              event_id TEXT PRIMARY KEY, run_id TEXT, post_id TEXT, brand TEXT, channel TEXT,
              stage TEXT NOT NULL, result TEXT, occurred_at TEXT NOT NULL, duration_ms INTEGER,
              script_version TEXT, rules_version TEXT, error_code TEXT, evidence_ref TEXT,
              before_json TEXT, after_json TEXT
            );
            CREATE TABLE IF NOT EXISTS lessons(
              lesson_id TEXT PRIMARY KEY, kind TEXT NOT NULL, brand TEXT, channel TEXT,
              problem TEXT NOT NULL, evidence_json TEXT NOT NULL, solution TEXT,
              scope TEXT, confidence REAL, test_json TEXT, version INTEGER NOT NULL,
              status TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS imports(source TEXT PRIMARY KEY, cursor TEXT NOT NULL);
            """)

    def add_event(self, event: dict) -> bool:
        cols = ("event_id","run_id","post_id","brand","channel","stage","result","occurred_at","duration_ms","script_version","rules_version","error_code","evidence_ref")
        values = [event.get(x) for x in cols]
        values += [json.dumps(event.get("before"), ensure_ascii=False), json.dumps(event.get("after"), ensure_ascii=False)]
        with self.connect() as con:
            cur = con.execute(f"INSERT OR IGNORE INTO events({','.join(cols)},before_json,after_json) VALUES ({','.join('?' for _ in range(len(values)))})", values)
            return cur.rowcount == 1

    def recent_events(self, limit: int = 100) -> list[dict]:
        with self.connect() as con:
            rows = con.execute("SELECT * FROM events ORDER BY occurred_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(x) for x in rows]

    def lessons(self, kind: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM lessons", ()
        if kind:
            sql, args = sql + " WHERE kind=?", (kind,)
        with self.connect() as con:
            rows = con.execute(sql + " ORDER BY created_at DESC", args).fetchall()
        return [dict(x) for x in rows]

