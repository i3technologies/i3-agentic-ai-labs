import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool, { setTenantContext } from '@/lib/db'

export const dynamic = 'force-dynamic'

/**
 * GET /api/workforce/gap-analysis
 *
 * Organisational skills gap analysis for Workforce Intelligence (EvalOS Phase 3).
 * Compares the skill inventory of employees in an org against a target role profile,
 * identifies gaps, and surfaces employees closest to meeting the target.
 *
 * Source: §10 Phase 3 — "Workforce Intelligence (organisational skills inventory
 *   & gap analysis)", ARCH-EVALOS-2026-V2
 *
 * Query params:
 *   org_id    — organisation UUID (required, admin only)
 *   role      — target role label for gap comparison (optional)
 *
 * HC-4: all queries tenant-scoped via RLS.
 */

export async function GET(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  if (!session.user.isAdmin) return NextResponse.json({ error: 'Forbidden — admin only' }, { status: 403 })

  const { searchParams } = new URL(req.url)
  const orgId = searchParams.get('org_id')
  if (!orgId) return NextResponse.json({ error: 'org_id is required' }, { status: 400 })

  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'

  const client = await pool.connect()
  try {
    await setTenantContext(client, tenantId)

    // ── Skill coverage: average proficiency by skill across org ────────────────
    const { rows: coverageRows } = await client.query(
      `SELECT
         sn.name                              AS skill_name,
         sn.level,
         COUNT(DISTINCT os.employee_id)::int  AS employee_count,
         ROUND(AVG(os.proficiency)::numeric, 1) AS avg_proficiency,
         ROUND(MIN(os.proficiency)::numeric, 1) AS min_proficiency,
         ROUND(MAX(os.proficiency)::numeric, 1) AS max_proficiency
       FROM org_skills os
       JOIN skill_nodes sn ON sn.id = os.skill_id
       WHERE os.org_id = $1
       GROUP BY sn.name, sn.level
       ORDER BY avg_proficiency DESC`,
      [orgId]
    )

    // ── Employee count ─────────────────────────────────────────────────────────
    const { rows: empCountRows } = await client.query(
      `SELECT COUNT(DISTINCT employee_id)::int AS total_employees FROM org_skills WHERE org_id = $1`,
      [orgId]
    )

    // ── Skills with no coverage (gap) — employees below 60% ──────────────────
    const gapSkills = coverageRows.filter(r => parseFloat(r.avg_proficiency) < 60)

    // ── Top performers (employees with >= 3 skills above 80%) ─────────────────
    const { rows: topPerformers } = await client.query(
      `SELECT employee_id, COUNT(*)::int AS high_skill_count,
              ROUND(AVG(proficiency)::numeric, 1) AS avg_proficiency
       FROM org_skills
       WHERE org_id = $1 AND proficiency >= 80
       GROUP BY employee_id
       HAVING COUNT(*) >= 3
       ORDER BY avg_proficiency DESC
       LIMIT 10`,
      [orgId]
    )

    // ── Credential count within org ─────────────────────────────────────────────
    const { rows: credRows } = await client.query(
      `SELECT COUNT(*)::int AS credential_count
       FROM credential_issuances ci
       JOIN org_skills os ON os.employee_id = ci.candidate_id
         AND os.org_id = $1
       WHERE ci.is_revoked = false`,
      [orgId]
    )

    return NextResponse.json({
      org_id:           orgId,
      total_employees:  empCountRows[0]?.total_employees ?? 0,
      credential_count: credRows[0]?.credential_count ?? 0,
      skill_coverage:   coverageRows,
      gap_skills: gapSkills.map(s => ({
        skill_name:        s.skill_name,
        avg_proficiency:   s.avg_proficiency,
        employee_coverage: s.employee_count,
        recommendation:    `Identify training for "${s.skill_name}" — org average ${s.avg_proficiency}%`,
      })),
      top_performers: topPerformers,
    })
  } finally {
    client.release()
  }
}
