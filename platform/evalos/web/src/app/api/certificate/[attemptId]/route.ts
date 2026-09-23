import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'
import { renderToBuffer } from '@react-pdf/renderer'
import { CertificatePDF } from '@/lib/certificate-pdf'
import { randomUUID } from 'crypto'

export const dynamic = 'force-dynamic'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

// POST /api/certificate/[attemptId] — issue or retrieve certificate
export async function POST(
  _req: Request,
  { params }: { params: { attemptId: string } }
) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { attemptId } = params
  if (!UUID_RE.test(attemptId)) return NextResponse.json({ error: 'Invalid attempt ID' }, { status: 400 })

  const userId   = session.user.userId || session.user.email || ''
  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'

  const client = await pool.connect()
  try {
    // HC-4: set RLS session variable
    await client.query('SET LOCAL app.tenant_id = $1', [tenantId])

    // Verify the attempt is a passing submission
    const { rows: attemptRows } = await client.query(
      `SELECT qa.id, qa.pct_score, qa.passed, e.code AS exam_code, e.title AS exam_title
       FROM quiz_attempts qa
       JOIN exams e ON e.id = qa.exam_id
       WHERE qa.id = $1 AND qa.student_id = $2
         AND qa.status IN ('submitted','graded') AND qa.passed = true`,
      [attemptId, userId]
    )
    if (attemptRows.length === 0) {
      return NextResponse.json({ error: 'No passing attempt found' }, { status: 404 })
    }
    const attempt = attemptRows[0]

    // Check if cert already issued
    const { rows: existing } = await client.query(
      `SELECT id, verify_code FROM certificates WHERE attempt_id = $1`,
      [attemptId]
    )
    if (existing.length > 0) {
      return NextResponse.json({ verifyCode: existing[0].verify_code })
    }

    // Issue new certificate (HC-4: tenant_id included)
    const verifyCode = randomUUID().replace(/-/g, '').slice(0, 16).toUpperCase()
    const studentName = session.user.name || session.user.email || userId
    const studentEmail = session.user.email || userId

    await client.query(
      `INSERT INTO certificates (student_id, student_name, student_email, exam_code, exam_title, pct_score, attempt_id, verify_code, tenant_id)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
      [userId, studentName, studentEmail, attempt.exam_code, attempt.exam_title, attempt.pct_score, attemptId, verifyCode, tenantId]
    )

    return NextResponse.json({ verifyCode })
  } finally {
    client.release()
  }
}

// GET /api/certificate/[attemptId] — download PDF
export async function GET(
  _req: Request,
  { params }: { params: { attemptId: string } }
) {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { attemptId } = params
  if (!UUID_RE.test(attemptId)) return NextResponse.json({ error: 'Invalid attempt ID' }, { status: 400 })

  const userId   = session.user.userId || session.user.email || ''
  const tenantId = (session.user as { tenant_id?: string }).tenant_id ?? '00000000-0000-0000-0000-000000000002'

  const certClient = await pool.connect()
  let rows: Record<string, unknown>[]
  try {
    await certClient.query('SET LOCAL app.tenant_id = $1', [tenantId])
    const result = await certClient.query(
      `SELECT * FROM certificates WHERE attempt_id = $1 AND student_id = $2`,
      [attemptId, userId]
    )
    rows = result.rows
  } finally {
    certClient.release()
  }
  if (rows.length === 0) return NextResponse.json({ error: 'Certificate not found' }, { status: 404 })

  const cert = rows[0]
  const pdfBuffer = await renderToBuffer(
    CertificatePDF({
      studentName: cert.student_name,
      studentEmail: cert.student_email,
      examCode: cert.exam_code,
      examTitle: cert.exam_title,
      pctScore: Number(cert.pct_score),
      verifyCode: cert.verify_code,
      issuedAt: new Date(cert.issued_at),
    })
  )

  return new NextResponse(new Uint8Array(pdfBuffer), {
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Disposition': `attachment; filename="i3-evalos-certificate-${cert.verify_code}.pdf"`,
    },
  })
}
