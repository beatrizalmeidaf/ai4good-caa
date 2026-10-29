// Zuli funciona sem internet depois do primeiro acesso.
// Página, código e dados: rede primeiro (pega atualizações), cache quando offline.
// Pictogramas e áudios: cache primeiro (não mudam), e ficam guardados conforme são usados.
const CACHE = "zuli-v13";
const BASE = ["./", "index.html", "prancha.html", "pais.html", "manifest.json", "js/core.js", "js/crianca.js", "js/slm.js", "js/treino.js", "js/pais.js",
  "assets/zuli.png", "assets/zuli-64.png", "data/vocab.json", "data/slm.json", "data/slm.bin"];

self.addEventListener("install", e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(BASE)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));

const guardar = (req, r) => { if (r.ok) { const c = r.clone(); caches.open(CACHE).then(x => x.put(req, c)); } return r; };
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (/\/(p|audio)\//.test(url.pathname)) {
    e.respondWith(caches.match(e.request).then(hit => hit || fetch(e.request).then(r => guardar(e.request, r))));
  } else {
    e.respondWith(fetch(e.request).then(r => guardar(e.request, r)).catch(() => caches.match(e.request, { ignoreSearch: true })));
  }
});
