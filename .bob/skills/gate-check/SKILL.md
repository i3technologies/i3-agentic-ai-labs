---
name: gate-check
description: Evaluates all entry and exit criteria for Phase 1, Phase 2, or Phase 3 before promoting the platform state.
---

When a Phase transition is requested:
1. Load the corresponding Exit Gate Checklist from `i3-platform-atomic-execution-plan.md`.
2. Sequentially evaluate each gate sensor:
   - Phase 1: P1-GATE-01 through P1-GATE-12 (gitleaks, PrometheusAlerts, Grafana PVC, Langfuse trace, OTP ratelimit, asyncpg pool).
   - Phase 2: P2-GATE-01 through P2-GATE-10 (Consent service live, Agent Registry, MCP Gateway, RLS, Kong auth, ADRs).
   - Phase 3: P3-GATE-01 through P3-GATE-15 (LiteLLM cache, async send, Fabric staging, 4-gate CI/CD, PWA Lighthouse >= 80).
3. Output the definitive gate decision: `APPROVED` or `BLOCKED`.