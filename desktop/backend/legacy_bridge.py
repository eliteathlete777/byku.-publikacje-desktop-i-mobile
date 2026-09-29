from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .studio_adapter import StudioAdapter


# Etapy wrzutu w kolejności, jak raportują je uploadery (krok w BYQ_STATUS -> nazwa dla Damiana).
UPLOAD_STEPS = [
    ("start", "Przeglądarka otwarta", ("start", "nawigacja")),
    ("konto", "Właściwe konto", ("konto",)),
    ("plik", "Film wgrany", ("wgranie_pliku", "tryb_zdjec", "wgranie_zdjec")),
    ("opis", "Opis wklejony", ("opis",)),
    ("okladka", "Okładka", ("okladka",)),
    ("muzyka", "Muzyka", ("muzyka", "dzwiek")),
    ("lokalizacja", "Lokalizacja", ("lokalizacja",)),
    ("znaczniki", "Znaczniki FB", ("znaczniki",)),
    ("termin", "Termin ustawiony", ("harmonogram_dzien", "harmonogram_godzina")),
    ("gotowe", "Gotowe — kliknij Zaplanuj", ("gotowe_do_klikniecia",)),
]
_RANK = {"ok": 1, "w_toku": 2, "blad": 3}


def _human_problem(text: str) -> str:
    """Pierwsze zdanie komunikatu uploadera, bez technicznych nazw wyjątków."""
    if "has been closed" in text or "TargetClosed" in text:
        return "Okno przeglądarki zostało zamknięte w trakcie wrzutu."
    text = re.sub(r"^próba \d+/\d+:\s*", "", text.strip())
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return first if not re.search(r"[A-Z][a-z]+Error|\(\'|Locator\.", first) else "Uploader zatrzymał się na tym etapie."


def upload_steps(log_text: str, channel: str) -> tuple[list[dict], str]:
    """Log konsoli -> [{id, label, state: todo|running|ok|error}] + czytelny opis problemu (albo "")."""
    platforms = {"obie": {"instagram", "facebook", "meta"}}.get(channel, {channel})
    per_platform: dict[tuple[str, str], str] = {}   # (platforma, krok) -> ostatni status
    problem = ""
    for line in log_text.splitlines():
        if not line.startswith("BYQ_STATUS:"):
            continue
        try:
            entry = json.loads(line[len("BYQ_STATUS:"):])
        except ValueError:
            continue
        if entry.get("platforma") not in platforms:
            continue
        per_platform[(entry["platforma"], entry.get("krok", ""))] = entry.get("status", "")
        if entry.get("status") == "blad" and entry.get("szczegoly"):
            problem = _human_problem(str(entry["szczegoly"]))
    latest: dict[str, str] = {}   # krok -> najgorszy z ostatnich statusów platform (IG i FB razem)
    for (_, krok), status in per_platform.items():
        if _RANK.get(status, 0) > _RANK.get(latest.get(krok, ""), 0):
            latest[krok] = status
    steps = []
    for sid, label, keys in UPLOAD_STEPS:
        if sid == "znaczniki" and channel != "obie":
            continue
        states = [latest[k] for k in keys if k in latest]
        if "blad" in states:
            state = "error"
        elif "w_toku" in states:
            state = "running"
        elif states:
            state = "ok"
        else:
            state = "todo"
        steps.append({"id": sid, "label": label, "state": state})
    if "nieoczekiwany_blad" in latest and not any(s["state"] == "error" for s in steps):
        for s in steps:
            if s["state"] in ("running", "todo"):
                s["state"] = "error"
                break
    return steps, problem


class LegacyBridge:
    """Jawny adapter do dojrzałych funkcji starego Studio; bez atrap i duplikacji."""

    def __init__(self, adapter: StudioAdapter):
        self.adapter = adapter
        self.runs: dict[tuple[str, str], dict] = {}  # (post_id, kanał) -> uruchomiony uploader tej sesji panelu

    def uploads(self) -> list[dict]:
        """Uploadery odpalone z panelu jako lista etapów (checkboxy dla Damiana).

        Etapy czytamy z linii BYQ_STATUS w logu konsoli; surowy log zostaje na dysku (pole log) do diagnozy.
        """
        out = []
        for (post_id, channel), run in self.runs.items():
            proc = run["proc"]
            code = proc.poll()
            if code is not None and run.get("fh"):
                run["fh"].close()
                run["fh"] = None
            text = ""
            if run["log"] and Path(run["log"]).is_file():
                try:
                    text = Path(run["log"]).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    text = ""
            steps, problem = upload_steps(text, channel)
            if code not in (None, 0) and not problem:
                problem = "Uploader zakończył się błędem, zanim zgłosił etap. Okna przeglądarki nie zamykaj, sprawdzę przyczynę."
            out.append({"post_id": post_id, "channel": channel, "pid": proc.pid, "running": code is None,
                        "exit_code": code, "started": run["started"], "log": run["log"],
                        "steps": steps, "problem": problem})
        return sorted(out, key=lambda r: r["started"], reverse=True)

    def available(self) -> bool:
        return bool(self.adapter.core is not None and getattr(self.adapter.core, "legacy", False))

    def _require(self, what: str) -> None:
        if not self.available():
            raise NotImplementedError(f"{what} wymaga rdzenia BYQ Studio (source_root). Obecny rdzeń: "
                                      f"{getattr(self.adapter.core, 'name', 'brak')}.")

    def open_generator(self, brand: str) -> dict:
        self._require("Pełny Generator")
        from studio.rdzen.most_generatora import otworz_generator, zapisz_marke_generatora
        zapisz_marke_generatora(brand)
        result = otworz_generator()
        if not result.get("ok"):
            raise RuntimeError(result.get("blad") or "Nie udało się uruchomić Generatora")
        return result

    def publication_capabilities(self, post_id: str) -> dict:
        if not self.available():
            card = self.adapter.get(post_id)
            return {"hd": {"stan": "niedostępny", "etykieta": "brak rdzenia Studio", "sciezka": ""}, "awaiting_music": False,
                    "is_carousel": card["assets"]["type"] == "carousel",
                    "channels": [k for k, v in card["channels"].items() if v.get("enabled")],
                    "adapter": None, "final_click": "manual", "legacy": False}
        from studio.rdzen.magazyn import wczytaj_paczke
        from studio.rdzen.pulpit_wrzutu import czeka_na_muzyke, stan_hd_paczki
        folder = self.adapter.folder_for(post_id)
        package = wczytaj_paczke(folder, sprawdz_sumy=False)
        hd = stan_hd_paczki(folder, package)
        return {
            "hd": {**hd, "sciezka": str(hd.get("sciezka") or "")},
            "awaiting_music": bool(czeka_na_muzyke(post_id)),
            "is_carousel": bool(package.jest_karuzela),
            "channels": list(package.platformy),
            "adapter": "studio.rdzen.most_publikacji",
            "final_click": "manual",
            "legacy": True,
        }

    def prepare_publication(self, post_id: str, channel: str, retry: bool = False) -> dict:
        if not self.adapter.settings.allow_publication:
            raise PermissionError("Publikowanie jest zablokowane (allow_publication=false). Końcowe kliknięcie i tak zawsze wykonujesz ręcznie.")
        if channel not in {"tiktok", "instagram", "facebook", "obie"}:
            raise ValueError("Nieprawidłowy kanał")
        self._require("Przygotowanie publikacji")
        running = self.runs.get((post_id, channel))
        if running and running["proc"].poll() is None:
            raise RuntimeError(f"Uploader {channel} dla tej paczki już pracuje (PID {running['proc'].pid}). "
                               "Dokończ w jego oknie przeglądarki albo poczekaj na koniec.")
        from studio.rdzen.most_publikacji import przygotuj_wrzut, uruchom_uploader
        prepared = przygotuj_wrzut(post_id, channel, root=self.adapter.settings.queue, ponownie=retry)
        if not prepared.get("ok"):
            raise RuntimeError("; ".join(prepared.get("problemy") or ["Nie udało się przygotować wrzutu"]))
        process = uruchom_uploader(prepared["cmd"], post_id=post_id, platforma=channel)
        self.runs[(post_id, channel)] = {"proc": process, "log": getattr(process, "_byq_log", ""),
                                         "fh": getattr(process, "_byq_log_fh", None),
                                         "started": datetime.now().isoformat(timespec="seconds")}
        return {"ok": True, "pid": process.pid, "post_id": post_id, "channel": channel,
                "retry": retry, "stage": "awaiting_manual_final_click", "folder": prepared.get("folder"),
                "media": prepared.get("wideo")}

    def music_ready(self, post_id: str) -> dict:
        if not self.adapter.settings.allow_publication:
            raise PermissionError("Sygnał muzyki jest zablokowany do czasu jawnego włączenia publikowania.")
        self._require("Sygnał muzyki")
        from studio.rdzen.pulpit_wrzutu import daj_sygnal_muzyki
        return {"ok": True, "path": str(daj_sygnal_muzyki(post_id))}

    def verify(self, post_id: str) -> dict:
        self._require("Weryfikacja na platformach")
        from studio.rdzen.magazyn import wczytaj_paczke
        from studio.rdzen.weryfikacja_statusu import raport_paczki
        folder = self.adapter.folder_for(post_id)
        return raport_paczki(wczytaj_paczke(folder, sprawdz_sumy=False))
