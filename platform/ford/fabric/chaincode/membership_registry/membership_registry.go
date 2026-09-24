// membership_registry.go — MembershipRegistry chaincode for FORD-Asili
// Deployed to: ford-channel
// HC-6: All identity tokens are HMAC-SHA256 hashes — no raw national IDs or phone numbers
//        ever enter this chaincode.
// HC-8: This chaincode has ZERO read/write path to voteChoicesCollection.
// HC-4: tenant_id is stored on every MemberRecord.
// HC-5: Endorsement policy requires ≥1 FordPeerMSP peer — no single agent can commit alone.
package main

import (
	"encoding/json"
	"fmt"
	"strconv"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// ── State key prefixes ──────────────────────────────────────────────────────
const (
	memberPrefix    = "MEMBER::"
	wardCountPrefix = "WARD_COUNT::"
	agentDutyPrefix = "AGENT_DUTY::"
)

// MemberRecord is the on-chain membership record.
// Only HMAC-SHA256 tokens are stored — never raw national IDs or phone numbers (HC-6).
type MemberRecord struct {
	IDHash      string `json:"id_hash"`     // HMAC-SHA256(national_id, MEMBER_HMAC_SECRET)
	PhoneHash   string `json:"phone_hash"`  // HMAC-SHA256(phone_number, MEMBER_HMAC_SECRET)
	WardCode    string `json:"ward_code"`
	TenantID    string `json:"tenant_id"`   // HC-4 — UUID
	AgentID     string `json:"agent_id"`
	Status      string `json:"status"`      // "active" | "revoked"
	RegisteredAt string `json:"registered_at"` // ISO8601
	RevokedAt   string `json:"revoked_at,omitempty"`
	RevokeReason string `json:"revoke_reason,omitempty"`
}

// MembershipRegistry is the Fabric smart contract.
type MembershipRegistry struct {
	contractapi.Contract
}

// RegisterMember records a verified FORD-Asili member on the ledger.
// idHash and phoneHash must be HMAC-SHA256 tokens produced by the ford-api
// service before this function is called (HC-6).
func (s *MembershipRegistry) RegisterMember(
	ctx contractapi.TransactionContextInterface,
	idHash string,
	phoneHash string,
	wardCode string,
	tenantID string,
	agentID string,
	timestamp string,
) error {
	if idHash == "" || phoneHash == "" || wardCode == "" || tenantID == "" {
		return fmt.Errorf("idHash, phoneHash, wardCode and tenantID are required")
	}

	key := memberPrefix + idHash

	// Idempotency: if already registered and active, return success (no double-count).
	existing, err := ctx.GetStub().GetState(key)
	if err != nil {
		return fmt.Errorf("failed to read world state: %w", err)
	}
	if existing != nil {
		var rec MemberRecord
		if jsonErr := json.Unmarshal(existing, &rec); jsonErr == nil && rec.Status == "active" {
			return nil // already registered — idempotent
		}
	}

	rec := MemberRecord{
		IDHash:       idHash,
		PhoneHash:    phoneHash,
		WardCode:     wardCode,
		TenantID:     tenantID,
		AgentID:      agentID,
		Status:       "active",
		RegisteredAt: timestamp,
	}
	data, err := json.Marshal(rec)
	if err != nil {
		return fmt.Errorf("failed to marshal member record: %w", err)
	}
	if err := ctx.GetStub().PutState(key, data); err != nil {
		return fmt.Errorf("failed to write member record: %w", err)
	}

	// Increment ward counter
	if err := s.incrementCounter(ctx, wardCountPrefix+wardCode); err != nil {
		return fmt.Errorf("failed to update ward count: %w", err)
	}
	// Increment agent duty counter
	if agentID != "" {
		if err := s.incrementCounter(ctx, agentDutyPrefix+agentID); err != nil {
			return fmt.Errorf("failed to update agent duty count: %w", err)
		}
	}

	// Emit TurnoutEvent (readable by IEBCObserverMSP peer via event subscription)
	payload, _ := json.Marshal(map[string]string{
		"ward_code":  wardCode,
		"tenant_id":  tenantID,
		"registered_at": timestamp,
	})
	_ = ctx.GetStub().SetEvent("TurnoutEvent", payload)

	return nil
}

// VerifyMember returns true if the member is registered and not revoked.
func (s *MembershipRegistry) VerifyMember(
	ctx contractapi.TransactionContextInterface,
	idHash string,
) (bool, error) {
	data, err := ctx.GetStub().GetState(memberPrefix + idHash)
	if err != nil {
		return false, fmt.Errorf("failed to read world state: %w", err)
	}
	if data == nil {
		return false, nil
	}
	var rec MemberRecord
	if err := json.Unmarshal(data, &rec); err != nil {
		return false, fmt.Errorf("failed to unmarshal member record: %w", err)
	}
	return rec.Status == "active", nil
}

// GetWardCount returns the total active registrations for a ward.
func (s *MembershipRegistry) GetWardCount(
	ctx contractapi.TransactionContextInterface,
	wardCode string,
) (int, error) {
	return s.readCounter(ctx, wardCountPrefix+wardCode)
}

// GetAgentDutyCount returns registrations performed by an agent in the current cycle.
func (s *MembershipRegistry) GetAgentDutyCount(
	ctx contractapi.TransactionContextInterface,
	agentID string,
) (int, error) {
	return s.readCounter(ctx, agentDutyPrefix+agentID)
}

// RevokeMember revokes a member registration. Only an authorised MSP admin may
// invoke this function (enforced via endorsement policy in the channel config).
func (s *MembershipRegistry) RevokeMember(
	ctx contractapi.TransactionContextInterface,
	idHash string,
	reason string,
	revokedAt string,
) error {
	key := memberPrefix + idHash
	data, err := ctx.GetStub().GetState(key)
	if err != nil {
		return fmt.Errorf("failed to read world state: %w", err)
	}
	if data == nil {
		return fmt.Errorf("member not found: %s", idHash)
	}
	var rec MemberRecord
	if err := json.Unmarshal(data, &rec); err != nil {
		return fmt.Errorf("failed to unmarshal member record: %w", err)
	}
	if rec.Status == "revoked" {
		return nil // already revoked — idempotent
	}
	rec.Status = "revoked"
	rec.RevokedAt = revokedAt
	rec.RevokeReason = reason

	updated, err := json.Marshal(rec)
	if err != nil {
		return fmt.Errorf("failed to marshal updated record: %w", err)
	}
	return ctx.GetStub().PutState(key, updated)
}

// ── Internal counter helpers ─────────────────────────────────────────────────

func (s *MembershipRegistry) incrementCounter(ctx contractapi.TransactionContextInterface, key string) error {
	n, err := s.readCounter(ctx, key)
	if err != nil {
		return err
	}
	return ctx.GetStub().PutState(key, []byte(strconv.Itoa(n+1)))
}

func (s *MembershipRegistry) readCounter(ctx contractapi.TransactionContextInterface, key string) (int, error) {
	data, err := ctx.GetStub().GetState(key)
	if err != nil {
		return 0, fmt.Errorf("failed to read counter %s: %w", key, err)
	}
	if data == nil {
		return 0, nil
	}
	n, err := strconv.Atoi(string(data))
	if err != nil {
		return 0, fmt.Errorf("invalid counter value for %s: %w", key, err)
	}
	return n, nil
}

// ── Entry point ──────────────────────────────────────────────────────────────

func main() {
	cc, err := contractapi.NewChaincode(&MembershipRegistry{})
	if err != nil {
		panic(fmt.Sprintf("error creating MembershipRegistry chaincode: %v", err))
	}
	if err := cc.Start(); err != nil {
		panic(fmt.Sprintf("error starting MembershipRegistry chaincode: %v", err))
	}
}
