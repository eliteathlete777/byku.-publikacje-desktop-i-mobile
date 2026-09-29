// Samouczek na żywo: podświetla prawdziwe elementy interfejsu, krok po kroku, na aktualnej kolejce.
import { $, esc, state } from "./core.js";
import { openCard } from "./drawer.js";

let steps = [];
let idx = 0;
let active = false;
let goto = () => {};

export function initTour(gotoView) { goto = gotoView; }

function pickCard(pred) {
  const inBrand = c => state.brand === "all" || c.brand === state.brand;
  return state.cards.find(c => !c.archived && inBrand(c) && pred(c)) || null;
}

function buildSteps() {
  const finishCard = pickCard(c => ["finish", "review_content"].includes(c.next_action.code));
  const phoneCard = pickCard(c => c.phone_ready);

  steps = [
    {
      view: "today",
      selector: "#nav button[data-view=\"today\"]",
      title: "Zaczynamy: Stół publikacji",
      text: "Pierwszy panel po otwarciu appki. Pulpit dnia — wszystko, co wymaga Twojej uwagi, na jednym ekranie. Marka wybrana na górze (ATLET / RIGGER / OBIE) filtruje cały panel."
    },
    {
      view: "today",
      selector: ".metrics .metric:first-child",
      title: "Metryki = filtry",
      text: () => {
        const n = $(".metrics .metric:first-child strong")?.textContent || "?";
        return `Klik w kafelek filtruje listę pod spodem. Teraz „Do działania": ${n} kart.`;
      }
    },
    {
      view: "today",
      selector: ".focus",
      skip: () => !$(".focus"),
      title: "Priorytet — TikTok gotowy, Instagram czeka",
      text: "Karty opublikowane już na TikToku, które czekają tylko na Instagram. Przycisk „Na telefon →” przenosi wprost do panelu TikTok → Instagram (krok dalej w tym samouczku)."
    },
    {
      view: "finish",
      selector: "#nav button[data-view=\"finish\"]",
      title: "Do dokończenia",
      text: "Tu trafiają paczki z brakami plików, bez opisu albo z niezaakceptowaną treścią. Klikasz kartę, uzupełniasz w zakładce Treść."
    },
    {
      view: "finish",
      selector: ".table .row:first-child",
      skip: () => !finishCard,
      title: "Przykładowa karta z Twojej kolejki",
      text: () => `„${finishCard.name}" (${finishCard.brand.toUpperCase()}) — ${finishCard.next_action.label}: ${finishCard.next_action.reason}`
    },
    {
      before: () => finishCard && openCard(finishCard.post_id, "content"),
      selector: "#drawer #description",
      skip: () => !finishCard,
      title: "Zakładka Treść — opis",
      text: "Pole opisu z licznikiem znaków (limit z profilu marki). Edytujesz bezpośrednio tutaj, appka liczy znaki i podpowiada uwagi na bieżąco."
    },
    {
      selector: "#drawer #kwChips, #drawer #chips",
      skip: () => !finishCard,
      title: "Słowa kluczowe",
      text: "Zamiast hashtagów frazy w treści opisu. Zielone już są w tekście, kliknięcie brakującej dopisuje ją do ostatniej linii."
    },
    {
      selector: "#drawer #approve",
      skip: () => !finishCard,
      title: "Zapisz i zaakceptuj",
      text: "To jedno kliknięcie zdejmuje kartę z listy „Do dokończenia” i zapisuje zaakceptowaną wersję do prawdziwej kolejki. Zapis produkcyjny jest teraz włączony — to realna zmiana."
    },
    {
      before: () => finishCard && openCard(finishCard.post_id, "preview"),
      selector: "#drawer label.file-btn",
      skip: () => !finishCard,
      title: "Zmiana miniatury (nowość)",
      text: "Klik otwiera edytor kadru: przeciągasz obraz, suwakiem przybliżasz, wybierasz proporcje 9:16 / 4:5 / 1:1. Dopiero „Zapisz miniaturę” wysyła wynik na serwer."
    },
    {
      before: () => finishCard && openCard(finishCard.post_id, "channels"),
      selector: "#drawer .channel:first-child",
      skip: () => !finishCard,
      title: "Zakładka Kanały",
      text: "Dowód platformy (co appka wykryła) i Twój ręczny haczyk („Potwierdzam wykonanie”) to dwie osobne rzeczy. Appka nigdy nie zamienia jednego na drugie za Ciebie."
    },
    {
      view: "transfer",
      selector: "#nav button[data-view=\"transfer\"]",
      title: "TikTok → Instagram",
      text: () => phoneCard
        ? `Kandydaci gotowi do przeniesienia na telefon — teraz m.in. „${phoneCard.name}". Stąd budujesz paczkę (manifest v2, SHA-256) i wysyłasz na Dysk Google albo na serwer telefonu.`
        : "Kandydaci gotowi do przeniesienia na telefon. Stąd budujesz paczkę i wysyłasz na Dysk Google albo na serwer telefonu."
    },
    {
      view: "calendar",
      selector: "#nav button[data-view=\"calendar\"]",
      title: "Kalendarz",
      text: "Dzień / tydzień / miesiąc / lista. Przeciągnij kartę na inny termin albo użyj „Rozłóż szkice” dla gotowej propozycji harmonogramu. Każdą zmianę można cofnąć."
    },
    {
      view: "brands",
      selector: "#nav button[data-view=\"brands\"]",
      title: "Marki i styl",
      text: "Pełny panel stylu: haki, merytoryka, pytania, CTA, słowa kluczowe, zakazane słowa i zasady pisania. Po prawej 3 szkice na żywo z niezapisanych zmian."
    },
    {
      view: "learning",
      selector: "#nav button[data-view=\"learning\"]",
      title: "Uczenie",
      text: "Dziennik zdarzeń appki: test → aktywacja → cofnięcie. Twoje akceptacje zmieniają przyszłe podpowiedzi stylu."
    },
    {
      view: "system",
      selector: "#nav button[data-view=\"system\"]",
      title: "System",
      text: "Tryb pracy, rdzeń, Dysk Google, serwer telefonu, zadania w tle. Sprawdzaj tu, dlaczego dany przycisk jest zablokowany."
    }
  ];
}

function waitFor(selector, timeout = 2500) {
  // setTimeout, nie requestAnimationFrame: appka musi się doczekać elementu nawet gdy okno/karta
  // straci fokus (np. przełączysz się na telefon obok) — rAF wtedy się zatrzymuje.
  return new Promise(resolve => {
    const start = Date.now();
    (function poll() {
      const el = document.querySelector(selector);
      if (el) return resolve(el);
      if (Date.now() - start > timeout) return resolve(null);
      setTimeout(poll, 60);
    })();
  });
}

function ensureOverlay() {
  if ($("#tourSpot")) return;
  const spot = document.createElement("div");
  spot.id = "tourSpot"; spot.className = "tour-spot"; spot.hidden = true;
  const bar = document.createElement("div");
  bar.id = "tourBar"; bar.className = "tour-bar"; bar.hidden = true;
  bar.innerHTML = `
    <p class="tour-step" id="tourStepLabel"></p>
    <h3 id="tourTitle"></h3>
    <p id="tourText"></p>
    <div class="tour-actions">
      <button class="btn ghost small" id="tourEnd" type="button">Zakończ</button>
      <div class="right">
        <button class="btn ghost small" id="tourPrev" type="button">‹ Wstecz</button>
        <button class="btn primary small" id="tourNext" type="button">Dalej ›</button>
      </div>
    </div>`;
  document.body.append(spot, bar);
  $("#tourEnd").onclick = endTour;
  $("#tourPrev").onclick = () => step(idx - 1);
  $("#tourNext").onclick = () => step(idx + 1);
}

function drawSpot(el) {
  const spot = $("#tourSpot");
  const r = el.getBoundingClientRect();
  const pad = 6;
  spot.hidden = false;
  spot.style.top = `${Math.max(0, r.top - pad)}px`;
  spot.style.left = `${Math.max(0, r.left - pad)}px`;
  spot.style.width = `${r.width + pad * 2}px`;
  spot.style.height = `${r.height + pad * 2}px`;
}

function positionSpot(el) {
  const spot = $("#tourSpot");
  if (!el) { spot.hidden = true; return; }
  if (el.scrollIntoView) el.scrollIntoView({ block: "center", behavior: "auto" });
  drawSpot(el);
  setTimeout(() => drawSpot(el), 80);
}

let busy = false;
async function step(n) {
  if (busy) return;
  busy = true;
  $("#tourNext").disabled = true; $("#tourPrev").disabled = true;
  try { await stepInner(n); } finally { busy = false; $("#tourNext").disabled = false; $("#tourPrev").disabled = idx === 0; }
}

async function stepInner(n) {
  let target = n;
  while (target >= 0 && target < steps.length && steps[target].skip?.()) target += n >= idx ? 1 : -1;
  if (target < 0 || target >= steps.length) return;
  idx = target;
  const s = steps[idx];
  if (s.view && state.view !== s.view) goto(s.view);
  await waitFor("#view .table, #view .metrics, #view .cal-layout, #view .brand-layout, #view .learning-layout, #view .sys-grid, #view .pipeline", 2000);
  if (s.before) s.before();
  const el = await waitFor(s.selector);
  positionSpot(el);
  $("#tourStepLabel").textContent = `Krok ${idx + 1} / ${steps.length}`;
  $("#tourTitle").textContent = s.title;
  $("#tourText").textContent = typeof s.text === "function" ? s.text() : s.text;
  $("#tourPrev").disabled = idx === 0;
  $("#tourNext").textContent = idx === steps.length - 1 ? "Zakończ ✓" : "Dalej ›";
  $("#tourNext").onclick = idx === steps.length - 1 ? endTour : () => step(idx + 1);
}

export function startTour() {
  buildSteps();
  ensureOverlay();
  active = true;
  document.body.classList.add("tour-active");
  $("#tourBar").hidden = false;
  idx = -1;
  step(0);
}

export function endTour() {
  active = false;
  document.body.classList.remove("tour-active");
  const spot = $("#tourSpot"), bar = $("#tourBar");
  if (spot) spot.hidden = true;
  if (bar) bar.hidden = true;
}

document.addEventListener("keydown", e => { if (active && e.key === "Escape") endTour(); });
window.addEventListener("resize", () => { if (active && steps[idx]) { const el = document.querySelector(steps[idx].selector); if (el) positionSpot(el); } });
