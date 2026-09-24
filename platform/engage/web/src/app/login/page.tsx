'use client'
import { signIn, useSession } from 'next-auth/react'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const { data: session, status } = useSession()
  const router = useRouter()

  useEffect(() => {
    if (session) router.replace('/dashboard')
  }, [session, router])

  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-indigo-900">
        <div className="text-white text-sm">Loading…</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-indigo-900">
      <div className="bg-white rounded-2xl shadow-2xl p-10 w-full max-w-sm text-center">
        <div className="text-3xl mb-2">📣</div>
        <h1 className="text-2xl font-bold text-slate-800 mb-1">i3 Engage</h1>
        <p className="text-slate-500 text-sm mb-8">AI-powered campaign & messaging platform</p>
        <button
          onClick={() => signIn('keycloak', { callbackUrl: '/dashboard' })}
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-xl transition-colors text-sm"
        >
          Sign in with i3 SSO
        </button>
        <p className="mt-4 text-xs text-slate-400">Powered by Keycloak · i3 Technologies</p>
      </div>
    </div>
  )
}
