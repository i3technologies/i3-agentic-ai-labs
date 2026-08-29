/**
 * evalos-scan.ts
 * Subagent: scans EvalOS schema, exam engine, quiz logic, and curriculum
 * integration.  Primarily serves the Bootcamp Student onboarding role.
 *
 * Real files it will reference from context:
 *   platform/evalos/schema.sql
 *   platform/evalos/nextjs/exam-engine.ts
 *   platform/admissions/admissions_agent.py
 */

import { BaseScan }     from './base-scan.js';
import { SubagentInput } from './types.js';

export class EvolosScan extends BaseScan {
  readonly subagentName = 'evalos-scan';

  readonly systemPrompt = `
You are the EvalOS Scanner for i3 Agentic AI Labs onboarding.

Your specialisation is the EvalOS learning platform:
- PostgreSQL schema: questions, exams, quiz_attempts, enrolment_queue, ai_interviews tables
- Next.js exam engine (platform/evalos/nextjs/exam-engine.ts)
- Anti-cheat event recording and Bloom's taxonomy difficulty levels
- Admissions agent integration (platform/admissions/admissions_agent.py)
- n8n auto-enrolment webhook triggered by enrolment_queue INSERT

When producing findings, focus on:
1. What the bootcamp student needs to understand to navigate the platform
2. How quizzes are structured and how Bloom levels map to C1000-207 exam domains
3. The enrolment flow from admissions → EvalOS → n8n → Keycloak
4. Any schema quirks or historical bugs worth studying
5. Developer tooling required to run EvalOS locally

Always cite exact file paths found in the context. Do not invent paths.
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

/** Singleton export */
export const evalosScan = new EvolosScan();

/** Convenience: run with default focus areas for bootcamp_student role */
export async function runEvalosScan(ragContext: string): Promise<ReturnType<EvolosScan['run']>> {
  const input: SubagentInput = {
    role:         'bootcamp_student',
    contextQuery: 'EvalOS schema exam engine quiz enrolment admissions',
    ragContext,
    focusAreas: [
      'PostgreSQL schema tables: questions, exams, quiz_attempts, enrolment_queue',
      'Bloom taxonomy difficulty levels and C1000-207 domain mapping',
      'Anti-cheat event recording in exam-engine.ts',
      'n8n auto-enrolment webhook from enrolment_queue INSERT trigger',
      'Admissions agent confidence gate (0.65 threshold)',
      'Local developer environment setup for EvalOS Next.js',
    ],
  };
  return evalosScan.run(input);
}
