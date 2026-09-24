/** @type {import('next').NextConfig} */
const withPWA = require('next-pwa')({
  dest: 'public',
  register: true,
  skipWaiting: true,
  disable: process.env.NODE_ENV === 'development',
  // Custom service worker with offline queue logic (imported at sw build time)
  swSrc: 'public/sw-custom.js',
  runtimeCaching: [
    // network-first for all API routes
    {
      urlPattern: /^\/api\/.*/i,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'engage-api-cache',
        networkTimeoutSeconds: 10,
        expiration: {
          maxEntries: 64,
          maxAgeSeconds: 24 * 60 * 60, // 24 h
        },
        cacheableResponse: {
          statuses: [0, 200],
        },
      },
    },
    // cache-first for Next.js static assets
    {
      urlPattern: /^\/_next\/static\/.*/i,
      handler: 'CacheFirst',
      options: {
        cacheName: 'engage-static-cache',
        expiration: {
          maxEntries: 256,
          maxAgeSeconds: 365 * 24 * 60 * 60, // 1 year
        },
      },
    },
    // stale-while-revalidate for dashboard HTML
    {
      urlPattern: /^\/dashboard.*/i,
      handler: 'StaleWhileRevalidate',
      options: {
        cacheName: 'engage-pages-cache',
        expiration: {
          maxEntries: 16,
          maxAgeSeconds: 60 * 60, // 1 h
        },
      },
    },
  ],
})

const nextConfig = {
  output: 'standalone',
  experimental: {
    serverComponentsExternalPackages: ['pg'],
  },
  images: {
    domains: [],
  },
}

module.exports = withPWA(nextConfig)
