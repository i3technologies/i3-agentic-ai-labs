# P1-GATE-07 — Langfuse Trace Verification Procedure

**Gate requirement:** End-to-end trace visible in Langfuse UI for the admissions agent
with a `tenant_id` attribute on at least one span.

**Classification:** Manual verification — requires cluster VPN access.

---

## Steps

1. **Connect** to the i3 cluster VPN or use the bastion host.

2. **Open** Langfuse at `https://langfuse.i3technologies.co.ke` and log in with your
   Keycloak SSO account (realm: `i3-platform`).

3. **Select Project** → `i3-admissions-agent`.

4. **Filter** traces:
   - Date range: last 24 hours
   - Service: `admissions-agent`

5. **Open** any trace. Expand the root span.

6. **Confirm** the following attributes are present on the root or a child span:
   - `tenant_id` — must be a UUID (e.g. `00000000-0000-0000-0000-000000000002`)
   - `agent` — value `admissions-agent`
   - `model` — one of the configured LiteLLM model names

7. **Screenshot** the trace detail view showing the `tenant_id` attribute.

8. **Record** the trace ID (format: `tr_xxxxxxxxxxxxxxxx`) in the gate sign-off ticket.

---

## Pass Criteria

| Criterion | Required value |
|-----------|---------------|
| Trace exists | At least one trace in last 24 h |
| `tenant_id` present | UUID, NOT NULL, NOT `00000000-0000-0000-0000-000000000000` |
| `agent` tag | `admissions-agent` |
| Trace status | `SUCCESS` or `PARTIAL` (not `ERROR` for all spans) |

---

## If No Traces Exist

```bash
# Trigger a test invocation from the cluster to generate a trace:
kubectl exec -n i3-admissions deploy/admissions-agent -- \
  python -c "
import httpx, os
r = httpx.post('http://localhost:8000/api/v1/enquire',
    json={'question': 'What are the admission requirements?',
          'tenant_id': '00000000-0000-0000-0000-000000000002'},
    headers={'Authorization': 'Bearer ' + os.environ['INTERNAL_API_KEY']})
print(r.status_code, r.json())
"
```

Wait 30 seconds and refresh the Langfuse UI. The trace should appear.

---

*Signed-off by:* ___________________________  *Date:* ___________  *Trace ID:* ___________
