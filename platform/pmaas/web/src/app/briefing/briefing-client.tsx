'use client'
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'

type BriefingSection = 'overview' | 'wards' | 'content' | 'sentiment' | 'plan'

const SECTIONS: { key: BriefingSection; label: string; emoji: string }[] = [
  { key: 'overview',   label: 'Executive Overview',  emoji: '📊' },
  { key: 'wards',      label: 'Ward Intelligence',   emoji: '🗺️' },
  { key: 'content',    label: 'Content Strategy',    emoji: '📣' },
  { key: 'sentiment',  label: 'Sentiment Analysis',  emoji: '💬' },
  { key: 'plan',       label: '48-Hour Action Plan', emoji: '⚡' },
]

interface BriefingResult {
  overview:   string
  wards:      string
  content:    string
  sentiment:  string
  plan:       string
  generatedAt: string
  modelUsed:  string
}

export function BriefingClient({ userName }: { userName: string }) {
  const [loading, setLoading]   = useState(false)
  const [result, setResult]     = useState<BriefingResult | null>(null)
  const [active, setActive]     = useState<BriefingSection>('overview')
  const [error, setError]       = useState<string | null>(null)
  const [question, setQuestion] = useState('')
  const [qaResult, setQaResult] = useState<string | null>(null)
  const [qaLoading, setQaLoading] = useState(false)

  async function generateBriefing() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const resp = await fetch('/api/briefing/generate', { method: 'POST' })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      setResult(data)
      setActive('overview')
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  async function askDawa() {
    if (!question.trim()) return
    setQaLoading(true)
    setQaResult(null)
    try {
      const resp = await fetch('/api/briefing/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      setQaResult(data.answer)
    } catch (e) {
      setQaResult(`Error: ${String(e)}`)
    } finally {
      setQaLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Generate button */}
      {!result && (
        <div className="stat-card flex flex-col items-center py-12 gap-4">
          <p className="text-4xl">🤖</p>
          <p className="text-gray-300 text-center max-w-md">
            Dawa will analyse your ward targets, voter data, and recent campaign activity
            to generate a personalised strategy briefing.
          </p>
          <button
            onClick={generateBriefing}
            disabled={loading}
            className="btn-primary px-8 py-3 text-base disabled:opacity-50"
          >
            {loading ? 'Generating briefing…' : 'Generate Today\'s Briefing'}
          </button>
          {error && <p className="text-red-400 text-sm">{error}</p>}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="stat-card animate-pulse flex items-center gap-3 py-8 justify-center">
          <span className="text-gray-400 text-sm">Dawa is analysing your campaign data…</span>
        </div>
      )}

      {/* Briefing result */}
      {result && !loading && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-xs text-gray-500">
              Generated {new Date(result.generatedAt).toLocaleTimeString()} via {result.modelUsed}
            </p>
            <button onClick={generateBriefing} className="btn-secondary text-xs">
              Refresh
            </button>
          </div>

          {/* Section tabs */}
          <div className="flex flex-wrap gap-2">
            {SECTIONS.map(s => (
              <button
                key={s.key}
                onClick={() => setActive(s.key)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors
                  ${active === s.key
                    ? 'bg-green-900/60 text-green-300 border border-green-800'
                    : 'bg-gray-800 text-gray-400 hover:text-gray-200'
                  }`}
              >
                {s.emoji} {s.label}
              </button>
            ))}
          </div>

          {/* Active section content */}
          <div className="stat-card prose prose-invert prose-sm max-w-none">
            <ReactMarkdown>{result[active]}</ReactMarkdown>
          </div>

          {/* Manifesto Q&A */}
          <div className="stat-card space-y-3">
            <h3 className="text-sm font-semibold text-gray-300">Ask Dawa About the Manifesto</h3>
            <div className="flex gap-2">
              <input
                type="text"
                value={question}
                onChange={e => setQuestion(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && askDawa()}
                placeholder="e.g. What is our water policy for Mwea Ward?"
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-green-700"
              />
              <button
                onClick={askDawa}
                disabled={qaLoading || !question.trim()}
                className="btn-primary disabled:opacity-50"
              >
                {qaLoading ? '…' : 'Ask'}
              </button>
            </div>
            {qaResult && (
              <div className="bg-gray-800/50 rounded-lg p-3 text-sm text-gray-300">
                <ReactMarkdown>{qaResult}</ReactMarkdown>
              </div>
            )}
          </div>

          {/* Re-generate */}
          <div className="text-center">
            <button onClick={generateBriefing} className="btn-secondary">
              Generate New Briefing
            </button>
          </div>
        </>
      )}
    </div>
  )
}
