'use client'

import { useState } from 'react'

interface StudyCoachPanelProps {
  attemptId: string
  passed: boolean
  score: number
}

// Render the markdown-ish report Mistral returns
// Handles ## headings, - bullet points, plain paragraphs
function RenderReport({ text }: { text: string }) {
  const lines = text.split('\n')
  const nodes: React.ReactNode[] = []
  let key = 0

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) {
      nodes.push(<div key={key++} className="h-2" />)
    } else if (trimmed.startsWith('## ')) {
      nodes.push(
        <h3 key={key++} className="text-sm font-bold text-slate-800 mt-5 mb-2 flex items-center gap-2">
          <span className="w-1 h-4 bg-blue-500 rounded-full inline-block flex-shrink-0" />
          {trimmed.slice(3)}
        </h3>
      )
    } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      nodes.push(
        <div key={key++} className="flex gap-2 items-start text-xs text-slate-700 mb-1 ml-2">
          <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0" />
          <span>{trimmed.slice(2)}</span>
        </div>
      )
    } else if (/^\d+\./.test(trimmed)) {
      nodes.push(
        <div key={key++} className="flex gap-2 items-start text-xs text-slate-700 mb-1 ml-2">
          <span className="font-semibold text-blue-600 flex-shrink-0 w-4">{trimmed.split('.')[0]}.</span>
          <span>{trimmed.slice(trimmed.indexOf('.') + 1).trim()}</span>
        </div>
      )
    } else {
      nodes.push(
        <p key={key++} className="text-xs text-slate-700 leading-relaxed mb-1">
          {trimmed}
        </p>
      )
    }
  }

  return <div>{nodes}</div>
}

export default function StudyCoachPanel({ attemptId, passed, score }: StudyCoachPanelProps) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [report, setReport] = useState<string>('')
  const [errorMsg, setErrorMsg] = useState<string>('')
  const [elapsed, setElapsed] = useState<number>(0)

  async function fetchReport() {
    setState('loading')
    setErrorMsg('')
    const start = Date.now()

    // Tick elapsed seconds
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000)

    try {
      const res = await fetch(`/api/study-coach/${attemptId}`, { cache: 'no-store' })
      clearInterval(timer)
      setElapsed(Math.floor((Date.now() - start) / 1000))

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        const detail = data.detail || data.error || `HTTP ${res.status}`
        setErrorMsg(detail)
        setState('error')
        return
      }

      const data = await res.json()
      setReport(data.report ?? '')
      setState('done')
    } catch (e) {
      clearInterval(timer)
      setErrorMsg(String(e))
      setState('error')
    }
  }

  // Idle state — show CTA
  if (state === 'idle') {
    return (
      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-6 mb-8">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.347.384A5 5 0 0112 17.5a5 5 0 01-3.071-1.088l-.348-.383z" />
            </svg>
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-slate-800 mb-1">AI Study Coach</h3>
            <p className="text-sm text-slate-600 mb-4">
              {passed
                ? `Great work scoring ${score}%! Get a personalised study plan to push even higher for the next set.`
                : `You scored ${score}%. Get a personalised AI analysis of your weak areas and a 3-day study plan to reach 90%.`}
            </p>
            <button
              onClick={fetchReport}
              className="inline-flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Generate My Study Plan
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Loading state
  if (state === 'loading') {
    return (
      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-6 mb-8">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
            <svg className="w-5 h-5 text-blue-600 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium text-slate-700">AI Study Coach is analysing your results…</p>
            <p className="text-xs text-slate-500 mt-0.5">
              Running on-cluster LLM (Mistral 7B) · {elapsed}s elapsed · usually 30–60s
            </p>
          </div>
        </div>
      </div>
    )
  }

  // Error state
  if (state === 'error') {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-6 mb-8">
        <div className="flex items-start gap-3">
          <svg className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div className="flex-1">
            <p className="text-sm font-medium text-red-800">Study Coach unavailable</p>
            <p className="text-xs text-red-600 mt-1">{errorMsg}</p>
            <button
              onClick={fetchReport}
              className="mt-3 text-xs text-red-700 underline hover:no-underline"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Done — render report
  return (
    <div className="bg-white border border-blue-200 rounded-xl overflow-hidden mb-8">
      <div className="flex items-center justify-between px-5 py-3.5 bg-gradient-to-r from-blue-600 to-indigo-600">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.347.384A5 5 0 0112 17.5a5 5 0 01-3.071-1.088l-.348-.383z" />
          </svg>
          <span className="text-sm font-semibold text-white">AI Study Coach Report</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-blue-200">Mistral 7B · on-cluster</span>
          <button
            onClick={fetchReport}
            className="text-xs text-blue-200 hover:text-white underline hover:no-underline transition-colors"
          >
            Regenerate
          </button>
        </div>
      </div>
      <div className="px-5 py-4">
        <RenderReport text={report} />
      </div>
      <div className="px-5 py-3 border-t border-slate-100 bg-slate-50 text-xs text-slate-400">
        Generated in {elapsed}s · AI-generated content — verify against official IBM C1000-207 documentation
      </div>
    </div>
  )
}
