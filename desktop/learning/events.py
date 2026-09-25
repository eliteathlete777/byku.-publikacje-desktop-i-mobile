from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .store import LearningStore


def emit(store: LearningStore, stage: str, *, event_id: str | None = None, **data) -> dict:
    event = {"event_id": event_id or str(uuid.uuid4()), "stage": stage, "occurred_at": datetime.now(timezone.utc).isoformat(), **data}
    store.add_event(event)
    return event


def import_jsonl(store: LearningStore, path: Path, *, source: str | None = None) -> dict:
    inserted = skipped = 0
    if not path.is_file():
        return {"inserted": 0, "skipped": 0, "missing": True}
    for index, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        try:
            raw = json.loads(line)
        except Exception:
            skipped += 1
            continue
        identity = f"{source or path}:{index}:{line}".encode("utf-8")
        event_id = raw.get("event_id") or hashlib.sha256(identity).hexdigest()
        event = {
            "event_id": event_id, "run_id": raw.get("run_id"), "post_id": raw.get("post_id"),
            "brand": raw.get("marka") or raw.get("brand"), "channel": raw.get("kanal") or raw.get("channel"),
            "stage": raw.get("nazwa_etapu") or raw.get("krok") or raw.get("stage") or "legacy_event",
            "result": raw.get("wynik") or raw.get("status"), "occurred_at": raw.get("czas") or raw.get("ts") or datetime.now(timezone.utc).isoformat(),
            "error_code": raw.get("kod_bledu"), "evidence_ref": str(path), "before": raw.get("przed"), "after": raw.get("po"),
        }
        inserted += int(store.add_event(event))
    return {"inserted": inserted, "skipped": skipped}

