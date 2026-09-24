/**
 * decisionLog.ts
 * Fire-and-forget helper that emits a structured decision record to the
 * Agent Registry after every LLM completion.
 *
 * Calling convention (non-blocking):
 *   emitDecision({ agentId: 'onboarding-planner-v1', ... }).catch(() => {});
 *
 * The agent's own functionality is completely unaffected if the registry
 * is unavailable — all errors are swallowed and logged at debug level.
 */

const AGENT_REGISTRY_URL =
  process.env.AGENT_REGISTRY_URL ??
  'http://agent-registry.i3-agent-mesh.svc.cluster.local:8200';

const DEFAULT_TENANT_ID =
  process.env.DEFAULT_TENANT_ID ?? '00000000-0000-0000-0000-000000000001';

export interface DecisionPayload {
  agentId: string;
  sessionId?: string;
  model: string;
  inputTokens?: number;
  outputTokens?: number;
  toolsInvoked?: string[];
  outcome?: 'success' | 'error' | 'timeout';
  correlationId?: string;
}

/**
 * Emit a decision log entry. Returns immediately; network call is best-effort.
 * Never throws — callers do not need to handle errors.
 */
export function emitDecision(payload: DecisionPayload): void {
  const body = {
    tenant_id:       DEFAULT_TENANT_ID,
    agent_id:        payload.agentId,
    session_id:      payload.sessionId ?? null,
    autonomy_tier:   'L1',
    model:           payload.model,
    input_tokens:    payload.inputTokens ?? null,
    output_tokens:   payload.outputTokens ?? null,
    tools_invoked:   payload.toolsInvoked ?? [],
    policy_decision: 'allowed',
    outcome:         payload.outcome ?? 'success',
    correlation_id:  payload.correlationId ?? null,
  };

  fetch(`${AGENT_REGISTRY_URL}/decisions`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(body),
    signal:  AbortSignal.timeout(3000),  // 3-second timeout — non-blocking
  }).catch((err: unknown) => {
    // debug-level only — never surface to caller
    console.debug('[decisionLog] emit failed (non-fatal):', (err as Error).message);
  });
}
