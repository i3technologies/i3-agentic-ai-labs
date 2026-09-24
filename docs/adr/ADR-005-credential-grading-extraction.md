# ADR-005: Credential and Grading Service Extraction

**Status:** Accepted  
**Date:** 2026-09-22  
**Deciders:** EvalOS / Trust Lead, Backend Domain Lead, Engineering Manager  

---

## Context

Exam grading logic lives inline in `platform/evalos/web/src/app/api/exam/[examId]/submit/route.ts`
and credential issuance lives inline in `platform/sit/api/main.py`.  Both are cross-domain
concerns: EvalOS, SIT, and FORD all need to issue verifiable credentials; any future exam domain
needs grading without duplicating the scoring engine.

Two additional defects exist in the current implementation:
- `Math.random()` Fisher-Yates shuffle in the exam start route is cryptographically insecure —
  an adversary who can seed the PRNG can predict question order.
- The credential QR token has no public verification endpoint, making issued credentials
  unverifiable by third parties.

E³ guide §8 (Trust & Evidence Plane) and Enhancement 3 E³ P6 (Evidence by construction) require
W3C Verifiable Credentials with a public verification endpoint.

---

## Decision

Extract grading into `platform/grading/` FastAPI service (`POST /grade`) and credential issuance
into `platform/credential/` FastAPI service (`POST /credentials`, `GET /credentials/{qr}/verify`).
Both services deploy in `i3-evalos` namespace (same network boundary as EvalOS).  
Replace `Math.random()` with `crypto.getRandomValues()` Fisher-Yates in the exam start route.  
Credential service MUST prepare a Hyperledger Fabric anchor slot for Phase 3 on-chain anchoring.

---

## Alternatives Considered

| Option | Rejected reason |
|--------|----------------|
| Keep grading inline in submit route | Prevents SIT/FORD reuse; logic duplication; harder to test in isolation |
| Use a third-party credentialing SaaS | Vendor dependency; PII leaves the cluster; HC-4 tenancy not guaranteed |
| Embed credential issuance in the Agent Registry | Scope creep; agent governance and trust evidence are separate bounded contexts |

---

## Consequences

**Positive:**
- Single grading engine — any future exam domain reuses `POST /grade` without reimplementing
  scoring logic.
- W3C VC JSON + public `GET /credentials/{qr_token}/verify` endpoint enables third-party
  credential verification without PII exposure.
- Cryptographically secure question shuffle removes the PRNG prediction attack surface.
- Fabric anchor slot means Phase 3 can add on-chain anchoring without architectural changes.

**Negative:**
- EvalOS submit route gains a synchronous dependency on grading-service; mitigated by
  co-located deployment (< 5 ms intra-namespace latency).
- W3C VC JSON-LD context requires a public hosted context URL for interoperability.

---

## Rollback Plan

If grading-service is unavailable, EvalOS submit route returns `503` (no silent data loss).
Rollback procedure:
1. `kubectl rollout undo deploy/grading-service -n i3-evalos`  
2. If rollback is to pre-extraction state: re-apply the previous `submit/route.ts` commit
   which contained inline grading; both code paths accept the same request body.

---

## Compliance Mapping

| Constraint | How this ADR satisfies it |
|-----------|--------------------------|
| HC-4 | `tenant_id UUID NOT NULL` on credential and grading tables; all API inputs require `tenant_id` |
| HC-8 | Credential service separates holder identity from assessment evidence (no co-location of voter ID and ballot) |
| E³ P6 | Evidence by construction — W3C VC is the output artefact; QR verification is the proof mechanism |
| E³ P4 | Open protocols — W3C VC 2.0 JSON-LD is an open standard |

---

## Sensor Gate (P2-GATE-05)

```bash
kubectl get pod -n i3-evalos -l app=grading-service     # Running
kubectl get pod -n i3-evalos -l app=credential-service  # Running
grep -n "Math.random" \
  "platform/evalos/web/src/app/api/exam"                # 0 matches
# POST /grade with known inputs → correct score
# POST /credentials + GET /credentials/{qr}/verify → valid:true
npm test -w platform/evalos/web                         # all pass
```
