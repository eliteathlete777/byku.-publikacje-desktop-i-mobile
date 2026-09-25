from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from backend.config import Settings, load_settings
from backend.content_service import ContentService, RevisionConflict
from backend.job_service import JobService
from backend.mobile_packages import MobilePackages
from backend.publication_view import channel_view, next_action
from backend.studio_adapter import StudioAdapter
from learning.events import emit, import_jsonl
from learning.store import LearningStore
from learning.lesson_service import LessonService


class CoreTests(unittest.TestCase):
    def make_sandbox(self, root: Path):
        source=Path(r"C:\Users\DELL\Desktop\aplikacje\05_APLIKACJE_SKRYPTY\byku-publisher-desktop")
        queue=root/"queue"; data=root/"data"; queue.mkdir(); data.mkdir()
        settings=Settings(source,source/"studio-kolejka",queue,data,"127.0.0.1",0,"sandbox",False,False,"Europe/Warsaw")
        adapter=StudioAdapter(settings)
        import sys
        if str(source) not in sys.path: sys.path.insert(0,str(source))
        from studio.rdzen.magazyn import zapisz_paczke
        from studio.rdzen.model import Paczka
        folder=queue/"test-post"; folder.mkdir()
        (folder/"clip.mp4").write_bytes(b"v"*12000)
        from PIL import Image
        Image.effect_noise((128,128),64).convert("RGB").save(folder/"miniaturka.png")
        (folder/"opis.txt").write_text("Stary opis\n\n#stary\nstary\n",encoding="utf-8")
        package=Paczka(post_id="test-post",marka="atlet",status="zaplanowany",nazwa_wideo="clip.mp4",opis="Stary opis",hashtagi="#stary",lokalizacja="Katowice",termin="2026-10-10 18:45")
        package.platformy_stan["tiktok"]["stan"]="potwierdzony"
        zapisz_paczke(folder,package)
        return adapter, LearningStore(data/"learning.sqlite3")

    def test_live_is_not_manual_check(self):
        view = channel_view({"stan": "potwierdzony", "haczyk": True}, manual_checked=False)
        self.assertEqual(view["platform_evidence"], "scheduled")
        self.assertFalse(view["manual_checked"])

    def test_instagram_does_not_change_facebook(self):
        card = {"archived": False, "assets": {"missing": []}, "content": {"description": "x", "approved": True}, "channels": {"instagram": channel_view({"dowod":"published"}, manual_checked=True), "facebook": channel_view({}, manual_checked=False)}}
        self.assertEqual(next_action(card, "instagram")["code"], "done")
        self.assertNotEqual(next_action(card, "facebook")["code"], "done")

    def test_active_job_has_priority_over_archive(self):
        card = {"archived": True, "assets":{"missing":[]}, "content":{"description":"x","approved":True}, "channels":{"tiktok":channel_view({"delivery":"awaiting_user"})}}
        self.assertEqual(next_action(card, "tiktok")["code"], "show_progress")

    def test_learning_deduplicates(self):
        with tempfile.TemporaryDirectory() as td:
            store=LearningStore(Path(td)/"learning.sqlite3")
            event={"event_id":"same","stage":"caption_edited","occurred_at":"2026-09-24T00:00:00+00:00"}
            self.assertTrue(store.add_event(event)); self.assertFalse(store.add_event(event))
            self.assertEqual(len(store.recent_events()),1)

    def test_profile_lock_is_shared_by_instagram_and_facebook(self):
        from backend.job_service import PROFILE_RESOURCE
        self.assertEqual(PROFILE_RESOURCE[("atlet","instagram")], PROFILE_RESOURCE[("atlet","facebook")])
        self.assertNotEqual(PROFILE_RESOURCE[("atlet","tiktok")], PROFILE_RESOURCE[("rigger","tiktok")])

    def test_content_persists_and_conflict_preserves_proposal(self):
        with tempfile.TemporaryDirectory() as td:
            adapter,store=self.make_sandbox(Path(td)); service=ContentService(adapter,store)
            before=adapter.get("test-post")
            saved=service.save("test-post",expected_revision=before["revision"],description="Nowy opis",hashtags="",location="Warszawa",approve=True)
            self.assertEqual(saved["content"]["description"],"Nowy opis")
            self.assertEqual(saved["content"]["hashtags"],"")
            restarted=StudioAdapter(adapter.settings).get("test-post")
            self.assertEqual(restarted["content"]["location"],"Warszawa")
            with self.assertRaises(RevisionConflict) as caught:
                service.save("test-post",expected_revision=before["revision"],description="Moja niezapisana propozycja",hashtags="",location="",approve=False)
            self.assertEqual(caught.exception.proposal["description"],"Moja niezapisana propozycja")

    def test_manual_check_is_independent_per_channel(self):
        with tempfile.TemporaryDirectory() as td:
            adapter,_=self.make_sandbox(Path(td)); before=adapter.get("test-post")
            after=adapter.set_manual_check("test-post","instagram",True,before["revision"])
            self.assertTrue(after["channels"]["instagram"]["manual_checked"])
            self.assertFalse(after["channels"]["facebook"]["manual_checked"])

    def test_phone_package_contains_ready_copy_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            adapter,_=self.make_sandbox(Path(td)); mobile=MobilePackages(adapter)
            self.assertEqual(len(mobile.candidates("atlet")),1)
            result=mobile.export("test-post")
            package_dir=mobile.root/"atlet"/"do-instagrama"/f"test-post-{result['manifest']['content_revision'][:16]}"
            self.assertEqual((package_dir/"opis-do-skopiowania.txt").read_text(encoding="utf-8").strip(),"Stary opis")
            self.assertTrue((package_dir/"hashtagi.txt").is_file())
            self.assertEqual(result["manifest"]["source_state"]["tiktok"],"scheduled")

    def test_mobile_events_are_deduplicated_and_do_not_touch_package(self):
        with tempfile.TemporaryDirectory() as td:
            adapter,_=self.make_sandbox(Path(td)); mobile=MobilePackages(adapter)
            before=adapter.get("test-post")["revision"]
            payload={"events":[{"event_id":"m1","type":"sent","post_id":"test-post","brand":"atlet"},{"event_id":"m1","type":"sent"},{"event_id":"bad","type":"archive"}]}
            result=mobile.import_events(payload)
            self.assertEqual((result["accepted"],result["skipped"]),(1,2))
            self.assertEqual(adapter.get("test-post")["revision"],before)

    def test_lesson_requires_test_and_can_be_reverted(self):
        with tempfile.TemporaryDirectory() as td:
            service=LessonService(LearningStore(Path(td)/"learning.sqlite3"))
            lesson=service.create({"kind":"process","brand":"atlet","problem":"Błąd etapu","solution":"Jawna naprawa","test":{"status":"ok"}})
            self.assertEqual(service.set_status(lesson["lesson_id"],"active")["status"],"active")
            self.assertEqual(service.set_status(lesson["lesson_id"],"reverted")["status"],"reverted")


if __name__ == "__main__": unittest.main()
