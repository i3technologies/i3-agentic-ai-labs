import { NextRequest, NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { searchParams } = new URL(req.url)
  const page     = Math.max(1, parseInt(searchParams.get('page') ?? '1', 10))
  const ward     = searchParams.get('ward') ?? ''
  const search   = searchParams.get('q') ?? ''
  const limit    = 50
  const offset   = (page - 1) * limit

  const conditions: string[] = []
  const params: unknown[]    = [limit, offset]
  let   p = 3

  if (ward)   { conditions.push(`v.ward_id = $${p++}`);     params.push(ward)   }
  if (search) { conditions.push(`v.name ILIKE $${p++}`);    params.push(`%${search}%`) }

  const where = conditions.length ? `WHERE ${conditions.join(' AND ')}` : ''

  const { rows } = await pool.query(
    `SELECT v.id, v.name, v.phone, v.ward_id, w.name AS ward_name,
            v.voter_status, v.contacted, v.support_level
     FROM voters v
     LEFT JOIN wards w ON w.id = v.ward_id
     ${where}
     ORDER BY v.name ASC
     LIMIT $1 OFFSET $2`,
    params
  )

  const { rows: countRows } = await pool.query(
    `SELECT COUNT(*)::int AS total FROM voters v ${where}`,
    params.slice(2)
  )

  return NextResponse.json({ voters: rows, total: countRows[0].total, page })
}

export async function POST(req: NextRequest) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  // Bulk import from CSV rows
  const body = await req.json()
  const { voters } = body as { voters: Record<string, string>[] }

  if (!Array.isArray(voters) || voters.length === 0) {
    return NextResponse.json({ error: 'voters array required' }, { status: 400 })
  }

  const client = await pool.connect()
  try {
    await client.query('BEGIN')
    let inserted = 0
    for (const v of voters) {
      await client.query(
        `INSERT INTO voters (id, name, phone, ward_id, voter_status, contacted, support_level, created_at)
         VALUES (gen_random_uuid(), $1, $2, $3, 'registered', false, 'unknown', NOW())
         ON CONFLICT (phone) DO NOTHING`,
        [v.name?.trim(), v.phone?.trim(), v.ward_id ?? null]
      )
      inserted++
    }
    await client.query(
      `INSERT INTO campaign_activity (type, description, created_at) VALUES ($1, $2, NOW())`,
      ['voters_imported', `${inserted} voters imported`]
    )
    await client.query('COMMIT')
    return NextResponse.json({ inserted }, { status: 201 })
  } catch (err) {
    await client.query('ROLLBACK')
    return NextResponse.json({ error: String(err) }, { status: 500 })
  } finally {
    client.release()
  }
}
