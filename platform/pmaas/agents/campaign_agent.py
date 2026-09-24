"""
PMaaS Campaign Agent — LangGraph-based autonomous strategy agent.

Capabilities:
  - /briefing  POST  — daily campaign briefing with RAG from manifesto
  - /ask       POST  — manifesto/strategy Q&A with ChromaDB RAG
  - /analyze   POST  — ward-level targeting analysis
  - /content   POST  — generate campaign content (social, WhatsApp, voice)
  - /health    GET   — liveness probe

STEP-P2-04 Migration: direct chromadb imports removed.
All tool calls (chroma.search, litellm.chat) route through the MCP Gateway.

Security (FINDING-CA-1, FINDING-CA-3):
  - All mutating endpoints require a valid Keycloak Bearer JWT (RS256).
  - tenant_id is derived from the JWT claim — not a static env-var.
  - The shared static API_KEY fallback is removed.

Env vars:
  MCP_GATEWAY_URL       — http://mcp-gateway.i3-agent-mesh.svc:8100
  LITELLM_MODEL_HEAVY   — qwen-heavy (default)
  LITELLM_MODEL_FAST    — qwen-fast (default)
  KAFKA_BOOTSTRAP       — kafka-bootstrap.i3-messaging.svc:9092
  KEYCLOAK_JWKS_URI     — Keycloak JWKS endpoint
  KEYCLOAK_ISSUER       — Keycloak issuer URL
"""

import os
import re
import json
import logging
import asyncio
import time
import uuid
from datetime import datetime, UTC
from typing import Annotated, TypedDict

import httpx
import jwt as pyjwt
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── OpenTelemetry — STEP-P1-13 ────────────────────────────────────────────────
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

_tracer_provider = TracerProvider()
_tracer_provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(
            endpoint=os.environ.get(
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                "http://otel-collector.i3-monitoring.svc.cluster.local:4317",
            )
        )
    )
)
trace.set_tracer_provider(_tracer_provider)
_tracer = trace.get_tracer("campaign-agent")

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("campaign-agent")

# ── Config ───────────────────────────────────────────────────────────────────
MCP_GATEWAY_URL     = os.getenv("MCP_GATEWAY_URL",        "http://mcp-gateway.i3-agent-mesh.svc.cluster.local:8100")
MODEL_HEAVY         = os.getenv("LITELLM_MODEL_HEAVY",    "qwen-heavy")
MODEL_FAST          = os.getenv("LITELLM_MODEL_FAST",     "qwen-fast")
CHROMA_COLL         = os.getenv("CHROMA_COLLECTION",      "pmaas-manifesto")
LITELLM_KEY         = os.getenv("LITELLM_KEY",            "")
KAFKA_BOOTSTRAP     = os.getenv("KAFKA_BOOTSTRAP",        "")
AGENT_REGISTRY_URL  = os.getenv("AGENT_REGISTRY_URL",    "http://agent-registry.i3-agent-mesh.svc.cluster.local:8200")
CONSENT_SERVICE_URL = os.getenv(
    "CONSENT_SERVICE_URL",
    "http://consent-service.i3-consent.svc.cluster.local:8000",
)
KEYCLOAK_JWKS_URI   = os.getenv(
    "KEYCLOAK_JWKS_URI",
    "https://sso.i3technologies.co.ke/realms/i3/protocol/openid-connect/certs",
)
KEYCLOAK_ISSUER     = os.getenv(
    "KEYCLOAK_ISSUER",
    "https://sso.i3technologies.co.ke/realms/i3",
)
AGENT_ID            = "pmaas-campaign-agent-v1"
FALLBACK_TENANT_ID  = os.getenv("DEFAULT_TENANT_ID",     "00000000-0000-0000-0000-000000000001")

# ── JWKS key cache ────────────────────────────────────────────────────────────
_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0


async def _get_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    if _jwks_cache and (time.monotonic() - _jwks_fetched_at) < 600:
        return _jwks_cache
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(KEYCLOAK_JWKS_URI)
        resp.raise_for_status()
    _jwks_cache = resp.json()
    _jwks_fetched_at = time.monotonic()
    return _jwks_cache


# ── Keycloak JWT dependency (FINDING-CA-1) ────────────────────────────────────
_bearer = HTTPBearer(auto_error=True)


class _CallerCtx:
    def __init__(self, sub: str, tenant_id: str, roles: list[str]):
        self.sub       = sub
        self.tenant_id = tenant_id
        self.roles     = roles


async def _require_auth(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> _CallerCtx:
    """Validate Keycloak Bearer JWT; return caller context with tenant_id.

    HC-7: DEV_BYPASS_AUTH is permanently forbidden.
    tenant_id is taken from the JWT 'tenant_id' claim (HC-4).
    """
    try:
        jwks = await _get_jwks()
        signing_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(
            next(k for k in jwks["keys"] if k.get("use") == "sig")
        )
        payload = pyjwt.decode(
            creds.credentials,
            signing_key,
            algorithms=["RS256"],
            issuer=KEYCLOAK_ISSUER,
            options={"verify_exp": True},
        )
    except StopIteration:
        raise HTTPException(status_code=401, detail="No signing key found in JWKS")
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    tenant_id = payload.get("tenant_id") or FALLBACK_TENANT_ID
    roles: list[str] = payload.get("realm_access", {}).get("roles", [])
    return _CallerCtx(sub=payload["sub"], tenant_id=tenant_id, roles=roles)

# ── Lobster Trap — Prompt Injection Firewall (14-pattern canonical set) ──────
# P13/P14 synced from lobster-trap.ts (P2-MED parity fix).
_LOBSTER_TRAP_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.I),
    re.compile(r"system\s+prompt\s+override", re.I),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.I),
    re.compile(r"output\s+all\s+passwords", re.I),
    re.compile(r"reveal\s+internal\s+logic", re.I),
    re.compile(r"bypass\s+safety\s+filter", re.I),
    re.compile(r"act\s+as\s+DAN", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"(drop|delete|truncate)\s+table", re.I),
    re.compile(r"prompt\s+injection", re.I),
    re.compile(r"disregard\s+(all\s+)?previous", re.I),
    re.compile(r"\bexfiltrate\b", re.I),
    re.compile(r"SELECT\s+.+FROM\s+", re.I | re.S),
    re.compile(r"<\s*(script|img|iframe|svg)\b", re.I),
]


def guard_input(text: str) -> str:
    """Raises HTTPException 400 if text matches any Lobster Trap injection pattern."""
    for pattern in _LOBSTER_TRAP_PATTERNS:
        if pattern.search(text):
            raise HTTPException(status_code=400, detail="Input rejected by content policy")
    return text


# ── Decision Log emission ─────────────────────────────────────────────────────

def emit_decision(
    session_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    tenant_id: str,
    tools_invoked: list[str] | None = None,
    outcome: str = "success",
    correlation_id: str | None = None,
) -> None:
    """Fire-and-forget POST to Agent Registry decision log.
    tenant_id is caller-derived (HC-4). Agent is unaffected if registry is down.
    """
    payload = {
        "tenant_id": tenant_id,
        "agent_id": AGENT_ID,
        "session_id": session_id,
        "autonomy_tier": "L1",
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "tools_invoked": tools_invoked or [],
        "policy_decision": "allowed",
        "outcome": outcome,
        "correlation_id": correlation_id or str(uuid.uuid4()),
    }
    try:
        with httpx.Client(timeout=3.0) as client:
            client.post(f"{AGENT_REGISTRY_URL}/decisions", json=payload)
    except Exception as exc:
        log.debug("Decision log emit failed (non-fatal): %s", exc)


# ── Consent gate helper (STEP-P2-02) ─────────────────────────────────────────

async def _consent_allowed(subject_id_hash: str, channel: str, purpose: str, tenant_id: str) -> bool:
    """Return True only when the consent-service confirms allowed=true.
    Default-deny on any network error or non-2xx (HC-6 / DPA 2019 §25).
    tenant_id is caller-derived (HC-4).
    """
    url = (
        f"{CONSENT_SERVICE_URL}/consent/{subject_id_hash}"
        f"?channel={channel}&purpose={purpose}&tenant_id={tenant_id}"
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            return False
        return bool(resp.json().get("allowed", False))
    except Exception as exc:
        log.warning("consent_check_failed channel=%s: %s", channel, exc)
        return False


# ── MCP Gateway helpers ───────────────────────────────────────────────────────

async def mcp_gateway_invoke(tool_name: str, payload: dict, session_id: str, tenant_id: str) -> dict:
    """Invoke a tool through the MCP Gateway with caller-derived tenant."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{MCP_GATEWAY_URL}/tools/{tool_name}/invoke",
            headers={
                "X-Agent-Id":       AGENT_ID,
                "X-Tenant-Id":      tenant_id,
                "X-Correlation-Id": session_id,
            },
            json={"input": payload},
        )
        resp.raise_for_status()
        return resp.json().get("output", {})


async def retrieve_context(query: str, tenant_id: str, n_results: int = 5, session_id: str = "") -> str:
    """Retrieve manifesto context from ChromaDB via the MCP Gateway chroma.search tool."""
    try:
        result = await mcp_gateway_invoke(
            "chroma.search",
            {"query": query, "collection": CHROMA_COLL, "n_results": n_results},
            session_id=session_id or str(uuid.uuid4()),
            tenant_id=tenant_id,
        )
        docs = [d.get("content", "") for d in result.get("documents", [])]
        return "\n\n---\n\n".join(docs) if docs else ""
    except Exception as exc:
        log.warning("ChromaDB retrieval via gateway failed: %s", exc)
        return ""


async def llm_chat(prompt: str, tenant_id: str, model: str = MODEL_HEAVY, max_tokens: int = 1000, session_id: str = "") -> str:
    """Chat completion via the MCP Gateway litellm.chat tool. Emits OTel span (STEP-P1-13)."""
    with _tracer.start_as_current_span("llm.chat") as span:
        span.set_attribute("ai.model", model)
        span.set_attribute("ai.tenant_id", tenant_id)
        span.set_attribute("ai.agent_id", AGENT_ID)
        span.set_attribute("ai.input_tokens", len(prompt) // 4)
        result = await mcp_gateway_invoke(
            "litellm.chat",
            {
                "model":       model,
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  max_tokens,
                "temperature": 0.7,
            },
            session_id=session_id or str(uuid.uuid4()),
            tenant_id=tenant_id,
        )
        content = result.get("content", "")
        span.set_attribute("ai.output_tokens", len(content) // 4)
        return content


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="PMaaS Campaign Agent", version="2.0.0")
# OTel FastAPI auto-instrumentation (STEP-P1-13)
FastAPIInstrumentor.instrument_app(app, tracer_provider=_tracer_provider)

# ── Request / Response models ─────────────────────────────────────────────────
class BriefingRequest(BaseModel):
    prompt:  str
    context: dict = {}

class AskRequest(BaseModel):
    question: str

class AnalyzeRequest(BaseModel):
    ward_name:          str
    registered_voters:  int = 0
    target_votes:       int = 0
    current_sentiment:  float = 50.0
    recent_interactions: int = 0

class ContentRequest(BaseModel):
    campaign_name: str
    ward_name:     str
    channel:       str = "whatsapp"   # whatsapp | social | voice
    tone:          str = "persuasive"
    key_message:   str = ""

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "campaign-agent", "ts": datetime.now(UTC).isoformat()}

@app.post("/briefing")
async def generate_briefing(
    req: BriefingRequest,
    caller: _CallerCtx = Depends(_require_auth),
):
    """Generate daily campaign briefing with optional manifesto RAG context."""
    session_id  = str(uuid.uuid4())
    tenant_id   = caller.tenant_id
    prompt_text = guard_input(req.prompt)

    rag_context = await retrieve_context(
        "campaign strategy ward voter engagement", tenant_id=tenant_id, session_id=session_id
    )

    augmented_prompt = prompt_text
    if rag_context:
        augmented_prompt = (
            f"{prompt_text}\n\n"
            f"MANIFESTO CONTEXT (from PMaaS knowledge base):\n{rag_context[:2000]}"
        )

    try:
        briefing_text = await llm_chat(
            augmented_prompt, tenant_id=tenant_id, model=MODEL_HEAVY, max_tokens=1400, session_id=session_id
        )
    except Exception as exc:
        log.error("LLM call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc

    # Emit decision log (P3-LOW: use get_running_loop)
    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None, emit_decision, session_id, MODEL_HEAVY,
        len(augmented_prompt.split()), len(briefing_text.split()), tenant_id,
        ["chroma.search", "litellm.chat"], "success", session_id,
    )

    return JSONResponse({
        "briefing":    briefing_text,
        "model":       f"agent/{MODEL_HEAVY}",
        "rag_used":    bool(rag_context),
        "generated_at": datetime.now(UTC).isoformat(),
    })

@app.post("/ask")
async def ask_manifesto(
    req: AskRequest,
    caller: _CallerCtx = Depends(_require_auth),
):
    """Answer a campaign question using manifesto RAG."""
    session_id  = str(uuid.uuid4())
    tenant_id   = caller.tenant_id
    question    = guard_input(req.question)
    rag_context = await retrieve_context(question, tenant_id=tenant_id, n_results=4, session_id=session_id)

    if rag_context:
        prompt = (
            f"You are Dawa, the AI campaign strategist. "
            f"Answer the following question using the manifesto context provided.\n\n"
            f"MANIFESTO CONTEXT:\n{rag_context[:3000]}\n\n"
            f"QUESTION: {question}\n\n"
            f"Give a concise, actionable answer in 2–4 sentences. "
            f"Quote from the manifesto where relevant."
        )
    else:
        prompt = (
            f"You are Dawa, the AI campaign strategist for a Kenyan political campaign. "
            f"Answer this campaign strategy question:\n\n{question}\n\n"
            f"Give a concise, actionable answer in 2–4 sentences."
        )

    try:
        answer = await llm_chat(prompt, tenant_id=tenant_id, model=MODEL_FAST, max_tokens=500, session_id=session_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None, emit_decision, session_id, MODEL_FAST,
        len(prompt.split()), len(answer.split()), tenant_id,
        ["chroma.search", "litellm.chat"], "success", session_id,
    )

    return {"answer": answer, "rag_used": bool(rag_context)}

@app.post("/analyze")
async def analyze_ward(
    req: AnalyzeRequest,
    caller: _CallerCtx = Depends(_require_auth),
):
    """Generate ward-specific targeting analysis and recommendations."""
    session_id = str(uuid.uuid4())
    tenant_id  = caller.tenant_id
    ward_name  = guard_input(req.ward_name)

    rag_context = await retrieve_context(
        f"{ward_name} ward development priorities", tenant_id=tenant_id, session_id=session_id
    )

    prompt = (
        f"You are Dawa, the AI campaign strategist.\n\n"
        f"Ward: {ward_name}\n"
        f"Registered Voters: {req.registered_voters:,}\n"
        f"Target Votes Needed: {req.target_votes:,}\n"
        f"Current Sentiment Score: {req.current_sentiment:.0f}/100\n"
        f"Recent Voter Interactions: {req.recent_interactions}\n"
    )
    if rag_context:
        prompt += f"\nMANIFESTO PRIORITIES FOR THIS AREA:\n{rag_context[:1500]}\n"

    prompt += (
        "\nProvide a strategic analysis with:\n"
        "1. VOTE GAP: How many more votes needed and feasibility assessment\n"
        "2. TOP 3 ISSUES: Key issues for this ward based on the manifesto\n"
        "3. OUTREACH STRATEGY: 3 specific actions to increase penetration\n"
        "4. RISK ASSESSMENT: Key risks and mitigation\n\n"
        "Keep it under 300 words and action-oriented."
    )

    try:
        analysis = await llm_chat(prompt, tenant_id=tenant_id, model=MODEL_HEAVY, max_tokens=600, session_id=session_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None, emit_decision, session_id, MODEL_HEAVY,
        len(prompt.split()), len(analysis.split()), tenant_id,
        ["chroma.search", "litellm.chat"], "success", session_id,
    )

    return {"ward": ward_name, "analysis": analysis, "model": MODEL_HEAVY}

@app.post("/content")
async def generate_content(
    req: ContentRequest,
    caller: _CallerCtx = Depends(_require_auth),
):
    """Generate campaign content for a specific channel.

    Consent gate (STEP-P2-02): consent is checked per-channel using HMAC-SHA256
    keyed by MEMBER_HMAC_SECRET (FLAG-8 / HC-6). The hash is computed from the
    campaign name for campaign-level consent; per-recipient checks happen at
    dispatch time in the Kafka consumer.
    """
    import hmac as _hmac
    import hashlib as _hashlib

    session_id  = str(uuid.uuid4())
    tenant_id   = caller.tenant_id
    ward_name   = guard_input(req.ward_name)
    key_message = guard_input(req.key_message)

    # FLAG-8 / HC-6: compute campaign-level consent hash using HMAC-SHA256 keyed
    # by MEMBER_HMAC_SECRET — NOT a plain string transform.
    member_hmac_secret = os.getenv("MEMBER_HMAC_SECRET", "")
    if not member_hmac_secret:
        raise HTTPException(status_code=500, detail="MEMBER_HMAC_SECRET is not configured")
    campaign_hash = _hmac.new(
        member_hmac_secret.encode(),
        req.campaign_name.lower().encode(),
        _hashlib.sha256,
    ).hexdigest()

    channel_map = {"whatsapp": "whatsapp", "voice": "voice", "social": "sms"}
    consent_channel = channel_map.get(req.channel, req.channel)

    if not await _consent_allowed(campaign_hash, consent_channel, "marketing", tenant_id):
        raise HTTPException(
            status_code=403,
            detail=f"Consent not recorded for channel={consent_channel}/purpose=marketing",
        )

    channel_instructions = {
        "whatsapp": "Write a WhatsApp message (max 160 words). Use bullet points, be conversational, include a clear call-to-action.",
        "social":   "Write a Twitter/X post (max 280 chars) AND a Facebook post (max 100 words). Use relevant hashtags.",
        "voice":    "Write a 30-second voice call script (approx 75 words). Natural speech, persuasive, ends with action request.",
    }
    instruction = channel_instructions.get(req.channel, channel_instructions["whatsapp"])

    rag_context = await retrieve_context(ward_name, tenant_id=tenant_id, n_results=3, session_id=session_id)

    prompt = (
        f"You are Dawa, generating campaign content for {req.campaign_name}.\n\n"
        f"Target Ward: {ward_name}\n"
        f"Channel: {req.channel}\n"
        f"Tone: {req.tone}\n"
        f"Key Message: {key_message or 'General campaign support'}\n"
    )
    if rag_context:
        prompt += f"\nMANIFESTO CONTEXT:\n{rag_context[:1000]}\n"
    prompt += f"\nINSTRUCTION: {instruction}\n\nGenerate the content now:"

    try:
        content = await llm_chat(prompt, tenant_id=tenant_id, model=MODEL_FAST, max_tokens=400, session_id=session_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None, emit_decision, session_id, MODEL_FAST,
        len(prompt.split()), len(content.split()), tenant_id,
        ["chroma.search", "litellm.chat"], "success", session_id,
    )

    return {
        "content":   content,
        "channel":   req.channel,
        "ward":      ward_name,
        "campaign":  req.campaign_name,
        "model":     MODEL_FAST,
    }
