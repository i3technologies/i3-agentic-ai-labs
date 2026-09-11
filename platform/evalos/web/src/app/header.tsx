'use client'

import { useSession, signOut } from 'next-auth/react'
import Link from 'next/link'
import Image from 'next/image'

export default function Header() {
  const { data: session } = useSession()

  return (
    <header className="bg-slate-900 text-white border-b border-slate-700/50">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-3">
          {/* i3 logo */}
          <Image
            src="/i3-logo.svg"
            alt="i3 Technologies"
            width={40}
            height={14}
            className="brightness-100"
            priority
          />
          <div className="h-4 w-px bg-slate-600" />
          <span className="text-white font-semibold text-sm tracking-tight">EvalOS</span>
          <span className="hidden sm:inline text-slate-400 text-xs">
            Certification Practice
          </span>
        </Link>

        <nav className="flex items-center gap-4">
          {session ? (
            <>
              {session.user.isAdmin && (
                <Link
                  href="/admin"
                  className="text-xs text-slate-300 hover:text-white transition-colors font-medium"
                >
                  Admin
                </Link>
              )}
              <Link
                href="/dashboard"
                className="text-xs text-slate-300 hover:text-white transition-colors"
              >
                Dashboard
              </Link>
              <Link
                href="/leaderboard"
                className="text-xs text-slate-300 hover:text-white transition-colors"
              >
                Leaderboard
              </Link>
              <Link
                href="/interview"
                className="text-xs text-slate-300 hover:text-white transition-colors"
              >
                AI Interview
              </Link>
              <Link
                href="/lab"
                className="text-xs text-slate-300 hover:text-white transition-colors"
              >
                Coding Labs
              </Link>
              <span className="text-slate-500 text-xs hidden sm:inline truncate max-w-[180px]">
                {session.user.name || session.user.email}
              </span>
              <button
                onClick={() => signOut({ callbackUrl: '/' })}
                className="text-xs text-slate-300 hover:text-white border border-slate-600 hover:border-slate-400 rounded-md px-3 py-1.5 transition-colors"
              >
                Sign out
              </button>
            </>
          ) : null}
        </nav>
      </div>
    </header>
  )
}
