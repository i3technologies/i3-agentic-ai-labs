"""
Tests — trace_flywheel.py
File: platform/agentic-os/tests/test_trace_flywheel.py

Covers:
  F1  DPO pair emitted when supervisor_override is present
  F2  Golden SFT record emitted when human_approved=True and no override
  F3  None returned for unapproved, unoverridden trace
  F4  HC-4: tenant_id is present in every emitted record
  F5  HC-6: provenance_hash is HMAC-SHA256, NOT raw SHA-256
  F6  HC-6: provenance_hash zeroes gracefully when MEMBER_HMAC_SECRET is unset
  F7  supervisor_override takes priority over human_approved
"""

from __future__ import annotations

import hashlib
import hmac
import os

import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trace_flywheel import DecisionTrace, process_flywheel_trace

TENANT    = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
TRACE_ID  = "trace-0001"
PROMPT    = "Enrol Jane Doe in AI Engineering"
GENERATED = {"action": "enrol", "student_id": "S-001"}
OVERRIDE  = {"action": "enrol", "student_id": "S-001", "reviewed": True}
SECRET    = "test-hmac-secret"


def _make_trace(**kwargs) -> DecisionTrace:
    defaults = dict(
        trace_id=TRACE_ID,
        tenant_id=TENANT,
        model_version="ibm-granite-3b-instruct",
        prompt=PROMPT,
        generated_action=GENERATED,
        supervisor_override=None,
        human_approved=False,
    )
    defaults.update(kwargs)
    return DecisionTrace(**defaults)


# ── F1: DPO pair ───────────────────────────────────────────────────────────────

def test_dpo_pair_emitted_when_override_present(monkeypatch):
    monkeypatch.setenv("MEMBER_HMAC_SECRET", SECRET)
    trace  = _make_trace(supervisor_override=OVERRIDE)
    result = process_flywheel_trace(trace)

    assert result is not None
    assert result["type"]    == "DPO_PAIR"
    assert result["chosen"]  == OVERRIDE
    assert result["rejected"] == GENERATED
    assert result["prompt"]  == PROMPT


# ── F2: Golden SFT ────────────────────────────────────────────────────────────

def test_golden_sft_emitted_when_human_approved(monkeypatch):
    monkeypatch.setenv("MEMBER_HMAC_SECRET", SECRET)
    trace  = _make_trace(human_approved=True)
    result = process_flywheel_trace(trace)

    assert result is not None
    assert result["type"]       == "GOLDEN_SFT"
    assert result["completion"] == GENERATED
    assert result["prompt"]     == PROMPT


# ── F3: None for unactionable trace ───────────────────────────────────────────

def test_none_returned_for_unapproved_unoverridden(monkeypatch):
    monkeypatch.setenv("MEMBER_HMAC_SECRET", SECRET)
    trace  = _make_trace()
    result = process_flywheel_trace(trace)
    assert result is None


# ── F4: HC-4 tenant_id present ────────────────────────────────────────────────

@pytest.mark.parametrize("human_approved,override", [
    (True,  None),
    (False, OVERRIDE),
])
def test_tenant_id_in_every_record(monkeypatch, human_approved, override):
    monkeypatch.setenv("MEMBER_HMAC_SECRET", SECRET)
    trace  = _make_trace(human_approved=human_approved, supervisor_override=override)
    result = process_flywheel_trace(trace)

    assert result is not None
    assert result["tenant_id"] == TENANT


# ── F5: HC-6 provenance_hash is HMAC-SHA256, not raw SHA-256 ─────────────────

def test_provenance_hash_is_hmac_not_raw_sha256(monkeypatch):
    monkeypatch.setenv("MEMBER_HMAC_SECRET", SECRET)
    trace  = _make_trace(human_approved=True)
    result = process_flywheel_trace(trace)

    expected_hmac = hmac.new(
        SECRET.encode(), TRACE_ID.encode(), hashlib.sha256
    ).hexdigest()
    raw_sha256 = hashlib.sha256(TRACE_ID.encode()).hexdigest()

    assert result["provenance_hash"] == expected_hmac
    # Guard: HMAC must differ from raw SHA-256 so the check is meaningful
    assert expected_hmac != raw_sha256, "test secret produced collision — choose a different secret"
    assert result["provenance_hash"] != raw_sha256, "HC-6 VIOLATION: raw SHA-256 used for provenance"


# ── F6: HC-6 graceful zero when secret is absent ─────────────────────────────

def test_provenance_hash_zeroes_when_secret_missing(monkeypatch):
    monkeypatch.delenv("MEMBER_HMAC_SECRET", raising=False)
    # Force reload so the module re-reads the env var
    import importlib
    import provenance as prov
    importlib.reload(prov)
    import trace_flywheel as tf
    importlib.reload(tf)

    trace  = tf.DecisionTrace(
        trace_id=TRACE_ID,
        tenant_id=TENANT,
        model_version="ibm-granite-3b-instruct",
        prompt=PROMPT,
        generated_action=GENERATED,
        human_approved=True,
    )
    result = tf.process_flywheel_trace(trace)

    assert result is not None
    # Zero-string sentinel: 64 hex zeros
    assert result["provenance_hash"] == "0" * 64


# ── F7: override takes priority over human_approved ──────────────────────────

def test_override_takes_priority_over_human_approved(monkeypatch):
    monkeypatch.setenv("MEMBER_HMAC_SECRET", SECRET)
    trace  = _make_trace(supervisor_override=OVERRIDE, human_approved=True)
    result = process_flywheel_trace(trace)

    assert result is not None
    assert result["type"] == "DPO_PAIR", "override must produce DPO_PAIR, not GOLDEN_SFT"
