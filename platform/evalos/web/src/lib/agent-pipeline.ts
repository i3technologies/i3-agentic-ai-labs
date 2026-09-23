/**
 * agent-pipeline.ts
 * Multi-agent evaluation pipeline for EvalOS Phase 2.
 *
 * Implements the Judge → Critic → Aggregator pattern described in
 * §6.3 of the EvalOS Technical Implementation Guide (ARCH-EVALOS-2026-V2).
 *
 * Agent roster (§6.2):
 *   CODE_EXAMINER  — correctness, complexity, maintainability, test coverage
 *   ARCHITECT      — design patterns, dependency graphs, security model
 *   ADVERSARIAL_QA — edge cases, fuzzing, resilience
 *   CRITIC         — actively disputes the primary judge's verdict
 *   AGGREGATOR     — reconciles Judge + Critic into a calibrated final score
 *   TUTOR          — post-assessment gap analysis and personalized study plan
 *
 * All inference routes through the on-cluster LiteLLM proxy (HC-5).
 * HC-3: L0/L1 only — agents propose, human has final authority on flagged cases.
 */

const LITELLM_URL = process.env.LITELLM_URL ?? 'http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1'
const LITELLM_KEY = process.env.LITELLM_KEY ?? ''

export type AgentType =
  | 'CODE_EXAMINER'
  | 'ARCHITECT'
  | 'ADVERSARIAL_QA'
  | 'CRITIC'
  | 'AGGREGATOR'
  | 'TUTOR'
  | 'CERT_READINESS'

export interface AgentInput {
  submission: string        // code or prose answer
  language?: string         // e.g. 'python', 'typescript', 'go'
  problem_statement: string
  rubric: string
  prior_reports?: AgentReport[]  // fed into Critic/Aggregator
  tenantId: string
  userId: string
  attemptId: string
}

export interface AgentReport {
  agentType: AgentType
  scoreAwarded: number       // 0–100
  maxScore: number           // always 100
  findingsSummary: string
  detailedMetrics: Record<string, unknown>
  modelUsed: string
  latencyMs: number
}

// ── LLM call helper ────────────────────────────────────────────────────────────
async function callLLM(
  systemPrompt: string,
  userContent: string,
  model: string,
  tenantId: string,
  agentId: string,
  timeoutMs = 60_000
): Promise<string> {
  const resp = await fetch(`${LITELLM_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type':       'application/json',
      'Authorization':      `Bearer ${LITELLM_KEY}`,
      'x-litellm-metadata': JSON.stringify({ tenant_id: tenantId, agent_id: agentId }),
    },
    body: JSON.stringify({
      model,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user',   content: userContent },
      ],
      temperature: 0.2,
      max_tokens:  1200,
      top_p: 0.9,
    }),
    signal: AbortSignal.timeout(timeoutMs),
  })
  if (!resp.ok) {
    throw new Error(`LiteLLM ${resp.status}: ${await resp.text()}`)
  }
  const data = await resp.json()
  return data.choices?.[0]?.message?.content ?? ''
}

function parseJsonSafe<T>(raw: string): T | null {
  const cleaned = raw.replace(/^```(?:json)?\n?/m, '').replace(/\n?```$/m, '').trim()
  try {
    return JSON.parse(cleaned) as T
  } catch {
    return null
  }
}

function elapsed(start: number): number {
  return Date.now() - start
}

// ── Agent: Code Examiner ────────────────────────────────────────────────────────
export async function runCodeExaminer(input: AgentInput): Promise<AgentReport> {
  const t = Date.now()
  const system = `You are an expert code examiner for certification assessments.
Evaluate submitted code for: correctness, complexity, maintainability, test coverage awareness, documentation quality.
Return ONLY valid JSON matching the schema shown.`

  const user = `Problem: ${input.problem_statement}
Language: ${input.language ?? 'unknown'}
Rubric: ${input.rubric}
Submission:
\`\`\`${input.language ?? ''}
${input.submission}
\`\`\`

Return JSON:
{"score":0-100,"correctness":0-100,"complexity_score":0-100,"maintainability":0-100,"summary":"<2-3 sentences>","findings":["..."]}`

  const raw = await callLLM(system, user, 'qwen-heavy', input.tenantId, 'evalos-code-examiner')
  const parsed = parseJsonSafe<{
    score: number; correctness: number; complexity_score: number
    maintainability: number; summary: string; findings: string[]
  }>(raw) ?? { score: 0, correctness: 0, complexity_score: 0, maintainability: 0, summary: 'Parse error', findings: [] }

  return {
    agentType: 'CODE_EXAMINER',
    scoreAwarded: Math.max(0, Math.min(100, Math.round(parsed.score ?? 0))),
    maxScore: 100,
    findingsSummary: parsed.summary ?? '',
    detailedMetrics: {
      correctness: parsed.correctness,
      complexity_score: parsed.complexity_score,
      maintainability: parsed.maintainability,
      findings: parsed.findings ?? [],
    },
    modelUsed: 'qwen-heavy',
    latencyMs: elapsed(t),
  }
}

// ── Agent: Architect ────────────────────────────────────────────────────────────
export async function runArchitectAgent(input: AgentInput): Promise<AgentReport> {
  const t = Date.now()
  const system = `You are a senior software architect reviewing assessment submissions.
Focus on: system design quality, dependency management, security patterns, scalability concerns.
Return ONLY valid JSON.`

  const user = `Problem: ${input.problem_statement}
Rubric: ${input.rubric}
Submission (excerpt):
${input.submission.slice(0, 3000)}

Return JSON:
{"score":0-100,"design_quality":0-100,"security_posture":0-100,"summary":"<2-3 sentences>","architectural_findings":["..."]}`

  const raw = await callLLM(system, user, 'qwen-heavy', input.tenantId, 'evalos-architect')
  const parsed = parseJsonSafe<{
    score: number; design_quality: number; security_posture: number
    summary: string; architectural_findings: string[]
  }>(raw) ?? { score: 0, design_quality: 0, security_posture: 0, summary: 'Parse error', architectural_findings: [] }

  return {
    agentType: 'ARCHITECT',
    scoreAwarded: Math.max(0, Math.min(100, Math.round(parsed.score ?? 0))),
    maxScore: 100,
    findingsSummary: parsed.summary ?? '',
    detailedMetrics: {
      design_quality: parsed.design_quality,
      security_posture: parsed.security_posture,
      architectural_findings: parsed.architectural_findings ?? [],
    },
    modelUsed: 'qwen-heavy',
    latencyMs: elapsed(t),
  }
}

// ── Agent: Adversarial QA ───────────────────────────────────────────────────────
export async function runAdversarialQA(input: AgentInput): Promise<AgentReport> {
  const t = Date.now()
  const system = `You are an adversarial QA agent. Your job is to find failure modes in submitted code.
Try: edge cases, null inputs, race conditions, integer overflow, injection vectors, error handling gaps.
Return ONLY valid JSON.`

  const user = `Problem: ${input.problem_statement}
Submission:
\`\`\`${input.language ?? ''}
${input.submission.slice(0, 3000)}
\`\`\`

Return JSON:
{"resilience_score":0-100,"vulnerabilities_found":["..."],"edge_cases_missing":["..."],"summary":"<2 sentences>"}`

  const raw = await callLLM(system, user, 'qwen-heavy', input.tenantId, 'evalos-adversarial-qa')
  const parsed = parseJsonSafe<{
    resilience_score: number; vulnerabilities_found: string[]
    edge_cases_missing: string[]; summary: string
  }>(raw) ?? { resilience_score: 50, vulnerabilities_found: [], edge_cases_missing: [], summary: 'Parse error' }

  return {
    agentType: 'ADVERSARIAL_QA',
    scoreAwarded: Math.max(0, Math.min(100, Math.round(parsed.resilience_score ?? 50))),
    maxScore: 100,
    findingsSummary: parsed.summary ?? '',
    detailedMetrics: {
      vulnerabilities_found: parsed.vulnerabilities_found ?? [],
      edge_cases_missing: parsed.edge_cases_missing ?? [],
    },
    modelUsed: 'qwen-heavy',
    latencyMs: elapsed(t),
  }
}

// ── Agent: Critic ────────────────────────────────────────────────────────────────
export async function runCriticAgent(
  input: AgentInput,
  priorReports: AgentReport[]
): Promise<AgentReport> {
  const t = Date.now()
  const priorSummary = priorReports.map(r =>
    `${r.agentType}: score=${r.scoreAwarded}, summary=${r.findingsSummary}`
  ).join('\n')

  const system = `You are the Critic agent in a multi-agent evaluation pipeline.
Your ONLY job is to find flaws, over-scoring, or missed issues in the prior agents' judgments.
Be skeptical. Return ONLY valid JSON.`

  const user = `Problem: ${input.problem_statement}
Rubric: ${input.rubric}

Prior agent findings:
${priorSummary}

Submission (excerpt):
${input.submission.slice(0, 2000)}

Critique: Is the aggregate score fair? What did the prior agents miss or over-credit?
Return JSON:
{"adjusted_score":0-100,"counter_evidence":["..."],"overscored_areas":["..."],"underscored_areas":["..."],"summary":"<2 sentences>"}`

  const raw = await callLLM(system, user, 'qwen-heavy', input.tenantId, 'evalos-critic')
  const parsed = parseJsonSafe<{
    adjusted_score: number; counter_evidence: string[]
    overscored_areas: string[]; underscored_areas: string[]; summary: string
  }>(raw) ?? { adjusted_score: 0, counter_evidence: [], overscored_areas: [], underscored_areas: [], summary: 'Parse error' }

  return {
    agentType: 'CRITIC',
    scoreAwarded: Math.max(0, Math.min(100, Math.round(parsed.adjusted_score ?? 0))),
    maxScore: 100,
    findingsSummary: parsed.summary ?? '',
    detailedMetrics: {
      counter_evidence: parsed.counter_evidence ?? [],
      overscored_areas: parsed.overscored_areas ?? [],
      underscored_areas: parsed.underscored_areas ?? [],
    },
    modelUsed: 'qwen-heavy',
    latencyMs: elapsed(t),
  }
}

// ── Agent: Aggregator ────────────────────────────────────────────────────────────
export async function runAggregatorAgent(
  input: AgentInput,
  judgeReports: AgentReport[],
  criticReport: AgentReport
): Promise<AgentReport> {
  const t = Date.now()
  const judgeSummary = judgeReports.map(r =>
    `${r.agentType}: score=${r.scoreAwarded}`
  ).join(', ')

  const system = `You are the Aggregator in a multi-agent evaluation pipeline.
Reconcile the primary judges' scores with the Critic's counter-evidence.
Produce a calibrated final score and a concise natural-language justification.
Return ONLY valid JSON.`

  const user = `Primary judge scores: ${judgeSummary}
Critic adjusted score: ${criticReport.scoreAwarded}
Critic evidence: ${criticReport.detailedMetrics.counter_evidence}

Rubric: ${input.rubric}

Produce a final calibrated score. Weight: judges 60%, critic 40%.
Return JSON:
{"final_score":0-100,"confidence":0-100,"justification":"<3-4 sentences>","skill_vector":{"correctness":0-100,"design":0-100,"resilience":0-100}}`

  const raw = await callLLM(system, user, 'qwen-heavy', input.tenantId, 'evalos-aggregator')
  const parsed = parseJsonSafe<{
    final_score: number; confidence: number; justification: string
    skill_vector: Record<string, number>
  }>(raw) ?? { final_score: 0, confidence: 0, justification: 'Aggregation failed', skill_vector: {} }

  return {
    agentType: 'AGGREGATOR',
    scoreAwarded: Math.max(0, Math.min(100, Math.round(parsed.final_score ?? 0))),
    maxScore: 100,
    findingsSummary: parsed.justification ?? '',
    detailedMetrics: {
      confidence: parsed.confidence,
      skill_vector: parsed.skill_vector ?? {},
    },
    modelUsed: 'qwen-heavy',
    latencyMs: elapsed(t),
  }
}

// ── Pipeline Orchestrator ─────────────────────────────────────────────────────
export interface PipelineResult {
  reports: AgentReport[]
  finalScore: number
  skillVector: Record<string, number>
  justification: string
  requiresHumanReview: boolean
}

/**
 * Run the full Judge → Critic → Aggregator pipeline.
 * All agents run in parallel for the judge layer, then Critic and Aggregator
 * execute sequentially. (HC-3: L1 — results are proposals, not final verdicts.)
 */
export async function runEvaluationPipeline(input: AgentInput): Promise<PipelineResult> {
  // Stage 1: Run judge agents in parallel (CODE_EXAMINER, ARCHITECT, ADVERSARIAL_QA)
  const [codeReport, archReport, advReport] = await Promise.allSettled([
    runCodeExaminer(input),
    runArchitectAgent(input),
    runAdversarialQA(input),
  ])

  const judgeReports: AgentReport[] = [
    codeReport.status === 'fulfilled' ? codeReport.value : fallbackReport('CODE_EXAMINER'),
    archReport.status === 'fulfilled'  ? archReport.value  : fallbackReport('ARCHITECT'),
    advReport.status === 'fulfilled'   ? advReport.value   : fallbackReport('ADVERSARIAL_QA'),
  ]

  // Stage 2: Critic challenges judge reports
  const criticReport = await runCriticAgent(input, judgeReports).catch(() => fallbackReport('CRITIC'))

  // Stage 3: Aggregator reconciles everything
  const aggregatorReport = await runAggregatorAgent(input, judgeReports, criticReport)
    .catch(() => fallbackReport('AGGREGATOR'))

  const allReports = [...judgeReports, criticReport, aggregatorReport]
  const finalScore = aggregatorReport.scoreAwarded
  const skillVector = (aggregatorReport.detailedMetrics.skill_vector as Record<string, number>) ?? {}

  // HC-3: flag for human review if agents disagree significantly (> 25 pt spread)
  const judgeScores = judgeReports.map(r => r.scoreAwarded)
  const scoreSpread = Math.max(...judgeScores) - Math.min(...judgeScores)
  const requiresHumanReview = scoreSpread > 25 || finalScore < 40

  return {
    reports: allReports,
    finalScore,
    skillVector,
    justification: aggregatorReport.findingsSummary,
    requiresHumanReview,
  }
}

function fallbackReport(agentType: AgentType): AgentReport {
  return {
    agentType,
    scoreAwarded: 0,
    maxScore: 100,
    findingsSummary: `${agentType} agent timed out or failed`,
    detailedMetrics: { error: 'agent_failure' },
    modelUsed: 'none',
    latencyMs: 0,
  }
}
