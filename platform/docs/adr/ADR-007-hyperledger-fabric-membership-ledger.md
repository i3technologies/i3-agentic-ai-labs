# ADR-007 — Hyperledger Fabric Membership Ledger

| Field       | Value                                                       |
|-------------|-------------------------------------------------------------|
| **ID**      | ADR-007                                                     |
| **Title**   | Hyperledger Fabric Membership Ledger for FORD-Asili         |
| **Status**  | Accepted                                                    |
| **Date**    | 2025-07-01                                                  |
| **Authors** | i3 Technologies Engineering Team                            |
| **Depends** | ADR-001 (Consent Service), ADR-004 (Tenant Isolation)       |

---

## Context

The FORD-Asili platform registers political-party members in Machakos County ahead of the 16 March 2027 IEBC statutory deadline.  Registration data has two distinct sensitivity profiles:

1. **Identity tokens** — HMAC-SHA256 hashes of national IDs and phone numbers.  Must be auditable, immutable, and tamper-evident, but must never expose raw PII.
2. **Ballot choices** — a voter's party-primary selection.  Must be architecturally isolated from the identity record (HC-8 ballot secrecy).

PostgreSQL alone cannot provide cryptographic finality, non-repudiation, or a multi-party audit trail required by electoral stakeholders.

A centralised database also creates a single party (i3 Technologies) as the sole custodian of registration proofs — a political and legal risk for FORD-Asili.

---

## Decision

**We will use Hyperledger Fabric as the append-only, tamper-evident ledger for FORD-Asili membership records.**

The `MembershipRegistry` smart contract (Go) is deployed to `ford-channel`.  It stores:

- `MEMBER::{id_hash}` — membership record with HMAC tokens, ward code, and status
- `WARD_COUNT::{wardCode}` — monotonic ward-level registration counter
- `AGENT_DUTY::{agentId}` — per-agent cycle duty counter

Ballot choices are **never written to this chaincode or to `ford-channel`**.  A separate private data collection (`voteChoicesCollection`) with `memberOnlyRead: true` and a distinct endorsement policy is defined in [`collections_config.json`](../../ford/fabric/collections_config.json), ensuring cryptographic separation at the peer level.

### Integration Architecture

```
Feature phone
  └─ Africa's Talking USSD *509#
       └─ POST /ussd  →  ford-ussd-bridge (Python/FastAPI)
            └─ POST /api/v1/members/register  →  ford-api (Python/FastAPI)
                 ├─ asyncpg → PostgreSQL  (primary store, Phase 3 transition)
                 ├─ Redis   (OTP, velocity, Fabric retry queue)
                 └─ POST /gateway/v1/commit  →  Fabric Gateway REST shim
                      └─ ford-channel peer endorsement
                           └─ MembershipRegistry.RegisterMember (Go chaincode)
```

### Ballot-Secrecy Separation (HC-8)

```
ford-channel (public ledger)          voteChoicesCollection (PDC)
────────────────────────────          ──────────────────────────────
MEMBER::{id_hash}                     { member_id_hash, choice_hash }
WARD_COUNT::{wardCode}                policy: FordPeerMSP.peer only
TurnoutEvent (Fabric event)           memberOnlyRead: true
                                      NOT queryable from MembershipRegistry
```

The `MembershipRegistry` chaincode has **no read or write path** to `voteChoicesCollection`.  A future ballot chaincode deployed under a separate namespace will manage that collection.

### Public Verification (no PII)

The endpoint `GET /api/v1/members/verify/{public_token}` returns:

```json
{ "registered": true, "ward_code": "001", "verified_at": "2025-07-01T12:00:00Z" }
```

`public_token` is `HMAC-SHA256(member_id + nonce)` generated at registration and stored in PostgreSQL.  It does not encode or permit derivation of a national ID or phone number.

---

## Consequences

### Positive

- **Cryptographic finality**: Fabric block hashes provide an immutable audit trail acceptable to IEBC observers.
- **Multi-party auditability**: The `IEBCObserverMSP` peer is a member of `turnoutAuditCollection`, allowing independent verification without i3 involvement.
- **HC-8 compliance**: Architectural separation between identity and ballot data is enforced by the PDC policy at the Fabric peer level, not by application-layer logic alone.
- **HC-6 compliance**: No raw national IDs or phone numbers ever enter the chaincode; all tokens are HMAC-SHA256 produced under the KMS-backed `MEMBER_HMAC_SECRET`.
- **Resilience**: Fabric is fire-and-forget in Phase 3; PostgreSQL remains the authoritative store.  A Redis-backed retry queue ensures eventual consistency if the gateway is unreachable.

### Negative / Trade-offs

- **Operational complexity**: Running a Fabric network on OpenShift (HLF Operator) adds peer, orderer, and CA management overhead.
- **Latency**: Fabric endorsement adds ~200–800 ms per registration.  Mitigated by the fire-and-forget pattern in Phase 3 (OTP verification returns before Fabric confirms).
- **Go chaincode build pipeline**: Requires a Go 1.21 build step in the Tekton pipeline alongside the existing Python/Node services.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| PostgreSQL-only with WAL archiving | No cryptographic finality; i3 Technologies is sole custodian — electoral risk |
| Ethereum/EVM smart contracts | Public chain costs; GDPR/DPA 2019 tension with on-chain hash storage |
| IBM Blockchain Platform (IBP) | Vendor lock-in; not compatible with on-premises OpenShift air-gapped deployment constraint |
| Centralised audit log (Loki + S3) | Not tamper-evident; no multi-party endorsement model |

---

## Implementation References

| Artifact | Path |
|---|---|
| Go chaincode | `platform/ford/fabric/chaincode/membership_registry/membership_registry.go` |
| Go module | `platform/ford/fabric/chaincode/membership_registry/go.mod` |
| PDC config | `platform/ford/fabric/collections_config.json` |
| Fabric network CRDs | `platform/ford/deploy/fabric-network.yaml` |
| API service | `platform/ford/api/main.py` |
| USSD bridge | `platform/ford/ussd/handler.py` |
| Atomic step | `STEP-P3-03` in `i3-platform-atomic-execution-plan.md` |

---

## Hard-Constraint Compliance Matrix

| Constraint | How ADR-007 satisfies it |
|---|---|
| HC-2 (IEBC deadline Nov 2026) | Fabric staging target defined in STEP-P3-03 |
| HC-6 (HMAC-SHA256 for IDs) | `hmac_token()` in ford-api; chaincode only receives pre-hashed values |
| HC-8 (ballot secrecy) | `voteChoicesCollection` PDC with `memberOnlyRead: true`; zero code path between MembershipRegistry and vote choices |
| HC-4 (tenant_id everywhere) | `tenant_id` field on `MemberRecord`; passed as arg to `RegisterMember` |
| HC-5 (agents propose, policy disposes) | Fabric endorsement policy requires ≥1 FordPeerMSP peer — no single agent can unilaterally commit |
