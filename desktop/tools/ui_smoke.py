"""Test przeglądarkowy panelu desktop na izolowanej kolejce testowej.

Sprawdza: każdy panel się renderuje, zero błędów konsoli, brak martwych przycisków
(każdy aktywny przycisk ma obsługę, każdy zablokowany ma podany powód),
kluczowe przepływy: edycja treści, hashtagi, paczka telefonu, kalendarz.

Użycie: python tools/ui_smoke.py [--shots KATALOG]
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from dataclasses import replace
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

import run  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.core import FallbackCore  # noqa: E402
from tools.make_sandbox import build  # noqa: E402

VIEWS = ["today", "finish", "transfer", "calendar", "board", "library", "brands", "learning", "archive", "system"]

DEAD_BUTTONS_JS = """
() => [...document.querySelectorAll('button, [role=tab]')].filter(b => b.offsetParent !== null).map(b => ({
  text: (b.innerText || b.getAttribute('aria-label') || '').trim().slice(0, 40),
  disabled: b.disabled,
  reason: b.getAttribute('data-reason') || b.getAttribute('title') || '',
  handled: typeof b.onclick === 'function' || b.type === 'submit' || !!b.closest('label')
})).filter(b => (!b.disabled && !b.handled) || (b.disabled && !b.reason && !b.text.includes('…')))
"""


def main(shots: Path | None) -> dict:
    tmp = tempfile.TemporaryDirectory()
    base = Path(tmp.name)
    settings = Settings(base / "brak", base / "brak", base / "queue", base / "data", "127.0.0.1", 0, "sandbox",
                        False, False, "Europe/Warsaw", core="fallback", drive_sync_dir=base / "drive")
    (base / "drive").mkdir()
    build(settings.sandbox_queue)
    app = run.App(settings, core=FallbackCore())
    server = ThreadingHTTPServer(("127.0.0.1", 0), run.make_handler(app))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    report: dict = {"views": {}, "errors": [], "dead": []}
    with sync_playwright() as p:
        executable = os.environ.get("BYKU_CHROMIUM") or ("/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None)
        browser = p.chromium.launch(headless=True, executable_path=executable)
        page = browser.new_page(viewport={"width": 1600, "height": 950})
        page.on("console", lambda m: report["errors"].append(f"console:{m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: report["errors"].append(f"page:{e}"))
        page.goto(url, wait_until="networkidle")
        page.wait_for_selector(".row")
        for view in VIEWS:
            page.click(f"#nav button[data-view='{view}']")
            page.wait_for_timeout(350)
            dead = page.evaluate(DEAD_BUTTONS_JS)
            report["dead"] += [{**d, "view": view} for d in dead]
            report["views"][view] = page.locator("#view").inner_text()[:80].replace("\n", " ")
            if shots:
                page.screenshot(path=str(shots / f"desktop-{view}.png"), full_page=False)
        # Przepływ: stół → karta → treść → hashtag → zapis i akceptacja
        page.click("#nav button[data-view='today']")
        page.click(".row[data-id='atlet-gumy-plecy'] .material")
        page.click(".tabs button[data-tab='content']")
        page.fill("#description", "Plecy z gumą. Kontrola ruchu ponad ciężar. Zero wymówek, system daje wyniki.")
        page.fill("#tagInput", "plecy"); page.press("#tagInput", "Enter")
        assert page.locator(".chip", has_text="#plecy").count() == 1
        report["dead"] += [{**d, "view": "drawer-content"} for d in page.evaluate(DEAD_BUTTONS_JS)]
        page.click("#approve")
        page.wait_for_selector(".toast.ok")
        card = app.adapter.get("atlet-gumy-plecy")
        assert "#plecy" in card["content"]["hashtags"] and card["content"]["approved"], card["content"]
        if shots:
            page.screenshot(path=str(shots / "desktop-drawer-content.png"))
        # Usunięcie wszystkich hashtagów
        page.click("#clearTags"); page.click("#save"); page.wait_for_timeout(400)
        assert app.adapter.get("atlet-gumy-plecy")["content"]["hashtags"] == ""
        # Kanały i telefon
        for tab in ("channels", "phone", "history", "preview"):
            page.click(f".tabs button[data-tab='{tab}']"); page.wait_for_timeout(250)
            report["dead"] += [{**d, "view": f"drawer-{tab}"} for d in page.evaluate(DEAD_BUTTONS_JS)]
            if shots and tab in ("channels", "phone"):
                page.screenshot(path=str(shots / f"desktop-drawer-{tab}.png"))
        page.click(".row[data-id='atlet-pompki-porecze'] .material")
        page.click(".tabs button[data-tab='phone']")
        page.click("#exportPkg"); page.wait_for_selector(".pkg")
        page.click("#toDrive"); page.wait_for_timeout(400)
        assert (base / "drive" / "atlet" / "do-instagrama" / "atlet-pompki-porecze" / "manifest.json").is_file()
        # Kalendarz: tryby i propozycje
        page.keyboard.press("Escape")
        page.click("#nav button[data-view='calendar']")
        for mode in ("day", "month", "list", "week"):
            page.click(f"[data-mode='{mode}']"); page.wait_for_timeout(150)
        page.click("#propose"); page.wait_for_selector(".variant")
        report["dead"] += [{**d, "view": "calendar-modal"} for d in page.evaluate(DEAD_BUTTONS_JS)]
        if shots:
            page.screenshot(path=str(shots / "desktop-calendar-variants.png"))
        page.click("[data-variant='regular']"); page.wait_for_timeout(500)
        assert app.adapter.get("atlet-karuzela-plan")["local_target_at"], "wariant nie ustawił terminu"
        page.click("#undo"); page.wait_for_timeout(500)
        assert not app.adapter.get("atlet-karuzela-plan")["local_target_at"], "cofnięcie nie zadziałało"
        # Szerokości ekranu
        for width in (1280, 1024, 800):
            page.set_viewport_size({"width": width, "height": 850}); page.wait_for_timeout(150)
            overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            report.setdefault("overflow", {})[width] = overflow
        browser.close()
    server.shutdown()
    tmp.cleanup()
    return report


if __name__ == "__main__":
    shots = None
    if "--shots" in sys.argv:
        shots = Path(sys.argv[sys.argv.index("--shots") + 1]); shots.mkdir(parents=True, exist_ok=True)
    result = main(shots)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    ok = not result["errors"] and not result["dead"] and all(v <= 1 for v in result.get("overflow", {}).values())
    print("UI SMOKE:", "OK" if ok else "BŁĘDY")
    sys.exit(0 if ok else 1)
