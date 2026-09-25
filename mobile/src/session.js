// Sesja po stronie telefonu. Prawdziwa ochrona danych jest na serwerze (cookie HttpOnly);
// tutaj pilnujemy, żeby ostatni odczyt offline był widoczny WYŁĄCZNIE przy ważnej sesji
// i żeby wylogowanie / wygaśnięcie / 401 czyściło wszystkie dane z urządzenia.
const PREFIX = "byku.m.";
export const MEDIA_CACHE = "byku-media";

export function createSession({ storage, cacheStorage = null, now = () => Date.now() }) {
  const get = k => { try { return JSON.parse(storage.getItem(PREFIX + k)); } catch { return null; } };
  const set = (k, v) => storage.setItem(PREFIX + k, JSON.stringify(v));

  const api = {
    current() { return get("session"); },
    isValid() {
      const s = get("session");
      return !!(s && s.user && Date.parse(s.expires_at) > now());
    },
    start(session) {
      const prev = get("session");
      if (prev && prev.user !== session.user) api.wipeData(); // inny użytkownik nie widzi cudzych danych
      set("session", { user: session.user, expires_at: session.expires_at });
    },
    /** Sprawdza sesję przed pokazaniem czegokolwiek; wygasła = czyszczenie. */
    guard() {
      if (api.isValid()) return true;
      if (get("session")) api.wipe();
      return false;
    },
    readCache() { return api.guard() ? get(`cache.${get("session").user}`) : null; },
    saveCache(value) { if (api.isValid()) set(`cache.${get("session").user}`, value); },
    readEvents() { return api.guard() ? get(`events.${get("session").user}`) || [] : []; },
    saveEvents(list) { if (api.isValid()) set(`events.${get("session").user}`, list); },
    wipeData() {
      const keys = [];
      for (let i = 0; i < storage.length; i++) { const k = storage.key(i); if (k && k.startsWith(PREFIX) && k !== PREFIX + "prefs") keys.push(k); }
      keys.forEach(k => storage.removeItem(k));
      if (cacheStorage) return cacheStorage.delete(MEDIA_CACHE).catch(() => false);
      return Promise.resolve(true);
    },
    wipe() { const p = api.wipeData(); storage.removeItem(PREFIX + "session"); return p; }
  };
  return api;
}

export class AuthError extends Error {}

/** Klient API: każda odpowiedź 401 kończy sesję lokalnie i czyści dane. */
export function createApi({ fetcher, session }) {
  async function request(path, opt = {}) {
    let response;
    try {
      response = await fetcher(path, { credentials: "same-origin", cache: "no-store", ...opt,
        headers: { "X-Byku-Client": "mobile", ...(opt.body ? { "Content-Type": "application/json" } : {}), ...(opt.headers || {}) } });
    } catch (e) {
      throw Object.assign(new Error("Brak połączenia"), { offline: true, cause: e });
    }
    if (response.status === 401) { await session.wipe(); throw new AuthError((await safeJson(response)).error || "Zaloguj się ponownie"); }
    return response;
  }
  async function json(path, opt) {
    const r = await request(path, opt);
    const data = await safeJson(r);
    if (!r.ok) throw Object.assign(new Error(data.error || `Błąd serwera (${r.status})`), { status: r.status });
    return data;
  }
  return {
    request, json,
    async login(login, password) {
      const s = await json("api/login", { method: "POST", body: JSON.stringify({ login, password }) });
      session.start(s); return s;
    },
    async logout() {
      try { await request("api/logout", { method: "POST", body: "{}" }); } catch { /* offline: i tak czyścimy */ }
      await session.wipe();
    },
    async check() {
      const s = await json("api/session");
      if (!s.authenticated) { await session.wipe(); throw new AuthError(s.reason || "Zaloguj się"); }
      session.start(s); return s;
    },
    index: () => json("api/index"),
    sendEvents: events => json("api/events", { method: "POST", body: JSON.stringify({ events }) })
  };
}

async function safeJson(r) { try { return await r.json(); } catch { return {}; } }
