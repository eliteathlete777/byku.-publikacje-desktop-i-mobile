// Biblioteka: siatka materiałów z filtrem typu. Kanały: tablica statusów per platforma.
import { $, $$, esc, state, pill, thumb, fmtTerm, activeCards, matches, CHANNELS } from "../core.js";
import { openCard } from "../drawer.js";

let kind = "all";

export function renderLibrary() {
  const cards = activeCards().filter(matches).filter(c => kind === "all" || c.assets.type === kind);
  $("#view").innerHTML = `
    <nav class="filters">${[["all", "Wszystko"], ["reel", "Rolki"], ["carousel", "Karuzele"]].map(([id, n]) => `<button type="button" class="chip-btn ${kind === id ? "active" : ""}" data-kind="${id}">${n}</button>`).join("")}<span class="muted">${cards.length} materiałów</span></nav>
    <div class="grid">${cards.map(c => `<button type="button" class="tile ${state.selected === c.post_id ? "selected" : ""}" data-id="${esc(c.post_id)}">
      ${thumb(c, "tile-img")}<span class="tile-type">${c.assets.type === "carousel" ? `▦ ${c.assets.files.length}` : "▶"}</span>
      <span class="tile-body"><b>${esc(c.name)}</b><small>${esc(c.brand.toUpperCase())} · ${esc(fmtTerm(c.local_target_at))}</small>
      <span class="tile-pills">${CHANNELS.map(([k, n]) => `<i title="${n}">${n[0]}</i>${pill(c.channels[k])}`).join("")}</span></span></button>`).join("") || `<div class="empty">Brak materiałów.</div>`}</div>`;
  $$("[data-kind]").forEach(b => b.onclick = () => { kind = b.dataset.kind; renderLibrary(); });
  $$(".tile").forEach(t => t.onclick = () => openCard(t.dataset.id));
}

const LANES = [
  ["Czeka", ch => ch.platform_evidence === "unknown" && !ch.manual_checked && !["running", "awaiting_user", "failed"].includes(ch.delivery)],
  ["W toku", ch => ["running", "awaiting_user"].includes(ch.delivery)],
  ["Zaplanowane", ch => ch.platform_evidence === "scheduled" || (ch.manual_checked && ch.platform_evidence === "unknown")],
  ["Opublikowane", ch => ch.platform_evidence === "published"],
  ["Błąd", ch => ch.delivery === "failed" || ch.platform_evidence === "failed"]
];

export function renderBoard() {
  const cards = activeCards().filter(matches);
  $("#view").innerHTML = `<p class="lead">Każda platforma ma własny status. Dowód platformy i Twój haczyk są rozdzielone.</p>
    <div class="board">${CHANNELS.map(([k, n]) => `<section class="lane-group"><h2>${n}</h2>${LANES.map(([lane, test]) => {
      const items = cards.filter(c => c.channels[k].enabled !== false && test(c.channels[k]));
      return `<div class="lane"><h3>${lane}<span>${items.length}</span></h3>${items.map(c => `<button type="button" class="lane-card" data-id="${esc(c.post_id)}">${thumb(c, "lane-thumb")}<span><b>${esc(c.name)}</b><small>${esc(fmtTerm(c.channels[k].platform_target_at || c.local_target_at))}</small>${pill(c.channels[k])}</span></button>`).join("")}</div>`;
    }).join("")}</section>`).join("")}</div>`;
  $$(".lane-card").forEach(b => b.onclick = () => openCard(b.dataset.id, "channels"));
}
