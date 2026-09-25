// Walidator kontraktu v2 (contract/KONTRAKT.md). Ten sam wynik co desktop/backend/contract.py
// i mobile/api/lib/contract.php dla contract/fixtures/cases.json.
export const SCHEMA_VERSION = 2;
export const BRANDS = ["atlet", "rigger"];
const EVIDENCE = ["unknown", "scheduled", "published", "failed"];
const ROLES = ["video", "slide", "thumbnail", "caption", "hashtags"];
const TIKTOK = ["published", "scheduled", "manual_checked"];
const HEX64 = /^[a-f0-9]{64}$/;
const ISO_UTC = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/;
const isObj = v => v !== null && typeof v === "object" && !Array.isArray(v);
const isInt = v => Number.isInteger(v);

export function safeName(name) {
  return typeof name === "string" && name !== "" && name !== "manifest.json" && !name.startsWith(".")
    && !/[\\/]/.test(name) && !name.includes("..") && name.length <= 180 && !/[\x00-\x1f]/.test(name);
}

export function validateManifest(m) {
  const errors = [];
  const err = (code, message) => errors.push({ code, message });
  if (!isObj(m)) return [{ code: "FIELD", message: "Brak manifestu" }];
  if (m.schema_version !== SCHEMA_VERSION) err("SCHEMA", `Nieobsługiwana wersja schematu: ${m.schema_version}`);
  if (!BRANDS.includes(m.brand)) err("BRAND", `Nieznana marka: ${m.brand || "brak"}`);
  if (m.channel !== "instagram") err("CHANNEL", `Niewłaściwy kanał: ${m.channel || "brak"}`);
  if (typeof m.post_id !== "string" || !m.post_id.trim() || !safeName(m.post_id)) err("FIELD", "Brak lub zły post_id");
  else if (m.package_id !== `${m.brand}--${m.post_id}`) err("FIELD", "package_id nie zgadza się z marką i post_id");
  if (typeof m.content_revision !== "string" || !HEX64.test(m.content_revision)) err("FIELD", "content_revision musi być sumą SHA-256");
  if (typeof m.exported_at !== "string" || !ISO_UTC.test(m.exported_at) || Number.isNaN(Date.parse(m.exported_at))) err("FIELD", "exported_at musi być datą ISO UTC");
  for (const k of ["caption", "hashtags", "location", "title"]) if (k in m && typeof m[k] !== "string") err("FIELD", `${k} musi być tekstem`);
  if (!["reel", "carousel"].includes(m.type)) err("TYPE", `Nieznany typ paczki: ${m.type || "brak"}`);
  let files = m.files;
  if (!Array.isArray(files) || !files.length) { err("FILES", "Brak listy plików"); files = []; }
  const names = new Set(); const roles = Object.fromEntries(ROLES.map(r => [r, []]));
  for (const f of files) {
    if (!isObj(f)) { err("FILE_NAME", "Nieprawidłowy wpis pliku"); continue; }
    if (!safeName(f.name)) err("FILE_NAME", `Niedozwolona nazwa pliku: ${f.name}`);
    else if (names.has(f.name)) err("FILE_NAME", `Powtórzony plik: ${f.name}`);
    else names.add(f.name);
    if (!ROLES.includes(f.role)) err("FILE_NAME", `Nieznana rola pliku ${f.name}: ${f.role}`); else roles[f.role].push(f);
    if (typeof f.sha256 !== "string" || !HEX64.test(f.sha256)) err("FILE_HASH", `Zła suma SHA-256: ${f.name}`);
    if (!isInt(f.size) || f.size < 0) err("FILE_HASH", `Zły rozmiar pliku: ${f.name}`);
  }
  if (files.length) {
    for (const [role, label] of [["thumbnail", "miniatury"], ["caption", "opisu"], ["hashtags", "hashtagów"]])
      if (roles[role].length !== 1) err("ROLE_MISSING", `Paczka musi mieć dokładnie jeden plik ${label}`);
    if (m.type === "reel" && !roles.video.length) err("ROLE_MISSING", "Rolka nie ma pliku wideo");
    if (m.type === "carousel") {
      if (roles.slide.length < 2) err("ROLE_MISSING", "Karuzela musi mieć co najmniej 2 slajdy");
      const orders = roles.slide.map(s => s.order);
      if (orders.some(o => !isInt(o)) || new Set(orders).size !== orders.length) err("ORDER", "Slajdy muszą mieć unikalną kolejność");
    }
  }
  if (!isObj(m.platforms)) err("PLATFORMS", "Brak stanów platform");
  else for (const ch of ["tiktok", "instagram", "facebook"]) {
    const p = m.platforms[ch];
    if (!isObj(p) || !EVIDENCE.includes(p.evidence) || typeof p.manual_checked !== "boolean") err("PLATFORMS", `Zły stan platformy: ${ch}`);
  }
  const t = m.transfer;
  if (!isObj(t) || t.from !== "tiktok" || t.to !== "instagram" || !TIKTOK.includes(t.tiktok) || t.instagram !== "pending")
    err("TRANSFER", "Paczka musi opisywać transfer: TikTok gotowy, Instagram oczekuje");
  return errors;
}

export const INCOMPATIBLE = new Set(["SCHEMA", "BRAND", "CHANNEL"]);
