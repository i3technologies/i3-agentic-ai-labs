'use client'

import { useState, useCallback } from 'react'
import dynamic from 'next/dynamic'

const MonacoEditor = dynamic(() => import('@monaco-editor/react'), { ssr: false })

interface Lab {
  id: string
  title: string
  description: string
  language: 'javascript' | 'python' | 'sql'
  starterCode: string
  expectedOutput?: string
  hints: string[]
}

interface LabClientProps {
  lab: Lab
}

function RenderReview({ text }: { text: string }) {
  const lines = text.split('\n')
  const nodes: React.ReactNode[] = []
  let key = 0
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) { nodes.push(<div key={key++} className="h-2" />); continue }
    if (trimmed.startsWith('## ')) {
      nodes.push(<h3 key={key++} className="text-sm font-bold text-slate-800 mt-4 mb-1">{trimmed.slice(3)}</h3>)
    } else if (trimmed.startsWith('```')) {
      // skip fence markers — code blocks are rendered inline
    } else if (/^\d+\./.test(trimmed)) {
      nodes.push(<p key={key++} className="text-xs text-slate-700 ml-3 mb-0.5">{trimmed}</p>)
    } else {
      nodes.push(<p key={key++} className="text-xs text-slate-700 mb-1">{trimmed}</p>)
    }
  }
  return <div>{nodes}</div>
}

export default function LabClient({ lab }: LabClientProps) {
  const [code, setCode] = useState(lab.starterCode)
  const [output, setOutput] = useState('')
  const [outputErr, setOutputErr] = useState('')
  const [runStatus, setRunStatus] = useState<'idle' | 'running' | 'done'>('idle')
  const [review, setReview] = useState('')
  const [reviewStatus, setReviewStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [reviewErr, setReviewErr] = useState('')
  const [showHints, setShowHints] = useState(false)
  const [hintIdx, setHintIdx] = useState(0)

  const runCode = useCallback(async () => {
    setRunStatus('running')
    setOutput('')
    setOutputErr('')
    try {
      const res = await fetch('/api/lab/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, language: lab.language }),
      })
      const data = await res.json()
      if (!res.ok) { setOutputErr(data.error ?? `HTTP ${res.status}`); return }
      setOutput(data.stdout ?? '')
      setOutputErr(data.stderr ?? '')
    } catch (e) {
      setOutputErr(String(e))
    } finally {
      setRunStatus('done')
    }
  }, [code, lab.language])

  const getReview = useCallback(async () => {
    setReviewStatus('loading')
    setReview('')
    setReviewErr('')
    try {
      const res = await fetch('/api/lab/run?action=review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          language: lab.language,
          labContext: lab.description,
          runOutput: output,
          runError: outputErr,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`)
      setReview(data.review ?? '')
      setReviewStatus('done')
    } catch (e) {
      setReviewErr(String(e))
      setReviewStatus('error')
    }
  }, [code, lab.language, lab.description, output, outputErr])

  return (
    <div className="h-screen flex flex-col">
      {/* Top bar */}
      <div className="bg-slate-900 text-white px-4 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold bg-purple-600 text-white px-2 py-0.5 rounded">
            {lab.language.toUpperCase()}
          </span>
          <span className="text-sm font-semibold">{lab.title}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { setShowHints(true); setHintIdx(0) }}
            className="text-xs text-slate-300 hover:text-white border border-slate-600 hover:border-slate-400 rounded px-3 py-1.5 transition-colors"
          >
            💡 Hint
          </button>
          <button
            onClick={runCode}
            disabled={runStatus === 'running'}
            className="text-xs bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white rounded px-4 py-1.5 font-medium transition-colors"
          >
            {runStatus === 'running' ? '⏳ Running…' : '▶ Run'}
          </button>
          <button
            onClick={getReview}
            disabled={reviewStatus === 'loading' || !code.trim()}
            className="text-xs bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded px-4 py-1.5 font-medium transition-colors"
          >
            {reviewStatus === 'loading' ? '⏳ Reviewing…' : '🤖 AI Review'}
          </button>
        </div>
      </div>

      {/* Body: 3-column layout */}
      <div className="flex flex-1 overflow-hidden">

        {/* Left: Lab description */}
        <div className="w-72 flex-shrink-0 bg-white border-r border-slate-200 overflow-y-auto p-4">
          <h2 className="text-sm font-bold text-slate-900 mb-2">{lab.title}</h2>
          <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap">{lab.description}</p>

          {lab.expectedOutput && (
            <div className="mt-4">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Expected Output</p>
              <pre className="bg-slate-50 border border-slate-200 rounded p-2 text-xs text-green-700 overflow-x-auto">
                {lab.expectedOutput}
              </pre>
            </div>
          )}

          {/* Hints */}
          {showHints && lab.hints.length > 0 && (
            <div className="mt-4 bg-yellow-50 border border-yellow-200 rounded-lg p-3">
              <p className="text-xs font-semibold text-yellow-800 mb-1">Hint {hintIdx + 1}/{lab.hints.length}</p>
              <p className="text-xs text-yellow-700">{lab.hints[hintIdx]}</p>
              <div className="flex gap-2 mt-2">
                {hintIdx < lab.hints.length - 1 && (
                  <button
                    onClick={() => setHintIdx(hintIdx + 1)}
                    className="text-xs text-yellow-700 underline"
                  >
                    Next hint →
                  </button>
                )}
                <button onClick={() => setShowHints(false)} className="text-xs text-slate-400 underline">
                  Hide
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Centre: Monaco editor */}
        <div className="flex-1 overflow-hidden">
          <MonacoEditor
            height="100%"
            language={lab.language}
            value={code}
            onChange={v => setCode(v ?? '')}
            theme="vs-dark"
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              lineNumbers: 'on',
              scrollBeyondLastLine: false,
              wordWrap: 'off',
              automaticLayout: true,
              tabSize: 2,
            }}
          />
        </div>

        {/* Right: Output + AI Review */}
        <div className="w-80 flex-shrink-0 bg-slate-950 flex flex-col overflow-hidden">
          {/* Terminal output */}
          <div className="flex-1 overflow-y-auto p-3">
            <p className="text-xs text-slate-500 font-mono mb-2">▶ Output</p>
            {output && (
              <pre className="text-xs text-green-400 font-mono whitespace-pre-wrap">{output}</pre>
            )}
            {outputErr && (
              <pre className="text-xs text-red-400 font-mono whitespace-pre-wrap">{outputErr}</pre>
            )}
            {!output && !outputErr && runStatus !== 'running' && (
              <p className="text-xs text-slate-600 font-mono">No output yet. Click ▶ Run.</p>
            )}
            {runStatus === 'running' && (
              <p className="text-xs text-yellow-400 font-mono">Running…</p>
            )}
          </div>

          {/* AI Review panel */}
          {(reviewStatus !== 'idle') && (
            <div className="border-t border-slate-800 max-h-72 overflow-y-auto p-3">
              <p className="text-xs text-blue-400 font-semibold mb-2">🤖 AI Code Review</p>
              {reviewStatus === 'loading' && (
                <p className="text-xs text-slate-400">Analysing your code…</p>
              )}
              {reviewStatus === 'error' && (
                <p className="text-xs text-red-400">{reviewErr}</p>
              )}
              {reviewStatus === 'done' && review && (
                <div className="text-slate-200">
                  <RenderReview text={review} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
