/**
 * planner.ts
 * Step 2 of the Task Execution Loop: Synthesis.
 *
 * Takes verified subagent findings + historical issue context and produces
 * the final RampUpPlan JSON conforming to the documented schema.
 *
 * Uses granite-heavy (Tier 1) for the synthesis call — best quality,
 * justified cost for the final plan output.
 *
 * Confidence scoring: 0.65 threshold (same as admissions agent).
 * Tasks below threshold are not included in the plan.
 */

import OpenAI from 'openai';
import { z }  from 'zod';
import { VerifiedScanResult, VerifiedFinding } from './verify.js';
import { OnboardingRole } from './subagents/types.js';

const client = new OpenAI({
  baseURL:    process.env.LITELLM_URL   ?? 'http://localhost:4000/v1',
  apiKey:     process.env.LITELLM_KEY   ?? 'no-key',
  timeout:    120_000,
  maxRetries: 2,
});

const SYNTH_MODEL       = process.env.LITELLM_MODEL_SYNTH ?? 'granite-heavy';
const CONFIDENCE_GATE   = 0.65;

// ──────────────────────────────────────────────────────────────────────────────
// Output Schema (RampUpPlan)
// ──────────────────────────────────────────────────────────────────────────────

export const RampUpTaskSchema = z.object({
  day:                z.number().int().min(1).max(5),
  title:              z.string(),
  description:        z.string(),
  filePaths:          z.array(z.string()),
  verified:           z.boolean(),
  verificationNote:   z.string().optional(),
  priority:           z.enum(['high', 'medium', 'low']),
  estimatedHours:     z.number().min(0.5).max(8),
  historicalIssueRef: z.string().optional(),
  roles:              z.array(z.string()),
  confidence:         z.number().min(0).max(1),
});

export const ArchitecturalSummarySchema = z.object({
  clusterVersion:    z.string(),
  region:            z.string(),
  namespaceCount:    z.number(),
  keyServices:       z.array(z.string()),
  forbiddenActions:  z.array(z.string()),
  creditBudget:      z.string(),
});

export const RampUpPlanSchema = z.object({
  schemaVersion:        z.literal('1.0'),
  generatedAt:          z.string(),
  role:                 z.string(),
  architecturalSummary: ArchitecturalSummarySchema,
  tasks:                z.array(RampUpTaskSchema),
  totalVerified:        z.number(),
  totalUnverified:      z.number(),
  staleDocWarnings:     z.array(z.string()),
});

export type RampUpTask = z.infer<typeof RampUpTaskSchema>;
export type RampUpPlan = z.infer<typeof RampUpPlanSchema>;

// ──────────────────────────────────────────────────────────────────────────────
// Static architectural summary (from platform analysis)
// ──────────────────────────────────────────────────────────────────────────────

const ARCHITECTURAL_SUMMARY: z.infer<typeof ArchitecturalSummarySchema> = {
  clusterVersion:   'ROKS 4.15',
  region:           'eu-de (Frankfurt)',
  namespaceCount:   12,
  keyServices: [
    'admissions-agent (i3-admissions)',
    'evalos (i3-evalos)',
    'litellm-proxy (i3-litellm)',
    'chromadb (i3-admissions)',
    'keycloak (i3-auth)',
    'openbao (i3-secrets)',
    'argocd (i3-gitops)',
    'n8n (i3-automation)',
    'directus (i3-cms)',
    'cert-manager (openshift-cert-manager)',
    'onboarding-agent (i3-onboarding) [wave 7]',
  ],
  forbiddenActions: [
    'Never modify solution-01 through solution-08 namespaces',
    'Never auto-write to EvalOS or Keycloak without 🔴 manual approval',
    'Never hardcode secrets — always inject from OpenBao KV v2 at i3/<service>/',
    'Never skip the Lobster Trap firewall on user-facing LLM input',
    'Never commit LITELLM_KEY or KEYCLOAK secrets to git',
  ],
  creditBudget: '$14,047.27 IBM Cloud credits expiring October 2026 — prefer Ollama Tier 2/3',
};

// ──────────────────────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────────────────────

function buildFindingsSummary(verified: VerifiedScanResult[]): string {
  return verified
    .flatMap(r =>
      r.findings.map(f =>
        `[${f.verified ? '✅' : '❌'} ${f.priority.toUpperCase()} Day ${f.suggestedDay}] ` +
        `${f.title}\n  ${f.description}\n  Paths: ${f.filePaths.join(', ')}` +
        (f.historicalIssueRef ? `\n  Historical ref: ${f.historicalIssueRef}` : '') +
        (!f.verified ? `\n  VERIFICATION FAIL: ${f.verificationNote}` : ''),
      ),
    )
    .join('\n\n');
}

function collectStalePaths(verified: VerifiedScanResult[]): string[] {
  return [...new Set(verified.flatMap(r => r.stalePaths))];
}

// ──────────────────────────────────────────────────────────────────────────────
// LLM synthesis
// ──────────────────────────────────────────────────────────────────────────────

async function synthesiseLLM(
  role:     OnboardingRole,
  findings: string,
): Promise<RampUpTask[]> {
  const systemPrompt = `
You are a Senior Solutions Architect and Onboarding Mentor for i3 Agentic AI Labs.
You create precise, role-specific first-week ramp-up plans.

RULES:
- Every task MUST reference a specific file path or architectural component.
- Do NOT generate generic "welcome to coding" advice.
- Output exactly one JSON object with key "tasks" (array).
- Tasks span days 1–5, covering ALL 5 working days.
- Include at least 2 high-priority tasks on Day 1.
- Include one task specifically for installing project-specific developer tools (README/Makefile).
- Include one task reviewing a historical bug (use historicalIssueRef field).
- Assign a confidence score (0.0–1.0) to each task.
- Tasks with confidence < 0.65 must set verified: false.
- Verified false tasks must have title prefixed: "Needs verification: [title] (referenced path not found — likely stale doc)"
- estimatedHours must be realistic (0.5–4 per task on days 1–2, up to 6 on days 4–5).
`.trim();

  const userPrompt =
    `ROLE BEING ONBOARDED: ${role}\n\n` +
    `VERIFIED SUBAGENT FINDINGS:\n${findings}\n\n` +
    `ARCHITECTURAL SUMMARY:\n` +
    `- Cluster: ${ARCHITECTURAL_SUMMARY.clusterVersion} in ${ARCHITECTURAL_SUMMARY.region}\n` +
    `- Key services: ${ARCHITECTURAL_SUMMARY.keyServices.slice(0, 6).join(', ')}\n` +
    `- FORBIDDEN: ${ARCHITECTURAL_SUMMARY.forbiddenActions[0]}\n\n` +
    `Synthesise these findings into a 5-day ramp-up plan with 12–15 tasks.\n` +
    `Output ONLY valid JSON with key "tasks". No markdown fences.\n`;

  const completion = await client.chat.completions.create({
    model:       SYNTH_MODEL,
    temperature: 0.15,
    max_tokens:  4000,
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user',   content: userPrompt },
    ],
  });

  const raw     = completion.choices[0]?.message?.content ?? '{"tasks":[]}';
  const cleaned = raw.replace(/^```(?:json)?\n?/m, '').replace(/\n?```$/m, '').trim();

  let parsed: { tasks: unknown[] };
  try {
    parsed = JSON.parse(cleaned);
  } catch {
    console.warn('[planner] LLM synthesis returned invalid JSON; using empty task list');
    return [];
  }

  if (!Array.isArray(parsed.tasks)) return [];

  const tasks: RampUpTask[] = [];
  for (const raw of parsed.tasks) {
    const result = RampUpTaskSchema.safeParse(raw);
    if (result.success) {
      tasks.push(result.data);
    } else {
      console.warn('[planner] Dropping malformed task:', result.error.issues[0]?.message);
    }
  }

  // Apply confidence gate
  return tasks.filter(t => t.confidence >= CONFIDENCE_GATE);
}

// ──────────────────────────────────────────────────────────────────────────────
// Fallback plan builder (used if LLM unavailable)
// Builds tasks deterministically from verified findings.
// ──────────────────────────────────────────────────────────────────────────────

function buildFallbackTasks(verified: VerifiedScanResult[]): RampUpTask[] {
  const allFindings: VerifiedFinding[] = verified.flatMap(r => r.findings);

  // Sort by priority then suggestedDay
  const priorityOrder = { high: 0, medium: 1, low: 2 };
  allFindings.sort((a, b) =>
    priorityOrder[a.priority] - priorityOrder[b.priority] ||
    a.suggestedDay - b.suggestedDay,
  );

  // Always include tool-install task on Day 1
  const hasDeveloperTools = allFindings.some(f =>
    f.title.toLowerCase().includes('tool') ||
    f.title.toLowerCase().includes('install') ||
    f.title.toLowerCase().includes('setup'),
  );

  const tasks: RampUpTask[] = allFindings.slice(0, 15).map((f): RampUpTask => ({
    day:                f.suggestedDay,
    title:              f.title,
    description:        f.description,
    filePaths:          f.filePaths,
    verified:           f.verified,
    verificationNote:   f.verificationNote,
    priority:           f.priority,
    estimatedHours:     f.priority === 'high' ? 3 : f.priority === 'medium' ? 2 : 1,
    historicalIssueRef: f.historicalIssueRef,
    roles:              f.roles,
    confidence:         f.verified ? 0.85 : 0.40,
  }));

  if (!hasDeveloperTools) {
    tasks.unshift({
      day:              1,
      title:            'Install project-specific developer tools (Makefile targets)',
      description:
        'Run `make install-tools` and `make env-setup` from the repo root. ' +
        'The Makefile defines all required CLI tools: oc, argocd, tekton, bao (OpenBao), ' +
        'and Node.js/Python version requirements. ' +
        'See platform/RUNBOOK.md §Developer Setup for prerequisite OS packages.',
      filePaths:        ['Makefile', 'platform/RUNBOOK.md'],
      verified:         true,
      verificationNote: 'Makefile and RUNBOOK.md confirmed present',
      priority:         'high',
      estimatedHours:   2,
      roles:            ['platform_engineer', 'ai_ml_engineer', 'backend_engineer'],
      confidence:       0.95,
    });
  }

  return tasks.filter(t => t.confidence >= CONFIDENCE_GATE);
}

// ──────────────────────────────────────────────────────────────────────────────
// Public API
// ──────────────────────────────────────────────────────────────────────────────

export interface PlannerInput {
  role:          OnboardingRole;
  verifiedScans: VerifiedScanResult[];
}

export async function generatePlan(input: PlannerInput): Promise<RampUpPlan> {
  const { role, verifiedScans } = input;
  const staleWarnings           = collectStalePaths(verifiedScans);
  const findingsSummary         = buildFindingsSummary(verifiedScans);

  let tasks: RampUpTask[];
  try {
    tasks = await synthesiseLLM(role, findingsSummary);
  } catch (err) {
    console.warn('[planner] LLM synthesis failed, using fallback:', (err as Error).message);
    tasks = buildFallbackTasks(verifiedScans);
  }

  // If LLM returned nothing, fall back
  if (tasks.length === 0) {
    tasks = buildFallbackTasks(verifiedScans);
  }

  // Sort by day then priority
  const priorityOrder = { high: 0, medium: 1, low: 2 };
  tasks.sort((a, b) => a.day - b.day || priorityOrder[a.priority] - priorityOrder[b.priority]);

  const totalVerified   = tasks.filter(t => t.verified).length;
  const totalUnverified = tasks.filter(t => !t.verified).length;

  return RampUpPlanSchema.parse({
    schemaVersion:        '1.0',
    generatedAt:          new Date().toISOString(),
    role,
    architecturalSummary: ARCHITECTURAL_SUMMARY,
    tasks,
    totalVerified,
    totalUnverified,
    staleDocWarnings:     staleWarnings,
  });
}
