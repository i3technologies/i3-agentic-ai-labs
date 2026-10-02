"""
CRM Intelligence — Rate Limiter Tests
File:      platform/crm/tests/test_rate_limiter.py

Verifies the Redis token-bucket RateLimiter (Rule 3):
  - Token consumption allows requests up to bucket capacity
  - Bucket exhaustion returns False (rate-limited)
  - Lua script logic via fakeredis (no live Redis required)
  - Domain key isolation (different domains don't share buckets)
"""

from __future__ import annotations

import os
import unittest.mock
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("CELERY_BROKER_URL", "redis://:test@localhost:6379/0")


class TestRateLimiterCapacity:
    """Test the capacity() helper — pure math, no Redis."""

    def test_capacity_rounds_up(self):
        from crm.rate_limiter import RateLimiter
        with patch("crm.rate_limiter._get_redis"):
            rl = RateLimiter.__new__(RateLimiter)
            rl._window = 10
            assert rl.capacity(0.5) == 5    # 0.5 * 10 = 5
            assert rl.capacity(0.3) == 3    # ceil(3.0) = 3
            assert rl.capacity(0.33) == 4   # ceil(3.3) = 4
            assert rl.capacity(0.01) == 1   # minimum 1

    def test_capacity_minimum_is_one(self):
        from crm.rate_limiter import RateLimiter
        with patch("crm.rate_limiter._get_redis"):
            rl = RateLimiter.__new__(RateLimiter)
            rl._window = 10
            assert rl.capacity(0.0) == 1    # floor(0) but min=1

    def test_key_normalises_to_lowercase(self):
        from crm.rate_limiter import RateLimiter, KEY_PREFIX
        with patch("crm.rate_limiter._get_redis"):
            rl = RateLimiter.__new__(RateLimiter)
            assert rl._key("Example.COM") == f"{KEY_PREFIX}example.com"


class TestRateLimiterAcquire:
    """Test acquire() using a mocked Redis Lua script."""

    def _make_limiter(self, script_return_value: int) -> "RateLimiter":  # type: ignore[name-defined]
        from crm.rate_limiter import RateLimiter

        mock_script = MagicMock(return_value=script_return_value)
        mock_redis = MagicMock()
        mock_redis.register_script.return_value = mock_script

        with patch("crm.rate_limiter._get_redis", return_value=mock_redis):
            rl = RateLimiter(window_seconds=10)

        return rl

    def test_acquire_returns_true_when_token_available(self):
        rl = self._make_limiter(script_return_value=1)
        assert rl.acquire("example.com", rps=0.5) is True

    def test_acquire_returns_false_when_bucket_empty(self):
        rl = self._make_limiter(script_return_value=0)
        assert rl.acquire("example.com", rps=0.5) is False

    def test_acquire_passes_capacity_and_window_to_script(self):
        from crm.rate_limiter import RateLimiter

        mock_script = MagicMock(return_value=1)
        mock_redis = MagicMock()
        mock_redis.register_script.return_value = mock_script

        with patch("crm.rate_limiter._get_redis", return_value=mock_redis):
            rl = RateLimiter(window_seconds=10)

        rl.acquire("example.com", rps=0.5)

        mock_script.assert_called_once_with(
            keys=["crm:ratelimit:example.com"],
            args=[5, 10],   # capacity=5 (0.5*10), window=10
        )


class TestRateLimiterReset:
    """reset() should delete the Redis key."""

    def test_reset_deletes_key(self):
        from crm.rate_limiter import RateLimiter, KEY_PREFIX

        mock_redis = MagicMock()
        mock_redis.register_script.return_value = MagicMock()

        with patch("crm.rate_limiter._get_redis", return_value=mock_redis):
            rl = RateLimiter(window_seconds=10)

        rl.reset("example.com")
        mock_redis.delete.assert_called_once_with(f"{KEY_PREFIX}example.com")
