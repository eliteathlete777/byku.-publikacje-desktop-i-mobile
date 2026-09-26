"""Kontrakt Desktop ↔ Mobile bez zależności od Studio: fałszywy adapter, prawdziwy eksport i prawdziwy kod telefonu."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from backend.config import Settings
from backend.hostinger_sync import HostingerSync
from backend.mobile_packages import MobilePackages

REPO = Path(__file__).resolve().parents[2]


class FakeAdapter:
    def __init__(self, root: Path):
        self.settings = SimpleNamespace(data_dir=root / "data")
        self.settings.data_dir.mkdir()
        self.queue = root / "queue"
        self.revision = "a" * 64

    def add(self, post_id: str, brand: str = "atlet"):
        folder = self.queue / post_id
        folder.mkdir(parents=True)
        (folder / "clip.mp4").write_bytes(b"video" * 4000)
        (folder / "miniaturka.png").write_bytes(b"\x89PNG fake")
        (folder / "post.json").write_text("{}", encoding="utf-8")
        self.brand = brand

    def folder_for(self, post_id: str) -> Path:
        return self.queue / post_id

    def get(self, post_id: str, channel: str = "instagram") -> dict:
        return {"brand": self.brand, "phone_ready": True, "name": "Pompki na poręczach", "local_target_at": "2026-09-27 19:07",
                "content": {"revision": self.revision, "description": "Nikt cię nie uratuje. Byku 💪", "hashtags": "#bykurigger #system"},
                "channels": {"tiktok": {"platform_evidence": "published"}, "instagram": {"platform_evidence": "unknown"}}}


class FakeFTP:
    def __init__(self, target: Path):
        self.target, self.stored = target, []

    def mkd(self, path): (self.target / path).mkdir(parents=True, exist_ok=True)

    def storbinary(self, cmd, stream):
        rel = cmd.split(" ", 1)[1]
        (self.target / rel).write_bytes(stream.read())
        self.stored.append(rel)

    def quit(self): pass


class MobileContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.adapter = FakeAdapter(self.tmp)
        self.mobile = MobilePackages(self.adapter)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_export_writes_index_with_newest_revision(self):
        self.adapter.add("post-1")
        self.mobile.export("post-1")
        self.adapter.revision = "b" * 64
        (self.adapter.queue / "post-1" / "clip.mp4").write_bytes(b"nowa wersja")
        self.mobile.export("post-1")
        index = json.loads((self.mobile.root / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["schema_version"], 1)
        self.assertEqual(len(index["packages"]), 1)
        entry = index["packages"][0]
        manifest = json.loads((self.mobile.root / entry["manifest_url"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["content_revision"], "b" * 64)
        self.assertEqual(set(manifest), {"schema_version", "post_id", "brand", "content_revision", "exported_at", "channel", "title", "target_at", "source_state", "files"})
        self.assertEqual((manifest["title"], manifest["target_at"]), ("Pompki na poręczach", "2026-09-27 19:07"))
        caption = (self.mobile.root / entry["manifest_url"]).parent / "podpis.txt"
        self.assertEqual(caption.read_text(encoding="utf-8"), "Nikt cię nie uratuje. Byku 💪\n\n#bykurigger #system\n")
        self.assertIn("podpis.txt", {f["name"] for f in manifest["files"]})

    def test_import_accepts_mobile_event_names_and_aliases(self):
        events = [{"event_id": "e1", "type": "description_copied", "post_id": "p", "brand": "atlet"},
                  {"event_id": "e2", "type": "hashtags_copied", "post_id": "p", "brand": "atlet"},
                  {"event_id": "e3", "type": "manual_hook", "post_id": "p", "brand": "atlet", "value": True},
                  {"event_id": "e4", "type": "caption_copied", "post_id": "p", "brand": "atlet"},
                  {"event_id": "e5", "type": "instagram_opened", "post_id": "p", "brand": "atlet"},
                  {"event_id": "e6", "type": "downloaded", "post_id": "p", "brand": "atlet", "files": ["clip.mp4"]},
                  {"event_id": "e7", "type": "hacked", "post_id": "p", "brand": "atlet"}]
        result = self.mobile.import_events({"schema_version": 1, "events": events})
        self.assertEqual((result["accepted"], result["skipped"]), (6, 1))
        again = self.mobile.import_events({"events": events})
        self.assertEqual(again["accepted"], 0)
        lines = [json.loads(x) for x in (self.mobile.root / "mobile-events.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(lines[3]["type"], "description_copied")
        self.assertTrue(lines[2]["value"])
        with self.assertRaises(ValueError): self.mobile.import_events({"schema_version": 2, "events": []})

    def test_hostinger_publish_uploads_changes_and_index_last(self):
        self.adapter.add("post-1")
        self.mobile.export("post-1")
        remote = self.tmp / "remote"; remote.mkdir()
        ftp = FakeFTP(remote)
        settings = Settings(self.tmp, self.tmp, self.tmp, self.adapter.settings.data_dir, "127.0.0.1", 0, "sandbox", False, False, "Europe/Warsaw",
                            {"enabled": True, "host": "ftp.test", "user": "u", "remote_dir": "public_html/publikacje/paczki"})
        sync = HostingerSync(settings, self.mobile.root, ftp_factory=lambda: ftp)
        first = sync.publish()
        self.assertEqual(ftp.stored[-1], "public_html/publikacje/paczki/index.json")
        self.assertTrue(any(x.endswith("manifest.json") for x in ftp.stored))
        self.assertFalse(any(x.endswith(".zip") or "mobile-events" in x for x in ftp.stored))
        second = sync.publish()
        self.assertEqual(second["uploaded"], 1)  # tylko index.json
        self.assertEqual(second["skipped"], first["uploaded"] - 1)
        disabled = HostingerSync(Settings(self.tmp, self.tmp, self.tmp, self.adapter.settings.data_dir, "127.0.0.1", 0, "sandbox", False, False, "Europe/Warsaw"), self.mobile.root)
        with self.assertRaises(PermissionError): disabled.publish()

    @unittest.skipUnless(shutil.which("node"), "brak Node.js")
    def test_mobile_code_reads_desktop_export_end_to_end(self):
        self.adapter.add("post-1", "rigger")
        self.mobile.export("post-1")
        handler = partial(SimpleHTTPRequestHandler, directory=str(self.mobile.root))
        handler.log_message = lambda *a: None
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            src = (REPO / "mobile" / "src").as_uri()
            script = f"""
import {{ refreshPackages }} from "{src}/sync.js";
import {{ validateManifest, resolveFileUrl, sha256Hex, isSourceMedia }} from "{src}/domain.js";
const r = await refreshPackages({{ indexUrl: "http://127.0.0.1:{server.server_port}/index.json", brand: "rigger", existing: [] }});
const m = r.manifests[0]; const v = validateManifest(m, "rigger");
let checked = 0;
for (const f of m.files) {{ const res = await fetch(resolveFileUrl(m._manifest_url, f.name)); const sha = await sha256Hex(await res.blob()); if (sha !== f.sha256) throw Error("SHA " + f.name); checked++; }}
console.log(JSON.stringify({{ ok: v.ok, errors: v.errors, state: r.results[0].state, checked, media: m.files.filter(x => isSourceMedia(x.name)).length }}));
"""
            out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            result = json.loads(out.stdout.strip().splitlines()[-1])
            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual(result["state"], "newer")
            self.assertGreaterEqual(result["checked"], 5)
            self.assertEqual(result["media"], 1)
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
