/**
 * sw-custom.js — PMaaS PWA custom service worker additions
 * This file is imported by next-pwa at build time (swSrc in next.config.js).
 * Workbox is injected automatically by next-pwa; this file adds only
 * application-specific offline handling.
 *
 * Offline queue: failed POST requests to /api/briefing/generate are stored in
 * IndexedDB and replayed on next connectivity event — important for field
 * campaign staff with intermittent connectivity.
 */

// ── Offline POST queue (briefing generation) ─────────────────────────────────
const OFFLINE_QUEUE_NAME = 'pmaas-offline-queue';

self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Only intercept POST /api/briefing/generate when offline
  if (
    request.method === 'POST' &&
    (request.url.includes('/api/briefing/generate') ||
     request.url.includes('/api/briefing/ask')) &&
    !self.navigator?.onLine
  ) {
    event.respondWith(
      (async () => {
        try {
          return await fetch(request.clone());
        } catch {
          await _enqueueOfflineRequest(request.clone());
          return new Response(
            JSON.stringify({ queued: true, message: 'Briefing queued — will process when online.' }),
            { status: 202, headers: { 'Content-Type': 'application/json' } }
          );
        }
      })()
    );
  }
});

// ── Replay queued requests on connectivity restored ───────────────────────────
self.addEventListener('sync', (event) => {
  if (event.tag === 'pmaas-offline-sync') {
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
    const req = indexedDB.open('pmaas-sw-db', 1);
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
