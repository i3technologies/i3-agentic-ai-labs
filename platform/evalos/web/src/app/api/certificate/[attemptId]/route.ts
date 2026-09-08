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

  const userId = session.user.userId || session.user.email || ''

  // Verify the attempt is a passing submission on the final set
  const { rows: attemptRows } = await pool.query(
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

  // Only issue certificate for SET6
  if (!attempt.exam_code.endsWith('SET6')) {
    return NextResponse.json({ error: 'Certificate only available after completing SET6' }, { status: 403 })
  }

  // Check if cert already issued
  const { rows: existing } = await pool.query(
    `SELECT id, verify_code FROM certificates WHERE attempt_id = $1`,
    [attemptId]
  )
  if (existing.length > 0) {
    return NextResponse.json({ verifyCode: existing[0].verify_code })
  }

  // Issue new certificate
  const verifyCode = randomUUID().replace(/-/g, '').slice(0, 16).toUpperCase()
  const studentName = session.user.name || session.user.email || userId
  const studentEmail = session.user.email || userId

  await pool.query(
    `INSERT INTO certificates (student_id, student_name, student_email, exam_code, exam_title, pct_score, attempt_id, verify_code)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
    [userId, studentName, studentEmail, attempt.exam_code, attempt.exam_title, attempt.pct_score, attemptId, verifyCode]
  )

  return NextResponse.json({ verifyCode })
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

  const userId = session.user.userId || session.user.email || ''

  const { rows } = await pool.query(
    `SELECT * FROM certificates WHERE attempt_id = $1 AND student_id = $2`,
    [attemptId, userId]
  )
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
