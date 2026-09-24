"""
Tests for the IMP-11 PII pre-filter sidecar.

Run: pytest platform/tools/test_pii_filter.py -v
"""
from __future__ import annotations

import sys
import os

# Inject platform/tools onto sys.path to avoid conflict with stdlib 'platform'
_TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"
)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import pytest

from pii_filter import redact, assert_clean, PiiFilterResult


# ---------------------------------------------------------------------------
# Phone numbers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("phone", [
    "0712345678",
    "0112345678",
    "+254712345678",
    "+254 712 345 678",
    "254712345678",
])
def test_phone_ke_redacted(phone):
    result = redact(f"Contact me on {phone} for details.", use_ner=False)
    assert result.found
    assert "PHONE_KE" in result.entity_types
    assert phone.replace(" ", "") not in result.redacted_text.replace(" ", "")


def test_phone_ke_not_in_output(phone="0722000111"):
    result = redact(f"Call {phone}", use_ner=False)
    assert phone not in result.redacted_text


# ---------------------------------------------------------------------------
# Kenya National ID
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,contains_nid", [
    ("National ID: 12345678 was verified", True),
    ("NID 9876543 issued today", True),
    ("ID number 34567890", True),
    ("Kitambulisho 2345678", True),
])
def test_national_id_redacted(text, contains_nid):
    result = redact(text, use_ner=False)
    if contains_nid:
        assert result.found
        assert "KENYAN_NID" in result.entity_types


# ---------------------------------------------------------------------------
# KRA PIN
# ---------------------------------------------------------------------------

def test_kra_pin_redacted():
    result = redact("KRA PIN: A000000000Z approved", use_ner=False)
    assert result.found
    assert "KRA_PIN" in result.entity_types
    assert "A000000000Z" not in result.redacted_text


# ---------------------------------------------------------------------------
# Transaction IDs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "MPESA code: QEF3LX2RKJ confirmed",
    "Transaction ID: RA3KXYZ123 receipt",
    "Txn ID: AB12CD34EF received",
])
def test_transaction_id_redacted(text):
    result = redact(text, use_ner=False)
    assert result.found
    assert "TRANSACTION_ID" in result.entity_types


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def test_email_redacted():
    result = redact("Email me at john.doe@example.co.ke", use_ner=False)
    assert result.found
    assert "EMAIL" in result.entity_types
    assert "john.doe@example.co.ke" not in result.redacted_text


# ---------------------------------------------------------------------------
# Clean text — no false positives on common strings
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clean_text", [
    "The system responded successfully.",
    "tenant_id: 550e8400-e29b-41d4-a716-446655440000",   # UUID must NOT be flagged
    "Score: 0.85 above threshold 0.70",
    "Version 3.1.4 released",
])
def test_no_false_positives(clean_text):
    result = redact(clean_text, use_ner=False)
    assert not result.found, (
        f"False positive on: {clean_text!r}  → types={result.entity_types}"
    )


# ---------------------------------------------------------------------------
# Multiple PII in one string
# ---------------------------------------------------------------------------

def test_multiple_pii_types():
    text = (
        "Customer: National ID 12345678, "
        "phone 0711223344, email cust@mail.co.ke"
    )
    result = redact(text, use_ner=False)
    assert result.found
    assert result.span_count >= 2
    # Originals must not appear
    assert "12345678" not in result.redacted_text
    assert "0711223344" not in result.redacted_text
    assert "cust@mail.co.ke" not in result.redacted_text


# ---------------------------------------------------------------------------
# Empty / None inputs
# ---------------------------------------------------------------------------

def test_empty_string():
    result = redact("", use_ner=False)
    assert not result.found
    assert result.redacted_text == ""


# ---------------------------------------------------------------------------
# assert_clean helper
# ---------------------------------------------------------------------------

def test_assert_clean_passes_on_clean():
    assert assert_clean("No PII here at all.") == "No PII here at all."


def test_assert_clean_raises_on_pii():
    with pytest.raises(ValueError, match="PII detected"):
        assert_clean("Call me on 0712345678")


# ---------------------------------------------------------------------------
# PiiFilterResult attributes
# ---------------------------------------------------------------------------

def test_result_attributes():
    result = redact("email test@example.com here", use_ner=False)
    assert isinstance(result, PiiFilterResult)
    assert result.found is True
    assert "EMAIL" in result.entity_types
    assert result.span_count == 1
    assert "[REDACTED:EMAIL]" in result.redacted_text
