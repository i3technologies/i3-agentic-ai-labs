import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { z } from 'zod'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'

export const dynamic = 'force-dynamic'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const BatchSchema = z.object({
  attemptId: z.string().regex(UUID_RE, 'Invalid attempt ID'),
  events: z.array(
    z.object({
      type: z.string(),
      ts: z.number(),
    })
  ),
})

export async function POST(
  req: Request,
  { params }: { params: { examId: string } }
) {
  const session = await getServerSession(authOptions)
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const examId = params.examId
  if (!UUID_RE.test(examId)) {
    return NextResponse.json({ error: 'Invalid exam ID' }, { status: 400 })
  }

  const body = await req.json().catch(() => null)
  const parsed = BatchSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }

  const { attemptId, events } = parsed.data
  const userId = session.user.userId || session.user.email || ''

  // Verify ownership
  const { rows } = await pool.query(
    `SELECT id FROM quiz_attempts
     WHERE id = $1 AND student_id = $2 AND exam_id = $3`,
    [attemptId, userId, examId]
  )
  if (rows.length === 0) {
    return NextResponse.json({ error: 'Attempt not found' }, { status: 404 })
  }

  // Count events by type and update the attempt
  const focusLost    = events.filter((e) => e.type === 'focus_lost').length
  const fsExits      = events.filter((e) => e.type === 'fullscreen_exit').length
  const clipboardEvt = events.filter((e) => e.type === 'clipboard_copy' || e.type === 'clipboard_paste').length
  const tabSwitches  = events.filter((e) => e.type === 'tab_switch')

  await pool.query(
    `UPDATE quiz_attempts
     SET focus_lost_count   = COALESCE(focus_lost_count, 0) + $1,
         fullscreen_exits   = COALESCE(fullscreen_exits, 0) + $2,
         clipboard_events   = COALESCE(clipboard_events, 0) + $3,
         tab_switch_events  = COALESCE(tab_switch_events, '[]'::jsonb) || $4::jsonb
     WHERE id = $5`,
    [focusLost, fsExits, clipboardEvt, JSON.stringify(tabSwitches), attemptId]
  )

  return NextResponse.json({ ok: true })
}
