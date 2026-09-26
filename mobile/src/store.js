const KEYS = { manifests: "byku.mobile.manifests.v1", events: "byku.mobile.events.v1", settings: "byku.mobile.settings.v1", lastSync: "byku.mobile.last-sync.v1" };
const parse = (value, fallback) => { try { return JSON.parse(value) ?? fallback; } catch { return fallback; } };

export function createStore(storage = (() => { try { return localStorage; } catch { return null; } })()) {
  if (!storage) { const mem = new Map(); storage = { getItem: k => mem.get(k) ?? null, setItem: (k, v) => mem.set(k, v) }; }
  const read = (key, fallback) => { try { return parse(storage.getItem(key), fallback); } catch { return fallback; } };
  const write = (key, value) => { try { storage.setItem(key, JSON.stringify(value)); } catch {} };
  return {
    manifests: () => read(KEYS.manifests, []),
    saveManifests: value => write(KEYS.manifests, value),
    events: () => read(KEYS.events, []),
    saveEvents: value => write(KEYS.events, value),
    settings: () => { const saved = read(KEYS.settings, {}); return { brand: saved.brand || "atlet", indexUrl: saved.indexUrl || "paczki/index.json" }; },
    saveSettings: value => write(KEYS.settings, value),
    lastSync: () => read(KEYS.lastSync, null),
    saveLastSync: value => write(KEYS.lastSync, value)
  };
}
