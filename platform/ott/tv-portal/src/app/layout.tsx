import type { Metadata, Viewport } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'i3 TV — Live & On-Demand Learning',
  description: 'Stream live classes and on-demand lectures from i3 Technologies Academy.',
}

// Next.js 15: viewport must be exported separately, not inside metadata
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
