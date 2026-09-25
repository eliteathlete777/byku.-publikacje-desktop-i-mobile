from __future__ import annotations

import json
import mimetypes
import os
import re
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

from backend.brand_service import BrandService
from backend.config import Settings, load_settings
from backend.content_service import ContentService, RevisionConflict
from backend.core import CoreUnavailable
from backend.job_service import JobService
from backend.legacy_bridge import LegacyBridge
from backend.mobile_packages import MobilePackages, TransferError
from backend.schedule_service import ScheduleService
from backend.studio_adapter import StudioAdapter
from learning.lesson_service import LessonService
from learning.store import LearningStore

MAX_JSON = 2 * 1024 * 1024
MAX_UPLOAD = 8 * 1024 * 1024
VERSION = "2.0.0"


class App:
    """Wszystkie serwisy jednej instancji (osobna instancja w testach)."""

    def __init__(self, settings: Settings, core=None, opener=None):
        self.settings = settings
        self.adapter = StudioAdapter(settings, core=core)
        self.learning = LearningStore(settings.data_dir / "learning.sqlite3")
        self.content = ContentService(self.adapter, self.learning)
        self.jobs = JobService(self.adapter, self.learning)
        self.schedule = ScheduleService(self.adapter)
        self.mobile = MobilePackages(self.adapter, opener=opener)
        self.legacy = LegacyBridge(self.adapter)
        self.lessons = LessonService(self.learning)
        self.brands = BrandService(settings.data_dir, self.learning)

    def health(self) -> dict:
        s = self.settings
        return {"ok": self.adapter.core is not None, "version": VERSION, "mode": s.mode,
                "writes": s.writes_allowed, "production_writes": s.allow_production_writes,
                "publication": s.allow_publication, "queue": str(s.queue),
                "core": getattr(self.adapter.core, "name", None), "core_error": self.adapter.core_error,
                "legacy": self.legacy.available(), "drive": self.mobile.drive_status(),
                "mobile_server": self.mobile.server_status(), "can_undo": self.schedule.can_undo()}


def make_handler(app: App):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / "frontend"), **kwargs)

        def log_message(self, fmt, *args):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'")
            super().end_headers()

        # ---------- odpowiedzi ----------
        def json(self, code: int, data) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def file(self, path: Path, content_type: str | None = None, download: str | None = None) -> None:
            size = path.stat().st_size
            ctype = content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            start, end, status = 0, size - 1, 200
            match = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", ""))
            if match and size:
                if match.group(1):
                    start = int(match.group(1)); end = int(match.group(2)) if match.group(2) else size - 1
                else:
                    start = max(0, size - int(match.group(2) or 0))
                end = min(end, size - 1)
                if start > end:
                    self.send_response(416); self.send_header("Content-Range", f"bytes */{size}"); self.end_headers(); return
                status = 206
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1 if size else 0))
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            if download:
                self.send_header("Content-Disposition", f'attachment; filename="{download}"')
            self.end_headers()
            with path.open("rb") as f:
                f.seek(start)
                remaining = end - start + 1 if size else 0
                while remaining > 0:
                    chunk = f.read(min(1024 * 256, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk); remaining -= len(chunk)

        def raw_body(self, limit: int) -> bytes:
            size = int(self.headers.get("Content-Length") or 0)
            if size > limit:
                raise ValueError("Zbyt duże żądanie")
            return self.rfile.read(size)

        def body(self) -> dict:
            data = json.loads(self.raw_body(MAX_JSON).decode("utf-8") or "{}")
            if not isinstance(data, dict):
                raise ValueError("Oczekiwano obiektu JSON")
            return data

        def guard(self, fn):
            try:
                return fn()
            except FileNotFoundError:
                return self.json(404, {"error": "Nie znaleziono paczki lub pliku."})
            except RevisionConflict as exc:
                return self.json(409, {"error": str(exc), "current": exc.current, "proposal": exc.proposal})
            except PermissionError as exc:
                return self.json(423, {"error": str(exc)})
            except CoreUnavailable as exc:
                return self.json(503, {"error": str(exc)})
            except NotImplementedError as exc:
                return self.json(501, {"error": str(exc)})
            except TransferError as exc:
                return self.json(502, {"error": str(exc)})
            except (ValueError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
                return self.json(400, {"error": str(exc) if not isinstance(exc, KeyError) else f"Brak pola: {exc}"})
            except Exception as exc:  # ostatnia linia: błąd widoczny w UI, serwer żyje dalej
                return self.json(500, {"error": f"Błąd wewnętrzny: {exc}"})

        def local_request(self) -> bool:
            # Ochrona przed stronami z innych domen (CSRF / DNS rebinding) — tylko lokalny panel.
            host = (self.headers.get("Host") or "").split(":")[0]
            origin = self.headers.get("Origin")
            if host not in {"127.0.0.1", "localhost"}:
                return False
            return origin is None or urllib.parse.urlparse(origin).hostname in {"127.0.0.1", "localhost"}

        # ---------- GET ----------
        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            path, q = url.path.rstrip("/"), urllib.parse.parse_qs(url.query)
            arg = lambda k, d=None: (q.get(k) or [d])[0]
            if not path.startswith("/api/"):
                return super().do_GET()
            if not self.local_request():
                return self.json(403, {"error": "Dostęp tylko z lokalnego panelu"})
            parts = [urllib.parse.unquote(x) for x in path.split("/")]

            def route():
                if path == "/api/health":
                    return self.json(200, app.health())
                if path == "/api/publications":
                    return self.json(200, app.adapter.list_cards(brand=arg("brand", "atlet"), include_archive=arg("archive") == "true",
                                                                  selected_channel=arg("channel", "instagram")))
                if len(parts) >= 4 and parts[2] == "publications":
                    post_id = parts[3]
                    if len(parts) == 4:
                        card = app.adapter.get(post_id, arg("channel", "instagram"))
                        card["mobile_events"] = app.mobile.mobile_events(post_id)
                        return self.json(200, card)
                    if parts[4] == "thumbnail":
                        return self.file(app.adapter.folder_for(post_id) / "miniaturka.png", "image/png") \
                            if (app.adapter.folder_for(post_id) / "miniaturka.png").is_file() else self.json(404, {"error": "Brak miniatury"})
                    if parts[4] == "media" and len(parts) == 6:
                        return self.file(app.adapter.file_for(post_id, parts[5]))
                    if parts[4] == "capabilities":
                        return self.json(200, app.legacy.publication_capabilities(post_id))
                    if parts[4] == "lint":
                        card = app.adapter.get(post_id)
                        return self.json(200, {"notes": app.brands.lint(card["brand"], arg("description", ""), arg("hashtags", ""))})
                if path == "/api/schedule/proposals":
                    return self.json(200, {"variants": app.schedule.propose(arg("brand", "atlet"), arg("start"))})
                if path == "/api/jobs":
                    return self.json(200, {"jobs": app.jobs.list(), "locks": app.jobs.locks_state()})
                if path.startswith("/api/jobs/"):
                    return self.json(200, app.jobs.get(parts[3]))
                if path == "/api/learning":
                    return self.json(200, {"events": app.learning.recent_events(), "lessons": app.learning.lessons()})
                if path == "/api/brands":
                    return self.json(200, {"brands": app.brands.all()})
                if path.startswith("/api/brands/") and path.endswith("/style"):
                    return self.json(200, {"examples": app.brands.style_examples(parts[3])})
                if path == "/api/mobile-candidates":
                    return self.json(200, {"items": app.mobile.candidates(arg("brand", "all")),
                                           "drive": app.mobile.drive_status(), "server": app.mobile.server_status()})
                if path == "/api/mobile-events":
                    return self.json(200, {"events": app.mobile.mobile_events()})
                if path.startswith("/api/mobile-packages/"):
                    name = Path(parts[-1]).name
                    file = app.mobile.root / name
                    if not name.endswith(".zip") or not file.is_file():
                        return self.json(404, {"error": "Brak paczki"})
                    return self.file(file, "application/zip", download=name)
                return self.json(404, {"error": "Nieznany adres"})
            return self.guard(route)

        # ---------- zapis ----------
        def do_PUT(self):
            return self.do_POST()

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path.rstrip("/")
            parts = [urllib.parse.unquote(x) for x in path.split("/")]
            if not self.local_request():
                return self.json(403, {"error": "Dostęp tylko z lokalnego panelu"})

            def route():
                if len(parts) == 5 and parts[2] == "publications":
                    post_id, action = parts[3], parts[4]
                    if action == "thumbnail":
                        rev = self.headers.get("X-Expected-Revision", "")
                        return self.json(200, app.content.replace_thumbnail(post_id, expected_revision=rev, data=self.raw_body(MAX_UPLOAD)))
                    data = self.body()
                    if action == "content":
                        return self.json(200, app.content.save(post_id, expected_revision=data["expected_revision"],
                                                               description=data.get("description", ""), hashtags=data.get("hashtags", ""),
                                                               location=data.get("location", ""), approve=bool(data.get("approve"))))
                    if action == "drafts":
                        card = app.adapter.get(post_id)
                        return self.json(200, {"drafts": app.brands.draft(card["brand"], post_id, data.get("topic") or card["name"])})
                    if action == "hashtags-suggest":
                        card = app.adapter.get(post_id)
                        return self.json(200, {"hashtags": app.brands.hashtags_for(card["brand"], post_id, int(data.get("variant", 0)))})
                    if action == "phone-package":
                        return self.json(200, app.mobile.export(post_id, data.get("channel", "instagram")))
                    if action == "to-drive":
                        return self.json(200, app.mobile.to_drive(post_id))
                    if action == "to-server":
                        return self.json(200, app.mobile.to_server(post_id))
                    if action == "manual-check":
                        return self.json(200, app.adapter.set_manual_check(post_id, data["channel"], bool(data.get("checked")), data["expected_revision"]))
                    if action == "publish":
                        return self.json(202, app.jobs.start(post_id, data["channel"], data["expected_revision"], data.get("request_id") or str(time.time_ns())))
                    if action == "prepare-publication":
                        return self.json(200, app.legacy.prepare_publication(post_id, data["channel"], bool(data.get("retry"))))
                    if action == "music-ready":
                        return self.json(200, app.legacy.music_ready(post_id))
                    if action == "verify":
                        return self.json(200, app.legacy.verify(post_id))
                    if action == "open-folder":
                        return self.json(200, open_folder(app.adapter.folder_for(post_id)))
                data = self.body()
                if path == "/api/schedule/apply":
                    return self.json(200, app.schedule.apply(data.get("changes", [])))
                if path == "/api/schedule/undo":
                    return self.json(200, app.schedule.undo())
                if path == "/api/mobile-events/import":
                    return self.json(200, app.mobile.import_events(data))
                if path == "/api/mobile-events/pull":
                    return self.json(200, app.mobile.pull_server_events())
                if path == "/api/generator/open":
                    return self.json(200, app.legacy.open_generator(data.get("brand", "atlet")))
                if path.startswith("/api/brands/") and len(parts) == 4:
                    return self.json(200, app.brands.update(parts[3], data))
                if path == "/api/learning/lessons":
                    return self.json(201, app.lessons.create(data))
                if path.startswith("/api/learning/lessons/") and path.endswith("/status"):
                    return self.json(200, app.lessons.set_status(parts[4], data["status"]))
                if path.startswith("/api/learning/lessons/") and path.endswith("/test"):
                    return self.json(200, app.lessons.record_test(parts[4], data.get("status", ""), data.get("note", "")))
                if path.startswith("/api/jobs/") and path.endswith("/release"):
                    return self.json(200, app.jobs.release(parts[3], data.get("result", "interrupted")))
                return self.json(404, {"error": "Nieznana operacja"})
            return self.guard(route)

    return Handler


def open_folder(folder: Path) -> dict:
    if sys.platform.startswith("win"):
        os.startfile(str(folder))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True, "path": str(folder)}


def main():
    settings = load_settings()
    app = App(settings)
    url = f"http://{settings.host}:{settings.port}"
    lock = settings.data_dir / f"desktop-{settings.port}.pid"
    if lock.exists():
        try:
            os.kill(int(lock.read_text()), 0)
            webbrowser.open(url)
            return
        except Exception:
            pass
    try:
        server = ThreadingHTTPServer((settings.host, settings.port), make_handler(app))
    except OSError:
        webbrowser.open(url)  # port zajęty — najpewniej działa już panel
        return
    lock.write_text(str(os.getpid()))
    if "--no-browser" not in sys.argv:
        threading.Timer(.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    finally:
        if lock.exists() and lock.read_text() == str(os.getpid()):
            lock.unlink()


if __name__ == "__main__":
    main()
