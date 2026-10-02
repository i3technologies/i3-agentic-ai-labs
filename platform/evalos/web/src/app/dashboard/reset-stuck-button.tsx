'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

interface ResetStuckButtonProps {
  /** When true, renders a compact inline link instead of a full button */
  compact?: boolean
  /** When provided, restricts the reset to this exam set number (e.g. 7) */
  setNumber?: number
}

export default function ResetStuckButton({ compact = false, setNumber }: ResetStuckButtonProps) {
  const router = useRouter()
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [message, setMessage] = useState<string | null>(null)

  const handleReset = async () => {
    setState('loading')
    setMessage(null)
    try {
      const body = setNumber !== undefined ? JSON.stringify({ setNumber }) : undefined
      const res = await fetch('/api/admin/reset-stuck', {
        method: 'POST',
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? 'Failed')

      setMessage(data.message ?? `${data.rescued} attempt(s) graded.`)
      setState('done')

      // Reload the dashboard after a short pause so new scores appear
      setTimeout(() => router.refresh(), 1200)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Something went wrong.')
      setState('error')
    }
  }

  const label = setNumber !== undefined ? `Grade Set ${setNumber}` : 'Grade All'

  if (compact) {
    if (state === 'loading') {
      return <span className="text-xs text-slate-400 italic">Grading…</span>
    }
    if (state === 'done') {
      return <span className="text-xs text-green-700 font-medium">✓ Graded</span>
    }
    return (
      <button
        onClick={handleReset}
        className="text-xs text-amber-600 hover:text-amber-800 font-medium underline"
      >
        Grade now →
      </button>
    )
  }

  // Full button variant (used in the banner)
  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={handleReset}
        disabled={state === 'loading' || state === 'done'}
        className={`whitespace-nowrap px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
          state === 'done'
            ? 'bg-green-100 text-green-800 cursor-default'
            : state === 'loading'
            ? 'bg-amber-100 text-amber-700 cursor-not-allowed'
            : 'bg-amber-500 hover:bg-amber-600 text-white'
        }`}
      >
        {state === 'loading'
          ? '⏳ Grading…'
          : state === 'done'
          ? '✓ Done — refreshing…'
          : `⚡ ${label}`}
      </button>
      {message && (
        <p
          className={`text-xs max-w-xs text-right ${
            state === 'error' ? 'text-red-600' : 'text-green-700'
          }`}
        >
          {message}
        </p>
      )}
    </div>
  )
}
