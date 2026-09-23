import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool, { setTenantContext } from '@/lib/db'

export const dynamic = 'force-dynamic'

/**
 * GET /api/admin/analytics
 *
 * Advanced analytics and bias-audit dashboard data for EvalOS Phase 2.
 *
 * Returns:
 *   - Attempt volume and pass rate over time
 *   - Domain-level performance distribution
 *   - Integrity flag rate and review queue depth
 *   - Certification readiness band distribution
 *   - Score variance by cohort (for bias-audit)
 *
 * Source: §2.3 "Bias-audit dashboards & blind-review modes",
 *         §13 Success Metrics — ARCH-EVALOS-2026-V2
 * HC-4: all queries scoped by tenant_id via RLS.
 */

export async function GET(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  if (!session.user.isAdmin) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const tenantId =
    (session.user as { tenant_id?: string }).tenant_id ??
    '00000000-0000-0000-0000-000000000002'

  const { searchParams } = new URL(req.url)
  const daysBack = Math.min(90, Math.max(7, parseInt(searchParams.get('days') ?? '30', 10)))

  const client = await pool.connect()
  try {
    await setTenantContext(client, tenantId)

    // ── Attempt volume & pass rate by day ────────────────────────────────────
    const { rows: volumeRows } = await client.query(
      `SELECT
         DATE_TRUNC('day', submitted_at)::date AS date,
         COUNT(*)::int                          AS attempts,
         SUM(CASE WHEN passed THEN 1 ELSE 0 END)::int AS passed,
         ROUND(AVG(pct_score)::numeric, 1)     AS avg_score
       FROM quiz_attempts
       WHERE submitted_at >= NOW() - ($1 || ' days')::INTERVAL
         AND status IN ('submitted','graded')
       GROUP BY 1
       ORDER BY 1`,
      [daysBack]
    )

    // ── Domain performance distribution ──────────────────────────────────────
    const { rows: domainRows } = await client.query(
      `SELECT
         e.code AS exam_code,
         elem->>'domain' AS domain,
         ROUND(AVG((elem->>'pct')::numeric), 1) AS avg_pct,
         COUNT(*)::int AS sample_n
       FROM quiz_attempts qa
       JOIN exams e ON e.id = qa.exam_id,
       LATERAL jsonb_array_elements(
         COALESCE(
           (SELECT f->'domain_breakdown'
            FROM jsonb_array_elements(qa.proctor_flags) AS f
            WHERE f ? 'domain_breakdown'
            LIMIT 1),
           '[]'::jsonb
         )
       ) AS elem
       WHERE qa.status IN ('submitted','graded')
         AND qa.submitted_at >= NOW() - ($1 || ' days')::INTERVAL
       GROUP BY e.code, elem->>'domain'
       ORDER BY e.code, avg_pct`,
      [daysBack]
    )

    // ── Integrity metrics ─────────────────────────────────────────────────────
    const { rows: integrityRows } = await client.query(
      `SELECT
         COUNT(*)::int                                         AS total_submitted,
         SUM(CASE WHEN requires_review THEN 1 ELSE 0 END)::int AS flagged_count,
         ROUND(
           100.0 * SUM(CASE WHEN requires_review THEN 1 ELSE 0 END) / NULLIF(COUNT(*),0),
           1
         ) AS flag_rate_pct,
         ROUND(AVG(trust_score)::numeric, 1)                  AS avg_trust_score,
         SUM(CASE WHEN status = 'voided' THEN 1 ELSE 0 END)::int AS voided_count
       FROM quiz_attempts
       WHERE status IN ('submitted','graded','voided')
         AND submitted_at >= NOW() - ($1 || ' days')::INTERVAL`,
      [daysBack]
    )

    // ── Certification readiness distribution ──────────────────────────────────
    const { rows: readinessRows } = await client.query(
      `SELECT readiness_band, COUNT(*)::int AS count
       FROM cert_readiness_scores
       WHERE computed_at >= NOW() - ($1 || ' days')::INTERVAL
       GROUP BY readiness_band
       ORDER BY count DESC`,
      [daysBack]
    )

    // ── Badges issued ─────────────────────────────────────────────────────────
    const { rows: badgeRows } = await client.query(
      `SELECT bc.name AS badge_name, COUNT(*)::int AS issued
       FROM credential_issuances ci
       JOIN badge_classes bc ON bc.id = ci.badge_class_id
       WHERE ci.is_revoked = false
         AND ci.issued_on >= NOW() - ($1 || ' days')::INTERVAL
       GROUP BY bc.name
       ORDER BY issued DESC`,
      [daysBack]
    )

    // ── Score variance by cohort (bias-audit) ─────────────────────────────────
    const { rows: cohortRows } = await client.query(
      `SELECT
         cohort_id,
         COUNT(*)::int                         AS n,
         ROUND(AVG(pct_score)::numeric, 1)    AS avg_score,
         ROUND(STDDEV(pct_score)::numeric, 1) AS stddev_score,
         ROUND(MIN(pct_score)::numeric, 1)    AS min_score,
         ROUND(MAX(pct_score)::numeric, 1)    AS max_score
       FROM quiz_attempts
       WHERE cohort_id IS NOT NULL
         AND status IN ('submitted','graded')
         AND submitted_at >= NOW() - ($1 || ' days')::INTERVAL
       GROUP BY cohort_id
       ORDER BY avg_score`,
      [daysBack]
    )

    return NextResponse.json({
      period_days:         daysBack,
      attempt_volume:      volumeRows,
      domain_performance:  domainRows,
      integrity:           integrityRows[0] ?? {},
      readiness_bands:     readinessRows,
      badges_issued:       badgeRows,
      cohort_variance:     cohortRows,
    })
  } finally {
    client.release()
  }
}
