# VPCP — OPA Entitlement Guardrail
# Package: partner.entitlements
# File:    platform/vpcp/policies/entitlements.rego
#
# Evaluated by the OPA sidecar co-located with the VPCP Core API pod.
# Called via:  POST http://localhost:8181/v1/data/partner/entitlements
#
# Expected input document shape:
# {
#   "partner": {
#     "id":       "<uuid>",
#     "kyc_status": "APPROVED" | "PENDING" | "REJECTED",
#     "tier":     "Registered" | "Solution" | "Authorised_Sovereign" | "OEM_Embedded",
#     "certifications": [
#       { "track": "agent_ai_engineer",       "is_active": true },
#       { "track": "forward_deployed_engineer","is_active": true }
#     ]
#   },
#   "user": {
#     "sub":  "<keycloak-sub-uuid>",
#     "role": "partner_admin" | "partner_sales" | "partner_viewer"
#   },
#   "tenant_id": "<uuid>"   # HC-4: must be present on every call
# }
#
# HC-4: tenant_id must be present on every input document — rule
#        `tenant_id_present` guards all downstream decisions.
# HC-5: This policy only authorises; it never mutates state directly.
# HC-7: No DEV_BYPASS_AUTH path exists in this policy.

package partner.entitlements

# ── Defaults ──────────────────────────────────────────────────────────────────
default allow_deal_registration = false
default download_factory_kit    = false
default tenant_id_present       = false

# ── HC-4 Guard ────────────────────────────────────────────────────────────────
# Every decision depends on a non-empty tenant_id in the input.
tenant_id_present {
    input.tenant_id != ""
    count(input.tenant_id) > 0
}

# ── Helper: Collect active certifications for a given track ───────────────────
certified_engineers(track) = certs {
    certs := [cert |
        cert := input.partner.certifications[_]
        cert.track    == track
        cert.is_active == true
    ]
}

# ── Tier sets ─────────────────────────────────────────────────────────────────
deal_registration_tiers := {
    "Registered",
    "Solution",
    "Authorised_Sovereign",
    "OEM_Embedded",
}

factory_kit_tiers := {
    "Authorised_Sovereign",
    "OEM_Embedded",
}

# ── Deal Registration Entitlement ─────────────────────────────────────────────
# Conditions:
#   1. HC-4: tenant_id must be present.
#   2. Partner KYC must be APPROVED.
#   3. Requesting user must hold partner_admin or partner_sales role.
#   4. Partner tier must be one of the four deal-eligible tiers.
allow_deal_registration {
    tenant_id_present
    input.partner.kyc_status               == "APPROVED"
    input.user.role                         in {"partner_admin", "partner_sales"}
    input.partner.tier                      in deal_registration_tiers
}

# ── Factory Integration Kit Download ─────────────────────────────────────────
# Conditions:
#   1. HC-4: tenant_id must be present.
#   2. Partner tier must be Authorised_Sovereign or OEM_Embedded.
#   3. At least 2 active Agent AI Engineers on record.
#   4. At least 1 active Forward Deployed Engineer on record.
#
# NOTE: kyc_status is intentionally NOT required here because factory kit
#       access is a post-onboarding capability gated solely on tier + certs.
#       Add `input.partner.kyc_status == "APPROVED"` here if policy changes.
download_factory_kit {
    tenant_id_present
    input.partner.tier in factory_kit_tiers
    count(certified_engineers("agent_ai_engineer"))       >= 2
    count(certified_engineers("forward_deployed_engineer")) >= 1
}
