"""Rdzeń zastępczy — minimalny, zgodny interfejs magazynu paczek.

Używany wyłącznie w trybie `sandbox` (testy, kopia kolejki, demo bez BYQ Studio).
Nie jest formatem produkcyjnym: produkcja zawsze idzie przez `studio.rdzen`.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CHANNELS = ("tiktok", "instagram", "facebook")


def _channel_state() -> dict[str, Any]:
    return {"stan": "czeka", "proby": 0, "url": "", "info": "", "haczyk": False}


@dataclass
class Package:
    post_id: str
    marka: str = "atlet"
    status: str = "szkic"
    nazwa_wideo: str = ""
    opis: str = ""
    hashtagi: str = ""
    lokalizacja: str = ""
    termin: str = ""
    etykieta_mediow: str = ""
    jest_karuzela: bool = False
    slajdy: list[str] = field(default_factory=list)
    platformy: list[str] = field(default_factory=lambda: list(CHANNELS))
    platformy_stan: dict[str, dict[str, Any]] = field(default_factory=lambda: {c: _channel_state() for c in CHANNELS})
    historia: list[dict[str, Any]] = field(default_factory=list)

    def dopisz_historie(self, co: str, szczegol: str = "") -> None:
        self.historia.append({"kiedy": time.strftime("%Y-%m-%d %H:%M:%S"), "co": co, "szczegol": szczegol})

    def recalc_status(self) -> None:
        if self.status == "archiwum":
            return
        states = [self.platformy_stan.get(c, {}) for c in self.platformy]
        if states and all(s.get("haczyk") for s in states):
            self.status = "opublikowany"
        elif self.termin:
            self.status = "zaplanowany"

    def do_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def read(folder: Path) -> Package:
    raw = json.loads((folder / "post.json").read_text(encoding="utf-8"))
    known = {k: raw[k] for k in Package.__dataclass_fields__ if k in raw}
    package = Package(**known)
    for channel in CHANNELS:
        package.platformy_stan.setdefault(channel, _channel_state())
    return package


def save(folder: Path, package: Package) -> None:
    _atomic(folder / "post.json", package.do_json())
    text = package.opis.strip()
    if package.hashtagi.strip():
        text += "\n\n" + package.hashtagi.strip()
    _atomic(folder / "opis.txt", text + ("\n" if text else ""))


def list_packages(root: Path) -> list[tuple[Path, Any, str | None]]:
    rows: list[tuple[Path, Any, str | None]] = []
    if not root.is_dir():
        return rows
    for folder in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        if not (folder / "post.json").is_file():
            continue
        try:
            rows.append((folder, read(folder), None))
        except Exception as exc:  # paczka uszkodzona — raport, nie awaria listy
            rows.append((folder, None, str(exc)))
    return rows


def _atomic(path: Path, value: str) -> None:
    tmp = path.with_suffix(path.suffix + ".byku-tmp")
    tmp.write_text(value, encoding="utf-8")
    os.replace(tmp, path)
