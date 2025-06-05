const CACHE_NAME = 'logichain-v1';
const ASSETS = [
    '/',
    '/index.html',
    '/css/style.css',
    '/js/main.js',
    '/assets/logo.svg',
    '/assets/logo-white.svg',
    '/assets/icon-192.png',
    '/assets/icon-512.png',
    '/manifest.json',
    '/docs/API.md',
    '/docs/ARCHITECTURE.md',
    '/docs/whitepaper.md',
    '/assets/architecture.svg'
];

// Instalação do Service Worker
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(ASSETS))
            .then(() => self.skipWaiting())
    );
});

// Ativação e limpeza de caches antigos
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames
                    .filter(name => name !== CACHE_NAME)
                    .map(name => caches.delete(name))
            );
        })
    );
});

// Estratégia de cache: Network First com fallback para cache
self.addEventListener('fetch', event => {
    // Não intercepta requisições para APIs
    if (event.request.url.includes('/api/')) {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then(response => {
                // Cache a resposta bem-sucedida
                const responseClone = response.clone();
                caches.open(CACHE_NAME)
                    .then(cache => cache.put(event.request, responseClone));
                return response;
            })
            .catch(() => {
                // Se falhar, tenta o cache
                return caches.match(event.request)
                    .then(response => {
                        if (response) {
                            return response;
                        }
                        // Se não houver cache, retorna página offline
                        if (event.request.mode === 'navigate') {
                            return caches.match('/offline.html');
                        }
                        return new Response('', {
                            status: 408,
                            statusText: 'Request timeout'
                        });
                    });
            })
    );
});

// Sincronização em background
self.addEventListener('sync', event => {
    if (event.tag === 'sync-messages') {
        event.waitUntil(
            // Tenta reenviar mensagens pendentes
            syncMessages()
        );
    }
});

// Push notifications
self.addEventListener('push', event => {
    const options = {
        body: event.data.text(),
        icon: '/assets/icon-192.png',
        badge: '/assets/badge.png',
        vibrate: [100, 50, 100],
        data: {
            dateOfArrival: Date.now(),
            primaryKey: 1
        },
        actions: [
            {
                action: 'explore',
                title: 'Ver detalhes',
                icon: '/assets/check.png'
            }
        ]
    };

    event.waitUntil(
        self.registration.showNotification('LogiChain', options)
    );
});

// Clique em notificação
self.addEventListener('notificationclick', event => {
    event.notification.close();

    if (event.action === 'explore') {
        event.waitUntil(
            clients.openWindow('/')
        );
    }
});

// Função auxiliar para sincronização
async function syncMessages() {
    try {
        const messagesQueue = await idb.open('messages-queue');
        const messages = await messagesQueue.getAll();

        for (const message of messages) {
            try {
                await fetch('/api/messages', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(message)
                });
                await messagesQueue.delete(message.id);
            } catch (error) {
                console.error('Erro ao sincronizar mensagem:', error);
            }
        }
    } catch (error) {
        console.error('Erro ao sincronizar mensagens:', error);
    }
} 