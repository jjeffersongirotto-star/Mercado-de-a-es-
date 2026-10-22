// Service worker do app instalável: sempre busca na rede (dados atuais); sem internet, mostra a última cópia salva.
// v2: a v1 juntava uma cópia de cada /static/x.js?v=hash a cada publicação (apagada no activate)
const CACHE = 'screenerB3-app-v2';
const KEEP = (p) => p === '/' || p.startsWith('/static/') || p === '/tailwind.config.js' || p === '/manifest.webmanifest' ||
  p === '/api/data' || p === '/api/countries' || p === '/api/metrics';
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
  .then(() => self.clients.claim())));
self.addEventListener('fetch', (e) => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== location.origin) return;
  e.respondWith(fetch(r).then(res => {
    if (res.ok && KEEP(u.pathname)) {
      const c = res.clone();
      caches.open(CACHE).then(async x => {
        // /static/: só a versão atual de cada arquivo (as de ?v= antigo saem)
        if (u.pathname.startsWith('/static/')) for (const k of await x.keys(r, { ignoreSearch: true })) if (k.url !== r.url) await x.delete(k);
        await x.put(r, c);
      }).catch(() => { });
    }
    return res;
  }).catch(() => caches.match(r).then(m => m || (r.mode === 'navigate' ? caches.match('/') : Response.error()))));
});
// Toque no aviso de alerta de preço: volta para o app aberto (ou abre)
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: 'window' }).then(cs => cs.length ? cs[0].focus() : self.clients.openWindow('/')));
});
