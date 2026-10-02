"""
CRM Intelligence — Redis Token-Bucket Rate Limiter
File:      platform/crm/rate_limiter.py
Namespace: crm-intelligence

Implements a sliding-window token-bucket algorithm using a Lua script
executed atomically on Redis.  This enforces Rule 3 of the crawl engine:
each domain has a configurable max_rps (requests per second) ceiling.

Algorithm:
  - Bucket capacity = ceil(max_rps * WINDOW_SECONDS)
  - On each acquire():
      1. MULTI/EXEC-equivalent via Lua: fetch current token count
      2. If tokens > 0: decrement and return True (allowed)
      3. If tokens == 0: return False (rate limited)
      4. Bucket refills via EXPIRE-based TTL (auto-reset per window)

HC-5: This limiter is called by crawl_domain BEFORE any HTTP request.
HC-7: Redis URL is injected from ExternalSecrets (OpenBao i3/crm/redis).

Thread/process safety: the Lua script executes atomically — safe for
concurrent Celery worker processes sharing the same Redis instance.
"""

from __future__ import annotations

import math
import os
from functools import lru_cache
from typing import Final

import redis

# ── Constants ──────────────────────────────────────────────────────────────
WINDOW_SECONDS: Final[int] = 10       # refill window (seconds)
KEY_PREFIX: Final[str] = "crm:ratelimit:"

# ── Lua token-bucket script ────────────────────────────────────────────────
# KEYS[1]  = Redis key (crm:ratelimit:<domain>)
# ARGV[1]  = bucket capacity (integer tokens per window)
# ARGV[2]  = window TTL in seconds
#
# Returns 1 if a token was consumed (request allowed), 0 if bucket empty.
_TOKEN_BUCKET_LUA = """
local key      = KEYS[1]
local capacity = tonumber(ARGV[1])
local ttl      = tonumber(ARGV[2])

local current = redis.call("GET", key)

if current == false then
    -- First request in this window: initialise bucket at capacity-1
    redis.call("SET", key, capacity - 1, "EX", ttl)
    return 1
end

local tokens = tonumber(current)
if tokens > 0 then
    redis.call("DECR", key)
    return 1
else
    return 0
end
"""


@lru_cache(maxsize=1)
def _get_redis() -> redis.Redis:
    """
    Return a shared Redis client.  Connection URL is injected from
    the CELERY_BROKER_URL env var (same Redis instance as the broker).
    Fails fast on startup if the variable is not set.
    """
    url = os.environ.get("CELERY_BROKER_URL")
    if not url:
        raise RuntimeError(
            "CELERY_BROKER_URL is not set — cannot initialise rate limiter. "
            "Inject from ExternalSecrets (OpenBao i3/crm/redis)."
        )
    return redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)


class RateLimiter:
    """
    Domain-scoped token-bucket rate limiter backed by Redis.

    Usage:
        limiter = RateLimiter()
        allowed = limiter.acquire(domain="example.com", rps=0.5)
        if not allowed:
            raise task.retry(countdown=2)
    """

    def __init__(self, window_seconds: int = WINDOW_SECONDS) -> None:
        self._window = window_seconds
        self._client = _get_redis()
        self._script = self._client.register_script(_TOKEN_BUCKET_LUA)

    def _key(self, domain: str) -> str:
        # Normalise domain to lowercase to prevent key duplication
        return f"{KEY_PREFIX}{domain.lower()}"

    def capacity(self, rps: float) -> int:
        """Bucket capacity = ceil(rps * window_seconds), minimum 1."""
        return max(1, math.ceil(rps * self._window))

    def acquire(self, domain: str, rps: float = 0.5) -> bool:
        """
        Attempt to consume one token for ``domain``.

        Returns True if the request is allowed, False if rate-limited.
        Raises redis.RedisError on connectivity failure (caller should retry).
        """
        cap = self.capacity(rps)
        result = self._script(
            keys=[self._key(domain)],
            args=[cap, self._window],
        )
        return bool(result)

    def remaining(self, domain: str) -> int:
        """Return the number of tokens remaining in the current window (for logging)."""
        raw = self._client.get(self._key(domain))
        return int(raw) if raw is not None else -1

    def reset(self, domain: str) -> None:
        """
        Manually reset the rate-limit bucket for a domain.
        Used in tests and by operator override.
        """
        self._client.delete(self._key(domain))
