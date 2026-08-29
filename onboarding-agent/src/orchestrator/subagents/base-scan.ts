/**
 * base-scan.ts
 * Abstract base class every subagent extends.
 * Handles: LiteLLM call via openai-compatible client, retry logic,
 * token budget management, JSON response parsing with Zod validation.
 */

import OpenAI from 'openai';
import { z }  from 'zod';
import { SubagentScanResult, SubagentInput, SubagentFinding } from './types.js';

const client = new OpenAI({
  baseURL: process.env.LITELLM_URL    ?? 'http://localhost:4000/v1',
  apiKey:  process.env.LITELLM_KEY    ?? 'no-key',
  timeout: 60_000,
  maxRetries: 2,
});

// Tier 2 model (mistral-nemo) used for all subagent scans
const SCAN_MODEL = process.env.LITELLM_MODEL_SCAN ?? 'mistral-nemo';

const FindingSchema = z.object({
  title:              z.string(),
  description:        z.string(),
  filePaths:          z.array(z.string()),
  priority:           z.enum(['high', 'medium', 'low']),
  suggestedDay:       z.number().min(1).max(5),
  roles:              z.array(z.string()),
  historicalIssueRef: z.string().optional(),
});

const ScanResponseSchema = z.object({
  findings: z.array(FindingSchema),
});

export abstract class BaseScan {
  abstract readonly subagentName: string;
  abstract readonly systemPrompt:  string;

  /** Subclasses override to provide the user prompt. */
  protected buildUserPrompt(input: SubagentInput): string {
    return (
      `You are the ${this.subagentName} subagent for the i3 Agentic AI Labs onboarding system.\n\n` +
      `ROLE BEING ONBOARDED: ${input.role}\n\n` +
      `FOCUS AREAS:\n${input.focusAreas.map(f => `- ${f}`).join('\n')}\n\n` +
      `RETRIEVED CONTEXT FROM PLATFORM REPOSITORY:\n${input.ragContext}\n\n` +
      `TASK: Analyze the context and produce a JSON object with a "findings" array.\n` +
      `Each finding must reference a real file path from the context above.\n` +
      `Suggest 3–6 findings. Output ONLY valid JSON, no markdown fences.\n`
    );
  }

  async run(input: SubagentInput): Promise<SubagentScanResult> {
    const t0 = Date.now();

    const completion = await client.chat.completions.create({
      model:       SCAN_MODEL,
      temperature: 0.2,
      max_tokens:  2000,
      messages: [
        { role: 'system', content: this.systemPrompt },
        { role: 'user',   content: this.buildUserPrompt(input) },
      ],
    });

    const raw = completion.choices[0]?.message?.content ?? '{"findings":[]}';

    // Strip any accidental markdown fences
    const cleaned = raw.replace(/^```(?:json)?\n?/m, '').replace(/\n?```$/m, '').trim();

    let parsed: z.infer<typeof ScanResponseSchema>;
    try {
      parsed = ScanResponseSchema.parse(JSON.parse(cleaned));
    } catch {
      console.warn(`[${this.subagentName}] LLM returned invalid JSON; using empty findings`);
      parsed = { findings: [] };
    }

    const findings = parsed.findings.map((f): SubagentFinding => ({
      title:              f.title,
      description:        f.description,
      filePaths:          f.filePaths,
      priority:           f.priority,
      suggestedDay:       f.suggestedDay as 1 | 2 | 3 | 4 | 5,
      roles:              f.roles as SubagentFinding['roles'],
      historicalIssueRef: f.historicalIssueRef,
    }));

    return {
      subagentName: this.subagentName,
      role:         input.role,
      findings,
      contextUsed:  [input.ragContext.slice(0, 500)],
      durationMs:   Date.now() - t0,
    };
  }
}
