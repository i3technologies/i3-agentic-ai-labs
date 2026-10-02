import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool, { setTenantContext } from '@/lib/db'

export const dynamic = 'force-dynamic'

/**
 * POST /api/admin/reset-stuck
 *
 * Grades ALL stuck attempts for the current tenant (or a specific set):
 *   - status = 'in_progress'    (student started but never submitted)
 *   - status = 'grading'        (submitted, pod died mid-grade)
 *   - status = 'grading_failed' (previously rescued, still ungraded)
 *
 * Uses the same inline gradeInline logic from the submit route.
 * Returns a summary of how many attempts were rescued.
 *
 * Body (optional):
 *   { setNumber?: number }  — when provided, restricts rescue to that exam set.
 *
 * Admin-only endpoint (requires session.user.isAdmin = true).
 * Non-admin users with a valid session can also call this to rescue
 * their OWN stuck attempts (scoped to student_id).
 */

interface QuestionSnap {
  id: string
  type: string
  question_type: string
  correct_answers: string[]
  domain_number: number
  domain_name: string
}

function gradeInline(
  snapshot: QuestionSnap[],
  answersRaw: Record<string, unknown>,
  passThreshold: number
): { score: number; max_score: number; pct_score: number; passed: boolean } {
  let correctCount = 0
  const total = snapshot.length

  for (const q of snapshot) {
    const selected = answersRaw[q.id] ?? null
    const isMr =
      q.type?.toUpperCase() === 'MR' ||
      ['mr', 'multiple_response', 'multi_select'].includes(
        q.question_type?.toLowerCase() ?? ''
      )

    let isCorrect = false
    if (isMr) {
      if (Array.isArray(selected) && selected.length > 0) {
        const given = [...selected]
          .map(String)
          .map((s) => s.toUpperCase())
          .sort()
        const expected = [...q.correct_answers]
          .map((s) => s.toUpperCase())
          .sort()
        isCorrect = JSON.stringify(given) === JSON.stringify(expected)
      }
    } else {
      if (selected !== null && selected !== undefined) {
        if (typeof selected === 'string') {
          isCorrect =
            selected.toUpperCase() ===
            (q.correct_answers[0] ?? '').toUpperCase()
        } else if (typeof selected === 'number') {
          isCorrect = selected === parseInt(q.correct_answers[0] ?? '-1', 10)
        }
      }
    }

    if (isCorrect) correctCount += 1
  }

  const pct = total > 0 ? (correctCount / total) * 100 : 0
  return {
    score: correctCount,
    max_score: total,
    pct_score: Math.round(pct * 10000) / 10000,
    passed: pct >= passThreshold,
  }
}

export async function POST(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const isAdmin = !!(session.user as { isAdmin?: boolean }).isAdmin
  const userId = session.user.userId || session.user.email || ''
  const tenantId =
    (session.user as { tenant_id?: string }).tenant_id ||
    '00000000-0000-0000-0000-000000000002'

  // Parse optional body: { setNumber?: number }
  let setNumber: number | null = null
  try {
    const body = await req.json().catch(() => ({}))
    if (body && typeof body.setNumber === 'number' && body.setNumber > 0) {
      setNumber = body.setNumber
    }
  } catch {
    // ignore — body is optional
  }

  const client = await pool.connect()
  try {
    await setTenantContext(client, tenantId)

    // Build set-filter clause when a specific set is requested
    const setFilterClause = setNumber !== null
      ? `AND e.code ~ $${isAdmin ? 1 : 2}_set_pattern`
      : ''

    // Admins rescue all stuck attempts in the tenant (optionally filtered by set).
    // Regular users rescue only their own stuck attempts.
    let stuckQuery: string
    let stuckArgs: unknown[]

    if (isAdmin) {
      stuckQuery = `
        SELECT
          qa.id,
          qa.question_snapshot,
          qa.answers,
          qa.status,
          qa.student_id,
          e.title AS exam_title,
          e.code  AS exam_code,
          COALESCE(e.pass_threshold, e.passing_score, 68)::NUMERIC(5,2) AS pass_threshold
        FROM quiz_attempts qa
        JOIN exams e ON e.id = qa.exam_id
        WHERE qa.status IN ('in_progress', 'grading', 'grading_failed')
          ${setNumber !== null ? `AND e.code ~ $1` : ''}
        ORDER BY qa.started_at ASC`
      stuckArgs = setNumber !== null ? [`SET${setNumber}$`] : []
    } else {
      stuckQuery = `
        SELECT
          qa.id,
          qa.question_snapshot,
          qa.answers,
          qa.status,
          qa.student_id,
          e.title AS exam_title,
          e.code  AS exam_code,
          COALESCE(e.pass_threshold, e.passing_score, 68)::NUMERIC(5,2) AS pass_threshold
        FROM quiz_attempts qa
        JOIN exams e ON e.id = qa.exam_id
        WHERE qa.status IN ('in_progress', 'grading', 'grading_failed')
          AND qa.student_id = $1
          ${setNumber !== null ? `AND e.code ~ $2` : ''}
        ORDER BY qa.started_at ASC`
      stuckArgs = setNumber !== null ? [userId, `SET${setNumber}$`] : [userId]
    }

    // Suppress the unused variable warning from the dynamic clause building
    void setFilterClause

    const { rows: stuck } = await client.query(stuckQuery, stuckArgs)

    if (stuck.length === 0) {
      const scope = setNumber !== null ? ` for Set ${setNumber}` : ''
      return NextResponse.json({
        ok: true,
        rescued: 0,
        message: `No stuck attempts found${scope}.`,
        attempts: [],
      })
    }

    const rescued: Array<{
      id: string
      student_id: string
      exam_code: string
      prev_status: string
      score: number
      max_score: number
      pct_score: number
      passed: boolean
    }> = []

    const now = new Date().toISOString()

    for (const row of stuck) {
      try {
        // Attempts with no question snapshot cannot be graded — mark grading_failed
        const snapshot = (row.question_snapshot as QuestionSnap[]) ?? []
        if (snapshot.length === 0) {
          await client.query(
            `UPDATE quiz_attempts
             SET status        = 'grading_failed',
                 proctor_flags = COALESCE(proctor_flags, '[]'::jsonb)
                                 || $1::jsonb
             WHERE id = $2`,
            [
              JSON.stringify([{
                graded_by:   'api/admin/reset-stuck',
                prev_status: row.status,
                graded_at:   now,
                note:        'empty snapshot — cannot grade',
              }]),
              row.id,
            ]
          )
          continue
        }

        const result = gradeInline(
          snapshot,
          (row.answers as Record<string, unknown>) ?? {},
          Number(row.pass_threshold) ?? 68
        )

        await client.query(
          `UPDATE quiz_attempts
           SET status               = 'submitted',
               submitted_at         = COALESCE(submitted_at, NOW()),
               graded_at            = NOW(),
               score                = $1,
               max_score            = $2,
               pct_score            = $3,
               passed               = $4,
               identity_score       = 100,
               behavior_score       = 100,
               integrity_confidence = 100,
               trust_score          = 100,
               requires_review      = FALSE,
               proctor_flags        = COALESCE(proctor_flags, '[]'::jsonb)
                                      || $5::jsonb
           WHERE id = $6`,
          [
            result.score,
            result.max_score,
            result.pct_score,
            result.passed,
            JSON.stringify([{
              graded_by:   'api/admin/reset-stuck',
              prev_status: row.status,
              exam_code:   row.exam_code,
              graded_at:   now,
              score:       result.score,
              max_score:   result.max_score,
              pct_score:   result.pct_score,
              note:        'inline grader — rescued via reset-stuck API',
            }]),
            row.id,
          ]
        )

        rescued.push({
          id:          row.id,
          student_id:  row.student_id,
          exam_code:   row.exam_code,
          prev_status: row.status,
          score:       result.score,
          max_score:   result.max_score,
          pct_score:   result.pct_score,
          passed:      result.passed,
        })
      } catch (err) {
        console.error(`[reset-stuck] failed to grade attempt ${row.id}:`, err)
        // Continue with remaining attempts even if one fails
      }
    }

    const scope = setNumber !== null ? ` for Set ${setNumber}` : ''
    return NextResponse.json({
      ok: true,
      rescued: rescued.length,
      total_stuck: stuck.length,
      message: `${rescued.length} of ${stuck.length} stuck attempt(s)${scope} have been graded and are now visible in your dashboard.`,
      attempts: rescued,
    })
  } finally {
    client.release()
  }
}
