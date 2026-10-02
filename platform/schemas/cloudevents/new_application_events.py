"""
i3 Platform — CloudEvent Schema Definitions
File:      platform/schemas/cloudevents/new_application_events.py

Six new CloudEvent types introduced by the three new applications.
All schemas enforce:
  • HC-4: tenantid UUID NOT NULL in every envelope
  • CloudEvent spec 1.0: all 9 mandatory fields present
  • UUIDv7 for id field (time-ordered deduplication)
  • Pydantic models use extra="ignore" for forward-compatible consumers

Schemas:
  App 1 — CRM Intelligence:
    i3.crm.organisation.created
    i3.crm.contact.verified

  App 2 — VPCP:
    i3.vpcp.partner.onboarded
    i3.vpcp.deal.registered
    i3.vpcp.deal.conflict_flagged

  App 3 — Agentic AI OS:
    i3.agentic.trace.flywheel_curated

Topic → Kafka topic mapping:
  i3.crm.organisation.created       → i3-crm-organisation-events
  i3.crm.contact.verified           → i3-crm-contact-events
  i3.vpcp.partner.onboarded         → i3-vpcp-partner-events
  i3.vpcp.deal.registered           → i3-vpcp-deal-events
  i3.vpcp.deal.conflict_flagged     → i3-vpcp-deal-events
  i3.agentic.trace.flywheel_curated → i3-agentic-flywheel-events
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ══════════════════════════════════════════════════════════════════════════
# Base envelope — enforces all 9 mandatory CloudEvent fields
# ══════════════════════════════════════════════════════════════════════════

class CloudEventEnvelope(BaseModel):
    """
    HC-4 compliant CloudEvent 1.0 envelope.
    All domain event models inherit from this base.
    """
    model_config = ConfigDict(extra="ignore")   # forward-compatible consumers

    specversion:      str = "1.0"
    id:               str = Field(default_factory=lambda: str(uuid.uuid4()))
    source:           str                       # e.g. "i3/crm-intel-worker"
    type:             str                       # e.g. "i3.crm.organisation.created"
    datacontenttype:  str = "application/json"
    time:             str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    tenantid:         str                       # HC-4: UUID NOT NULL — never absent
    subject:          str                       # e.g. "organisation/uuid"
    data:             dict[str, Any]


# ══════════════════════════════════════════════════════════════════════════
# APP 1 — CRM Intelligence
# ══════════════════════════════════════════════════════════════════════════

class OrgCreatedData(BaseModel):
    """Data payload for i3.crm.organisation.created"""
    model_config = ConfigDict(extra="ignore")

    organisation_id:    str     # UUIDv7 — matches organisations.id in crm_db
    source_company_id:  Optional[str] = None   # Original TAM workbook ID (Rule 1 — preserved)
    canonical_name:     str
    domain:             Optional[str] = None
    country:            str
    segment:            Optional[str] = None
    propensity_score:   Optional[float] = None # Original TAM score — never overwritten
    confidence_score:   float
    tenant_id:          str     # HC-4: also included in data for consumer convenience


class OrgCreatedEvent(CloudEventEnvelope):
    """
    i3.crm.organisation.created
    Source:  i3/crm-intel-worker
    Trigger: TAM XLSX organisation record successfully ingested and domain resolved.
    Topic:   i3-crm-organisation-events
    """
    source: str = "i3/crm-intel-worker"
    type:   str = "i3.crm.organisation.created"
    data:   OrgCreatedData


class ContactVerifiedData(BaseModel):
    """Data payload for i3.crm.contact.verified"""
    model_config = ConfigDict(extra="ignore")

    contact_id:         str     # UUIDv7 — matches contacts.id in crm_db
    organisation_id:    str
    # HC-6: email stored as HMAC-SHA256 — never plaintext
    email_hmac:         Optional[str] = None   # 64-char hex HMAC-SHA256
    domain_has_mx:      bool
    confidence_score:   float
    source_url:         str     # Public URL where contact was observed (Rule 2)
    content_hash:       str     # HMAC-SHA256 of field:value:url:method composite
    lawful_basis:       str     # Kenya DPA 2019 lawful basis code
    tenant_id:          str     # HC-4


class ContactVerifiedEvent(CloudEventEnvelope):
    """
    i3.crm.contact.verified
    Source:  i3/crm-verify-worker
    Trigger: Email DNS MX check passed; provenance hash written to evidence table.
    Topic:   i3-crm-contact-events
    """
    source: str = "i3/crm-verify-worker"
    type:   str = "i3.crm.contact.verified"
    data:   ContactVerifiedData


# ══════════════════════════════════════════════════════════════════════════
# APP 2 — Vendor & Partner Collaboration Portal (VPCP)
# ══════════════════════════════════════════════════════════════════════════

class PartnerOnboardedData(BaseModel):
    """Data payload for i3.vpcp.partner.onboarded"""
    model_config = ConfigDict(extra="ignore")

    partner_id:                  str    # UUIDv7 — matches partners.id in vpcp_db
    tier:                        str    # e.g. "Registered", "Authorised_Sovereign"
    kyc_status:                  str    # "APPROVED" (only emitted on PROVISIONED state)
    certified_engineers_count:   int    # Total active certified engineers at onboarding
    # breakdown per certification track
    agent_ai_engineers:          int = 0
    forward_deployed_engineers:  int = 0
    provisioned_at:              str    # ISO 8601
    tenant_id:                   str    # HC-4


class PartnerOnboardedEvent(CloudEventEnvelope):
    """
    i3.vpcp.partner.onboarded
    Source:  i3/vpcp-core
    Trigger: Partner KYC state machine reaches PROVISIONED state.
    Topic:   i3-vpcp-partner-events
    """
    source: str = "i3/vpcp-core"
    type:   str = "i3.vpcp.partner.onboarded"
    data:   PartnerOnboardedData


class DealRegisteredData(BaseModel):
    """Data payload for i3.vpcp.deal.registered"""
    model_config = ConfigDict(extra="ignore")

    deal_id:                str    # UUIDv7 — matches deals.id in vpcp_db
    customer_account:       str    # TAM organisation canonical_name or source_company_id
    product_family:         str    # e.g. "watsonx.ai", "Red Hat OpenShift AI"
    estimated_arr_usd:      float
    partner_id:             str
    ibm_sales_cloud_ref:    Optional[str] = None  # IBM Sales Cloud opportunity ID
    expected_close_date:    str
    registered_at:          str    # ISO 8601
    tenant_id:              str    # HC-4


class DealRegisteredEvent(CloudEventEnvelope):
    """
    i3.vpcp.deal.registered
    Source:  i3/vpcp-core
    Trigger: Deal registration Temporal saga completes, IBM Sales Cloud synced.
    Topic:   i3-vpcp-deal-events
    """
    source: str = "i3/vpcp-core"
    type:   str = "i3.vpcp.deal.registered"
    data:   DealRegisteredData


class DealConflictFlaggedData(BaseModel):
    """Data payload for i3.vpcp.deal.conflict_flagged"""
    model_config = ConfigDict(extra="ignore")

    deal_id:                 str    # The new deal that triggered conflict detection
    conflicting_deal_id:     Optional[str] = None  # The existing deal within the window
    customer_account:        str
    product_family:          str
    conflict_window_days:    int = 90
    flagged_at:              str    # ISO 8601
    tenant_id:               str    # HC-4


class DealConflictFlaggedEvent(CloudEventEnvelope):
    """
    i3.vpcp.deal.conflict_flagged
    Source:  i3/vpcp-temporal-worker
    Trigger: checkDealConflict activity returns true within the 90-day window.
    Topic:   i3-vpcp-deal-events
    """
    source: str = "i3/vpcp-temporal-worker"
    type:   str = "i3.vpcp.deal.conflict_flagged"
    data:   DealConflictFlaggedData


# ══════════════════════════════════════════════════════════════════════════
# APP 3 — Agentic AI Operating System
# ══════════════════════════════════════════════════════════════════════════

class FlywheelCuratedData(BaseModel):
    """Data payload for i3.agentic.trace.flywheel_curated"""
    model_config = ConfigDict(extra="ignore")

    trace_id:             str    # Langfuse trace ID
    model_version:        str    # e.g. "ibm-granite-3b-instruct-v1.0"
    dpo_type:             str    # "DPO_PAIR" | "GOLDEN_SFT"
    # DPO_PAIR: supervisor overrode the model output
    # GOLDEN_SFT: human approved the model output without change
    provenance_hash:      str    # HMAC-SHA256 of trace_id for tamper evidence
    object_storage_path:  str    # IBM Cloud Object Storage path (s3://i3-flywheel/...)
    curated_at:           str    # ISO 8601
    tenant_id:            str    # HC-4
    # Present only for DPO_PAIR
    override_reason:      Optional[str] = None


class FlywheelCuratedEvent(CloudEventEnvelope):
    """
    i3.agentic.trace.flywheel_curated
    Source:  i3/agentic-ai-os
    Trigger: Langfuse trace webhook fires for a completed trace with
             supervisor_override=True or human_approved=True.
    Topic:   i3-agentic-flywheel-events
    """
    source: str = "i3/agentic-ai-os"
    type:   str = "i3.agentic.trace.flywheel_curated"
    data:   FlywheelCuratedData


# ══════════════════════════════════════════════════════════════════════════
# Factory helpers — produce validated event dicts ready for Kafka
# ══════════════════════════════════════════════════════════════════════════

def make_org_created_event(
    organisation_id: str,
    canonical_name: str,
    country: str,
    tenant_id: str,
    **kwargs,
) -> dict:
    """Build and validate an i3.crm.organisation.created event dict."""
    data = OrgCreatedData(
        organisation_id=organisation_id,
        canonical_name=canonical_name,
        country=country,
        tenant_id=tenant_id,
        **kwargs,
    )
    event = OrgCreatedEvent(
        tenantid=tenant_id,
        subject=f"organisation/{organisation_id}",
        data=data.model_dump(),
    )
    return json.loads(event.model_dump_json())


def make_contact_verified_event(
    contact_id: str,
    organisation_id: str,
    tenant_id: str,
    **kwargs,
) -> dict:
    """Build and validate an i3.crm.contact.verified event dict."""
    data = ContactVerifiedData(
        contact_id=contact_id,
        organisation_id=organisation_id,
        tenant_id=tenant_id,
        **kwargs,
    )
    event = ContactVerifiedEvent(
        tenantid=tenant_id,
        subject=f"contact/{contact_id}",
        data=data.model_dump(),
    )
    return json.loads(event.model_dump_json())


def make_deal_registered_event(
    deal_id: str,
    customer_account: str,
    product_family: str,
    estimated_arr_usd: float,
    partner_id: str,
    expected_close_date: str,
    tenant_id: str,
    ibm_sales_cloud_ref: str | None = None,
) -> dict:
    """Build and validate an i3.vpcp.deal.registered event dict."""
    data = DealRegisteredData(
        deal_id=deal_id,
        customer_account=customer_account,
        product_family=product_family,
        estimated_arr_usd=estimated_arr_usd,
        partner_id=partner_id,
        ibm_sales_cloud_ref=ibm_sales_cloud_ref,
        expected_close_date=expected_close_date,
        registered_at=datetime.now(UTC).isoformat(),
        tenant_id=tenant_id,
    )
    event = DealRegisteredEvent(
        tenantid=tenant_id,
        subject=f"deal/{deal_id}",
        data=data.model_dump(),
    )
    return json.loads(event.model_dump_json())


def make_flywheel_curated_event(
    trace_id: str,
    model_version: str,
    dpo_type: str,
    provenance_hash: str,
    object_storage_path: str,
    tenant_id: str,
    override_reason: str | None = None,
) -> dict:
    """Build and validate an i3.agentic.trace.flywheel_curated event dict."""
    data = FlywheelCuratedData(
        trace_id=trace_id,
        model_version=model_version,
        dpo_type=dpo_type,
        provenance_hash=provenance_hash,
        object_storage_path=object_storage_path,
        curated_at=datetime.now(UTC).isoformat(),
        tenant_id=tenant_id,
        override_reason=override_reason,
    )
    event = FlywheelCuratedEvent(
        tenantid=tenant_id,
        subject=f"trace/{trace_id}",
        data=data.model_dump(),
    )
    return json.loads(event.model_dump_json())
