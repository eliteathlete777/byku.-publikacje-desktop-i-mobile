"""Zakładka „Dodaj”: goły film → szkic paczki w kolejce Studio.

Tak jak stary Generator: praca zaczyna się od samego wideo. Nazwa folderu
rolki = nazwa rolki (i nazwa pliku w paczce). Z folderu bierzemy największy film
— mniejszy plik to odpad produkcji (np. sam dźwięk). Okładka startowa = klatka
z filmu (ffmpeg); opis, lokalizację, termin i akceptację Damian robi w karcie.
Szkic bez opisu nie przejdzie bramki wrzutu (rdzeń wymaga opisu).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import BinaryIO

from .studio_adapter import StudioAdapter

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}
MIN_VIDEO = 10_000
MAX_VIDEO = 4 * 1024 ** 3
BRANDS = {"atlet", "rigger"}
SOURCE_TAG = "BYKU.PUBLIKACJE Dodaj"


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
        return {"status": "added", "post_id": post_id, "title": title, "thumbnail": thumb}


def _drain(stream: BinaryIO, length: int) -> None:
    left = length
    while left > 0:
        chunk = stream.read(min(1024 * 1024, left))
        if not chunk:
            return
        left -= len(chunk)
