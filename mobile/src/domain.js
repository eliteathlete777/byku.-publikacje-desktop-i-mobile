export const SUPPORTED_SCHEMA_VERSION = 1;
export const BRANDS = new Set(["atlet", "rigger"]);

export function packageKey(manifest) {
  return `${manifest.post_id}::${manifest.brand}`;
}

export function validateManifest(manifest, expectedBrand) {
  const errors = [];
  if (!manifest || typeof manifest !== "object") return { ok: false, errors: ["Brak manifestu"] };
  if (manifest.schema_version !== SUPPORTED_SCHEMA_VERSION) errors.push(`Nieobsługiwany schema_version: ${manifest.schema_version}`);
  if (!String(manifest.post_id || "").trim()) errors.push("Brak post_id");
  if (!BRANDS.has(manifest.brand)) errors.push(`Nieznana marka: ${manifest.brand || "brak"}`);
  if (expectedBrand && manifest.brand !== expectedBrand) errors.push(`Niezgodna marka: ${manifest.brand || "brak"}`);
  if (!String(manifest.content_revision || "").trim()) errors.push("Brak content_revision");
  if (manifest.channel !== "instagram") errors.push(`Niewłaściwy kanał: ${manifest.channel || "brak"}`);
  if (!Array.isArray(manifest.files) || !manifest.files.length) errors.push("Brak listy plików");
  else {
    const names = new Set();
    for (const file of manifest.files) {
      if (!file?.name || !/^[a-f0-9]{64}$/i.test(file.sha256 || "")) errors.push(`Nieprawidłowy wpis pliku: ${file?.name || "bez nazwy"}`);
      if (names.has(file?.name)) errors.push(`Powtórzony plik: ${file.name}`);
      names.add(file?.name);
    }
    if (!names.has("opis-do-skopiowania.txt")) errors.push("Brak opisu");
    if (!names.has("hashtagi.txt")) errors.push("Brak hashtagów");
    if (![...names].some(isSourceMedia)) errors.push("Brak źródłowego filmu lub slajdów");
  }
  return { ok: errors.length === 0, errors };
}

export function isSourceMedia(name) {
  return /\.(mp4|mov|webm|m4v|jpg|jpeg|png|webp)$/i.test(name) && name !== "miniaturka.png";
}

export function comparePackage(local, remote, expectedBrand) {
  const validation = validateManifest(remote, expectedBrand);
  if (!validation.ok) {
    const incompatible = validation.errors.some(x => /schema_version|marka|kanał/i.test(x));
    return { state: incompatible ? "incompatible" : "incomplete", details: validation.errors };
  }
  if (!local) return { state: "newer", details: ["Nowa paczka na Dysku Google"] };
  if (local.content_revision === remote.content_revision) return { state: "current", details: [] };
  const localTime = Date.parse(local.exported_at || 0);
  const remoteTime = Date.parse(remote.exported_at || 0);
  if (Number.isFinite(localTime) && Number.isFinite(remoteTime) && remoteTime <= localTime) {
    return { state: "current", details: ["Na Dysku jest starsza rewizja; lokalna pozostaje bez zmian"] };
  }
  return { state: "newer", details: ["Na Dysku Google jest nowsza rewizja"] };
}

export function mergeManifests(existing = [], incoming = [], expectedBrand) {
  const map = new Map(existing.map(x => [packageKey(x), x]));
  const results = [];
  for (const remote of incoming) {
    let key;
    try { key = packageKey(remote); } catch { key = `invalid-${results.length}`; }
    const local = map.get(key);
    const comparison = comparePackage(local, remote, expectedBrand);
    if ((comparison.state === "newer" || comparison.state === "current") && validateManifest(remote, expectedBrand).ok) {
      if (!local || comparison.state === "newer") map.set(key, remote);
    }
    results.push({ key, manifest: map.get(key) || remote, remote, ...comparison });
  }
  return { manifests: [...map.values()], results };
}

export function createEvent(type, manifest, extra = {}, id = crypto.randomUUID()) {
  return { event_id: id, type, post_id: manifest.post_id, brand: manifest.brand, channel: "instagram", occurred_at: new Date().toISOString(), ...extra };
}

export function appendUniqueEvent(events, event) {
  return events.some(x => x.event_id === event.event_id) ? events : [...events, event];
}

export async function sha256Hex(blob) {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(hash)].map(x => x.toString(16).padStart(2, "0")).join("");
}

export function resolveFileUrl(manifestUrl, name) {
  return new URL(name.split("/").map(encodeURIComponent).join("/"), manifestUrl).href;
}
