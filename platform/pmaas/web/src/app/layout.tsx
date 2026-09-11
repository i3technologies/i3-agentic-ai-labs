import type { Metadata } from 'next'
import './globals.css'
import { Providers } from './providers'
import { Header } from './header'

export const metadata: Metadata = {
  title: 'PMaaS 4.0 — Political Campaign Operating System',
  description: 'AI-powered campaign intelligence platform by i3 Technologies',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        <Providers>
          <Header />
          <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
        </Providers>
      </body>
    </html>
  )
}
