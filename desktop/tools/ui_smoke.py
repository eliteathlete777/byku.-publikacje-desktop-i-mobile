from pathlib import Path
from http.server import ThreadingHTTPServer
from threading import Thread
import sys
from playwright.sync_api import sync_playwright
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run import Handler

OUT=Path(__file__).resolve().parents[1]/"data"
server=ThreadingHTTPServer(("127.0.0.1",8901),Handler)
Thread(target=server.serve_forever,daemon=True).start()
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={"width":1440,"height":900}, device_scale_factor=1)
    errors=[]
    page.on("console",lambda m: errors.append(f"console:{m.type}:{m.text}") if m.type=="error" else None)
    page.on("pageerror",lambda e: errors.append(f"page:{e}"))
    page.goto("http://127.0.0.1:8901",wait_until="networkidle")
    page.wait_for_selector(".row")
    assert page.locator(".row").count()>0
    assert page.locator(".thumb[src]").count()>0
    page.locator(".row").first.click()
    page.get_by_role("button",name="Treść",exact=True).click()
    assert page.locator("#description").is_visible()
    page.screenshot(path=str(OUT/"ui-1440.png"),full_page=True)
    for width in (1280,1024):
        page.set_viewport_size({"width":width,"height":800}); page.wait_for_timeout(150)
        page.screenshot(path=str(OUT/f"ui-{width}.png"),full_page=True)
    print({"rows":page.locator(".row").count(),"thumbs":page.locator(".thumb[src]").count(),"errors":errors})
    browser.close()
server.shutdown()
