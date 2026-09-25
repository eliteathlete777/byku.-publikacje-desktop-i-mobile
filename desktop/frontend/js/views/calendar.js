// Kalendarz: dzień / tydzień / miesiąc / lista, przeciąganie, warianty rozkładu, cofanie.
import { $, $$, api, post, esc, state, toast, run, modal, pill, activeCards, matches, guarded, blockReason } from "../core.js";
import { openCard } from "../drawer.js";

let mode = "week";
let anchor = startOfDay(new Date());
let reload = async () => {};
export function initCalendar(fn) { reload = fn; }

function startOfDay(d) { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; }
function iso(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }
function addDays(d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }
function monday(d) { const x = startOfDay(d); const wd = (x.getDay() + 6) % 7; return addDays(x, -wd); }
const DAY = ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"];

function range() {
  if (mode === "day") return [anchor];
  if (mode === "week") { const m = monday(anchor); return [...Array(7)].map((_, i) => addDays(m, i)); }
  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1), start = monday(first);
  return [...Array(42)].map((_, i) => addDays(start, i));
}

function title() {
  if (mode === "day") return anchor.toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  if (mode === "week") { const r = range(); return `${r[0].toLocaleDateString("pl-PL", { day: "numeric", month: "short" })} – ${r[6].toLocaleDateString("pl-PL", { day: "numeric", month: "short", year: "numeric" })}`; }
  if (mode === "month") return anchor.toLocaleDateString("pl-PL", { month: "long", year: "numeric" });
  return "Wszystkie terminy";
}

function card(c, compact = false) {
  return `<article class="cal-card ${esc(c.brand)}" draggable="${!blockReason("write")}" data-id="${esc(c.post_id)}" title="${esc(c.name)}">
    <b>${esc((c.local_target_at || "").slice(11) || "—")}</b><span>${esc(c.name)}</span>${compact ? "" : `<small>${esc(c.brand.toUpperCase())} · ${c.assets.type === "carousel" ? "karuzela" : "rolka"}</small>${pill(c.channels.instagram)}`}</article>`;
}

export function renderCalendar() {
  const cards = activeCards().filter(matches);
  const byDay = {};
  cards.forEach(c => { const k = (c.local_target_at || "").slice(0, 10); (byDay[k] ||= []).push(c); });
  Object.values(byDay).forEach(xs => xs.sort((a, b) => a.local_target_at.localeCompare(b.local_target_at)));
  const unscheduled = byDay[""] || [];
  const today = iso(new Date());
  let body;
  if (mode === "list") {
    const days = Object.keys(byDay).filter(Boolean).sort();
    body = `<div class="cal-list">${days.map(d => `<section class="cal-day" data-day="${d}"><h3>${new Date(d + "T00:00").toLocaleDateString("pl-PL", { weekday: "long", day: "numeric", month: "long" })}</h3>${byDay[d].map(c => card(c)).join("")}</section>`).join("") || `<div class="empty">Brak terminów.</div>`}</div>`;
  } else {
    const days = range();
    body = `<div class="cal-grid ${mode}">${mode !== "day" ? DAY.map(d => `<div class="cal-dow">${d}</div>`).join("") : ""}${days.map(d => {
      const k = iso(d), items = byDay[k] || [], out = mode === "month" && d.getMonth() !== anchor.getMonth();
      return `<section class="cal-day ${k === today ? "today" : ""} ${out ? "out" : ""}" data-day="${k}"><h3>${mode === "month" ? d.getDate() : d.toLocaleDateString("pl-PL", { weekday: "short", day: "numeric", month: "short" })}<span>${items.length || ""}</span></h3>${items.map(c => card(c, mode === "month")).join("")}</section>`;
    }).join("")}</div>`;
  }
  $("#view").innerHTML = `
    <div class="cal-toolbar">
      <div class="segmented">${[["day", "Dzień"], ["week", "Tydzień"], ["month", "Miesiąc"], ["list", "Lista"]].map(([id, n]) => `<button type="button" data-mode="${id}" class="${mode === id ? "active" : ""}">${n}</button>`).join("")}</div>
      ${mode !== "list" ? `<div class="cal-nav"><button class="icon-btn" type="button" data-nav="-1" aria-label="Wstecz">‹</button><button class="btn ghost small" type="button" data-nav="0">Dziś</button><button class="icon-btn" type="button" data-nav="1" aria-label="Dalej">›</button></div>` : ""}
      <h2 class="cal-title">${esc(title())}</h2>
      <div class="actions"><button class="btn ghost" type="button" id="propose" ${guarded("write")}>Rozłóż szkice</button><button class="btn ghost" type="button" id="undo" ${state.health?.can_undo ? guarded("write") : 'disabled title="Brak zmian do cofnięcia"'}>Cofnij ostatnią zmianę</button></div>
    </div>
    ${blockReason("write") ? `<p class="note">${esc(blockReason("write"))} Kalendarz działa w trybie podglądu.</p>` : ""}
    <div class="cal-layout">
      <aside class="cal-day unscheduled" data-day=""><h3>Bez terminu<span>${unscheduled.length}</span></h3>${unscheduled.map(c => card(c)).join("") || `<p class="muted">Wszystko ma termin.</p>`}<p class="note">Przeciągnij tutaj, aby zdjąć termin.</p></aside>
      ${body}
    </div>`;
  bind();
}

function bind() {
  $$("[data-mode]").forEach(b => b.onclick = () => { mode = b.dataset.mode; renderCalendar(); });
  $$("[data-nav]").forEach(b => b.onclick = () => {
    const n = +b.dataset.nav;
    if (n === 0) anchor = startOfDay(new Date());
    else if (mode === "day") anchor = addDays(anchor, n);
    else if (mode === "week") anchor = addDays(anchor, 7 * n);
    else anchor = new Date(anchor.getFullYear(), anchor.getMonth() + n, 1);
    renderCalendar();
  });
  $$(".cal-card").forEach(x => {
    x.onclick = () => openCard(x.dataset.id);
    x.ondragstart = e => { e.dataTransfer.setData("text/plain", x.dataset.id); x.classList.add("dragging"); };
    x.ondragend = () => x.classList.remove("dragging");
  });
  $$(".cal-day").forEach(zone => {
    zone.ondragover = e => { e.preventDefault(); zone.classList.add("drop"); };
    zone.ondragleave = () => zone.classList.remove("drop");
    zone.ondrop = e => { e.preventDefault(); zone.classList.remove("drop"); const id = e.dataTransfer.getData("text/plain"); if (id) move(id, zone.dataset.day); };
  });
  $("#undo").onclick = e => run(e.currentTarget, async () => { await post("/api/schedule/undo"); await reload(); }, "Cofnięto ostatnią zmianę kalendarza.");
  $("#propose").onclick = propose;
}

function move(id, day) {
  const c = state.cards.find(x => x.post_id === id);
  if (!c) return;
  if (!day) return save([{ post_id: id, before: c.local_target_at, after: "" }], "Zdjęto termin.");
  const slots = state.brands[c.brand]?.posting_slots || ["18:45"];
  const current = (c.local_target_at || "").slice(11);
  modal(`<h2>Godzina publikacji</h2><p class="muted">${esc(c.name)} → ${esc(day)}</p>
    <div class="slot-list">${slots.map(s => `<button class="btn ghost" type="button" data-slot="${esc(s)}">${esc(s)}</button>`).join("")}</div>
    <label class="field"><span>Własna godzina</span><input type="time" id="customTime" value="${esc(current || slots[0])}"></label>
    <div class="actions end"><button class="btn primary" type="button" id="saveTime">Ustaw termin</button></div>`, dlg => {
    const done = t => { dlg.close(); save([{ post_id: id, before: c.local_target_at, after: `${day} ${t}` }], `Termin: ${day} ${t}`); };
    $$("[data-slot]", dlg).forEach(b => b.onclick = () => done(b.dataset.slot));
    $("#saveTime", dlg).onclick = () => { const t = $("#customTime", dlg).value; if (t) done(t); };
  });
}

async function save(changes, msg) {
  try { await post("/api/schedule/apply", { changes }); await reload(); toast(msg, "ok"); }
  catch (e) { toast(e.message, "error"); }
}

async function propose(e) {
  const brand = state.brand === "all" ? "atlet" : state.brand;
  const r = await run(e.currentTarget, () => api(`/api/schedule/proposals?brand=${brand}`));
  if (!r) return;
  if (!r.variants[0]?.changes.length) return toast("Wszystkie szkice tej marki mają już termin.");
  modal(`<h2>Rozłóż szkice — ${esc(brand.toUpperCase())}</h2><p class="muted">Wybierz rytm. Nic nie zapisze się bez Twojego kliknięcia. Każdą zmianę możesz cofnąć.</p>
    <div class="variants">${r.variants.map(v => `<article class="variant"><header><b>${esc(v.label)}</b><small>${esc(v.slots.join(" · "))}${v.weekends ? " · z weekendami" : ""}</small></header>
      <ol>${v.changes.slice(0, 8).map(ch => `<li><span>${esc(ch.after)}</span>${esc(ch.name)}</li>`).join("")}${v.changes.length > 8 ? `<li class="muted">…i ${v.changes.length - 8} kolejnych</li>` : ""}</ol>
      <small class="muted">Do: ${esc(v.until)}</small><button class="btn primary" type="button" data-variant="${esc(v.id)}">Zastosuj ${v.changes.length}</button></article>`).join("")}</div>`, dlg => {
    $$("[data-variant]", dlg).forEach(b => b.onclick = async () => { const v = r.variants.find(x => x.id === b.dataset.variant); dlg.close(); await save(v.changes, `Ustawiono ${v.changes.length} terminów (${v.label}).`); });
  });
}
