import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool, { setTenantContext } from '@/lib/db'

export const dynamic = 'force-dynamic'

/**
 * GET /api/cert-readiness/[attemptId]
 *
 * Computes a certification-readiness band for a completed attempt, based on:
 *   - Domain-level percentage scores
 *   - Pass threshold configuration
 *   - Historical attempt trend (previous attempts on same exam)
 *
 * Readiness bands: READY · ALMOST_READY · NEEDS_PREPARATION · NOT_READY
 *
 * Source: §6.2 Certification Agent — "Ready / Almost Ready / Not Ready decision
 * plus concrete next actions", ARCH-EVALOS-2026-V2
 * HC-4: RLS set on every query.
 */

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function computeReadiness(
  pctScore: number,
  passThreshold: number,
  weakDomains: { domain: string; pct: number }[],
  attempts: number
): { band: string; predictedPassProb: number; nextActions: string[] } {
  const gap = passThreshold - pctScore
  const nextActions: string[] = []

  // Predicted pass probability using logistic curve
  const predictedPassProb = Math.min(0.99, Math.max(0.01,
    1 / (1 + Math.exp(-((pctScore - passThreshold) / 10)))
  ))

  if (pctScore >= passThreshold) {
    nextActions.push('You have met the pass threshold — book your certification exam now.')
    return { band: 'READY', predictedPassProb, nextActions }
  }

  if (gap <= 8) {
    weakDomains.slice(0, 3).forEach(d => {
      nextActions.push(`Focus 2 hours on "${d.domain}" (current: ${d.pct}%)`)
    })
    nextActions.push('Retake after targeted revision — you are very close.')
    return { band: 'ALMOST_READY', predictedPassProb, nextActions }
  }

  if (gap <= 20) {
    weakDomains.slice(0, 4).forEach(d => {
      nextActions.push(`Study "${d.domain}" in depth (current: ${d.pct}%)`)
    })
    if (attempts < 3) {
      nextActions.push('Complete 2 more full practice sets before retaking.')
    }
    return { band: 'NEEDS_PREPARATION', predictedPassProb, nextActions }
  }

  nextActions.push('Review the IBM watsonx Orchestrate study guide from the beginning.')
  weakDomains.forEach(d => {
    nextActions.push(`"${d.domain}": ${d.pct}% — requires fundamental study`)
  })
  nextActions.push('Complete all 6 practice sets before attempting again.')
  return { band: 'NOT_READY', predictedPassProb, nextActions }
}

export async function GET(
  _req: Request,
  { params }: { params: { attemptId: string } }
) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { attemptId } = params
  if (!UUID_RE.test(attemptId)) {
    return NextResponse.json({ error: 'Invalid attempt ID' }, { status: 400 })
  }

  const userId   = session.user.userId || session.user.email || ''
  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'

  const client = await pool.connect()
  try {
    await setTenantContext(client, tenantId)

    // Fetch attempt + exam metadata
    const { rows } = await client.query(
      `SELECT qa.id, qa.pct_score, qa.passed, qa.proctor_flags, qa.exam_id,
              e.code AS exam_code, e.title AS exam_title,
              COALESCE(e.pass_threshold, 70) AS pass_threshold
       FROM quiz_attempts qa
       JOIN exams e ON e.id = qa.exam_id
       WHERE qa.id = $1 AND qa.student_id = $2
         AND qa.status IN ('submitted','graded')`,
      [attemptId, userId]
    )

    if (rows.length === 0) {
      return NextResponse.json({ error: 'Attempt not found or not yet graded' }, { status: 404 })
    }

    const row = rows[0]
    const pctScore      = parseFloat(row.pct_score) || 0
    const passThreshold = parseFloat(row.pass_threshold) || 70

    // Extract domain breakdown from proctor_flags (stored by submit route)
    const domainBreakdown: { domain: string; pct: number }[] =
      (row.proctor_flags as Array<Record<string, unknown>>)
        ?.flatMap(f => {
          if (f && typeof f === 'object' && Array.isArray(f['domain_breakdown'])) {
            return (f['domain_breakdown'] as Array<{ domain: string; pct: number }>)
              .filter(d => d.pct < passThreshold)
              .sort((a, b) => a.pct - b.pct)
          }
          return []
        }) ?? []

    // Count historical attempts on this exam
    const { rows: histRows } = await client.query(
      `SELECT COUNT(*)::int AS total FROM quiz_attempts
       WHERE exam_id = $1 AND student_id = $2
         AND status IN ('submitted','graded')`,
      [row.exam_id, userId]
    )
    const attemptCount: number = histRows[0]?.total ?? 1

    const { band, predictedPassProb, nextActions } = computeReadiness(
      pctScore, passThreshold, domainBreakdown, attemptCount
    )

    // Persist readiness score
    client.query(
      `INSERT INTO cert_readiness_scores
         (tenant_id, candidate_id, exam_id, attempt_id, readiness_band,
          predicted_pass_prob, weak_domains, next_actions)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`,
      [
        tenantId, userId, row.exam_id, attemptId,
        band, predictedPassProb,
        JSON.stringify(domainBreakdown),
        JSON.stringify(nextActions),
      ]
    ).catch(() => { /* best-effort */ })

    return NextResponse.json({
      attempt_id:          attemptId,
      exam_code:           row.exam_code,
      exam_title:          row.exam_title,
      score:               pctScore,
      pass_threshold:      passThreshold,
      readiness_band:      band,
      predicted_pass_prob: Math.round(predictedPassProb * 100),
      weak_domains:        domainBreakdown.slice(0, 5),
      next_actions:        nextActions,
      attempt_number:      attemptCount,
    })
  } finally {
    client.release()
  }
}
