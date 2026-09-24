Run the verify-step skill to execute sensor checks for a specific atomic execution step.

Ask the user for the step ID if not already provided (e.g. P1-05, P2-03, P3-07).
Then activate the verify-step skill and:
1. Read the Sensor Checks section for that step from i3-platform-atomic-execution-plan.md
2. Execute each sensor check command sequentially
3. Output a Sensor Verification Matrix table:
   | Sensor Check ID | Command | Expected | Actual | Status (PASS/FAIL) |

If any check fails, immediately propose the exact remediation code change required.
Do not mark the step as complete until all sensor checks show PASS.
