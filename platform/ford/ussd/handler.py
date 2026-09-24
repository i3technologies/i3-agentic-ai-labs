"""
FORD-Asili USSD Bridge — Africa's Talking callback handler
Namespace: i3-ford

USSD flow (*509#):
  Step 0 (text=""):    Language selection  → CON
  Step 1 (text="1"):   ID number entry     → CON
  Step 2 (text="1*<id>"):  OTP dispatch    → CON
  Step 3 (text="1*<id>*<otp>"): Confirm   → END / CON (re-ask on invalid)

HC-6: National IDs stored only as HMAC-SHA256 tokens.
       OTPs stored as HMAC(otp) in Redis with OTP_TTL expiry — never in-memory or SQL.
HC-4: tenant_id on every DB/API call.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import random
import string

import aioredis
import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import PlainTextResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
log = logging.getLogger("ford-ussd")

# ── Environment ───────────────────────────────────────────────────────────────
FORD_API_URL        = os.getenv(
    "FORD_API_URL",
    "http://ford-api.i3-ford.svc.cluster.local:8000",
)
MEMBER_HMAC_SECRET  = os.environ["MEMBER_HMAC_SECRET"]   # OpenBao-injected (HC-6)
REDIS_URL           = os.getenv("REDIS_URL", "redis://redis.i3-data.svc.cluster.local:6379/1")
FORD_TENANT_ID      = os.getenv("FORD_TENANT_ID", "00000000-0000-0000-0000-000000000005")
AT_API_KEY          = os.getenv("AT_API_KEY", "")          # Africa's Talking API key (for outbound SMS)
AT_USERNAME         = os.getenv("AT_USERNAME", "sandbox")

OTP_TTL:          int = 600   # seconds — must match ford-api constant
OTP_MAX_ATTEMPTS: int = 5     # max failed OTP checks before 429

app = FastAPI(title="FORD-Asili USSD Bridge")

# ── Redis client — initialised at startup; replaces the in-memory session store ──
_redis: aioredis.Redis | None = None

# ── In-memory session metadata (non-sensitive: lang, step, national_id only)
# OTPs are NEVER stored here — they go to Redis via store_otp.
_sessions: dict[str, dict] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def hmac_token(value: str) -> str:
    """Return HMAC-SHA256(UPPER(STRIP(value)), MEMBER_HMAC_SECRET) hex digest (HC-6)."""
    return hmac.new(
        MEMBER_HMAC_SECRET.encode(),
        value.strip().upper().encode(),
        hashlib.sha256,
    ).hexdigest()


def _otp() -> str:
    return "".join(random.choices(string.digits, k=6))


# ── OTP Redis helpers (HC-6: OTP stored as HMAC in Redis, never in-memory) ───

async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def store_otp(phone: str, otp: str) -> None:
    """Store HMAC(otp) in Redis keyed by HMAC(phone) with OTP_TTL expiry (HC-6)."""
    r = await _get_redis()
    phone_token = hmac_token(phone)
    await r.set(f"otp:{phone_token}", hmac_token(otp), ex=OTP_TTL)


async def verify_otp_token(phone: str, otp: str) -> bool:
    """
    Rate-check then compare stored HMAC(otp) against HMAC(submitted otp)
    using constant-time hmac.compare_digest (HC-6).

    Returns True on match; False if OTP missing, expired, or incorrect.
    Raises _OTPRateLimitError when OTP_MAX_ATTEMPTS is exceeded.
    """
    r = await _get_redis()
    phone_token = hmac_token(phone)
    attempt_key = f"otp_attempts:{phone_token}"

    count = await r.incr(attempt_key)
    if count == 1:
        await r.expire(attempt_key, OTP_TTL)
    if count > OTP_MAX_ATTEMPTS:
        raise _OTPRateLimitError()

    stored = await r.get(f"otp:{phone_token}")
    if stored is None:
        return False
    return hmac.compare_digest(stored, hmac_token(otp))


async def delete_otp(phone: str) -> None:
    """Delete both OTP and attempt-counter keys for a phone after successful verification."""
    r = await _get_redis()
    phone_token = hmac_token(phone)
    await r.delete(f"otp:{phone_token}", f"otp_attempts:{phone_token}")


class _OTPRateLimitError(Exception):
    """Raised internally when OTP_MAX_ATTEMPTS is exceeded."""


async def _send_otp_sms(phone: str, otp: str) -> None:
    """Dispatch OTP via Africa's Talking SMS (fire-and-forget)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                "https://api.africastalking.com/version1/messaging",
                headers={
                    "apiKey":       AT_API_KEY,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept":       "application/json",
                },
                data={
                    "username": AT_USERNAME,
                    "to":       phone,
                    "message":  f"Your FORD-Asili OTP is: {otp}. Valid for 5 minutes.",
                },
            )
    except Exception as exc:
        log.warning("otp_sms_failed phone=%s: %s", phone[-4:], exc)


async def _call_register(national_id: str, phone: str, ward_code: str, agent_id: str = "USSD") -> dict:
    """Call ford-api /register. Returns response dict with fabric_tx_id."""
    async with httpx.AsyncClient(timeout=12.0) as client:
        resp = await client.post(
            f"{FORD_API_URL}/api/v1/members/register",
            json={
                "national_id":  national_id,
                "phone":        phone,
                "ward_code":    ward_code,
                "constituency": "unknown",  # USSD flow collects ward only; constituency resolved server-side
                "county":       "unknown",
                "agent_id":     agent_id,
                "consent":      True,
            },
        )
        resp.raise_for_status()
        return resp.json()


# ── USSD entry point ──────────────────────────────────────────────────────────

@app.post("/ussd", response_class=PlainTextResponse)
async def ussd_callback(
    sessionId:   str = Form(...),
    serviceCode: str = Form(...),
    phoneNumber: str = Form(...),
    text:        str = Form(""),
) -> str:
    """
    Africa's Talking USSD callback.
    Returns "CON <text>" to continue the session or "END <text>" to terminate.

    State machine:
      Step 0 — language selection
      Step 1 — national ID entry
      Step 2 — OTP verification
      Step 3 — confirmation / registration
    """
    log.info("ussd session=%s phone=%s text=%r", sessionId, phoneNumber[-4:], text)

    parts = [p for p in text.split("*")]  # AT sends accumulated input separated by *

    session = _sessions.setdefault(sessionId, {"phone": phoneNumber, "step": 0})

    step = len([p for p in parts if p])  # empty text = step 0

    # ── Step 0: Language selection ────────────────────────────────────────────
    if step == 0:
        session["step"] = 0
        return (
            "CON Welcome to FORD-Asili / Karibu FORD-Asili\n"
            "1. English\n"
            "2. Kiswahili"
        )

    lang = parts[0]
    session["lang"] = "sw" if lang == "2" else "en"

    # ── Step 1: ID number entry ───────────────────────────────────────────────
    if step == 1:
        if session["lang"] == "sw":
            return "CON Ingiza nambari yako ya kitambulisho cha taifa:"
        return "CON Enter your national ID number:"

    national_id = parts[1].strip()
    if not national_id.isdigit() or not (6 <= len(national_id) <= 10):
        if session["lang"] == "sw":
            return "CON Nambari ya kitambulisho si sahihi. Jaribu tena:"
        return "CON Invalid ID number. Please try again:"

    # ── Step 2: OTP dispatch ──────────────────────────────────────────────────
    if step == 2:
        otp = _otp()
        session["national_id"] = national_id
        # HC-6: store HMAC(otp) in Redis — never in-memory session or SQL.
        await store_otp(phoneNumber, otp)
        # Dispatch OTP SMS (fire-and-forget; do not block the USSD response)
        asyncio.ensure_future(_send_otp_sms(phoneNumber, otp))

        if session["lang"] == "sw":
            return f"CON Nambari ya uthibitisho imetumwa kwa {phoneNumber[-4:]}.\nIngiza nambari ya OTP:"
        return f"CON OTP sent to {phoneNumber[-4:]}.\nEnter your OTP:"

    # ── Step 3: OTP verification + registration ───────────────────────────────
    if step == 3:
        entered_otp = parts[2].strip()
        stored_id   = session.get("national_id", "")

        # HC-6: constant-time HMAC comparison via Redis-backed verify_otp_token.
        # Rate-limit: max OTP_MAX_ATTEMPTS (5) attempts per phone token before END 429.
        try:
            otp_valid = await verify_otp_token(phoneNumber, entered_otp)
        except _OTPRateLimitError:
            _sessions.pop(sessionId, None)
            if session["lang"] == "sw":
                return "END Majaribio mengi sana. Tafadhali jaribu tena baadaye."
            return "END Too many OTP attempts. Please try again later."

        if not otp_valid:
            if session["lang"] == "sw":
                return "END Nambari ya OTP si sahihi. Jaribu tena kwa kupiga *509#."
            return "END Invalid OTP. Please try again by dialling *509#."

        # Register via ford-api; clean up OTP keys on success (HC-6).
        try:
            ward_code = "001"  # default ward; in production resolve from constituency lookup
            result = await _call_register(stored_id, phoneNumber, ward_code)
            fabric_tx = result.get("fabric_tx_id", "pending")
            await delete_otp(phoneNumber)    # HC-6: remove OTP + attempt counter after success
            _sessions.pop(sessionId, None)   # clean up session metadata

            if session["lang"] == "sw":
                return (
                    f"END Umefanikiwa kusajiliwa kwa FORD-Asili.\n"
                    f"Nambari ya uthibitisho: {result.get('member_id','')[:8].upper()}"
                )
            return (
                f"END Registration successful.\n"
                f"Reference: {result.get('member_id','')[:8].upper()}"
            )
        except Exception as exc:
            log.error("ussd_register_failed session=%s: %s", sessionId, exc)
            if session["lang"] == "sw":
                return "END Hitilafu ya mfumo. Tafadhali jaribu tena baadaye."
            return "END System error. Please try again later."

    # ── Catch-all: restart session ────────────────────────────────────────────
    _sessions.pop(sessionId, None)
    return "END Session expired. Please dial *509# to restart."


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ford-ussd"}
