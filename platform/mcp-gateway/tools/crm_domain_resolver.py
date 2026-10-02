"""
MCP Tool: crm.domain.resolver — Tier 2 (DNS-based domain resolution)

Resolves the primary internet domain for a TAM account (organisation) using
DNS queries (A / MX / SOA records) against the public resolver.

HC-4: tenant_id enforced on every operation.
HC-6: No raw NID or phone numbers are handled here; domain strings only.

Input schema:
  {
    "company_name": str,          # canonical name from TAM XLSX
    "candidate_domains": [str],   # optional list of candidate FQDNs to test
    "n_results": int              # max domains to return (default 3)
  }

Output:
  {
    "resolved_domain": str | null,   # best-match domain or null
    "candidates": [
      { "domain": str, "has_a": bool, "has_mx": bool, "confidence": float }
    ]
  }

Confidence scoring:
  - has_a  record: +0.4
  - has_mx record: +0.4
  - name similarity to company_name: up to +0.2 (difflib SequenceMatcher)
"""

from __future__ import annotations

import asyncio
import difflib
import logging
import socket
from typing import Any

from fastapi import HTTPException

from main import register_tool
from schemas import McpToolSpec

log = logging.getLogger("mcp.crm.domain.resolver")

SPEC = McpToolSpec(
    name="crm.domain.resolver",
    description=(
        "Resolve the internet domain for a TAM account using DNS (A + MX record checks). "
        "Tier 2: external DNS read; no PII involved. "
        "Used by the CRM Intelligence enrichment pipeline to fill missing domain fields."
    ),
    version="1.0.0",
    tenant_scope="single",
    read_write="read",
    side_effect_class="external_read",
    risk_tier=2,
    rate_limit=30,
    timeout_ms=15_000,
    audit_required=False,
)


# ── DNS helpers ───────────────────────────────────────────────────────────────

async def _has_a_record(domain: str) -> bool:
    """Return True if the domain resolves to at least one A/AAAA address."""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, socket.gethostbyname, domain)
        return True
    except (socket.gaierror, OSError):
        return False


async def _has_mx_record(domain: str) -> bool:
    """Return True if the domain has MX records (email deliverable)."""
    loop = asyncio.get_event_loop()

    def _check() -> bool:
        try:
            import dns.resolver  # dnspython
            answers = dns.resolver.resolve(domain, "MX", lifetime=5.0)
            return len(answers) > 0
        except Exception:
            return False

    return await loop.run_in_executor(None, _check)


def _name_similarity(domain: str, company_name: str) -> float:
    """
    Rough token overlap between domain stem and company name.
    Returns 0.0–1.0.
    """
    stem = domain.split(".")[0].lower().replace("-", " ")
    name = company_name.lower()
    return difflib.SequenceMatcher(None, stem, name).ratio()


async def _probe_domain(domain: str, company_name: str) -> dict:
    """Probe a single candidate domain; return its scored record."""
    has_a, has_mx = await asyncio.gather(
        _has_a_record(domain),
        _has_mx_record(domain),
    )
    sim        = _name_similarity(domain, company_name)
    confidence = round(
        (0.4 if has_a else 0.0) +
        (0.4 if has_mx else 0.0) +
        (0.2 * sim),
        3,
    )
    return {"domain": domain, "has_a": has_a, "has_mx": has_mx, "confidence": confidence}


# ── Domain candidate generation ───────────────────────────────────────────────

def _generate_candidates(company_name: str) -> list[str]:
    """
    Produce a short list of plausible domain candidates from a company name.
    Strips common suffixes (Ltd, Inc, Group, …) and common TLDs.
    """
    # Normalise
    name = company_name.lower()
    for suffix in (" limited", " ltd", " inc", " incorporated", " group",
                   " corporation", " corp", " llc", " plc", " co", " company"):
        name = name.removesuffix(suffix).strip()

    slug = name.replace(" & ", " ").replace("&", " ")
    slug = "".join(c if c.isalnum() else "-" for c in slug).strip("-")
    # Collapse consecutive hyphens
    while "--" in slug:
        slug = slug.replace("--", "-")

    tlds = ["com", "co.ke", "ke", "africa", "org"]
    return [f"{slug}.{tld}" for tld in tlds]


# ── Handler ───────────────────────────────────────────────────────────────────

async def handle(payload: dict[str, Any], *, tenant_id: str, db=None) -> dict:
    """
    HC-4: tenant_id required before any DNS resolution.
    """
    if not tenant_id:
        raise HTTPException(status_code=422, detail="HC-4: tenant_id is required")

    company_name = payload.get("company_name", "").strip()
    if not company_name:
        raise HTTPException(status_code=422, detail="company_name is required")

    n_results = min(int(payload.get("n_results", 3)), 10)

    # Use caller-provided candidates if given; otherwise generate
    provided = payload.get("candidate_domains") or []
    candidates = (
        [str(d).lower().strip() for d in provided]
        if provided
        else _generate_candidates(company_name)
    )[:10]  # hard cap to prevent abuse

    # Probe all candidates concurrently
    probed = await asyncio.gather(
        *[_probe_domain(d, company_name) for d in candidates],
        return_exceptions=True,
    )

    results = []
    for item in probed:
        if isinstance(item, Exception):
            log.debug("Probe error (non-fatal): %s", item)
            continue
        results.append(item)

    # Sort by confidence descending
    results.sort(key=lambda x: x["confidence"], reverse=True)
    top = results[:n_results]

    best = top[0]["domain"] if (top and top[0]["confidence"] > 0.4) else None

    log.info(
        "crm.domain.resolver: company=%r resolved=%s tenant=%s",
        company_name, best, tenant_id,
    )
    return {"resolved_domain": best, "candidates": top}


register_tool(SPEC, handle)
