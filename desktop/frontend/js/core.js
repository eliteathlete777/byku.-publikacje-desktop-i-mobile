// Wspólne narzędzia: API, stan, formatowanie, powiadomienia, modal.
export const $ = (s, root = document) => root.querySelector(s);
export const $$ = (s, root = document) => [...root.querySelectorAll(s)];
export const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export const CHANNELS = [["tiktok", "TikTok"], ["instagram", "Instagram"], ["facebook", "Facebook"]];

export const state = {
  cards: [], errors: [], health: null, brands: {},
  brand: loadPref("brand", "atlet"), view: loadPref("view", "today"),
  selected: null, tab: "preview", filter: "action", query: ""
};

function loadPref(key, fallback) { try { return localStorage.getItem(`byku.desktop.${key}`) || fallback; } catch { return fallback; } }
export function savePref(key, value) { try { localStorage.setItem(`byku.desktop.${key}`, value); } catch { /* brak pamięci przeglądarki */ } }

export async function api(path, opt = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json", ...(opt.headers || {}) }, ...opt });
  const text = await r.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { error: text }; }
  if (!r.ok) throw Object.assign(new Error(data.error || `Operacja nie powiodła się (HTTP ${r.status})`), { status: r.status, data });
  return data;
}
export const post = (path, body = {}) => api(path, { method: "POST", body: JSON.stringify(body) });
export const pub = id => `/api/publications/${encodeURIComponent(id)}`;

export function toast(text, kind = "info") {
  const t = $("#toast");
  t.textContent = text; t.className = `toast show ${kind}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.remove("show"), kind === "error" ? 6500 : 3500);
}

export async function run(button, fn, ok) {
  // Każdy przycisk: blokada na czas operacji, wynik zawsze widoczny.
  const label = button?.innerHTML;
  if (button) { button.disabled = true; button.classList.add("busy"); }
  try { const r = await fn(); if (ok) toast(typeof ok === "function" ? ok(r) : ok, "ok"); return r; }
  catch (e) { toast(e.message, "error"); return undefined; }
  finally { if (button && button.isConnected) { button.disabled = false; button.classList.remove("busy"); button.innerHTML = label; } }
}

export function modal(html, bind) {
  const dlg = $("#modal");
  $("#modalBody").innerHTML = `<button class="modal-close" type="button" aria-label="Zamknij">×</button>${html}`;
  $(".modal-close", dlg).onclick = () => dlg.close();
  if (bind) bind(dlg);
  if (!dlg.open) dlg.showModal();
  return dlg;
}

export function confirmDialog(title, text, confirmLabel = "Potwierdzam") {
  return new Promise(resolve => {
    const dlg = modal(`<h2>${esc(title)}</h2><p class="muted">${esc(text)}</p><div class="actions end"><button class="btn ghost" data-a="no" type="button">Anuluj</button><button class="btn primary" data-a="yes" type="button">${esc(confirmLabel)}</button></div>`, d => {
      $$("[data-a]", d).forEach(b => b.onclick = () => { d.close(); resolve(b.dataset.a === "yes"); });
    });
    dlg.addEventListener("close", () => resolve(false), { once: true });
  });
}

export function channelLabel(ch) {
  if (!ch) return ["—", "idle"];
  const e = ch.platform_evidence, d = ch.delivery;
  if (ch.enabled === false) return ["Nie dotyczy", "off"];
  if (d === "running") return ["W toku", "running"];
  if (d === "awaiting_user") return ["Czeka na Ciebie", "wait"];
  if (d === "failed" || e === "failed") return ["Błąd", "failed"];
  if (e === "published") return [ch.manual_checked ? "Opublikowany ✓" : "Wykryto publikację", "published"];
  if (e === "scheduled") return [ch.manual_checked ? "Zaplanowany ✓" : "Wykryto w kalendarzu", "scheduled"];
  if (ch.manual_checked) return ["Oznaczony ręcznie", "checked"];
  if (ch.legacy_state === "wyslany") return ["Wysłano — sprawdź", "wait"];
  return ["Czeka", "idle"];
}

export const pill = ch => { const [t, c] = channelLabel(ch); return `<span class="pill ${c}">${esc(t)}</span>`; };

export function thumb(card, cls = "thumb") {
  return card.assets.thumbnail_url
    ? `<img class="${cls}" src="${esc(card.assets.thumbnail_url)}" alt="" loading="lazy">`
    : `<div class="${cls} missing">brak<br>miniatury</div>`;
}

export function fmtTerm(v) {
  if (!v) return "Bez terminu";
  const d = new Date(v.replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleString("pl-PL", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export const brandCards = () => state.cards.filter(c => state.brand === "all" || c.brand === state.brand);
export const activeCards = () => brandCards().filter(c => !c.archived);

export function matches(card) {
  const q = state.query.trim().toLowerCase();
  if (!q) return true;
  return `${card.name} ${card.post_id} ${card.content.description} ${card.content.hashtags}`.toLowerCase().includes(q);
}

// Możliwości środowiska → powód blokady przycisku (zamiast martwego przycisku).
export function blockReason(kind) {
  const h = state.health || {};
  if (kind === "write" && !h.writes) return "Zapis wyłączony: bezpieczny podgląd (allow_production_writes=false).";
  if (kind === "publish" && !h.publication) return "Publikowanie wyłączone (allow_publication=false).";
  if ((kind === "publish" || kind === "legacy") && !h.legacy) return "Wymaga rdzenia BYQ Studio (source_root).";
  if (kind === "drive" && !h.drive?.available) return "Ustaw folder Google Drive w config.json (google_drive.local_sync_dir).";
  if (kind === "server" && !(h.mobile_server?.configured && h.mobile_server?.token)) return "Ustaw adres serwera mobilnego i token w .env.";
  return "";
}

export function guarded(kind, attrs = "") {
  const reason = blockReason(kind);
  return reason ? `disabled title="${esc(reason)}" data-reason="${esc(reason)}" ${attrs}` : attrs;
}
