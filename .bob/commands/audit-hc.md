Switch to i3-audit mode and perform a full Hard Constraints compliance review of the platform.

Check each of the 8 Hard Constraints (HC-1 through HC-8) across the codebase:
- HC-1: Scan for any references to solution-01 through solution-08 namespaces in modified files
- HC-2: Confirm Fabric chaincode and USSD bridge are on track for November 2026 staging
- HC-3: Scan all agent manifest files for autonomy_level L2 or L3 values
- HC-4: Verify tenant_id UUID NOT NULL is present in any new or modified SQL DDL
- HC-5: Check that no agent directly calls state-modifying endpoints without MCP gateway routing
- HC-6: Scan for raw SHA-256 or unhashed national ID / phone number usage
- HC-7: Scan all non-gitignored files for DEV_BYPASS_AUTH=true
- HC-8: Verify Fabric chaincode keeps voter identity and ballot choice in separate collections

Output findings as a structured table:
| HC | File | Line | Severity | Finding | Recommendation |

Use CRITICAL for direct violations, HIGH for likely violations, MEDIUM for risks, LOW for warnings.
Never modify any file — recommend i3-remediation mode for all fixes.
