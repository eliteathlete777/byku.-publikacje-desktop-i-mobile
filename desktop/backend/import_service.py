"""Zakładka „Dodaj”: goły film → szkic paczki w kolejce Studio.

Tak jak stary Generator: praca zaczyna się od samego wideo. Nazwa folderu
rolki = nazwa rolki (i nazwa pliku w paczce). Z folderu bierzemy największy film
— mniejszy plik to odpad produkcji (np. sam dźwięk). Okładka startowa = klatka
z filmu (ffmpeg); opis, lokalizację, termin i akceptację Damian robi w karcie.
Szkic bez opisu nie przejdzie bramki wrzutu (rdzeń wymaga opisu).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import BinaryIO

from .studio_adapter import StudioAdapter

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}
MIN_VIDEO = 10_000
MAX_VIDEO = 4 * 1024 ** 3
BRANDS = {"atlet", "rigger"}
SOURCE_TAG = "BYKU.PUBLIKACJE Dodaj"
PENDING_FILE = "podstawy-oczekujace.json"


class ImportProblem(ValueError):
    pass


def clean_title(title: str) -> str:
    """Nazwa rolki z nazwy folderu — bez znaków zakazanych w nazwach plików Windows."""
    t = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", str(title or ""))
    t = re.sub(r"\s+", " ", t).strip().rstrip(". ")
    return t[:120]


def title_key(name: str) -> str:
    return clean_title(Path(name).stem if Path(name).suffix.lower() in VIDEO_EXT else name).casefold()


def _ffmpeg() -> str | None:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def frame_png(video: Path, dest: Path) -> bool:
    """Klatka z filmu jako miniaturka.png (1 s, a gdy film krótszy — pierwsza klatka)."""
    exe = _ffmpeg()
    if not exe:
        return False
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for ss in ("1", "0"):
        try:
            subprocess.run([exe, "-v", "error", "-y", "-ss", ss, "-i", str(video), "-frames:v", "1", str(dest)],
                           capture_output=True, timeout=60, creationflags=flags)
        except Exception:
            continue
        if dest.is_file() and dest.stat().st_size > 1000:
            return True
    dest.unlink(missing_ok=True)
    return False


def frame_at(video: Path, t: float) -> bytes:
    """Klatka filmu jako PNG (dla studia miniatury, gdy przeglądarka nie dekoduje HEVC)."""
    exe = _ffmpeg()
    if not exe:
        raise ImportProblem("Brak ffmpeg — nie wytnę klatki z filmu.")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run([exe, "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1",
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, timeout=60, creationflags=flags)
    if not r.stdout:
        raise ImportProblem("Nie udało się wyciąć klatki z filmu.")
    return r.stdout


_preview_locks: dict[str, threading.Lock] = {}
_preview_guard = threading.Lock()


def video_codec(video: Path) -> str:
    exe = _ffmpeg()
    if not exe:
        return ""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run([exe, "-hide_banner", "-i", str(video)], capture_output=True, timeout=30, creationflags=flags)
    m = re.search(r"Video: (\w+)", r.stderr.decode("utf-8", "replace"))
    return m.group(1).lower() if m else ""


def preview_video(video: Path, cache_dir: Path) -> Path:
    """Film do obejrzenia w panelu. H.264 idzie wprost; HEVC z telefonu (przeglądarka go nie
    odtworzy) dostaje kopię podglądową H.264 720p w data/podglady — paczka zostaje nietknięta."""
    if video_codec(video) in {"h264", ""}:
        return video
    st = video.stat()
    key = hashlib.sha1(f"{video.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:16]
    dest = cache_dir / f"{key}.mp4"
    with _preview_guard:
        lock = _preview_locks.setdefault(key, threading.Lock())
    with lock:  # dwa odtwarzacze naraz = jedno kodowanie
        if dest.is_file() and dest.stat().st_size > 0:
            return dest
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".part.mp4")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", str(video), "-vf", "scale=-2:'min(1280,ih)'",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(tmp)],
                           capture_output=True, timeout=900, creationflags=flags)
        if r.returncode != 0 or not tmp.is_file():
            tmp.unlink(missing_ok=True)
            raise ImportProblem("Nie udało się przygotować podglądu filmu: " + r.stderr.decode("utf-8", "replace")[-200:])
        tmp.replace(dest)
        return dest


def warm_preview(video: Path, cache_dir: Path) -> None:
    """Po dodaniu rolki: podgląd koduje się w tle, żeby przy pierwszym obejrzeniu nie czekać."""
    def work():
        try:
            preview_video(video, cache_dir)
        except Exception:
            pass
    threading.Thread(target=work, daemon=True).start()


class ImportService:
    def __init__(self, adapter: StudioAdapter):
        self.adapter = adapter

    def existing_titles(self, brand: str) -> dict[str, str]:
        out = {}
        for c in self.adapter.list_cards(brand=brand, include_archive=True)["items"]:
            out[title_key(c["name"])] = c["post_id"]
        return out

    def check(self, brand: str, titles: list[str]) -> dict:
        brand = self._brand(brand)
        have = self.existing_titles(brand)
        return {"existing": {t: have[title_key(t)] for t in titles if title_key(t) in have}}

    def _brand(self, brand: str) -> str:
        b = str(brand or "").strip().lower()
        if b not in BRANDS:
            raise ImportProblem("Wybierz markę: Atlet albo Rigger.")
        return b

    def add_reel(self, *, brand: str, title: str, filename: str, stream: BinaryIO, length: int, location: str = "") -> dict:
        try:
            return self._add_reel(brand=brand, title=title, filename=filename, stream=stream, length=length, location=location)
        except Exception:
            # Odrzucony film trzeba doczytać do końca — inaczej przeglądarka widzi zerwane
            # połączenie zamiast powodu błędu.
            if length <= MAX_VIDEO:
                _drain(stream, length - getattr(stream, "byku_read", 0))
            raise

    def _add_reel(self, *, brand: str, title: str, filename: str, stream: BinaryIO, length: int, location: str = "") -> dict:
        brand = self._brand(brand)
        title = clean_title(title)
        if not title:
            raise ImportProblem("Rolka musi mieć nazwę (nazwa folderu).")
        ext = Path(filename or "").suffix.lower()
        if ext not in VIDEO_EXT:
            raise ImportProblem(f"{filename}: to nie jest plik wideo ({', '.join(sorted(VIDEO_EXT))}).")
        if length < MIN_VIDEO:
            raise ImportProblem(f"{filename}: plik jest za mały na film.")
        if length > MAX_VIDEO:
            raise ImportProblem(f"{filename}: plik jest za duży (max 4 GB).")
        self.adapter.ensure_writes("Dodawanie rolek")
        core = self.adapter.require_core()
        existing = self.existing_titles(brand).get(title.casefold())
        if existing:
            _drain(stream, length)
            stream.byku_read = length
            return {"status": "exists", "post_id": existing, "title": title}

        queue = Path(self.adapter.settings.queue)
        queue.mkdir(parents=True, exist_ok=True)
        tmp = queue / f".import-dodaj-{time.time_ns()}"
        tmp.mkdir()
        try:
            video = tmp / f"{title}{ext}"
            with video.open("wb") as fh:
                left = length
                while left > 0:
                    chunk = stream.read(min(1024 * 1024, left))
                    if not chunk:
                        raise ImportProblem("Przerwane przesyłanie pliku — spróbuj jeszcze raz.")
                    fh.write(chunk)
                    left -= len(chunk)
                    stream.byku_read = length - left
            thumb = frame_png(video, tmp / "miniaturka.png")
            post_id = core.create_draft(tmp, brand=brand, video_name=video.name, location=location.strip(),
                                        source=f"{SOURCE_TAG}: {title}")
            dest = queue / post_id
            if dest.exists():
                raise ImportProblem(f"Kolizja ID paczki {post_id} — spróbuj jeszcze raz.")
            tmp.replace(dest)
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        warm_preview(dest / video.name, Path(self.adapter.settings.data_dir) / "podglady")
        basis = self.attach_pending_basis(brand, title, post_id)
        return {"status": "added", "post_id": post_id, "title": title, "thumbnail": thumb, "basis": basis}

    def attach_pending_basis(self, brand: str, title: str, post_id: str) -> bool:
        """Podstawa opisu przygotowana zawczasu (data/podstawy-oczekujace.json, klucz = nazwa folderu
        rolki) trafia do data/podstawy.json pod nowy post_id. Wpis zostaje z polem post_id (ślad)."""
        data_dir = Path(self.adapter.settings.data_dir)
        pending_file = data_dir / PENDING_FILE
        if not pending_file.is_file():
            return False
        pending = json.loads(pending_file.read_text(encoding="utf-8"))
        key = title_key(title)
        match = next((k for k, v in pending.items() if title_key(k) == key
                      and str(v.get("marka", "")).lower() == brand and not v.get("post_id")), None)
        if match is None or not str(pending[match].get("podstawa", "")).strip():
            return False
        basis_file = data_dir / "podstawy.json"
        bases = json.loads(basis_file.read_text(encoding="utf-8")) if basis_file.is_file() else {}
        if not bases.get(post_id):
            bases[post_id] = str(pending[match]["podstawa"]).strip()
            _write_json(basis_file, bases)
        pending[match]["post_id"] = post_id
        _write_json(pending_file, pending)
        return True


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _drain(stream: BinaryIO, length: int) -> None:
    left = length
    while left > 0:
        chunk = stream.read(min(1024 * 1024, left))
        if not chunk:
            return
        left -= len(chunk)
