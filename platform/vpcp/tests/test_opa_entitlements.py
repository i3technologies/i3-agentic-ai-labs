"""
VPCP — OPA Entitlements Policy Unit Tests
File: platform/vpcp/tests/test_opa_entitlements.py

Evaluates platform/vpcp/policies/entitlements.rego using the `opa` CLI
as a subprocess, exercising every decision rule with positive and negative
inputs.  Tests are skipped automatically when the `opa` binary is absent
(CI environments without OPA installed).

Test scenarios:
  OPA-1  tenant_id_present = false when tenant_id is empty / absent
  OPA-2  tenant_id_present = true for a valid UUID
  OPA-3  allow_deal_registration = false for wrong role
  OPA-4  allow_deal_registration = false for KYC PENDING
  OPA-5  allow_deal_registration = false when tenant_id missing
  OPA-6  allow_deal_registration = true for approved admin partner
  OPA-7  download_factory_kit = false when <2 active agent_ai_engineer certs
  OPA-8  download_factory_kit = false when 0 active forward_deployed_engineer
  OPA-9  download_factory_kit = false when is_active=false (cert revoked)
  OPA-10 download_factory_kit = true when all conditions met
  OPA-11 Cross-tenant: tenant_id_present scopes decision to input only
         (Tenant A input cannot produce a result referencing Tenant B)

HC-4: every test input carries a non-empty tenant_id (or deliberately omits it
      to assert that the guard fires).
HC-7: no DEV_BYPASS_AUTH present in any input document.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# OPA binary discovery
# ---------------------------------------------------------------------------

OPA_BIN = shutil.which("opa")
POLICY_PATH = Path(__file__).parent.parent / "policies" / "entitlements.rego"

pytestmark = pytest.mark.skipif(
    OPA_BIN is None,
    reason="opa binary not found on PATH — install OPA to run policy tests",
)

TENANT_A = "a1b2c3d4-0000-0000-0000-000000000001"
TENANT_B = "b9b2c3d4-0000-0000-0000-000000000002"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def eval_opa(rule: str, input_doc: dict[str, Any]) -> Any:
    """
    Run `opa eval` against the entitlements policy and return the value
    of the specified rule (e.g. "data.partner.entitlements.allow_deal_registration").
    """
    result = subprocess.run(
        [
            OPA_BIN,
            "eval",
            "--data", str(POLICY_PATH),
            "--input", "/dev/stdin",
            "--format", "raw",
            f"data.partner.entitlements.{rule}",
        ],
        input=json.dumps(input_doc).encode(),
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"opa eval failed:\nstdout={result.stdout.decode()}\nstderr={result.stderr.decode()}"
    )
    return json.loads(result.stdout.decode().strip())


def _base_input(
    *,
    tenant_id: str = TENANT_A,
    kyc_status: str = "APPROVED",
    tier: str = "Solution",
    role: str = "partner_admin",
    certifications: list | None = None,
) -> dict:
    """Build a minimal valid input document."""
    if certifications is None:
        certifications = []
    return {
        "tenant_id": tenant_id,
        "partner": {
            "id": "partner-uuid-001",
            "kyc_status": kyc_status,
            "tier": tier,
            "certifications": certifications,
        },
        "user": {
            "sub": "user-uuid-001",
            "role": role,
        },
    }


def _certs(*tracks_active: tuple[str, bool]) -> list:
    return [{"track": t, "is_active": a} for t, a in tracks_active]


# ---------------------------------------------------------------------------
# OPA-1/2 — tenant_id_present guard
# ---------------------------------------------------------------------------

class TestTenantIdPresent:
    def test_empty_tenant_id_is_not_present(self):
        doc = _base_input(tenant_id="")
        assert eval_opa("tenant_id_present", doc) is False

    def test_valid_uuid_is_present(self):
        doc = _base_input(tenant_id=TENANT_A)
        assert eval_opa("tenant_id_present", doc) is True

    def test_missing_tenant_id_key_is_not_present(self):
        doc = _base_input()
        del doc["tenant_id"]
        assert eval_opa("tenant_id_present", doc) is False


# ---------------------------------------------------------------------------
# OPA-3/4/5/6 — allow_deal_registration
# ---------------------------------------------------------------------------

class TestAllowDealRegistration:
    def test_approved_admin_solution_tier_allowed(self):
        """OPA-6: All conditions met → True."""
        doc = _base_input(kyc_status="APPROVED", tier="Solution", role="partner_admin")
        assert eval_opa("allow_deal_registration", doc) is True

    def test_approved_sales_registered_tier_allowed(self):
        doc = _base_input(kyc_status="APPROVED", tier="Registered", role="partner_sales")
        assert eval_opa("allow_deal_registration", doc) is True

    def test_approved_admin_authorised_sovereign_allowed(self):
        doc = _base_input(kyc_status="APPROVED", tier="Authorised_Sovereign", role="partner_admin")
        assert eval_opa("allow_deal_registration", doc) is True

    def test_approved_admin_oem_embedded_allowed(self):
        doc = _base_input(kyc_status="APPROVED", tier="OEM_Embedded", role="partner_admin")
        assert eval_opa("allow_deal_registration", doc) is True

    def test_wrong_role_viewer_denied(self):
        """OPA-3: partner_viewer has no deal registration entitlement."""
        doc = _base_input(role="partner_viewer")
        assert eval_opa("allow_deal_registration", doc) is False

    def test_kyc_pending_denied(self):
        """OPA-4: KYC not APPROVED → denied."""
        doc = _base_input(kyc_status="PENDING")
        assert eval_opa("allow_deal_registration", doc) is False

    def test_kyc_rejected_denied(self):
        doc = _base_input(kyc_status="REJECTED")
        assert eval_opa("allow_deal_registration", doc) is False

    def test_missing_tenant_id_denied(self):
        """OPA-5: HC-4 guard fires — no tenant_id → denied."""
        doc = _base_input(tenant_id="")
        assert eval_opa("allow_deal_registration", doc) is False

    def test_default_deny_empty_input(self):
        """Deny-by-default: empty input document returns False."""
        assert eval_opa("allow_deal_registration", {}) is False


# ---------------------------------------------------------------------------
# OPA-7/8/9/10 — download_factory_kit
# ---------------------------------------------------------------------------

class TestDownloadFactoryKit:
    def _sovereign_input(self, certs: list) -> dict:
        return _base_input(tier="Authorised_Sovereign", certifications=certs)

    def test_all_certs_active_sovereign_allowed(self):
        """OPA-10: 2 active agent_ai_engineer + 1 active FDE → True."""
        certs = _certs(
            ("agent_ai_engineer", True),
            ("agent_ai_engineer", True),
            ("forward_deployed_engineer", True),
        )
        doc = self._sovereign_input(certs)
        assert eval_opa("download_factory_kit", doc) is True

    def test_oem_embedded_tier_with_full_certs_allowed(self):
        certs = _certs(
            ("agent_ai_engineer", True),
            ("agent_ai_engineer", True),
            ("forward_deployed_engineer", True),
        )
        doc = _base_input(tier="OEM_Embedded", certifications=certs)
        assert eval_opa("download_factory_kit", doc) is True

    def test_only_one_agent_ai_engineer_denied(self):
        """OPA-7: only 1 active agent_ai_engineer → denied."""
        certs = _certs(
            ("agent_ai_engineer", True),
            ("forward_deployed_engineer", True),
        )
        doc = self._sovereign_input(certs)
        assert eval_opa("download_factory_kit", doc) is False

    def test_no_forward_deployed_engineer_denied(self):
        """OPA-8: 2 agent_ai_engineers but 0 FDE → denied."""
        certs = _certs(
            ("agent_ai_engineer", True),
            ("agent_ai_engineer", True),
        )
        doc = self._sovereign_input(certs)
        assert eval_opa("download_factory_kit", doc) is False

    def test_cert_revocation_drops_access_immediately(self):
        """
        OPA-9: Percipio revokes an engineer → is_active=False.
        Previously 2 active agent_ai_engineers; now only 1 → denied.
        This is the cert-revocation scenario from the Step 4 test spec.
        """
        certs = _certs(
            ("agent_ai_engineer", True),
            ("agent_ai_engineer", False),  # ← revoked by Percipio mock
            ("forward_deployed_engineer", True),
        )
        doc = self._sovereign_input(certs)
        assert eval_opa("download_factory_kit", doc) is False

    def test_all_certs_revoked_denied(self):
        certs = _certs(
            ("agent_ai_engineer", False),
            ("agent_ai_engineer", False),
            ("forward_deployed_engineer", False),
        )
        doc = self._sovereign_input(certs)
        assert eval_opa("download_factory_kit", doc) is False

    def test_wrong_tier_solution_denied(self):
        """Solution tier is NOT in factory_kit_tiers."""
        certs = _certs(
            ("agent_ai_engineer", True),
            ("agent_ai_engineer", True),
            ("forward_deployed_engineer", True),
        )
        doc = _base_input(tier="Solution", certifications=certs)
        assert eval_opa("download_factory_kit", doc) is False

    def test_missing_tenant_id_denied_for_factory_kit(self):
        """HC-4: empty tenant_id → factory kit also denied."""
        certs = _certs(
            ("agent_ai_engineer", True),
            ("agent_ai_engineer", True),
            ("forward_deployed_engineer", True),
        )
        doc = _base_input(tenant_id="", tier="Authorised_Sovereign", certifications=certs)
        assert eval_opa("download_factory_kit", doc) is False

    def test_extra_inactive_certs_do_not_help(self):
        """Three agent_ai certs but only 1 active → still denied."""
        certs = _certs(
            ("agent_ai_engineer", True),
            ("agent_ai_engineer", False),
            ("agent_ai_engineer", False),
            ("forward_deployed_engineer", True),
        )
        doc = self._sovereign_input(certs)
        assert eval_opa("download_factory_kit", doc) is False


# ---------------------------------------------------------------------------
# OPA-11 — Cross-tenant isolation
# ---------------------------------------------------------------------------

class TestCrossTenantIsolation:
    """
    OPA-11: An input document carrying Tenant A's tenant_id cannot produce a
    decision that references Tenant B's entitlements.  The policy is purely
    input-scoped — there is no shared state, no DB query, and no cross-tenant
    reference in the Rego.

    These tests confirm that:
      (a) Tenant A with APPROVED credentials is allowed.
      (b) If the same input is re-evaluated with Tenant B's UUID, the
          allow decision reflects ONLY Tenant B's input fields —
          demonstrating that the policy is stateless and input-scoped.
    """

    def test_tenant_a_allowed_independently(self):
        doc = _base_input(tenant_id=TENANT_A, kyc_status="APPROVED", role="partner_admin")
        assert eval_opa("allow_deal_registration", doc) is True

    def test_tenant_b_with_same_profile_also_allowed(self):
        """Tenant B with identical profile is also allowed — isolation is per-request."""
        doc = _base_input(tenant_id=TENANT_B, kyc_status="APPROVED", role="partner_admin")
        assert eval_opa("allow_deal_registration", doc) is True

    def test_tenant_b_with_pending_kyc_denied(self):
        """Tenant B with PENDING KYC is denied, regardless of Tenant A's status."""
        doc = _base_input(tenant_id=TENANT_B, kyc_status="PENDING", role="partner_admin")
        assert eval_opa("allow_deal_registration", doc) is False

    def test_no_cross_contamination_between_evaluations(self):
        """
        Two sequential evaluations with different tenant_ids must not influence
        each other.  OPA is stateless; each eval call starts fresh.
        """
        doc_a = _base_input(tenant_id=TENANT_A, kyc_status="APPROVED")
        doc_b = _base_input(tenant_id=TENANT_B, kyc_status="PENDING")

        result_a = eval_opa("allow_deal_registration", doc_a)
        result_b = eval_opa("allow_deal_registration", doc_b)

        assert result_a is True
        assert result_b is False
