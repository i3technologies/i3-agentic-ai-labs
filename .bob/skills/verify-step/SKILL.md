---
name: verify-step
description: Runs machine-verifiable sensor checks for any atomic step (e.g., STEP-P1-01 to STEP-P3-05) to ensure zero regressions before marking done.
---

When the user requests to verify an atomic step:
1. Identify the target step ID (e.g., `P1-05`, `P2-04`).
2. Read the corresponding `Sensor Checks` section in `i3-platform-atomic-execution-plan.md`.
3. Execute each sensor check command sequentially using terminal execution:
   - For grep checks: ensure exit codes and match counts conform to expected targets.
   - For python/pytest/npm checks: ensure exit code is 0.
   - For curl/HTTP checks: verify expected HTTP status codes (e.g., 401, 201, 202).
4. Output a Sensor Verification Matrix:
   | Sensor Check ID | Command | Expected | Actual | Status (PASS/FAIL) |
5. If any check fails, immediately propose the exact code remediation and do not advance the phase gate.