from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path

from learning.events import emit
from learning.store import LearningStore

from .studio_adapter import StudioAdapter


PROFILE_RESOURCE = {
    ("atlet", "tiktok"): "edge-tiktok:9224", ("rigger", "tiktok"): "edge-rigger:9223",
    ("atlet", "instagram"): "edge-meta:9222", ("atlet", "facebook"): "edge-meta:9222",
    ("rigger", "instagram"): "chrome-rigger:9333", ("rigger", "facebook"): "chrome-rigger:9333",
}


class JobService:
    def __init__(self, adapter: StudioAdapter, learning: LearningStore):
        self.adapter, self.learning = adapter, learning
        self.root = adapter.settings.data_dir / "jobs"
        self.locks = adapter.settings.data_dir / "locks"
        self.root.mkdir(parents=True, exist_ok=True); self.locks.mkdir(parents=True, exist_ok=True)

    def _read(self, job_id: str) -> dict:
        return json.loads((self.root / f"{job_id}.json").read_text(encoding="utf-8"))

    def get(self, job_id: str) -> dict:
        return self._read(job_id)

    def start(self, post_id: str, channel: str, expected_revision: str, request_id: str) -> dict:
        if not self.adapter.settings.allow_publication:
            raise PermissionError("Publikowanie jest wyłączone w konfiguracji odbiorowej")
        card = self.adapter.get(post_id, channel)
        if card["revision"] != expected_revision:
            raise RuntimeError("Paczka zmieniła się przed startem")
        resource = PROFILE_RESOURCE[(card["brand"], channel)]
        lock = self.locks / (resource.replace(":", "-") + ".json")
        if lock.exists():
            owner = json.loads(lock.read_text(encoding="utf-8"))
            raise RuntimeError(f"Profil zajęty przez {owner.get('post_id')} ({owner.get('run_id')})")
        job_id = str(uuid.uuid4())
        state = {"job_id": job_id, "run_id": job_id, "request_id": request_id, "post_id": post_id, "channel": channel, "brand": card["brand"], "resource": resource, "state": "queued", "stage": "awaiting_safe_dispatch", "updated_at": time.time()}
        lock.write_text(json.dumps({"run_id": job_id, "post_id": post_id, "pid": os.getpid(), "heartbeat": time.time()}, ensure_ascii=False), encoding="utf-8")
        (self.root / f"{job_id}.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        emit(self.learning, "task_started", event_id=request_id, run_id=job_id, post_id=post_id, brand=card["brand"], channel=channel, result="queued")
        # Wydanie lokalne zatrzymuje się przed procesem zewnętrznym; dispatch włącza się osobną flagą.
        return state

    def complete_user_step(self, job_id: str) -> dict:
        state = self._read(job_id)
        state.update({"state": "verifying", "stage": "verify_platform", "updated_at": time.time()})
        (self.root / f"{job_id}.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return state

    def release(self, job_id: str, result: str = "interrupted") -> dict:
        state = self._read(job_id)
        state.update({"state": result, "updated_at": time.time()})
        (self.root / f"{job_id}.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        lock = self.locks / (state["resource"].replace(":", "-") + ".json")
        if lock.exists() and json.loads(lock.read_text(encoding="utf-8")).get("run_id") == job_id:
            lock.unlink()
        return state

