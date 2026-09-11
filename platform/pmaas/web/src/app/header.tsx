'use client'
import Link from 'next/link'
import { useSession, signIn, signOut } from 'next-auth/react'
import { usePathname } from 'next/navigation'

const NAV = [
  { href: '/dashboard',  label: 'Dashboard'   },
  { href: '/campaigns',  label: 'Campaigns'   },
  { href: '/wards',      label: 'Ward Map'    },
  { href: '/voters',     label: 'Voters'      },
  { href: '/briefing',   label: 'AI Briefing' },
  { href: '/calendar',   label: 'Calendar'    },
]

export function Header() {
  const { data: session } = useSession()
  const path = usePathname()

  return (
    <header className="border-b border-gray-800 bg-gray-950 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 flex items-center h-14 gap-6">
        {/* Logo */}
        <Link href="/dashboard" className="flex items-center gap-2 flex-shrink-0">
          <span className="text-green-500 font-bold text-lg tracking-tight">PMaaS</span>
          <span className="text-gray-500 text-xs font-medium">4.0</span>
        </Link>

        {/* Nav */}
        <nav className="flex items-center gap-1 flex-1 overflow-x-auto">
          {NAV.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors whitespace-nowrap
                ${path === href
                  ? 'bg-green-900/50 text-green-400'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
                }`}
            >
              {label}
            </Link>
          ))}
        </nav>

        {/* Auth */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {session ? (
            <>
              <span className="text-xs text-gray-400 hidden sm:block">
                {session.user?.name ?? session.user?.email}
              </span>
              <button onClick={() => signOut()} className="text-xs text-gray-500 hover:text-gray-300">
                Sign out
              </button>
            </>
          ) : (
            <button onClick={() => signIn('keycloak')} className="btn-primary text-xs">
              Sign in
            </button>
          )}
        </div>
      </div>
    </header>
  )
}
