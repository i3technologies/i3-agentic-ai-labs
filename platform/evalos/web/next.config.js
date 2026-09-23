/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // Next.js 14.0+ moved serverComponentsExternalPackages out of experimental.
  // Keeping it under experimental also works in 14.x but emits a deprecation
  // warning that appears in server logs and can mask real errors.
  serverExternalPackages: [
    'pg',
    '@react-pdf/renderer',
    '@fingerprintjs/fingerprintjs',
  ],
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
