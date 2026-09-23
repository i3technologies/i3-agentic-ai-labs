/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // Next.js 14.x: the correct key is experimental.serverComponentsExternalPackages.
  // (serverExternalPackages is Next.js 15+ only and emits "Unrecognized key" in 14.x)
  experimental: {
    serverComponentsExternalPackages: [
      'pg',
      '@react-pdf/renderer',
      '@fingerprintjs/fingerprintjs',
    ],
  },
  env: {
    NEXTAUTH_URL: process.env.NEXTAUTH_URL,
    KEYCLOAK_ISSUER: process.env.KEYCLOAK_ISSUER,
    KEYCLOAK_CLIENT_ID: process.env.KEYCLOAK_CLIENT_ID,
    N8N_WEBHOOK_URL: process.env.N8N_WEBHOOK_URL,
    KEYCLOAK_ADMIN_PASSWORD: process.env.KEYCLOAK_ADMIN_PASSWORD,
  },
  // Suppress punycode deprecation warning from transitive deps
  webpack(config) {
    config.resolve.fallback = { ...config.resolve.fallback, punycode: false }
    return config
  },
}

module.exports = nextConfig
