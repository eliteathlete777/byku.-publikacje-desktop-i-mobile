from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable

BRANDS = ("atlet", "rigger")
BRAND_LOCKS = {"atlet": ("edge-tiktok-9224", "edge-meta-9222"), "rigger": ("edge-rigger-9223", "chrome-rigger-9333")}


def _studio_live_age(brand: str) -> str:
    from studio.rdzen.kalendarz_live import wczytaj_zrzut_live
    return str(wczytaj_zrzut_live(brand).get("kiedy") or "")


def _studio_live_snapshot(brand: str) -> dict:
    from studio.rdzen.kalendarz_live import zrzut_kalendarzy_live
    return zrzut_kalendarzy_live(brand)


def _studio_persist_live(snap: dict, root: Path) -> dict:
    from studio.rdzen.kalendarz_live import naloz_live_na_kolejke
    return naloz_live_na_kolejke(snap, root=root)


def _studio_persist_jsonl(root: Path) -> dict:
    from studio.rdzen.weryfikacja_statusu import odswiez_weryfikacje_kolejki
    return odswiez_weryfikacje_kolejki(root=root)


class SyncService:
    """„Aktualizuj wszystko”: kalendarze LIVE (TikTok Studio, Meta Terminarz), wysyłki (status/*.jsonl),
    paczki telefonu i czynności z telefonu — przy starcie appki, przy otwarciu okna i na przycisk.

    Kalendarze czyta Studio (Edge/Chrome, tylko odczyt, zero „Zaplanuj”); zrzut trafia do
    status/kalendarz-live-<marka>.json. Do post.json wynik zapisujemy tylko przy
    allow_production_writes — w trybie podglądu desktop nakłada świeży zrzut w pamięci (StudioAdapter).
    """

    def __init__(self, adapter, mobile, *, live_snapshot: Callable[[str], dict] = _studio_live_snapshot,
                 persist_live: Callable[[dict, Path], dict] = _studio_persist_live,
                 persist_jsonl: Callable[[Path], dict] = _studio_persist_jsonl,
                 live_age: Callable[[str], str] = _studio_live_age):
        self.adapter, self.mobile = adapter, mobile
        self.live_snapshot, self.persist_live, self.persist_jsonl, self.live_age = live_snapshot, persist_live, persist_jsonl, live_age
        self.state_file = adapter.settings.data_dir / "sync-state.json"
        self.locks = adapter.settings.data_dir / "locks"
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        try: self.state = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError): self.state = {}
        self.state["running"] = False

    # ── stan ──
    def status(self) -> dict:
        with self._lock: return json.loads(json.dumps(self.state))

    def overview(self) -> dict:
        """Stan + kiedy każda marka miała ostatnio przeczytane kalendarze LIVE (także przez Studio)."""
        live = {}
        for brand in BRANDS:
            try: live[brand] = self.live_age(brand)
            except Exception: live[brand] = ""
        return {**self.status(), "live": live, "writes": bool(self.adapter.settings.allow_production_writes)}

    def _save(self, **changes):
        with self._lock:
            self.state.update(changes)
            snapshot = json.dumps(self.state, ensure_ascii=False, indent=2)
        try: self.state_file.write_text(snapshot, encoding="utf-8")
        except OSError: pass

    def _step(self, steps: list[dict], sid: str, state: str, detail: str = ""):
        for s in steps:
            if s["id"] == sid: s.update(state=state, detail=detail, at=time.strftime("%H:%M:%S"))
        self._save(steps=steps)

    # ── szybka: bez przeglądarek, przy każdym otwarciu okna ──
    def quick(self, trigger: str = "open") -> dict:
        phone = self.sync_phone()
        self._save(quick={"at": _now(), "trigger": trigger, "phone": phone})
        return self.overview()

    def sync_phone(self) -> dict:
        cards = self.adapter.list_cards(brand="all", include_archive=True, selected_channel="instagram")["items"]
        return self.mobile.sync(cards)

    # ── pełna: kalendarze LIVE obu marek + wysyłki + telefon ──
    def start_full(self, trigger: str = "manual", brands: tuple[str, ...] = BRANDS) -> dict:
        with self._lock:
            if self.state.get("running"): return json.loads(json.dumps(self.state))
            self.state["running"] = True
        steps = [{"id": "jsonl", "label": "Wysyłki (status/*.jsonl)", "state": "pending", "detail": ""}]
        steps += [{"id": f"live-{b}", "label": f"Kalendarze LIVE {b.upper()} (TikTok + Meta)", "state": "pending", "detail": ""} for b in brands]
        steps += [{"id": "phone", "label": "Paczki telefonu i czynności", "state": "pending", "detail": ""}]
        self._save(running=True, trigger=trigger, started_at=_now(), finished_at="", error="", steps=steps)
        self._thread = threading.Thread(target=self._run_full, args=(steps, brands), name="sync-full", daemon=True)
        self._thread.start()
        return self.status()

    def wait(self, timeout: float = 30):
        if self._thread: self._thread.join(timeout)

    def _run_full(self, steps: list[dict], brands: tuple[str, ...]):
        writes = self.adapter.settings.allow_production_writes
        root = self.adapter.settings.queue
        failed = []
        try:
            self._step(steps, "jsonl", "running")
            try:
                if writes:
                    r = self.persist_jsonl(root)
                    self._step(steps, "jsonl", "ok", f"{r.get('n', 0)} paczek · potwierdzone {r.get('potwierdzone', 0)} · błędy {r.get('bledy', 0)}")
                else:
                    self._step(steps, "jsonl", "ok", "Tryb podglądu: odczyt bez zapisu do kolejki")
            except Exception as exc:
                failed.append("jsonl"); self._step(steps, "jsonl", "error", str(exc)[:200])
            for brand in brands:
                sid = f"live-{brand}"
                busy = [x for x in BRAND_LOCKS.get(brand, ()) if (self.locks / f"{x}.json").exists()]
                if busy:
                    self._step(steps, sid, "skipped", "Profil przeglądarki zajęty przez trwającą wysyłkę — pominięto"); continue
                self._step(steps, sid, "running", "Otwieram TikTok Studio i Meta Terminarz (tylko odczyt)…")
                try:
                    snap = self.live_snapshot(brand)
                    detail = f"TikTok {len(snap.get('tiktok') or [])} · Meta {len(snap.get('meta') or [])} wpisów"
                    errors = [f"{k}: {str(snap.get(f'blad_{k}'))[:90]}" for k in ("tiktok", "meta") if snap.get(f"blad_{k}")]
                    if writes:
                        live = self.persist_live(snap, root)
                        detail += f" · dopasowane {live.get('live_ok', 0)}"
                    empty = [k for k in ("tiktok", "meta") if not snap.get(k) and not snap.get(f"blad_{k}")]
                    if errors:
                        failed.append(sid); self._step(steps, sid, "error", detail + " · " + " · ".join(errors))
                    elif empty:
                        # Studio nie zgłasza błędu, gdy strona wróci pusta (np. wylogowany profil) — nie udajemy sukcesu.
                        names = " i ".join({"tiktok": "TikTok Studio", "meta": "Meta Business"}[k] for k in empty)
                        self._step(steps, sid, "warn", f"{detail} · pusto w {names} — sprawdź logowanie w tej przeglądarce")
                    else:
                        self._step(steps, sid, "ok", detail)
                except Exception as exc:
                    failed.append(sid); self._step(steps, sid, "error", str(exc)[:200])
            self._step(steps, "phone", "running")
            try:
                r = self.sync_phone()
                self._step(steps, "phone", "ok", f"odświeżone {r['refreshed']} · zdjęte z telefonu {r['hidden']} · w telefonie {r['packages']} · czynności {r['events']}")
            except Exception as exc:
                failed.append("phone"); self._step(steps, "phone", "error", str(exc)[:200])
        finally:
            warned = [s["id"] for s in steps if s["state"] == "warn"]
            self._save(running=False, finished_at=_now(), ok=not failed, warn=", ".join(warned), error=", ".join(failed))


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")
