// Transfer TikTok → paczka → telefon → Instagram.
import { $, $$, api, post, pub, esc, state, run, toast, thumb, fmtTerm, guarded, blockReason } from "../core.js";
import { openCard } from "../drawer.js";

export async function renderTransfer() {
  const v = $("#view");
  v.innerHTML = `<div class="loading">Wyszukuję materiały: TikTok gotowy, Instagram czeka…</div>`;
  const brand = state.brand;
  let data;
  try { data = await api(`/api/mobile-candidates?brand=${brand}`); } catch (e) { v.innerHTML = `<div class="alert">${esc(e.message)}</div>`; return; }
  if (state.view !== "transfer") return;
  const drive = data.drive, server = data.server;
  v.innerHTML = `
    <section class="pipeline">
      <div><b>1 · TikTok</b><small>opublikowany lub zaplanowany</small></div>
      <div><b>2 · Paczka</b><small>plik, miniatura, opis, hashtagi, SHA-256</small></div>
      <div class="${drive.available ? "ok" : "warn"}"><b>3a · Google Drive</b><small>${drive.available ? esc(drive.path) : "folder nieustawiony"}</small></div>
      <div class="${server.configured && server.token ? "ok" : "warn"}"><b>3b · Serwer telefonu</b><small>${server.configured ? esc(server.url) : "adres nieustawiony"}${server.configured && !server.token ? " · brak tokenu" : ""}</small></div>
      <div><b>4 · Instagram</b><small>publikujesz ręcznie z telefonu</small></div>
    </section>
    <div class="actions">
      <button class="btn primary" type="button" id="exportAll" ${data.items.length ? "" : "disabled title=\"Brak kandydatów\""}>Przygotuj wszystkie paczki (${data.items.length})</button>
      <button class="btn ghost" type="button" id="sendAll" ${data.items.length ? guarded("server") : "disabled"}>Wyślij wszystkie na telefon</button>
      <button class="btn ghost" type="button" id="pull" ${guarded("server")}>Pobierz zgłoszenia z telefonu</button>
    </div>
    <div class="table transfer"><div class="thead"><span>Materiał</span><span>TikTok</span><span>Paczka</span><span>Drive</span><span>Telefon</span><span>Akcje</span></div>
    <div class="tbody">${data.items.map(c => { const t = c.transfer || {}; const fresh = t.revision === c.content.revision; return `
      <article class="row" data-id="${esc(c.post_id)}">
        <div class="material">${thumb(c)}<div><b>${esc(c.name)}</b><small>${esc(c.brand.toUpperCase())} · ${esc(fmtTerm(c.local_target_at))}</small></div></div>
        <div class="cell"><span class="pill ${c.tiktok_transfer === "published" ? "published" : "scheduled"}">${esc({ published: "Opublikowany", scheduled: "Zaplanowany", manual_checked: "Oznaczony ręcznie" }[c.tiktok_transfer])}</span></div>
        <div class="cell">${fresh ? `<span class="pill published">Gotowa</span><small>${esc(t.exported_at || "")}</small>` : t.revision ? `<span class="pill wait">Stara wersja</span>` : `<span class="pill idle">Brak</span>`}</div>
        <div class="cell">${fresh && t.drive_at ? `<span class="pill published">Na Dysku</span><small>${esc(t.drive_at)}</small>` : `<span class="pill idle">—</span>`}</div>
        <div class="cell">${fresh && t.server_at ? `<span class="pill published">Wysłano</span><small>${esc(t.server_at)}</small>` : `<span class="pill idle">—</span>`}</div>
        <div class="next row-actions">
          <button class="btn ghost small" type="button" data-act="export">Paczka</button>
          <button class="btn ghost small" type="button" data-act="drive" ${fresh ? guarded("drive") : 'disabled title="Najpierw paczka"'}>Drive</button>
          <button class="btn ghost small" type="button" data-act="server" ${fresh ? guarded("server") : 'disabled title="Najpierw paczka"'}>Telefon</button>
          <button class="btn ghost small" type="button" data-act="open">Szczegóły</button>
        </div>
      </article>`; }).join("") || `<div class="empty">Brak materiałów w stanie „TikTok gotowy — Instagram czeka”.</div>`}</div></div>
    ${blockReason("server") ? `<p class="note">Wysyłka na telefon: ${esc(blockReason("server"))} Instrukcja: <code>desktop/README.md</code> → „Serwer telefonu”.</p>` : ""}`;
  const act = { export: id => post(`${pub(id)}/phone-package`, { channel: "instagram" }), drive: id => post(`${pub(id)}/to-drive`), server: id => post(`${pub(id)}/to-server`) };
  $$("[data-act]", v).forEach(b => b.onclick = e => {
    const id = b.closest(".row").dataset.id;
    if (b.dataset.act === "open") return openCard(id, "phone");
    run(e.currentTarget, async () => { await act[b.dataset.act](id); await renderTransfer(); }, { export: "Paczka gotowa.", drive: "Skopiowano na Google Drive.", server: "Wysłano na telefon." }[b.dataset.act]);
  });
  $("#exportAll").onclick = e => bulk(e.currentTarget, data.items, ["export"]);
  $("#sendAll").onclick = e => bulk(e.currentTarget, data.items, ["export", "server"]);
  $("#pull").onclick = e => run(e.currentTarget, () => post("/api/mobile-events/pull"), r => `Zgłoszenia z telefonu: nowe ${r.accepted}, pominięte ${r.skipped}.`);

  async function bulk(button, items, steps) {
    let ok = 0; const failed = [];
    await run(button, async () => {
      for (const c of items) {
        button.textContent = `Przetwarzam ${ok + failed.length + 1}/${items.length}…`;
        try { for (const s of steps) await act[s](c.post_id); ok++; } catch (e) { failed.push(`${c.name}: ${e.message}`); }
      }
    });
    toast(failed.length ? `Gotowe ${ok}, błędy ${failed.length}: ${failed[0]}` : `Gotowe: ${ok} paczek.`, failed.length ? "error" : "ok");
    await renderTransfer();
  }
}
