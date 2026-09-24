/**
 * sw-custom.js — Engage PWA custom service worker additions
 * This file is imported by next-pwa at build time (swSrc in next.config.js).
 * Workbox is injected automatically by next-pwa; this file adds only
 * application-specific offline handling.
 *
 * Offline queue: failed POST requests to /api/campaigns/send are stored in
 * IndexedDB and replayed on next connectivity event.
 */

// ── Offline POST queue (campaign send) ───────────────────────────────────────
const OFFLINE_QUEUE_NAME = 'engage-offline-queue';

self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Only intercept POST /api/campaigns/send when offline
  if (
    request.method === 'POST' &&
    request.url.includes('/api/campaigns/send') &&
    !self.navigator?.onLine
  ) {
    event.respondWith(
      (async () => {
        try {
          return await fetch(request.clone());
        } catch {
          // Store the request in IndexedDB for later replay
          await _enqueueOfflineRequest(request.clone());
          return new Response(
            JSON.stringify({ queued: true, message: 'Campaign queued for send when online.' }),
            { status: 202, headers: { 'Content-Type': 'application/json' } }
          );
        }
      })()
    );
  }
});

// ── Replay queued requests on connectivity restored ───────────────────────────
self.addEventListener('sync', (event) => {
  if (event.tag === 'engage-offline-sync') {
    event.waitUntil(_replayOfflineQueue());
  }
});

async function _enqueueOfflineRequest(request) {
  const db = await _openDb();
  const tx = db.transaction(OFFLINE_QUEUE_NAME, 'readwrite');
  const store = tx.objectStore(OFFLINE_QUEUE_NAME);
  const body = await request.text();
  store.add({ url: request.url, method: request.method, body, timestamp: Date.now() });
}

async function _replayOfflineQueue() {
  const db = await _openDb();
  const tx = db.transaction(OFFLINE_QUEUE_NAME, 'readwrite');
  const store = tx.objectStore(OFFLINE_QUEUE_NAME);
  const all = await _promisify(store.getAll());
  for (const entry of all) {
    try {
      await fetch(entry.url, { method: entry.method, body: entry.body,
        headers: { 'Content-Type': 'application/json' } });
      store.delete(entry.id);
    } catch {
      // Keep in queue — will retry on next sync
    }
  }
}

function _openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('engage-sw-db', 1);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(OFFLINE_QUEUE_NAME)) {
        db.createObjectStore(OFFLINE_QUEUE_NAME, { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror   = (e) => reject(e.target.error);
  });
}

function _promisify(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = (e) => resolve(e.target.result);
    request.onerror   = (e) => reject(e.target.error);
  });
}
