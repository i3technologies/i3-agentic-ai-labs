/**
 * n8n webhook integration — fire-and-forget event notifications.
 * The webhook URL is set via N8N_WEBHOOK_URL env var.
 * n8n handles: pass/fail emails, SET6 certificate notifications, lab provisioning.
 */

const N8N_WEBHOOK_URL = process.env.N8N_WEBHOOK_URL

export async function triggerN8nWebhook(payload: Record<string, unknown>): Promise<void> {
  if (!N8N_WEBHOOK_URL) return // silently skip if not configured

  await fetch(N8N_WEBHOOK_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, ts: new Date().toISOString(), source: 'evalos' }),
    // short timeout — this must never block the response
    signal: AbortSignal.timeout(3000),
  })
}
