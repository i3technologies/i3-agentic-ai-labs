'use client'

import { useState, useEffect, useRef } from 'react'
import dynamic from 'next/dynamic'

// Monaco Editor — loaded client-side only (no SSR)
const MonacoEditor = dynamic(() => import('@monaco-editor/react'), { ssr: false })

interface InterviewQuestion {
  id: string
  text: string
  type: 'text' | 'code'
  language?: string
  rubric: string
  timeLimit: number   // seconds
}

interface EvaluationResult {
  score: number
  maxScore: number
  passed: boolean
  feedback: string
  strengths: string[]
  improvements: string[]
  modelUsed: string
}

interface QuestionState {
  answer: string
  evaluation: EvaluationResult | null
  status: 'idle' | 'evaluating' | 'done' | 'error'
  error: string
  timeLeft: number
}

const DEFAULT_CODE_STUB: Record<string, string> = {
  javascript: `// Write your solution here
function solution() {
  // Your code
}`,
  python: `# Write your solution here
def solution():
    # Your code
    pass`,
  sql: `-- Write your SQL query here
SELECT`,
}

interface InterviewClientProps {
  examId: string
  questions: InterviewQuestion[]
  studentName: string
}

export default function InterviewClient({ examId, questions, studentName }: InterviewClientProps) {
  const [currentIdx, setCurrentIdx] = useState(0)
  const [states, setStates] = useState<QuestionState[]>(() =>
    questions.map(q => ({
      answer: q.type === 'code' ? DEFAULT_CODE_STUB[q.language ?? 'javascript'] ?? '' : '',
      evaluation: null,
      status: 'idle',
      timeLeft: q.timeLimit,
      error: '',
    }))
  )
  const [submitted, setSubmitted] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const currentQ = questions[currentIdx]
  const currentState = states[currentIdx]

  // Countdown timer for current question
  useEffect(() => {
    if (currentState.status !== 'idle' || submitted) return
    timerRef.current = setInterval(() => {
      setStates(prev => {
        const next = [...prev]
        const s = { ...next[currentIdx] }
        if (s.timeLeft <= 1) {
          clearInterval(timerRef.current!)
          return next
        }
        s.timeLeft = s.timeLeft - 1
        next[currentIdx] = s
        return next
      })
    }, 1000)
    return () => clearInterval(timerRef.current!)
  }, [currentIdx, submitted]) // eslint-disable-line react-hooks/exhaustive-deps

  function updateAnswer(value: string) {
    setStates(prev => {
      const next = [...prev]
      next[currentIdx] = { ...next[currentIdx], answer: value }
      return next
    })
  }

  function setStatus(idx: number, status: QuestionState['status'], extra?: Partial<QuestionState>) {
    setStates(prev => {
      const next = [...prev]
      next[idx] = { ...next[idx], status, ...extra }
      return next
    })
  }

  async function evaluateQuestion(idx: number) {
    const q = questions[idx]
    const s = states[idx]
    if (!s.answer.trim()) return

    clearInterval(timerRef.current!)
    setStatus(idx, 'evaluating')

    try {
      const res = await fetch('/api/interview/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          examId,
          questionId: q.id,
          questionText: q.text,
          questionType: q.type,
          language: q.language,
          studentAnswer: s.answer,
          rubric: q.rubric,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`)
      setStatus(idx, 'done', { evaluation: data })
    } catch (err) {
      setStatus(idx, 'error', { error: String(err) })
    }
  }

  function handleNext() {
    if (currentIdx < questions.length - 1) {
      setCurrentIdx(currentIdx + 1)
    } else {
      setSubmitted(true)
    }
  }

  const allEvaluated = states.every(s => s.status === 'done' || s.status === 'error')
  const totalScore = submitted
    ? Math.round(states.reduce((acc, s) => acc + (s.evaluation?.score ?? 0), 0) / questions.length)
    : 0

  if (submitted && allEvaluated) {
    return <InterviewResults questions={questions} states={states} totalScore={totalScore} studentName={studentName} />
  }

  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  const progress = Math.round(((currentIdx + (currentState.status === 'done' ? 1 : 0)) / questions.length) * 100)

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900">AI Interview Round</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Question {currentIdx + 1} of {questions.length} · {currentQ.type === 'code' ? 'Coding' : 'Technical'} Question
          </p>
        </div>
        <div className={`text-sm font-mono font-bold px-3 py-1 rounded-lg ${
          currentState.timeLeft < 60 ? 'bg-red-100 text-red-700' : 'bg-slate-100 text-slate-700'
        }`}>
          {fmt(currentState.timeLeft)}
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1.5 bg-slate-100 rounded-full mb-6">
        <div
          className="h-1.5 bg-blue-500 rounded-full transition-all"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Question card */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden mb-6">
        <div className="px-5 py-4 border-b border-slate-100 bg-slate-50">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full mr-2 ${
            currentQ.type === 'code'
              ? 'bg-purple-100 text-purple-700'
              : 'bg-blue-100 text-blue-700'
          }`}>
            {currentQ.type === 'code' ? `Code · ${currentQ.language ?? 'JS'}` : 'Technical'}
          </span>
          <span className="text-xs text-slate-400">{Math.round(currentQ.timeLimit / 60)} min limit</span>
        </div>
        <div className="px-5 py-5">
          <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">{currentQ.text}</p>
        </div>
      </div>

      {/* Answer area */}
      {currentQ.type === 'code' ? (
        <div className="border border-slate-200 rounded-xl overflow-hidden mb-6">
          <div className="px-4 py-2 bg-slate-900 flex items-center gap-2">
            <span className="text-xs text-slate-400">{currentQ.language ?? 'javascript'}</span>
          </div>
          <MonacoEditor
            height="320px"
            language={currentQ.language ?? 'javascript'}
            value={currentState.answer}
            onChange={v => updateAnswer(v ?? '')}
            theme="vs-dark"
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              lineNumbers: 'on',
              scrollBeyondLastLine: false,
              wordWrap: 'on',
              automaticLayout: true,
            }}
          />
        </div>
      ) : (
        <textarea
          value={currentState.answer}
          onChange={e => updateAnswer(e.target.value)}
          placeholder="Type your answer here…"
          rows={8}
          className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm text-slate-800 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 mb-6"
        />
      )}

      {/* Evaluation result */}
      {currentState.status === 'done' && currentState.evaluation && (
        <EvaluationCard evaluation={currentState.evaluation} />
      )}
      {currentState.status === 'error' && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 mb-6 text-sm text-red-700">
          Evaluation failed: {currentState.error}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between">
        <div className="text-xs text-slate-400">
          {currentState.status === 'evaluating' && '⏳ AI is evaluating your answer…'}
          {currentState.status === 'done' && '✓ Evaluated'}
        </div>
        <div className="flex gap-3">
          {currentState.status === 'idle' && (
            <button
              onClick={() => evaluateQuestion(currentIdx)}
              disabled={!currentState.answer.trim()}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Submit Answer
            </button>
          )}
          {currentState.status === 'done' && (
            <button
              onClick={handleNext}
              className="px-5 py-2 bg-slate-900 hover:bg-slate-800 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {currentIdx < questions.length - 1 ? 'Next Question →' : 'Finish Interview'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function EvaluationCard({ evaluation }: { evaluation: EvaluationResult }) {
  const { score, feedback, strengths, improvements } = evaluation
  const color = score >= 80 ? 'green' : score >= 60 ? 'yellow' : 'red'
  const colorClasses = {
    green:  'bg-green-50 border-green-200 text-green-800',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-800',
    red:    'bg-red-50 border-red-200 text-red-800',
  }

  return (
    <div className={`border rounded-xl px-5 py-4 mb-6 ${colorClasses[color]}`}>
      <div className="flex items-center gap-3 mb-3">
        <span className="text-2xl font-extrabold">{score}</span>
        <span className="text-sm font-medium">/100 · {score >= 60 ? '✓ Pass' : '✗ Below passing'}</span>
      </div>
      <p className="text-sm mb-3">{feedback}</p>
      {strengths.length > 0 && (
        <div className="mb-2">
          <p className="text-xs font-semibold uppercase tracking-wide mb-1">Strengths</p>
          <ul className="space-y-0.5">
            {strengths.map((s, i) => <li key={i} className="text-xs">✓ {s}</li>)}
          </ul>
        </div>
      )}
      {improvements.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide mb-1">To Improve</p>
          <ul className="space-y-0.5">
            {improvements.map((s, i) => <li key={i} className="text-xs">→ {s}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}

function InterviewResults({
  questions,
  states,
  totalScore,
  studentName,
}: {
  questions: InterviewQuestion[]
  states: QuestionState[]
  totalScore: number
  studentName: string
}) {
  const passed = totalScore >= 70
  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className={`rounded-xl p-8 mb-8 text-center ${passed ? 'bg-green-50 border border-green-200' : 'bg-orange-50 border border-orange-200'}`}>
        <div className="text-5xl font-extrabold mb-2" style={{ color: passed ? '#065f46' : '#9a3412' }}>
          {totalScore}%
        </div>
        <div className="text-lg font-semibold mb-1" style={{ color: passed ? '#065f46' : '#9a3412' }}>
          {passed ? '🎉 Interview Passed' : 'Interview Complete'}
        </div>
        <p className="text-sm text-slate-600">
          {passed
            ? `Excellent work, ${studentName}! You passed the AI Interview Round.`
            : `${studentName}, review the feedback below and try again.`}
        </p>
      </div>

      <div className="space-y-4">
        {questions.map((q, i) => {
          const s = states[i]
          return (
            <div key={q.id} className="bg-white border border-slate-200 rounded-xl overflow-hidden">
              <div className="px-5 py-3 bg-slate-50 flex items-center justify-between">
                <span className="text-sm font-semibold text-slate-700">Q{i + 1}: {q.type === 'code' ? '💻 Code' : '💬 Text'}</span>
                {s.evaluation && (
                  <span className={`text-sm font-bold ${s.evaluation.score >= 70 ? 'text-green-700' : 'text-red-600'}`}>
                    {s.evaluation.score}/100
                  </span>
                )}
              </div>
              <div className="px-5 py-4">
                <p className="text-sm text-slate-700 mb-3">{q.text.slice(0, 120)}…</p>
                {s.evaluation && <EvaluationCard evaluation={s.evaluation} />}
              </div>
            </div>
          )
        })}
      </div>

      <div className="mt-8 text-center">
        <a href="/dashboard" className="text-sm text-slate-500 hover:text-slate-700 transition-colors">
          ← Back to Dashboard
        </a>
      </div>
    </div>
  )
}
