'use client'

import { useState } from 'react'

interface GeneratedQuestion {
  text: string
  type: 'SC' | 'MR'
  options: { label: string; text: string }[]
  correct_answers: string[]
  explanation: string
  domain_name: string
  topic: string
  set_number: number
  is_active: boolean
}

interface GeneratorFormState {
  topic: string
  domain: string
  setNumber: string
  count: string
  difficulty: 'easy' | 'medium' | 'hard'
  questionTypes: ('SC' | 'MR')[]
}

interface SaveResult {
  saved: number
  ids: string[]
}

export default function QuestionGeneratorPanel() {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<GeneratorFormState>({
    topic: '',
    domain: '',
    setNumber: '1',
    count: '3',
    difficulty: 'medium',
    questionTypes: ['SC', 'MR'],
  })
  const [status, setStatus] = useState<'idle' | 'generating' | 'reviewing' | 'saving' | 'saved' | 'error'>('idle')
  const isSaving = status === ('saving' as string)
  const [questions, setQuestions] = useState<GeneratedQuestion[]>([])
  const [rejected, setRejected] = useState<Set<number>>(new Set())
  const [errorMsg, setErrorMsg] = useState('')
  const [saveResult, setSaveResult] = useState<SaveResult | null>(null)

  function toggleType(t: 'SC' | 'MR') {
    setForm(f => ({
      ...f,
      questionTypes: f.questionTypes.includes(t)
        ? f.questionTypes.filter(x => x !== t)
        : [...f.questionTypes, t],
    }))
  }

  function toggleReject(i: number) {
    setRejected(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  async function generate() {
    if (!form.topic.trim() || !form.domain.trim()) {
      setErrorMsg('Topic and Domain are required.')
      setStatus('error')
      return
    }
    if (form.questionTypes.length === 0) {
      setErrorMsg('Select at least one question type.')
      setStatus('error')
      return
    }
    setStatus('generating')
    setErrorMsg('')
    setQuestions([])
    setRejected(new Set())
    setSaveResult(null)

    try {
      const res = await fetch('/api/admin/generate-questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: form.topic,
          domain: form.domain,
          setNumber: parseInt(form.setNumber),
          count: parseInt(form.count),
          difficulty: form.difficulty,
          questionTypes: form.questionTypes,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`)
      setQuestions(data.questions ?? [])
      setStatus('reviewing')
    } catch (e) {
      setErrorMsg(String(e))
      setStatus('error')
    }
  }

  async function saveApproved() {
    const approved = questions.filter((_, i) => !rejected.has(i))
    if (approved.length === 0) {
      setErrorMsg('No questions to save — un-reject at least one.')
      setStatus('error')
      return
    }
    setStatus('saving')
    setErrorMsg('')

    try {
      const res = await fetch('/api/admin/questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ questions: approved }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`)
      setSaveResult({ saved: data.saved, ids: data.ids })
      setStatus('saved')
    } catch (e) {
      setErrorMsg(String(e))
      setStatus('error')
    }
  }

  return (
    <div className="mb-6">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 px-4 py-2 bg-indigo-700 hover:bg-indigo-800 text-white text-sm font-medium rounded-lg transition-colors"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        {open ? 'Hide AI Generator' : 'AI Question Generator'}
      </button>

      {open && (
        <div className="mt-3 bg-white border border-indigo-200 rounded-xl overflow-hidden">
          {/* Panel header */}
          <div className="flex items-center gap-2 px-5 py-3.5 bg-gradient-to-r from-indigo-700 to-purple-700">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.347.384A5 5 0 0112 17.5a5 5 0 01-3.071-1.088l-.348-.383z" />
            </svg>
            <span className="text-sm font-semibold text-white">AI Question Generator</span>
            <span className="text-xs text-indigo-200 ml-1">· Powered by Qwen2.5 14B via LiteLLM</span>
          </div>

          <div className="px-5 py-5">
            {/* Form */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
              <div className="lg:col-span-2">
                <label className="block text-xs font-semibold text-slate-600 mb-1">Topic *</label>
                <input
                  value={form.topic}
                  onChange={e => setForm(f => ({ ...f, topic: e.target.value }))}
                  placeholder="e.g. watsonx Orchestrate Skill Flows and Automation Builder"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Domain *</label>
                <input
                  value={form.domain}
                  onChange={e => setForm(f => ({ ...f, domain: e.target.value }))}
                  placeholder="e.g. Building Skills and Automations"
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Exam Set</label>
                <select
                  value={form.setNumber}
                  onChange={e => setForm(f => ({ ...f, setNumber: e.target.value }))}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 bg-white"
                >
                  {[1,2,3,4,5,6].map(s => <option key={s} value={s}>SET {s}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Questions to Generate</label>
                <select
                  value={form.count}
                  onChange={e => setForm(f => ({ ...f, count: e.target.value }))}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 bg-white"
                >
                  {[1,2,3,4,5].map(n => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Difficulty</label>
                <select
                  value={form.difficulty}
                  onChange={e => setForm(f => ({ ...f, difficulty: e.target.value as GeneratorFormState['difficulty'] }))}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 bg-white"
                >
                  <option value="easy">Easy — Core recall</option>
                  <option value="medium">Medium — Applied scenarios</option>
                  <option value="hard">Hard — Synthesis &amp; edge cases</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Question Types</label>
                <div className="flex gap-3 mt-1.5">
                  {(['SC', 'MR'] as const).map(t => (
                    <label key={t} className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={form.questionTypes.includes(t)}
                        onChange={() => toggleType(t)}
                        className="rounded"
                      />
                      <span className="text-sm text-slate-700">
                        {t === 'SC' ? 'Single Choice' : 'Multiple Response'}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            {/* Generate button */}
            <div className="flex items-center gap-3 mb-5">
              <button
                onClick={generate}
                disabled={status === 'generating' || status === 'saving'}
                className="px-5 py-2 bg-indigo-700 hover:bg-indigo-800 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
              >
                {status === 'generating'
                  ? '⏳ Generating (30–90s)…'
                  : '⚡ Generate Questions'}
              </button>
              {status === 'error' && (
                <span className="text-sm text-red-600">{errorMsg}</span>
              )}
            </div>

            {/* Review panel */}
            {status === 'reviewing' && questions.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-800">
                    Review {questions.length} generated question{questions.length !== 1 ? 's' : ''}
                    <span className="ml-2 text-xs text-slate-400 font-normal">
                      All are DRAFT (inactive) until you save &amp; activate in Question Bank
                    </span>
                  </h3>
                  <button
                    onClick={saveApproved}
                    disabled={rejected.size === questions.length}
                    className="px-4 py-2 bg-green-700 hover:bg-green-800 disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors"
                  >
                    💾 Save {questions.length - rejected.size} Approved to DB
                  </button>
                </div>

                {questions.map((q, i) => (
                  <div
                    key={i}
                    className={`border rounded-xl overflow-hidden transition-opacity ${
                      rejected.has(i) ? 'opacity-40 border-red-200' : 'border-slate-200'
                    }`}
                  >
                    {/* Q header */}
                    <div className="flex items-center justify-between px-4 py-2.5 bg-slate-50 border-b border-slate-100">
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                          q.type === 'MR' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
                        }`}>{q.type}</span>
                        <span className="text-xs text-slate-500">SET{q.set_number} · {q.domain_name} · {q.topic}</span>
                      </div>
                      <button
                        onClick={() => toggleReject(i)}
                        className={`text-xs px-3 py-1 rounded-full font-medium transition-colors ${
                          rejected.has(i)
                            ? 'bg-slate-200 text-slate-600 hover:bg-green-100 hover:text-green-700'
                            : 'bg-red-100 text-red-700 hover:bg-red-200'
                        }`}
                      >
                        {rejected.has(i) ? '↩ Restore' : '✕ Reject'}
                      </button>
                    </div>

                    {/* Q body */}
                    <div className="px-4 py-3">
                      <p className="text-sm text-slate-800 mb-3 leading-relaxed">{q.text}</p>
                      <div className="space-y-1 mb-3">
                        {q.options.map(opt => {
                          const isCorrect = q.correct_answers.includes(opt.label)
                          return (
                            <div
                              key={opt.label}
                              className={`flex gap-2 items-start text-xs rounded px-2 py-1 ${
                                isCorrect ? 'bg-green-50 text-green-800' : 'text-slate-600'
                              }`}
                            >
                              <span className={`font-bold flex-shrink-0 w-4 ${isCorrect ? 'text-green-700' : 'text-slate-400'}`}>
                                {opt.label}.
                              </span>
                              <span>{opt.text}</span>
                              {isCorrect && <span className="ml-auto text-green-600 text-xs flex-shrink-0">✓ Correct</span>}
                            </div>
                          )
                        })}
                      </div>
                      {q.explanation && (
                        <div className="bg-amber-50 border border-amber-100 rounded px-3 py-2">
                          <p className="text-xs text-amber-800"><span className="font-semibold">Explanation:</span> {q.explanation}</p>
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {/* Save button (bottom) */}
                <div className="flex items-center justify-between pt-2">
                  <p className="text-xs text-slate-400">
                    Saved questions go to Question Bank as <span className="font-semibold">inactive drafts</span>.
                    Enable them individually in /admin/questions.
                  </p>
                  <button
                    onClick={saveApproved}
                    disabled={rejected.size === questions.length || isSaving}
                    className="px-5 py-2 bg-green-700 hover:bg-green-800 disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors"
                  >
                    {isSaving ? '⏳ Saving…' : `💾 Save ${questions.length - rejected.size} Questions`}
                  </button>
                </div>
              </div>
            )}

            {/* Saved confirmation */}
            {status === 'saved' && saveResult && (
              <div className="bg-green-50 border border-green-200 rounded-xl px-5 py-4 flex items-start gap-3">
                <span className="text-green-600 text-lg">✓</span>
                <div>
                  <p className="text-sm font-semibold text-green-800">
                    {saveResult.saved} question{saveResult.saved !== 1 ? 's' : ''} saved to Question Bank as drafts.
                  </p>
                  <p className="text-xs text-green-600 mt-1">
                    Activate them individually: Admin → Question Bank → filter by <em>Inactive only</em> → toggle is_active.
                  </p>
                  <button
                    onClick={() => { setStatus('idle'); setQuestions([]); setRejected(new Set()) }}
                    className="mt-2 text-xs text-green-700 underline hover:no-underline"
                  >
                    Generate more questions
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
