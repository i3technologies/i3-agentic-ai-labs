import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { z } from 'zod'
import { randomBytes } from 'crypto'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

/**
 * POST /api/badges/issue
 *
 * Issues an Open Badges 3.0 OpenBadgeCredential to a candidate who has
 * met the minimum score requirement for a badge class.
 *
 * The issued credential is stored in credential_issuances and the
 * ob3_credential JSONB field contains the full OB3 payload for serving
 * at /api/verify/[code].
 *
 * Source: §5 Layer 6, §2.1 of ARCH-EVALOS-2026-V2
 * HC-4: tenant_id propagated on all queries.
 */

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const IssueSchema = z.object({
  attempt_id:      z.string().regex(UUID_RE),
  badge_class_slug: z.string().min(1),
})

function generateVerificationCode(): string {
  return randomBytes(12).toString('base64url').slice(0, 16).toUpperCase()
}

function buildOB3Credential(params: {
  credentialId: string
  verificationCode: string
  badgeName: string
  badgeDescription: string
  issuerName: string
  issuerUrl: string
  issuerEmail: string
  candidateName: string
  candidateEmail: string
  issuedOn: string
  expiresOn?: string
  scoreEvidence: number
  criteriaUrl?: string
  imageUrl?: string
  alignment: unknown[]
}): Record<string, unknown> {
  return {
    '@context': [
      'https://www.w3.org/2018/credentials/v1',
      'https://purl.imsglobal.org/spec/ob/v3p0/context-3.0.3.json',
    ],
    id: params.credentialId,
    type: ['VerifiableCredential', 'OpenBadgeCredential'],
    issuer: {
      id: params.issuerUrl,
      type: 'Profile',
      name: params.issuerName,
      email: params.issuerEmail,
      url: params.issuerUrl,
    },
    issuanceDate: params.issuedOn,
    ...(params.expiresOn ? { expirationDate: params.expiresOn } : {}),
    credentialSubject: {
      type: 'AchievementSubject',
      identifier: {
        type: 'emailAddress',
        identityHash: params.candidateEmail,
      },
      name: params.candidateName,
      achievement: {
        id:   `${params.issuerUrl}/badges/${params.verificationCode}`,
        type: 'Achievement',
        name: params.badgeName,
        description: params.badgeDescription,
        criteria: { narrative: params.criteriaUrl ?? params.badgeDescription },
        ...(params.imageUrl ? { image: { id: params.imageUrl, type: 'Image' } } : {}),
        alignment: params.alignment,
      },
      result: [
        {
          type: 'Result',
          resultDescription: 'Assessment score',
          value: String(params.scoreEvidence),
          status: 'Completed',
        },
      ],
    },
    verificationCode: params.verificationCode,
  }
}

export async function POST(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await req.json().catch(() => null)
  const parsed = IssueSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Invalid request', details: parsed.error.flatten() },
      { status: 400 }
    )
  }

  const { attempt_id, badge_class_slug } = parsed.data
  const userId   = session.user.userId || session.user.email || ''
  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'

  const client = await pool.connect()
  try {
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])

    // Fetch badge class
    const { rows: badgeRows } = await client.query(
      `SELECT * FROM badge_classes WHERE slug = $1 AND is_active = true`,
      [badge_class_slug]
    )
    if (badgeRows.length === 0) {
      return NextResponse.json({ error: 'Badge class not found' }, { status: 404 })
    }
    const badge = badgeRows[0]

    // Fetch attempt to verify eligibility
    const { rows: attemptRows } = await client.query(
      `SELECT qa.id, qa.student_id, qa.pct_score, qa.passed,
              e.pass_threshold
       FROM quiz_attempts qa
       JOIN exams e ON e.id = qa.exam_id
       WHERE qa.id = $1 AND qa.student_id = $2
         AND qa.status IN ('submitted','graded')`,
      [attempt_id, userId]
    )
    if (attemptRows.length === 0) {
      return NextResponse.json({ error: 'Attempt not found or not graded' }, { status: 404 })
    }

    const attempt = attemptRows[0]
    const pctScore = parseFloat(attempt.pct_score) || 0

    if (pctScore < badge.min_score) {
      return NextResponse.json(
        {
          error: 'score_below_threshold',
          message: `Minimum score for this badge is ${badge.min_score}%. You scored ${pctScore.toFixed(1)}%.`,
          required: badge.min_score,
          achieved: pctScore,
        },
        { status: 422 }
      )
    }

    // Check if already issued
    const { rows: existing } = await client.query(
      `SELECT id, verification_code FROM credential_issuances
       WHERE badge_class_id = $1 AND candidate_id = $2 AND is_revoked = false`,
      [badge.id, userId]
    )
    if (existing.length > 0) {
      return NextResponse.json({
        ok: true,
        already_issued: true,
        verification_code: existing[0].verification_code,
        credential_id: existing[0].id,
      })
    }

    // Generate credential
    const verificationCode = generateVerificationCode()
    const credentialId     = `https://credentials.i3technologies.co.ke/badges/${verificationCode}`
    const issuedOn         = new Date().toISOString()
    const expiresOn        = new Date(Date.now() + 3 * 365 * 24 * 60 * 60 * 1000).toISOString()

    const candidateName  = session.user.name ?? userId
    const candidateEmail = session.user.email ?? userId

    const ob3Credential = buildOB3Credential({
      credentialId,
      verificationCode,
      badgeName:       badge.name,
      badgeDescription: badge.description,
      issuerName:      badge.issuer_name,
      issuerUrl:       badge.issuer_url,
      issuerEmail:     badge.issuer_email,
      candidateName,
      candidateEmail,
      issuedOn,
      expiresOn,
      scoreEvidence: Math.round(pctScore),
      criteriaUrl:   badge.criteria_url,
      imageUrl:      badge.image_url,
      alignment:     badge.alignment ?? [],
    })

    const { rows: issued } = await client.query(
      `INSERT INTO credential_issuances
         (tenant_id, badge_class_id, candidate_id, candidate_email, candidate_name,
          attempt_id, score_pct, performance_band, skill_vector,
          credential_id, issued_on, expires_on, verification_code, ob3_credential)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
       RETURNING id, verification_code`,
      [
        tenantId, badge.id, userId, candidateEmail, candidateName,
        attempt_id, pctScore, null, JSON.stringify({}),
        credentialId, issuedOn, expiresOn, verificationCode,
        JSON.stringify(ob3Credential),
      ]
    )

    return NextResponse.json({
      ok: true,
      credential_id:     issued[0].id,
      verification_code: issued[0].verification_code,
      badge_name:        badge.name,
      issued_on:         issuedOn,
      expires_on:        expiresOn,
      verify_url:        `https://evalos.i3technologies.co.ke/verify/${verificationCode}`,
      ob3_credential:    ob3Credential,
    })
  } finally {
    client.release()
  }
}
