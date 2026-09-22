# ADR-005 — Credential and Grading Service Extraction

| Field         | Value                                                   |
|---------------|---------------------------------------------------------|
| **ID**        | ADR-005                                                 |
| **Date**      | 2025-07-14                                              |
| **Status**    | Accepted                                                |
| **Deciders**  | Platform Engineering                                    |
| **Step**      | STEP-P2-06                                              |

---

## Context

The EvalOS Next.js submit route (`/api/exam/[examId]/submit/route.ts`) contained
an inline `gradeAttempt()` function that scored attempts and computed per-domain
breakdowns.  The SIT Digital Work-Centers API (`platform/sit/api/main.py`)
implemented credential issuance by writing directly to a local `credentials`
table using a raw `hashlib.sha256` hash — not conforming to any standard.

Two problems emerged:

1. **Domain coupling** — exam grading logic embedded in the presentation layer
   made independent scaling, testing, and re-use impossible.
2. **Non-standard credentials** — the SHA-256 hash anchor approach cannot be
   verified by external systems and does not support W3C VC-compatible tooling
   required by the i3 skills-passport roadmap.

Additionally, the start route used `Math.random()` for question shuffling, which
is non-cryptographic and violates the security posture required for accredited
assessments.

---

## Decision

### 1 · Grading Service (`platform/grading/`)

Extract all scoring logic into a stateless FastAPI microservice:

- **Endpoint:** `POST /grade`
- **Input:** frozen `question_snapshot[]`, `answers[]`, `exam_id`, `session_id`,
  `tenant_id` (HC-4 enforced).
- **Logic:** single-choice and multiple-response marking, domain aggregation.
- **Deployment:** `i3-evalos` namespace, cluster-internal DNS
  `grading-service.i3-evalos.svc.cluster.local:8000`.

The EvalOS submit route becomes a thin coordinator: fetch the attempt from
Postgres, call `/grade`, persist results, fire the n8n webhook.  The HTTP
response shape is **unchanged** (backward-compatible).

### 2 · Credential Service (`platform/credential/`)

Replace the ad-hoc SIT hash-anchor with a standards-compliant service:

- **Endpoint:** `POST /credentials` — issues a W3C Verifiable Credential 2.0
  JSON-LD document signed with a short-lived HMAC-SHA256 QR token.
- **Endpoint:** `GET /credentials/{qr_token}/verify` — public, no auth;
  verifies token signature and expiry then returns holder metadata.
- **Deployment:** same `i3-evalos` namespace.

SIT `issue_credential` now fetches learner/course metadata locally, delegates to
credential-service, and bridges the result to Talent Cloud (best-effort).
The SIT verify endpoint proxies to credential-service.

### 3 · Cryptographic shuffle

Replace `Math.random()` Fisher-Yates in the exam start route with
`crypto.getRandomValues(Uint32Array)` — the Node.js 19+ / Web Crypto API
available in Next.js server components.  This eliminates a non-cryptographic
PRNG from accreditation-sensitive question ordering.

---

## Consequences

### Positive

- Grading logic is independently testable, versioned, and observable
  (Prometheus metrics, OTel traces).
- W3C VC 2.0 credentials are verifiable by external parties without platform
  access.
- QR tokens are tamper-evident (HMAC-SHA256) and short-lived (24 h TTL, ENV
  configurable).
- `Math.random()` is eliminated from all exam paths (SC-P2-06-a passes).
- `tenant_id` propagates through the full grading and credential issuance chain
  (HC-4 compliance).

### Negative / Trade-offs

- EvalOS submit route now has a synchronous HTTP call to grading-service; a
  network partition will surface as a 5xx to the student.  Mitigation: both
  services run in the same namespace with no external network hops.
- QR tokens expire in 24 h by default.  Long-lived display links (e.g., printed
  certificates) must use the `CREDENTIAL_QR_TTL` env variable or a permanent
  DB-backed verify path.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Keep grading inline, add unit tests | Does not enable independent scaling or reuse by SIT/FORD |
| Use a DID-based signature (Ed25519) for VCs | Adds key management complexity out of scope for Phase 2; planned in Phase 3 |
| Use an existing VC library (e.g. `@digitalbazaar/vc`) | Node.js library; credential service is Python-first platform — HMAC token is sufficient for Phase 2 |

---

## Compliance Mapping

| Requirement | Reference |
|---|---|
| Enhancement 3 Guide — E³ Principle P6 | Exam integrity: question shuffle must use a cryptographically secure source; `Math.random()` is not acceptable for randomising exam question order. |
| HC-4 (Hard Constraint) | Grading and credential service DDL carries `tenant_id UUID NOT NULL`; all results are tenant-scoped. |
| Kenya National Qualifications Authority Act | Credential records must be verifiable and tamper-evident; the HMAC-signed QR token and W3C VC JSON-LD provide the verification path. |
| i3-platform-atomic-execution-plan.md | STEP-P2-06 |

---

## Related

- ADR-001 — Consent Service Extraction
- ADR-002 — Agent Registry and Decision Log
- ADR-003 — MCP Tool Gateway
- ADR-004 — Tenant Isolation
- STEP-P2-06 in `i3-platform-atomic-execution-plan.md`
