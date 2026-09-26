const CACHE="byku-mobile-v2";
const SHELL=["./","./index.html","./styles.css","./fonts.css","./src/app.js","./src/domain.js","./src/store.js","./src/sync.js","./manifest.webmanifest","./icon.svg"];
self.addEventListener("install",e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())));
self.addEventListener("activate",e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener("fetch",e=>{
  const url=new URL(e.request.url);
  // Paczki (filmy, manifesty, index.json) zawsze z sieci — offline obsługuje ostatni odczyt w localStorage, nie cache SW.
  if(e.request.method!=="GET"||url.origin!==location.origin||url.pathname.includes("/paczki/")||e.request.headers.has("range"))return;
  e.respondWith(fetch(e.request).then(r=>{if(r.ok&&r.status===200){const copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request,copy))}return r}).catch(()=>caches.match(e.request).then(r=>r||caches.match("./index.html"))));
});
