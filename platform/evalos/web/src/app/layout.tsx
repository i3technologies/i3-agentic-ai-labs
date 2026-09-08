import type { Metadata } from 'next'
import './globals.css'
import Providers from './providers'
import Header from './header'

export const metadata: Metadata = {
  title: 'EvalOS — IBM watsonx Orchestrate Certification Practice',
  description:
    'Practice exam platform for IBM watsonx Orchestrate (C1000-207) certification.',
  icons: {
    icon: '/favicon.svg',
    shortcut: '/favicon.svg',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <Header />
          <main>{children}</main>
        </Providers>
      </body>
    </html>
  )
}
