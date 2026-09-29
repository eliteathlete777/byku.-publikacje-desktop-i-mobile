// Studio miniatury — te same funkcje co panel MINIATURKA w starym Generatorze:
// klatka z filmu (suwak), kadr (zoom suwakiem i kółkiem, przesuwanie, reset), do 3 napisów
// (tekst, pozycja, wielkość, obrót, kolor, efekt, przeciąganie po kadrze),
// „1 góra + 2 dół”, reset pozycji, pobranie PNG i zapis do paczki.
// Ustawienia każdej karty zostają w przeglądarce — po ponownym otwarciu wracasz do tego samego.
import { $, $$, esc, pub, modal, run, toast, markWatched } from "./core.js";

// Jedna czcionka na wszystkich miniaturach (Damian 29.09): Anton — ta z poprzednich miniatur Generatora.
export const FONT = "'Anton',sans-serif";
export const COLOR_SWATCHES = [["#e5262b", "Czerwony"], ["#ff6b1a", "Pomarańcz"], ["#ffffff", "Biały"], ["#ffe566", "Żółty"], ["#111111", "Grafit"]];
const EFFECTS = [["bar", "Belka + kontrast"], ["invert", "Odwrócone"], ["stroke", "Kontur"]];
const RATIOS = [["4:5", 4 / 5], ["9:16", 9 / 16], ["1:1", 1]];
const W = 756;             // podgląd jak w Generatorze (1080 × 0,7); zapis w pełnej rozdzielczości 1080
const OUT_W = 1080;
const RESET = { zoom: 1.15, x: 0, y: 40 };

const newLayer = pos => ({ text: "", pos, size: 46, color: "#e5262b", font: FONT, rotate: 0, x: null, y: null, effect: "bar" });
const prefKey = id => `byku.desktop.thumb.${id}`;
function loadPrefs(id) { try { return JSON.parse(localStorage.getItem(prefKey(id)) || "null"); } catch { return null; } }
function savePrefs(id, s) {
  try { localStorage.setItem(prefKey(id), JSON.stringify({ ratio: s.ratio, zoom: s.zoom, x: s.x, y: s.y, t: s.t, source: s.source, layers: s.layers.map(({ _anchor, ...l }) => l) })); } catch { /* brak pamięci przeglądarki */ }
}

function contrastInk(hex) {
  const h = (hex || "#fff").replace("#", "");
  const n = h.length === 3 ? [...h].map(c => c + c).join("") : h;
  const r = parseInt(n.slice(0, 2), 16), g = parseInt(n.slice(2, 4), 16), b = parseInt(n.slice(4, 6), 16);
  return 0.299 * r + 0.587 * g + 0.114 * b > 160 ? "#111111" : "#ffffff";
}

function wrapText(ctx, text, maxW) {
  const lines = []; let cur = "";
  text.split(" ").forEach(w => {
    const test = cur ? `${cur} ${w}` : w;
    if (ctx.measureText(test).width > maxW && cur) { lines.push(cur); cur = w; } else cur = test;
  });
  if (cur) lines.push(cur);
  return lines;
}

/** Otwiera studio. `c` = karta; `opts.file` = obraz z dysku jako źródło (opcjonalnie). */
export function openThumbStudio(c, opts = {}, onSaved = async () => {}) {
  const video = c.assets.type === "carousel" ? "" : (c.assets.media_urls || [])[0] || "";
  const slide = c.assets.type === "carousel" ? (c.assets.media_urls || [])[0] || "" : "";
  const saved = loadPrefs(c.post_id);
  const s = {
    ratio: saved?.ratio || "4:5", zoom: saved?.zoom ?? RESET.zoom, x: saved?.x ?? RESET.x, y: saved?.y ?? RESET.y,
    t: saved?.t ?? 0, layers: saved?.layers || [],
    source: opts.file ? "file" : saved?.source && saved.source !== "file" ? saved.source : video ? "video" : slide ? "slide" : "current"
  };
  if (s.source === "video" && !video) s.source = slide ? "slide" : "current";
  let fileUrl = opts.file ? URL.createObjectURL(opts.file) : "";
  const H = () => Math.round(W / RATIOS.find(([k]) => k === s.ratio)[1]);

  const dlg = modal(`
    <h2>Miniatura — ${esc(c.name.replace(/\.[^.]+$/, ""))}</h2>
    <div class="ts">
      <section class="ts-col">
        <h3>Źródło</h3>
        <div class="seg ts-src">
          ${video ? `<button type="button" data-src="video">Klatka z filmu</button>` : ""}
          ${slide ? `<button type="button" data-src="slide">Pierwszy slajd</button>` : ""}
          ${c.assets.thumbnail_url ? `<button type="button" data-src="current">Obecna miniatura</button>` : ""}
          <button type="button" data-src="file">Z pliku…</button>
        </div>
        <input type="file" id="tsFile" accept="image/*" hidden>
        <div id="tsVideoBox" ${video ? "" : "hidden"}>
          <video id="tsVideo" controls muted playsinline preload="auto" src="${esc(video)}"></video>
          <label class="ts-field"><span>Klatka</span><input type="range" id="tsScrub" min="0" max="1000" value="0"></label>
          <p class="muted small" id="tsVideoHint">Odtwórz albo przesuń suwak — klatka od razu ląduje w miniaturze.</p>
        </div>
      </section>
      <section class="ts-col ts-stage">
        <h3>Miniaturka</h3>
        <canvas id="tsCanvas" width="${W}" height="${H()}"></canvas>
        <p class="muted small">Kółko = zoom. Puste miejsce = przesuń kadr. Napis = przesuń tekst.</p>
        <div class="seg" id="tsRatio">${RATIOS.map(([k]) => `<button type="button" data-r="${k}">${k}</button>`).join("")}</div>
        <label class="ts-field"><span>Kadr (twarz)</span><input type="range" id="tsZoom" min="100" max="250"></label>
        <div class="actions"><button type="button" class="btn ghost small" id="tsResetCrop">Reset kadru</button>
          <button type="button" class="btn ghost small" id="tsPng">PNG</button></div>
      </section>
      <section class="ts-col">
        <h3>Napisy</h3>
        <button type="button" class="btn primary small" id="tsAdd"></button>
        <div id="tsLayers"></div>
        <div class="actions" id="tsLayerTools"><button type="button" class="btn ghost small" id="tsLayout">1 góra + 2 dół</button>
          <button type="button" class="btn ghost small" id="tsResetPos">Reset pozycji</button></div>
      </section>
    </div>
    <div class="actions end">
      <button class="btn ghost" id="tsCancel" type="button">Anuluj</button>
      <button class="btn primary" id="tsSave" type="button">Zapisz miniaturę</button>
    </div>`, d => {
    d.classList.add("wide");
    d.addEventListener("close", () => { d.classList.remove("wide"); if (fileUrl) URL.revokeObjectURL(fileUrl); savePrefs(c.post_id, s); }, { once: true });
  });

  const canvas = $("#tsCanvas", dlg), ctx = canvas.getContext("2d"), vid = $("#tsVideo", dlg);
  const img = new Image();
  let srcReady = false;
  // HEVC (H.265) z telefonu: przeglądarka często zna długość, ale nie rysuje obrazu (videoWidth = 0).
  // Wtedy klatkę pod suwak wycina serwer panelu (ffmpeg) — /frame?t=.
  const frame = new Image();
  let serverFrames = false, frameReady = false, frameTimer = null;
  function loadServerFrame(t) {
    clearTimeout(frameTimer);
    frameTimer = setTimeout(() => {
      frame.onload = () => { frameReady = true; redraw(); };
      frame.onerror = () => toast("Serwer nie wyciął klatki z filmu.", "error");
      frame.src = `${pub(c.post_id)}/frame?t=${(t || 0).toFixed(2)}`;
    }, 180);
  }
  function useServerFrames() {
    if (serverFrames) return;
    serverFrames = true;
    $("#tsVideoHint", dlg).textContent = "Ta przeglądarka nie pokazuje obrazu tego filmu (HEVC) — klatki wycina serwer panelu. Przesuń suwak albo zatrzymaj odtwarzanie w wybranym miejscu.";
    loadServerFrame(s.t);
  }

  // ---------- rysowanie (ta sama logika co Generator; k = skala zapisu) ----------
  function sourceEl() {
    if (s.source === "video") {
      if (serverFrames) return frameReady ? [frame, frame.naturalWidth, frame.naturalHeight] : null;
      return vid.readyState >= 2 && vid.videoWidth ? [vid, vid.videoWidth, vid.videoHeight] : null;
    }
    return srcReady && img.naturalWidth ? [img, img.naturalWidth, img.naturalHeight] : null;
  }
  function paint(target = ctx, k = 1) {
    const cw = W, ch = H();
    target.save(); target.scale(k, k);
    target.fillStyle = "#0c0d0e"; target.fillRect(0, 0, cw, ch);
    const src = sourceEl();
    if (src) {
      const [el, sw, sh] = src;
      const scale = Math.max(cw / sw, ch / sh) * Math.max(1, s.zoom);
      const dw = sw * scale, dh = sh * scale;
      target.drawImage(el, (cw - dw) / 2 + s.x, (ch - dh) / 2 + s.y, dw, dh);
    }
    const offset = { top: 0, mid: 0, bottom: 0 };
    s.layers.forEach(t => {
      const text = (t.text || "").trim().toUpperCase();
      t._anchor = null;
      if (!text) return;
      target.font = `900 ${t.size}px ${FONT}`;
      target.textAlign = "center"; target.textBaseline = "alphabetic";
      const lines = wrapText(target, text, cw - 126);
      const lh = t.size * 1.22, blockH = (lines.length - 1) * lh;
      let ax, ay;
      if (t.x !== null) { ax = t.x; ay = t.y; }
      else {
        ax = cw / 2;
        const extra = offset[t.pos];
        ay = t.pos === "top" ? 36 + t.size + extra : t.pos === "mid" ? ch / 2 - blockH / 2 + extra : ch - 36 - extra - blockH;
        offset[t.pos] += lines.length * lh + 10;
      }
      t._anchor = { x: ax, y: ay };
      target.save();
      target.translate(ax, ay - blockH / 2);
      target.rotate((t.rotate || 0) * Math.PI / 180);
      lines.forEach((line, i) => {
        const ly = i * lh, tw = target.measureText(line).width;
        const padX = t.size * 0.22, padY = t.size * 0.16;
        const bx = -tw / 2 - padX, by = ly - t.size + padY * 0.2, bw = tw + padX * 2, bh = t.size + padY * 1.4;
        if (t.effect === "bar" || t.effect === "invert") {
          const bar = t.effect === "invert" ? contrastInk(t.color) : t.color;
          target.fillStyle = bar;
          target.beginPath(); target.roundRect ? target.roundRect(bx, by, bw, bh, 7) : target.rect(bx, by, bw, bh); target.fill();
          target.fillStyle = t.effect === "invert" ? t.color : contrastInk(t.color);
          target.fillText(line, 0, ly);
        } else {
          target.lineWidth = t.size * 0.12; target.strokeStyle = "rgba(0,0,0,.92)"; target.lineJoin = "round";
          target.fillStyle = t.color;
          target.strokeText(line, 0, ly); target.fillText(line, 0, ly);
        }
      });
      target.restore();
    });
    target.restore();
  }
  const redraw = () => paint();

  // ---------- źródło ----------
  function setSource(src) {
    if (src === "file" && !fileUrl) { $("#tsFile", dlg).click(); return; }
    s.source = src; srcReady = false;
    $$(".ts-src button", dlg).forEach(b => b.classList.toggle("active", b.dataset.src === src));
    $("#tsVideoBox", dlg).hidden = src !== "video";
    if (src === "video") { if (serverFrames && !frameReady) loadServerFrame(s.t); redraw(); return; }
    img.onload = () => { srcReady = true; redraw(); };
    img.onerror = () => toast("Nie udało się wczytać obrazu źródłowego.", "error");
    img.src = src === "file" ? fileUrl : src === "slide" ? slide : c.assets.thumbnail_url;
    redraw();
  }
  $$(".ts-src button", dlg).forEach(b => b.onclick = () => b.dataset.src === "file" ? $("#tsFile", dlg).click() : setSource(b.dataset.src));
  $("#tsFile", dlg).onchange = e => {
    const f = e.target.files[0]; e.target.value = "";
    if (!f) return;
    if (fileUrl) URL.revokeObjectURL(fileUrl);
    fileUrl = URL.createObjectURL(f); setSource("file");
  };
  if (video) {
    vid.addEventListener("loadedmetadata", () => {
      vid.currentTime = Math.min(s.t || 0, vid.duration || 0);
      $("#tsScrub", dlg).value = vid.duration ? Math.round((s.t / vid.duration) * 1000) : 0;
      if (!vid.videoWidth) useServerFrames();
    });
    vid.addEventListener("error", useServerFrames);
    vid.addEventListener("play", () => markWatched(c.post_id), { once: true });
    setTimeout(() => { if (!vid.videoWidth) useServerFrames(); }, 4000);
    ["seeked", "loadeddata", "timeupdate"].forEach(ev => vid.addEventListener(ev, () => {
      if (s.source !== "video") return;
      s.t = vid.currentTime;
      if (serverFrames) { if (ev === "seeked" || vid.paused) loadServerFrame(s.t); } else redraw();
    }));
    vid.addEventListener("pause", () => { if (serverFrames) loadServerFrame(vid.currentTime); });
    $("#tsScrub", dlg).oninput = e => {
      const dur = vid.duration || 30;
      s.t = (e.target.value / 1000) * dur;
      if (vid.duration) vid.currentTime = s.t;
      if (serverFrames) loadServerFrame(s.t);
    };
  }

  // ---------- kadr ----------
  const zoomEl = $("#tsZoom", dlg);
  const syncZoom = () => { zoomEl.value = String(Math.round(s.zoom * 100)); };
  zoomEl.oninput = () => { s.zoom = zoomEl.value / 100; redraw(); };
  $("#tsResetCrop", dlg).onclick = () => { Object.assign(s, { zoom: RESET.zoom, x: RESET.x, y: RESET.y }); syncZoom(); redraw(); };
  const setRatio = r => {
    s.ratio = r; canvas.height = H();
    $$("#tsRatio button", dlg).forEach(b => b.classList.toggle("active", b.dataset.r === r));
    s.layers.forEach(t => { t.x = null; t.y = null; });
    redraw();
  };
  $$("#tsRatio button", dlg).forEach(b => b.onclick = () => setRatio(b.dataset.r));

  const toCanvas = e => {
    const r = canvas.getBoundingClientRect();
    return { x: Math.max(0, Math.min(canvas.width, (e.clientX - r.left) * canvas.width / r.width)), y: Math.max(0, Math.min(canvas.height, (e.clientY - r.top) * canvas.height / r.height)) };
  };
  const nearest = p => {
    let best = null, dist = Infinity;
    s.layers.forEach(t => {
      if (!t.text.trim() || !t._anchor) return;
      const d = (t._anchor.x - p.x) ** 2 + (t._anchor.y - p.y) ** 2;
      if (d < dist) { dist = d; best = t; }
    });
    const lim = (best?.size || 48) * 3.2;
    return best && dist < lim * lim ? best : null;
  };
  let dragging = null, panLast = null;
  canvas.onpointerdown = e => {
    const p = toCanvas(e);
    canvas.setPointerCapture(e.pointerId);
    dragging = nearest(p);
    if (dragging) { dragging.x = p.x; dragging.y = p.y; redraw(); } else panLast = p;
  };
  canvas.onpointermove = e => {
    const p = toCanvas(e);
    if (dragging) { dragging.x = p.x; dragging.y = p.y; redraw(); }
    else if (panLast) { s.x += p.x - panLast.x; s.y += p.y - panLast.y; panLast = p; redraw(); }
  };
  canvas.onpointerup = canvas.onpointercancel = () => { dragging = null; panLast = null; };
  canvas.addEventListener("wheel", e => {
    if (e.ctrlKey) return;
    e.preventDefault();
    s.zoom = Math.max(1, Math.min(2.5, s.zoom + (e.deltaY < 0 ? 0.08 : -0.08)));
    syncZoom(); redraw();
  }, { passive: false });

  // ---------- napisy ----------
  function drawLayers() {
    const box = $("#tsLayers", dlg);
    box.innerHTML = s.layers.map((t, i) => `<div class="ts-layer" data-i="${i}">
      <div class="ts-layer-head"><b>Opcja ${i + 1}</b><button type="button" class="btn ghost small" data-del>Usuń</button></div>
      <input type="text" data-k="text" value="${esc(t.text)}" placeholder="${i === 0 ? "linia na GÓRZE kadru" : "linie na DOLE kadru"}">
      <div class="ts-grid">
        <label class="ts-field"><span>Pozycja</span><select data-k="pos"><option value="top">Góra</option><option value="mid">Środek</option><option value="bottom">Dół</option></select></label>
        <label class="ts-field"><span>Wielkość</span><input type="range" data-k="size" min="21" max="105" value="${t.size}"></label>
        <label class="ts-field"><span>Obrót</span><input type="range" data-k="rotate" min="-45" max="45" value="${t.rotate}"></label>
      </div>
      <span class="ts-label">Kolor</span>
      <div class="ts-swatches">${COLOR_SWATCHES.map(([hex, n]) => `<button type="button" class="swatch ${t.color === hex ? "on" : ""}" data-color="${hex}" title="${esc(n)}" aria-label="${esc(n)}" style="background:${hex}"></button>`).join("")}</div>
      <span class="ts-label">Efekt</span>
      <div class="seg">${EFFECTS.map(([k, n]) => `<button type="button" data-fx="${k}" class="${(t.effect || "bar") === k ? "active" : ""}">${esc(n)}</button>`).join("")}</div>
    </div>`).join("");
    $$(".ts-layer", box).forEach(row => {
      const t = s.layers[+row.dataset.i];
      $("[data-k=pos]", row).value = t.pos;
      $$("[data-k]", row).forEach(inp => inp.oninput = () => {
        const k = inp.dataset.k;
        t[k] = ["size", "rotate"].includes(k) ? +inp.value : inp.value;
        if (k === "pos") { t.x = null; t.y = null; }
        redraw();
      });
      $$("[data-color]", row).forEach(b => b.onclick = () => { t.color = b.dataset.color; $$("[data-color]", row).forEach(x => x.classList.toggle("on", x === b)); redraw(); });
      $$("[data-fx]", row).forEach(b => b.onclick = () => { t.effect = b.dataset.fx; $$("[data-fx]", row).forEach(x => x.classList.toggle("active", x === b)); redraw(); });
      $("[data-del]", row).onclick = () => { s.layers.splice(+row.dataset.i, 1); drawLayers(); redraw(); };
    });
    const add = $("#tsAdd", dlg);
    add.textContent = !s.layers.length ? "Dodaj napisy" : s.layers.length >= 3 ? "Maks. 3 napisy" : s.layers.length === 2 ? "Dodaj 3. napis" : "Dodaj opcję";
    add.disabled = s.layers.length >= 3;
    $("#tsLayerTools", dlg).hidden = !s.layers.length;
  }
  $("#tsAdd", dlg).onclick = () => {
    if (!s.layers.length) s.layers.push(newLayer("top"), newLayer("bottom"));
    else if (s.layers.length < 3) s.layers.push(newLayer("bottom"));
    drawLayers(); redraw();
  };
  $("#tsLayout", dlg).onclick = () => {
    while (s.layers.length < 2) s.layers.push(newLayer(s.layers.length ? "bottom" : "top"));
    Object.assign(s.layers[0], { pos: "top", x: null, y: null }); Object.assign(s.layers[1], { pos: "bottom", x: null, y: null });
    drawLayers(); redraw();
  };
  $("#tsResetPos", dlg).onclick = () => { s.layers.forEach(t => { t.x = null; t.y = null; }); redraw(); };

  // ---------- zapis ----------
  async function exportBlob() {
    const k = OUT_W / W, out = document.createElement("canvas");
    out.width = OUT_W; out.height = Math.round(H() * k);
    paint(out.getContext("2d"), k);
    const blob = await new Promise(res => out.toBlob(res, "image/png"));
    if (!blob) throw new Error("Miniatura jest pusta.");
    return blob;
  }
  $("#tsPng", dlg).onclick = e => run(e.currentTarget, async () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await exportBlob());
    a.download = `${c.name.replace(/\.[^.]+$/, "") || "miniaturka"}.png`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2500);
  }, "PNG pobrany.");
  $("#tsCancel", dlg).onclick = () => dlg.close();
  $("#tsSave", dlg).onclick = e => run(e.currentTarget, async () => {
    if (!sourceEl()) throw new Error("Poczekaj, aż wczyta się źródło miniatury.");
    const r = await fetch(`${pub(c.post_id)}/thumbnail`, { method: "PUT", body: await exportBlob(), headers: { "X-Expected-Revision": c.revision } });
    const data = await r.json(); if (!r.ok) throw new Error(data.error);
    dlg.close();
    await onSaved(data);
  }, "Miniatura zapisana w paczce.");

  // Czcionki muszą być wczytane, zanim canvas narysuje napis — inaczej wychodzi systemowa.
  document.fonts?.load(`900 40px ${FONT}`, "AĄĘŁŃÓŚŹŻ").then(redraw).catch(() => {});
  syncZoom(); drawLayers(); setRatio(s.ratio); setSource(s.source);
}
