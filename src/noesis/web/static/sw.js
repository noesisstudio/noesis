// Service worker mínimo de Bynoesis: habilita instalar la app y deja la base para
// trabajo offline más adelante. De momento, paso directo a la red.
const CACHE = "noesis-v1";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
  // Network-first; si falla la red, intentamos la caché (para el shell).
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
