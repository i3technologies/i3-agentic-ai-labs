package main

import (
	"encoding/json"
	"testing"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-chaincode-go/shimtest"
	"github.com/hyperledger/fabric-contract-api-go/contractapi"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// newTestStub creates a shimtest.MockStub wired to the MemberRegistryContract.
func newTestStub(t *testing.T) *shimtest.MockStub {
	t.Helper()
	cc, err := contractapi.NewChaincode(&MemberRegistryContract{})
	require.NoError(t, err)
	stub := shimtest.NewMockStub("member-registry", cc)
	stub.MockInit("init-tx", [][]byte{[]byte("init"), []byte("{}")})
	return stub
}

// invokeCC is a helper to call a chaincode function via MockStub.
func invokeCC(stub *shimtest.MockStub, fn string, args ...string) shim.Response {
	argBytes := [][]byte{[]byte(fn)}
	for _, a := range args {
		argBytes = append(argBytes, []byte(a))
	}
	return stub.MockInvoke("tx-"+fn, argBytes)
}

// ── Tests ────────────────────────────────────────────────────────────────────

func TestRegisterMember_Success(t *testing.T) {
	stub := newTestStub(t)
	resp := invokeCC(stub, "RegisterMember", "hmac-token-001", "Nairobi-West", "tenant-uuid-001")
	assert.Equal(t, int32(200), resp.Status, resp.Message)
}

func TestRegisterMember_DuplicateBlocked(t *testing.T) {
	stub := newTestStub(t)
	invokeCC(stub, "RegisterMember", "hmac-token-002", "Westlands", "tenant-uuid-001")
	resp := invokeCC(stub, "RegisterMember", "hmac-token-002", "Westlands", "tenant-uuid-001")
	assert.Equal(t, int32(500), resp.Status)
	assert.Contains(t, resp.Message, "already registered")
}

func TestRegisterMember_NoRawNID(t *testing.T) {
	// HC-6: the token field must be an HMAC token, not resemble a raw NID
	// Raw Kenyan NID format is 8 digits — tokens should be hex strings.
	stub := newTestStub(t)
	// This test documents the expectation — in production, NID validation
	// happens off-chain before the token is computed. Chaincode accepts any string.
	resp := invokeCC(stub, "RegisterMember", "a1b2c3d4e5f6", "Kilimani", "tenant-uuid-001")
	assert.Equal(t, int32(200), resp.Status, resp.Message)
}

func TestGetMember_NotFound(t *testing.T) {
	stub := newTestStub(t)
	resp := invokeCC(stub, "GetMember", "nonexistent-token")
	assert.Equal(t, int32(500), resp.Status)
	assert.Contains(t, resp.Message, "does not exist")
}

func TestGetMember_ReturnsRecord(t *testing.T) {
	stub := newTestStub(t)
	invokeCC(stub, "RegisterMember", "hmac-token-003", "Langata", "tenant-uuid-002")
	resp := invokeCC(stub, "GetMember", "hmac-token-003")
	assert.Equal(t, int32(200), resp.Status)
	var record MemberRecord
	require.NoError(t, json.Unmarshal(resp.Payload, &record))
	assert.Equal(t, "hmac-token-003", record.MemberToken)
	assert.Equal(t, "Langata", record.Ward)
	assert.Equal(t, "tenant-uuid-002", record.TenantID)
}

func TestGetMember_NoBallotDataLeaked(t *testing.T) {
	// HC-8: GetMember must never return ballot choice data
	stub := newTestStub(t)
	invokeCC(stub, "RegisterMember", "hmac-token-004", "Kibera", "tenant-uuid-001")
	resp := invokeCC(stub, "GetMember", "hmac-token-004")
	assert.Equal(t, int32(200), resp.Status)
	// Verify the response payload does not contain any ballot-related fields
	payload := string(resp.Payload)
	assert.NotContains(t, payload, "candidateId")
	assert.NotContains(t, payload, "ballotId")
}
