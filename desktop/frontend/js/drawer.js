// Panel szczegółów publikacji: podgląd, treść, kanały, telefon, historia.
import { $, $$, api, post, pub, esc, state, toast, run, pill, thumb, fmtTerm, guarded, blockReason, confirmDialog, CHANNELS } from "./core.js";

let reload = async () => {};
export function initDrawer(onReload) { reload = onReload; }

const TABS = [["preview", "Podgląd"], ["content", "Treść"], ["channels", "Kanały"], ["phone", "Telefon"], ["history", "Historia"]];

export function closeDrawer() { state.selected = null; renderDrawer(); document.dispatchEvent(new CustomEvent("byku:select")); }

export function openCard(id, tab = "preview") {
  state.selected = id; state.tab = tab; renderDrawer();
  document.dispatchEvent(new CustomEvent("byku:select"));
}

export function renderDrawer() {
  const d = $("#drawer"), c = state.cards.find(x => x.post_id === state.selected);
  document.body.classList.toggle("drawer-open", !!c);
  if (!c) { d.innerHTML = ""; return; }
  d.innerHTML = `
    <div class="drawer-head">
      ${thumb(c, "drawer-thumb")}
      <div class="drawer-title">
        <p class="kicker">${esc(c.brand.toUpperCase())} · ${c.assets.type === "carousel" ? "KARUZELA" : "ROLKA"}</p>
        <h2>${esc(c.name)}</h2>
        <small class="muted mono">${esc(c.post_id)}</small>
      </div>
      <button class="icon-btn" id="closeDrawer" type="button" aria-label="Zamknij szczegóły">×</button>
    </div>
    <div class="next-step ${esc(c.next_action.code)}"><span>Następny krok</span><b>${esc(c.next_action.label)}</b><small>${esc(c.next_action.reason)}</small></div>
    <div class="tabs" role="tablist">${TABS.map(([id, n]) => `<button role="tab" type="button" data-tab="${id}" class="${state.tab === id ? "active" : ""}">${n}</button>`).join("")}</div>
    <div class="drawer-body" id="panel"></div>`;
  $("#closeDrawer").onclick = closeDrawer;
  $$(".tabs button", d).forEach(b => b.onclick = () => { state.tab = b.dataset.tab; renderDrawer(); });
  ({ preview, content, channels, phone, history })[state.tab](c, $("#panel"));
}

async function refreshCard(c, fresh) {
  if (fresh) Object.assign(c, fresh);
  else Object.assign(c, await api(pub(c.post_id)));
  renderDrawer();
  document.dispatchEvent(new CustomEvent("byku:changed"));
}

// ---------- Podgląd ----------
function preview(c, p) {
  const media = c.assets.media_urls || [];
  const player = c.assets.type === "carousel"
    ? `<div class="slides">${media.map((u, i) => `<figure><img src="${esc(u)}" alt="Slajd ${i + 1}"><figcaption>${i + 1}</figcaption></figure>`).join("")}</div>`
    : media[0] ? `<video class="player" controls preload="metadata" src="${esc(media[0])}" poster="${esc(c.assets.thumbnail_url)}"></video>` : `<div class="player missing">Brak pliku wideo</div>`;
  p.innerHTML = `${player}
    <dl class="facts">
      <div><dt>Termin lokalny</dt><dd>${esc(fmtTerm(c.local_target_at))}</dd></div>
      <div><dt>Braki</dt><dd>${esc(c.assets.missing.join(", ") || "Paczka kompletna")}</dd></div>
      <div><dt>Treść</dt><dd>${c.content.approved ? "Zaakceptowana" : "Niezaakceptowana"}</dd></div>
      <div><dt>Lokalizacja</dt><dd>${esc(c.content.location || "—")}</dd></div>
    </dl>
    <p class="caption-preview">${esc(c.content.description || "Brak opisu.")}</p>
    <p class="tags">${esc(c.content.hashtags || "Brak hashtagów.")}</p>
    <div class="actions">
      <button class="btn primary" id="primary" type="button">${esc(c.next_action.label)}</button>
      <button class="btn ghost" id="folder" type="button">Otwórz folder</button>
      <label class="btn ghost file-btn" ${blockReason("write") ? `title="${esc(blockReason("write"))}"` : ""}>Zmień miniaturę<input type="file" accept="image/png" id="thumbInput" ${blockReason("write") ? "disabled" : ""}></label>
    </div>`;
  $("#folder").onclick = e => run(e.currentTarget, () => post(`${pub(c.post_id)}/open-folder`), "Otwarto folder paczki.");
  $("#primary").onclick = () => primary(c);
  $("#thumbInput").onchange = async e => {
    const file = e.target.files[0]; if (!file) return;
    try {
      const r = await fetch(`${pub(c.post_id)}/thumbnail`, { method: "PUT", body: file, headers: { "X-Expected-Revision": c.revision } });
      const data = await r.json(); if (!r.ok) throw new Error(data.error);
      await refreshCard(c, data); toast("Miniatura podmieniona. Nowa wersja treści.", "ok");
    } catch (err) { toast(err.message, "error"); }
  };
}

export function primary(c) {
  const code = c.next_action.code;
  state.tab = ["finish", "review_content"].includes(code) ? "content"
    : code === "show_history" ? "history"
    : code === "phone_package" ? "phone"
    : code === "schedule" ? "preview" : "channels";
  if (code === "schedule") { document.dispatchEvent(new CustomEvent("byku:goto", { detail: "calendar" })); return; }
  renderDrawer();
}

// ---------- Treść ----------
function content(c, p) {
  const profile = state.brands[c.brand] || {};
  const locations = [...new Set([...(profile.locations || []), ...state.cards.map(x => x.content.location).filter(Boolean)])];
  p.innerHTML = `
    <label class="field"><span>Opis <small id="counter" class="muted"></small></span><textarea id="description" rows="8">${esc(c.content.description)}</textarea></label>
    <div class="field"><span>Hashtagi</span>
      <div class="chips" id="chips"></div>
      <div class="inline"><input id="tagInput" placeholder="Dodaj hashtag i Enter"><button class="btn ghost" id="suggestTags" type="button">Podpowiedz z marki</button><button class="btn ghost danger" id="clearTags" type="button">Usuń wszystkie</button></div>
    </div>
    <label class="field"><span>Lokalizacja</span><input id="location" list="locations" value="${esc(c.content.location)}"><datalist id="locations">${locations.map(l => `<option value="${esc(l)}">`).join("")}</datalist></label>
    <ul class="lint" id="lint"></ul>
    <div class="actions">
      <button class="btn ghost" id="drafts" type="button">Generuj 3 szkice</button>
      <button class="btn ghost" id="save" type="button" ${guarded("write")}>Zapisz wersję</button>
      <button class="btn primary" id="approve" type="button" ${guarded("write")}>Zapisz i zaakceptuj</button>
    </div>
    <div id="draftList" class="drafts"></div>
    ${blockReason("write") ? `<p class="note">${esc(blockReason("write"))} Tekst możesz edytować i skopiować — zapis do kolejki odblokuje właściciel.</p>` : ""}`;
  let tags = c.content.hashtags.split(/\s+/).filter(Boolean);
  const desc = $("#description"), limit = profile.caption_max || 2200;
  const drawChips = () => {
    $("#chips").innerHTML = tags.length ? tags.map((t, i) => `<span class="chip">${esc(t)}<button type="button" data-i="${i}" aria-label="Usuń ${esc(t)}">×</button></span>`).join("") : `<span class="muted">Brak hashtagów — to dozwolone.</span>`;
    $$("#chips button").forEach(b => b.onclick = () => { tags.splice(+b.dataset.i, 1); drawChips(); lint(); });
  };
  const counter = () => { const n = desc.value.trim().length; $("#counter").textContent = `${n} / ${limit}`; $("#counter").className = n > limit ? "bad" : "muted"; };
  let lintTimer;
  const lint = () => { clearTimeout(lintTimer); lintTimer = setTimeout(async () => {
    try {
      const q = new URLSearchParams({ description: desc.value, hashtags: tags.join(" ") });
      const r = await api(`${pub(c.post_id)}/lint?${q}`);
      $("#lint").innerHTML = r.notes.map(n => `<li class="${esc(n.level)}">${esc(n.text)}</li>`).join("");
    } catch { /* kontrola jest pomocnicza */ }
  }, 250); };
  const addTag = raw => raw.split(/[\s,]+/).filter(Boolean).forEach(t => { const tag = "#" + t.replace(/^#+/, ""); if (tag.length > 1 && !tags.some(x => x.toLowerCase() === tag.toLowerCase())) tags.push(tag); });
  $("#tagInput").onkeydown = e => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addTag(e.target.value); e.target.value = ""; drawChips(); lint(); } };
  $("#suggestTags").onclick = e => run(e.currentTarget, async () => { const r = await post(`${pub(c.post_id)}/hashtags-suggest`, { variant: Math.floor(Math.random() * 5) }); tags = []; addTag(r.hashtags); drawChips(); lint(); }, "Hashtagi z biblioteki marki. Sprawdź przed zapisem.");
  $("#clearTags").onclick = () => { tags = []; drawChips(); lint(); toast("Usunięto hashtagi w edytorze. Zapisz, żeby utrwalić."); };
  desc.oninput = () => { counter(); lint(); };
  const save = approve => async e => {
    const pending = $("#tagInput").value.trim(); if (pending) { addTag(pending); $("#tagInput").value = ""; drawChips(); }
    await run(e.currentTarget, async () => {
      try {
        const fresh = await post(`${pub(c.post_id)}/content`, { expected_revision: c.revision, description: desc.value, hashtags: tags.join(" "), location: $("#location").value, approve });
        await refreshCard(c, fresh);
      } catch (err) {
        if (err.status === 409) throw new Error("Paczka zmieniła się w międzyczasie. Twój tekst został w edytorze — skopiuj go, odśwież i zapisz ponownie.");
        throw err;
      }
    }, approve ? "Zapisano i zaakceptowano. Wersja odczytana ponownie z dysku." : "Zapisano. Wersja wymaga akceptacji.");
  };
  $("#save").onclick = save(false);
  $("#approve").onclick = save(true);
  $("#drafts").onclick = e => run(e.currentTarget, async () => {
    const r = await post(`${pub(c.post_id)}/drafts`, { topic: c.content.description.split("\n").find(Boolean) || c.name });
    $("#draftList").innerHTML = r.drafts.map(d => `<article class="draft"><header><b>Szkic ${d.variant}</b><button class="btn ghost small" type="button" data-v="${d.variant}">Wstaw do edytora</button></header><p>${esc(d.description)}</p><small class="tags">${esc(d.hashtags)}</small></article>`).join("");
    $$("#draftList [data-v]").forEach(b => b.onclick = () => { const d = r.drafts[+b.dataset.v - 1]; desc.value = d.description; tags = []; addTag(d.hashtags); drawChips(); counter(); lint(); toast("Szkic w edytorze. Popraw i zapisz."); });
  }, "Szkice z szablonu marki. Nic nie zostało zapisane.");
  drawChips(); counter(); lint();
}

// ---------- Kanały ----------
function channels(c, p) {
  p.innerHTML = `${CHANNELS.map(([k, n]) => { const ch = c.channels[k]; return `
    <article class="channel ${ch.enabled === false ? "off" : ""}">
      <header><b>${n}</b>${pill(ch)}</header>
      <dl class="mini">
        <div><dt>Dowód platformy</dt><dd>${esc(ch.platform_evidence)}${ch.evidence_source ? ` · ${esc(ch.evidence_source)}` : ""}</dd></div>
        <div><dt>Twój haczyk</dt><dd>${ch.manual_checked ? "tak (ręcznie)" : "nie"}</dd></div>
        <div><dt>Termin platformy</dt><dd>${esc(ch.platform_target_at || "—")}</dd></div>
        ${ch.info ? `<div><dt>Info</dt><dd>${esc(ch.info)}</dd></div>` : ""}
      </dl>
      <div class="actions">
        <button class="btn ghost" type="button" data-prepare="${k}" ${guarded("publish")}>Przygotuj</button>
        <button class="btn ghost" type="button" data-retry="${k}" ${guarded("publish")}>Ponów</button>
        <button class="btn ${ch.manual_checked ? "ghost" : "primary"}" type="button" data-manual="${k}" data-checked="${!ch.manual_checked}" ${guarded("write")}>${ch.manual_checked ? "Cofnij mój haczyk" : "Potwierdzam wykonanie"}</button>
      </div>
    </article>`; }).join("")}
    <div class="actions">
      <button class="btn ghost" id="both" type="button" ${guarded("publish")}>Przygotuj IG + FB</button>
      <button class="btn ghost" id="music" type="button" ${guarded("publish")}>Muzyka dobrana</button>
      <button class="btn ghost" id="verify" type="button" ${guarded("legacy")}>Sprawdź na platformach</button>
    </div>
    <p class="note" id="caps">Odczytuję HD, muzykę i adapter…</p>
    <pre class="report" id="report" hidden></pre>
    <p class="note">Końcowe kliknięcie „Opublikuj” zawsze wykonujesz ręcznie. Haczyk to Twoje oświadczenie — nie zmienia dowodu platformy.</p>`;
  const prepare = (channel, retry) => e => run(e.currentTarget, () => post(`${pub(c.post_id)}/prepare-publication`, { channel, retry }), "Formularz przygotowany. Sprawdź i kliknij publikację ręcznie.");
  $$("[data-prepare]", p).forEach(b => b.onclick = prepare(b.dataset.prepare, false));
  $$("[data-retry]", p).forEach(b => b.onclick = async e => { if (await confirmDialog("Ponowić wysyłkę?", "Najpierw upewnij się na platformie, że poprzednia próba nie przeszła. Inaczej powstanie duplikat.", "Ponów")) prepare(b.dataset.retry, true)(e); });
  $$("[data-manual]", p).forEach(b => b.onclick = async e => {
    const checked = b.dataset.checked === "true";
    if (checked && !(await confirmDialog("Potwierdzasz wykonanie?", `Oświadczasz, że ${b.dataset.manual} jest opublikowany lub zaplanowany na platformie. To ręczne oznaczenie, nie dowód.`))) return;
    run(e.currentTarget, async () => refreshCard(c, await post(`${pub(c.post_id)}/manual-check`, { channel: b.dataset.manual, checked, expected_revision: c.revision })), checked ? "Zapisano Twój haczyk." : "Cofnięto Twój haczyk.");
  });
  $("#both").onclick = prepare("obie", false);
  $("#music").onclick = e => run(e.currentTarget, () => post(`${pub(c.post_id)}/music-ready`), "Sygnał muzyki wysłany do uploadera.");
  $("#verify").onclick = e => run(e.currentTarget, async () => { const r = await post(`${pub(c.post_id)}/verify`); const pre = $("#report"); pre.hidden = false; pre.textContent = JSON.stringify(r, null, 2); }, "Raport weryfikacji poniżej. Statusy nie zostały zmienione automatycznie.");
  api(`${pub(c.post_id)}/capabilities`).then(x => { $("#caps").textContent = `HD: ${x.hd.etykieta || x.hd.stan} · Muzyka: ${x.awaiting_music ? "czeka na wybór" : "nie czeka"} · ${x.is_carousel ? "karuzela" : "rolka"} · końcowe kliknięcie: ręczne`; }).catch(e => { $("#caps").textContent = e.message; });
}

// ---------- Telefon ----------
function phone(c, p) {
  const ev = c.mobile_events;
  p.innerHTML = `
    <div class="transfer-flow">
      <div class="step ${c.tiktok_transfer ? "ok" : ""}"><b>1</b><span>TikTok</span><small>${esc(c.tiktok_transfer || "brak dowodu")}</small></div>
      <div class="step ${c.phone_ready ? "ok" : ""}"><b>2</b><span>Paczka</span><small>${c.phone_ready ? "gotowa do eksportu" : "warunek niespełniony"}</small></div>
      <div class="step"><b>3</b><span>Telefon</span><small>Drive / serwer</small></div>
      <div class="step ${c.channels.instagram.manual_checked ? "ok" : ""}"><b>4</b><span>Instagram</span><small>${c.channels.instagram.manual_checked ? "potwierdzony" : "oczekuje"}</small></div>
    </div>
    ${c.phone_ready ? "" : `<p class="note">Paczka telefonu wymaga: TikTok opublikowany/zaplanowany, Instagram jeszcze nieopublikowany, komplet plików, poza archiwum.</p>`}
    <div class="actions">
      <button class="btn primary" id="exportPkg" type="button" ${c.phone_ready ? "" : "disabled title=\"Warunek transferu niespełniony\""}>Przygotuj paczkę</button>
      <button class="btn ghost" id="toDrive" type="button" ${c.phone_ready ? guarded("drive") : "disabled"}>Wyślij na Google Drive</button>
      <button class="btn ghost" id="toServer" type="button" ${c.phone_ready ? guarded("server") : "disabled"}>Wyślij na telefon (serwer)</button>
    </div>
    <div id="pkgResult"></div>
    <h3>Zgłoszenia z telefonu</h3>
    ${ev === undefined ? `<p class="muted">Odczytuję…</p>` : ev.length ? `<ul class="events">${ev.map(x => `<li><b>${esc(x.type)}</b> <small>${esc(x.occurred_at || "")}</small></li>`).join("")}</ul><p class="note">Zgłoszenia telefonu są informacją. Haczyk w kolejce stawiasz sam w zakładce Kanały.</p>` : `<p class="muted">Brak zgłoszeń.</p>`}`;
  if (ev === undefined) api(pub(c.post_id)).then(fresh => { c.mobile_events = fresh.mobile_events || []; if (state.selected === c.post_id && state.tab === "phone") renderDrawer(); });
  $("#exportPkg").onclick = e => run(e.currentTarget, async () => {
    const r = await post(`${pub(c.post_id)}/phone-package`, { channel: "instagram" });
    $("#pkgResult").innerHTML = `<div class="pkg"><b>Paczka ${esc(r.manifest.content_revision.slice(0, 12))}</b><small>${r.manifest.files.length} plików · sumy SHA-256 · ${esc(r.manifest.exported_at)}</small><a class="btn ghost small" href="${esc(r.url)}" download>Pobierz ZIP</a></div>`;
  }, "Paczka gotowa. Manifest zgodny z kontraktem v2.");
  $("#toDrive").onclick = e => run(e.currentTarget, () => post(`${pub(c.post_id)}/to-drive`), r => `Skopiowano na Dysk: ${r.path}`);
  $("#toServer").onclick = e => run(e.currentTarget, () => post(`${pub(c.post_id)}/to-server`), "Wysłano na serwer. Telefon zobaczy paczkę po odświeżeniu.");
}

// ---------- Historia ----------
function history(c, p) {
  p.innerHTML = c.history.length
    ? `<ol class="timeline">${c.history.slice().reverse().map(h => `<li><b>${esc(h.co || "Zmiana")}</b><small>${esc(h.kiedy || "")}</small><span>${esc(h.szczegol || "")}</span></li>`).join("")}</ol>`
    : `<p class="muted">Brak zapisanej historii.</p>`;
}

export { reload };
