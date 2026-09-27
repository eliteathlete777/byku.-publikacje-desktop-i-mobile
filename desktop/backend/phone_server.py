from __future__ import annotations

import json
import mimetypes
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

TYPES = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".html": "text/html; charset=utf-8",
         ".json": "application/json; charset=utf-8", ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml",
         ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8", ".mp4": "video/mp4", ".mov": "video/quicktime",
         ".webm": "video/webm", ".m4v": "video/mp4", ".webp": "image/webp"}
PACKAGE_FILE = re.compile(r"^(index\.json|(atlet|rigger)/do-instagrama/[^/]+/[^/]+)$")
MAX_EVENTS_BODY = 1024 * 1024
TAILSCALE = [shutil.which("tailscale"), r"C:\Program Files\Tailscale\tailscale.exe"]


class PhoneServer:
    """Serwer telefonu zamiast Hostingera: appka mobilna + paczki + przyjęcie czynności.

    Wystawia tylko to, czego potrzebuje telefon. Całe API desktopu (zapis treści, haczyki,
    kalendarz) zostaje na porcie desktopu i nigdy nie jest dostępne z telefonu. Na zewnątrz
    wystawia go Tailscale (`tailscale serve --bg <port>`) — prywatne HTTPS tylko dla Twoich urządzeń.
    """

    def __init__(self, app_dir: Path, packages_root: Path, import_events: Callable[[dict], dict], *, host: str = "127.0.0.1",
                 port: int = 8903, public_url: str = ""):
        self.app_dir, self.packages_root, self.import_events = app_dir, packages_root, import_events
        self.host, self.port, self.public_url = host, port, public_url
        self.server: ThreadingHTTPServer | None = None
        self._tailscale: tuple[float, dict] = (0.0, {})

    # ── status dla desktopu ──
    def tailscale(self) -> dict:
        at, cached = self._tailscale
        if time.time() - at < 60: return cached
        info = {"installed": False, "online": False, "url": ""}
        exe = next((x for x in TAILSCALE if x and Path(x).is_file()), None)
        if exe:
            info["installed"] = True
            try:
                raw = subprocess.run([exe, "status", "--json"], capture_output=True, text=True, timeout=4,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
                me = json.loads(raw or "{}").get("Self") or {}
                name = str(me.get("DNSName") or "").rstrip(".")
                info["online"] = bool(me.get("Online")) and bool(name)
                info["url"] = f"https://{name}/" if name else ""
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
        self._tailscale = (time.time(), info)
        return info

    def status(self) -> dict:
        ts = self.tailscale()
        return {"running": self.server is not None, "port": self.port, "local_url": f"http://127.0.0.1:{self.port}/",
                "app_found": (self.app_dir / "index.html").is_file(), "public_url": self.public_url or ts["url"], "tailscale": ts,
                "packages": self._package_count()}

    def _package_count(self) -> int:
        try: return len(json.loads((self.packages_root / "index.json").read_text(encoding="utf-8")).get("packages", []))
        except (OSError, ValueError): return 0

    # ── serwer ──
    def handler(self):
        phone = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "BYKU-Telefon"
            sys_version = ""

            def log_message(self, fmt, *args): pass

            def headers_common(self, cache: str):
                self.send_header("Cache-Control", cache)
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Robots-Tag", "noindex, nofollow")
                self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")

            def json(self, code: int, data: dict):
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body)))
                self.headers_common("no-store"); self.end_headers()
                if self.command != "HEAD": self.wfile.write(body)

            def resolve(self) -> tuple[Path | None, str]:
                path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
                if path.startswith("/paczki/"):
                    rel = path[len("/paczki/"):]
                    if not PACKAGE_FILE.match(rel): return None, "no-store"
                    return phone._inside(phone.packages_root, rel), "no-store"
                rel = path.lstrip("/") or "index.html"
                if rel.endswith("/"): rel += "index.html"
                if rel.split("/", 1)[0] == "paczki": return None, "no-store"
                cache = "no-store" if rel in {"index.html", "sw.js", "manifest.webmanifest"} else "no-cache"
                return phone._inside(phone.app_dir, rel), cache

            def do_HEAD(self): self.do_GET()

            def do_GET(self):
                if urllib.parse.urlparse(self.path).path.rstrip("/") == "/api/ping":
                    return self.json(200, {"ok": True, "app": "BYKU.PUBLIKACJE", "packages": phone._package_count(), "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
                file, cache = self.resolve()
                if not file or not file.is_file(): return self.json(404, {"error": "Nie ma takiego pliku"})
                size = file.stat().st_size
                start, end = 0, size - 1
                ranged = re.match(r"^bytes=(\d*)-(\d*)$", self.headers.get("Range", ""))
                if ranged and size:
                    a, b = ranged.groups()
                    if a: start, end = int(a), min(int(b), size - 1) if b else size - 1
                    elif b: start = max(0, size - int(b))
                    if start > end or start >= size:
                        self.send_response(416); self.send_header("Content-Range", f"bytes */{size}"); self.headers_common(cache); self.end_headers(); return
                self.send_response(206 if ranged and size else 200)
                self.send_header("Content-Type", TYPES.get(file.suffix.lower()) or mimetypes.guess_type(file.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(end - start + 1 if size else 0))
                self.send_header("Accept-Ranges", "bytes")
                if ranged and size: self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.headers_common(cache); self.end_headers()
                if self.command == "HEAD" or not size: return
                try:
                    with file.open("rb") as f:
                        f.seek(start); left = end - start + 1
                        while left > 0:
                            chunk = f.read(min(256 * 1024, left))
                            if not chunk: break
                            self.wfile.write(chunk); left -= len(chunk)
                except (ConnectionError, OSError):
                    pass  # telefon przerwał pobieranie (zamknięta paczka) — to normalne

            def do_POST(self):
                if urllib.parse.urlparse(self.path).path.rstrip("/") != "/api/events": return self.json(404, {"error": "Nieznana operacja"})
                size = int(self.headers.get("Content-Length") or 0)
                if size <= 0 or size > MAX_EVENTS_BODY: return self.json(413, {"error": "Nieprawidłowy rozmiar danych"})
                try:
                    payload = json.loads(self.rfile.read(size).decode("utf-8"))
                    if not isinstance(payload, dict): raise ValueError("Oczekiwano obiektu JSON")
                    return self.json(200, phone.import_events(payload))
                except (ValueError, AttributeError) as exc:
                    return self.json(400, {"error": str(exc)})

        return Handler

    @staticmethod
    def _inside(root: Path, rel: str) -> Path | None:
        try:
            base = root.resolve(); target = (base / rel).resolve()
            target.relative_to(base)
            return target
        except (ValueError, OSError):
            return None

    def start(self) -> "PhoneServer":
        self.server = ThreadingHTTPServer((self.host, self.port), self.handler())
        self.port = self.server.server_port
        threading.Thread(target=self.server.serve_forever, name="phone-server", daemon=True).start()
        return self

    def stop(self):
        if self.server:
            self.server.shutdown(); self.server.server_close(); self.server = None
