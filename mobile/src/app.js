import { createSession, createApi, AuthError, MEDIA_CACHE } from "./session.js";
import { mergeIndex, markOpened, mediaFiles, filesByRole, verifiedBlob, IntegrityError, fileUrl, createEvent, appendUnique, STATE_LABEL } from "./domain.js";

const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const session = createSession({ storage: localStorage, cacheStorage: "caches" in window ? caches : null });
const api = createApi({ fetcher: (...a) => fetch(...a), session });

let data = { packages: [], results: [], summary: "current", fetched_at: null };
let brand = localStorage.getItem("byku.m.prefs") || "all";
const objectUrls = new Map();
const blocked = new Set();

// ---------------- pomocnicze ----------------
function toast(text, kind = "") {
  const t = $("#toast"); t.textContent = text; t.className = `toast show ${kind}`;
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove("show"), kind === "error" ? 6000 : 3000);
}
function fmt(iso) { const d = new Date(iso); return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("pl-PL", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); }
const TIKTOK = { published: "opublikowany", scheduled: "zaplanowany", manual_checked: "oznaczony ręcznie" };

function showLogin(message = "") {
  closeDetail(); revokeAll();
  data = { packages: [], results: [], summary: "current", fetched_at: null };
  $("#app").hidden = true; $("#list").innerHTML = "";
  $("#loginScreen").hidden = false;
  $("#loginStatus").textContent = message;
  $("#passwordInput").value = "";
}
function showApp() {
  $("#loginScreen").hidden = true; $("#app").hidden = false;
  $("#userLabel").textContent = (session.current()?.user || "").toUpperCase();
}
function handleError(e, where = "") {
  if (e instanceof AuthError) { showLogin(e.message); return; }
  if (e?.offline) { setSync("offline"); return; }
  toast(`${where}${e.message}`, "error");
}

// ---------------- pliki (SHA-256 + pamięć offline) ----------------
async function getVerified(m, file) {
  const url = fileUrl(m, file.name);
  const cache = "caches" in window ? await caches.open(MEDIA_CACHE) : null;
  const cached = cache ? await cache.match(url) : null;
  if (cached) {
    try { return await verifiedBlob(await cached.blob(), file); }
    catch { await cache.delete(url); }
  }
  if (!session.guard()) throw new AuthError("Sesja wygasła. Zaloguj się ponownie");
  const r = await api.request(url);
  if (r.status === 410) throw new Error("Ta wersja nie jest już aktualna — odśwież");
  if (!r.ok) throw new Error(`${file.name}: HTTP ${r.status}`);
  const blob = await r.blob();
  try { await verifiedBlob(blob, file); }
  catch (e) { blocked.add(m.package_id); renderList(); throw e; }
  if (cache) await cache.put(url, new Response(blob, { headers: { "Content-Type": blob.type } }));
  return blob;
}
async function objectUrl(m, file) {
  const key = `${m.package_id}:${m.content_revision}:${file.name}`;
  if (!objectUrls.has(key)) objectUrls.set(key, URL.createObjectURL(await getVerified(m, file)));
  return objectUrls.get(key);
}
function revokeAll() { objectUrls.forEach(u => URL.revokeObjectURL(u)); objectUrls.clear(); }

// ---------------- zdarzenia ----------------
function track(type, m) {
  const events = appendUnique(session.readEvents(), createEvent(type, m));
  session.saveEvents(events);
  flushEvents();
}
async function flushEvents() {
  const pending = session.readEvents().filter(e => !e.sent);
  if (!pending.length || !navigator.onLine) return;
  try {
    await api.sendEvents(pending.map(({ sent, ...e }) => e));
    const ids = new Set(pending.map(e => e.event_id));
    session.saveEvents(session.readEvents().map(e => ids.has(e.event_id) ? { ...e, sent: true } : e));
  } catch (e) { if (e instanceof AuthError) showLogin(e.message); }
}
const done = (m, type) => session.readEvents().some(e => e.package_id === m.package_id && e.type === type);

// ---------------- synchronizacja ----------------
function setSync(state, detail = "") {
  const bar = $("#syncBar"); bar.dataset.state = state;
  const when = data.fetched_at ? `Ostatni poprawny odczyt: ${fmt(data.fetched_at)}` : "Brak zapisanego odczytu";
  const text = {
    current: ["Wszystko aktualne", `${data.packages.length} paczek · ${when}`],
    newer: ["Dostępna nowsza wersja", `Pobrano nowe wersje — sprawdź oznaczone paczki · ${when}`],
    incomplete: ["Paczka niekompletna", detail || "Część paczek ma braki — nie używaj ich, desktop musi je wysłać ponownie"],
    incompatible: ["Paczka niezgodna", detail || "Wersja paczki nie pasuje do aplikacji — zaktualizuj desktop albo telefon"],
    offline: ["Offline", `Pokazuję ostatni poprawny odczyt. ${when}`]
  }[state] || ["", ""];
  $("#syncStatus").innerHTML = `<b>${esc(text[0])}</b><span>${esc(text[1])}</span>`;
}

async function refresh() {
  const btn = $("#refreshButton");
  btn.disabled = true; btn.textContent = "Sprawdzam serwer i sumy…";
  try {
    await api.check();
    const index = await api.index();
    const merged = mergeIndex(data.packages, index.packages || []);
    data = { packages: merged.packages, results: merged.results, summary: merged.summary, fetched_at: new Date().toISOString() };
    session.saveCache(data);
    blocked.clear();
    setSync(merged.summary);
    renderList();
    flushEvents();
  } catch (e) {
    handleError(e, "Odświeżanie: ");
    if (e?.offline) renderList();
  } finally {
    btn.disabled = false; btn.textContent = "↻ Odśwież i sprawdź zgodność";
  }
}

// ---------------- lista ----------------
function renderList() {
  if (!session.guard()) return showLogin("Sesja wygasła. Zaloguj się ponownie.");
  $$("#brandFilter button").forEach(b => b.classList.toggle("active", b.dataset.brand === brand));
  const problems = data.results.filter(r => ["incomplete", "incompatible"].includes(r.state));
  $("#problems").innerHTML = problems.map(p => `<div class="problem ${p.state}"><b>${esc(STATE_LABEL[p.state])}: ${esc(p.package_id)}</b><small>${esc(p.details.slice(0, 3).join(" · "))}</small></div>`).join("");
  const rows = data.packages.filter(m => brand === "all" || m.brand === brand);
  const list = $("#list");
  if (!rows.length) { list.innerHTML = `<div class="empty">${data.fetched_at ? "Brak paczek do przeniesienia na Instagram." : "Naciśnij „Odśwież i sprawdź zgodność”."}</div>`; return; }
  list.innerHTML = rows.map(m => {
    const state = blocked.has(m.package_id) ? "incomplete" : m._state || "current";
    const reported = done(m, "manual_check");
    return `<button class="card" type="button" data-id="${esc(m.package_id)}">
      <span class="thumb" data-thumb="${esc(m.package_id)}"></span>
      <span class="card-body">
        <b>${esc(m.title || m.post_id)}</b>
        <small>${esc(m.brand.toUpperCase())} · ${m.type === "carousel" ? `karuzela ${filesByRole(m, "slide").length} slajdów` : "rolka"}</small>
        <small>TikTok: ${esc(TIKTOK[m.transfer.tiktok] || "—")} · Instagram: ${reported ? "zgłoszono publikację" : "oczekuje"}</small>
        <em class="chip ${reported ? "done" : state}">${reported ? "Zgłoszone ✓" : esc(STATE_LABEL[state])}</em>
      </span><i>›</i></button>`;
  }).join("");
  $$(".card").forEach(c => c.onclick = () => openDetail(c.dataset.id));
  rows.forEach(async m => {
    const thumb = filesByRole(m, "thumbnail")[0];
    const el = document.querySelector(`[data-thumb="${CSS.escape(m.package_id)}"]`);
    if (!thumb || !el) return;
    try { el.style.backgroundImage = `url("${await objectUrl(m, thumb)}")`; }
    catch (e) { el.classList.add("broken"); el.textContent = e instanceof IntegrityError ? "SHA ✗" : "brak"; if (e instanceof AuthError) showLogin(e.message); }
  });
}

// ---------------- szczegóły ----------------
function closeDetail() { const d = $("#detail"); if (d.open) d.close(); }

async function openDetail(id) {
  const m = data.packages.find(p => p.package_id === id);
  if (!m || !session.guard()) return;
  if (m._state === "newer") { data.packages = markOpened(data.packages, id); session.saveCache(data); }
  const media = mediaFiles(m), isBlocked = blocked.has(m.package_id);
  const reported = done(m, "manual_check");
  const step = (key, label, type) => `<li class="${done(m, type) ? "ok" : ""}"><b>${key}</b>${label}</li>`;
  $("#detailBody").innerHTML = `
    <header class="detail-head"><button class="icon-btn" type="button" id="closeDetail" aria-label="Wróć">‹</button><div><p class="kicker">${esc(m.brand.toUpperCase())} · ${m.type === "carousel" ? "KARUZELA" : "ROLKA"}</p><h2>${esc(m.title || m.post_id)}</h2></div></header>
    <div class="preview" id="preview"><div class="spinner">Sprawdzam SHA-256…</div></div>
    <div class="state-box"><span>TikTok <b>${esc(TIKTOK[m.transfer.tiktok])}</b></span><span>Instagram <b>${reported ? "zgłoszono publikację" : "oczekuje"}</b></span><span>Wersja <b>${esc(m.content_revision.slice(0, 10))}</b> · ${esc(fmt(m.exported_at))}</span></div>
    ${isBlocked ? `<div class="problem incomplete"><b>Plik zablokowany</b><small>Suma SHA-256 się nie zgadza. Odśwież; jeśli nie pomoże, wyślij paczkę z desktopu ponownie.</small></div>` : ""}
    <ol class="steps">${step("1", "Zapisz lub udostępnij " + (m.type === "carousel" ? "slajdy" : "film"), "downloaded")}${step("2", "Skopiuj opis", "caption_copied")}${step("3", "Skopiuj hashtagi", "hashtags_copied")}${step("4", "Otwórz Instagram, dodaj muzykę, opublikuj ręcznie", "instagram_opened")}${step("5", "Zgłoś publikację", "manual_check")}</ol>
    <div class="actions">
      <button class="btn primary big" type="button" id="shareMedia" ${isBlocked ? "disabled" : ""}>${navigator.canShare ? "Udostępnij / zapisz " : "Pobierz "}${m.type === "carousel" ? `slajdy (${media.length})` : "film"}</button>
      <button class="btn" type="button" id="copyCaption">Kopiuj opis</button>
      <button class="btn" type="button" id="copyTags">Kopiuj hashtagi</button>
      <button class="btn" type="button" id="copyAll">Kopiuj opis + hashtagi</button>
      <button class="btn" type="button" id="downloadThumb">Pobierz miniaturę</button>
      <button class="btn" type="button" id="openInstagram">Otwórz Instagram</button>
      <button class="btn ${reported ? "" : "accent"}" type="button" id="reportDone" ${reported ? "disabled" : ""}>${reported ? "Publikacja zgłoszona ✓" : "Zgłoś: opublikowane na Instagramie"}</button>
    </div>
    <details class="text-box"><summary>Opis (${m.caption.length} znaków)</summary><p>${esc(m.caption || "—")}</p></details>
    <details class="text-box"><summary>Hashtagi</summary><p class="tags">${esc(m.hashtags || "Brak hashtagów")}</p></details>
    ${m.location ? `<p class="muted">Lokalizacja: <b>${esc(m.location)}</b></p>` : ""}
    <p class="note">Muzyka i końcowe kliknięcie „Udostępnij” w Instagramie są zawsze ręczne. Zgłoszenie z telefonu to informacja dla desktopu — nie zmienia statusu automatycznie.</p>
    <p id="detailStatus" class="status" aria-live="polite"></p>`;
  $("#detail").showModal();
  $("#closeDetail").onclick = closeDetail;
  const status = t => { $("#detailStatus").textContent = t; };
  renderPreview(m).catch(e => { $("#preview").innerHTML = `<div class="spinner bad">${esc(e.message)}</div>`; handleError(e); });

  // Pliki przygotowujemy od razu (z weryfikacją SHA-256), żeby udostępnienie ruszyło
  // bezpośrednio z kliknięcia — iOS wymaga świeżego gestu użytkownika dla navigator.share.
  let prepared = null;
  const prepare = (async () => {
    const files = [];
    for (const f of media) { const blob = await getVerified(m, f); files.push(new File([blob], f.name, { type: blob.type || "application/octet-stream" })); }
    prepared = files;
    return files;
  })();
  prepare.catch(() => {});
  $("#shareMedia").onclick = async () => {
    try {
      const files = prepared || (status("Pobieram i sprawdzam SHA-256…"), await prepare);
      if (navigator.canShare && navigator.canShare({ files })) {
        await navigator.share({ files, title: m.title || m.post_id });
      } else {
        for (const f of files) saveFile(f);
      }
      track("downloaded", m); status(`Gotowe: ${files.length} plik(ów), każda suma SHA-256 zgodna.`); refreshSteps(m);
    } catch (e) {
      if (e.name === "AbortError") return status("Anulowano.");
      if (e.name === "NotAllowedError") return status("Pliki gotowe — naciśnij przycisk jeszcze raz.");
      status(e.message); handleError(e);
    }
  };
  const copyText = async (text, type, label) => {
    try { await navigator.clipboard.writeText(text); track(type, m); status(`${label} w schowku.`); refreshSteps(m); toast(`${label} skopiowane`, "ok"); }
    catch (e) { status(`Nie udało się skopiować: ${e.message}`); }
  };
  $("#copyCaption").onclick = () => copyText(m.caption, "caption_copied", "Opis");
  $("#copyTags").onclick = () => copyText(m.hashtags, "hashtags_copied", "Hashtagi");
  $("#copyAll").onclick = () => copyText([m.caption, m.hashtags].filter(Boolean).join("\n\n"), "caption_copied", "Opis i hashtagi");
  $("#downloadThumb").onclick = async () => {
    try { const f = filesByRole(m, "thumbnail")[0]; saveFile(new File([await getVerified(m, f)], f.name, { type: "image/png" })); status("Miniatura zapisana (SHA-256 zgodna)."); }
    catch (e) { status(e.message); handleError(e); }
  };
  $("#openInstagram").onclick = () => { track("instagram_opened", m); refreshSteps(m); window.location.href = "instagram://camera"; setTimeout(() => { if (document.visibilityState === "visible") window.location.href = "https://www.instagram.com/"; }, 1200); };
  $("#reportDone").onclick = () => {
    if (!confirm("Potwierdzasz, że ten materiał jest już opublikowany na Instagramie?")) return;
    track("manual_check", m); status("Zgłoszono. Desktop pokaże to jako Twoje ręczne zgłoszenie."); renderList(); openDetail(id);
  };
}

function refreshSteps(m) {
  const types = ["downloaded", "caption_copied", "hashtags_copied", "instagram_opened", "manual_check"];
  $$(".steps li").forEach((li, i) => li.classList.toggle("ok", done(m, types[i])));
}

async function renderPreview(m) {
  const box = $("#preview"), media = mediaFiles(m);
  if (m.type === "reel") {
    const url = await objectUrl(m, media[0]);
    const poster = filesByRole(m, "thumbnail")[0];
    box.innerHTML = `<video controls playsinline preload="metadata" src="${url}" ${poster ? `poster="${await objectUrl(m, poster)}"` : ""}></video>`;
  } else {
    const urls = [];
    for (const f of media) urls.push(await objectUrl(m, f));
    box.innerHTML = `<div class="slides">${urls.map((u, i) => `<figure><img src="${u}" alt="Slajd ${i + 1}"><figcaption>${i + 1}/${urls.length}</figcaption></figure>`).join("")}</div>`;
  }
}

function saveFile(file) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(file); a.download = file.name;
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

// ---------------- start ----------------
function setNet() { const b = $("#netBadge"); b.textContent = navigator.onLine ? "ONLINE" : "OFFLINE"; b.classList.toggle("off", !navigator.onLine); }

$("#loginForm").onsubmit = async e => {
  e.preventDefault();
  const btn = $("#loginButton"); btn.disabled = true; $("#loginStatus").textContent = "Loguję…";
  try {
    if (!navigator.onLine) throw new Error("Brak internetu — logowanie wymaga połączenia.");
    await api.login($("#loginInput").value.trim(), $("#passwordInput").value);
    $("#passwordInput").value = "";
    data = session.readCache() || data;
    showApp(); setSync(data.fetched_at ? "current" : "current"); renderList(); await refresh();
  } catch (err) { $("#loginStatus").textContent = err.offline ? "Brak połączenia z serwerem." : err.message; }
  finally { btn.disabled = false; }
};
$("#logoutButton").onclick = async () => {
  if (!confirm("Wylogować? Zapisane na telefonie paczki i pliki zostaną usunięte.")) return;
  await flushEvents(); await api.logout(); showLogin("Wylogowano. Dane usunięte z telefonu.");
};
$("#refreshButton").onclick = refresh;
$$("#brandFilter button").forEach(b => b.onclick = () => { brand = b.dataset.brand; localStorage.setItem("byku.m.prefs", brand); renderList(); });
window.addEventListener("online", () => { setNet(); refresh(); });
window.addEventListener("offline", () => { setNet(); setSync("offline"); });
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible" && !$("#app").hidden && !session.guard()) showLogin("Sesja wygasła. Zaloguj się ponownie."); });
setInterval(() => { if (!$("#app").hidden && !session.guard()) showLogin("Sesja wygasła. Zaloguj się ponownie."); }, 30000);

setNet();
if (session.guard()) {
  data = session.readCache() || data;
  showApp(); setSync(navigator.onLine ? "current" : "offline"); renderList();
  if (navigator.onLine) refresh();
} else {
  showLogin(navigator.onLine ? "" : "Brak internetu. Zaloguj się, gdy będziesz online.");
}
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
