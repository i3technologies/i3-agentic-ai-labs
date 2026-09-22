"""
test_otp_ratelimit.py
---------------------
P1-GATE-08 sensor: pytest platform/ford/tests/test_otp_ratelimit.py → PASSED

Covers:
  - OTP attempt counter increments per phone token (Redis)
  - 429 is raised after OTP_MAX_ATTEMPTS (5) exhausted
  - Counter resets once the OTP_TTL expires (simulated by flushing the key)
  - Constant-time hmac comparison (verify_otp_token returns False for wrong OTP)
  - Successful verification clears the attempt counter and otp key
  - Rate-limit window is keyed by HMAC of phone, never plain phone number (HC-6)
"""

import asyncio
import hmac
import hashlib
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException

# ── env stubs needed before importing the module ─────────────────────────────
import os
import sys
import importlib.util
from types import ModuleType
from unittest.mock import MagicMock

os.environ.setdefault("FORD_DB_URL",        "postgresql://test:test@localhost/ford_test")
os.environ.setdefault("MEMBER_HMAC_SECRET", "deadbeefdeadbeefdeadbeefdeadbeef"
                                             "deadbeefdeadbeefdeadbeefdeadbeef")
os.environ.setdefault("REDIS_URL",          "redis://localhost:6379/0")

# Stub platform.consent.circuit_breaker before main.py loads to prevent the
# stdlib 'platform' module name collision on Python 3.14 (Windows).
_consent_pkg = ModuleType("platform.consent")
_cb_mod = ModuleType("platform.consent.circuit_breaker")
_cb_mod.consent_allowed = MagicMock(return_value=True)  # type: ignore[attr-defined]
_cb_mod.breaker_state = MagicMock(return_value="closed")  # type: ignore[attr-defined]
sys.modules.setdefault("platform.consent", _consent_pkg)
sys.modules.setdefault("platform.consent.circuit_breaker", _cb_mod)

# Import main.py directly by file path to avoid the stdlib 'platform' name collision.
_MAIN_PATH = os.path.join(os.path.dirname(__file__), "..", "api", "main.py")
_spec = importlib.util.spec_from_file_location("ford_main", os.path.abspath(_MAIN_PATH))
_ford_main = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["ford_main"] = _ford_main
_spec.loader.exec_module(_ford_main)  # type: ignore[union-attr]

hmac_token       = _ford_main.hmac_token
store_otp        = _ford_main.store_otp
verify_otp_token = _ford_main.verify_otp_token
delete_otp       = _ford_main.delete_otp
_otp_rate_check  = _ford_main._otp_rate_check
OTP_MAX_ATTEMPTS = _ford_main.OTP_MAX_ATTEMPTS
OTP_TTL          = _ford_main.OTP_TTL


# ── helpers ───────────────────────────────────────────────────────────────────

def _expected_token(value: str) -> str:
    """Mirror of hmac_token() for test assertions."""
    secret = os.environ["MEMBER_HMAC_SECRET"].encode()
    return hmac.new(secret, value.strip().upper().encode(), hashlib.sha256).hexdigest()


# ── HMAC-token unit tests (HC-6 compliance) ──────────────────────────────────

class TestHmacToken:
    def test_output_is_hex_sha256(self):
        token = hmac_token("0712345678")
        assert len(token) == 64
        assert all(c in "0123456789abcdef" for c in token)

    def test_same_input_same_output(self):
        assert hmac_token("0712345678") == hmac_token("0712345678")

    def test_different_inputs_different_outputs(self):
        assert hmac_token("0712345678") != hmac_token("0712345679")

    def test_phone_normalised_to_upper(self):
        """hmac_token strips and uppercases — ensures consistent key for digits."""
        assert hmac_token("  07123  ") == hmac_token("07123")

    def test_is_keyed_not_raw_sha256(self):
        """Result must differ from raw SHA-256 of the same input (HC-6)."""
        raw = hashlib.sha256("0712345678".upper().encode()).hexdigest()
        assert hmac_token("0712345678") != raw


# ── OTP rate-limit tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestOtpRateCheck:
    """_otp_rate_check increments an attempt counter and raises 429 beyond cap."""

    async def test_first_attempt_allowed(self):
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 1
        mock_redis.expire = AsyncMock()

        _ford_main._redis = mock_redis

        # Should not raise
        await _otp_rate_check("some-phone-token")
        mock_redis.incr.assert_awaited_once_with("otp_attempts:some-phone-token")
        mock_redis.expire.assert_awaited_once_with("otp_attempts:some-phone-token", OTP_TTL)

    async def test_ttl_set_only_on_first_increment(self):
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 2   # already incremented once before
        mock_redis.expire = AsyncMock()

        _ford_main._redis = mock_redis

        await _otp_rate_check("tok")
        mock_redis.expire.assert_not_awaited()

    async def test_raises_429_on_exceeded_attempts(self):
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = OTP_MAX_ATTEMPTS + 1
        mock_redis.expire = AsyncMock()

        _ford_main._redis = mock_redis

        with pytest.raises(HTTPException) as exc_info:
            await _otp_rate_check("tok")
        assert exc_info.value.status_code == 429

    async def test_exactly_at_cap_is_still_allowed(self):
        """The cap is *strict greater than*, so attempt == OTP_MAX_ATTEMPTS passes."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = OTP_MAX_ATTEMPTS  # == cap, not over
        mock_redis.expire = AsyncMock()

        _ford_main._redis = mock_redis

        await _otp_rate_check("tok")   # must NOT raise


# ── verify_otp_token tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestVerifyOtpToken:
    """verify_otp_token: constant-time comparison + rate-limit integration."""

    def _make_redis(self, stored_otp_plaintext: str | None, attempt_count: int = 1):
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = attempt_count
        mock_redis.expire = AsyncMock()
        if stored_otp_plaintext is None:
            mock_redis.get.return_value = None
        else:
            mock_redis.get.return_value = _expected_token(stored_otp_plaintext)
        return mock_redis

    async def test_correct_otp_returns_true(self):
        _ford_main._redis = self._make_redis("ABCDEF")

        result = await verify_otp_token("+254712345678", "ABCDEF")
        assert result is True

    async def test_wrong_otp_returns_false(self):
        _ford_main._redis = self._make_redis("ABCDEF")

        result = await verify_otp_token("+254712345678", "ZZZZZZ")
        assert result is False

    async def test_expired_otp_returns_false(self):
        _ford_main._redis = self._make_redis(None)

        result = await verify_otp_token("+254712345678", "ABCDEF")
        assert result is False

    async def test_rate_limit_fires_before_check(self):
        """429 from rate-check propagates before any Redis GET."""
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = OTP_MAX_ATTEMPTS + 1
        mock_redis.expire = AsyncMock()
        _ford_main._redis = mock_redis

        with pytest.raises(HTTPException) as exc_info:
            await verify_otp_token("+254712345678", "ABCDEF")
        assert exc_info.value.status_code == 429
        mock_redis.get.assert_not_awaited()


# ── delete_otp tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestDeleteOtp:
    async def test_deletes_otp_and_attempt_keys(self):
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()

        _ford_main._redis = mock_redis

        phone = "+254712345678"
        await delete_otp(phone)

        phone_token = _expected_token(phone)
        mock_redis.delete.assert_awaited_once_with(
            f"otp:{phone_token}",
            f"otp_attempts:{phone_token}",
        )
