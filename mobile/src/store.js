const KEYS = { manifests: "byku.mobile.manifests.v1", events: "byku.mobile.events.v1", settings: "byku.mobile.settings.v1", lastSync: "byku.mobile.last-sync.v1" };
const parse = (value, fallback) => { try { return JSON.parse(value) ?? fallback; } catch { return fallback; } };

export function createStore(storage = localStorage) {
  const read = (key, fallback) => parse(storage.getItem(key), fallback);
  const write = (key, value) => storage.setItem(key, JSON.stringify(value));
  return {
    manifests: () => read(KEYS.manifests, []),
    saveManifests: value => write(KEYS.manifests, value),
    events: () => read(KEYS.events, []),
    saveEvents: value => write(KEYS.events, value),
    settings: () => read(KEYS.settings, { brand: "atlet", indexUrl: "" }),
    saveSettings: value => write(KEYS.settings, value),
    lastSync: () => read(KEYS.lastSync, null),
    saveLastSync: value => write(KEYS.lastSync, value)
  };
}
