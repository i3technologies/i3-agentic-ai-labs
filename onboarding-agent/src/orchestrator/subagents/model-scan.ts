/**
 * model-scan.ts
 * Subagent: scans model configuration, prompt engineering patterns,
 * RAGAS evaluation, and red-team/safety testing.
 * Primarily serves the AI/ML Engineer onboarding role (deep model focus).
 *
 * Real files it will reference:
 *   platform/testing/testing.py              (RAGAS + promptfoo setup)
 *   platform/admissions/admissions_agent.py  (prompt patterns + confidence gate)
 *   platform/docs/platform-documentation.md  (model tier config)
 */

import { BaseScan }      from './base-scan';
import { SubagentInput } from './types';

export class ModelScan extends BaseScan {
  readonly subagentName = 'model-scan';

  readonly systemPrompt = `
You are the Model & Evaluation Scanner for i3 Agentic AI Labs onboarding.

Your specialisation is LLM model configuration, prompt engineering, and evaluation:
- LiteLLM model tiers: granite-nano (Tier 3), mistral-nemo (Tier 2), granite-heavy (Tier 1)
- IBM Cloud credit budget: $14,047.27 — credit cost per tier must be considered
- RAGAS evaluation framework (platform/testing/testing.py --ragas flag)
- promptfoo red-team configuration (--promptfoo-config flag in testing.py)
- Locust load tests for LLM endpoints
- Confidence gate pattern (0.65 threshold in admissions_agent.py)
- Prompt injection defence: Lobster Trap 12-pattern firewall
- C1000-207 IBM Exam domains mapped to Bloom's taxonomy (Agent Integration 23q=38%)

When producing findings, focus on:
1. How to configure and test model tiers locally
2. How to run RAGAS evaluations against the onboarding corpus
3. The promptfoo red-team config — what attack patterns are covered
4. Confidence gate tuning (why 0.65, how to adjust)
5. How to add a new model to LiteLLM without changing application code
6. Locust performance baselines for LLM endpoints

Always cite exact file paths from context. Do not invent paths.
`.trim();

  protected buildUserPrompt(input: SubagentInput): string {
    return (
      `SUBAGENT: ${this.subagentName}\n` +
      `ROLE: ${input.role}\n\n` +
      `FOCUS AREAS:\n${input.focusAreas.map(f => `- ${f}`).join('\n')}\n\n` +
      `PLATFORM CONTEXT:\n${input.ragContext}\n\n` +
      `Produce a JSON object with key "findings" (array of 4–6 items).\n` +
      `Each item: title, description, filePaths[], priority (high/medium/low), ` +
      `suggestedDay (1-5), roles[], optional historicalIssueRef.\n` +
      `Output ONLY valid JSON. No markdown fences.\n`
    );
  }
}

export const modelScan = new ModelScan();

export async function runModelScan(ragContext: string): Promise<ReturnType<ModelScan['run']>> {
  const input: SubagentInput = {
    role:         'ai_ml_engineer',
    contextQuery: 'RAGAS promptfoo Locust confidence gate LiteLLM models C1000-207 Bloom',
    ragContext,
    focusAreas: [
      'LiteLLM model tier configuration and credit cost management',
      'RAGAS evaluation framework — running platform/testing/testing.py --ragas',
      'promptfoo red-team attack patterns and configuration',
      'Confidence gate: 0.65 threshold, how to tune and monitor',
      'Lobster Trap 12 injection patterns — extending for new attack vectors',
      'C1000-207 exam domain weights and Bloom taxonomy mapping',
      'Locust load test baselines for LLM streaming endpoints',
    ],
  };
  return modelScan.run(input);
}
