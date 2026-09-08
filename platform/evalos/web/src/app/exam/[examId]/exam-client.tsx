'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'

interface QuestionOption {
  label: string
  text: string
}

interface Question {
  id: string
  text: string
  type: string
  question_type: string
  options: QuestionOption[]
  domain_number: number
  domain_name: string
  topic: string
}

interface Exam {
  id: string
  title: string
  code: string
  duration_secs: number
  pass_threshold: number
}

interface ExamClientProps {
  exam: Exam
  existingAttemptId: string | null
  existingSnapshot: Question[] | null
  existingAnswers: Record<string, string | string[]> | null
  existingStartedAt: string | null
}

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

export default function ExamClient({
  exam,
  existingAttemptId,
  existingSnapshot,
  existingAnswers,
  existingStartedAt,
}: ExamClientProps) {
  const router = useRouter()
  const [attemptId, setAttemptId] = useState<string | null>(existingAttemptId)
  const [questions, setQuestions] = useState<Question[]>(existingSnapshot ?? [])
  const [answers, setAnswers] = useState<Record<string, string | string[]>>(existingAnswers ?? {})
  const [currentIndex, setCurrentIndex] = useState(0)
  const [timeLeft, setTimeLeft] = useState<number>(() => {
    if (existingStartedAt) {
      const elapsed = Math.floor((Date.now() - new Date(existingStartedAt).getTime()) / 1000)
      return Math.max(0, exam.duration_secs - elapsed)
    }
    return exam.duration_secs
  })
  const [loading, setLoading] = useState(!existingAttemptId)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)
  const anticheatQueue = useRef<object[]>([])
  const flushTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  // ---- Start attempt if none exists ----
  useEffect(() => {
    if (attemptId) return
    ;(async () => {
      try {
        const res = await fetch(`/api/exam/${exam.id}/start`, { method: 'POST' })
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          if (data.error === 'attempts_exhausted') {
            setError(`You have used all ${data.max} attempts for this exam. Return to your dashboard to view your results.`)
          } else if (data.error === 'prerequisite_not_met') {
            setError(data.message ?? 'You must pass the previous set before attempting this one.')
          } else {
            setError('Failed to start exam. Please try again.')
          }
          setLoading(false)
          return
        }
        const data = await res.json()
        setAttemptId(data.attemptId)
        setQuestions(data.questions)
        setLoading(false)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to start exam')
        setLoading(false)
      }
    })()
  }, [exam.id, attemptId])

  // ---- Countdown timer ----
  useEffect(() => {
    if (timeLeft <= 0) {
      handleAutoSubmit()
      return
    }
    const id = setTimeout(() => setTimeLeft((t) => t - 1), 1000)
    return () => clearTimeout(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeLeft])

  // ---- Anti-cheat setup ----
  useEffect(() => {
    const handleVisibility = () => {
      if (document.hidden) queueEvent({ type: 'tab_switch', ts: Date.now() })
    }
    const handleBlur = () => queueEvent({ type: 'focus_lost', ts: Date.now() })
    const handleCopy = (e: ClipboardEvent) => {
      e.preventDefault()
      queueEvent({ type: 'clipboard_copy', ts: Date.now() })
    }
    const handlePaste = (e: ClipboardEvent) => {
      e.preventDefault()
      queueEvent({ type: 'clipboard_paste', ts: Date.now() })
    }
    const handleContextMenu = (e: MouseEvent) => e.preventDefault()
    const handleFullscreenChange = () => {
      if (!document.fullscreenElement) {
        queueEvent({ type: 'fullscreen_exit', ts: Date.now() })
      }
    }

    document.addEventListener('visibilitychange', handleVisibility)
    window.addEventListener('blur', handleBlur)
    document.addEventListener('copy', handleCopy)
    document.addEventListener('paste', handlePaste)
    document.addEventListener('contextmenu', handleContextMenu)
    document.addEventListener('fullscreenchange', handleFullscreenChange)

    // Request fullscreen
    document.documentElement.requestFullscreen?.().catch(() => {/* ignore */})

    // Flush anti-cheat events every 10s
    flushTimer.current = setInterval(flushAnticheat, 10000)

    return () => {
      document.removeEventListener('visibilitychange', handleVisibility)
      window.removeEventListener('blur', handleBlur)
      document.removeEventListener('copy', handleCopy)
      document.removeEventListener('paste', handlePaste)
      document.removeEventListener('contextmenu', handleContextMenu)
      document.removeEventListener('fullscreenchange', handleFullscreenChange)
      if (flushTimer.current) clearInterval(flushTimer.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attemptId])

  function queueEvent(event: object) {
    anticheatQueue.current.push(event)
  }

  const flushAnticheat = useCallback(async () => {
    if (!attemptId || anticheatQueue.current.length === 0) return
    const events = [...anticheatQueue.current]
    anticheatQueue.current = []
    try {
      await fetch(`/api/exam/${exam.id}/anticheat/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ attemptId, events }),
      })
    } catch {
      // put events back if flush failed
      anticheatQueue.current = [...events, ...anticheatQueue.current]
    }
  }, [attemptId, exam.id])

  // ---- Answer handling ----
  const handleSingleAnswer = async (questionId: string, value: string) => {
    const newAnswers = { ...answers, [questionId]: value }
    setAnswers(newAnswers)
    await saveAnswer(questionId, value)
  }

  const handleMultiAnswer = async (questionId: string, label: string, checked: boolean) => {
    const current = (answers[questionId] as string[]) ?? []
    const next = checked
      ? [...current, label].filter((v, i, a) => a.indexOf(v) === i).sort()
      : current.filter((v) => v !== label)
    const newAnswers = { ...answers, [questionId]: next }
    setAnswers(newAnswers)
    await saveAnswer(questionId, next)
  }

  const saveAnswer = async (questionId: string, value: string | string[]) => {
    if (!attemptId) return
    try {
      await fetch(`/api/exam/${exam.id}/answer`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ attemptId, questionId, answer: value }),
      })
    } catch {/* best-effort */}
  }

  // ---- Submit ----
  const handleAutoSubmit = useCallback(async () => {
    if (!attemptId || submitting) return
    setSubmitting(true)
    await flushAnticheat()
    try {
      await fetch(`/api/exam/${exam.id}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ attemptId }),
      })
      router.push(`/exam/${exam.id}/results?attemptId=${attemptId}`)
    } catch {
      setSubmitting(false)
    }
  }, [attemptId, exam.id, flushAnticheat, router, submitting])

  const handleSubmit = async () => {
    if (!attemptId || submitting) return
    setSubmitting(true)
    setShowConfirm(false)
    await flushAnticheat()
    try {
      await fetch(`/api/exam/${exam.id}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ attemptId }),
      })
      router.push(`/exam/${exam.id}/results?attemptId=${attemptId}`)
    } catch {
      setError('Submission failed. Please try again.')
      setSubmitting(false)
    }
  }

  // ---- Render ----
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-slate-500 text-sm">Loading exam...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 font-medium">{error}</p>
          <button
            onClick={() => router.push('/dashboard')}
            className="mt-4 text-sm text-blue-600 underline"
          >
            Return to dashboard
          </button>
        </div>
      </div>
    )
  }

  const question = questions[currentIndex]
  if (!question) return null

  const isMultiple =
    question.type === 'MR' ||
    question.question_type === 'multiple_response' ||
    question.question_type === 'MR'
  const answeredIds = Object.keys(answers).filter((k) => {
    const v = answers[k]
    return Array.isArray(v) ? v.length > 0 : !!v
  })
  const answeredCount = answeredIds.length
  const progressPct = questions.length > 0 ? (answeredCount / questions.length) * 100 : 0

  const currentAnswer = answers[question.id]
  const timerColor = timeLeft < 300 ? 'text-red-600' : timeLeft < 600 ? 'text-yellow-600' : 'text-slate-700'

  return (
    <div className="no-select min-h-screen bg-slate-50">
      {/* Top bar */}
      <div className="sticky top-0 z-20 bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide truncate">
              {exam.code} — {exam.title}
            </div>
            <div className="flex items-center gap-3 mt-1">
              <div className="flex-1 bg-slate-200 rounded-full h-1.5">
                <div
                  className="bg-blue-600 h-1.5 rounded-full transition-all"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
              <span className="text-xs text-slate-500 whitespace-nowrap">
                {answeredCount}/{questions.length} answered
              </span>
            </div>
          </div>

          <div className={`font-mono font-bold text-lg tabular-nums ${timerColor}`}>
            {formatTime(timeLeft)}
          </div>
        </div>
      </div>

      {/* Question */}
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="bg-white border border-slate-200 rounded-xl p-6 md:p-8">
          {/* Q header */}
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold text-blue-600 uppercase tracking-wide">
              Question {currentIndex + 1} of {questions.length}
            </span>
            <span className="text-xs text-slate-400">
              {question.domain_name}
            </span>
          </div>

          {isMultiple && (
            <p className="text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded px-2.5 py-1 inline-block mb-3">
              Select all that apply
            </p>
          )}

          <p className="text-base font-medium text-slate-900 leading-relaxed mb-6 whitespace-pre-wrap">
            {question.text}
          </p>

          {/* Options */}
          <div className="space-y-2.5">
            {question.options.map((opt) => {
              const selected = isMultiple
                ? ((currentAnswer as string[]) ?? []).includes(opt.label)
                : currentAnswer === opt.label

              return (
                <label
                  key={opt.label}
                  className={`flex items-start gap-3 p-3.5 rounded-lg border cursor-pointer transition-colors ${
                    selected
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                  }`}
                >
                  {isMultiple ? (
                    <input
                      type="checkbox"
                      className="mt-0.5 flex-shrink-0 accent-blue-600"
                      checked={selected}
                      onChange={(e) =>
                        handleMultiAnswer(question.id, opt.label, e.target.checked)
                      }
                    />
                  ) : (
                    <input
                      type="radio"
                      name={`q-${question.id}`}
                      className="mt-0.5 flex-shrink-0 accent-blue-600"
                      checked={selected}
                      onChange={() => handleSingleAnswer(question.id, opt.label)}
                    />
                  )}
                  <span className="flex gap-2 text-sm text-slate-800">
                    <span className="font-semibold text-slate-500 w-4 flex-shrink-0">
                      {opt.label}.
                    </span>
                    <span>{opt.text}</span>
                  </span>
                </label>
              )
            })}
          </div>
        </div>

        {/* Navigation */}
        <div className="mt-6 flex items-center justify-between gap-4">
          <button
            onClick={() => setCurrentIndex((i) => Math.max(0, i - 1))}
            disabled={currentIndex === 0}
            className="px-5 py-2.5 text-sm font-medium border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Previous
          </button>

          {/* Question dots (up to 12) */}
          <div className="flex gap-1.5 flex-wrap justify-center max-w-xs">
            {questions.slice(0, 12).map((q, i) => {
              const ans = answers[q.id]
              const done = Array.isArray(ans) ? ans.length > 0 : !!ans
              return (
                <button
                  key={q.id}
                  onClick={() => setCurrentIndex(i)}
                  className={`w-6 h-6 rounded text-xs font-medium transition-colors ${
                    i === currentIndex
                      ? 'bg-blue-600 text-white'
                      : done
                      ? 'bg-green-100 text-green-700 border border-green-200'
                      : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                  }`}
                >
                  {i + 1}
                </button>
              )
            })}
            {questions.length > 12 && (
              <span className="text-xs text-slate-400 self-center">
                +{questions.length - 12}
              </span>
            )}
          </div>

          {currentIndex < questions.length - 1 ? (
            <button
              onClick={() => setCurrentIndex((i) => Math.min(questions.length - 1, i + 1))}
              className="px-5 py-2.5 text-sm font-medium bg-slate-900 text-white rounded-lg hover:bg-slate-800 transition-colors"
            >
              Next
            </button>
          ) : (
            <button
              onClick={() => setShowConfirm(true)}
              disabled={submitting}
              className="px-5 py-2.5 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60 transition-colors"
            >
              Submit Exam
            </button>
          )}
        </div>

        {/* Submit shortcut if not on last question */}
        {currentIndex < questions.length - 1 && (
          <div className="mt-4 text-center">
            <button
              onClick={() => setShowConfirm(true)}
              disabled={submitting}
              className="text-sm text-slate-500 hover:text-slate-700 underline underline-offset-2"
            >
              Submit exam now
            </button>
          </div>
        )}
      </div>

      {/* Confirm modal */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="text-base font-bold text-slate-900 mb-2">Submit exam?</h3>
            <p className="text-sm text-slate-600 mb-1">
              You have answered{' '}
              <span className="font-semibold">{answeredCount}</span> of{' '}
              <span className="font-semibold">{questions.length}</span> questions.
            </p>
            {answeredCount < questions.length && (
              <p className="text-sm text-amber-700 bg-amber-50 rounded p-2 mt-2">
                {questions.length - answeredCount} question
                {questions.length - answeredCount !== 1 ? 's' : ''} unanswered. Unanswered questions count as incorrect.
              </p>
            )}
            <div className="flex gap-3 mt-5">
              <button
                onClick={() => setShowConfirm(false)}
                className="flex-1 px-4 py-2 text-sm font-medium border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50"
              >
                Continue exam
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className="flex-1 px-4 py-2 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-60"
              >
                {submitting ? 'Submitting...' : 'Submit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
