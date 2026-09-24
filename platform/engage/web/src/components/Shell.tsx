/* Shared layout shell: sidebar + topbar */
'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { signOut, useSession } from 'next-auth/react'
import clsx from 'clsx'

const nav = [
  { href: '/dashboard',   label: 'Dashboard',  icon: '▦' },
  { href: '/contacts',    label: 'Contacts',   icon: '👥' },
  { href: '/lists',       label: 'Lists',      icon: '📋' },
  { href: '/campaigns',   label: 'Campaigns',  icon: '📧' },
  { href: '/sms',         label: 'SMS',        icon: '💬' },
  { href: '/analytics',   label: 'Analytics',  icon: '📊' },
]

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const { data: session } = useSession()

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-56 bg-indigo-900 text-white flex flex-col shrink-0">
        <div className="px-5 py-5 border-b border-indigo-700">
          <span className="font-bold text-lg tracking-tight">i3 Engage</span>
          <div className="text-xs text-indigo-300 mt-0.5">Campaign Platform</div>
        </div>
        <nav className="flex-1 py-4 space-y-0.5 px-2">
          {nav.map(n => (
            <Link
              key={n.href}
              href={n.href}
              className={clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                pathname.startsWith(n.href)
                  ? 'bg-indigo-700 text-white'
                  : 'text-indigo-200 hover:bg-indigo-800 hover:text-white'
              )}
            >
              <span className="text-base">{n.icon}</span>
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="p-4 border-t border-indigo-700">
          <div className="text-xs text-indigo-300 truncate mb-2">
            {session?.user?.email ?? ''}
          </div>
          <button
            onClick={() => signOut({ callbackUrl: '/login' })}
            className="text-xs text-indigo-300 hover:text-white transition-colors"
          >
            Sign out →
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 bg-white border-b border-slate-200 flex items-center px-6 shrink-0">
          <h1 className="text-sm font-semibold text-slate-700 capitalize">
            {pathname.split('/')[1] || 'Dashboard'}
          </h1>
        </header>
        <main className="flex-1 p-6 overflow-auto bg-slate-50">
          {children}
        </main>
      </div>
    </div>
  )
}
