import test from "node:test";
import assert from "node:assert/strict";
import { createSession, createApi, AuthError } from "../src/session.js";
import { memoryStorage, fakeCaches } from "./helpers.js";

const NOW = Date.parse("2026-09-25T12:00:00Z");
const future = "2026-09-26T00:00:00Z", past = "2026-09-25T11:00:00Z";
const make = () => { const storage = memoryStorage(), caches = fakeCaches(); let now = NOW; const s = createSession({ storage, cacheStorage: caches, now: () => now }); return { storage, caches, s, tick: ms => { now += ms; } }; };

test("brak sesji oznacza odmowę dostępu do danych", () => {
  const { s } = make();
  assert.equal(s.guard(), false);
  assert.equal(s.readCache(), null);
  assert.deepEqual(s.readEvents(), []);
});

test("poprawna sesja daje dostęp do ostatniego odczytu", () => {
  const { s } = make();
  s.start({ user: "damian", expires_at: future });
  s.saveCache({ packages: [{ package_id: "atlet--x" }] });
  assert.equal(s.readCache().packages.length, 1);
});

test("wygasła sesja wymusza ponowne logowanie i czyści dane", () => {
  const { s, storage, caches, tick } = make();
  s.start({ user: "damian", expires_at: future });
  s.saveCache({ packages: [{ package_id: "atlet--x" }] });
  tick(13 * 3600 * 1000);
  assert.equal(s.guard(), false);
  assert.equal(s.readCache(), null);
  assert.equal(Object.keys(storage.dump()).filter(k => k.startsWith("byku.m.")).length, 0);
  assert.deepEqual(caches.deleted, ["byku-media"]);
});

test("wylogowanie blokuje dane i usuwa pliki z pamięci telefonu", async () => {
  const { s, storage, caches } = make();
  s.start({ user: "damian", expires_at: future });
  s.saveCache({ packages: [1] });
  const api = createApi({ fetcher: async () => new Response("{}", { status: 200 }), session: s });
  await api.logout();
  assert.equal(s.readCache(), null);
  assert.equal(storage.getItem("byku.m.cache.damian"), null);
  assert.ok(caches.deleted.includes("byku-media"));
});

test("tryb offline nie ujawnia danych niezalogowanej osobie", async () => {
  const { s, storage } = make();
  storage.setItem("byku.m.session", JSON.stringify({ user: "damian", expires_at: past }));
  storage.setItem("byku.m.cache.damian", JSON.stringify({ packages: [{ package_id: "atlet--tajne" }] }));
  const offlineApi = createApi({ fetcher: async () => { throw new TypeError("Failed to fetch"); }, session: s });
  await assert.rejects(offlineApi.index(), e => e.offline === true);
  assert.equal(s.readCache(), null);
  assert.equal(storage.getItem("byku.m.cache.damian"), null);
});

test("odpowiedź 401 serwera kończy sesję na telefonie", async () => {
  const { s } = make();
  s.start({ user: "damian", expires_at: future });
  s.saveCache({ packages: [1] });
  const api = createApi({ fetcher: async () => new Response(JSON.stringify({ error: "Sesja wygasła" }), { status: 401 }), session: s });
  await assert.rejects(api.index(), AuthError);
  assert.equal(s.isValid(), false);
  assert.equal(s.readCache(), null);
});

test("inny użytkownik nie widzi danych poprzedniego", () => {
  const { s } = make();
  s.start({ user: "damian", expires_at: future });
  s.saveCache({ packages: [1] });
  s.start({ user: "asystent", expires_at: future });
  assert.equal(s.readCache(), null);
});
