import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool, { setTenantContext } from '@/lib/db'

export const dynamic = 'force-dynamic'

/**
 * GET /api/passport/[candidateId]
 *
 * Returns the Skills Passport for a candidate — a portable professional identity
 * containing multi-dimensional proficiency scores, verifiable credentials,
 * and an employability mapping layer.
 *
 * Access control:
 *   - The candidate themselves (session.user.userId match)
 *   - Any i3-admin
 *   - Public share link (via ?token=<public_token>)
 *
 * Source: §5 Layer 6, §10 Phase 3 — ARCH-EVALOS-2026-V2
 * HC-4: tenant_id scoped on all queries.
 */

const UUID_LIKE_RE = /^[a-zA-Z0-9_@.-]{1,128}$/

export async function GET(
  req: Request,
  { params }: { params: { candidateId: string } }
) {
  const { candidateId } = params
  if (!UUID_LIKE_RE.test(candidateId)) {
    return NextResponse.json({ error: 'Invalid candidate ID' }, { status: 400 })
  }

  const { searchParams } = new URL(req.url)
  const shareToken = searchParams.get('token') ?? null

  const session = await getServerSession(authOptions)
  const tenantId = (session?.user as { tenant_id?: string } | undefined)?.tenant_id
    ?? '00000000-0000-0000-0000-000000000002'

  const client = await pool.connect()
  try {
    await setTenantContext(client, tenantId)

    // Determine access: self, admin, or public share token
    const isSelf  = session?.user?.userId === candidateId ||
                    session?.user?.email === candidateId
    const isAdmin = session?.user?.isAdmin ?? false

    let passport: Record<string, unknown> | null = null

    if (shareToken) {
      // Public share link access
      const { rows } = await client.query(
        `SELECT * FROM skills_passports
         WHERE candidate_id = $1 AND public_token = $2 AND is_public = true`,
        [candidateId, shareToken]
      )
      passport = rows[0] ?? null
    } else if (isSelf || isAdmin) {
      const { rows } = await client.query(
        `SELECT * FROM skills_passports WHERE candidate_id = $1`,
        [candidateId]
      )
      passport = rows[0] ?? null
    } else {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
    }

    // If no passport exists yet, build it on-the-fly from skill evidence
    if (!passport) {
      const { rows: evidenceRows } = await client.query(
        `SELECT sn.name AS skill_name, sn.level, cse.proficiency, cse.evidence_type,
                cse.recorded_at
         FROM candidate_skill_evidence cse
         JOIN skill_nodes sn ON sn.id = cse.skill_id
         WHERE cse.candidate_id = $1
         ORDER BY cse.recorded_at DESC`,
        [candidateId]
      )

      const { rows: credRows } = await client.query(
        `SELECT ci.verification_code, bc.name AS badge_name,
                ci.score_pct, ci.issued_on, ci.expires_on, ci.is_revoked
         FROM credential_issuances ci
         JOIN badge_classes bc ON bc.id = ci.badge_class_id
         WHERE ci.candidate_id = $1 AND ci.is_revoked = false
         ORDER BY ci.issued_on DESC`,
        [candidateId]
      )

      return NextResponse.json({
        candidate_id:   candidateId,
        passport_exists: false,
        skill_evidence:  evidenceRows,
        credentials:     credRows,
        message:         'Passport not yet generated — showing raw evidence. POST /api/passport/build to generate.',
      })
    }

    // Load credentials and skill evidence to augment passport
    const { rows: credRows } = await client.query(
      `SELECT ci.verification_code, bc.name AS badge_name,
              ci.score_pct, ci.issued_on, ci.expires_on
       FROM credential_issuances ci
       JOIN badge_classes bc ON bc.id = ci.badge_class_id
       WHERE ci.candidate_id = $1 AND ci.is_revoked = false
       ORDER BY ci.issued_on DESC`,
      [candidateId]
    )

    const { rows: skillRows } = await client.query(
      `SELECT sn.name AS skill, sn.level, ROUND(cse.proficiency::numeric, 1) AS proficiency,
              cse.evidence_type
       FROM candidate_skill_evidence cse
       JOIN skill_nodes sn ON sn.id = cse.skill_id
       WHERE cse.candidate_id = $1
       ORDER BY cse.proficiency DESC`,
      [candidateId]
    )

    return NextResponse.json({
      candidate_id:     passport.candidate_id,
      candidate_name:   passport.candidate_name,
      tier:             passport.tier,
      skill_summary:    passport.skill_summary,
      employability:    passport.employability,
      credential_count: credRows.length,
      credentials:      credRows,
      skills:           skillRows,
      is_public:        passport.is_public,
      last_updated_at:  passport.last_updated_at,
    })
  } finally {
    client.release()
  }
}
