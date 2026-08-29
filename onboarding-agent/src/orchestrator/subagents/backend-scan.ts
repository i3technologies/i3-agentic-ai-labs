/**
 * backend-scan.ts
 * Subagent: scans Node.js/Express API structure, authentication middleware,
 * database models, and API route conventions.
 * Primarily serves the Backend Engineer onboarding role.
 *
 * Real files it will reference:
 *   platform/admissions/admissions_agent.py  (FastAPI pattern to understand)
 *   platform/evalos/schema.sql               (database schema)
 *   platform/docs/platform-documentation.md  (API URL directory)
 */

import { BaseScan }      from './base-scan.js';
import { SubagentInput } from './types.js';

export class BackendScan extends BaseScan {
  readonly subagentName = 'backend-scan';

  readonly systemPrompt = `
You are the Backend Scanner for i3 Agentic AI Labs onboarding.

Your specialisation is the backend API and data layer:
- FastAPI admissions agent (Python) — production streaming API pattern
- EvalOS PostgreSQL schema (questions, exams, quiz_attempts, enrolment_queue, ai_interviews)
- Directus CMS headless API for programme guides and curriculum content
- Keycloak Bearer token authentication on all protected endpoints
- LiteLLM OpenAI-compatible API routing pattern
- n8n webhook integration points from backend triggers
- OpenBao secret injection via environment variables
- Rate limiting and security middleware patterns

When producing findings, focus on:
1. How the admissions agent FastAPI endpoints are structured (streaming vs standard)
2. EvalOS schema entities a backend engineer needs to understand on day 1
3. Authentication pattern: Keycloak JWT → jwks-rsa verification → req.user
4. Environment variable conventions (all secrets from OpenBao, never hardcoded)
5. API URL naming convention (from platform-documentation.md URL directory)
6. How to run the backend services locally (admissions_agent.py, EvalOS API)

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

export const backendScan = new BackendScan();

export async function runBackendScan(ragContext: string): Promise<ReturnType<BackendScan['run']>> {
  const input: SubagentInput = {
    role:         'backend_engineer',
    contextQuery: 'FastAPI Express routes authentication JWT schema API endpoints Directus',
    ragContext,
    focusAreas: [
      'FastAPI admissions_agent.py — streaming endpoint and Lobster Trap middleware',
      'EvalOS schema: questions, exams, quiz_attempts, ai_interviews tables',
      'Keycloak Bearer token pattern and jwks-rsa JWT validation',
      'Environment variable conventions — all secrets via OpenBao',
      'API URL directory (from platform-documentation.md)',
      'n8n webhook trigger points from backend INSERT triggers',
      'Local development: how to run admissions_agent.py and EvalOS API',
    ],
  };
  return backendScan.run(input);
}
