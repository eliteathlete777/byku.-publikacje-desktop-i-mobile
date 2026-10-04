// Pełnoekranowy dashboard edycji rolki (nowa zakładka: /?edit=<post_id>) — wszystko na jednym ekranie, bez przewijania strony.
import { $, $$, api, post, pub, esc, state, toast, run, playUrl, markWatched, guarded, blockReason } from "./core.js";
import { openThumbStudio } from "./thumbstudio.js";

// Wybór z trzech wariantów: zakładki 1/2/3, strzałki ←/→, jeden duży podgląd i jedno „Użyj”.
export function variantPicker(box, drafts, onUse) {
  let i = 0;
  const draw = () => {
    const d = drafts[i];
    box.innerHTML = `<div class="vp">
      <div class="vp-tabs" role="tablist">${drafts.map((x, k) => `<button type="button" role="tab" class="${k === i ? "on" : ""}" data-k="${k}"><b>${k + 1}</b><small>${x.description.length} zn.</small></button>`).join("")}</div>
      <article class="vp-body"><p>${esc(d.description)}</p>${d.missing ? `<p class="note">Konkret podniósłby tekst: ${esc(d.missing)}</p>` : ""}${d.lint?.length ? `<ul class="lint">${d.lint.map(n => `<li class="${esc(n.level)}">${esc(n.text)}</li>`).join("")}</ul>` : d.lint ? `<small class="ok-note">Zgodny z kompendium.</small>` : ""}</article>
      <div class="vp-actions"><button type="button" class="btn ghost small" data-step="-1" aria-label="Poprzedni">←</button><button type="button" class="btn primary" data-use>Użyj wariantu ${i + 1}</button><button type="button" class="btn ghost small" data-step="1" aria-label="Następny">→</button></div></div>`;
    $$("[data-k]", box).forEach(b => b.onclick = () => { i = +b.dataset.k; draw(); });
    $$("[data-step]", box).forEach(b => b.onclick = () => { i = (i + +b.dataset.step + drafts.length) % drafts.length; draw(); });
    $("[data-use]", box).onclick = () => onUse(drafts[i]);
  };
  draw();
  box.tabIndex = 0;
  box.onkeydown = e => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    i = (i + (e.key === "ArrowRight" ? 1 : drafts.length - 1)) % drafts.length; draw(); box.focus();
  };
}

// Brakujące słowa kluczowe: jedna linia na samym końcu opisu.
export function finishKeywords(text, keywords) {
  const missing = keywords.filter(k => !text.toLowerCase().includes(k.toLowerCase()));
  if (!missing.length) return text;
  const paras = text.trimEnd().split(/\n\s*\n/);
  const last = paras[paras.length - 1] || "";
  const isKwLine = keywords.some(k => last.toLowerCase().includes(k.toLowerCase())) && last.length < 260;
  if (isKwLine) { paras[paras.length - 1] = last.replace(/[.!\s]*$/, "") + ", " + missing.join(", ") + "."; return paras.join("\n\n"); }
  const line = missing.join(", ");
  return `${text.trimEnd()}\n\n${line[0].toUpperCase()}${line.slice(1)}.`;
}

export async function renderDashboard(id) {
  const root = $("#drawer");
  const c = state.cards.find(x => x.post_id === id);
  if (!c) { root.innerHTML = `<div class="dash-empty"><h2>Nie znaleziono rolki</h2><p class="muted">${esc(id)}</p></div>`; return; }
  document.title = `Edycja · ${c.name}`;
  const queue = (new URLSearchParams(location.search).get("q") || "").split(",").filter(x => state.cards.some(k => k.post_id === x));
  const pos = queue.indexOf(id);
  const go = target => { if (target) location.search = `?edit=${encodeURIComponent(target)}&q=${encodeURIComponent(queue.join(","))}${new URLSearchParams(location.search).get("studio") === "1" ? "&studio=1" : ""}`; };
  const nextNoCover = queue.find((x, k) => k !== pos && !state.cards.find(y => y.post_id === x).assets.cover_custom);
  const profile = state.brands[c.brand] || {};
  const kwMode = profile.tag_mode === "keywords", keywords = profile.keywords || [];
  const limit = profile.caption_max || 2200, min = profile.caption_min || 0;
  const ai = state.health?.ai || {};
  const aiBlock = !ai.sdk ? "Brak biblioteki AI." : !ai.key ? "Brak klucza API w desktop/.env." : "";
  const locations = [...new Set([...(profile.locations || []), ...state.cards.map(x => x.content.location).filter(Boolean)])];
  const media = c.assets.media_urls || [];
  const player = c.assets.type === "carousel"
    ? `<div class="slides dash-slides">${media.map((u, k) => `<img src="${esc(u)}" alt="Slajd ${k + 1}">`).join("")}</div>`
    : media[0] ? `<video class="dash-video" controls preload="metadata" src="${esc(playUrl(c))}" poster="${esc(c.assets.thumbnail_url)}"></video>` : `<div class="dash-video missing">Brak pliku wideo</div>`;
  root.innerHTML = `
  <div class="dash">
    <header class="dash-top">
      <div class="dash-id"><span class="brand-mark">B</span><div><p class="kicker">${esc(c.brand.toUpperCase())} · ${c.assets.type === "carousel" ? "KARUZELA" : "ROLKA"} · edycja pełnoekranowa</p><h1>${esc(c.name)}</h1></div></div>
      ${queue.length > 1 ? `<div class="dash-nav"><button class="btn ghost small" id="navPrev" type="button" ${pos <= 0 ? "disabled" : ""}>‹</button><span>${pos + 1} / ${queue.length}</span><button class="btn ghost small" id="navNext" type="button" ${pos >= queue.length - 1 ? "disabled" : ""}>›</button>${nextNoCover ? `<button class="btn primary small" id="navNoCover" type="button">Następna bez okładki →</button>` : ""}</div>` : ""}
      <ol class="dash-steps" id="steps"></ol>
      <div class="dash-actions">
        <button class="btn ghost" id="dSave" type="button" ${guarded("write")}>Zapisz wersję</button>
        <button class="btn primary" id="dApprove" type="button">Zapisz i zaakceptuj</button>
      </div>
    </header>
    <section class="dash-col dash-media">
      <h2>Film i okładka</h2>
      ${player}
      <div class="dash-cover">
        <button type="button" class="dash-cover-img" id="dCover" title="Otwórz Studio miniatury" ${guarded("write")}>${c.assets.thumbnail_url ? `<img src="${esc(c.assets.thumbnail_url)}" alt="Okładka">` : `<span>brak okładki</span>`}</button>
        <div><span class="cover-badge ${c.assets.cover_custom ? "ok" : "bad"}">${c.assets.cover_custom ? "✓ Nowa okładka z tytułem" : "✕ Brak nowej okładki z tytułem"}</span>
          <p class="muted small">System nie przepuści rolki bez okładki zrobionej w Studiu miniatury (klatka startowa się nie liczy).</p>
          <button class="btn ${c.assets.cover_custom ? "ghost" : "primary"}" id="dStudio" type="button" ${guarded("write")}>${c.assets.cover_custom ? "Popraw okładkę" : "Zrób okładkę z tytułem"}</button></div>
      </div>
      <label class="field"><span>Lokalizacja</span><input id="location" list="locs" value="${esc(c.content.location)}"><datalist id="locs">${locations.map(l => `<option value="${esc(l)}">`).join("")}</datalist></label>
    </section>
    <section class="dash-col dash-compose">
      <h2>Opis z podstawy</h2>
      <label class="field"><span>Podstawa opisu <small class="muted">tylko to trafi do opisu</small></span><textarea id="basis" rows="4" placeholder="Miejsce, sytuacja, ćwiczenie, liczby…"></textarea></label>
      <div class="inline"><button class="btn primary" id="compose" type="button" ${aiBlock ? `disabled title="${esc(aiBlock)}"` : ""}>Ułóż 3 warianty</button><small class="muted" id="basisState">${aiBlock ? esc(aiBlock) : `${esc(ai.label || "")} ${esc(ai.model || "")}`}</small></div>
      <div id="variants" class="variants"><p class="muted small">Po kliknięciu pojawią się trzy warianty: przełączaj 1 / 2 / 3 albo strzałkami ← →, potem „Użyj”.</p></div>
    </section>
    <section class="dash-col dash-text">
      <h2>Opis <small id="counter" class="muted"></small></h2>
      <textarea id="description" class="dash-desc">${esc(c.content.description)}</textarea>
      ${kwMode ? `<div class="kw-box"><div class="kw-head"><span>Słowa kluczowe na końcu <small class="muted">minimum każdej rolki</small></span><button class="btn ghost small" id="kwAll" type="button">Dopisz brakujące na końcu</button></div><div class="chips" id="kwChips"></div></div>` : ""}
      <ul class="lint" id="lint"></ul>
    </section>
  </div>`;

  const desc = $("#description"), basis = $("#basis"), basisState = $("#basisState");
  const hasKw = () => keywords.every(k => desc.value.toLowerCase().includes(k.toLowerCase()));
  const checks = () => [
    ["Film", media.length > 0],
    ["Okładka z tytułem", !!c.assets.cover_custom],
    [`Opis ≥ ${min}`, desc.value.trim().length >= min && desc.value.trim().length > 0 && desc.value.trim().length <= limit],
    ...(kwMode ? [["Słowa kluczowe", hasKw()]] : []),
    ["Lokalizacja", !!$("#location").value.trim()]
  ];
  const paint = () => {
    $("#steps").innerHTML = checks().map(([n, ok]) => `<li class="${ok ? "ok" : ""}"><i>${ok ? "✓" : "○"}</i>${esc(n)}</li>`).join("");
    const n = desc.value.trim().length;
    $("#counter").textContent = `${n} / ${limit}`; $("#counter").className = n > limit ? "bad" : "muted";
    const block = blockReason("write") || (!c.assets.cover_custom ? "Najpierw nowa okładka z tytułem." : "");
    const ap = $("#dApprove"); ap.disabled = !!block; ap.title = block;
    if (kwMode) {
      const t = desc.value.toLowerCase();
      $("#kwChips").innerHTML = keywords.map(k => t.includes(k.toLowerCase()) ? `<span class="chip kw-ok">✓ ${esc(k)}</span>` : `<span class="chip kw-missing">${esc(k)}</span>`).join("");
      $("#kwAll").disabled = hasKw();
    }
  };
  let lintTimer;
  const lint = () => { clearTimeout(lintTimer); lintTimer = setTimeout(async () => {
    try { const r = await api(`${pub(c.post_id)}/lint?${new URLSearchParams({ description: desc.value, hashtags: c.content.hashtags || "" })}`); $("#lint").innerHTML = r.notes.map(n => `<li class="${esc(n.level)}">${esc(n.text)}</li>`).join(""); } catch { /* kontrola jest pomocnicza */ }
  }, 250); };
  desc.oninput = () => { paint(); lint(); };
  $("#location").oninput = paint;
  if (kwMode) $("#kwAll").onclick = () => { desc.value = finishKeywords(desc.value, keywords); paint(); lint(); toast("Słowa kluczowe dopisane na końcu."); };

  const refresh = async fresh => { Object.assign(c, fresh || await api(pub(c.post_id))); renderDashboard(id); };
  $("video.dash-video")?.addEventListener("play", () => markWatched(c.post_id), { once: true });
  const studio = () => openThumbStudio(c, {}, fresh => refresh(fresh));
  $("#dCover").onclick = studio; $("#dStudio").onclick = studio;
  if (new URLSearchParams(location.search).get("studio") === "1" && !c.assets.cover_custom && !renderDashboard.autoOpened) { renderDashboard.autoOpened = true; setTimeout(studio, 300); }

  api(`${pub(c.post_id)}/basis`).then(r => { if (!basis.value) basis.value = r.basis || ""; }).catch(() => {});
  let bt; basis.oninput = () => { clearTimeout(bt); bt = setTimeout(() => post(`${pub(c.post_id)}/basis`, { basis: basis.value }).catch(() => {}), 600); };
  $("#compose").onclick = e => run(e.currentTarget, async () => {
    basisState.textContent = `${ai.label || "AI"} układa warianty… (do minuty)`;
    try {
      const r = await post(`${pub(c.post_id)}/compose`, { basis: basis.value });
      variantPicker($("#variants"), r.drafts, d => { desc.value = d.description; paint(); lint(); toast("Wariant wstawiony. Dopisz słowa kluczowe i zapisz."); });
      basisState.textContent = `${r.drafts.length} warianty od ${r.model}.`;
    } catch (err) { basisState.textContent = err.message; throw err; }
  }, "Warianty gotowe. Nic nie zostało zapisane.");

  const save = approve => e => run(e.currentTarget, async () => {
    try { await refresh(await post(`${pub(c.post_id)}/content`, { expected_revision: c.revision, description: desc.value, hashtags: kwMode ? "" : c.content.hashtags, location: $("#location").value, approve })); }
    catch (err) { if (err.status === 409) throw new Error("Paczka zmieniła się w międzyczasie. Skopiuj tekst, odśwież stronę i zapisz ponownie."); throw err; }
  }, approve ? "Zapisano i zaakceptowano." : "Zapisano jako wersję roboczą.");
  $("#dSave").onclick = save(false); $("#dApprove").onclick = save(true);
  $("#navPrev")?.addEventListener("click", () => go(queue[pos - 1]));
  $("#navNext")?.addEventListener("click", () => go(queue[pos + 1]));
  $("#navNoCover")?.addEventListener("click", () => go(nextNoCover));
  paint(); lint();
}
