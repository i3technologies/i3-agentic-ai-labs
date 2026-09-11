import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import pool from '@/lib/db'
import { traceLangfuse, estimateTokens } from '@/lib/langfuse'
import { randomUUID } from 'crypto'

export const dynamic = 'force-dynamic'

const LITELLM_URL   = process.env.LITELLM_URL   ?? ''
const LITELLM_KEY   = process.env.LITELLM_KEY   ?? ''
const AGENT_URL     = process.env.AGENT_URL     ?? 'http://campaign-agent.i3-pmaas.svc.cluster.local:8080'

async function getContextData() {
  const results: Record<string, unknown> = {}
  try {
    const { rows: wardRows } = await pool.query(`
      SELECT w.name, wt.priority, wt.registered_voters, wt.target_votes,
             COALESCE(wt.sentiment_score, 50) AS sentiment_score
      FROM ward_targets wt
      JOIN wards w ON w.id = wt.ward_id
      WHERE wt.campaign_id IN (SELECT id FROM campaigns WHERE status='active')
      ORDER BY wt.priority ASC
      LIMIT 10
    `)
    results.topWards = wardRows

    const { rows: activityRows } = await pool.query(`
      SELECT type, description, created_at
      FROM campaign_activity
      ORDER BY created_at DESC
      LIMIT 20
    `)
    results.recentActivity = activityRows

    const { rows: statsRows } = await pool.query(`
      SELECT
        (SELECT COUNT(*) FROM voters)::int                               AS total_voters,
        (SELECT COUNT(*) FROM campaigns WHERE status='active')::int      AS active_campaigns,
        (SELECT AVG(sentiment_score) FROM ward_targets)::numeric(5,1)    AS avg_sentiment
    `)
    results.stats = statsRows[0]
  } catch {
    results.error = 'Could not fetch context data'
  }
  return results
}

function buildBriefingPrompt(context: Record<string, unknown>, today: string): string {
  return `You are Dawa, the AI campaign strategist for a Kenyan political campaign powered by PMaaS 4.0.

Today is ${today}. Below is the latest campaign data:

TOP WARD TARGETS:
${JSON.stringify(context.topWards ?? [], null, 2)}

RECENT ACTIVITY (last 20 events):
${JSON.stringify(context.recentActivity ?? [], null, 2)}

OVERALL STATS:
${JSON.stringify(context.stats ?? {}, null, 2)}

Generate a comprehensive daily campaign briefing with EXACTLY these five sections.
Each section must use markdown with ## headings and bullet points where appropriate.

## Executive Overview
3–4 sentences on the overall campaign position, momentum, and critical priorities today.

## Ward Intelligence
For each of the top 5 wards: current sentiment score, registered voters vs target, and 1 specific action to improve penetration.

## Content Strategy
3 specific content pieces to produce today (social media, WhatsApp, or voice calls) — include target ward, message angle, and medium.

## Sentiment Analysis
Summarise the emotional pulse of the electorate from the activity data. Identify any risk signals and opportunities.

## 48-Hour Action Plan
A prioritised list of 5 concrete campaign actions the team must execute in the next 48 hours, with assigned lead (e.g. Field Team, Digital Team, Candidate).

Keep the tone strategic, direct, and action-oriented. Total length: 600–800 words.`
}

export async function POST() {
  const session = await getServerSession(authOptions)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const context  = await getContextData()
  const today    = new Date().toLocaleDateString('en-KE', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  })
  const prompt   = buildBriefingPrompt(context, today)
  const traceId  = randomUUID()
  const start    = new Date()

  // Try Campaign Agent first (it also does RAG), fall back to LiteLLM direct
  let rawBriefing = ''
  let modelUsed   = ''

  try {
    // Attempt Campaign Agent endpoint
    const agentResp = await fetch(`${AGENT_URL}/briefing`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key':    LITELLM_KEY,
      },
      body: JSON.stringify({ prompt, context }),
      signal: AbortSignal.timeout(120_000),
    })
    if (!agentResp.ok) throw new Error(`Agent ${agentResp.status}`)
    const agentData = await agentResp.json()
    rawBriefing = agentData.briefing ?? agentData.response ?? ''
    modelUsed = agentData.model ?? 'campaign-agent/qwen-heavy'
  } catch {
    // Fall back to LiteLLM directly
    if (!LITELLM_URL || !LITELLM_KEY) {
      return NextResponse.json({ error: 'No AI backend configured' }, { status: 503 })
    }
    const litellmResp = await fetch(`${LITELLM_URL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${LITELLM_KEY}`,
      },
      body: JSON.stringify({
        model:       'qwen-heavy',
        messages:    [{ role: 'user', content: prompt }],
        temperature: 0.7,
        max_tokens:  1200,
      }),
      signal: AbortSignal.timeout(120_000),
    })
    if (!litellmResp.ok) {
      const err = await litellmResp.text()
      return NextResponse.json({ error: `LiteLLM ${litellmResp.status}: ${err}` }, { status: 502 })
    }
    const litellmData = await litellmResp.json()
    rawBriefing = litellmData.choices?.[0]?.message?.content ?? ''
    modelUsed = 'litellm/qwen-heavy'
  }

  // Parse the five sections out of the markdown response
  const sectionPattern = /##\s+(Executive Overview|Ward Intelligence|Content Strategy|Sentiment Analysis|48-Hour Action Plan)([\s\S]*?)(?=##\s+(?:Executive Overview|Ward Intelligence|Content Strategy|Sentiment Analysis|48-Hour Action Plan)|$)/gi
  const sections: Record<string, string> = {
    overview:  '',
    wards:     '',
    content:   '',
    sentiment: '',
    plan:      '',
  }
  const keyMap: Record<string, keyof typeof sections> = {
    'executive overview':    'overview',
    'ward intelligence':     'wards',
    'content strategy':      'content',
    'sentiment analysis':    'sentiment',
    '48-hour action plan':   'plan',
  }
  let m: RegExpExecArray | null
  while ((m = sectionPattern.exec(rawBriefing)) !== null) {
    const heading = m[1].toLowerCase().trim()
    const key     = keyMap[heading]
    if (key) sections[key] = (`## ${m[1]}\n${m[2]}`).trim()
  }
  // If parsing failed, dump everything into overview
  if (!sections.overview) sections.overview = rawBriefing

  const end = new Date()
  traceLangfuse({
    traceId,
    name:      'pmaas-briefing',
    userId:    session.user?.email ?? '',
    metadata:  { today, modelUsed },
    input:     prompt,
    output:    rawBriefing,
    startTime: start.toISOString(),
    endTime:   end.toISOString(),
    modelName: modelUsed,
    promptTokens:     estimateTokens(prompt),
    completionTokens: estimateTokens(rawBriefing),
    latencyMs: end.getTime() - start.getTime(),
  })

  // Persist briefing for audit
  try {
    await pool.query(
      `INSERT INTO campaign_activity (type, description, created_at)
       VALUES ($1, $2, NOW())`,
      ['ai_briefing', `AI briefing generated (${modelUsed})`]
    )
  } catch { /* non-critical */ }

  return NextResponse.json({
    ...sections,
    generatedAt: end.toISOString(),
    modelUsed,
  })
}
