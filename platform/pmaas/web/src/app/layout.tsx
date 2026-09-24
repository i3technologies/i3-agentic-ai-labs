import type { Metadata } from 'next'
import './globals.css'
import { Providers } from './providers'
import { Header } from './header'

export const metadata: Metadata = {
  title: 'PMaaS 4.0 — Political Campaign Operating System',
  description: 'AI-powered campaign intelligence platform by i3 Technologies',
  manifest: '/manifest.json',
  themeColor: '#1a56db',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'i3 PMaaS',
  },
  viewport: {
    width: 'device-width',
    initialScale: 1,
    maximumScale: 1,
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#1a56db" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
        <meta name="apple-mobile-web-app-title" content="i3 PMaaS" />
        <link rel="apple-touch-icon" href="/icon-192.png" />
      </head>
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        <Providers>
          <Header />
          <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
        </Providers>
      </body>
    </html>
  )
}
