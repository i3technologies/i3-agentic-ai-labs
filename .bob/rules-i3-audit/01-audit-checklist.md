# i3 Platform Auditor — Supplementary Rules

These rules apply only when the i3-audit mode is active.
They define the audit methodology, severity guide, and per-HC checklist.

---

## Audit Methodology

1. **Read, never write.** Use `read_file`, `grep`, and MCP tools only. Never use `apply_diff`,
   `write_file`, or `execute_command` with side effects.
2. **Reference constraints by ID.** Every finding must cite the specific HC number (HC-1 through HC-8).
3. **Structured output only.** All findings must be in the standard findings table format.
4. **Recommend, don't fix.** End every finding with: *"Switch to 🛡️ i3-remediation mode to apply this fix."*

---

## Standard Findings Table Format

```
| File | Line | HC | Severity | Finding | Recommendation |
|------|------|----|----------|---------|----------------|
| platform/foo/bar.py | 42 | HC-4 | HIGH | INSERT missing tenant_id | Add tenant_id column to INSERT statement |
```

---

## Severity Guide

| Severity | Meaning | Examples |
|----------|---------|---------|
| CRITICAL | Direct constraint violation, exploitable now | Raw NID in DB, `DEV_BYPASS_AUTH=true` in code, L2 agent in prod |
| HIGH | Constraint violation with likely exploit path | Missing RLS policy, asyncpg.connect() in handler |
| MEDIUM | Risk of constraint violation under specific conditions | Missing tenant_id index, no HMAC on phone number |
| LOW | Code quality or future-risk issue | Hardcoded default tenant ID, missing `go test` coverage |
| INFO | Observation, no risk | Deprecated API usage, missing docstring |

---

## Per-HC Audit Checklist

### HC-1 — Namespace Isolation
- [ ] No file references `solution-01` through `solution-08` in modified manifests
- [ ] `platform/namespaces/namespaces.yaml` does not define forbidden namespaces

### HC-3 — Autonomy Ceiling
- [ ] All agent manifest YAML files have `autonomy_level: L0` or `autonomy_level: L1`
- [ ] No manifest contains keywords: `L2`, `L3`, `autonomous`, `full_autonomy`
- [ ] Use `validate_agent_manifest` MCP tool for automated check

### HC-4 — Multi-Tenancy
- [ ] Every `CREATE TABLE` statement has `tenant_id UUID NOT NULL`
- [ ] Every `CREATE TABLE` has `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`
- [ ] Every `INSERT INTO` statement includes `tenant_id` column
- [ ] Every Kafka CloudEvent payload includes a `tenantid` UUID field
- [ ] Use `audit_sql_ast` MCP tool for automated SQL check
- [ ] Use `verify_cloudevent_envelope` MCP tool for CloudEvent check

### HC-6 — Anonymisation
- [ ] No Python or TypeScript file calls `hashlib.sha256(nid)` or `crypto.createHash('sha256')` on raw IDs
- [ ] All NID/phone references use `hmac.new(key, msg, hashlib.sha256)` with `MEMBER_HMAC_SECRET`
- [ ] No raw NID stored in any database column or Kafka event

### HC-7 — Auth Bypass Gate
- [ ] `DEV_BYPASS_AUTH=true` does not appear in any non-gitignored file
- [ ] Use `test_prompt_injection` MCP tool to test suspicious input strings

### HC-8 — Ballot Secrecy
- [ ] Go chaincode does not store voter identity and ballot choice in the same key or collection
- [ ] `collections_config.json` defines `ballotPrivate` with `memberOnlyRead: true`
