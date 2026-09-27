"""„Aktualizuj wszystko”: kalendarze LIVE, wysyłki, telefon — bez przeglądarek (atrapy Studio)."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from backend.mobile_packages import MobilePackages
from backend.sync_service import SyncService
from tests.test_mobile_contract import FakeAdapter


class SyncAdapter(FakeAdapter):
    """FakeAdapter + lista kart, jak w StudioAdapter.list_cards."""
    def __init__(self, root: Path, writes: bool = False):
        super().__init__(root)
        self.settings.allow_production_writes = writes
        self.settings.queue = self.queue
        self.ready = True

    def get(self, post_id: str, channel: str = "instagram") -> dict:
        card = super().get(post_id, channel)
        card["phone_ready"] = self.ready
        return card

    def list_cards(self, **_) -> dict:
        return {"items": [{"post_id": p.name, **self.get(p.name)} for p in sorted(self.queue.iterdir())]}


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.calls: list[str] = []

    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def service(self, writes=False, live_error=""):
        self.adapter = SyncAdapter(self.tmp, writes)
        self.adapter.queue.mkdir(parents=True, exist_ok=True)
        self.mobile = MobilePackages(self.adapter)
        snap = lambda b: (self.calls.append(f"live:{b}"), {"kiedy": "2026-09-27T20:00:00", "tiktok": [{}, {}], "meta": [{}], "blad_tiktok": live_error, "blad_meta": ""})[1]
        persist_live = lambda s, root: (self.calls.append("persist_live"), {"live_ok": 2})[1]
        persist_jsonl = lambda root: (self.calls.append("persist_jsonl"), {"n": 3, "potwierdzone": 1, "bledy": 0})[1]
        return SyncService(self.adapter, self.mobile, live_snapshot=snap, persist_live=persist_live, persist_jsonl=persist_jsonl, live_age=lambda b: "2026-09-27T20:00:00")

    def run_full(self, sync):
        sync.start_full(trigger="test"); sync.wait(10)
        return sync.status()

    def test_full_sync_reads_both_brands_and_never_writes_queue_in_preview(self):
        st = self.run_full(self.service(writes=False))
        self.assertEqual(self.calls, ["live:atlet", "live:rigger"])
        self.assertTrue(st["ok"]); self.assertFalse(st["running"])
        self.assertEqual([s["state"] for s in st["steps"]], ["ok", "ok", "ok", "ok"])
        self.assertIn("TikTok 2 · Meta 1", st["steps"][1]["detail"])
        persisted = json.loads((self.adapter.settings.data_dir / "sync-state.json").read_text(encoding="utf-8"))
        self.assertEqual(persisted["trigger"], "test")

    def test_writes_mode_persists_like_studio_button(self):
        self.run_full(self.service(writes=True))
        self.assertEqual(self.calls, ["persist_jsonl", "live:atlet", "persist_live", "live:rigger", "persist_live"])

    def test_busy_browser_profile_is_skipped_and_platform_error_is_reported(self):
        sync = self.service(live_error="brak logowania")
        (self.adapter.settings.data_dir / "locks").mkdir(exist_ok=True)
        (self.adapter.settings.data_dir / "locks" / "chrome-rigger-9333.json").write_text("{}", encoding="utf-8")
        st = self.run_full(sync)
        states = {s["id"]: s["state"] for s in st["steps"]}
        self.assertEqual((states["live-atlet"], states["live-rigger"]), ("error", "skipped"))
        self.assertFalse(st["ok"]); self.assertIn("live-atlet", st["error"])
        self.assertEqual(self.calls, ["live:atlet"])

    def test_second_start_while_running_does_not_start_twice(self):
        sync = self.service()
        sync.state["running"] = True
        sync.start_full()
        self.assertEqual(self.calls, [])

    def test_overview_reports_live_calendar_age(self):
        ov = self.service().overview()
        self.assertEqual(ov["live"], {"atlet": "2026-09-27T20:00:00", "rigger": "2026-09-27T20:00:00"})
        self.assertFalse(ov["writes"])


class PhoneSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.adapter = SyncAdapter(self.tmp)
        self.mobile = MobilePackages(self.adapter)
        self.adapter.add("post-1")
        self.mobile.export("post-1")

    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def cards(self): return self.adapter.list_cards()["items"]

    def index(self): return json.loads((self.mobile.root / "index.json").read_text(encoding="utf-8"))["packages"]

    def test_changed_content_is_reexported_automatically(self):
        self.adapter.revision = "c" * 64
        r = self.mobile.sync(self.cards())
        self.assertEqual((r["refreshed"], r["hidden"], r["packages"]), (1, 0, 1))
        self.assertEqual(self.index()[0]["content_revision"], "c" * 64)

    def test_published_on_instagram_disappears_from_phone_until_exported_again(self):
        self.adapter.ready = False
        r = self.mobile.sync(self.cards())
        self.assertEqual((r["hidden"], r["packages"]), (1, 0))
        self.assertEqual(self.index(), [])
        self.adapter.ready = True
        self.mobile.export("post-1")
        self.assertEqual(len(self.index()), 1)

    def test_sync_never_exports_packages_that_were_not_sent_to_phone(self):
        (self.adapter.queue / "post-2").mkdir()
        (self.adapter.queue / "post-2" / "clip.mp4").write_bytes(b"x")
        r = self.mobile.sync(self.cards())
        self.assertEqual(r["packages"], 1)


if __name__ == "__main__":
    unittest.main()
