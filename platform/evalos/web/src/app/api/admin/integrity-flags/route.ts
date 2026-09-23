import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool, { setTenantContext } from '@/lib/db'

export const dynamic = 'force-dynamic'

/**
 * GET /api/admin/integrity-flags
 *
 * Returns all quiz_attempts where requires_review = true, ordered by
 * trust_score ASC (lowest trust first) for human-review triage.
 *
 * Source: §5 Layer 1 — Risk-Based Proctoring, §8 Phase 3 of ARCH-EVALOS-2026-V2
 *   "flag-then-human, never auto-fail"
 *
 * Admin-only — requires i3-admin Keycloak realm role.
 */
export async function GET() {
  const session = await getServerSession(authOptions)
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }
  if (!session.user.isAdmin) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const tenantId =
    (session.user as { tenant_id?: string }).tenant_id ??
    '00000000-0000-0000-0000-000000000002'

  const client = await pool.connect()
  try {
    // HC-4: set RLS context
    await setTenantContext(client, tenantId)

    const { rows } = await client.query(
      `SELECT
         qa.id                                  AS attempt_id,
         qa.student_id,
         e.title                                AS exam_title,
         e.code                                 AS exam_code,
         qa.status,
         qa.pct_score,
         qa.passed,
         qa.started_at,
         qa.submitted_at,
         ROUND(qa.trust_score::numeric, 1)      AS trust_score,
         ROUND(qa.identity_score::numeric, 1)   AS identity_score,
         ROUND(qa.behavior_score::numeric, 1)   AS behavior_score,
         ROUND(qa.integrity_confidence::numeric, 1) AS integrity_confidence,
         COALESCE(qa.focus_lost_count, 0)       AS focus_lost_count,
         COALESCE(qa.fullscreen_exits, 0)       AS fullscreen_exits,
         COALESCE(qa.clipboard_events, 0)       AS clipboard_events,
         jsonb_array_length(
           COALESCE(qa.tab_switch_events, '[]'::jsonb)
         )                                      AS tab_switch_count,
         qa.device_fingerprint IS NOT NULL      AS has_device_fingerprint,
         qa.proctor_flags
       FROM quiz_attempts qa
       JOIN exams e ON e.id = qa.exam_id
       WHERE qa.requires_review = true
       ORDER BY qa.trust_score ASC NULLS FIRST,
                qa.submitted_at DESC
       LIMIT 200`
    )

    return NextResponse.json({
      total: rows.length,
      items: rows,
    })
  } finally {
    client.release()
  }
}

/**
 * PATCH /api/admin/integrity-flags
 *
 * Admin adjudication: clear or escalate a flagged attempt.
 * Body: { attemptId: string, action: "clear" | "void" | "escalate" }
 */
export async function PATCH(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }
  if (!session.user.isAdmin) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  const body = await req.json().catch(() => null)
  const { attemptId, action } = body ?? {}

  if (!attemptId || !['clear', 'void', 'escalate'].includes(action)) {
    return NextResponse.json(
      { error: 'attemptId and action (clear|void|escalate) are required' },
      { status: 400 }
    )
  }

  const tenantId =
    (session.user as { tenant_id?: string }).tenant_id ??
    '00000000-0000-0000-0000-000000000002'
  const reviewedBy = session.user.email ?? session.user.userId ?? 'admin'

  const client = await pool.connect()
  try {
    await setTenantContext(client, tenantId)

    if (action === 'clear') {
      // Reviewer is satisfied: remove flag, keep scores as-is
      await client.query(
        `UPDATE quiz_attempts
         SET requires_review = false,
             proctor_flags   = proctor_flags || $1::jsonb
         WHERE id = $2`,
        [
          JSON.stringify({
            review_cleared_by: reviewedBy,
            review_cleared_at: new Date().toISOString(),
          }),
          attemptId,
        ]
      )
    } else if (action === 'void') {
      // Reviewer confirms misconduct: void the attempt
      await client.query(
        `UPDATE quiz_attempts
         SET status          = 'voided',
             requires_review = false,
             proctor_flags   = proctor_flags || $1::jsonb
         WHERE id = $2`,
        [
          JSON.stringify({
            voided_by: reviewedBy,
            voided_at: new Date().toISOString(),
            reason: 'integrity_violation_confirmed',
          }),
          attemptId,
        ]
      )
    } else {
      // escalate: keep requires_review=true, log the escalation
      await client.query(
        `UPDATE quiz_attempts
         SET proctor_flags = proctor_flags || $1::jsonb
         WHERE id = $2`,
        [
          JSON.stringify({
            escalated_by: reviewedBy,
            escalated_at: new Date().toISOString(),
          }),
          attemptId,
        ]
      )
    }

    return NextResponse.json({ ok: true, action, attemptId })
  } finally {
    client.release()
  }
}
