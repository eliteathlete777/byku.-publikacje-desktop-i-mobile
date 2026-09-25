"""Test end-to-end: TikTok → paczka (desktop) → serwer mobilny (PHP) → telefon (PWA) → zgłoszenie → desktop.

Uruchamia prawdziwy kod obu aplikacji: desktop (kolejka testowa), serwer PHP z mobile/api,
PWA w Chromium z widokiem telefonu. Nic nie dotyka danych produkcyjnych.

Użycie: python e2e/test_transfer.py [--shots KATALOG]
"""
from __future__ import annotations

import json
import os
import random
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DESKTOP, MOBILE = REPO / "desktop", REPO / "mobile"
sys.path.insert(0, str(DESKTOP))

from playwright.sync_api import sync_playwright  # noqa: E402

import run  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.core import FallbackCore  # noqa: E402
from tools.make_sandbox import build  # noqa: E402

TOKEN = "e2e" + "x" * 61
PASSWORD = "Test-Haslo-E2E-2026"
PHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 3, "is_mobile": True, "has_touch": True,
         "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


def main(shots: Path | None) -> list[str]:
    checks: list[str] = []
    ok = lambda text: checks.append(text) or print("  ✓", text)
    tmp = Path(tempfile.mkdtemp(prefix="byku-e2e-"))
    private = tmp / "private"
    subprocess.run(["php", str(MOBILE / "api/tools/make-config.php"), str(private), "damian"], check=True, capture_output=True,
                   env={**os.environ, "BYKU_PASSWORD": PASSWORD, "BYKU_UPLOAD_TOKEN": TOKEN})
    port = free_port()
    php = subprocess.Popen(["php", "-S", f"127.0.0.1:{port}", "-t", str(MOBILE), str(MOBILE / "tests/router.php")],
                           env={**os.environ, "BYKU_PRIVATE_DIR": str(private), "BYKU_INSECURE_COOKIE": "1"},
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try: urllib.request.urlopen(url + "/api/session"); break
            except Exception: time.sleep(0.1)

        # ---------- DESKTOP: wykrycie i wysyłka ----------
        settings = Settings(tmp / "brak", tmp / "brak", tmp / "queue", tmp / "data", "127.0.0.1", 0, "sandbox", False, False,
                            "Europe/Warsaw", core="fallback", mobile_server_url=url, mobile_upload_token=TOKEN)
        build(settings.sandbox_queue)
        app = run.App(settings, core=FallbackCore())
        candidates = [c["post_id"] for c in app.mobile.candidates("all")]
        assert candidates[0] == "atlet-pompki-porecze", candidates
        assert "rigger-demontaz-noc" not in candidates
        ok(f"desktop wykrył {len(candidates)} materiały TikTok gotowy / Instagram czeka (opublikowane TikToki pierwsze)")
        for post_id in ("atlet-pompki-porecze", "atlet-karuzela-plan"):
            app.mobile.export(post_id)
            result = app.mobile.to_server(post_id)
            assert result["ok"], result
        ok("desktop wysłał 2 paczki (rolka + karuzela) na serwer z weryfikacją SHA-256")
        card = app.adapter.get("atlet-pompki-porecze")

        with sync_playwright() as p:
            executable = os.environ.get("BYKU_CHROMIUM") or ("/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None)
            browser = p.chromium.launch(headless=True, executable_path=executable)
            ctx = browser.new_context(**PHONE)
            ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=url)
            page = ctx.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))

            # ---------- brak sesji ----------
            page.goto(url + "/", wait_until="networkidle")
            assert page.locator("#loginScreen").is_visible() and not page.locator("#app").is_visible()
            status = page.evaluate("fetch('api/index').then(r => r.status)")
            assert status == 401
            ok("bez logowania: ekran logowania, serwer zwraca 401 dla indeksu")
            if shots: page.screenshot(path=str(shots / "mobile-login.png"))

            # ---------- PWA ----------
            manifest = page.evaluate("fetch('manifest.webmanifest').then(r => r.json())")
            assert manifest["display"] == "standalone" and {"192x192", "512x512"} <= {i["sizes"] for i in manifest["icons"]}
            page.wait_for_function("navigator.serviceWorker && navigator.serviceWorker.controller !== null || navigator.serviceWorker.getRegistration().then(r => !!r)")
            assert page.evaluate("navigator.serviceWorker.getRegistration().then(r => !!r && !!(r.active || r.installing || r.waiting))")
            ok("manifest PWA poprawny (standalone, ikony 192/512), service worker zarejestrowany")

            # ---------- złe hasło, potem poprawne ----------
            page.fill("#loginInput", "damian"); page.fill("#passwordInput", "zle-haslo"); page.click("#loginButton")
            page.wait_for_function("document.querySelector('#loginStatus').textContent.includes('Nieprawidłowy')")
            page.fill("#passwordInput", PASSWORD); page.click("#loginButton")
            page.wait_for_selector(".card")
            assert page.locator(".card").count() == 2
            ok("logowanie: złe hasło odrzucone, poprawne pokazuje 2 paczki")
            page.wait_for_function("[...document.querySelectorAll('.thumb')].every(t => t.style.backgroundImage)")
            if shots: page.screenshot(path=str(shots / "mobile-list.png"))

            # ---------- szczegóły: podgląd, kopiowanie ----------
            page.click(f".card[data-id='atlet--atlet-pompki-porecze']")
            page.wait_for_selector("#preview video")
            ok("podgląd wideo załadowany po sprawdzeniu SHA-256")
            page.click("#copyCaption"); page.wait_for_timeout(200)
            assert page.evaluate("navigator.clipboard.readText()") == card["content"]["description"]
            page.click("#copyTags"); page.wait_for_timeout(200)
            assert page.evaluate("navigator.clipboard.readText()") == card["content"]["hashtags"]
            ok("opis i hashtagi skopiowane do schowka — zgodne z desktopem")
            with page.expect_download() as dl:
                page.click("#downloadThumb")
            assert dl.value.suggested_filename == "miniaturka.png"
            ok("miniatura pobrana na telefon")
            if shots: page.screenshot(path=str(shots / "mobile-detail.png"), full_page=True)
            page.once("dialog", lambda d: d.accept())
            page.click("#reportDone"); page.wait_for_timeout(600)
            page.click("#closeDetail")

            # ---------- karuzela ----------
            page.click(f".card[data-id='atlet--atlet-karuzela-plan']")
            page.wait_for_selector("#preview .slides img")
            assert page.locator("#preview .slides img").count() == 3
            ok("karuzela: 3 slajdy w kolejności, zweryfikowane")
            page.click("#closeDetail")

            # ---------- zgłoszenie wraca na desktop ----------
            page.click("#refreshButton"); page.wait_for_timeout(600)
            pulled = app.mobile.pull_server_events()
            assert pulled["accepted"] >= 3, pulled
            after = app.adapter.get("atlet-pompki-porecze")
            assert not after["channels"]["instagram"]["manual_checked"]
            assert any(e["type"] == "manual_check" for e in app.mobile.mobile_events("atlet-pompki-porecze"))
            ok("zgłoszenie publikacji z telefonu dotarło na desktop jako osobne zdarzenie (haczyk nietknięty)")

            # ---------- ponowne odświeżenie: bez duplikatów ----------
            page.click("#refreshButton"); page.wait_for_timeout(500)
            assert page.locator(".card").count() == 2
            ok("ponowne odświeżenie nie tworzy duplikatów")

            # ---------- nowsza wersja z desktopu ----------
            app.content.save("atlet-karuzela-plan", expected_revision=app.adapter.get("atlet-karuzela-plan")["revision"],
                             description="Nowa wersja opisu karuzeli.", hashtags="#bykuathlete", location="", approve=True)
            time.sleep(1.1)
            app.mobile.export("atlet-karuzela-plan"); app.mobile.to_server("atlet-karuzela-plan")
            page.click("#refreshButton")
            page.wait_for_function("document.querySelector('#syncBar').dataset.state === 'newer'")
            assert page.locator(".chip.newer").count() >= 1
            ok("nowa wersja z desktopu: telefon pokazuje „Dostępna nowsza wersja”")
            if shots: page.screenshot(path=str(shots / "mobile-newer.png"))

            # ---------- offline po zalogowaniu ----------
            ctx.set_offline(True)
            page.reload(wait_until="domcontentloaded"); page.wait_for_timeout(500)
            assert page.locator(".card").count() == 2 and page.locator("#syncBar").get_attribute("data-state") == "offline"
            ok("offline z ważną sesją: ostatni poprawny odczyt widoczny, stan „Offline”")
            if shots: page.screenshot(path=str(shots / "mobile-offline.png"))
            ctx.set_offline(False)

            # ---------- podmieniony plik na serwerze → blokada ----------
            page.reload(wait_until="networkidle")
            page.evaluate("caches.delete('byku-media')")
            stored = next((private / "packages").glob("atlet--atlet-pompki-porecze/*/film.mp4"))
            stored.write_bytes(b"PODMIENIONY PLIK")
            page.click(f".card[data-id='atlet--atlet-pompki-porecze']")
            page.wait_for_selector("#preview .spinner.bad")
            assert "SHA-256" in page.locator("#preview").inner_text()
            ok("podmieniony plik: suma SHA-256 niezgodna — plik zablokowany")
            page.click("#closeDetail")

            # ---------- wylogowanie + offline ----------
            page.once("dialog", lambda d: d.accept())
            page.click("#logoutButton")
            page.wait_for_selector("#loginScreen:not([hidden])")
            leftovers = page.evaluate("Object.keys(localStorage).filter(k => k.startsWith('byku.m.') && k !== 'byku.m.prefs')")
            media = page.evaluate("caches.has('byku-media')")
            assert leftovers == [] and media is False, (leftovers, media)
            ctx.set_offline(True)
            page.reload(wait_until="domcontentloaded"); page.wait_for_timeout(400)
            assert page.locator("#loginScreen").is_visible() and page.locator(".card").count() == 0
            assert "pompki" not in page.content().lower()
            ok("po wylogowaniu offline: zero danych na urządzeniu, tylko ekran logowania")
            ctx.set_offline(False)
            assert not errors, errors
            browser.close()
    finally:
        php.terminate()
        shutil.rmtree(tmp, ignore_errors=True)
    return checks


if __name__ == "__main__":
    shots = None
    if "--shots" in sys.argv:
        shots = Path(sys.argv[sys.argv.index("--shots") + 1]); shots.mkdir(parents=True, exist_ok=True)
    print("E2E TikTok → paczka → telefon → Instagram")
    done = main(shots)
    print(f"E2E: OK ({len(done)} kontroli)")
