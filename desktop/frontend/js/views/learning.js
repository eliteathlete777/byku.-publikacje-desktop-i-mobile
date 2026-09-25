// Uczenie: lekcje stylu/procesu/kodu z testem, aktywacją i cofaniem + dziennik zdarzeń.
import { $, $$, api, post, esc, state, run, modal } from "../core.js";

const KIND = { style: "Styl", process: "Proces", code: "Propozycja kodu" };
const STATUS = { draft: "Szkic", active: "Aktywna", reverted: "Cofnięta", rejected: "Odrzucona" };

export async function renderLearning() {
  const v = $("#view");
  const data = await api("/api/learning");
  if (state.view !== "learning") return;
  const testOf = l => { try { return JSON.parse(l.test_json || "{}"); } catch { return {}; } };
  v.innerHTML = `
    <div class="actions"><button class="btn primary" type="button" id="newLesson">Dodaj lekcję</button><span class="muted">Lekcja działa dopiero po teście i aktywacji. Każdą można cofnąć.</span></div>
    <div class="learning-layout">
      <section><h2>Lekcje</h2>${data.lessons.map(l => { const t = testOf(l); return `
        <article class="lesson ${esc(l.status)}">
          <header><b>${esc(KIND[l.kind] || l.kind)} · ${esc((l.brand || "wszystkie marki").toUpperCase())} · v${l.version}</b><span class="pill ${l.status === "active" ? "published" : l.status === "draft" ? "wait" : "idle"}">${esc(STATUS[l.status] || l.status)}</span></header>
          <p><b>Problem:</b> ${esc(l.problem)}</p><p><b>Rozwiązanie:</b> ${esc(l.solution || "—")}</p>
          <small class="muted">Test: ${esc(t.status || t.type || "brak")}${t.note ? ` — ${esc(t.note)}` : ""}</small>
          <div class="actions">
            ${l.status === "draft" ? `<button class="btn ghost small" type="button" data-test="${l.lesson_id}">Zapisz wynik testu</button><button class="btn primary small" type="button" data-status="active" data-id="${l.lesson_id}">Aktywuj</button><button class="btn ghost small" type="button" data-status="rejected" data-id="${l.lesson_id}">Odrzuć</button>` : ""}
            ${l.status === "active" ? `<button class="btn ghost small" type="button" data-status="reverted" data-id="${l.lesson_id}">Cofnij</button>` : ""}
            ${["reverted", "rejected"].includes(l.status) ? `<button class="btn ghost small" type="button" data-status="draft" data-id="${l.lesson_id}">Przywróć do szkicu</button>` : ""}
          </div>
        </article>`; }).join("") || `<div class="empty">Brak lekcji.</div>`}</section>
      <section><h2>Dziennik zdarzeń</h2><ol class="timeline">${data.events.slice(0, 60).map(e => `<li><b>${esc(e.stage)}</b><small>${esc(e.occurred_at)} · ${esc((e.brand || "").toUpperCase())} ${esc(e.post_id || "")}</small><span>${esc(e.result || "")}</span></li>`).join("") || `<li class="muted">Brak zdarzeń.</li>`}</ol></section>
    </div>`;
  $("#newLesson").onclick = () => modal(`<h2>Nowa lekcja</h2><form id="lessonForm" class="stack">
      <div class="two"><label class="field"><span>Rodzaj</span><select name="kind"><option value="process">Proces</option><option value="style">Styl</option><option value="code">Propozycja kodu</option></select></label>
      <label class="field"><span>Marka</span><select name="brand"><option value="">Wszystkie</option><option value="atlet">ATLET</option><option value="rigger">RIGGER</option></select></label></div>
      <label class="field"><span>Potwierdzony problem</span><textarea name="problem" rows="3" required></textarea></label>
      <label class="field"><span>Rozwiązanie</span><textarea name="solution" rows="3" required></textarea></label>
      <label class="field"><span>Dowód (skąd wiesz)</span><input name="evidence" placeholder="np. log z 24.09, zrzut ekranu"></label>
      <div class="actions end"><button class="btn primary" type="submit">Zapisz jako szkic</button></div></form>`, dlg => {
    $("#lessonForm", dlg).onsubmit = e => {
      e.preventDefault(); const f = new FormData(e.target);
      run(e.submitter, async () => { await post("/api/learning/lessons", { kind: f.get("kind"), brand: f.get("brand") || null, problem: f.get("problem"), solution: f.get("solution"), evidence: [f.get("evidence") || "obserwacja użytkownika"] }); dlg.close(); await renderLearning(); }, "Lekcja zapisana jako szkic.");
    };
  });
  $$("[data-test]", v).forEach(b => b.onclick = () => modal(`<h2>Wynik testu</h2><form id="testForm" class="stack"><label class="field"><span>Wynik</span><select name="status"><option value="ok">OK — rozwiązanie działa</option><option value="failed">Nie działa</option></select></label><label class="field"><span>Notatka</span><input name="note" placeholder="Co i jak sprawdzono"></label><div class="actions end"><button class="btn primary" type="submit">Zapisz</button></div></form>`, dlg => {
    $("#testForm", dlg).onsubmit = e => { e.preventDefault(); const f = new FormData(e.target); run(e.submitter, async () => { await post(`/api/learning/lessons/${b.dataset.test}/test`, { status: f.get("status"), note: f.get("note") }); dlg.close(); await renderLearning(); }, "Wynik testu zapisany."); };
  }));
  $$("[data-status]", v).forEach(b => b.onclick = e => run(e.currentTarget, async () => { await post(`/api/learning/lessons/${b.dataset.id}/status`, { status: b.dataset.status }); await renderLearning(); }, `Status: ${STATUS[b.dataset.status]}.`));
}
