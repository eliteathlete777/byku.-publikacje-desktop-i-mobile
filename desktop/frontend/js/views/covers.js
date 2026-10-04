// Okładki RIGGER: wszystkie aktywne rolki Riggera (także już zaplanowane/opublikowane) w jednej siatce, bez filtrów Stołu.
import { $, $$, esc, state, fmtTerm, post, pub, run, toast, confirmDialog } from "../core.js";

const ACTIVE = c => c.brand === "rigger" && !c.archived;

function statusLine(c) {
  const ch = c.channels.tiktok;
  if (c.next_action.code === "done") return "Opublikowana";
  if (["scheduled", "published"].includes(ch.platform_evidence) || ch.manual_checked) return "Zaplanowana";
  return c.content.approved ? "Zaakceptowana" : "W przygotowaniu";
}

export function renderCovers() {
  const v = $("#view");
  const all = state.cards.filter(ACTIVE).sort((a, b) => (a.local_target_at || "9999").localeCompare(b.local_target_at || "9999"));
  const todo = all.filter(c => !c.assets.cover_custom);
  const ids = (todo.length ? todo : all).map(c => c.post_id);
  const open = (id, studio) => window.open(`/?edit=${encodeURIComponent(id)}&q=${encodeURIComponent(ids.join(","))}${studio ? "&studio=1" : ""}`, "_blank");
  v.innerHTML = `
    <section class="cover-hero">
      <div><p class="kicker">RIGGER</p><h2>${todo.length ? `${todo.length} z ${all.length} rolek bez nowej okładki z tytułem` : `Wszystkie ${all.length} rolek mają nową okładkę z tytułem ✓`}</h2>
        <p class="muted">Dotyczy też rolek już zaplanowanych i opublikowanych. Kliknij „Zrób okładkę” — otworzy się pełny ekran ze Studiem miniatury.</p></div>
      ${todo.length ? `<button type="button" class="btn primary" id="coversStart">⛶ Zacznij od pierwszej (${esc(todo[0].name)})</button>` : ""}
    </section>
    <div class="cover-grid">${all.map(c => `
      <article class="cover-tile ${c.assets.cover_custom ? "ok" : "bad"}">
        <button type="button" class="cover-tile-img" data-id="${esc(c.post_id)}" data-studio="1" title="Zrób okładkę">${c.assets.thumbnail_url ? `<img src="${esc(c.assets.thumbnail_url)}" alt="" loading="lazy">` : `<span>brak okładki</span>`}</button>
        <div class="cover-tile-body"><b>${esc(c.name)}</b>
          <small>${esc(statusLine(c))} · ${esc(fmtTerm(c.local_target_at))}</small>
          <span class="row-cover ${c.assets.cover_custom ? "ok" : "bad"}">${c.assets.cover_custom ? "✓ okładka z tytułem" : "✕ brak okładki z tytułem"}</span>
          <button type="button" class="btn ${c.assets.cover_custom ? "ghost" : "primary"} small" data-id="${esc(c.post_id)}" data-studio="1">${c.assets.cover_custom ? "Popraw okładkę" : "Zrób okładkę"}</button>
          <button type="button" class="btn ghost small" data-id="${esc(c.post_id)}">⛶ Pełny ekran</button>
          ${c.assets.cover_custom || !c.assets.thumbnail_url ? "" : `<button type="button" class="btn ghost small" data-accept="${esc(c.post_id)}" title="Ta okładka ma już tytuł — uznaj ją za gotową">✓ Obecna okładka jest OK</button>`}
          <button type="button" class="btn ghost small danger" data-arch="${esc(c.post_id)}">🗄 Archiwizuj</button></div>
      </article>`).join("") || `<p class="muted">Brak aktywnych rolek Riggera.</p>`}</div>`;
  $("#coversStart")?.addEventListener("click", () => open(todo[0].post_id, true));
  $$("[data-id]", v).forEach(b => b.onclick = () => open(b.dataset.id, !!b.dataset.studio));
  $$("[data-accept]", v).forEach(b => b.onclick = async e => {
    const c = state.cards.find(x => x.post_id === b.dataset.accept);
    if (!(await confirmDialog(`Uznać obecną okładkę „${c.name}”?`, "Potwierdzasz, że ta okładka ma już tytuł i nie wymaga przerabiania. Rolka przestanie być blokowana.", "Uznaję"))) return;
    await run(e.currentTarget, async () => { Object.assign(c, await post(`${pub(c.post_id)}/cover-accept`)); document.dispatchEvent(new CustomEvent("byku:reload")); }, "Okładka uznana.");
  });
  $$("[data-arch]", v).forEach(b => b.onclick = async e => {
    const c = state.cards.find(x => x.post_id === b.dataset.arch);
    if (!(await confirmDialog(`Zarchiwizować „${c.name}”?`, "Rolka zniknie z list roboczych, zostaje w Archiwum i można ją przywrócić. Nic nie jest usuwane.", "Archiwizuj"))) return;
    await run(e.currentTarget, async () => { Object.assign(c, await post(`${pub(c.post_id)}/archive`, { archived: true })); document.dispatchEvent(new CustomEvent("byku:reload")); }, "Przeniesiono do Archiwum.");
  });
}
