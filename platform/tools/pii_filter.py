"""
i3 AI Platform — PII Pre-Filter Sidecar (IMP-11 / Workstream B5)

Intercepts any text string before it is written to a log, stored in a
database, or forwarded to an LLM prompt.  Applies NER-based + regex-based
redaction tuned to Kenyan identifier formats.

Identifier types covered
------------------------
  KENYAN_NID     Kenya National ID  (6–8 digit number, often labelled)
  KRA_PIN        KRA PIN  A000000000X or Pxxxxxxxx
  PHONE_KE       Kenyan phone  +254 / 07xx / 01xx patterns (10–13 digits)
  TRANSACTION_ID MPESA / bank txn IDs  (e.g. QEF3LX2RKJ, RA3KXYZ...)
  EMAIL          RFC-5321 email addresses
  IBAN           International Bank Account Number
  PASSPORT       International passport number heuristic
  NER_PER        Person name (spaCy NER — falls back gracefully if model absent)
  NER_ORG        Organisation name (spaCy NER)

All matched spans are replaced with ``[REDACTED:<TYPE>]`` tokens before
any downstream write.  The original value MUST NOT appear in logs.

Compliance notes
----------------
  HC-6: Kenyan NIDs and phone numbers are redacted at sidecar ingress; only
        the HMAC token (computed separately by the credential service) may
        flow downstream.
  HC-4: tenant_id is never redacted (it is a non-personal UUID).

Usage
-----
  from platform.tools.pii_filter import redact, PiiFilterResult

  result = redact("Call me on 0712345678, my ID is 12345678")
  print(result.redacted_text)
  # "Call me on [REDACTED:PHONE_KE], my ID is [REDACTED:KENYAN_NID]"
  if result.found:
      logging.warning("PII detected and redacted: %s", result.entity_types)
"""
from __future__ import annotations

import re
import dataclasses
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Regex patterns — Kenya-specific
# ---------------------------------------------------------------------------

# Kenya National ID: 7–8 digits (some legacy 6-digit IDs exist).
# Preceded by optional label words to reduce false positives in plain numbers.
_NID_PATTERN = re.compile(
    r"(?i)(?:national\s+id|nid|id\s*no\.?|id\s*number|kitambulisho)[:\s#]*"
    r"([0-9]{6,8})"
    r"|(?<!\d)([0-9]{6,8})(?!\d)(?=\s*(?:national|id|nid|kitambulisho|\b))",
    re.UNICODE,
)

# KRA PIN: letter + 9 digits + letter  (e.g. A000000000X, P123456789Z)
_KRA_PIN_PATTERN = re.compile(
    r"\b[A-PR-Z][0-9]{9}[A-Z]\b",
    re.IGNORECASE,
)

# Kenyan phone numbers:
#   +2547XXXXXXXX  +2541XXXXXXXX  +254 7XX XXX XXX  07XXXXXXXX  01XXXXXXXX
# Spaces/hyphens are allowed between the country code and the subscriber number,
# and within the subscriber number (e.g. +254 712 345 678).
_PHONE_KE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:"
    r"\+?254[-\s]?[71](?:[-\s]?[0-9]){8}"   # +254 7xx … (spaces/hyphens OK)
    r"|0[71][0-9]{8}"                          # 07xx / 01xx (no spaces)
    r")"
    r"(?!\d)",
    re.UNICODE,
)

# MPESA / bank transaction IDs: uppercase alphanumeric, 8–12 chars,
# often preceded by label keywords.
_TXN_ID_PATTERN = re.compile(
    r"(?i)(?:transaction\s+id|txn\s*id|mpesa\s*code|receipt\s*no\.?)[:\s#]*"
    r"([A-Z0-9]{8,12})\b",
    re.UNICODE,
)

# Email addresses (simplified RFC-5321)
_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    re.UNICODE,
)

# IBAN (basic — letter+letter+digits, 15–34 chars)
_IBAN_PATTERN = re.compile(
    r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}\b",
    re.UNICODE,
)

# International passport number heuristic: 1–2 letters + 6–9 digits
_PASSPORT_PATTERN = re.compile(
    r"(?i)(?:passport\s*(?:no\.?|number)?)[:\s#]*([A-Z]{1,2}[0-9]{6,9})\b",
    re.UNICODE,
)

# Ordered list: (label, compiled_pattern)
_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("KRA_PIN",        _KRA_PIN_PATTERN),
    ("KENYAN_NID",     _NID_PATTERN),
    ("PHONE_KE",       _PHONE_KE_PATTERN),
    ("TRANSACTION_ID", _TXN_ID_PATTERN),
    ("EMAIL",          _EMAIL_PATTERN),
    ("IBAN",           _IBAN_PATTERN),
    ("PASSPORT",       _PASSPORT_PATTERN),
]

# ---------------------------------------------------------------------------
# Optional spaCy NER (degrades gracefully)
# ---------------------------------------------------------------------------

_NLP = None
_NLP_TRIED = False


def _get_nlp():
    global _NLP, _NLP_TRIED  # noqa: PLW0603
    if _NLP_TRIED:
        return _NLP
    _NLP_TRIED = True
    try:
        import spacy  # noqa: PLC0415
        # Prefer a small multilingual model; fall back to en_core_web_sm
        for model_name in ("xx_ent_wiki_sm", "en_core_web_sm"):
            try:
                _NLP = spacy.load(model_name)
                break
            except OSError:
                continue
    except ImportError:
        pass
    return _NLP


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class PiiFilterResult:
    redacted_text: str
    found: bool
    entity_types: List[str]      # de-duplicated list of redacted label types
    span_count: int               # total number of redacted spans


# ---------------------------------------------------------------------------
# Core redaction function
# ---------------------------------------------------------------------------

def redact(text: str, *, use_ner: bool = True) -> PiiFilterResult:
    """
    Redact all PII spans in *text*.

    Parameters
    ----------
    text:    Input string (may be multi-line).
    use_ner: If True (default) also apply spaCy NER for PERSON / ORG entities.
             Set to False in hot-path code where latency matters more.

    Returns
    -------
    PiiFilterResult with ``redacted_text``, ``found`` flag, ``entity_types``,
    and ``span_count``.
    """
    if not text:
        return PiiFilterResult(
            redacted_text=text, found=False, entity_types=[], span_count=0
        )

    # Collect all spans as (start, end, label) — process in offset order,
    # longest span wins on overlap.
    spans: List[Tuple[int, int, str]] = []

    # --- Regex patterns ---
    for label, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            # Some patterns have capturing groups; use the full match span
            start, end = m.start(), m.end()
            spans.append((start, end, label))

    # --- spaCy NER ---
    if use_ner:
        nlp = _get_nlp()
        if nlp is not None:
            doc = nlp(text[:10_000])  # cap to avoid OOM on very long strings
            for ent in doc.ents:
                if ent.label_ in ("PERSON", "PER"):
                    spans.append((ent.start_char, ent.end_char, "NER_PER"))
                elif ent.label_ in ("ORG",):
                    spans.append((ent.start_char, ent.end_char, "NER_ORG"))

    if not spans:
        return PiiFilterResult(
            redacted_text=text, found=False, entity_types=[], span_count=0
        )

    # Sort by start offset; on ties, prefer longer span
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))

    # Merge overlapping spans (greedy, longest-wins)
    merged: List[Tuple[int, int, str]] = []
    for start, end, label in spans:
        if merged and start < merged[-1][1]:
            # Overlap — extend if current is longer
            prev_start, prev_end, prev_label = merged[-1]
            if end > prev_end:
                merged[-1] = (prev_start, end, prev_label)
        else:
            merged.append((start, end, label))

    # Build redacted string
    result_parts: List[str] = []
    cursor = 0
    entity_types_seen: List[str] = []

    for start, end, label in merged:
        result_parts.append(text[cursor:start])
        result_parts.append(f"[REDACTED:{label}]")
        entity_types_seen.append(label)
        cursor = end

    result_parts.append(text[cursor:])
    redacted = "".join(result_parts)

    # De-duplicate entity types while preserving order
    seen: set = set()
    unique_types: List[str] = []
    for t in entity_types_seen:
        if t not in seen:
            seen.add(t)
            unique_types.append(t)

    return PiiFilterResult(
        redacted_text=redacted,
        found=True,
        entity_types=unique_types,
        span_count=len(merged),
    )


# ---------------------------------------------------------------------------
# Convenience: redact-or-raise
# ---------------------------------------------------------------------------

def assert_clean(text: str) -> str:
    """
    Run redact(); if any PII is found, raise ValueError.
    Useful in test assertions.
    """
    result = redact(text, use_ner=False)
    if result.found:
        raise ValueError(
            f"PII detected ({result.entity_types}) — value must be pre-redacted "
            "before reaching this call site."
        )
    return text
