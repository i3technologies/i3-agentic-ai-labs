/**
 * ailab-scan.ts
 * Subagent: scans the AI/ML lab components — LiteLLM gateway, ChromaDB RAG,
 * granite/mistral model tiers, and agent patterns.
 * Primarily serves the AI/ML Engineer onboarding role.
 *
 * Real files it will reference:
 *   platform/admissions/admissions_agent.py  (agent pattern source of truth)
 *   platform/admissions/mcp/mcp_connectors.py
 *   platform/docs/platform-documentation.md  (LiteLLM config, ChromaDB details)
 */

import { BaseScan }      from './base-scan';
import { SubagentInput } from './types';

export class AilabScan extends BaseScan {
  readonly subagentName = 'ailab-scan';

  readonly systemPrompt = `
You are the AI Lab Scanner for i3 Agentic AI Labs onboarding.

Your specialisation is the LLM / AI infrastructure layer:
- LiteLLM proxy at litellm.i3technologies.co.ke/v1, port 4000
- Model tiers: granite-nano (Tier 3), mistral-nemo (Tier 2), granite-heavy (Tier 1)
- IBM Cloud credit budget: $14,047.27 expiring Oct 2026 — prefer local Ollama tiers
- ChromaDB at chromadb.i3-admissions.svc.cluster.local:8000
- RAG pipeline (admissions-docs collection, onboarding-corpus collection)
- Lobster Trap prompt injection firewall (12 patterns)
- Admissions agent streaming SSE pattern and confidence gate
- MCP connectors 2-stage confirmation gate (in-memory _pending dict)
- KEDA autoscaler on LiteLLM (1–6 replicas, Prometheus request rate metric)
- RHOAI namespace (i3-ai-lab) — noted as Month 3 in docs; check if live

When producing findings, focus on:
1. How to run the admissions agent locally and call LiteLLM
2. How to add a new model to the LiteLLM gateway config
3. The Lobster Trap firewall patterns and how to extend them
4. ChromaDB collection management and embedding strategies
5. The RHOAI "Month 3" stale-doc risk — flag if namespace not yet confirmed live
6. MCP confirmation gate pattern for safe tool calls

Always cite exact file paths from context. Do not invent paths.
IMPORTANT: If context mentions RHOAI/i3-ai-lab as "available from Month 3" but no
live namespace confirmation is present, emit a finding with historicalIssueRef
"stale-doc: RHOAI namespace availability" and set priority: "high".
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

export const ailabScan = new AilabScan();

export async function runAilabScan(ragContext: string): Promise<ReturnType<AilabScan['run']>> {
  const input: SubagentInput = {
    role:         'ai_ml_engineer',
    contextQuery: 'LiteLLM ChromaDB RAG admissions agent Lobster Trap MCP RHOAI',
    ragContext,
    focusAreas: [
      'LiteLLM gateway tiers: granite-nano, mistral-nemo, granite-heavy',
      'IBM Cloud credit budget conservation — prefer Ollama Tier 2/3',
      'ChromaDB collections: admissions-docs and onboarding-corpus',
      'Lobster Trap 12-pattern prompt injection firewall',
      'Admissions agent SSE streaming and 0.65 confidence gate',
      'MCP 2-stage confirmation gate (mcp_connectors.py)',
      'RHOAI i3-ai-lab namespace — stale doc risk (Month 3 caveat)',
      'KEDA autoscaler for LiteLLM on Prometheus metrics',
    ],
  };
  return ailabScan.run(input);
}
