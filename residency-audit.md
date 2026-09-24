# B3 — Regional Data Residency Audit

> ⚠ **STATUS: INCOMPLETE — LIVE CLUSTER EVIDENCE REQUIRED**  
> This document is the required evidence artefact for the "Regional data residency" capability claim.  
> The claim **MAY NOT** be made in the present tense until every section below is completed and signed PASS.

| Field | Value |
|-------|-------|
| **Evidence ID** | B3-residency-audit |
| **Capability Claim** | "Regional data residency" |
| **Condition to unlock** | B3 residency audit PASS |
| **Auditor** | _[To be completed by platform team]_ |
| **Audit date** | _[YYYY-MM-DD]_ |
| **Environment** | Production cluster — `https://api.i3technologies.co.ke` |
| **Region under audit** | Nairobi, Kenya (IBM Cloud `eu-de` / designated Kenyan data-centre) |
| **Classification** | Internal Engineering |

---

## Acceptance Criteria

All of the following must be confirmed PASS before the claim is unlocked:

| # | Criterion | Status |
|---|-----------|--------|
| RC-01 | All PostgreSQL data volumes reside on storage nodes physically located in the declared Kenyan/approved-residency region | ⬜ INCOMPLETE |
| RC-02 | All S3/Object Store buckets (including WORM audit partition) are in the declared residency region | ⬜ INCOMPLETE |
| RC-03 | Kafka topic partition leaders reside in-region | ⬜ INCOMPLETE |
| RC-04 | ChromaDB vector store PVC is bound to in-region storage class | ⬜ INCOMPLETE |
| RC-05 | Redis (session/plan cache) is in-region | ⬜ INCOMPLETE |
| RC-06 | No cross-region replication routes Kenyan PII to a non-approved region | ⬜ INCOMPLETE |
| RC-07 | Keycloak token issuer URL resolves to in-region infrastructure | ⬜ INCOMPLETE |
| RC-08 | LiteLLM model routing does NOT forward prompts containing PII to non-residency-approved model endpoints | ⬜ INCOMPLETE |
| RC-09 | Network egress policy (Calico/OpenShift NetworkPolicy) blocks data-plane traffic to non-approved regions | ⬜ INCOMPLETE |
| RC-10 | Data residency documented in DPA-2019-compliant Data Processing Agreement | ⬜ INCOMPLETE |

---

## Required Evidence Checklist

Run each check and record the output below:

### RC-01 — PostgreSQL Storage Region

```bash
# Confirm storage class region label
kubectl get pvc -n i3-data -o jsonpath='{.items[*].spec.storageClassName}'
# Expected: storage class with region=<approved-region> label

kubectl get storageclass <classname> -o yaml | grep region
# Expected: region: <nairobi/eu-ke/approved-region-label>
```

**Result:** _[Paste output]_  
**Status:** ⬜ INCOMPLETE

---

### RC-02 — S3 Audit Bucket Region

```bash
# IBM Cloud COS bucket region
ibmcloud cos bucket-location-get --bucket $AUDIT_S3_BUCKET
# Expected: "LocationConstraint: <approved-region>"

# Cross-check Object Lock is COMPLIANCE (not just standard)
ibmcloud cos bucket-object-lock-configuration-get --bucket $AUDIT_S3_BUCKET
# Expected: ObjectLockEnabled: Enabled, DefaultRetention.Mode: COMPLIANCE
```

**Result:** _[Paste output]_  
**Status:** ⬜ INCOMPLETE

---

### RC-03 — Kafka Partition Leaders In-Region

```bash
kubectl exec -n i3-messaging kafka-0 -- \
  kafka-topics.sh --bootstrap-server localhost:9092 \
  --describe --topic i3.events
# Expected: Leader broker is in-region node
```

**Result:** _[Paste output]_  
**Status:** ⬜ INCOMPLETE

---

### RC-04 — ChromaDB PVC Storage Class

```bash
kubectl get pvc -n i3-admissions -l app=chromadb -o yaml | grep storageClassName
# Expected: in-region storage class
```

**Result:** _[Paste output]_  
**Status:** ⬜ INCOMPLETE

---

### RC-05 — Redis In-Region

```bash
kubectl get pod -n i3-data -l app=redis -o wide
# Expected: NODE column shows in-region node
```

**Result:** _[Paste output]_  
**Status:** ⬜ INCOMPLETE

---

### RC-06 — No Cross-Region PII Replication

```bash
# Confirm no COS replication rules route to non-approved buckets
ibmcloud cos replication-configuration-get --bucket $AUDIT_S3_BUCKET
# Expected: No rules, or all rules target in-region bucket

# Confirm database backup target is in-region
kubectl get cronjob -n i3-data -o yaml | grep -A5 "backup"
# Expected: backup destination is in-region
```

**Result:** _[Paste output]_  
**Status:** ⬜ INCOMPLETE

---

### RC-07 — Keycloak Issuer In-Region

```bash
# Resolve SSO hostname
nslookup sso.i3technologies.co.ke
# Expected: IP resolves to in-region load balancer

# Confirm JWKS endpoint is served from in-region
curl -s https://sso.i3technologies.co.ke/realms/i3/.well-known/openid-configuration \
  | jq '.issuer, .jwks_uri'
# Expected: both URIs are the in-region hostname
```

**Result:** _[Paste output]_  
**Status:** ⬜ INCOMPLETE

---

### RC-08 — LiteLLM Model Routing (No PII Egress to Non-Approved Regions)

Review `platform/model-gateway/litellm/litellm-config-oss.yaml` and confirm:
- No model endpoint routes to a non-approved-region API (e.g., external OpenAI endpoint for PII-bearing requests)
- watsonx.ai tier-1 endpoints are in IBM Cloud `eu-de` (Frankfurt) — confirm this is approved for Kenyan PII under the applicable DPA or note if a Kenyan-region watsonx.ai endpoint must be used instead

**Reviewed by:** _[Name]_  
**Finding:** _[Document any non-compliant model routes]_  
**Status:** ⬜ INCOMPLETE

---

### RC-09 — Network Egress Policy

```bash
# List NetworkPolicies restricting egress
kubectl get networkpolicy -A | grep -i egress
# Expected: egress policies in all data-bearing namespaces (i3-data, i3-auth, i3-consent, i3-messaging)

# Confirm no wildcard egress 0.0.0.0/0 in data namespaces
kubectl get networkpolicy -n i3-data -o yaml | grep -A5 "egress"
```

**Result:** _[Paste output]_  
**Status:** ⬜ INCOMPLETE

---

### RC-10 — Data Processing Agreement

| DPA Field | Value |
|-----------|-------|
| DPA reference number | _[To be completed]_ |
| Effective date | _[YYYY-MM-DD]_ |
| Data controller | i3 Technologies (Instrumented Interconnected & Intelligent Technologies Limited) |
| Declared data residency region | _[e.g., Kenya / IBM Cloud eu-de with DPA carve-out]_ |
| DPA compliance with Kenya DPA 2019 | _[Confirmed / Pending legal review]_ |
| Signed by | _[Name, Role]_ |

**Status:** ⬜ INCOMPLETE

---

## Overall Verdict

**Current status: INCOMPLETE — claim LOCKED**

| Criterion | Status |
|-----------|--------|
| RC-01 PostgreSQL storage region | ⬜ |
| RC-02 S3 audit bucket region | ⬜ |
| RC-03 Kafka in-region | ⬜ |
| RC-04 ChromaDB PVC in-region | ⬜ |
| RC-05 Redis in-region | ⬜ |
| RC-06 No cross-region PII replication | ⬜ |
| RC-07 Keycloak issuer in-region | ⬜ |
| RC-08 LiteLLM no PII egress to non-approved region | ⬜ |
| RC-09 Network egress policy enforced | ⬜ |
| RC-10 DPA-2019 compliant agreement | ⬜ |

**All 10 criteria must be ✅ PASS before this artefact may be signed.**

---

## Sign-Off (complete when all criteria PASS)

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Platform Architect | | | |
| Security Lead | | | |
| Data Protection Officer | | | |

---

*Document path: `residency-audit.md`*  
*Template generated by Bob AI Auditor · i3 AI Platform*  
*Do not mark PASS until all RC-01 → RC-10 sensor checks are completed with live cluster evidence.*
