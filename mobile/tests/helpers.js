import { readFileSync } from "node:fs";
export const cases = JSON.parse(readFileSync(new URL("../../contract/fixtures/cases.json", import.meta.url), "utf8"));
export const reel = () => structuredClone(cases.find(c => c.name === "poprawna rolka").manifest);

export function memoryStorage() {
  const map = new Map();
  return {
    get length() { return map.size; },
    key: i => [...map.keys()][i] ?? null,
    getItem: k => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: k => map.delete(k),
    dump: () => Object.fromEntries(map)
  };
}
export function fakeCaches() {
  const deleted = [];
  return { deleted, delete: async name => { deleted.push(name); return true; } };
}
