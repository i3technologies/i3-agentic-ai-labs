/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  env: {
    NEXT_PUBLIC_HLS_BASE_URL: process.env.NEXT_PUBLIC_HLS_BASE_URL || 'https://stream.i3technologies.co.ke',
    NEXT_PUBLIC_CMS_URL: process.env.NEXT_PUBLIC_CMS_URL || 'https://cms.i3technologies.co.ke',
    NEXT_PUBLIC_SSO_URL: process.env.NEXT_PUBLIC_SSO_URL || 'https://sso.i3technologies.co.ke',
  },
  images: {
    // Allow thumbnails served by Directus CMS and SeaweedFS S3
    remotePatterns: [
      { protocol: 'https', hostname: 'cms.i3technologies.co.ke' },
      { protocol: 'https', hostname: 'stream.i3technologies.co.ke' },
      { protocol: 'http',  hostname: 'directus.i3-ott.svc.cluster.local' },
    ],
  },
  // hls.js uses browser APIs; exclude from server-side bundle tree-shaking
  serverExternalPackages: ['hls.js'],
}

module.exports = nextConfig
