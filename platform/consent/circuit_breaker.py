"""
Consent Service circuit-breaker — shared across Python callers.

Pattern: half-open exponential back-off with a fail-closed default.

States:
  CLOSED   — normal operation; failures are counted.
  OPEN     — fast-fail for OPEN_TIMEOUT seconds after FAILURE_THRESHOLD failures.
  HALF_OPEN— single probe allowed; success → CLOSED, failure → OPEN (back-off doubles).

Usage:
    from platform.consent.circuit_breaker import consent_allowed

    if not await consent_allowed(subject_id_hash, channel, purpose, tenant_id):
        # deny the request
        ...

HC compliance:
  Default-deny on OPEN state (fail-closed) as required by STEP-P2-02 / DPA 2019 §25.
  The breaker state is module-level (per-process). For multi-replica deployments
  each replica maintains its own breaker state, which is acceptable because the
  default-deny guarantees correct safety posture regardless of state divergence.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from enum import Enum

import httpx

log = logging.getLogger("consent-breaker")

CONSENT_SERVICE_URL: str = os.getenv(
    "CONSENT_SERVICE_URL",
    "http://consent-service.i3-consent.svc.cluster.local:8000",
)

# ── Breaker configuration (overridable via env) ────────────────────────────────
FAILURE_THRESHOLD: int   = int(os.getenv("CONSENT_CB_FAILURE_THRESHOLD", "5"))
OPEN_TIMEOUT: float      = float(os.getenv("CONSENT_CB_OPEN_TIMEOUT",    "30"))
REQUEST_TIMEOUT: float   = float(os.getenv("CONSENT_CB_REQUEST_TIMEOUT",  "5"))
MAX_OPEN_TIMEOUT: float  = float(os.getenv("CONSENT_CB_MAX_OPEN_TIMEOUT", "300"))


class _State(str, Enum):
    CLOSED    = "CLOSED"
    OPEN      = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class _ConsentBreaker:
    """Thread-safe async circuit-breaker for the consent-service HTTP endpoint."""

    def __init__(self) -> None:
        self._state: _State       = _State.CLOSED
        self._failures: int       = 0
        self._opened_at: float    = 0.0
        self._current_timeout: float = OPEN_TIMEOUT
        self._lock: asyncio.Lock  = asyncio.Lock()

    # ── State transitions ──────────────────────────────────────────────────────

    def _trip(self) -> None:
        self._state         = _State.OPEN
        self._opened_at     = time.monotonic()
        log.warning(
            "consent-breaker OPEN (failures=%d, retry_in=%.0fs)",
            self._failures, self._current_timeout,
        )

    def _reset(self) -> None:
        self._state            = _State.CLOSED
        self._failures         = 0
        self._current_timeout  = OPEN_TIMEOUT
        log.info("consent-breaker CLOSED (recovered)")

    def _is_probe_allowed(self) -> bool:
        """Return True if the open timeout has elapsed (allow a half-open probe)."""
        return (time.monotonic() - self._opened_at) >= self._current_timeout

    # ── Public interface ───────────────────────────────────────────────────────

    async def check(
        self,
        subject_id_hash: str,
        channel: str,
        purpose: str,
        tenant_id: str,
    ) -> bool:
        """
        Return True when the consent-service confirms allowed=true.
        Return False (fail-closed) when:
          - The circuit is OPEN and the back-off timeout has not elapsed.
          - The consent-service returns non-200 or a network error occurs.
          - The subject has no consent record (default-deny).
        """
        async with self._lock:
            if self._state == _State.OPEN:
                if not self._is_probe_allowed():
                    log.debug("consent-breaker fast-fail (OPEN)")
                    return False
                # Transition to HALF_OPEN to allow a single probe
                self._state = _State.HALF_OPEN
                log.info("consent-breaker HALF_OPEN (probing)")

        try:
            result = await self._call(subject_id_hash, channel, purpose, tenant_id)
        except Exception as exc:
            await self._on_failure(exc)
            return False

        await self._on_success()
        return result

    async def _call(
        self,
        subject_id_hash: str,
        channel: str,
        purpose: str,
        tenant_id: str,
    ) -> bool:
        url = f"{CONSENT_SERVICE_URL}/consent/{subject_id_hash}"
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(
                url,
                params={"channel": channel, "purpose": purpose, "tenant_id": tenant_id},
            )
        if resp.status_code != 200:
            return False
        return bool(resp.json().get("allowed", False))

    async def _on_success(self) -> None:
        async with self._lock:
            if self._state in (_State.HALF_OPEN, _State.CLOSED):
                self._reset()

    async def _on_failure(self, exc: Exception) -> None:
        async with self._lock:
            self._failures += 1
            log.warning(
                "consent-service call failed (failures=%d/%d): %s",
                self._failures, FAILURE_THRESHOLD, exc,
            )
            if self._state == _State.HALF_OPEN:
                # Double the open timeout (capped at MAX_OPEN_TIMEOUT)
                self._current_timeout = min(
                    self._current_timeout * 2, MAX_OPEN_TIMEOUT
                )
                self._trip()
            elif self._failures >= FAILURE_THRESHOLD:
                self._trip()

    @property
    def state(self) -> str:
        return self._state.value


# ── Module-level singleton ─────────────────────────────────────────────────────
_breaker = _ConsentBreaker()


async def consent_allowed(
    subject_id_hash: str,
    channel: str,
    purpose: str,
    tenant_id: str,
) -> bool:
    """
    Primary API for all callers.  Returns True only when consent is confirmed.
    Fail-closed: returns False on circuit open, timeout, or service error.
    """
    return await _breaker.check(subject_id_hash, channel, purpose, tenant_id)


def breaker_state() -> str:
    """Return current breaker state string for health endpoints."""
    return _breaker.state
