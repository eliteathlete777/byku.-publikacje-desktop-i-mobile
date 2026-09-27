"""Telefon bez Hostingera: serwer telefonu, wybór materiału do paczki i tytuły kart."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from backend.mobile_packages import MobilePackages, phone_files
from backend.phone_server import PhoneServer
from backend.publication_view import headline
from tests.test_mobile_contract import FakeAdapter


def fetch(url: str, *, data: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as r: return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


class PhoneFilesTests(unittest.TestCase):
    def setUp(self): self.tmp = Path(tempfile.mkdtemp())
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def test_reel_gets_exactly_one_video_preferring_hd(self):
        for name in ("13.mp4", "13-hd.mp4", "13-hd.part.mp4", "miniaturka.png", "opis.txt", "post.json"):
            (self.tmp / name).write_bytes(b"x")
        self.assertEqual(sorted(p.name for p in phone_files(self.tmp)), ["13-hd.mp4", "miniaturka.png", "opis.txt"])

    def test_reel_without_hd_keeps_original_and_carousel_keeps_all_slides(self):
        (self.tmp / "klip.mov").write_bytes(b"x")
        self.assertEqual([p.name for p in phone_files(self.tmp)], ["klip.mov"])
        (self.tmp / "klip.mov").unlink()
        for name in ("slajd-01.jpg", "slajd-02.webp", "slajd-03.png"): (self.tmp / name).write_bytes(b"x")
        self.assertEqual(len(phone_files(self.tmp)), 3)


class HeadlineTests(unittest.TestCase):
    def test_first_paragraph_joined_and_cleaned(self):
        self.assertEqual(headline("🔥 Trening na magazynie bez\nwymówek.\n\nKiedy inni jedzą"), "Trening na magazynie bez wymówek.")
        self.assertEqual(headline("🔥 Pompki na klatce?!\n🔥\n\nSchody w bloku"), "Pompki na klatce?!")

    def test_long_paragraph_cut_at_first_sentence_and_fallbacks(self):
        self.assertEqual(headline("🔥 Rok 2023, a krata na brzuchu siedzi! 🔥 Trening w każdych warunkach. Kalistenika to klucz do siły."), "Rok 2023, a krata na brzuchu siedzi!")
        self.assertEqual(headline("🔥 przypinam kratę do zwyżki!"), "Przypinam kratę do zwyżki!")
        self.assertEqual(headline("#tylko #hashtagi", "13.mp4"), "13.mp4")
        self.assertEqual(headline("", "13.mp4"), "13.mp4")


class PhoneServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.adapter = FakeAdapter(self.tmp)
        self.mobile = MobilePackages(self.adapter)
        self.adapter.add("post-1")
        (self.adapter.queue / "post-1" / "clip-hd.mp4").write_bytes(b"hd" * 5000)
        self.manifest = self.mobile.export("post-1")["manifest"]
        (self.mobile.root / "tajne.txt").write_text("nie dla telefonu", encoding="utf-8")
        app = self.tmp / "mobile"; app.mkdir()
        (app / "index.html").write_text("<!doctype html><title>BYKU</title>", encoding="utf-8")
        (app / "sw.js").write_text("// sw", encoding="utf-8")
        self.server = PhoneServer(app, self.mobile.root, self.mobile.import_events, port=0).start()
        self.base = f"http://127.0.0.1:{self.server.port}/"

    def tearDown(self):
        self.server.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_export_ships_one_hd_video_and_headline(self):
        names = {f["name"] for f in self.manifest["files"]}
        self.assertIn("clip-hd.mp4", names)
        self.assertNotIn("clip.mp4", names)
        self.assertEqual(self.manifest["media_type"], "reel")
        self.assertIn("headline", self.manifest)

    def test_serves_app_index_and_package_files(self):
        code, headers, body = fetch(self.base)
        self.assertEqual((code, body[:15]), (200, b"<!doctype html>"))
        self.assertEqual(headers["Cache-Control"], "no-store")
        code, _, body = fetch(self.base + "paczki/index.json")
        entry = json.loads(body)["packages"][0]
        code, headers, _ = fetch(self.base + "paczki/" + entry["manifest_url"])
        self.assertEqual(code, 200)
        video = entry["manifest_url"].rsplit("/", 1)[0] + "/clip-hd.mp4"
        code, headers, body = fetch(self.base + "paczki/" + video, headers={"Range": "bytes=0-9"})
        self.assertEqual((code, len(body), headers["Content-Range"]), (206, 10, "bytes 0-9/10000"))
        self.assertEqual(headers["Content-Type"], "video/mp4")

    def test_blocks_everything_outside_the_phone_contract(self):
        for path in ("paczki/tajne.txt", "paczki/../config.json", "paczki/atlet/do-instagrama/..%2F..%2Ftajne.txt/x",
                     "paczki/mobile-events.jsonl", "paczki/post-1-" + "a" * 16 + ".zip", "api/publications", "../run.py", "%2e%2e/run.py"):
            self.assertEqual(fetch(self.base + path)[0], 404, path)
        self.assertEqual(fetch(self.base + "api/publications/x/manual-check", data=b"{}")[0], 404)

    def test_ping_and_events_are_deduplicated(self):
        code, _, body = fetch(self.base + "api/ping")
        self.assertEqual((code, json.loads(body)["packages"]), (200, 1))
        payload = json.dumps({"schema_version": 1, "events": [{"event_id": "e1", "type": "manual_hook", "value": True, "post_id": "post-1", "brand": "atlet"}]}).encode()
        headers = {"Content-Type": "application/json"}
        self.assertEqual(json.loads(fetch(self.base + "api/events", data=payload, headers=headers)[2])["accepted"], 1)
        self.assertEqual(json.loads(fetch(self.base + "api/events", data=payload, headers=headers)[2])["accepted"], 0)
        self.assertEqual(fetch(self.base + "api/events", data=b"[1]", headers=headers)[0], 400)
        self.assertEqual(self.mobile.events("post-1")[0]["type"], "manual_hook")


if __name__ == "__main__":
    unittest.main()
