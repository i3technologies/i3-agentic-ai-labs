# i3 AI Platform — Bob Agent Context

> Auto-loaded by IBM Bob on every task. Keep this file concise — it contributes to the fixed
> token overhead on every prompt. Full detail lives in mode-specific rules and skills.

---

## Test Commands

| Stack | Command |
|-------|---------|
| Python (all services) | `pytest platform/` |
| TypeScript / Next.js | `npm test` (run from the relevant subdirectory) |
| Go chaincode | `go test ./...` (run from the chaincode directory) |
| Lobster Trap parity | activate `sync-lobster-trap` skill |

---

## Mode Selection Guide

| Task | Mode |
|------|------|
| Rotating secrets / credential leaks / asyncpg cleanup | 🛡️ `i3-remediation` |
| New FastAPI microservice / DDD scaffolding / Agent Registry | 🧠 `i3-mesh-architect` |
| Hyperledger Fabric chaincode / USSD bridge / IEBC work | ⛓️ `i3-fabric-blockchain` |
| LiteLLM caching / KEDA / PWA / Tekton 4-gate pipelines | ⚡ `i3-runtime-opt` |
| Security audit / HC compliance review (read-only) | 🔍 `i3-audit` |
| General codebase questions | Built-in Ask mode |

---

## Skill Quick Reference

| Skill | When to use |
|-------|-------------|
| `verify-step` | After completing any atomic step — outputs sensor verification matrix |
| `gate-check` | Before advancing a phase — outputs APPROVED / BLOCKED |
| `rotate-secrets` | When rotating any `i3/` OpenBao KV v2 secret |
| `sync-lobster-trap` | When editing prompt firewall patterns in TS or Python |
| `extract-domain-service` | When scaffolding a new bounded-context FastAPI service |
| `chaincode-scaffold` | When writing new Hyperledger Fabric Go chaincode |

---

## Hard Constraints (Non-Negotiable)

All 8 hard constraints are enforced in `.bob/rules/01-hard-constraints.md` on every prompt.
Key ones to keep front-of-mind:

- **HC-1**: `solution-01` through `solution-08` have been **fully migrated off this cluster**. Constraint is retired on this server — documented for audit traceability only.
- **HC-3**: No agent autonomy above L1 without verified evaluation evidence.
- **HC-4**: `tenant_id UUID NOT NULL` on every DDL, RLS policy, Kafka event, and query.
- **HC-6**: Kenyan NIDs and phone numbers → HMAC-SHA256 via `MEMBER_HMAC_SECRET` in OpenBao. Never raw SHA-256.
- **HC-7**: `DEV_BYPASS_AUTH=true` is **forbidden**. Fail any task where this appears in a non-gitignored file.
- **HC-8**: Voter identity and ballot choice must be in separate Fabric collections — never co-located.

---

## Key Reference Documents

- Phase steps & sensor checks: `i3-platform-atomic-execution-plan.md`
- Modernisation roadmap: `i3-platform-modernisation-roadmap-plan.md`
- Bob environment: `.bob/` directory

---

## Context Window Tips

- Open a **new task** (`+`) after each atomic step to prevent transcript bloat.
- Use `@platform/admissions/admissions_agent.py` style references — not full directory loads.
- Disable unused watsonx-orchestrate tools mid-session when not needed.
