# Sensor Check Quick Reference — i3 Platform Atomic Steps

Compact reference for the `verify-step` skill. Use this file to look up
sensor check IDs and commands without loading the full atomic execution plan.

Full detail in: `i3-platform-atomic-execution-plan.md`

---

## Phase 1 — Foundation Sensor Checks

| Step | Sensor Check | Command | Expected |
|------|-------------|---------|----------|
| P1-01 | SC-P1-01-A | `gitleaks detect --source . --no-git` | Exit 0, 0 findings |
| P1-01 | SC-P1-01-B | `grep -r "DEV_BYPASS_AUTH=true" . --include="*.py" --include="*.ts"` | Exit 1 (no matches) |
| P1-02 | SC-P1-02-A | `grep -r "asyncpg.connect(" platform/ --include="*.py"` | Exit 1 (no matches) |
| P1-02 | SC-P1-02-B | `grep -r "asyncio.new_event_loop" platform/ --include="*.py"` | Exit 1 (no matches) |
| P1-03 | SC-P1-03-A | `grep -rn "rejectUnauthorized: false" . --include="*.ts"` | Exit 1 (no matches) |
| P1-04 | SC-P1-04-A | `grep -rn "new Map()" onboarding-agent/src/ --include="*.ts"` | Exit 1 (no matches — use Redis) |
| P1-05 | SC-P1-05-A | `grep -c "TRAP_PATTERNS" platform/admissions/admissions_agent.py` | 1 |
| P1-05 | SC-P1-05-B | `grep -c "TRAP_PATTERNS" platform/pmaas/agents/campaign_agent.py` | 1 |
| P1-06 | SC-P1-06-A | `grep -rn "timingSafeEqual" onboarding-agent/src/ --include="*.ts"` | ≥1 match |
| P1-07 | SC-P1-07-A | `grep -rn "hashlib.sha256" platform/ --include="*.py"` | Exit 1 (no raw SHA-256) |
| P1-08 | SC-P1-08-A | `grep -rn "tenant_id" platform/engage/web/src/lib/db.ts` | ≥1 match |

---

## Phase 2 — Agent Mesh Sensor Checks

| Step | Sensor Check | Command | Expected |
|------|-------------|---------|----------|
| P2-01 | SC-P2-01-A | `curl -s http://consent-service.i3-consent.svc/healthz` | HTTP 200 |
| P2-02 | SC-P2-02-A | `curl -s http://agent-registry.i3-agent-mesh.svc/healthz` | HTTP 200 |
| P2-03 | SC-P2-03-A | `curl -s http://mcp-gateway.i3-agent-mesh.svc/healthz` | HTTP 200 |
| P2-04 | SC-P2-04-A | `grep -rn "chromadb" platform/admissions/ --include="*.py"` | Exit 1 (removed) |
| P2-05 | SC-P2-05-A | `grep -rn "autonomy_level: L[23]" platform/ --include="*.yaml"` | Exit 1 (no L2/L3) |

---

## Phase 3 — Runtime Optimisation Sensor Checks

| Step | Sensor Check | Command | Expected |
|------|-------------|---------|----------|
| P3-01 | SC-P3-01-A | `redis-cli -n 1 keys "litellm:*" \| wc -l` | >0 (cache active) |
| P3-02 | SC-P3-02-A | `kubectl get scaledobject -n i3-engage` | 1+ ScaledObject |
| P3-03 | SC-P3-03-A | `curl -s https://pmaas.i3.co.ke/manifest.json` | HTTP 200 + `"start_url"` |
| P3-04 | SC-P3-04-A | `kubectl get pipeline -n tekton-pipelines` | Pipeline exists |
| P3-05 | SC-P3-05-A | Lighthouse CLI PWA score | ≥80 |

---

## Exit Gate Quick Reference

### Phase 1 Gate (P1-GATE)
All of the following must be green:
- `gitleaks detect` → 0 findings
- No `asyncpg.connect()` in handlers
- No `rejectUnauthorized: false`
- Lobster Trap 12 patterns in all runtimes
- `timingSafeEqual` on webhooks

### Phase 2 Gate (P2-GATE)
- Consent, Agent Registry, MCP Gateway all return HTTP 200
- No direct chromadb imports
- No L2/L3 agent manifests

### Phase 3 Gate (P3-GATE)
- LiteLLM Redis cache active
- KEDA ScaledObjects deployed
- PWA Lighthouse ≥ 80
- Fabric chaincode in staging
- 4-gate Tekton pipeline passing
