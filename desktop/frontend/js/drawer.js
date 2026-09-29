// Panel szczegółów publikacji: podgląd, treść, kanały, telefon, historia.
import { $, $$, api, post, pub, esc, state, toast, run, pill, thumb, fmtTerm, guarded, blockReason, confirmDialog, modal, CHANNELS } from "./core.js";

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
      ${c.assets.thumbnail_url ? `<button type="button" class="thumb-edit-btn" id="headThumb" title="Kliknij, aby edytować kadr miniatury">${thumb(c, "drawer-thumb")}</button>` : thumb(c, "drawer-thumb")}
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
  if ($("#headThumb")) $("#headThumb").onclick = () => openThumbnailEditor(c, { url: c.assets.thumbnail_url });
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
  const hasThumb = !!c.assets.thumbnail_url;
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
    <div class="caption-edit">
      <textarea id="captionQuick" rows="6">${esc(c.content.description)}</textarea>
      <div class="caption-edit-actions" id="captionEditActions" hidden>
        <button class="btn ghost small" id="captionCancel" type="button">Anuluj</button>
        <button class="btn primary small" id="captionSave" type="button" ${guarded("write")}>Zapisz opis</button>
      </div>
    </div>
    ${(state.brands[c.brand] || {}).tag_mode === "keywords"
      ? (c.content.hashtags ? `<p class="note">Ma jeszcze hashtagi (${esc(c.content.hashtags)}). Marka używa słów kluczowych, usuń je w zakładce Treść.</p>` : "")
      : `<p class="tags">${esc(c.content.hashtags || "Brak hashtagów.")}</p>`}
    <div class="actions">
      <button class="btn primary" id="primary" type="button">${esc(c.next_action.label)}</button>
      <button class="btn ghost" id="folder" type="button">Otwórz folder</button>
      <label class="btn ghost file-btn" ${blockReason("write") ? `title="${esc(blockReason("write"))}"` : ""}>Zmień miniaturę<input type="file" accept="image/png" id="thumbInput" ${blockReason("write") ? "disabled" : ""}></label>
      ${!hasThumb ? `<button class="btn ghost" id="genThumb" type="button" ${guarded("write")}>Wygeneruj miniaturę ${c.assets.type === "carousel" ? "z pierwszego slajdu" : "z wideo"}</button>` : ""}
    </div>`;
  $("#folder").onclick = e => run(e.currentTarget, () => post(`${pub(c.post_id)}/open-folder`), "Otwarto folder paczki.");
  $("#primary").onclick = () => primary(c);
  $("#thumbInput").onchange = e => {
    const file = e.target.files[0]; e.target.value = "";
    if (file) openThumbnailEditor(c, { file });
  };
  if ($("#genThumb")) $("#genThumb").onclick = e => run(e.currentTarget, async () => {
    const url = c.assets.type === "carousel" ? media[0] : await captureVideoFrame(media[0]);
    if (!url) throw new Error("Brak pliku źródłowego do wygenerowania miniatury.");
    openThumbnailEditor(c, { url });
  });
  const captionArea = $("#captionQuick"), captionActions = $("#captionEditActions");
  const original = c.content.description;
  captionArea.oninput = () => { captionActions.hidden = captionArea.value === original; };
  $("#captionCancel").onclick = () => { captionArea.value = original; captionActions.hidden = true; };
  $("#captionSave").onclick = e => run(e.currentTarget, async () => {
    const fresh = await post(`${pub(c.post_id)}/content`, { expected_revision: c.revision, description: captionArea.value, hashtags: c.content.hashtags, location: c.content.location, approve: false });
    await refreshCard(c, fresh);
  }, "Opis zapisany jako wersja robocza. Zaakceptuj w zakładce Treść, gdy będzie gotowy.");
}

// Brakujące słowo kluczowe dopisujemy do linii słów kluczowych (ostatni akapit z frazami), inaczej nowy akapit.
function withKeyword(text, keyword, keywords) {
  const paras = text.trimEnd().split(/\n\s*\n/);
  const last = paras[paras.length - 1] || "";
  if (keywords.some(k => last.toLowerCase().includes(k.toLowerCase()))) {
    paras[paras.length - 1] = last.replace(/[.!\s]*$/, "") + `, ${keyword}.`;
    return paras.join("\n\n");
  }
  return `${text.trimEnd()}\n\n${keyword[0].toUpperCase()}${keyword.slice(1)}.`;
}

// Scena do szkicu = konkretny akapit po haku (miejsce, sytuacja), nie hak i nie końcowa linia SEO.
function sceneFrom(description) {
  const paras = (description || "").split(/\n\s*\n/).map(p => p.replace(/\s+/g, " ").trim()).filter(p => p && !p.includes("#"));
  if (paras.length > 2) return paras[1];
  if (!paras[0]) return "";
  const emoji = [...paras[0]][0];
  const afterHook = /[\p{L}\p{N}]/u.test(emoji) ? "" : paras[0].split(emoji).slice(2).join(emoji).trim();
  return afterHook.split(/(?<=[.!?])\s/)[0] || "";
}

function captureVideoFrame(videoUrl) {
  return new Promise((resolve, reject) => {
    if (!videoUrl) return resolve(null);
    const v = document.createElement("video");
    v.src = videoUrl; v.muted = true; v.playsInline = true; v.preload = "auto";
    v.addEventListener("loadedmetadata", () => { v.currentTime = Math.min(1, (v.duration || 2) * 0.1) || 0.05; });
    v.addEventListener("seeked", () => {
      const canvas = document.createElement("canvas");
      canvas.width = v.videoWidth; canvas.height = v.videoHeight;
      canvas.getContext("2d").drawImage(v, 0, 0);
      resolve(canvas.toDataURL("image/png"));
    });
    v.addEventListener("error", () => reject(new Error("Nie udało się wczytać wideo, aby wygenerować miniaturę.")));
  });
}

// ---------- Edytor miniatury ----------
const THUMB_RATIOS = [["9:16", 9 / 16], ["4:5", 4 / 5], ["1:1", 1]];
const FRAME_W = 260;

function openThumbnailEditor(c, source) {
  const fromFile = !!source.file;
  const url = fromFile ? URL.createObjectURL(source.file) : source.url;
  const img = new Image();
  let ratioKey = c.assets.type === "carousel" ? "1:1" : "9:16";
  const st = { scale: 1, offX: 0, offY: 0 };

  const dlg = modal(`
    <h2>${fromFile ? "Zmień miniaturę" : "Edytuj kadr miniatury"}</h2>
    <p class="muted small">Przeciągnij, aby przesunąć kadr. Suwak przybliża.</p>
    <div class="thumb-editor">
      <div class="thumb-frame" id="thumbFrame"><img id="thumbImg" src="${esc(url)}" alt="" draggable="false"></div>
      <div class="thumb-controls">
        <div class="field"><span>Proporcje</span><div class="seg" id="ratioSeg">${THUMB_RATIOS.map(([k]) => `<button type="button" data-r="${k}" class="${k === ratioKey ? "active" : ""}">${k}</button>`).join("")}</div></div>
        <div class="field"><span>Powiększenie</span><input id="thumbZoom" type="range" min="1" max="3" step="0.01" value="1"></div>
      </div>
    </div>
    <div class="actions end">
      <button class="btn ghost" id="thumbCancel" type="button">Anuluj</button>
      <button class="btn primary" id="thumbSave" type="button">Zapisz miniaturę</button>
    </div>`, d => {
    if (fromFile) d.addEventListener("close", () => URL.revokeObjectURL(url), { once: true });
  });

  const frame = $("#thumbFrame", dlg), imgEl = $("#thumbImg", dlg), zoom = $("#thumbZoom", dlg);
  let coverScale = 1, ready = false;

  const setFrameSize = () => {
    const h = Math.round(FRAME_W / THUMB_RATIOS.find(([k]) => k === ratioKey)[1]);
    frame.style.width = `${FRAME_W}px`; frame.style.height = `${h}px`;
  };
  const clamp = () => {
    const s = coverScale * st.scale;
    const maxX = Math.max(0, (img.naturalWidth * s - frame.clientWidth) / 2);
    const maxY = Math.max(0, (img.naturalHeight * s - frame.clientHeight) / 2);
    st.offX = Math.min(maxX, Math.max(-maxX, st.offX));
    st.offY = Math.min(maxY, Math.max(-maxY, st.offY));
  };
  const paint = () => {
    if (!ready) return;
    clamp();
    const s = coverScale * st.scale;
    imgEl.style.width = `${img.naturalWidth * s}px`;
    imgEl.style.height = `${img.naturalHeight * s}px`;
    imgEl.style.transform = `translate(-50%, -50%) translate(${st.offX}px, ${st.offY}px)`;
  };

  img.onload = () => {
    ready = true; setFrameSize();
    coverScale = Math.max(frame.clientWidth / img.naturalWidth, frame.clientHeight / img.naturalHeight);
    st.scale = 1; st.offX = 0; st.offY = 0; zoom.value = "1";
    paint();
  };
  img.src = url;

  $$("#ratioSeg button", dlg).forEach(b => b.onclick = () => {
    ratioKey = b.dataset.r;
    $$("#ratioSeg button", dlg).forEach(x => x.classList.toggle("active", x === b));
    setFrameSize();
    coverScale = Math.max(frame.clientWidth / img.naturalWidth, frame.clientHeight / img.naturalHeight);
    st.offX = 0; st.offY = 0; paint();
  });
  zoom.oninput = () => { st.scale = +zoom.value; paint(); };

  let dragging = null;
  frame.onpointerdown = e => { dragging = { x: e.clientX, y: e.clientY, offX: st.offX, offY: st.offY }; frame.setPointerCapture(e.pointerId); };
  frame.onpointermove = e => { if (!dragging) return; st.offX = dragging.offX + (e.clientX - dragging.x); st.offY = dragging.offY + (e.clientY - dragging.y); paint(); };
  const endDrag = () => { dragging = null; };
  frame.onpointerup = endDrag; frame.onpointercancel = endDrag;

  $("#thumbCancel", dlg).onclick = () => dlg.close();
  $("#thumbSave", dlg).onclick = async e => {
    await run(e.currentTarget, async () => {
      const outW = 1080, outH = Math.round(outW / THUMB_RATIOS.find(([k]) => k === ratioKey)[1]);
      const canvas = document.createElement("canvas");
      canvas.width = outW; canvas.height = outH;
      const ctx = canvas.getContext("2d");
      const k = outW / frame.clientWidth, s = coverScale * st.scale * k;
      ctx.save();
      ctx.translate(outW / 2 + st.offX * k, outH / 2 + st.offY * k);
      ctx.scale(s, s);
      ctx.drawImage(img, -img.naturalWidth / 2, -img.naturalHeight / 2);
      ctx.restore();
      const blob = await new Promise(res => canvas.toBlob(res, "image/png"));
      const r = await fetch(`${pub(c.post_id)}/thumbnail`, { method: "PUT", body: blob, headers: { "X-Expected-Revision": c.revision } });
      const data = await r.json(); if (!r.ok) throw new Error(data.error);
      dlg.close();
      await refreshCard(c, data);
    }, "Miniatura podmieniona. Nowa wersja treści.");
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
  const kwMode = profile.tag_mode === "keywords";
  const locations = [...new Set([...(profile.locations || []), ...state.cards.map(x => x.content.location).filter(Boolean)])];
  const ai = state.health?.ai || {};
  const aiBlock = !ai.sdk ? "Brak biblioteki anthropic (python -m pip install anthropic)." : !ai.key ? "Brak klucza API: dopisz ANTHROPIC_API_KEY=... do desktop/.env i uruchom appkę ponownie." : "";
  p.innerHTML = `
    <div class="basis-box">
      <label class="field"><span>Podstawa opisu</span><small class="basis-hint">Wszystko, co ma się znaleźć w opisie: miejsce, sytuacja, ćwiczenie, liczby, żart. Nic spoza niej nie zostanie dopisane.</small><textarea id="basis" rows="5" placeholder="Np. Hotel w Katowicach po montażu, 22:30, dwie serie pompek przy łóżku przed prysznicem, guma w plecaku…"></textarea></label>
      <div class="inline"><button class="btn primary" id="compose" type="button" ${aiBlock ? `disabled title="${esc(aiBlock)}"` : ""}>Ułóż opis z podstawy</button><small class="muted" id="basisState">${aiBlock ? esc(aiBlock) : `${esc(ai.model || "")} · 3 warianty według kompendium`}</small></div>
    </div>
    <label class="field"><span>Opis <small id="counter" class="muted"></small></span><textarea id="description" rows="8">${esc(c.content.description)}</textarea></label>
    ${kwMode ? `<div class="field"><span>Słowa kluczowe <small class="muted">w treści opisu, bez #. Kliknij brakujące, żeby dopisać</small></span>
      <div class="chips" id="kwChips"></div>
      <div id="oldTags"></div>
    </div>` : `<div class="field"><span>Hashtagi</span>
      <div class="chips" id="chips"></div>
      <div class="inline"><input id="tagInput" placeholder="Dodaj hashtag i Enter"><button class="btn ghost" id="suggestTags" type="button">Podpowiedz z marki</button><button class="btn ghost danger" id="clearTags" type="button">Usuń wszystkie</button></div>
    </div>`}
    <label class="field"><span>Lokalizacja</span><input id="location" list="locations" value="${esc(c.content.location)}"><datalist id="locations">${locations.map(l => `<option value="${esc(l)}">`).join("")}</datalist></label>
    <ul class="lint" id="lint"></ul>
    <div class="actions">
      <button class="btn ghost" id="drafts" type="button" title="Szybkie szkice z banków tekstów marki, bez AI i bez podstawy">Szkice z banków (bez AI)</button>
      <button class="btn ghost" id="save" type="button" ${guarded("write")}>Zapisz wersję</button>
      <button class="btn primary" id="approve" type="button" ${guarded("write")}>Zapisz i zaakceptuj</button>
    </div>
    <div id="draftList" class="drafts"></div>
    ${blockReason("write") ? `<p class="note">${esc(blockReason("write"))} Tekst możesz edytować i skopiować — zapis do kolejki odblokuje właściciel.</p>` : ""}`;
  let tags = c.content.hashtags.split(/\s+/).filter(Boolean);
  const desc = $("#description"), limit = profile.caption_max || 2200;
  const keywords = profile.keywords || [];
  const drawChips = () => {
    if (kwMode) {
      const text = desc.value.toLowerCase();
      $("#kwChips").innerHTML = keywords.map((k, i) => text.includes(k.toLowerCase())
        ? `<span class="chip kw-ok">✓ ${esc(k)}</span>`
        : `<button type="button" class="chip kw-missing" data-k="${i}">+ ${esc(k)}</button>`).join("") || `<span class="muted">Ustaw słowa kluczowe w panelu Marki i styl.</span>`;
      $$("#kwChips [data-k]").forEach(b => b.onclick = () => { desc.value = withKeyword(desc.value, keywords[+b.dataset.k], keywords); drawChips(); counter(); lint(); });
      $("#oldTags").innerHTML = tags.length ? `<p class="note">Ten post ma jeszcze hashtagi: ${esc(tags.join(" "))} <button type="button" class="btn ghost small danger" id="dropTags">Usuń hashtagi</button></p>` : "";
      if ($("#dropTags")) $("#dropTags").onclick = () => { tags = []; drawChips(); lint(); toast("Hashtagi usunięte w edytorze. Zapisz, żeby utrwalić."); };
      return;
    }
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
  if (!kwMode) {
    $("#tagInput").onkeydown = e => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addTag(e.target.value); e.target.value = ""; drawChips(); lint(); } };
    $("#suggestTags").onclick = e => run(e.currentTarget, async () => { const r = await post(`${pub(c.post_id)}/hashtags-suggest`, { variant: Math.floor(Math.random() * 5) }); tags = []; addTag(r.hashtags); drawChips(); lint(); }, "Hashtagi z biblioteki marki. Sprawdź przed zapisem.");
    $("#clearTags").onclick = () => { tags = []; drawChips(); lint(); toast("Usunięto hashtagi w edytorze. Zapisz, żeby utrwalić."); };
  }
  desc.oninput = () => { counter(); lint(); if (kwMode) drawChips(); };
  const save = approve => async e => {
    const pending = $("#tagInput")?.value.trim(); if (pending) { addTag(pending); $("#tagInput").value = ""; drawChips(); }
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
    const r = await post(`${pub(c.post_id)}/drafts`, { topic: sceneFrom(c.content.description) });
    $("#draftList").innerHTML = r.drafts.map(d => `<article class="draft"><header><b>Szkic ${d.variant}</b><button class="btn ghost small" type="button" data-v="${d.variant}">Wstaw do edytora</button></header><p>${esc(d.description)}</p>${d.hashtags ? `<small class="tags">${esc(d.hashtags)}</small>` : ""}</article>`).join("");
    $$("#draftList [data-v]").forEach(b => b.onclick = () => { const d = r.drafts[+b.dataset.v - 1]; desc.value = d.description; tags = []; addTag(d.hashtags); drawChips(); counter(); lint(); toast("Szkic w edytorze. Popraw i zapisz."); });
  }, "Szkice z szablonu marki. Nic nie zostało zapisane.");
  const basis = $("#basis"), basisState = $("#basisState");
  const showDrafts = drafts => {
    $("#draftList").innerHTML = drafts.map(d => `<article class="draft"><header><b>Wariant ${d.variant}${d.hook_mechanism ? ` · <small class="muted">${esc(d.hook_mechanism)}</small>` : ""}</b><span><small class="muted">${d.description.length} znaków</small> <button class="btn ghost small" type="button" data-v="${d.variant}">Wstaw do edytora</button></span></header><p>${esc(d.description)}</p>${d.hashtags ? `<small class="tags">${esc(d.hashtags)}</small>` : ""}${d.missing ? `<p class="note">Konkret podniósłby tekst: ${esc(d.missing)}</p>` : ""}${d.lint?.length ? `<ul class="lint">${d.lint.map(n => `<li class="${esc(n.level)}">${esc(n.text)}</li>`).join("")}</ul>` : d.lint ? `<small class="ok-note">Zgodny z kompendium.</small>` : ""}</article>`).join("");
    $$("#draftList [data-v]").forEach(b => b.onclick = () => { const d = drafts[+b.dataset.v - 1]; desc.value = d.description; tags = []; addTag(d.hashtags || ""); drawChips(); counter(); lint(); toast("Wariant w edytorze. Popraw i zapisz."); });
  };
  api(`${pub(c.post_id)}/basis`).then(r => { if (!basis.value) basis.value = r.basis || ""; }).catch(() => {});
  let basisTimer;
  basis.oninput = () => { clearTimeout(basisTimer); basisTimer = setTimeout(() => post(`${pub(c.post_id)}/basis`, { basis: basis.value }).then(() => { basisState.textContent = "Podstawa zapisana."; }).catch(() => {}), 600); };
  $("#compose").onclick = e => run(e.currentTarget, async () => {
    basisState.textContent = "Claude układa 3 warianty według kompendium… (do minuty)";
    try {
      const r = await post(`${pub(c.post_id)}/compose`, { basis: basis.value });
      showDrafts(r.drafts);
      basisState.textContent = `${r.drafts.length} warianty od ${r.model}. Wybierz, wstaw, popraw i zapisz.`;
    } catch (err) { basisState.textContent = err.message; throw err; }
  }, "Warianty gotowe. Nic nie zostało zapisane w kolejce.");
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
