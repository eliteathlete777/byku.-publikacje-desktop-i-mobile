from __future__ import annotations

import json
import mimetypes
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.config import load_settings
from backend.content_service import ContentService, RevisionConflict
from backend.job_service import JobService
from backend.legacy_bridge import LegacyBridge
from backend.mobile_packages import MobilePackages
from backend.schedule_service import ScheduleService
from backend.studio_adapter import StudioAdapter
from learning.store import LearningStore
from learning.lesson_service import LessonService

SETTINGS = load_settings()
ADAPTER = StudioAdapter(SETTINGS)
LEARNING = LearningStore(SETTINGS.data_dir / "learning.sqlite3")
CONTENT = ContentService(ADAPTER, LEARNING)
JOBS = JobService(ADAPTER, LEARNING)
SCHEDULE = ScheduleService(ADAPTER)
MOBILE = MobilePackages(ADAPTER)
LEGACY = LegacyBridge(ADAPTER)
LESSONS = LessonService(LEARNING)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(ROOT / "frontend"), **kwargs)
    def log_message(self, fmt, *args): pass
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'")
        super().end_headers()
    def json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def body(self):
        size = int(self.headers.get("Content-Length", 0)); return json.loads(self.rfile.read(size).decode("utf-8") or "{}")
    def do_GET(self):
        url = urllib.parse.urlparse(self.path); path = url.path.rstrip("/")
        try:
            if path == "/api/health": return self.json(200, {"ok": True, "mode": SETTINGS.mode, "writes": SETTINGS.allow_production_writes, "publication": SETTINGS.allow_publication})
            if path == "/api/publications":
                q = urllib.parse.parse_qs(url.query); brand=(q.get("brand") or ["atlet"])[0]; channel=(q.get("channel") or ["instagram"])[0]; archive=(q.get("archive") or ["false"])[0] == "true"
                return self.json(200, ADAPTER.list_cards(brand=brand, include_archive=archive, selected_channel=channel))
            if path.startswith("/api/publications/") and path.endswith("/capabilities"):
                return self.json(200, LEGACY.publication_capabilities(urllib.parse.unquote(path.split("/")[3])))
            if path.startswith("/api/publications/"):
                parts = path.split("/"); post_id = urllib.parse.unquote(parts[3])
                if len(parts) == 5 and parts[4] == "thumbnail":
                    file = ADAPTER.folder_for(post_id) / "miniaturka.png"
                    if not file.is_file(): return self.send_error(404)
                    data=file.read_bytes(); self.send_response(200); self.send_header("Content-Type","image/png"); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); return
                return self.json(200, ADAPTER.get(post_id))
            if path == "/api/schedule/proposals":
                q=urllib.parse.parse_qs(url.query); return self.json(200, {"variants": SCHEDULE.propose((q.get("brand") or ["atlet"])[0], (q.get("start") or [None])[0])})
            if path.startswith("/api/jobs/"): return self.json(200, JOBS.get(path.split("/")[-1]))
            if path == "/api/learning": return self.json(200, {"events": LEARNING.recent_events(), "lessons": LEARNING.lessons()})
            if path == "/api/mobile-candidates":
                q=urllib.parse.parse_qs(url.query); return self.json(200,{"items":MOBILE.candidates((q.get("brand") or ["all"])[0])})
            if path.startswith("/api/mobile-packages/"):
                name=Path(urllib.parse.unquote(path.split("/")[-1])).name; file=MOBILE.root/name
                if not file.is_file(): return self.send_error(404)
                data=file.read_bytes(); self.send_response(200); self.send_header("Content-Type","application/zip"); self.send_header("Content-Disposition",f'attachment; filename="{name}"'); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data); return
            return super().do_GET()
        except FileNotFoundError: return self.json(404, {"error":"Nie znaleziono paczki."})
        except Exception as exc: return self.json(500, {"error":str(exc)})
    def do_POST(self):
        path=urllib.parse.urlparse(self.path).path.rstrip("/")
        try:
            data=self.body()
            if path.endswith("/content"):
                post_id=urllib.parse.unquote(path.split("/")[3]); result=CONTENT.save(post_id, expected_revision=data["expected_revision"], description=data.get("description", ""), hashtags=data.get("hashtags", ""), location=data.get("location", ""), approve=bool(data.get("approve"))); return self.json(200,result)
            if path.endswith("/phone-package"):
                post_id=urllib.parse.unquote(path.split("/")[3]); return self.json(200,MOBILE.export(post_id, data.get("channel","instagram")))
            if path.endswith("/manual-check"):
                post_id=urllib.parse.unquote(path.split("/")[3]); return self.json(200,ADAPTER.set_manual_check(post_id,data["channel"],bool(data.get("checked")),data["expected_revision"]))
            if path.endswith("/publish"):
                post_id=urllib.parse.unquote(path.split("/")[3]); return self.json(202,JOBS.start(post_id,data["channel"],data["expected_revision"],data.get("request_id") or str(time.time_ns())))
            if path.endswith("/prepare-publication"):
                post_id=urllib.parse.unquote(path.split("/")[3]); return self.json(200,LEGACY.prepare_publication(post_id,data["channel"],bool(data.get("retry"))))
            if path.endswith("/music-ready"):
                post_id=urllib.parse.unquote(path.split("/")[3]); return self.json(200,LEGACY.music_ready(post_id))
            if path.endswith("/verify"):
                post_id=urllib.parse.unquote(path.split("/")[3]); return self.json(200,LEGACY.verify(post_id))
            if path == "/api/schedule/apply": return self.json(200,SCHEDULE.apply(data.get("changes",[])))
            if path == "/api/schedule/undo": return self.json(200,SCHEDULE.undo())
            if path == "/api/mobile-events/import": return self.json(200,MOBILE.import_events(data))
            if path == "/api/generator/open": return self.json(200,LEGACY.open_generator(data.get("brand","atlet")))
            if path == "/api/learning/lessons": return self.json(201,LESSONS.create(data))
            if path.startswith("/api/learning/lessons/") and path.endswith("/status"):
                return self.json(200,LESSONS.set_status(path.split("/")[4],data["status"]))
            if path == "/api/open-folder":
                folder=ADAPTER.folder_for(data["post_id"]); os.startfile(str(folder)); return self.json(200,{"ok":True})
            return self.json(404,{"error":"Nieznana operacja"})
        except RevisionConflict as exc: return self.json(409,{"error":str(exc),"current":exc.current,"proposal":exc.proposal})
        except PermissionError as exc: return self.json(423,{"error":str(exc)})
        except Exception as exc: return self.json(400,{"error":str(exc)})


def main():
    lock=SETTINGS.data_dir/f"desktop-{SETTINGS.port}.pid"
    if lock.exists():
        try:
            pid=int(lock.read_text()); os.kill(pid,0); webbrowser.open(f"http://{SETTINGS.host}:{SETTINGS.port}"); return
        except Exception: pass
    lock.write_text(str(os.getpid()))
    server=ThreadingHTTPServer((SETTINGS.host,SETTINGS.port),Handler)
    threading.Timer(.6,lambda:webbrowser.open(f"http://{SETTINGS.host}:{SETTINGS.port}")).start()
    try: server.serve_forever()
    finally:
        if lock.exists() and lock.read_text()==str(os.getpid()): lock.unlink()


if __name__ == "__main__": main()
