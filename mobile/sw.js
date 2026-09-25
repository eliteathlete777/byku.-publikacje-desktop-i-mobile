// Service worker: wyłącznie powłoka aplikacji. API i materiały NIGDY nie trafiają do pamięci SW —
// dane są dostępne tylko przez zalogowaną aplikację (i czyszczone przy wylogowaniu).
const VERSION = "byku-shell-v2.0.0";
const SHELL = ["./", "./index.html", "./styles.css", "./src/app.js", "./src/domain.js", "./src/contract.js", "./src/session.js",
  "./manifest.webmanifest", "./icons/icon-192.png", "./icons/icon-512.png", "./icons/apple-touch-icon.png"];

self.addEventListener("install", e => e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith("byku-shell-") && k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim())));

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.includes("/api/")) return; // sieć, bez pamięci
  e.respondWith(
    fetch(e.request).then(r => {
      if (r.ok && SHELL.some(p => url.pathname.endsWith(p.slice(1)) || (p === "./" && url.pathname.endsWith("/")))) {
        const copy = r.clone(); caches.open(VERSION).then(c => c.put(e.request, copy));
      }
      return r;
    }).catch(() => caches.match(e.request).then(r => r || (e.request.mode === "navigate" ? caches.match("./index.html") : Response.error())))
  );
});
