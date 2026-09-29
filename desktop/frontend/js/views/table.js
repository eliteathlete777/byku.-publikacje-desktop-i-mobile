// Stół publikacji, Do dokończenia, Archiwum — tabela kart z filtrami i metrykami.
import { $, $$, esc, state, pill, thumb, fmtTerm, activeCards, brandCards, matches, CHANNELS, api, post, pub, run, toast, confirmDialog, guarded, blockReason } from "../core.js";
import { openCard, primary } from "../drawer.js";

// ---------- Wrzut na platformy: nasz Python (tiktok_uploader / meta_uploader) odpalany ze Stołu ----------
const legDone = ch => !ch || ch.enabled === false || ["scheduled", "published"].includes(ch.platform_evidence) || ch.manual_checked;
const LEGS = [["tiktok", "TikTok", c => !legDone(c.channels.tiktok)],
              ["obie", "IG + FB", c => !legDone(c.channels.instagram) || !legDone(c.channels.facebook)]];
const LEG_NAME = { tiktok: "TikTok", obie: "IG + FB", instagram: "Instagram", facebook: "Facebook" };
let uploadTimer = null;

function uploadCandidates(cards) {
  return cards.filter(c => c.content.approved && c.local_target_at && LEGS.some(([, , need]) => need(c)))
    .sort((a, b) => a.local_target_at.localeCompare(b.local_target_at));
}

function uploadPanel(cards) {
  const list = uploadCandidates(cards);
  const reason = blockReason("publish");
  return `<section class="upload-panel" id="uploadPanel">
    <header><div><p class="kicker">Wrzut na platformy</p><h2>Python wgrywa, Ty klikasz Zaplanuj</h2></div>
      <small class="muted">${reason ? esc(reason) : "Okno przeglądarki marki: wideo, okładka, opis, lokalizacja i termin z paczki. Końcowe Zaplanuj/Udostępnij klikasz sam."}</small></header>
    <div class="upload-list">${list.map(c => `<div class="upload-item">${thumb(c)}
        <span><b>${esc(c.name)}</b><small>${esc(c.brand.toUpperCase())} · ${esc(fmtTerm(c.local_target_at))} · 📍 ${esc(c.content.location || "brak lokalizacji")}</small></span>
        <span class="upload-btns">${LEGS.map(([k, n, need]) => need(c)
          ? `<button type="button" class="btn primary small" data-up="${k}" data-id="${esc(c.post_id)}" ${guarded("publish")}>Wrzuć ${n}</button>`
          : `<span class="pill published">${n} ✓</span>`).join("")}</span>
      </div>`).join("") || `<p class="muted">Brak zaakceptowanych paczek z terminem do wrzucenia. Zaakceptuj treść w karcie (zakładka Treść).</p>`}</div>
    <div id="uploadRuns"></div>
  </section>`;
}

function drawRuns(uploads) {
  const box = $("#uploadRuns");
  if (!box) return false;
  const name = id => state.cards.find(c => c.post_id === id)?.name || id;
  box.innerHTML = uploads.length ? `<h3>Uruchomione w tej sesji</h3>${uploads.map(u => `<article class="upload-run ${u.running ? "live" : u.exit_code === 0 ? "ok" : "bad"}">
      <header><b>${esc(name(u.post_id))} · ${esc(LEG_NAME[u.channel] || u.channel)}</b>
        <span class="pill ${u.running ? "running" : u.exit_code === 0 ? "published" : "failed"}">${u.running ? "Pracuje…" : u.exit_code === 0 ? "Skończył — sprawdź i kliknij Zaplanuj" : `Błąd (kod ${u.exit_code})`}</span>
        ${u.running ? `<button type="button" class="btn ghost small" data-music="${esc(u.post_id)}">Muzyka dobrana</button>` : ""}
        <button type="button" class="btn ghost small" data-open-run="${esc(u.post_id)}">Karta</button></header>
      <pre class="report">${esc(u.tail.join("\n") || "Czekam na pierwsze linie logu…")}</pre>
    </article>`).join("")}` : "";
  $$("[data-music]", box).forEach(b => b.onclick = e => run(e.currentTarget, () => post(`${pub(b.dataset.music)}/music-ready`), "Sygnał muzyki wysłany, Python jedzie dalej."));
  $$("[data-open-run]", box).forEach(b => b.onclick = () => openCard(b.dataset.openRun, "channels"));
  return true;
}

async function pollUploads() {
  clearTimeout(uploadTimer);
  if (!$("#uploadRuns")) return;
  try {
    const { uploads } = await api("/api/uploads");
    if (!drawRuns(uploads)) return;
    uploadTimer = setTimeout(pollUploads, uploads.some(u => u.running) ? 2500 : 15000);
  } catch { uploadTimer = setTimeout(pollUploads, 15000); }
}

function bindUploads(v) {
  $$("[data-up]", v).forEach(b => b.onclick = async e => {
    const c = state.cards.find(x => x.post_id === b.dataset.id), leg = b.dataset.up, btn = e.currentTarget;
    const ok = await confirmDialog(`Wrzucić ${c.name} na ${LEG_NAME[leg]}?`,
      `Python otworzy okno przeglądarki ${c.brand.toUpperCase()} i wypełni formularz: wideo, okładka, opis, lokalizacja „${c.content.location || "brak"}”, termin ${fmtTerm(c.local_target_at)}. `
      + "Nie zamykaj tego okna. Zaplanuj/Udostępnij klikasz Ty, gdy wszystko się zgadza.", "Uruchom");
    if (!ok) return;
    await run(btn, () => post(`${pub(c.post_id)}/prepare-publication`, { channel: leg }), r => `Uploader wystartował (PID ${r.pid}). Postęp poniżej.`);
    pollUploads();
  });
  pollUploads();
}

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
    ${mode === "today" ? uploadPanel(cards) : ""}
    ${focus.length ? `<section class="focus"><header><p class="kicker">Priorytet</p><h2>TikTok gotowy — Instagram czeka</h2></header><div class="focus-list">${focus.map(c => `<button type="button" class="focus-item" data-open="${esc(c.post_id)}" data-tab="phone">${thumb(c)}<span><b>${esc(c.name)}</b><small>TikTok: ${esc({ published: "opublikowany", scheduled: "zaplanowany", manual_checked: "oznaczony ręcznie" }[c.tiktok_transfer] || "—")} · ${esc(fmtTerm(c.local_target_at))}</small></span><em>Na telefon →</em></button>`).join("")}</div></section>` : ""}
    ${mode === "today" ? `<nav class="filters">${Object.entries(FILTERS).map(([id, [n]]) => `<button type="button" class="chip-btn ${state.filter === id ? "active" : ""}" data-filter="${id}">${n}</button>`).join("")}</nav>` : `<p class="lead">Paczki z brakami plików, bez opisu albo z niezaakceptowaną treścią. Kliknij, uzupełnij w zakładce Treść.</p>`}
    ${state.errors.length ? `<div class="alert">Nie odczytano ${state.errors.length} paczek: ${state.errors.slice(0, 3).map(e => esc(e.post_id)).join(", ")}…</div>` : ""}
    <div class="table"><div class="thead"><span>Materiał i termin</span><span>TikTok</span><span>Instagram</span><span>Facebook</span><span>Następny krok</span></div>
    <div class="tbody">${rows.map(row).join("") || `<div class="empty">Nic tu nie ma. ${mode === "finish" ? "Wszystkie paczki są kompletne." : "Zmień filtr albo markę."}</div>`}</div></div>`;
  $$("[data-filter]", v).forEach(b => b.onclick = () => { state.filter = b.dataset.filter; renderTable(mode); });
  $$("[data-open]", v).forEach(b => b.onclick = () => openCard(b.dataset.open, b.dataset.tab));
  if (mode === "today") bindUploads(v);
  bind(v);
}

function bind(v) {
  $$(".row", v).forEach(r => {
    r.onclick = e => { if (!e.target.closest("[data-primary]")) openCard(r.dataset.id); };
    r.onkeydown = e => { if (e.key === "Enter") openCard(r.dataset.id); };
  });
  $$("[data-primary]", v).forEach(b => b.onclick = () => { const c = state.cards.find(x => x.post_id === b.dataset.primary); openCard(c.post_id); primary(c); });
}
