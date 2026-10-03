// Dodaj — nowe rolki z gołego filmu. Folder = jedna rolka (nazwa folderu = nazwa rolki),
// z folderu idzie największy film (mniejszy plik to odpad produkcji). Potem ta sama rolka
// przechodzi przez panel: opis z podstawy → okładka → lokalizacja → akceptacja → termin → wrzut.
import { $, $$, esc, state, api, post, toast, thumb, fmtTerm, guarded, blockReason, isWatched, markWatched, playUrl, modal, legChips, bindLegs } from "../core.js";
import { openCard, openStudio } from "../drawer.js";

const VIDEO = /\.(mp4|mov|m4v|avi|mkv)$/i;
const SOURCE = "BYKU.PUBLIKACJE Dodaj";
let groups = [];          // [{title, file, skipped: [names], note, existing, include, status, progress}]
let busy = false;

const mb = n => `${(n / 1024 / 1024).toFixed(1)} MB`;
const cleanTitle = t => String(t || "").replace(/[<>:"/\\|?*\u0000-\u001f]/g, " ").replace(/\s+/g, " ").trim().replace(/[. ]+$/, "");
const keyOf = name => cleanTitle(String(name).replace(VIDEO, "")).toLocaleLowerCase("pl");

// ---------- zbieranie plików: przeciągnięte foldery, wybrane pliki, wybrany folder ----------
async function entriesToFiles(entries) {
  const out = [];
  const walk = async (entry, path) => {
    if (entry.isFile) {
      const file = await new Promise((res, rej) => entry.file(res, rej));
      out.push({ file, path: path + file.name });
    } else if (entry.isDirectory) {
      const reader = entry.createReader();
      let batch;
      do {
        batch = await new Promise((res, rej) => reader.readEntries(res, rej));
        for (const e of batch) await walk(e, `${path}${entry.name}/`);
      } while (batch.length);
    }
  };
  for (const e of entries) await walk(e, "");
  return out;
}

function groupFiles(items) {
  // Klucz = folder, w którym leży plik. Plik luzem = własna rolka o nazwie pliku.
  const map = new Map();
  for (const { file, path } of items) {
    const parts = path.split("/").filter(Boolean);
    const title = cleanTitle(parts.length > 1 ? parts[parts.length - 2] : file.name.replace(/\.[^.]+$/, ""));
    const key = parts.length > 1 ? parts.slice(0, -1).join("/") : `plik:${file.name}`;
    if (!map.has(key)) map.set(key, { title, files: [] });
    map.get(key).files.push(file);
  }
  const res = [];
  for (const { title, files } of map.values()) {
    const videos = files.filter(f => VIDEO.test(f.name)).sort((a, b) => b.size - a.size);
    if (!videos.length) {
      res.push({ title, file: null, skipped: files.map(f => f.name), note: "brak filmu — pomijam", include: false });
      continue;
    }
    const skipped = files.filter(f => f !== videos[0]).map(f => f.name);
    res.push({ title, file: videos[0], skipped, note: skipped.length ? `pomijam mniejsze: ${skipped.join(", ")}` : "", include: true });
  }
  return res.sort((a, b) => a.title.localeCompare(b.title, "pl"));
}

async function accept(items) {
  if (busy) return toast("Poczekaj, aż skończy się dodawanie.", "error");
  const fresh = groupFiles(items);
  if (!fresh.length) return toast("Nic nie weszło. Przeciągnij foldery z rolkami albo pliki wideo.", "error");
  // Nowe foldery dopisuję do listy; ten sam tytuł zastępuje poprzedni wybór.
  const byTitle = new Map(groups.filter(g => g.status !== "added").map(g => [keyOf(g.title), g]));
  fresh.forEach(g => byTitle.set(keyOf(g.title), g));
  groups = [...byTitle.values()].sort((a, b) => a.title.localeCompare(b.title, "pl"));
  await markExisting();
  draw();
}

function brandPicked() { return $("#addBrand")?.value || ""; }

async function markExisting() {
  const brand = brandPicked();
  groups.forEach(g => { delete g.existing; });
  if (!brand) return;
  try {
    const { existing } = await post("/api/import/check", { brand, titles: groups.map(g => g.title) });
    groups.forEach(g => {
      const id = existing[g.title];
      if (id && g.status !== "added") { g.existing = id; g.include = false; }
    });
  } catch (e) { toast(e.message, "error"); }
}

// ---------- wysyłka: jeden film = jedno żądanie, strumieniem z paskiem postępu ----------
function upload(g, brand, location) {
  return new Promise((resolve, reject) => {
    const q = new URLSearchParams({ brand, title: g.title, name: g.file.name, location });
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/import/reel?${q}`);
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = e => { if (e.lengthComputable) { g.progress = e.loaded / e.total; drawProgress(g); } };
    xhr.onload = () => {
      let data = {};
      try { data = JSON.parse(xhr.responseText || "{}"); } catch { /* odpowiedź nie-JSON */ }
      xhr.status < 300 ? resolve(data) : reject(new Error(data.error || `HTTP ${xhr.status}`));
    };
    xhr.onerror = () => reject(new Error("Połączenie z panelem przerwane."));
    xhr.send(g.file);
  });
}

async function addAll(btn) {
  const brand = brandPicked();
  if (!brand) return toast("Wybierz markę: Atlet albo Rigger.", "error");
  const todo = groups.filter(g => g.include && g.file && g.status !== "added");
  if (!todo.length) return toast("Nie ma nic zaznaczonego do dodania.", "error");
  const location = $("#addLocation").value.trim();
  busy = true; btn.disabled = true;
  let ok = 0;
  for (const g of todo) {
    g.status = "sending"; g.progress = 0; g.error = ""; draw();
    try {
      const r = await upload(g, brand, location);
      g.status = r.status === "exists" ? "exists" : "added"; g.post_id = r.post_id;
      if (r.status === "added") ok++;
      if (r.status === "added" && !r.thumbnail) g.note = "okładki nie dało się wyciąć — zrób ją w edytorze";
    } catch (e) { g.status = "failed"; g.error = e.message; }
    draw();
  }
  busy = false;
  document.dispatchEvent(new CustomEvent("byku:reload"));
  toast(ok ? `Dodano ${ok} ${ok === 1 ? "rolkę" : "rolek"}. Teraz opis z podstawy — kliknij rolkę na liście niżej.` : "Nic nowego nie dodano.", ok ? "ok" : "info");
}

// ---------- rysowanie ----------
const STATUS = { sending: ["Wysyłam…", "running"], added: ["Dodana ✓", "published"], exists: ["Już jest w panelu", "idle"], failed: ["Błąd", "failed"] };

function groupRow(g, i) {
  const st = g.status ? STATUS[g.status] : g.existing ? ["Już jest w panelu", "idle"] : null;
  return `<div class="add-item ${g.file ? "" : "off"}" data-i="${i}">
    <input type="checkbox" data-inc="${i}" ${g.include ? "checked" : ""} ${!g.file || g.status === "added" || busy ? "disabled" : ""} aria-label="Dodaj ${esc(g.title)}">
    <span><input class="add-title" data-title="${i}" value="${esc(g.title)}" ${g.status === "added" || busy ? "disabled" : ""} aria-label="Nazwa rolki">
      <small>${g.file ? `🎬 ${esc(g.file.name)} · ${mb(g.file.size)}` : ""}${g.note ? ` · ${esc(g.note)}` : ""}${g.error ? ` · <span class="bad">${esc(g.error)}</span>` : ""}</small>
      ${g.status === "sending" ? `<div class="add-bar"><i style="width:${Math.round((g.progress || 0) * 100)}%"></i></div>` : ""}</span>
    ${st ? `<span class="pill ${st[1]}">${st[0]}</span>` : `<span></span>`}
    ${g.post_id || g.existing ? `<button type="button" class="btn ghost small" data-card="${esc(g.post_id || g.existing)}">Karta</button>` : `<span></span>`}
  </div>`;
}

function drawProgress(g) {
  const bar = $(`.add-item[data-i="${groups.indexOf(g)}"] .add-bar i`);
  if (bar) bar.style.width = `${Math.round((g.progress || 0) * 100)}%`;
}

// Obejrzenie filmu na świeżo — duży odtwarzacz z dźwiękiem, potem prosto do okładki albo opisu.
function watch(c) {
  const dlg = modal(`<h2>${esc(c.name.replace(/\.[^.]+$/, ""))}</h2>
    <video class="watch-player" id="watchVideo" controls autoplay playsinline preload="auto" src="${esc(playUrl(c))}" poster="${esc(c.assets.thumbnail_url)}"></video>
    <p class="muted small" id="watchHint">Przygotowuję film do odtwarzania (film z telefonu w HEVC koduje się przy pierwszym otwarciu)…</p>
    <div class="actions end"><button type="button" class="btn ghost" id="watchCover">Okładka →</button>
      <button type="button" class="btn primary" id="watchCaption">Opis z podstawy →</button></div>`);
  const v = $("#watchVideo", dlg);
  v.addEventListener("canplay", () => { $("#watchHint", dlg).textContent = "Obejrzyj na świeżo: o co chodzi, co widać, co pada. Potem okładka i opis."; }, { once: true });
  v.addEventListener("play", () => markWatched(c.post_id), { once: true });
  v.addEventListener("error", () => { $("#watchHint", dlg).textContent = "Nie udało się odtworzyć filmu. Otwórz folder paczki z karty i obejrzyj go w odtwarzaczu Windows."; });
  dlg.addEventListener("close", () => { v.pause(); v.removeAttribute("src"); v.load(); }, { once: true });
  $("#watchCover", dlg).onclick = () => { dlg.close(); openCard(c.post_id, "preview"); openStudio(c); };
  $("#watchCaption", dlg).onclick = () => { dlg.close(); openCard(c.post_id, "content"); };
}

// Etapy rolki od dodania do Zaplanuj — ta sama kolejność, w jakiej idzie praca.
const legDone = ch => !ch || ch.enabled === false || ["scheduled", "published"].includes(ch.platform_evidence) || ch.manual_checked;
function stages(c) {
  const imp = (c.history || []).find(h => h.co === "import");
  const at = imp ? new Date(String(imp.kiedy).replace(" ", "T")).getTime() / 1000 : 0;
  const v = Number((c.assets.thumbnail_url.match(/[?&]v=(\d+)/) || [])[1] || 0);
  const coverEdited = v && at && v > at + 5;
  const desc = (c.content.description || "").trim();
  return [
    // Kolejność procesu twórczego Damiana (29.09): film → odtworzenie → okładka → opis z podstawy → lokalizacja → akceptacja → termin → TikTok → IG + FB.
    ["Film wrzucony", "ok", "preview"],
    ["Odtworzenie filmu", isWatched(c.post_id) || coverEdited || desc ? "ok" : "todo", "watch"],
    [coverEdited ? "Okładka" : c.assets.thumbnail_url ? "Okładka (na razie klatka z filmu)" : "Okładka", coverEdited ? "ok" : c.assets.thumbnail_url ? "running" : "todo", "cover"],
    [desc.length >= 250 ? "Opis z podstawy" : desc ? `Opis z podstawy (${desc.length}/250)` : "Opis z podstawy", desc.length >= 250 ? "ok" : desc ? "running" : "todo", "content"],
    [c.content.location ? `Lokalizacja: ${c.content.location}` : "Lokalizacja", c.content.location ? "ok" : "todo", "content"],
    ["Akceptacja treści", c.content.approved ? "ok" : "todo", "content"],
    [c.local_target_at ? `Termin: ${fmtTerm(c.local_target_at)}` : "Termin", c.local_target_at ? "ok" : "todo", "preview"],
    ["TikTok", c.legs?.tiktok?.mine || legDone(c.channels.tiktok) ? "ok" : "todo", "channels"],
    ["IG + FB", c.legs?.meta?.mine || (legDone(c.channels.instagram) && legDone(c.channels.facebook)) ? "ok" : "todo", "channels"]
  ];
}

function pipeline() {
  const cards = state.cards.filter(c => !c.archived && (state.brand === "all" || c.brand === state.brand)
    && (c.history || []).some(h => h.co === "import" && String(h.szczegol || "").startsWith(SOURCE)));
  const open = cards.filter(c => stages(c).some(s => s[1] !== "ok"));
  const ICON = { ok: "✓", running: "…", todo: "" };
  return `<section class="upload-panel">
    <header><div><p class="kicker">Dodane rolki</p><h2>Od filmu do Zaplanuj</h2></div>
      <small class="muted">Kliknij etap, żeby otworzyć kartę w tym miejscu. Kolejność: film → odtworzenie → okładka → opis z podstawy → lokalizacja → akceptacja → termin → TikTok → IG + FB (wrzut ze Stołu publikacji).</small></header>
    ${open.map(c => `<article class="upload-run">
      <header>${thumb(c)}<b>${esc(c.name.replace(/\.[^.]+$/, ""))}</b><small class="muted">${esc(c.brand.toUpperCase())}</small>${legChips(c)}
        <button type="button" class="btn ghost small" data-card="${esc(c.post_id)}">Karta</button></header>
      <ul class="steps">${stages(c).map(([label, st, tab]) => `<li class="${st}"><button type="button" class="step-link" data-card="${esc(c.post_id)}" data-tab="${tab}"><span class="box">${ICON[st]}</span>${esc(label)}</button></li>`).join("")}</ul>
    </article>`).join("") || `<p class="muted">${cards.length ? "Wszystkie dodane rolki przeszły całą drogę." : "Jeszcze nic nie dodano z tej zakładki."}</p>`}
  </section>`;
}

function draw() {
  const v = $("#view");
  if (!v || state.view !== "add") return;
  const prevBrand = brandPicked() || (state.brand !== "all" ? state.brand : "");
  const prevLoc = $("#addLocation")?.value || "";
  const writeBlock = blockReason("write");
  const n = groups.filter(g => g.include && g.file && g.status !== "added").length;
  v.innerHTML = `
    <section class="upload-panel add-panel">
      <header><div><p class="kicker">Dodaj</p><h2>Nowe rolki z folderów</h2></div>
        <small class="muted">Jeden folder = jedna rolka, nazwa folderu = nazwa rolki. Z folderu biorę największy film, mniejsze pliki pomijam. Okładka startowa to klatka z filmu.</small></header>
      <div class="add-form">
        <label>Marka<select id="addBrand"><option value="">— wybierz —</option><option value="atlet">Atlet</option><option value="rigger">Rigger</option></select></label>
        <label>Lokalizacja dla całego wsadu <input id="addLocation" placeholder="puste = uzupełnisz w karcie" value="${esc(prevLoc)}"></label>
      </div>
      <div class="add-drop" id="addDrop" tabindex="0">
        <b>Przeciągnij tu foldery z rolkami</b>
        <span class="muted">albo pojedyncze filmy · kilka naraz · folder nadrzędny też (każdy podfolder = rolka)</span>
        <span class="add-pick"><button type="button" class="btn ghost small" id="pickDir">Wybierz folder…</button><button type="button" class="btn ghost small" id="pickFiles">Wybierz pliki…</button></span>
        <input type="file" id="inDir" webkitdirectory directory multiple hidden>
        <input type="file" id="inFiles" accept="video/*" multiple hidden>
      </div>
      ${groups.length ? `<div class="add-list">${groups.map(groupRow).join("")}</div>
        <div class="actions end"><button type="button" class="btn ghost" id="addClear" ${busy ? "disabled" : ""}>Wyczyść listę</button>
        <button type="button" class="btn primary" id="addGo" ${writeBlock ? guarded("write") : busy || !n ? "disabled" : ""}>Dodaj ${n} ${n === 1 ? "rolkę" : "rolek"}</button></div>` : ""}
    </section>
    ${pipeline()}`;
  $("#addBrand").value = prevBrand;
  $("#addBrand").onchange = async () => { await markExisting(); draw(); };
  const drop = $("#addDrop");
  ["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("drag"); }));
  ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("drag"); }));
  drop.addEventListener("drop", async e => {
    const entries = [...(e.dataTransfer.items || [])].map(i => i.webkitGetAsEntry?.()).filter(Boolean);
    const items = entries.length ? await entriesToFiles(entries) : [...e.dataTransfer.files].map(file => ({ file, path: file.name }));
    accept(items);
  });
  $("#pickDir").onclick = () => $("#inDir").click();
  $("#pickFiles").onclick = () => $("#inFiles").click();
  $("#inDir").onchange = e => accept([...e.target.files].map(file => ({ file, path: file.webkitRelativePath || file.name })));
  $("#inFiles").onchange = e => accept([...e.target.files].map(file => ({ file, path: file.name })));
  $$("[data-inc]", v).forEach(b => b.onchange = () => { groups[+b.dataset.inc].include = b.checked; draw(); });
  $$("[data-title]", v).forEach(b => b.onchange = async () => { groups[+b.dataset.title].title = cleanTitle(b.value); await markExisting(); draw(); });
  $$("[data-card]", v).forEach(b => b.onclick = () => {
    const tab = b.dataset.tab;
    openCard(b.dataset.card, ["cover", "watch"].includes(tab) ? "preview" : tab || "content");
    const card = state.cards.find(x => x.post_id === b.dataset.card);
    if (tab === "cover" && card) openStudio(card);
    if (tab === "watch" && card) watch(card);
  });
  bindLegs(v);
  if ($("#addClear")) $("#addClear").onclick = () => { groups = []; draw(); };
  if ($("#addGo")) $("#addGo").onclick = e => addAll(e.currentTarget);
}

export function renderAdd() { draw(); }
