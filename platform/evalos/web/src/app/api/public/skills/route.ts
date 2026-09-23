import { NextResponse } from 'next/server'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

/**
 * GET /api/public/skills
 *
 * Public Skills API (Assessment-as-a-Service) — Phase 3.
 * Returns the top-level skills taxonomy and, for each skill, the number of
 * public candidates who have evidence at each proficiency tier.
 *
 * This is an unauthenticated endpoint for external integrations (ATS, LMS,
 * employer portals). Tenant scoped to the default public tenant.
 *
 * Source: §10 Phase 3 — "Public Skills API (Assessment-as-a-Service)",
 *         §4.1 EvalOS API™ — ARCH-EVALOS-2026-V2
 *
 * Rate-limit: configured at API Gateway (Kong) — 100 req/min per IP.
 */

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const level  = searchParams.get('level') ?? null   // filter by taxonomy level
  const search = searchParams.get('q') ?? null        // text search

  // Public API uses default tenant; no auth, no RLS bypass needed
  const tenantId = '00000000-0000-0000-0000-000000000002'

  const client = await pool.connect()
  try {
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])

    const { rows: skillRows } = await client.query(
      `SELECT
         sn.id,
         sn.name,
         sn.level,
         sn.description,
         parent.name AS parent_skill,
         COUNT(DISTINCT cse.candidate_id)::int AS assessed_candidates,
         ROUND(AVG(cse.proficiency)::numeric, 1) AS avg_proficiency,
         -- Tier distribution
         SUM(CASE WHEN cse.proficiency >= 80 THEN 1 ELSE 0 END)::int AS advanced_count,
         SUM(CASE WHEN cse.proficiency >= 60 AND cse.proficiency < 80 THEN 1 ELSE 0 END)::int AS intermediate_count,
         SUM(CASE WHEN cse.proficiency < 60 THEN 1 ELSE 0 END)::int AS beginner_count
       FROM skill_nodes sn
       LEFT JOIN skill_nodes parent ON parent.id = sn.parent_id
       LEFT JOIN candidate_skill_evidence cse ON cse.skill_id = sn.id
       WHERE sn.tenant_id = $1
         AND ($2::text IS NULL OR sn.level = $2)
         AND ($3::text IS NULL OR sn.name ILIKE '%' || $3 || '%')
       GROUP BY sn.id, sn.name, sn.level, sn.description, parent.name
       ORDER BY sn.level, assessed_candidates DESC`,
      [tenantId, level, search]
    )

    return NextResponse.json(
      {
        version:     '1.0',
        tenant:      'i3-technologies',
        skills:      skillRows,
        count:       skillRows.length,
        docs:        'https://evalos.i3technologies.co.ke/api-docs/skills',
      },
      {
        headers: {
          'Cache-Control': 'public, max-age=300, stale-while-revalidate=60',
          'X-API-Version':  '1.0',
        },
      }
    )
  } finally {
    client.release()
  }
}
