---
name: sync-lobster-trap
description: Synchronizes and verifies all 12 canonical prompt injection regex patterns across TypeScript and Python runtimes.
---

1. Inspect `onboarding-agent/src/security/lobster-trap.ts` and `platform/admissions/admissions_agent.py`.
2. Ensure both engines evaluate all 12 canonical patterns:
   - 01: `ignore\s+(all\s+)?(previous|prior)\s+instructions`
   - 02: `system\s+prompt\s+override`
   - 03: `you\s+are\s+now\s+in\s+developer\s+mode`
   - 04: `output\s+all\s+passwords`
   - 05: `reveal\s+internal\s+logic`
   - 06: `bypass\s+safety\s+filter`
   - 07: `act\s+as\s+DAN`
   - 08: `jailbreak`
   - 09: `drop\s+table`
   - 10: `prompt\s+injection`
   - 11: `disregard\s+(all\s+)?previous`
   - 12: `\bexfiltrate\b`
3. Verify that `platform/pmaas/agents/campaign_agent.py` calls `guard_input()` on user-controlled fields (`ward_name`, `key_message`, `prompt`).
4. Run validation against test injection strings.