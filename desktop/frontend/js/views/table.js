// Stół publikacji, Do dokończenia, Archiwum — tabela kart z filtrami i metrykami.
import { $, $$, esc, state, pill, thumb, fmtTerm, activeCards, brandCards, matches, CHANNELS } from "../core.js";
import { openCard, primary } from "../drawer.js";

const FILTERS = {
  action: ["Do działania", c => c.next_action.code !== "done"],
  phone: ["TikTok → IG", c => c.phone_ready],
  wait: ["Czeka na Ciebie", c => Object.values(c.channels).some(x => ["running", "awaiting_user"].includes(x.delivery))],
  review: ["Do potwierdzenia", c => Object.values(c.channels).some(x => x.enabled !== false && x.platform_evidence !== "unknown" && !x.manual_checked)],
  unscheduled: ["Bez terminu", c => !c.local_target_at && c.next_action.code !== "done"],
  done: ["Zakończone", c => c.next_action.code === "done"],
  all: ["Wszystkie", () => true]
};
const FINISH = c => ["finish", "review_content"].includes(c.next_action.code);

function metrics(cards) {
  const n = f => cards.filter(f).length;
  const today = new Date().toISOString().slice(0, 10);
  return [
    ["Do działania", n(FILTERS.action[1]), "action"],
    ["TikTok → IG", n(FILTERS.phone[1]), "phone"],
    ["Czeka na Ciebie", n(FILTERS.wait[1]), "wait"],
    ["Do potwierdzenia", n(FILTERS.review[1]), "review"],
    ["Dziś w planie", n(c => (c.local_target_at || "").startsWith(today)), "all"],
    ["Bez terminu", n(FILTERS.unscheduled[1]), "unscheduled"]
  ];
}

function row(c) {
  const primaryCls = ["phone_package", "publish", "manual_check"].includes(c.next_action.code) ? "primary" : "ghost";
  return `<article class="row ${state.selected === c.post_id ? "selected" : ""}" data-id="${esc(c.post_id)}" tabindex="0">
    <div class="material">${thumb(c)}<div><b>${esc(c.name)}</b><small>${esc(c.brand.toUpperCase())} · ${c.assets.type === "carousel" ? "Karuzela" : "Rolka"}${c.assets.missing.length ? ` · <span class="bad">${esc(c.assets.missing.join(", "))}</span>` : ""}</small><small class="term">${esc(fmtTerm(c.local_target_at))}</small></div></div>
    ${CHANNELS.map(([k]) => `<div class="cell">${pill(c.channels[k])}</div>`).join("")}
    <div class="next"><button type="button" class="btn ${primaryCls} small" data-primary="${esc(c.post_id)}">${esc(c.next_action.label)}</button><small>${esc(c.next_action.reason)}</small></div>
  </article>`;
}

export function renderTable(mode) {
  const v = $("#view");
  if (mode === "archive") {
    const rows = brandCards().filter(c => c.archived && matches(c));
    v.innerHTML = `<div class="table"><div class="thead"><span>Materiał</span><span>TikTok</span><span>Instagram</span><span>Facebook</span><span>Status</span></div><div class="tbody">${rows.map(row).join("") || `<div class="empty">Archiwum jest puste.</div>`}</div></div>`;
    return bind(v);
  }
  const cards = activeCards();
  const base = mode === "finish" ? cards.filter(FINISH) : cards;
  if (!FILTERS[state.filter]) state.filter = "action";
  const rows = (mode === "finish" ? base : base.filter(FILTERS[state.filter][1])).filter(matches);
  const focus = mode === "today" ? cards.filter(FILTERS.phone[1]).slice(0, 3) : [];
  v.innerHTML = `
    ${mode === "today" ? `<section class="metrics">${metrics(cards).map(([n, val, f]) => `<button type="button" class="metric ${state.filter === f ? "active" : ""}" data-filter="${f}"><strong>${val}</strong><span>${n}</span></button>`).join("")}</section>` : ""}
    ${focus.length ? `<section class="focus"><header><p class="kicker">Priorytet</p><h2>TikTok gotowy — Instagram czeka</h2></header><div class="focus-list">${focus.map(c => `<button type="button" class="focus-item" data-open="${esc(c.post_id)}" data-tab="phone">${thumb(c)}<span><b>${esc(c.name)}</b><small>TikTok: ${esc({ published: "opublikowany", scheduled: "zaplanowany", manual_checked: "oznaczony ręcznie" }[c.tiktok_transfer] || "—")} · ${esc(fmtTerm(c.local_target_at))}</small></span><em>Na telefon →</em></button>`).join("")}</div></section>` : ""}
    ${mode === "today" ? `<nav class="filters">${Object.entries(FILTERS).map(([id, [n]]) => `<button type="button" class="chip-btn ${state.filter === id ? "active" : ""}" data-filter="${id}">${n}</button>`).join("")}</nav>` : `<p class="lead">Paczki z brakami plików, bez opisu albo z niezaakceptowaną treścią. Kliknij, uzupełnij w zakładce Treść.</p>`}
    ${state.errors.length ? `<div class="alert">Nie odczytano ${state.errors.length} paczek: ${state.errors.slice(0, 3).map(e => esc(e.post_id)).join(", ")}…</div>` : ""}
    <div class="table"><div class="thead"><span>Materiał i termin</span><span>TikTok</span><span>Instagram</span><span>Facebook</span><span>Następny krok</span></div>
    <div class="tbody">${rows.map(row).join("") || `<div class="empty">Nic tu nie ma. ${mode === "finish" ? "Wszystkie paczki są kompletne." : "Zmień filtr albo markę."}</div>`}</div></div>`;
  $$("[data-filter]", v).forEach(b => b.onclick = () => { state.filter = b.dataset.filter; renderTable(mode); });
  $$("[data-open]", v).forEach(b => b.onclick = () => openCard(b.dataset.open, b.dataset.tab));
  bind(v);
}

function bind(v) {
  $$(".row", v).forEach(r => {
    r.onclick = e => { if (!e.target.closest("[data-primary]")) openCard(r.dataset.id); };
    r.onkeydown = e => { if (e.key === "Enter") openCard(r.dataset.id); };
  });
  $$("[data-primary]", v).forEach(b => b.onclick = () => { const c = state.cards.find(x => x.post_id === b.dataset.primary); openCard(c.post_id); primary(c); });
}
