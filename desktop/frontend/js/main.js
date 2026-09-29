import { $, $$, api, post, esc, state, savePref, toast, confirmDialog } from "./core.js";
import { initDrawer, renderDrawer } from "./drawer.js";
import { renderTable } from "./views/table.js";
import { renderLibrary, renderBoard } from "./views/library.js";
import { renderCalendar, initCalendar } from "./views/calendar.js";
import { renderTransfer } from "./views/transfer.js";
import { renderBrands } from "./views/brands.js";
import { renderLearning } from "./views/learning.js";
import { renderSystem } from "./views/system.js";
import { renderAdd } from "./views/add.js";
import { initTour, startTour } from "./tour.js";

const VIEWS = {
  add: ["Dodaj", "Nowe rolki: foldery z filmem → opis → okładka → wrzut", "＋", renderAdd],
  today: ["Stół publikacji", "Praca na dziś", "◉", () => renderTable("today")],
  finish: ["Do dokończenia", "Braki, opisy, akceptacja", "✎", () => renderTable("finish")],
  transfer: ["TikTok → Instagram", "Paczki na telefon", "⇄", renderTransfer],
  calendar: ["Kalendarz", "Plan dnia, tygodnia i miesiąca", "▣", renderCalendar],
  board: ["Kanały", "Status każdej platformy osobno", "▥", renderBoard],
  library: ["Biblioteka", "Rolki i karuzele", "▦", renderLibrary],
  brands: ["Marki i styl", "Styl pisania, słowa kluczowe, podgląd na żywo", "Aa", renderBrands],
  learning: ["Uczenie", "Lekcje stylu i procesu", "◇", renderLearning],
  archive: ["Archiwum", "Zakończone i odłożone", "□", () => renderTable("archive")],
  system: ["System", "Bezpieczeństwo i integracje", "⚙", renderSystem]
};

function counts() {
  const a = state.cards.filter(c => !c.archived && (state.brand === "all" || c.brand === state.brand));
  return {
    today: a.filter(c => c.next_action.code !== "done").length,
    finish: a.filter(c => ["finish", "review_content"].includes(c.next_action.code)).length,
    transfer: a.filter(c => c.phone_ready).length
  };
}

function renderNav() {
  const n = counts();
  $("#nav").innerHTML = Object.entries(VIEWS).map(([id, [name, , ico]]) => `<button type="button" data-view="${id}" class="${state.view === id ? "active" : ""}"><i>${ico}</i><span>${name}</span>${n[id] ? `<b>${n[id]}</b>` : ""}</button>`).join("");
  $$("#nav button").forEach(b => b.onclick = () => go(b.dataset.view));
  $$("#brandSwitch button").forEach(b => b.classList.toggle("active", b.dataset.brand === state.brand));
}

function go(view) {
  if (!VIEWS[view]) view = "today";
  state.view = view; savePref("view", view);
  render();
}

export function render() {
  if (!VIEWS[state.view]) state.view = "today";
  const [title, kicker] = VIEWS[state.view];
  $("#title").textContent = title; $("#kicker").textContent = kicker;
  renderNav();
  Promise.resolve(VIEWS[state.view][3]()).catch(e => { $("#view").innerHTML = `<div class="alert">${esc(e.message)}</div>`; });
  renderDrawer();
}

function renderHealth() {
  const h = state.health;
  const safe = !h.writes && !h.publication;
  $("#healthDot").className = `dot ${!h.ok ? "bad" : safe ? "safe" : "live"}`;
  $("#modeLabel").textContent = !h.ok ? "Brak rdzenia" : h.mode === "sandbox" ? "Kolejka testowa" : safe ? "Bezpieczny podgląd" : "Tryb produkcyjny";
  $("#modeDetail").textContent = `${h.writes ? "zapis włączony" : "zapis zablokowany"} · ${h.publication ? "publikacja włączona" : "publikacja zablokowana"}`;
  const banner = $("#banner");
  if (!h.ok) { banner.hidden = false; banner.className = "banner bad"; banner.textContent = h.core_error || "Rdzeń magazynu niedostępny."; }
  else if (h.mode === "sandbox") { banner.hidden = false; banner.className = "banner info"; banner.textContent = `Kolejka testowa: ${h.queue}. Zmiany nie dotykają produkcji.`; }
  else banner.hidden = true;
}

export async function load() {
  try {
    state.health = await api("/api/health");
    renderHealth();
    if (!state.health.ok) { state.cards = []; render(); return; }
    const [brands, pubs] = await Promise.all([api("/api/brands"), api(`/api/publications?brand=all&archive=true`)]);
    state.brands = brands.brands; state.cards = pubs.items; state.errors = pubs.errors;
    render();
  } catch (e) {
    $("#view").innerHTML = `<div class="alert">Nie mogę odczytać danych: ${esc(e.message)}</div>`;
    toast(e.message, "error");
  }
}

initDrawer(load);
initCalendar(load);
initTour(go);
$("#tourStart").onclick = startTour;
document.addEventListener("byku:select", () => { if (["today", "finish", "archive", "library"].includes(state.view)) VIEWS[state.view][3](); });
document.addEventListener("byku:changed", () => { renderNav(); if (!["transfer", "learning", "brands", "system", "add"].includes(state.view)) VIEWS[state.view][3](); api("/api/health").then(h => { state.health = h; renderHealth(); }).catch(() => {}); });
document.addEventListener("byku:goto", e => go(e.detail));
document.addEventListener("byku:reload", () => load());
document.addEventListener("byku:watched", () => { if (state.view === "add") renderAdd(); });
document.addEventListener("byku:brand", () => { savePref("brand", state.brand); render(); });
$$("#brandSwitch button").forEach(b => b.onclick = () => { state.brand = b.dataset.brand; savePref("brand", state.brand); render(); });
let searchTimer;
$("#search").oninput = e => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { state.query = e.target.value; if (!["brands", "learning", "system", "transfer"].includes(state.view)) VIEWS[state.view][3](); }, 120); };
$("#refreshCal").onclick = async e => {
  const btn = e.currentTarget, label = btn.innerHTML;
  const who = state.brand === "all" ? "Atlet + Rigger" : state.brand.toUpperCase();
  if (!(await confirmDialog(`Odświeżyć kalendarze ${who}?`, "Python otworzy TikTok Studio i Terminarz Meta w oknach marki i odhaczy to, co już jest wstawione albo zaplanowane. Okno Meta przejdzie na Terminarz — jeśli jakiś formularz czeka na Twoje Zaplanuj, najpierw go dokończ.", "Odśwież"))) return;
  btn.disabled = true; btn.innerHTML = "📅 ↻ Sprawdzam kalendarze…";
  try {
    await post("/api/calendar/refresh", { brand: state.brand });
    toast(`Otwieram kalendarze ${who} w oknach marki. To potrwa ok. minuty na markę.`);
    let s;
    do { await new Promise(r => setTimeout(r, 3000)); s = await api("/api/calendar/refresh"); } while (s.state === "running");
    await load();
    if (s.state === "failed") throw new Error(`Kalendarze: ${s.problem}`);
    const parts = Object.entries(s.result).map(([b, r]) => `${b.toUpperCase()}: ${r.potwierdzone} wstawione lub zaplanowane${r.bledy.length ? ` (${r.bledy.join("; ")})` : ""}`);
    toast(`Kalendarze sprawdzone. ${parts.join(" · ")}`, "ok");
  } catch (err) { toast(err.message, "error"); }
  finally { btn.disabled = false; btn.innerHTML = label; }
};
$("#refresh").onclick = async e => { const btn = e.currentTarget; btn.classList.add("spin"); await load(); btn.classList.remove("spin"); toast("Odświeżono z kolejki.", "ok"); };
$("#systemCard").onclick = () => go("system");
document.addEventListener("keydown", e => { if (e.key === "Escape" && state.selected && !$("#modal").open) { state.selected = null; render(); } });
load();
