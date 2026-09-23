import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { z } from 'zod'
import { authOptions } from '@/lib/auth'
import pool, { setTenantContext } from '@/lib/db'

export const dynamic = 'force-dynamic'

/**
 * POST   /api/marketplace/listings  — create a new listing (author or admin)
 * GET    /api/marketplace/listings  — browse published listings (any authenticated user)
 *
 * Source: §10 Phase 3 — Assessment Marketplace
 *         "third-party authors sell assessments; i3 takes a 20–30% revenue share"
 *         ARCH-EVALOS-2026-V2
 * HC-4: tenant_id on all queries.
 */

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const CreateListingSchema = z.object({
  title:            z.string().min(5).max(255),
  description:      z.string().min(20).max(5000),
  price_usd:        z.number().min(0).max(9999),
  exam_id:          z.string().regex(UUID_RE).optional(),
  skill_tags:       z.array(z.string()).max(10).optional(),
  target_roles:     z.array(z.string()).max(10).optional(),
  difficulty_level: z.enum(['BEGINNER','INTERMEDIATE','ADVANCED','EXPERT']).optional(),
})

export async function POST(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const body = await req.json().catch(() => null)
  const parsed = CreateListingSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'Invalid request', details: parsed.error.flatten() },
      { status: 400 }
    )
  }

  const { title, description, price_usd, exam_id, skill_tags, target_roles, difficulty_level } = parsed.data
  const authorId = session.user.userId || session.user.email || ''
  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'

  // Platform share: 20% for admins, 25% standard, 30% for unverified authors
  const platformShare = session.user.isAdmin ? 20 : 25

  const client = await pool.connect()
  try {
    await setTenantContext(client, tenantId)

    const { rows } = await client.query(
      `INSERT INTO marketplace_listings
         (tenant_id, author_id, title, description, price_usd, platform_share,
          exam_id, skill_tags, target_roles, difficulty_level, status)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'draft')
       RETURNING id, status, created_at`,
      [
        tenantId, authorId, title, description, price_usd, platformShare,
        exam_id ?? null,
        JSON.stringify(skill_tags ?? []),
        JSON.stringify(target_roles ?? []),
        difficulty_level ?? null,
      ]
    )

    return NextResponse.json({
      ok:         true,
      listing_id: rows[0].id,
      status:     rows[0].status,
      created_at: rows[0].created_at,
      message:    'Listing created in draft. Submit for review to publish.',
    }, { status: 201 })
  } finally {
    client.release()
  }
}

export async function GET(req: Request) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { searchParams } = new URL(req.url)
  const tag     = searchParams.get('tag') ?? null
  const level   = searchParams.get('level') ?? null
  const page    = Math.max(1, parseInt(searchParams.get('page') ?? '1', 10))
  const limit   = Math.min(50, Math.max(1, parseInt(searchParams.get('limit') ?? '20', 10)))
  const offset  = (page - 1) * limit

  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'

  const client = await pool.connect()
  try {
    await setTenantContext(client, tenantId)

    const { rows } = await client.query(
      `SELECT id, title, description, price_usd, platform_share,
              skill_tags, target_roles, difficulty_level,
              avg_rating, review_count, sales_count, author_id, created_at
       FROM marketplace_listings
       WHERE status = 'published'
         AND ($1::text IS NULL OR skill_tags @> ARRAY[$1]::text[])
         AND ($2::text IS NULL OR difficulty_level = $2)
       ORDER BY avg_rating DESC NULLS LAST, sales_count DESC
       LIMIT $3 OFFSET $4`,
      [tag, level, limit, offset]
    )

    const { rows: countRows } = await client.query(
      `SELECT COUNT(*)::int AS total FROM marketplace_listings
       WHERE status = 'published'
         AND ($1::text IS NULL OR skill_tags @> ARRAY[$1]::text[])
         AND ($2::text IS NULL OR difficulty_level = $2)`,
      [tag, level]
    )

    return NextResponse.json({
      listings: rows,
      pagination: {
        page,
        limit,
        total: countRows[0]?.total ?? 0,
        pages: Math.ceil((countRows[0]?.total ?? 0) / limit),
      },
    })
  } finally {
    client.release()
  }
}
