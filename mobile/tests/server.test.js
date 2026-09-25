// Test integracyjny prawdziwego serwera PHP (ten sam kod, który idzie na Hostinger).
import test, { before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn, execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { reel } from "./helpers.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const HAS_PHP = spawnSync("php", ["-v"]).status === 0;
const TOKEN = "t".repeat(64), PASSWORD = "Bardzo-Mocne-Haslo-2026";
let priv, servers = [], base, baseFuture;

const sha = b => createHash("sha256").update(b).digest("hex");

async function startServer(port, env = {}) {
  const proc = spawn("php", ["-S", `127.0.0.1:${port}`, "-t", ROOT, join(ROOT, "tests/router.php")],
    { env: { ...process.env, BYKU_PRIVATE_DIR: priv, BYKU_INSECURE_COOKIE: "1", ...env }, stdio: "ignore" });
  servers.push(proc);
  for (let i = 0; i < 50; i++) {
    try { await fetch(`http://127.0.0.1:${port}/api/session`); return `http://127.0.0.1:${port}`; }
    catch { await new Promise(r => setTimeout(r, 100)); }
  }
  throw new Error("PHP nie wystartował");
}

before(async () => {
  if (!HAS_PHP) return;
  priv = mkdtempSync(join(tmpdir(), "byku-private-"));
  execFileSync("php", [join(ROOT, "api/tools/make-config.php"), priv, "damian"], { env: { ...process.env, BYKU_PASSWORD: PASSWORD, BYKU_UPLOAD_TOKEN: TOKEN } });
  const port = 18700 + Math.floor(Math.random() * 200);
  base = await startServer(port);
  // Ten sam katalog prywatny, zegar przesunięty o 8 dni — symulacja wygaśnięcia sesji.
  baseFuture = await startServer(port + 1, { BYKU_TEST_NOW: String(Math.floor(Date.now() / 1000) + 8 * 86400) });
});
after(() => { servers.forEach(p => p.kill()); if (priv) rmSync(priv, { recursive: true, force: true }); });

const opts = { skip: !HAS_PHP && "brak PHP" };
const mobile = (cookie, extra = {}) => ({ headers: { "X-Byku-Client": "mobile", "Content-Type": "application/json", ...(cookie ? { Cookie: cookie } : {}) }, ...extra });
const auth = { Authorization: `Bearer ${TOKEN}` };
async function login(url = base) {
  const r = await fetch(`${url}/api/login`, { method: "POST", ...mobile(null), body: JSON.stringify({ login: "damian", password: PASSWORD }) });
  assert.equal(r.status, 200);
  const cookie = r.headers.get("set-cookie");
  assert.match(cookie, /HttpOnly/i); assert.match(cookie, /SameSite=Strict/i);
  return cookie.split(";")[0];
}

// Paczka z prawdziwymi bajtami i sumami.
const bytes = { "film.mp4": Buffer.from("FILM".repeat(5000)), "miniaturka.png": Buffer.from("PNG"), "opis-do-skopiowania.txt": Buffer.from("Opis\n"), "hashtagi.txt": Buffer.from("#byku\n") };
function manifest(overrides = {}) {
  const m = { ...reel(), ...overrides };
  m.files = m.files.map(f => ({ ...f, sha256: sha(bytes[f.name]), size: bytes[f.name].length }));
  return m;
}
async function upload(m, tamper = null) {
  for (const f of m.files) {
    const body = tamper === f.name ? Buffer.from("podmiana") : bytes[f.name];
    const q = new URLSearchParams({ package: m.package_id, rev: m.content_revision, name: f.name });
    const r = await fetch(`${base}/api/upload/file?${q}`, { method: "PUT", headers: { ...auth, "X-Sha256": f.sha256 }, body });
    if (tamper === f.name) return r;
    assert.equal(r.status, 200, await r.text());
  }
  return fetch(`${base}/api/upload/commit`, { method: "POST", headers: { ...auth, "Content-Type": "application/json" }, body: JSON.stringify(m) });
}

test("brak sesji oznacza odmowę dostępu (serwer)", opts, async () => {
  for (const path of ["/api/index", "/api/file?package=atlet--post-1&rev=" + "b".repeat(64) + "&name=film.mp4"]) {
    const r = await fetch(base + path);
    assert.equal(r.status, 401);
    const body = await r.json();
    assert.equal(body.packages, undefined);
  }
  const s = await (await fetch(`${base}/api/session`)).json();
  assert.equal(s.authenticated, false);
});

test("desktop bez tokenu nie może wysyłać", opts, async () => {
  const r = await fetch(`${base}/api/upload/commit`, { method: "POST", body: "{}" });
  assert.equal(r.status, 401);
  const r2 = await fetch(`${base}/api/events/export`, { headers: { Authorization: "Bearer zly" } });
  assert.equal(r2.status, 401);
});

test("błędna suma SHA-256 blokuje przyjęcie pliku", opts, async () => {
  const r = await upload(manifest(), "film.mp4");
  assert.equal(r.status, 422);
});

test("wysyłka, duplikat i starsza wersja", opts, async () => {
  const first = manifest({ exported_at: "2026-09-25T10:00:00Z" });
  let r = await upload(first);
  assert.equal(r.status, 200, await r.clone().text());
  assert.equal((await r.json()).state, "new");
  r = await upload(first);
  assert.equal((await r.json()).duplicate, true); // ponowna wysyłka nie tworzy duplikatu
  const older = manifest({ content_revision: "c".repeat(64), exported_at: "2026-09-01T10:00:00Z" });
  r = await upload(older);
  assert.equal(r.status, 409); // starsza nie zastępuje nowszej
  const cookie = await login();
  const index = await (await fetch(`${base}/api/index`, mobile(cookie))).json();
  assert.equal(index.packages.length, 1);
  assert.equal(index.packages[0].content_revision, first.content_revision);
});

test("poprawna sesja daje dostęp do indeksu i plików (z Range)", opts, async () => {
  const cookie = await login();
  const index = await (await fetch(`${base}/api/index`, mobile(cookie))).json();
  const m = index.packages[0];
  const r = await fetch(`${base}/${m.base_url}&name=film.mp4`, mobile(cookie));
  assert.equal(r.status, 200);
  const body = Buffer.from(await r.arrayBuffer());
  assert.equal(sha(body), m.files.find(f => f.name === "film.mp4").sha256);
  const part = await fetch(`${base}/${m.base_url}&name=film.mp4`, mobile(cookie, { headers: { Cookie: cookie, Range: "bytes=0-3" } }));
  assert.equal(part.status, 206);
  assert.equal(Buffer.from(await part.arrayBuffer()).toString(), "FILM");
  const traversal = await fetch(`${base}/${m.base_url}&name=..%2Fconfig.php`, mobile(cookie));
  assert.equal(traversal.status, 400);
});

test("wylogowanie blokuje dane", opts, async () => {
  const cookie = await login();
  assert.equal((await fetch(`${base}/api/index`, mobile(cookie))).status, 200);
  const out = await fetch(`${base}/api/logout`, { method: "POST", ...mobile(cookie), body: "{}" });
  assert.equal(out.status, 200);
  assert.equal((await fetch(`${base}/api/index`, mobile(cookie))).status, 401);
});

test("wygasła sesja wymusza ponowne logowanie", opts, async () => {
  const cookie = await login();
  const r = await fetch(`${baseFuture}/api/index`, mobile(cookie));
  assert.equal(r.status, 401);
  assert.match((await r.json()).error, /wygasła/);
});

test("zdarzenia telefonu: deduplikacja i eksport dla desktopu", opts, async () => {
  const cookie = await login();
  const events = [{ event_id: "evt-00000001", type: "manual_check", package_id: "atlet--post-1", post_id: "post-1", brand: "atlet" }, { event_id: "evt-00000001", type: "manual_check" }, { event_id: "evt-00000002", type: "zly-typ" }];
  const r = await (await fetch(`${base}/api/events`, { method: "POST", ...mobile(cookie), body: JSON.stringify({ events }) })).json();
  assert.deepEqual(r, { accepted: 1, skipped: 2 });
  const again = await (await fetch(`${base}/api/events`, { method: "POST", ...mobile(cookie), body: JSON.stringify({ events }) })).json();
  assert.equal(again.accepted, 0);
  const exported = await (await fetch(`${base}/api/events/export`, { headers: auth })).json();
  assert.equal(exported.events.length, 1);
  assert.equal(exported.events[0].user, "damian");
});

test("żądanie z obcej strony (bez nagłówka klienta) jest odrzucone", opts, async () => {
  const r = await fetch(`${base}/api/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ login: "damian", password: PASSWORD }) });
  assert.equal(r.status, 403);
});

test("limit prób logowania", opts, async () => {
  let last;
  for (let i = 0; i < 6; i++) last = await fetch(`${base}/api/login`, { method: "POST", ...mobile(null), body: JSON.stringify({ login: "damian", password: "zle" }) });
  assert.equal(last.status, 429);
});
