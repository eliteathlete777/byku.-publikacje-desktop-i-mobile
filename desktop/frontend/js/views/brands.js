// Marki i styl: kompendium stylu (jedyne źródło zasad), banki tekstów w kolejności sekcji i podgląd szkiców na żywo.
import { $, $$, api, post, esc, state, run, guarded } from "../core.js";

const DAYS = ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"];
const BANK_LABELS = {
  hooks: ["Haki (pierwsza linia)", "zatrzymują scroll; emoji dokleja się samo, jeśli go nie ma"],
  scene: ["Scena", "brana z opisu posta; gdy go nie ma, z banku scen poniżej"],
  scenes: ["Sceny zapasowe", "gdy post nie ma własnej sceny; tylko prawdziwe fakty"],
  merytoryka: ["Rozwinięcie / technika", "2–3 zdania w linii"],
  closings: ["Motywacyjne domknięcia", "po konkrecie, nigdy pusty lukier"],
  facts: ["Ciekawostki „po co”", "tylko fakty potwierdzone przez Damiana"],
  side: ["Wątek poboczny: trening / humor", "sekcja opcjonalna"],
  questions: ["Pytania do komentarzy", "jedno w linii"],
  ctas: ["CTA akcji", "rotuj, nie dwa razy z rzędu to samo"],
  closers: ["Linia słów kluczowych (ostatnia)", "frazy wplecione naturalnie, bez #"]
};
const lines = v => String(v || "").split("\n").map(x => x.trim()).filter(Boolean);
const area = (b, k, label, hint, rows = 5) =>
  `<label class="field"><span>${label} <small class="muted">${hint}</small></span><textarea name="${k}" rows="${rows}">${esc((b[k] || []).join("\n"))}</textarea></label>`;
const secKeys = b => (b.sections || []).flatMap(s => s.replace("?", "").split("|"));
const secLabel = s => s.replace("?", "").split("|").map(k => (BANK_LABELS[k] || [k])[0].split(" (")[0]).join(" / ") + (s.endsWith("?") ? " (opcjonalnie)" : "");

// Minimalny renderer markdownu kompendium: nagłówki, listy, tabele, cytaty, bloki kodu. Wszystko przez esc().
function renderMarkdown(md) {
  const inline = s => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>");
  const out = [];
  let code = null, table = null, list = null;
  const flush = () => {
    if (table) { out.push(`<table>${table.map((r, i) => `<tr>${r.map(c => i ? `<td>${inline(c)}</td>` : `<th>${inline(c)}</th>`).join("")}</tr>`).join("")}</table>`); table = null; }
    if (list) { out.push(`<${list.tag}>${list.items.map(x => `<li>${x}</li>`).join("")}</${list.tag}>`); list = null; }
  };
  for (const raw of md.split("\n")) {
    if (raw.startsWith("```")) { if (code) { out.push(`<pre>${esc(code.join("\n"))}</pre>`); code = null; } else { flush(); code = []; } continue; }
    if (code) { code.push(raw); continue; }
    const line = raw.trimEnd();
    if (/^\|.*\|$/.test(line)) { if (/^\|[\s:|-]+\|$/.test(line)) continue; const cells = line.slice(1, -1).split("|").map(c => c.trim()); (table ||= []).push(cells); continue; }
    const li = line.match(/^\s*(?:[-*]|(\d+)\.)\s+(.*)$/);
    if (li) { const tag = li[1] ? "ol" : "ul"; if (list && list.tag !== tag) flush(); if (table) flush(); (list ||= { tag, items: [] }).items.push(inline(li[2].replace(/^\[ \]\s*/, "☐ "))); continue; }
    flush();
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) out.push(`<h${h[1].length + 1}>${inline(h[2])}</h${h[1].length + 1}>`);
    else if (line.startsWith(">")) out.push(`<blockquote>${inline(line.replace(/^>\s?/, ""))}</blockquote>`);
    else if (line === "---") out.push("<hr>");
    else if (line) out.push(`<p>${inline(line)}</p>`);
  }
  flush();
  if (code) out.push(`<pre>${esc(code.join("\n"))}</pre>`);
  return out.join("");
}

let previewTimer;

export async function renderBrands() {
  const id = state.brand === "all" ? "atlet" : state.brand;
  const b = state.brands[id];
  const kw = (b.tag_mode || "hashtags") === "keywords";
  const banks = [...new Set([...secKeys(b), ...(b.scenes?.length ? ["scenes"] : [])])].filter(k => k !== "scene" && BANK_LABELS[k]);
  const v = $("#view");
  v.innerHTML = `
    <div class="brand-tabs segmented">${Object.values(state.brands).map(x => `<button type="button" data-b="${esc(x.id)}" class="${x.id === id ? "active" : ""}">${esc(x.name)}</button>`).join("")}</div>
    <section class="style-sec compendium" id="compendium"><h3>Kompendium stylu <small class="muted">jedyne źródło zasad dla ${esc(b.name)}</small></h3><p class="muted">Odczytuję…</p></section>
    <div class="style-layout">
      <form class="brand-form" id="brandForm">
        <section class="style-sec"><h3>1 · Tożsamość i ton</h3>
          <div class="two"><label class="field"><span>Nazwa</span><input name="name" value="${esc(b.name)}"></label><label class="field"><span>Profil</span><input name="handle" value="${esc(b.handle)}"></label></div>
          <label class="field"><span>Kim jest profil i jak mówi</span><textarea name="tone" rows="4">${esc(b.tone)}</textarea></label>
          ${area(b, "style_rules", "Kontrola przed oddaniem", "z kompendium; widoczna obok podglądu", 8)}
        </section>

        <section class="style-sec"><h3>2 · Budowa opisu <small class="muted">w tej kolejności składa się szkic</small></h3>
          <ol class="post-map">${(b.sections || []).map(s => `<li>${esc(secLabel(s))}</li>`).join("")}</ol>
          <label class="field"><span>Emoji haka <small class="muted">${b.hook_emojis?.length ? "dobierane na zmianę, to samo z obu stron" : "haki tej marki niosą własne emoji dobrane pod temat"}</small></span><input name="allowed_hook_emojis" value="${esc((b.allowed_hook_emojis || []).join(" "))}"></label>
          ${banks.map(k => area(b, k, ...BANK_LABELS[k], k === "hooks" ? 9 : 6)).join("")}
        </section>

        <section class="style-sec"><h3>3 · ${kw ? "Słowa kluczowe" : "Hashtagi"}</h3>
          <label class="field"><span>Tryb</span><select name="tag_mode"><option value="keywords" ${kw ? "selected" : ""}>Słowa kluczowe w opisie (bez #)</option><option value="hashtags" ${kw ? "" : "selected"}>Hashtagi</option></select></label>
          <div class="kw-only" ${kw ? "" : "hidden"}>${area(b, "keywords", "Słowa kluczowe", "fraza w linii; kontrola sprawdza, czy są w opisie", 5)}</div>
          <div class="tag-only grid-2" ${kw ? "hidden" : ""}>
            ${area(b, "fixed_hashtags", "Stałe hashtagi", "zawsze")}
            ${area(b, "rotating_hashtags", "Rotacyjne hashtagi", "wybierane po kolei")}
            <label class="field"><span>Ile rotacyjnych</span><input type="number" name="rotating_count" min="0" max="10" value="${b.rotating_count}"></label>
          </div>
        </section>

        <section class="style-sec"><h3>4 · Kontrola tekstu</h3>
          <div class="grid-2">
            ${area(b, "banned_words", "Zakazane (błąd)", "łapie też odmiany", 8)}
            ${area(b, "avoid_phrases", "Ogólniki / metafory spoza stylu (ostrzeżenie)", "fraza w linii", 8)}
          </div>
          <div class="three">
            <label class="field"><span>Opis min. znaków</span><input type="number" name="caption_min" min="0" value="${b.caption_min}"></label>
            <label class="field"><span>Opis maks. znaków</span><input type="number" name="caption_max" min="1" max="2200" value="${b.caption_max}"></label>
            <label class="field"><span>Max myślników „-”</span><input type="number" name="max_dashes" min="0" value="${b.max_dashes ?? ""}" placeholder="bez limitu"></label>
            <label class="field"><span>Max wykrzykników</span><input type="number" name="max_exclaims" min="0" value="${b.max_exclaims ?? ""}" placeholder="bez limitu"></label>
            <label class="field"><span>Zakazany zwrot do widza</span><input name="forbidden_address" value="${esc(b.forbidden_address || "")}" placeholder="brak"></label>
            <label class="field"><span>Wymagane słowo</span><input name="required_words" value="${esc((b.required_words || []).join(" "))}" placeholder="brak"></label>
          </div>
          <label class="check"><input type="checkbox" name="hook_no_question" ${b.hook_no_question ? "checked" : ""}> Hak nie może być pytaniem</label>
        </section>

        <section class="style-sec"><h3>5 · Publikacja</h3>
          <div class="grid-2">
            ${area(b, "locations", "Lokalizacje", "podpowiedzi w edytorze")}
            ${area(b, "posting_slots", "Godziny publikacji", "GG:MM, niepełne minuty")}
          </div>
          <fieldset class="field days"><legend>Dni publikacji</legend>${DAYS.map((d, i) => `<label><input type="checkbox" name="posting_days" value="${i}" ${(b.posting_days || []).includes(i) ? "checked" : ""}> ${d}</label>`).join("")}</fieldset>
        </section>

        <div class="actions style-save"><button class="btn primary" type="submit">Zapisz styl marki</button><span class="muted" id="dirty">Zapis lokalny (data/brands.json). Nie zmienia kolejki.</span></div>
      </form>

      <aside class="style-preview">
        <section class="card"><h3>Podgląd na żywo</h3>
          <label class="field"><span>Scena testowa <small class="muted">puste = scena z banku</small></span><input id="pvScene" value=""></label>
          <div id="pvDrafts" class="muted">Generuję…</div>
        </section>
        <section class="card"><h3>Sprawdź swój tekst</h3>
          <textarea id="pvSample" rows="7" placeholder="Wklej opis, kontrola pokaże uwagi według kompendium"></textarea>
          <ul class="lint" id="pvLint"></ul>
        </section>
        <section class="card"><h3>Kontrola przed oddaniem</h3><ul class="rules" id="pvRules"></ul></section>
        <section class="card"><h3>Pełny Generator opisów</h3><p class="muted">Stary Generator (8765) pisze do tej samej kolejki Studio.</p><button class="btn ghost" type="button" id="generator" ${guarded("legacy")}>Otwórz Generator ${esc(b.name)}</button></section>
        <section class="card"><h3>Wzorce stylu</h3><p class="muted">Powstają, gdy akceptujesz zmieniony opis. Widoczne i odwracalne w panelu Uczenie.</p><div id="examples" class="muted">Odczytuję…</div></section>
      </aside>
    </div>`;

  const form = $("#brandForm");
  const collect = () => {
    const f = new FormData(form), patch = {};
    ["name", "handle", "tone", "tag_mode", "forbidden_address"].forEach(k => patch[k] = f.get(k) || "");
    [...banks, "style_rules", "keywords", "fixed_hashtags", "rotating_hashtags", "banned_words", "avoid_phrases", "locations", "posting_slots"].forEach(k => patch[k] = lines(f.get(k)));
    patch.allowed_hook_emojis = String(f.get("allowed_hook_emojis") || "").split(/\s+/).filter(Boolean);
    if ((b.hook_emojis || []).length) patch.hook_emojis = patch.allowed_hook_emojis;
    patch.required_words = String(f.get("required_words") || "").split(/\s+/).filter(Boolean);
    ["caption_min", "caption_max", "rotating_count"].forEach(k => patch[k] = Number(f.get(k)));
    ["max_dashes", "max_exclaims"].forEach(k => patch[k] = f.get(k) === "" ? null : Number(f.get(k)));
    patch.hook_no_question = f.get("hook_no_question") === "on";
    patch.posting_days = f.getAll("posting_days").map(Number);
    return patch;
  };

  const refresh = async () => {
    const patch = collect();
    $("#pvRules").innerHTML = patch.style_rules.map(r => `<li>${esc(r)}</li>`).join("") || `<li class="muted">Brak zasad.</li>`;
    try {
      const r = await post(`/api/brands/${id}/preview`, { patch, topic: $("#pvScene").value, sample: $("#pvSample").value });
      $("#pvDrafts").className = "";
      $("#pvDrafts").innerHTML = r.drafts.map(d => `<article class="draft"><header><b>Szkic ${d.variant}</b><small class="muted">${d.description.length} znaków</small></header><p>${esc(d.description)}</p>${d.hashtags ? `<small class="tags">${esc(d.hashtags)}</small>` : ""}${d.lint.length ? `<ul class="lint">${d.lint.map(n => `<li class="${esc(n.level)}">${esc(n.text)}</li>`).join("")}</ul>` : `<small class="ok-note">Zgodny z kompendium.</small>`}</article>`).join("");
      $("#pvLint").innerHTML = r.sample_lint.map(n => `<li class="${esc(n.level)}">${esc(n.text)}</li>`).join("") || ($("#pvSample").value.trim() ? `<li class="info">Bez uwag. Tekst zgodny z kompendium.</li>` : "");
    } catch (err) { $("#pvDrafts").className = "bad"; $("#pvDrafts").textContent = err.message; }
  };
  const schedule = () => { $("#dirty").textContent = "Niezapisane zmiany. Podgląd już je pokazuje."; clearTimeout(previewTimer); previewTimer = setTimeout(refresh, 350); };

  const drawCompendium = c => {
    const box = $("#compendium");
    box.innerHTML = `<h3>Kompendium stylu <small class="muted">jedyne źródło zasad dla ${esc(b.name)}</small></h3>
      ${c.markdown ? `<p class="muted">${esc(c.version)} · plik ${esc(c.file)}${c.source ? ` · źródło: ${esc(c.source)}` : ""}</p>
        ${c.source_newer ? `<p class="note">W folderze źródłowym jest inna wersja tego pliku. <button class="btn primary small" type="button" id="reimport">Wczytaj nową wersję</button></p>` : ""}
        <details><summary>Pokaż całe kompendium</summary><div class="md">${renderMarkdown(c.markdown)}</div></details>`
      : `<p class="bad">Brak pliku kompendium w appce (${esc(c.file || "nie ustawiono")}).</p>`}`;
    if ($("#reimport")) $("#reimport").onclick = e => run(e.currentTarget, async () => drawCompendium(await post(`/api/brands/${id}/compendium/reimport`)),
      "Kompendium zaktualizowane. Jeśli zmieniły się zasady, poproś o przeniesienie ich do banków i kontroli.");
  };

  form.addEventListener("input", schedule);
  form.tag_mode.onchange = () => {
    const isKw = form.tag_mode.value === "keywords";
    $(".kw-only", v).hidden = !isKw; $(".tag-only", v).hidden = isKw;
    schedule();
  };
  $("#pvScene").oninput = schedule;
  $("#pvSample").oninput = schedule;
  $$("[data-b]", v).forEach(x => x.onclick = () => { state.brand = x.dataset.b; document.dispatchEvent(new CustomEvent("byku:brand")); });
  form.onsubmit = e => {
    e.preventDefault();
    const patch = collect();
    const bad = patch.posting_slots.find(s => !/^\d{2}:\d{2}$/.test(s));
    if (bad) return run(null, async () => { throw new Error(`Zła godzina: ${bad}. Format GG:MM.`); });
    run(e.submitter, async () => { const r = await post(`/api/brands/${id}`, patch); state.brands[id] = r; renderBrands(); }, "Styl marki zapisany.");
  };
  $("#generator").onclick = e => run(e.currentTarget, () => post("/api/generator/open", { brand: id }), "Generator uruchomiony i podłączony do wspólnej kolejki.");
  refresh();
  api(`/api/brands/${id}/compendium`).then(drawCompendium).catch(err => { $("#compendium").innerHTML = `<p class="bad">${esc(err.message)}</p>`; });
  try {
    const ex = await api(`/api/brands/${id}/style`);
    const box = $("#examples");
    if (box) box.innerHTML = ex.examples.length ? ex.examples.map(x => `<blockquote><small>v${x.version} · ${esc(x.post_id)}</small>${esc(x.after.slice(0, 220))}</blockquote>`).join("") : "Brak zaakceptowanych wzorców.";
  } catch (err) { const box = $("#examples"); if (box) box.textContent = err.message; }
}
