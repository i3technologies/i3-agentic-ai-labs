---
name: chaincode-scaffold
description: Scaffolds Hyperledger Fabric 2.5 Go chaincode for the FORD-Asili system — enforces ballot secrecy (HC-8), no raw NID on-chain (HC-6), and private data collection separation. Use when writing new chaincode contracts or USSD bridge state machines.
---

When creating or modifying Hyperledger Fabric chaincode:

## 1. Directory Layout

```
platform/fabric/chaincode/<ContractName>/
├── go.mod                  (module i3-ford/<ContractName>; go 1.22)
├── go.sum
├── <contractname>.go       (chaincode implementation)
├── <contractname>_test.go  (unit tests using shimtest.MockStub)
└── collections_config.json (private data collection definitions)
```

## 2. Chaincode Invariants (Non-Negotiable)

### HC-8 — Ballot Secrecy
- **NEVER** store voter identity and ballot choice in the same state key or collection.
- Voter registration → public ledger collection (`memberRegistry`).
- Ballot submissions → PRIVATE data collection (`ballotPrivate`) with `memberOnlyPolicy`.
- The `ballotPrivate` collection MUST have `blockToLive: 0` (permanent) and `memberOnlyRead: true`.

### HC-6 — No Raw National IDs On-Chain
- All member identifiers stored on-chain MUST be HMAC-SHA256 tokens, never raw Kenyan National IDs.
- Use the pre-computed token passed by the client — never compute the hash inside chaincode.
- Token field name convention: `memberToken` (not `nationalId`, `nid`, or `idNumber`).

### HC-3 — Autonomy Ceiling
- Chaincode may READ and WRITE state; it MUST NOT invoke external HTTP calls autonomously.
- Any cross-contract call requires a corresponding policy check emitted as a `Decision` event.

## 3. Minimal Chaincode Template

```go
package main

import (
    "encoding/json"
    "fmt"
    "github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// MemberRecord — public registry entry (no raw NID)
type MemberRecord struct {
    MemberToken string `json:"memberToken"` // HMAC-SHA256 of NID — HC-6
    Ward        string `json:"ward"`
    TenantID    string `json:"tenantId"`    // HC-4
    RegisteredAt string `json:"registeredAt"`
}

type MemberRegistryContract struct {
    contractapi.Contract
}

func (c *MemberRegistryContract) RegisterMember(
    ctx contractapi.TransactionContextInterface,
    memberToken, ward, tenantId string,
) error {
    existing, _ := ctx.GetStub().GetState(memberToken)
    if existing != nil {
        return fmt.Errorf("member already registered")
    }
    record := MemberRecord{
        MemberToken:  memberToken,
        Ward:         ward,
        TenantID:     tenantId,
        RegisteredAt: ctx.GetStub().GetTxTimestamp().String(),
    }
    data, err := json.Marshal(record)
    if err != nil {
        return err
    }
    return ctx.GetStub().PutState(memberToken, data)
}
```

## 4. Private Data Collection Config (`collections_config.json`)

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

## 5. USSD State Machine Rules

When building Africa's Talking USSD handlers:
- State is persisted to Redis with a TTL of **300 seconds** (5 minutes) per session.
- Session key format: `ussd:<sessionId>:<msisdn>` — never store raw MSISDN; use HMAC token.
- State transitions must be validated against the allowed FSM graph before execution.
- All Kafka events emitted from USSD flows MUST include `tenantid` (HC-4).

## 6. Pre-Commit Checklist

Run these sensor checks before marking a chaincode step complete:

```bash
# Unit tests
go test ./...

# No raw NID references
grep -rn "nationalId\|nid\|idNumber" . --include="*.go"  # must return 0 lines

# No HTTP calls in chaincode
grep -rn "http\." . --include="*.go"  # must return 0 lines in chaincode files

# HC-8: ballotPrivate collection defined
grep -l "ballotPrivate" collections_config.json  # must match
```
