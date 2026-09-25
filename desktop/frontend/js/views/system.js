// System: tryb, blokady bezpieczeństwa, rdzeń, Drive, serwer telefonu, zadania i blokady profili.
import { $, $$, api, post, esc, state, run } from "../core.js";

const yes = (ok, a = "Tak", b = "Nie") => `<span class="pill ${ok ? "published" : "wait"}">${ok ? a : b}</span>`;

export async function renderSystem() {
  const h = state.health || {};
  let jobs = { jobs: [], locks: [] };
  try { jobs = await api("/api/jobs"); } catch { /* panel pokaże pustą listę */ }
  if (state.view !== "system") return;
  $("#view").innerHTML = `
    <div class="sys-grid">
      <section class="card"><h3>Tryb pracy</h3><dl class="facts">
        <div><dt>Tryb</dt><dd>${esc(h.mode)} · v${esc(h.version)}</dd></div>
        <div><dt>Kolejka</dt><dd class="mono">${esc(h.queue)}</dd></div>
        <div><dt>Zapis do kolejki</dt><dd>${yes(h.writes, "Włączony", "Zablokowany")}</dd></div>
        <div><dt>Publikowanie</dt><dd>${yes(h.publication, "Włączone", "Zablokowane")}</dd></div>
        <div><dt>Końcowe kliknięcie</dt><dd>Zawsze ręczne</dd></div></dl>
        <p class="note">Przełączniki <code>allow_production_writes</code> i <code>allow_publication</code> zmienia wyłącznie właściciel w <code>config.json</code>. Panel ich nie przełącza.</p></section>
      <section class="card"><h3>Rdzeń magazynu</h3><dl class="facts">
        <div><dt>Rdzeń</dt><dd>${esc(h.core || "brak")}</dd></div>
        <div><dt>BYQ Studio (uploadery, Generator)</dt><dd>${yes(h.legacy, "Podłączony", "Niedostępny")}</dd></div>
        ${h.core_error ? `<div><dt>Błąd</dt><dd class="bad">${esc(h.core_error)}</dd></div>` : ""}</dl></section>
      <section class="card"><h3>Google Drive</h3><dl class="facts">
        <div><dt>Folder synchronizowany</dt><dd class="mono">${esc(h.drive?.path || "nieustawiony")}</dd></div>
        <div><dt>Dostępny</dt><dd>${yes(h.drive?.available)}</dd></div>
        <div><dt>Root / ATLET / RIGGER</dt><dd class="mono small">${esc(Object.values(h.drive?.folder_ids || {}).join(" · "))}</dd></div></dl></section>
      <section class="card"><h3>Serwer telefonu</h3><dl class="facts">
        <div><dt>Adres</dt><dd class="mono">${esc(h.mobile_server?.url || "nieustawiony")}</dd></div>
        <div><dt>Token w .env</dt><dd>${yes(h.mobile_server?.token, "Jest", "Brak")}</dd></div></dl></section>
    </div>
    <section class="card"><h3>Zadania publikacji</h3>${jobs.jobs.length ? `<ol class="timeline">${jobs.jobs.map(j => `<li><b>${esc(j.post_id)} · ${esc(j.channel)}</b><small>${esc(j.state)} · ${esc(j.stage)}</small>${["queued", "running", "verifying"].includes(j.state) ? `<button class="btn ghost small" type="button" data-release="${esc(j.job_id)}">Zwolnij profil</button>` : ""}</li>`).join("")}</ol>` : `<p class="muted">Brak zadań.</p>`}
      <h3>Blokady profili przeglądarki</h3>${jobs.locks.length ? `<ul>${jobs.locks.map(l => `<li class="mono">${esc(l.resource)} — ${esc(l.post_id || l.error)}</li>`).join("")}</ul>` : `<p class="muted">Wszystkie profile wolne.</p>`}</section>
    ${state.errors.length ? `<section class="card"><h3>Paczki nieodczytane</h3><ul>${state.errors.map(e => `<li><b>${esc(e.post_id)}</b> — ${esc(e.error)}</li>`).join("")}</ul></section>` : ""}`;
  $$("[data-release]").forEach(b => b.onclick = e => run(e.currentTarget, async () => { await post(`/api/jobs/${b.dataset.release}/release`, { result: "interrupted" }); await renderSystem(); }, "Profil zwolniony. Zadanie oznaczone jako przerwane."));
}
