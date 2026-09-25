// Logika paczek: łączenie indeksu z ostatnim poprawnym odczytem, stany, SHA-256.
import { validateManifest, INCOMPATIBLE } from "./contract.js";

export const STATE_LABEL = {
  current: "Aktualna", newer: "Nowa wersja", incomplete: "Niekompletna",
  incompatible: "Niezgodna", offline: "Offline — ostatni odczyt"
};

const time = v => { const t = Date.parse(v || ""); return Number.isFinite(t) ? t : 0; };

/**
 * Łączy lokalne paczki (ostatni poprawny odczyt) z indeksem serwera.
 * - klucz: package_id (marka + post_id) → brak duplikatów przy ponownym odświeżeniu,
 * - starszy exported_at nigdy nie zastępuje nowszego,
 * - paczka niezgodna/niekompletna nie zastępuje poprawnej lokalnej.
 */
export function mergeIndex(local = [], remote = []) {
  const byId = new Map(local.map(p => [p.package_id, p]));
  const results = [];
  const seen = new Set();
  for (const incoming of remote) {
    const errors = validateManifest(stripServerFields(incoming));
    const id = incoming?.package_id || `nieznana-${results.length}`;
    if (seen.has(id)) continue; // serwer podał tę samą paczkę dwa razy
    seen.add(id);
    const existing = byId.get(id);
    if (errors.length) {
      const state = errors.some(e => INCOMPATIBLE.has(e.code)) ? "incompatible" : "incomplete";
      results.push({ package_id: id, state, details: errors.map(e => e.message) });
      continue;
    }
    if (!existing) {
      byId.set(id, { ...incoming, _state: "newer" });
      results.push({ package_id: id, state: "newer", details: ["Nowa paczka"] });
    } else if (existing.content_revision === incoming.content_revision) {
      byId.set(id, { ...incoming, _state: existing._state === "newer" ? "newer" : "current", _opened: existing._opened });
      results.push({ package_id: id, state: "current", details: [] });
    } else if (time(incoming.exported_at) > time(existing.exported_at)) {
      byId.set(id, { ...incoming, _state: "newer" });
      results.push({ package_id: id, state: "newer", details: ["Na serwerze jest nowsza wersja — pobrano"] });
    } else {
      results.push({ package_id: id, state: "current", details: ["Serwer ma starszą wersję — zostaje nowsza lokalna"] });
    }
  }
  // Paczki, których serwer już nie wydaje, znikają (Instagram zakończony albo wycofane na desktopie).
  const packages = [...byId.values()].filter(p => seen.has(p.package_id));
  packages.sort((a, b) => time(b.exported_at) - time(a.exported_at));
  return { packages, results, summary: summarize(results) };
}

export function summarize(results) {
  const states = new Set(results.map(r => r.state));
  for (const s of ["incompatible", "incomplete", "newer"]) if (states.has(s)) return s;
  return "current";
}

export function stripServerFields(m) {
  if (!m || typeof m !== "object") return m;
  const { base_url, _state, _opened, ...rest } = m;
  return rest;
}

export function markOpened(packages, id) {
  return packages.map(p => p.package_id === id ? { ...p, _state: "current", _opened: true } : p);
}

export const filesByRole = (m, role) => (m.files || []).filter(f => f.role === role).sort((a, b) => (a.order || 0) - (b.order || 0));
export const mediaFiles = m => [...filesByRole(m, "video"), ...filesByRole(m, "slide")];

export async function sha256Hex(data) {
  const bytes = data instanceof ArrayBuffer ? data : await data.arrayBuffer();
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(hash)].map(x => x.toString(16).padStart(2, "0")).join("");
}

export class IntegrityError extends Error {}

/** Zwraca blob tylko, gdy suma SHA-256 zgadza się z manifestem. */
export async function verifiedBlob(blob, file) {
  const actual = await sha256Hex(blob);
  if (actual !== String(file.sha256).toLowerCase()) {
    throw new IntegrityError(`${file.name}: suma SHA-256 się nie zgadza — plik zablokowany`);
  }
  return blob;
}

export function fileUrl(m, name) {
  const base = m.base_url || `api/file?package=${encodeURIComponent(m.package_id)}&rev=${m.content_revision}`;
  return `${base}&name=${encodeURIComponent(name)}`;
}

export function createEvent(type, m, id = crypto.randomUUID()) {
  return { event_id: id, type, package_id: m.package_id, post_id: m.post_id, brand: m.brand, occurred_at: new Date().toISOString() };
}

export const appendUnique = (events, e) => events.some(x => x.event_id === e.event_id) ? events : [...events, e];
