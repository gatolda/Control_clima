// Service worker minimo para que la PWA sea instalable y tenga
// fallback offline basico (no cachea data dinamica).

const CACHE_NAME = 'greenhouse-v1';
const APP_SHELL = [
    '/static/style.css',
    '/static/manifest.webmanifest',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL).catch(() => {}))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((names) =>
            Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    // Solo cachear GET de mismo origen, archivos estaticos
    if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;

    // Network-first para HTML y data dinamica
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/socket.io/')) {
        return; // dejar pasar sin cache
    }
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(event.request).then((cached) =>
                cached || fetch(event.request).then((res) => {
                    if (res.ok) {
                        const copy = res.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
                    }
                    return res;
                })
            )
        );
    }
});
