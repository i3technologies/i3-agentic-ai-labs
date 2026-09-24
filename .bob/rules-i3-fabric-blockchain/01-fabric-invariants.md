# i3 Fabric & Trust Engineer — Supplementary Rules

These rules apply only when the i3-fabric-blockchain mode is active.
They supplement the Go standards in `.bob/rules/02-architecture-standards.md`.

---

## HC-8 — Ballot Secrecy: Physical Data Separation

Voter registration and ballot casting are **architecturally separated systems**:

| Data | Storage | Collection | Access |
|------|---------|------------|--------|
| Member registration (identity) | Public ledger | `memberRegistry` | All peers |
| Ballot submission (vote choice) | Private data | `ballotPrivate` | Org members only |

**Required `collections_config.json` for any voting chaincode:**
```json
[
  {
    "name": "ballotPrivate",
    "policy": "OR('FORD-Org1MSP.member')",
    "requiredPeerCount": 1,
    "maxPeerCount": 3,
    "blockToLive": 0,
    "memberOnlyRead": true,
    "memberOnlyWrite": true
  }
]
```

**NEVER** combine voter identity and ballot choice in:
- The same state key
- The same collection
- The same transaction response
- The same log line

---

## HC-6 — No Raw National IDs On-Chain

All member identifiers stored on-chain MUST be pre-computed HMAC-SHA256 tokens.

| Field name | Allowed | Forbidden |
|------------|---------|-----------|
| `memberToken` | ✅ HMAC token from client | ❌ Raw NID |
| `idNumber` | ❌ Forbidden field name | — |
| `nationalId` | ❌ Forbidden field name | — |
| `nid` | ❌ Forbidden field name | — |

The token is computed off-chain by the client using `MEMBER_HMAC_SECRET` from OpenBao.
Chaincode receives and stores only the token — it never computes or validates the HMAC itself.

---

## Chaincode Determinism Rules

Chaincode MUST be deterministic. Forbidden patterns:

- `time.Now()` — use `ctx.GetStub().GetTxTimestamp()` instead
- `rand.Intn()` or any random number generation
- `http.Get()` or any external HTTP calls
- Non-deterministic map iteration (use sorted keys)
- `os.Getenv()` — use chaincode parameters or collection config

---

## IEBC Deadline Tracking

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Chaincode unit tests passing | Q3 2025 | Track |
| Private data collection verified | Q3 2025 | Track |
| Staging deployment | November 2026 | **HC-2 statutory** |
| IEBC go-live | 16 March 2027 | **HC-2 statutory** |

Never propose an architecture that cannot meet the November 2026 staging deadline.

---

## Pre-Commit Sensor Checks

Before marking any chaincode step complete:
```bash
# Unit tests
go test ./...

# No raw NID field names
grep -rn "nationalId\|\.nid\|idNumber" . --include="*.go"   # must be 0 lines

# No HTTP calls from chaincode
grep -rn "net/http\|http\.Get\|http\.Post" . --include="*.go"  # must be 0 lines in chaincode

# ballotPrivate collection defined
grep "ballotPrivate" collections_config.json   # must match
```
