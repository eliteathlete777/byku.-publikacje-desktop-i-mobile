from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
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
    ("termin", "Termin ustawiony", ("harmonogram_dzien", "harmonogram_godzina")),
    ("gotowe", "Gotowe — kliknij Zaplanuj", ("gotowe_do_klikniecia",)),
]
_RANK = {"ok": 1, "w_toku": 2, "blad": 3}


STALL_S = 120        # tyle bez nowej linii w logu = zawieszony (start przeglądarki trwa ~35 s)
WATCH_EVERY_S = 5


def _read(log: str | None) -> str:
    try:
        return Path(log).read_text(encoding="utf-8", errors="replace") if log and Path(log).is_file() else ""
    except OSError:
        return ""


def _size(log: str | None) -> int:
    try:
        return Path(log).stat().st_size if log else -1
    except OSError:
        return -1


def _archive_log(post_id: str, channel: str) -> None:
    """uruchom_uploader nadpisuje log tej nogi; poprzedni odkładamy z godziną, żeby diagnoza nie ginęła."""
    try:
        from niezawodnosc import STATUS_DIR
        old = Path(STATUS_DIR) / f"{post_id}-{channel}-konsola.log"
        if old.is_file():
            stamp = datetime.fromtimestamp(old.stat().st_mtime).strftime("%Y%m%d-%H%M%S")
            old.replace(old.with_name(f"{old.stem}-{stamp}.log"))
    except Exception:
        pass


def _clear_orphan_lock(post_id: str, channel: str) -> bool:
    """Blokada po martwym uploaderze. niezawodnosc sam odmawia, gdy Zaplanuj było już klikane (duplikat)."""
    if _uploader_alive(post_id, channel):
        return False
    try:
        from niezawodnosc import zdejmij_osierocona_blokade
        return bool(zdejmij_osierocona_blokade(post_id, channel))
    except Exception:
        return False


def _python_processes() -> list[tuple[int, str]]:
    """(pid, linia komend) żywych procesów Pythona. Bajty + UTF-8: polskie litery w nazwie filmu
    (np. „przytyło”) wywracały dekodowanie text=True (stdout = None → błąd 'splitlines')."""
    if os.name != "nt":
        return []
    try:
        raw = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
             "Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }"],
            capture_output=True, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    out = []
    for line in (raw or b"").decode("utf-8", errors="replace").splitlines():
        pid, _, cmd = line.partition("|")
        if pid.strip().isdigit():
            out.append((int(pid), cmd))
    return out


def _uploader_alive(post_id: str, channel: str = "") -> bool:
    """Czy w systemie żyje uploader tej paczki (także z BYQ Studio). Z kanałem: tylko ta noga —
    TikTok i Meta to osobne przeglądarki i mogą iść równolegle."""
    skrypt = (r"tiktok(_karuzela)?_uploader\.py\b" if channel == "tiktok"
              else r"meta(_karuzela)?_uploader\.py\b" if channel else r"_uploader\.py\b")
    return any(post_id in cmd and re.search(skrypt, cmd) for _, cmd in _python_processes())


class _AdoptedProcess:
    """Uploader, który przeżył restart panelu (log idzie do pliku, więc żyje dalej) — pilnowany po PID."""

    def __init__(self, pid: int):
        self.pid = pid

    def poll(self):
        return None if any(pid == self.pid for pid, _ in _python_processes()) else 0

    def kill(self):
        try:
            os.kill(self.pid, 9)
        except OSError:
            pass

    def wait(self, timeout=None):
        return 0


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
        if getattr(adapter.settings, "mode", "") == "production":  # testy/sandbox nie dotykają żywych uploaderów
            threading.Thread(target=self._adopt_running, daemon=True).start()

    def _adopt_running(self) -> None:
        """Po restarcie panelu: przejmij żywe uploadery (np. czekające na dźwięk), żeby lista etapów
        i przycisk „Muzyka dobrana” nie zniknęły."""
        try:
            from niezawodnosc import STATUS_DIR
        except Exception:
            return
        for pid, cmd in _python_processes():
            m_script = re.search(r"(tiktok|meta)(_karuzela)?_uploader\.py\b", cmd)
            m_post = re.search(r"byq-\d{8}-\d{6}-\d+", cmd)
            if not (m_script and m_post):
                continue
            post_id = m_post.group(0)
            logs = sorted(Path(STATUS_DIR).glob(f"{post_id}-*-konsola.log"), key=lambda x: x.stat().st_mtime, reverse=True)
            logs = [x for x in logs if (x.name == f"{post_id}-tiktok-konsola.log") == (m_script.group(1) == "tiktok")]
            if not logs:
                continue
            channel = logs[0].name[len(post_id) + 1:-len("-konsola.log")]
            if (post_id, channel) in self.runs:
                continue
            run = {"proc": _AdoptedProcess(pid), "log": str(logs[0]), "fh": None, "phase": "running",
                   "started": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(logs[0].stat().st_ctime))}
            self.runs[(post_id, channel)] = run
            threading.Thread(target=self._watch, args=(post_id, channel, run), daemon=True).start()

    def uploads(self) -> list[dict]:
        """Uploadery odpalone z panelu jako lista etapów (checkboxy dla Damiana).

        Etapy czytamy z linii BYQ_STATUS w logu konsoli; surowy log zostaje na dysku (pole log) do diagnozy.
        """
        out = []
        for (post_id, channel), run in list(self.runs.items()):
            proc = run.get("proc")
            code = proc.poll() if proc else None
            if code is not None and run.get("fh"):
                run["fh"].close()
                run["fh"] = None
            steps, problem = upload_steps(_read(run.get("log")), channel)
            prep_state = {"preparing": "running", "failed": "error"}.get(run.get("phase"), "ok")
            steps.insert(0, {"id": "przygotowanie", "label": "Film przygotowany (HD)", "state": prep_state})
            problem = run.get("problem") or problem
            if code not in (None, 0) and not problem:
                problem = "Uploader zakończył się błędem, zanim zgłosił etap. Okna przeglądarki nie zamykaj."
            running = run.get("phase") == "preparing" or (proc is not None and code is None)
            out.append({"post_id": post_id, "channel": channel, "pid": getattr(proc, "pid", None), "running": running,
                        "exit_code": code, "started": run["started"], "log": run.get("log", ""),
                        "steps": steps, "problem": problem, "stopped": run.get("stopped", "")})
        return sorted(out, key=lambda r: r["started"], reverse=True)

    # ---------- start w tle + strażnik postępu ----------
    def _launch(self, post_id: str, channel: str, retry: bool, run: dict) -> None:
        """Wątek: HD + walidacja (przygotuj_wrzut), start uploadera, potem pilnowanie postępu."""
        try:
            from studio.rdzen.most_publikacji import przygotuj_wrzut, uruchom_uploader
            prepared = przygotuj_wrzut(post_id, channel, root=self.adapter.settings.queue, ponownie=retry)
            if not prepared.get("ok"):
                run.update(phase="failed", problem="; ".join(prepared.get("problemy") or ["Nie udało się przygotować wrzutu"]))
                return
            _archive_log(post_id, channel)
            process = uruchom_uploader(prepared["cmd"], post_id=post_id, platforma=channel)
            run.update(proc=process, log=getattr(process, "_byq_log", ""), fh=getattr(process, "_byq_log_fh", None), phase="running")
        except Exception as exc:  # błąd ma być widoczny na liście, nie w konsoli serwera
            run.update(phase="failed", problem=f"Przygotowanie wrzutu padło: {exc}")
            return
        self._watch(post_id, channel, run)

    def _watch(self, post_id: str, channel: str, run: dict) -> None:
        """Brak nowej linii w logu przez STALL_S (i nie czekamy na Damiana) -> przerywamy, zdejmujemy blokadę."""
        proc, last_size, last_change = run["proc"], -1, time.monotonic()
        while proc.poll() is None:
            time.sleep(WATCH_EVERY_S)
            size = _size(run.get("log"))
            if size != last_size:
                last_size, last_change = size, time.monotonic()
                continue
            steps, _ = upload_steps(_read(run.get("log")), channel)
            state = {s["id"]: s["state"] for s in steps}
            waiting_for_user = state.get("muzyka") == "running" or state.get("gotowe") in ("running", "ok")
            if not waiting_for_user and time.monotonic() - last_change > STALL_S:
                proc.kill()
                proc.wait(timeout=10)
                run["stopped"] = (f"Brak postępu przez {STALL_S // 60} min, przerwałem, żeby nie blokować. "
                                  "Okno przeglądarki zostaje; możesz kliknąć Wrzuć jeszcze raz.")
                run["problem"] = run["stopped"]
                _clear_orphan_lock(post_id, channel)
                return
        _clear_orphan_lock(post_id, channel)
        self._auto_confirm(post_id, channel, run)

    def _auto_confirm(self, post_id: str, channel: str, run: dict) -> bool:
        """Damian 30.09: wrzut z panelu, który ma ✓ na wszystkich etapach (muzyka się nie liczy),
        odhacza nogę jako wrzuconą. Dowód z kalendarza platformy dochodzi osobno (Odśwież kalendarz)."""
        if run.get("confirmed"):
            return True
        steps, _ = upload_steps(_read(run.get("log")), channel)
        if not steps or any(s["state"] != "ok" for s in steps if s["id"] != "muzyka"):
            return False
        leg = "tiktok" if channel == "tiktok" else "meta"
        try:
            self.adapter.set_leg(post_id, leg, True, source="panel_wrzut")
        except Exception as exc:  # brak zapisu nie może wywrócić strażnika
            run["problem"] = f"Wrzut gotowy, ale nie odhaczyłem {leg}: {exc}"
            return False
        run["confirmed"] = True
        return True

    # ---------- odświeżenie kalendarzy platform (TikTok Studio + Terminarz Meta) ----------
    def calendar_status(self) -> dict:
        return dict(getattr(self, "_cal", None) or {"state": "idle"})

    def refresh_calendars(self, brand: str) -> dict:
        """W tle: zrzut LIVE kalendarzy marki (okna przeglądarek marki) i naniesienie na kolejkę."""
        self._require("Odświeżenie kalendarzy")
        if self.calendar_status().get("state") == "running":
            raise RuntimeError("Kalendarze już się odświeżają. Poczekaj na wynik.")
        if any(u["running"] for u in self.uploads()):
            raise RuntimeError("Trwa wrzut. Kalendarz przełączyłby jego okno na Terminarz — odśwież po zakończeniu wrzutu.")
        brands = ["atlet", "rigger"] if brand in ("all", "obie") else [brand]
        self._cal = {"state": "running", "brands": brands, "started": datetime.now().isoformat(timespec="seconds"),
                     "done": [], "result": {}, "problem": ""}

        def work():
            try:
                from studio.rdzen.kalendarz_live import naloz_live_na_kolejke, zrzut_kalendarzy_live
                for b in brands:
                    snap = zrzut_kalendarzy_live(b)
                    wynik = naloz_live_na_kolejke(snap, root=self.adapter.settings.queue)
                    errors = [e for e in (snap.get("blad_tiktok"), snap.get("blad_meta")) if e]
                    self._cal["result"][b] = {"potwierdzone": wynik.get("live_ok", 0), "brak": wynik.get("live_brak", 0),
                                              "tiktok": len(snap.get("tiktok") or []), "meta": len(snap.get("meta") or []),
                                              "bledy": [_human_problem(str(e)) for e in errors]}
                    self._cal["done"].append(b)
                self._cal["mismatches"] = self.write_mismatches(brands)
                self._cal["state"] = "done"
            except Exception as exc:
                self._cal.update(state="failed", problem=_human_problem(str(exc)))

        threading.Thread(target=work, daemon=True).start()
        return self.calendar_status()

    # ---------- rozbieżności: Twój checkbox vs lista platformy ----------
    def mismatches_path(self) -> Path:
        return Path(self.adapter.settings.data_dir) / "rozbieznosci.json"

    def write_mismatches(self, brands: list[str]) -> list[dict]:
        """Po odczycie kalendarzy: gdzie checkbox (Damian/automat) i lista platformy się nie zgadzają.
        Plik czyta agent AI: sprawdza wpis w oknie platformy zdalnie, poprawia odczyt kalendarza albo checkbox."""
        rows = []
        for brand in brands:
            for card in self.adapter.list_cards(brand=brand)["items"]:
                if not card.get("local_target_at"):
                    continue
                for leg, v in (card.get("legs") or {}).items():
                    if v["mismatch"]:
                        rows.append({"post_id": card["post_id"], "brand": brand, "name": card["name"], "leg": leg,
                                     "mismatch": v["mismatch"], "termin": card["local_target_at"],
                                     "opis_start": (card["content"]["description"] or "")[:80]})
        data = {"checked_at": datetime.now().isoformat(timespec="seconds"), "brands": brands, "items": rows}
        try:
            self.mismatches_path().write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass
        return rows

    def mismatches(self) -> dict:
        try:
            return json.loads(self.mismatches_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"checked_at": "", "items": []}

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
        if not self.adapter.cover_custom(self.adapter.folder_for(post_id)):
            raise ValueError("Brak nowej okładki z tytułem. Zrób ją w Studiu miniatury, zanim ruszy wrzut.")
        current = self.runs.get((post_id, channel))
        if current and (current.get("phase") == "preparing" or (current.get("proc") and current["proc"].poll() is None)):
            raise RuntimeError("Ten wrzut już trwa. Poczekaj na checkboxy albo aż strażnik go przerwie.")
        if _uploader_alive(post_id, channel):
            raise RuntimeError("Dla tej paczki i tego kanału działa już uploader (np. z BYQ Studio). Dokończ tamten wrzut.")
        _clear_orphan_lock(post_id, channel)  # tylko gdy nikt nie pracuje i Zaplanuj nie było klikane
        run = {"proc": None, "log": "", "fh": None, "phase": "preparing", "problem": "",
               "started": datetime.now().isoformat(timespec="seconds")}
        self.runs[(post_id, channel)] = run
        threading.Thread(target=self._launch, args=(post_id, channel, retry, run), daemon=True).start()
        return {"ok": True, "post_id": post_id, "channel": channel, "retry": retry, "stage": "preparing"}

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
