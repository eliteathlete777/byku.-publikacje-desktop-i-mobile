"""Warstwa dostępu do magazynu paczek.

Produkcja używa istniejącego rdzenia BYQ Studio (`studio.rdzen`, katalog `source_root`),
bez przepisywania uploaderów. Gdy rdzeń jest niedostępny, tryb `sandbox` może użyć
rdzenia zastępczego (`fallback_core`) — tylko do testów i pracy na kopii kolejki.
Tryb `production` bez prawdziwego rdzenia zwraca czytelny błąd zamiast zgadywać format.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Iterable

from . import fallback_core


class CoreUnavailable(RuntimeError):
    pass


class StudioCore:
    name = "studio"
    legacy = True

    def __init__(self, source_root: Path):
        if str(source_root) not in sys.path:
            sys.path.insert(0, str(source_root))
        from studio.rdzen import magazyn  # noqa: F401  — sprawdza dostępność rdzenia
        self._magazyn = magazyn

    def read(self, folder: Path) -> Any:
        return self._magazyn.wczytaj_paczke(folder, sprawdz_sumy=False)

    def save(self, folder: Path, package: Any, *, recompute: bool = True) -> None:
        self._magazyn.zapisz_paczke(folder, package, przelicz_sumy=recompute)

    def save_content(self, folder: Path, package: Any) -> None:
        hashtags = package.hashtagi
        self.save(folder, package, recompute=True)
        if not hashtags.strip():
            # Rdzeń historyczny przy pustej wartości dopisuje domyślne hashtagi.
            # Jawne wyczyszczenie jest osobną operacją nowego kontraktu.
            package.hashtagi = ""
            _atomic_text(folder / "opis.txt", package.opis + ("\n" if package.opis else ""))
            _atomic_text(folder / "post.json", package.do_json())

    def list(self, root: Path) -> Iterable[tuple[Path, Any, str | None]]:
        return self._magazyn.lista_paczek(root=root)

    def set_term(self, folder: Path, value: str) -> None:
        self._magazyn.ustaw_termin(folder, value)

    def clear_term(self, folder: Path) -> None:
        self._magazyn.wyczysc_termin(folder)

    def manual_hook(self, package: Any, channel: str) -> bool:
        try:
            from studio.rdzen.most_publikacji import haczyk_reczny
            return bool(haczyk_reczny(package, channel))
        except Exception:
            raw = getattr(package, "platformy_stan", {}).get(channel, {})
            return bool(raw.get("haczyk")) if isinstance(raw, dict) else False

    def recalc_status(self, package: Any) -> None:
        package._przelicz_status()


class FallbackCore:
    name = "fallback"
    legacy = False

    def read(self, folder: Path) -> Any:
        return fallback_core.read(folder)

    def save(self, folder: Path, package: Any, *, recompute: bool = True) -> None:
        fallback_core.save(folder, package)

    def save_content(self, folder: Path, package: Any) -> None:
        fallback_core.save(folder, package)

    def list(self, root: Path) -> Iterable[tuple[Path, Any, str | None]]:
        return fallback_core.list_packages(root)

    def set_term(self, folder: Path, value: str) -> None:
        package = fallback_core.read(folder); package.termin = value; fallback_core.save(folder, package)

    def clear_term(self, folder: Path) -> None:
        self.set_term(folder, "")

    def manual_hook(self, package: Any, channel: str) -> bool:
        raw = package.platformy_stan.get(channel, {})
        return bool(raw.get("haczyk")) if isinstance(raw, dict) else False

    def recalc_status(self, package: Any) -> None:
        package.recalc_status()


def load_core(source_root: Path, mode: str, preference: str = "auto"):
    if preference == "fallback":
        if mode == "production":
            raise CoreUnavailable("Rdzeń zastępczy nie może obsługiwać kolejki produkcyjnej")
        return FallbackCore()
    try:
        return StudioCore(source_root)
    except Exception as exc:
        if preference == "studio" or mode == "production":
            raise CoreUnavailable(
                f"Nie znaleziono rdzenia BYQ Studio w {source_root}. Sprawdź `source_root` w config.json. ({exc})") from exc
        return FallbackCore()


def _atomic_text(path: Path, value: str) -> None:
    tmp = path.with_suffix(path.suffix + ".byku-tmp")
    tmp.write_text(value, encoding="utf-8")
    os.replace(tmp, path)
