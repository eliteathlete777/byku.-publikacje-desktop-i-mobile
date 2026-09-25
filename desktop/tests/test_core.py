from __future__ import annotations

import io
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from dataclasses import replace
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import contract
from backend.config import Settings
from backend.content_service import ContentService, RevisionConflict, normalize_hashtags
from backend.core import CoreUnavailable, FallbackCore, load_core
from backend.mobile_packages import MobilePackages, TransferError
from backend.publication_view import channel_view, next_action
from backend.schedule_service import ScheduleService
from backend.studio_adapter import StudioAdapter
from learning.events import emit
from learning.lesson_service import LessonService
from learning.store import LearningStore
from tools.make_sandbox import build

CASES = json.loads((ROOT.parent / "contract" / "fixtures" / "cases.json").read_text(encoding="utf-8"))


def make_settings(root: Path, **kw) -> Settings:
    queue, data = root / "queue", root / "data"
    queue.mkdir(exist_ok=True); data.mkdir(exist_ok=True)
    base = Settings(root / "brak-studio", root / "brak-studio" / "studio-kolejka", queue, data,
                    "127.0.0.1", 0, "sandbox", False, False, "Europe/Warsaw", core="fallback")
    return replace(base, **kw)


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.settings = make_settings(self.root)
        build(self.settings.sandbox_queue)
        self.adapter = StudioAdapter(self.settings, core=FallbackCore())
        self.store = LearningStore(self.settings.data_dir / "learning.sqlite3")

    def tearDown(self):
        self.tmp.cleanup()


class ContractTests(unittest.TestCase):
    def test_shared_fixtures(self):
        for case in CASES:
            with self.subTest(case["name"]):
                codes = {e["code"] for e in contract.validate(case["manifest"])}
                if case["valid"]:
                    self.assertEqual(codes, set())
                else:
                    self.assertIn(case["error"], codes)


class ViewTests(unittest.TestCase):
    def test_live_is_not_manual_check(self):
        view = channel_view({"stan": "potwierdzony", "haczyk": True}, manual_checked=False)
        self.assertEqual(view["platform_evidence"], "scheduled")
        self.assertFalse(view["manual_checked"])

    def test_instagram_does_not_change_facebook(self):
        card = {"archived": False, "assets": {"missing": []}, "content": {"description": "x", "approved": True},
                "channels": {"instagram": channel_view({"dowod": "published"}, manual_checked=True), "facebook": channel_view({}, manual_checked=False)}}
        self.assertEqual(next_action(card, "instagram")["code"], "done")
        self.assertNotEqual(next_action(card, "facebook")["code"], "done")

    def test_active_job_has_priority_over_archive(self):
        card = {"archived": True, "assets": {"missing": []}, "content": {"description": "x", "approved": True},
                "channels": {"tiktok": channel_view({"delivery": "awaiting_user"})}}
        self.assertEqual(next_action(card, "tiktok")["code"], "show_progress")

    def test_profile_lock_is_shared_by_instagram_and_facebook(self):
        from backend.job_service import PROFILE_RESOURCE
        self.assertEqual(PROFILE_RESOURCE[("atlet", "instagram")], PROFILE_RESOURCE[("atlet", "facebook")])
        self.assertNotEqual(PROFILE_RESOURCE[("atlet", "tiktok")], PROFILE_RESOURCE[("rigger", "tiktok")])

    def test_hashtags_normalized_and_deduplicated(self):
        self.assertEqual(normalize_hashtags("byku, #Byku  #trening #"), "#byku #trening")
        self.assertEqual(normalize_hashtags("   "), "")


class CoreSafetyTests(unittest.TestCase):
    def test_production_never_uses_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(CoreUnavailable):
                load_core(Path(td), "production", "auto")
            with self.assertRaises(CoreUnavailable):
                load_core(Path(td), "production", "fallback")

    def test_production_without_writes_blocks_changes(self):
        with tempfile.TemporaryDirectory() as td:
            settings = make_settings(Path(td))
            build(settings.sandbox_queue)
            prod = replace(settings, mode="production", production_queue=settings.sandbox_queue)
            adapter = StudioAdapter(prod, core=FallbackCore())
            card = adapter.get("atlet-pompki-porecze")
            with self.assertRaises(PermissionError):
                ContentService(adapter, LearningStore(prod.data_dir / "l.sqlite3")).save(
                    "atlet-pompki-porecze", expected_revision=card["revision"], description="x", hashtags="", location="")
            with self.assertRaises(PermissionError):
                adapter.set_manual_check("atlet-pompki-porecze", "instagram", True, card["revision"])
            with self.assertRaises(PermissionError):
                ScheduleService(adapter).apply([{"post_id": "atlet-pompki-porecze", "after": "2026-10-01 18:45"}])
            self.assertEqual(adapter.get("atlet-pompki-porecze")["revision"], card["revision"])

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = StudioAdapter(make_settings(Path(td)), core=FallbackCore())
            for bad in ("../x", "..", "a/b", "a\\b", ".ukryty"):
                with self.assertRaises(ValueError):
                    adapter.folder_for(bad)


class ContentTests(Sandbox):
    def test_content_persists_and_conflict_preserves_proposal(self):
        service = ContentService(self.adapter, self.store)
        before = self.adapter.get("atlet-pompki-porecze")
        saved = service.save("atlet-pompki-porecze", expected_revision=before["revision"], description="Nowy opis",
                             hashtags="", location="Warszawa", approve=True)
        self.assertEqual(saved["content"]["description"], "Nowy opis")
        self.assertEqual(saved["content"]["hashtags"], "")
        self.assertTrue(saved["content"]["approved"])
        restarted = StudioAdapter(self.settings, core=FallbackCore()).get("atlet-pompki-porecze")
        self.assertEqual(restarted["content"]["location"], "Warszawa")
        with self.assertRaises(RevisionConflict) as caught:
            service.save("atlet-pompki-porecze", expected_revision=before["revision"], description="Moja propozycja",
                         hashtags="", location="", approve=False)
        self.assertEqual(caught.exception.proposal["description"], "Moja propozycja")

    def test_edit_after_approval_requires_new_approval(self):
        service = ContentService(self.adapter, self.store)
        card = self.adapter.get("atlet-pompki-porecze")
        self.assertTrue(card["content"]["approved"])
        edited = service.save("atlet-pompki-porecze", expected_revision=card["revision"], description="Zmiana",
                              hashtags="#a", location="", approve=False)
        self.assertFalse(edited["content"]["approved"])

    def test_approved_change_becomes_style_lesson(self):
        service = ContentService(self.adapter, self.store)
        card = self.adapter.get("rigger-kratownica-narodowy")
        service.save(card["post_id"], expected_revision=card["revision"], description="Nowy styl, byku.",
                     hashtags="#rigger", location="", approve=True)
        styles = [x for x in self.store.lessons("style") if x["brand"] == "rigger"]
        self.assertEqual(len(styles), 1)
        self.assertEqual(styles[0]["status"], "active")

    def test_thumbnail_replace_checks_format_and_revision(self):
        from tools.make_sandbox import png
        service = ContentService(self.adapter, self.store)
        card = self.adapter.get("atlet-gumy-plecy")
        with self.assertRaises(ValueError):
            service.replace_thumbnail(card["post_id"], expected_revision=card["revision"], data=b"not png")
        updated = service.replace_thumbnail(card["post_id"], expected_revision=card["revision"], data=png((1, 2, 3)))
        self.assertNotEqual(updated["revision"], card["revision"])
        with self.assertRaises(RevisionConflict):
            service.replace_thumbnail(card["post_id"], expected_revision=card["revision"], data=png((1, 2, 3)))

    def test_manual_check_is_independent_per_channel(self):
        before = self.adapter.get("atlet-gumy-plecy")
        after = self.adapter.set_manual_check("atlet-gumy-plecy", "instagram", True, before["revision"])
        self.assertTrue(after["channels"]["instagram"]["manual_checked"])
        self.assertFalse(after["channels"]["facebook"]["manual_checked"])
        self.assertEqual(after["channels"]["instagram"]["platform_evidence"], "unknown")  # haczyk ≠ dowód


class ScheduleTests(Sandbox):
    def test_apply_undo_and_validation(self):
        schedule = ScheduleService(self.adapter)
        with self.assertRaises(ValueError):
            schedule.apply([{"post_id": "atlet-karuzela-plan", "after": "jutro"}])
        schedule.apply([{"post_id": "atlet-karuzela-plan", "after": "2026-10-05 19:15"}])
        self.assertEqual(self.adapter.get("atlet-karuzela-plan")["local_target_at"], "2026-10-05 19:15")
        schedule.undo()
        self.assertEqual(self.adapter.get("atlet-karuzela-plan")["local_target_at"], "")
        self.assertFalse(schedule.can_undo())

    def test_proposals_do_not_collide(self):
        variants = ScheduleService(self.adapter).propose("atlet", "2026-10-05")
        self.assertEqual({v["id"] for v in variants}, {"calm", "regular", "intensive"})
        for variant in variants:
            targets = [c["after"] for c in variant["changes"]]
            self.assertEqual(len(targets), len(set(targets)))


class FakeServer:
    """Udaje API serwera mobilnego (Hostinger) dla testu transferu."""

    def __init__(self):
        self.files, self.commits = {}, []

    def __call__(self, request, timeout=0):
        url, method = request.full_url, request.get_method()
        if request.get_header("Authorization") != "Bearer sekret":
            raise urllib.error.HTTPError(url, 401, "x", {}, io.BytesIO(b'{"error":"brak"}'))
        if "/api/upload/file" in url:
            import hashlib
            self.files[url] = request.data
            assert hashlib.sha256(request.data).hexdigest() == request.get_header("X-sha256")
            body = {"ok": True}
        elif url.endswith("/api/upload/commit"):
            manifest = json.loads(request.data)
            self.commits.append(manifest)
            body = {"ok": True, "state": "current"}
        else:
            body = {"events": [{"event_id": "e1", "type": "manual_check", "post_id": "x", "brand": "atlet"}]}
        return io.BytesIO(json.dumps(body).encode())


class MobileTests(Sandbox):
    def test_candidates_priority_and_exclusions(self):
        mobile = MobilePackages(self.adapter)
        ids = [c["post_id"] for c in mobile.candidates("all")]
        self.assertIn("atlet-pompki-porecze", ids)
        self.assertIn("atlet-gumy-plecy", ids)  # TikTok zaplanowany
        self.assertNotIn("rigger-demontaz-noc", ids)  # Instagram już opublikowany
        self.assertNotIn("atlet-szkic-bez-opisu", ids)  # TikTok bez dowodu
        self.assertNotIn("rigger-archiwum", ids)
        self.assertLess(ids.index("atlet-pompki-porecze"), ids.index("atlet-gumy-plecy"))  # opublikowany TikTok pierwszy

    def test_phone_package_is_valid_contract_with_checksums(self):
        mobile = MobilePackages(self.adapter)
        result = mobile.export("atlet-pompki-porecze")
        manifest = result["manifest"]
        self.assertEqual(contract.validate(manifest), [])
        self.assertEqual(manifest["transfer"], {"from": "tiktok", "to": "instagram", "tiktok": "published", "instagram": "pending"})
        self.assertEqual(manifest["package_id"], "atlet--atlet-pompki-porecze")
        check = mobile.verify_dir(Path(result["dir"]))
        self.assertTrue(check["ok"], check["errors"])
        package_dir = Path(result["dir"])
        self.assertEqual((package_dir / "opis-do-skopiowania.txt").read_text(encoding="utf-8").strip(), manifest["caption"])
        (package_dir / "film.mp4").write_bytes(b"zmieniony")
        self.assertFalse(mobile.verify_dir(package_dir)["ok"])

    def test_carousel_package_has_ordered_slides(self):
        manifest = MobilePackages(self.adapter).export("atlet-karuzela-plan")["manifest"]
        slides = [f for f in manifest["files"] if f["role"] == "slide"]
        self.assertEqual([s["order"] for s in slides], [1, 2, 3])

    def test_not_ready_package_is_refused(self):
        with self.assertRaises(ValueError):
            MobilePackages(self.adapter).export("rigger-demontaz-noc")

    def test_export_does_not_change_queue(self):
        before = self.adapter.get("atlet-pompki-porecze")["revision"]
        MobilePackages(self.adapter).export("atlet-pompki-porecze")
        self.assertEqual(self.adapter.get("atlet-pompki-porecze")["revision"], before)

    def test_drive_transfer_copies_verified_package(self):
        drive = self.root / "GoogleDrive"
        drive.mkdir()
        mobile = MobilePackages(StudioAdapter(replace(self.settings, drive_sync_dir=drive), core=FallbackCore()))
        with self.assertRaises(ValueError):
            mobile.to_drive("atlet-pompki-porecze")  # najpierw paczka
        mobile.export("atlet-pompki-porecze")
        result = mobile.to_drive("atlet-pompki-porecze")
        target = Path(result["path"])
        self.assertEqual(target, drive / "atlet" / "do-instagrama" / "atlet-pompki-porecze")
        self.assertTrue(mobile.verify_dir(target)["ok"])

    def test_server_transfer_and_event_pull(self):
        fake = FakeServer()
        settings = replace(self.settings, mobile_server_url="https://byku.test", mobile_upload_token="sekret")
        mobile = MobilePackages(StudioAdapter(settings, core=FallbackCore()), opener=fake)
        mobile.export("atlet-pompki-porecze")
        result = mobile.to_server("atlet-pompki-porecze")
        self.assertTrue(result["ok"])
        self.assertEqual(len(fake.files), 4)
        self.assertEqual(fake.commits[0]["post_id"], "atlet-pompki-porecze")
        self.assertEqual(mobile.pull_server_events()["accepted"], 1)
        self.assertEqual(mobile.pull_server_events()["accepted"], 0)  # idempotentnie

    def test_server_not_configured_is_explicit(self):
        mobile = MobilePackages(self.adapter)
        mobile.export("atlet-pompki-porecze")
        with self.assertRaises(TransferError):
            mobile.to_server("atlet-pompki-porecze")

    def test_mobile_events_are_deduplicated_and_do_not_touch_package(self):
        mobile = MobilePackages(self.adapter)
        before = self.adapter.get("atlet-pompki-porecze")["revision"]
        payload = {"events": [{"event_id": "m1", "type": "manual_check", "post_id": "atlet-pompki-porecze", "brand": "atlet"},
                              {"event_id": "m1", "type": "manual_check"}, {"event_id": "bad", "type": "archive"}]}
        result = mobile.import_events(payload)
        self.assertEqual((result["accepted"], result["skipped"]), (1, 2))
        after = self.adapter.get("atlet-pompki-porecze")
        self.assertEqual(after["revision"], before)
        self.assertFalse(after["channels"]["instagram"]["manual_checked"])


class LearningTests(unittest.TestCase):
    def test_learning_deduplicates(self):
        with tempfile.TemporaryDirectory() as td:
            store = LearningStore(Path(td) / "learning.sqlite3")
            event = {"event_id": "same", "stage": "caption_edited", "occurred_at": "2026-09-24T00:00:00+00:00"}
            self.assertTrue(store.add_event(event)); self.assertFalse(store.add_event(event))
            self.assertEqual(len(store.recent_events()), 1)

    def test_lesson_requires_passed_test_and_can_be_reverted(self):
        with tempfile.TemporaryDirectory() as td:
            service = LessonService(LearningStore(Path(td) / "learning.sqlite3"))
            lesson = service.create({"kind": "process", "brand": "atlet", "problem": "Błąd etapu", "solution": "Jawna naprawa"})
            with self.assertRaises(ValueError):
                service.set_status(lesson["lesson_id"], "active")
            service.record_test(lesson["lesson_id"], "ok", "sprawdzone ręcznie")
            self.assertEqual(service.set_status(lesson["lesson_id"], "active")["status"], "active")
            self.assertEqual(service.set_status(lesson["lesson_id"], "reverted")["status"], "reverted")


class BrandTests(Sandbox):
    def test_drafts_respect_brand_limits_and_lint(self):
        from backend.brand_service import BrandService
        brands = BrandService(self.settings.data_dir, self.store)
        drafts = brands.draft("rigger", "p1", "Kratownica w górę " * 30)
        self.assertEqual(len(drafts), 3)
        for d in drafts:
            self.assertLessEqual(len(d["description"]), 250)
            self.assertTrue(d["hashtags"].startswith("#rigger #backstage #bykurigger"))
        notes = brands.lint("rigger", "Kup mój ebook", " ".join(f"#t{i}" for i in range(31)))
        texts = " ".join(n["text"] for n in notes)
        self.assertIn("ebook", texts)
        self.assertIn("maks. 30", texts)

    def test_brand_update_persists_and_validates(self):
        from backend.brand_service import BrandService
        brands = BrandService(self.settings.data_dir, self.store)
        updated = brands.update("atlet", {"locations": ["Gliwice", " "], "fixed_hashtags": ["byku", "#byku"]})
        self.assertEqual(updated["locations"], ["Gliwice"])
        self.assertEqual(updated["fixed_hashtags"], ["#byku"])
        with self.assertRaises(ValueError):
            brands.update("atlet", {"caption_max": 5000})
        with self.assertRaises(ValueError):
            brands.get("inna")


class HttpTests(Sandbox):
    def setUp(self):
        super().setUp()
        import run
        self.app = run.App(self.settings, core=FallbackCore())
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), run.make_handler(self.app))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown(); self.server.server_close()
        super().tearDown()

    def call(self, path, body=None, headers=None, method=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method or ("POST" if data is not None else "GET"),
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_endpoints(self):
        code, body = self.call("/api/health")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["core"], "fallback")
        code, body = self.call("/api/publications?brand=all&archive=true")
        self.assertEqual(len(json.loads(body)["items"]), 7)
        code, _ = self.call("/api/publications/atlet-pompki-porecze/media/film.mp4", headers={"Range": "bytes=0-9"})
        self.assertEqual(code, 206)
        code, _ = self.call("/api/publications/atlet-pompki-porecze/media/..%2Fpost.json")
        self.assertIn(code, (400, 404))
        code, body = self.call("/api/publications/atlet-pompki-porecze/drafts", {})
        self.assertEqual(len(json.loads(body)["drafts"]), 3)
        code, body = self.call("/api/publications/atlet-pompki-porecze/phone-package", {"channel": "instagram"})
        self.assertEqual(code, 200)
        name = json.loads(body)["name"]
        code, _ = self.call(f"/api/mobile-packages/{name}")
        self.assertEqual(code, 200)
        code, body = self.call("/api/generator/open", {"brand": "atlet"})
        self.assertEqual(code, 501)  # brak rdzenia Studio → czytelny komunikat, nie cisza
        code, body = self.call("/api/publications/atlet-pompki-porecze/prepare-publication", {"channel": "instagram"})
        self.assertEqual(code, 423)  # allow_publication=false
        code, _ = self.call("/api/nieznane", {})
        self.assertEqual(code, 404)

    def test_foreign_origin_blocked(self):
        code, _ = self.call("/api/health", headers={"Origin": "https://zla-strona.test"})
        self.assertEqual(code, 403)


if __name__ == "__main__":
    unittest.main()
