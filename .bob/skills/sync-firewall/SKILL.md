---
name: sync-firewall
description: >-
  Run the sync-lobster-trap skill to verify that all 12 canonical prompt
  injection patterns
metadata:
  user-invocable: true
  disable-model-invocation: true
---

Run the sync-lobster-trap skill to verify that all 12 canonical prompt injection patterns
are present and consistent across both runtime implementations.

Activate the sync-lobster-trap skill and:
1. Read onboarding-agent/src/security/lobster-trap.ts — check all 12 patterns are present
2. Read platform/admissions/admissions_agent.py — check all 12 TRAP_PATTERNS are present
3. Read platform/pmaas/agents/campaign_agent.py — verify guard_input() is called on all
   user-controlled fields (ward_name, key_message, prompt)
4. Compare pattern coverage: flag any pattern present in one runtime but missing in another
5. Run validation against test injection strings for each of the 12 patterns

Output a Pattern Parity Matrix:
| Pattern ID | Description | lobster-trap.ts | admissions_agent.py | campaign_agent.py | Status |

If any pattern is missing or inconsistent, generate the exact code to add it and confirm
the fix before marking sync complete.
