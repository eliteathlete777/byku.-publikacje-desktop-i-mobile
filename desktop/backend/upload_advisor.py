"""Doradca wrzutu: gdy uploader stanie, Sonnet 5 patrzy na okno przeglądarki marki i mówi, co kliknąć.

Tylko doradza (Damian 29.09): nic nie klika, niczego nie zamyka. Zrzut robimy przez CDP okna marki
w osobnym procesie (Patchright), rozumowanie i odpowiedź przez Claude API z obrazem.
"""
from __future__ import annotations

import base64
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

MODEL = "claude-sonnet-5"  # Damian 29.09: doradca na Sonnet 5

# Okna marek na stałych portach CDP (niezawodnosc.cdp_port_dla_profilu).
PORTS = {("tiktok", "rigger"): 9223, ("tiktok", "atlet"): 9224, ("meta", "atlet"): 9222, ("meta", "rigger"): 9333}
URL_HINT = {"tiktok": "tiktok.com", "meta": "facebook.com"}

FLOW = {
    "meta": "film → opis → lokalizacja → okładka (miniaturka.png z folderu paczki) → bez znaczników, przełącznik "
            "„Dostosuj post na Facebooka i Instagram” WYŁĄCZONY → Dalej → bez muzyki → Dalej → Zaplanuj → data i godzina "
            "→ końcowe Zaplanuj klika Damian.",
    "tiktok": "film → opis → okładka → lokalizacja → Zaplanuj + data i godzina → dźwięk → końcowe Zaplanuj klika Damian.",
}

TASK = """Jesteś doradcą przy ręcznym dokończeniu wrzutu posta w przeglądarce. Skrypt Pythona wypełniał formularz {platforma} dla marki {marka} i zatrzymał się. Damian ma przed sobą to samo okno, które widzisz na zrzucie.

Właściwa kolejność kroków: {flow}

Twoje zadanie: obejrzyj zrzut, porównaj z listą etapów i komunikatem skryptu, ustal, co już jest zrobione i czego brakuje, i powiedz Damianowi dokładnie, co ma kliknąć, żeby dojść do końcowego „Zaplanuj”. Ty niczego nie klikasz.

Zasady odpowiedzi:
- po polsku, krótko, zwykły tekst bez formatowania (bez gwiazdek, nagłówków i markdown), bez żargonu technicznego i bez nazw błędów programistycznych;
- najpierw jedno zdanie „Co widzę”, potem ponumerowane kroki (max 6) z nazwami przycisków dokładnie tak, jak są na ekranie;
- jeśli film już jest w formularzu, napisz wyraźnie, żeby NIE wgrywał go drugi raz (duplikat);
- jeśli czegoś nie widać na zrzucie, powiedz, gdzie przewinąć albo co sprawdzić, zamiast zgadywać;
- końcowe „Zaplanuj” zawsze klika Damian — przypomnij o sprawdzeniu daty i godziny ({termin}) przed kliknięciem."""


class AdvisorError(RuntimeError):
    pass


_CAPTURE = r"""
import os, sys
from patchright.sync_api import sync_playwright
port, hint, out = int(sys.argv[1]), sys.argv[2], sys.argv[3]
p = sync_playwright().start()
b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=8000)
pages = [pg for c in b.contexts for pg in c.pages if hint in (pg.url or "")]
if not pages:
    print("NOPAGE", flush=True); os._exit(3)
pages[-1].screenshot(path=out, timeout=15000)
print("OK", flush=True)
os._exit(0)   # bez close(): okno przeglądarki zostaje
"""


def capture(channel: str, brand: str, runner: Callable = subprocess.run) -> bytes:
    """PNG okna marki. Brak okna/portu -> AdvisorError z ludzkim opisem."""
    kind = "tiktok" if channel == "tiktok" else "meta"
    port = PORTS.get((kind, brand))
    if not port:
        raise AdvisorError("Nie znam okna przeglądarki tej marki.")
    out = Path(tempfile.gettempdir()) / f"byku-doradca-{kind}-{brand}.png"
    out.unlink(missing_ok=True)
    try:
        res = runner([sys.executable.replace("pythonw.exe", "python.exe"), "-c", _CAPTURE, str(port), URL_HINT[kind], str(out)],
                     capture_output=True, text=True, timeout=60,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as exc:
        raise AdvisorError("Okno przeglądarki nie odpowiedziało na zrzut ekranu.") from exc
    if "NOPAGE" in (res.stdout or ""):
        raise AdvisorError("Okno wrzutu jest zamknięte — nie ma czego oglądać. Kliknij Wrzuć jeszcze raz.")
    if res.returncode != 0 or not out.is_file():
        raise AdvisorError("Nie mogę zajrzeć do okna przeglądarki (zamknięte albo bez połączenia).")
    return out.read_bytes()


def advise(*, png: bytes, channel: str, brand: str, name: str, term: str, steps: list[dict], problem: str,
           log_tail: str, api_key: str, client_factory: Callable | None = None) -> str:
    if not api_key:
        raise AdvisorError("Brak klucza ANTHROPIC_API_KEY w desktop/.env — doradca AI nie działa bez niego.")
    kind = "tiktok" if channel == "tiktok" else "meta"
    platforma = "TikTok Studio" if kind == "tiktok" else "Meta Business Suite (Instagram + Facebook)"
    system = TASK.format(platforma=platforma, marka=brand.upper(), flow=FLOW[kind], termin=term or "z karty")
    stan = "\n".join(f"- {s['label']}: {dict(ok='zrobione', running='w toku', error='ZATRZYMAŁ SIĘ', todo='jeszcze nie')[s['state']]}"
                     for s in steps)
    tekst = (f"Materiał: {name}. Termin: {term or 'brak'}.\n\nEtapy według skryptu:\n{stan}\n\n"
             f"Komunikat skryptu: {problem or 'brak'}\n\nOstatnie linie logu skryptu (dla Ciebie, nie cytuj ich Damianowi):\n{log_tail[-6000:]}")
    if client_factory is None:
        try:
            import anthropic
        except ImportError as exc:
            raise AdvisorError("Brak biblioteki anthropic.") from exc
        client = anthropic.Anthropic(api_key=api_key, timeout=180.0)
    else:
        client = client_factory(api_key)
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                             "data": base64.b64encode(png).decode("ascii")}},
                {"type": "text", "text": tekst},
            ]}],
        )
    except Exception as exc:
        raise AdvisorError(f"Doradca AI nie odpowiedział: {getattr(exc, 'message', exc)}") from exc
    if response.stop_reason == "refusal":
        raise AdvisorError("Doradca AI odmówił odpowiedzi dla tego zrzutu.")
    out = "".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip()
    if not out:
        raise AdvisorError("Doradca AI zwrócił pustą odpowiedź. Spróbuj jeszcze raz.")
    return out
