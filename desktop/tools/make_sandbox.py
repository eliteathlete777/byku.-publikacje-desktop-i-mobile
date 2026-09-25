"""Buduje izolowaną kolejkę testową (rdzeń zastępczy) — do testów i demo bez danych produkcyjnych.

Użycie:  python tools/make_sandbox.py [katalog_kolejki]
Domyślnie: data/sandbox-queue (katalog ignorowany przez git).
"""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.fallback_core import Package, save  # noqa: E402


def png(color: tuple[int, int, int], size: int = 96) -> bytes:
    """Minimalny PNG bez zależności (jednolity kolor + pasek)."""
    rows = b""
    for y in range(size):
        line = bytes(color) * size if y < size * 0.7 else bytes((237, 22, 31)) * size
        rows += b"\x00" + line
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


SAMPLES = [
    # post_id, marka, typ, tiktok, instagram, termin, opis
    ("atlet-pompki-porecze", "atlet", "reel", "published", "czeka", "2026-09-26 19:15", "Pompki na poręczach. 5 serii, zero wymówek."),
    ("atlet-gumy-plecy", "atlet", "reel", "scheduled", "czeka", "2026-09-28 20:05", "Plecy z gumą. Kontrola ruchu ponad ciężar."),
    ("atlet-karuzela-plan", "atlet", "carousel", "published", "czeka", "", "Plan tygodnia bez siłowni. Zapisz."),
    ("atlet-szkic-bez-opisu", "atlet", "reel", "czeka", "czeka", "", ""),
    ("rigger-kratownica-narodowy", "rigger", "reel", "published", "czeka", "2026-09-27 12:30", "⚠️ Tu nie ma miejsca na błąd, byku. Kratownica 12 m w górę przed próbą."),
    ("rigger-demontaz-noc", "rigger", "reel", "published", "opublikowany", "2026-09-20 18:45", "Demontaż o 3:00. Zasada 15 minut."),
    ("rigger-archiwum", "rigger", "reel", "published", "opublikowany", "2026-09-01 18:45", "Stary materiał."),
]


def build(queue: Path) -> list[str]:
    queue.mkdir(parents=True, exist_ok=True)
    created = []
    for i, (post_id, brand, kind, tiktok, instagram, term, text) in enumerate(SAMPLES):
        folder = queue / post_id
        if (folder / "post.json").exists():
            continue
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "miniaturka.png").write_bytes(png((40 + i * 25, 40, 40)))
        package = Package(post_id=post_id, marka=brand, opis=text, termin=term,
                          hashtagi="#bykuathlete #kalistenika" if brand == "atlet" else "#rigger #backstage",
                          lokalizacja="Katowice" if brand == "atlet" else "PGE Narodowy",
                          etykieta_mediow=post_id.replace("-", " ").capitalize(), status="zaplanowany" if term else "szkic")
        if kind == "carousel":
            package.jest_karuzela = True
            package.slajdy = ["slajd-1.png", "slajd-2.png", "slajd-3.png"]
            for n, name in enumerate(package.slajdy):
                (folder / name).write_bytes(png((60, 60 + n * 40, 90)))
        else:
            package.nazwa_wideo = "film.mp4"
            (folder / "film.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + bytes([i]) * 4096)
        if tiktok == "published":
            package.platformy_stan["tiktok"].update(dowod="published", stan="opublikowany", haczyk=True)
        elif tiktok == "scheduled":
            package.platformy_stan["tiktok"].update(stan="potwierdzony")
        if instagram == "opublikowany":
            package.platformy_stan["instagram"].update(dowod="published", stan="opublikowany", haczyk=True)
        if text:
            package.dopisz_historie("content_approved", "dane testowe")
        if post_id == "rigger-archiwum":
            package.status = "archiwum"
        save(folder, package)
        created.append(post_id)
    return created


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "sandbox-queue"
    print("Utworzono:", ", ".join(build(target)) or "nic (kolejka już istnieje)")
