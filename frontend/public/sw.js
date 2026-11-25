/* TempleGate AP Automation service worker (PWA installability + offline shell).
 *
 * Policy:
 *  - NEVER cache API calls (/api/...) or media (/media/...): invoice data must
 *    always come from the server, there is no offline invoice data.
 *  - Navigation requests: network-first with an offline fallback message.
 *  - Static assets (hashed Vite bundles, icons, manifest): stale-while-revalidate.
 */
const CACHE_NAME = 'tg-ap-static-v1';
const OFFLINE_MESSAGE = '<!doctype html><html><head><meta charset="utf-8">' +
  '<meta name="viewport" content="width=device-width, initial-scale=1">' +
  '<title>TempleGate AP Automation</title>' +
  '<style>body{font-family:system-ui,sans-serif;background:#14365D;color:#fff;' +
  'display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}' +
  'div{max-width:420px;padding:24px;text-align:center}h1{font-size:20px}</style></head>' +
  '<body><div><h1>You are offline</h1>' +
  '<p>TempleGate AP Automation needs a connection to load invoices, approvals and payments.</p>' +
  '<p>Reconnect and reload the app.</p></div></body></html>';

self.addEventListener('install', (event) => {
  self.skipWaiting();
  // Pre-cache only the app shell icons; bundles are hashed and cached lazily.
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll([
      '/manifest.webmanifest',
      '/icons/icon-192.png',
      '/icons/icon-512.png',
    ]).catch(() => undefined))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);

  // 1. API and media: always network, never cached.
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/media/')) {
    event.respondWith(fetch(request));
    return;
  }

  // 2. SPA navigations: network-first, offline fallback page.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => response)
        .catch(() =>
          new Response(OFFLINE_MESSAGE, { headers: { 'Content-Type': 'text/html' } })
        )
    );
    return;
  }

  // 3. Static assets: stale-while-revalidate.
  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(request);
      const network = fetch(request)
        .then((response) => {
          if (response && response.status === 200 && response.type === 'basic') {
            cache.put(request, response.clone());
          }
          return response;
        })
        .catch(() => cached || Response.error());
      return cached || network;
    })
  );
});
