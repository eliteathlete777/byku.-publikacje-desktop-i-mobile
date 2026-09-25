// Marki i styl: ton, haki, CTA, hashtagi, lokalizacje, limity, sloty, wzorce stylu, pełny Generator.
import { $, $$, api, post, esc, state, run, guarded } from "../core.js";

const LISTS = [
  ["hooks", "Haki otwierające", "Jeden hak w linii"],
  ["ctas", "Zakończenia / pytania", "Jedno zakończenie w linii"],
  ["fixed_hashtags", "Stałe hashtagi", "Zawsze w opisie"],
  ["rotating_hashtags", "Rotacyjne hashtagi", "Wybierane po kolei"],
  ["banned_words", "Zakazane słowa", "Kontrola opisu je wyłapie"],
  ["locations", "Lokalizacje", "Podpowiedzi w edytorze"],
  ["posting_slots", "Godziny publikacji", "GG:MM, jedna w linii"]
];
const DAYS = ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"];

export async function renderBrands() {
  const id = state.brand === "all" ? "atlet" : state.brand;
  const b = state.brands[id];
  const v = $("#view");
  v.innerHTML = `
    <div class="brand-tabs segmented">${Object.values(state.brands).map(x => `<button type="button" data-b="${esc(x.id)}" class="${x.id === id ? "active" : ""}">${esc(x.name)}</button>`).join("")}</div>
    <div class="brand-layout">
      <form class="brand-form" id="brandForm">
        <div class="two"><label class="field"><span>Nazwa</span><input name="name" value="${esc(b.name)}"></label><label class="field"><span>Profil</span><input name="handle" value="${esc(b.handle)}"></label></div>
        <label class="field"><span>Ton komunikacji</span><textarea name="tone" rows="3">${esc(b.tone)}</textarea></label>
        <div class="grid-2">${LISTS.map(([k, n, hint]) => `<label class="field"><span>${n} <small class="muted">${hint}</small></span><textarea name="${k}" rows="4">${esc((b[k] || []).join("\n"))}</textarea></label>`).join("")}</div>
        <div class="three">
          <label class="field"><span>Opis min. znaków</span><input type="number" name="caption_min" min="0" value="${b.caption_min}"></label>
          <label class="field"><span>Opis maks. znaków</span><input type="number" name="caption_max" min="1" max="2200" value="${b.caption_max}"></label>
          <label class="field"><span>Ile rotacyjnych</span><input type="number" name="rotating_count" min="0" max="10" value="${b.rotating_count}"></label>
        </div>
        <fieldset class="field days"><legend>Dni publikacji</legend>${DAYS.map((d, i) => `<label><input type="checkbox" name="posting_days" value="${i}" ${(b.posting_days || []).includes(i) ? "checked" : ""}> ${d}</label>`).join("")}</fieldset>
        <div class="actions"><button class="btn primary" type="submit">Zapisz profil marki</button><span class="muted">Zapis lokalny (data/brands.json). Nie zmienia kolejki.</span></div>
      </form>
      <aside class="brand-side">
        <section class="card"><h3>Pełny Generator opisów</h3><p class="muted">Stary Generator (8765) pisze do tej samej kolejki Studio.</p><button class="btn ghost" type="button" id="generator" ${guarded("legacy")}>Otwórz Generator ${esc(b.name)}</button></section>
        <section class="card"><h3>Wzorce stylu</h3><p class="muted">Powstają, gdy akceptujesz zmieniony opis. Widoczne i odwracalne w panelu Uczenie.</p><div id="examples" class="muted">Odczytuję…</div></section>
        <section class="card"><h3>Podgląd hashtagów</h3><p class="tags">${esc([...(b.fixed_hashtags || []), ...(b.rotating_hashtags || []).slice(0, b.rotating_count)].join(" "))}</p></section>
      </aside>
    </div>`;
  $$("[data-b]", v).forEach(x => x.onclick = () => { state.brand = x.dataset.b; document.dispatchEvent(new CustomEvent("byku:brand")); });
  $("#brandForm").onsubmit = e => {
    e.preventDefault();
    const f = new FormData(e.target), patch = {};
    ["name", "handle", "tone"].forEach(k => patch[k] = f.get(k));
    LISTS.forEach(([k]) => patch[k] = String(f.get(k) || "").split("\n").map(x => x.trim()).filter(Boolean));
    ["caption_min", "caption_max", "rotating_count"].forEach(k => patch[k] = Number(f.get(k)));
    patch.posting_days = f.getAll("posting_days").map(Number);
    const bad = patch.posting_slots.find(s => !/^\d{2}:\d{2}$/.test(s));
    if (bad) return run(null, async () => { throw new Error(`Zła godzina: ${bad}. Format GG:MM.`); });
    run(e.submitter, async () => { const r = await post(`/api/brands/${id}`, patch); state.brands[id] = r; renderBrands(); }, "Profil marki zapisany.");
  };
  $("#generator").onclick = e => run(e.currentTarget, () => post("/api/generator/open", { brand: id }), "Generator uruchomiony i podłączony do wspólnej kolejki.");
  try {
    const ex = await api(`/api/brands/${id}/style`);
    const box = $("#examples");
    if (box) box.innerHTML = ex.examples.length ? ex.examples.map(x => `<blockquote><small>v${x.version} · ${esc(x.post_id)}</small>${esc(x.after.slice(0, 220))}</blockquote>`).join("") : "Brak zaakceptowanych wzorców.";
  } catch (err) { const box = $("#examples"); if (box) box.textContent = err.message; }
}
