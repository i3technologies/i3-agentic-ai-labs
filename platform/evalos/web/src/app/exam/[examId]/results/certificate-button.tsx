'use client'

import { useState } from 'react'

export default function CertificateButton({ attemptId }: { attemptId: string }) {
  const [state, setState] = useState<'idle' | 'issuing' | 'ready' | 'error'>('idle')
  const [verifyCode, setVerifyCode] = useState<string | null>(null)

  const handleIssue = async () => {
    setState('issuing')
    try {
      // Issue / retrieve cert
      const issueRes = await fetch(`/api/certificate/${attemptId}`, { method: 'POST' })
      if (!issueRes.ok) throw new Error('Failed to issue certificate')
      const { verifyCode: code } = await issueRes.json()
      setVerifyCode(code)
      setState('ready')
    } catch {
      setState('error')
    }
  }

  const handleDownload = () => {
    window.open(`/api/certificate/${attemptId}`, '_blank')
  }

  if (state === 'idle') {
    return (
      <button
        onClick={handleIssue}
        className="px-6 py-2.5 bg-green-600 hover:bg-green-700 text-white text-sm font-semibold rounded-lg transition-colors flex items-center gap-2"
      >
        🏆 Get Certificate
      </button>
    )
  }

  if (state === 'issuing') {
    return (
      <button disabled className="px-6 py-2.5 bg-green-100 text-green-700 text-sm font-medium rounded-lg cursor-not-allowed">
        Issuing…
      </button>
    )
  }

  if (state === 'ready' && verifyCode) {
    return (
      <div className="flex flex-wrap gap-2 items-center justify-center">
        <button
          onClick={handleDownload}
          className="px-6 py-2.5 bg-green-600 hover:bg-green-700 text-white text-sm font-semibold rounded-lg transition-colors flex items-center gap-2"
        >
          📄 Download Certificate
        </button>
        <a
          href={`/verify/${verifyCode}`}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-slate-500 hover:text-slate-700 underline"
        >
          Verify: {verifyCode}
        </a>
      </div>
    )
  }

  return (
    <button
      onClick={handleIssue}
      className="px-6 py-2.5 border border-red-300 text-red-600 text-sm font-medium rounded-lg"
    >
      Retry certificate
    </button>
  )
}
