---
name: phase-gate
description: Run the gate-check skill to evaluate the exit criteria for a platform phase.
metadata:
  user-invocable: true
  disable-model-invocation: true
---

Run the gate-check skill to evaluate the exit criteria for a platform phase.

Ask the user which phase they want to evaluate (1, 2, or 3) if they have not already specified it.
Then activate the gate-check skill and evaluate all gate sensors for that phase:
- Phase 1: P1-GATE-01 through P1-GATE-12
- Phase 2: P2-GATE-01 through P2-GATE-10
- Phase 3: P3-GATE-01 through P3-GATE-15

Output the definitive gate decision (APPROVED or BLOCKED) with a full sensor results table showing
each gate ID, its command, expected result, actual result, and PASS/FAIL status.
If any gate is BLOCKED, list all failing gates and the exact remediation required before re-running.
