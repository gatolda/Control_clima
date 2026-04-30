// Service worker minimo: PWA instalable + fallback offline basico.
// Estrategia: network-first para CSS/JS (para que cambios de estilo se reflejen
// inmediatamente), cache solo como fallback offline.

const CACHE_NAME = 'greenhouse-v3';
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
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;

    // No cachear API ni Socket.IO
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/socket.io/')) {
        return;
    }

    // Network-first para static assets (CSS/JS/manifest/icon).
    // Si la red falla (offline), servimos del cache.
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            fetch(event.request)
                .then((res) => {
                    if (res.ok) {
                        const copy = res.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
                    }
                    return res;
                })
                .catch(() => caches.match(event.request))
        );
    }
});
