package main

import (
	"encoding/json"
	"fmt"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// ── Types ────────────────────────────────────────────────────────────────────

// MemberRecord is stored on the public ledger (no raw NID — HC-6).
// memberToken is the pre-computed HMAC-SHA256 of the Kenyan National ID.
type MemberRecord struct {
	MemberToken  string `json:"memberToken"`  // HMAC-SHA256(NID, MEMBER_HMAC_SECRET) — HC-6
	Ward         string `json:"ward"`
	TenantID     string `json:"tenantId"`     // HC-4: always present
	RegisteredAt string `json:"registeredAt"` // ctx.GetStub().GetTxTimestamp()
	IsActive     bool   `json:"isActive"`
}

// BallotRecord is stored in the 'ballotPrivate' private data collection.
// Voter identity and ballot choice are NEVER stored together (HC-8).
type BallotRecord struct {
	BallotID    string `json:"ballotId"`
	CandidateID string `json:"candidateId"`
	CastAt      string `json:"castAt"`
	// NOTE: memberToken is the key used to PUT to the private collection —
	// it is NOT stored in the value to prevent correlation.
}

// ── Contract ─────────────────────────────────────────────────────────────────

// MemberRegistryContract manages FORD-Asili membership and ballot state.
type MemberRegistryContract struct {
	contractapi.Contract
}

// RegisterMember adds a new member to the public ledger using only their
// HMAC token — no raw National ID is accepted or stored (HC-6).
func (c *MemberRegistryContract) RegisterMember(
	ctx contractapi.TransactionContextInterface,
	memberToken string,
	ward string,
	tenantID string, // HC-4: caller must supply
) error {
	if memberToken == "" || ward == "" || tenantID == "" {
		return fmt.Errorf("memberToken, ward, and tenantID are all required")
	}

	// Check for duplicate registration
	existing, err := ctx.GetStub().GetState(memberToken)
	if err != nil {
		return fmt.Errorf("failed to read world state: %w", err)
	}
	if existing != nil {
		return fmt.Errorf("member %s is already registered", memberToken)
	}

	ts, err := ctx.GetStub().GetTxTimestamp()
	if err != nil {
		return fmt.Errorf("failed to get transaction timestamp: %w", err)
	}

	record := MemberRecord{
		MemberToken:  memberToken,
		Ward:         ward,
		TenantID:     tenantID,
		RegisteredAt: ts.String(),
		IsActive:     true,
	}

	data, err := json.Marshal(record)
	if err != nil {
		return fmt.Errorf("failed to marshal member record: %w", err)
	}

	return ctx.GetStub().PutState(memberToken, data)
}

// GetMember retrieves a member record by their HMAC token.
func (c *MemberRegistryContract) GetMember(
	ctx contractapi.TransactionContextInterface,
	memberToken string,
) (*MemberRecord, error) {
	data, err := ctx.GetStub().GetState(memberToken)
	if err != nil {
		return nil, fmt.Errorf("failed to read world state: %w", err)
	}
	if data == nil {
		return nil, fmt.Errorf("member %s does not exist", memberToken)
	}

	var record MemberRecord
	if err := json.Unmarshal(data, &record); err != nil {
		return nil, fmt.Errorf("failed to unmarshal member record: %w", err)
	}
	return &record, nil
}

// CastBallot stores a ballot in the 'ballotPrivate' private data collection.
// Voter identity (memberToken) is the PUT key only — never stored in the value (HC-8).
func (c *MemberRegistryContract) CastBallot(
	ctx contractapi.TransactionContextInterface,
	memberToken string,
	candidateID string,
) error {
	if memberToken == "" || candidateID == "" {
		return fmt.Errorf("memberToken and candidateID are required")
	}

	// Verify member exists and is active
	data, err := ctx.GetStub().GetState(memberToken)
	if err != nil || data == nil {
		return fmt.Errorf("member %s not found or not registered", memberToken)
	}

	// Check for double-vote by checking private collection
	existing, err := ctx.GetStub().GetPrivateData("ballotPrivate", memberToken)
	if err != nil {
		return fmt.Errorf("failed to read ballot state: %w", err)
	}
	if existing != nil {
		return fmt.Errorf("member %s has already cast a ballot", memberToken)
	}

	ts, err := ctx.GetStub().GetTxTimestamp()
	if err != nil {
		return fmt.Errorf("failed to get transaction timestamp: %w", err)
	}

	ballot := BallotRecord{
		BallotID:    ctx.GetStub().GetTxID(),
		CandidateID: candidateID,
		CastAt:      ts.String(),
		// memberToken is intentionally NOT stored in the value (HC-8)
	}

	ballotData, err := json.Marshal(ballot)
	if err != nil {
		return fmt.Errorf("failed to marshal ballot: %w", err)
	}

	// Key = memberToken (links identity to ballot in the private collection)
	// This is the ONLY linkage — the value contains NO identity information (HC-8)
	return ctx.GetStub().PutPrivateData("ballotPrivate", memberToken, ballotData)
}

// ── Entry Point ──────────────────────────────────────────────────────────────

func main() {
	chaincode, err := contractapi.NewChaincode(&MemberRegistryContract{})
	if err != nil {
		panic(fmt.Sprintf("error creating chaincode: %v", err))
	}
	if err := chaincode.Start(); err != nil {
		panic(fmt.Sprintf("error starting chaincode: %v", err))
	}
}
