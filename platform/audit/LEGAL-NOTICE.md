# LEGAL-NOTICE.md — WORM Audit Retention Parameters (IMP-09)

## Status: ⚠ OPEN LEGAL QUESTION — Not Yet Confirmed

This document tracks the unresolved legal questions around the audit log
retention configuration for the i3 AI Platform WORM audit pipeline (IMP-09).

---

## Affected Parameters

| Parameter | Config Location | Current Default | Legal Status |
|-----------|----------------|-----------------|--------------|
| `AUDIT_RETENTION_DAYS` | `audit-config` ConfigMap | 2557 (≈7 years) | **Pending legal review** |
| `AUDIT_LOCK_MODE` | `audit-config` ConfigMap | `COMPLIANCE` | **Pending legal review** |

---

## Open Questions

1. **Minimum retention period**: What is the minimum number of days that
   audit logs must be retained under applicable Kenyan data protection law
   (Data Protection Act 2019, Cap 411C), IEBC regulations, and any sector-
   specific requirements for financial services and electoral systems?

2. **Maximum retention period**: Is there a data-minimisation requirement
   (under the Data Protection Act or GDPR-equivalent guidance) that caps how
   long audit logs may be stored?

3. **Object Lock mode**: Should the retention lock be `COMPLIANCE` (prevents
   deletion even by bucket owners) or `GOVERNANCE` (allows privileged users
   to override)?  `COMPLIANCE` is the more conservative default but may
   interfere with legal-hold override workflows.

4. **Cross-border data residency**: If audit objects are stored in a non-Kenyan
   S3 region, does this trigger additional consent or notification obligations?

---

## Current Conservative Defaults

The defaults (2557 days / COMPLIANCE) were chosen as conservative placeholders:

- **2557 days ≈ 7 years**: Aligns with common financial-services retention
  periods in East Africa but is **not** confirmed as legally required.
- **COMPLIANCE mode**: Prevents premature deletion and is the safest default,
  but must be approved before production deployment because it cannot be
  reversed during the lock period.

---

## Action Required Before Production Deployment

- [ ] Obtain written sign-off from legal counsel on `AUDIT_RETENTION_DAYS`.
- [ ] Obtain written sign-off from legal counsel on `AUDIT_LOCK_MODE`.
- [ ] Update `platform/audit/cronjob-tamper-check.yaml` ConfigMap with
      the confirmed values.
- [ ] Remove the `legal-review-required: "true"` annotation from the
      ConfigMap once sign-off is received.
- [ ] Record sign-off reference (e.g. legal ticket number) in this file.

---

## Sign-off Record

| Date | Reviewer | Decision | Reference |
|------|----------|----------|-----------|
| *(pending)* | *(pending)* | *(pending)* | *(pending)* |
