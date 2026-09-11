"""
PMaaS Campaign Agent — LangGraph-based autonomous strategy agent.

Capabilities:
  - /briefing  POST  — daily campaign briefing with RAG from manifesto
  - /ask       POST  — manifesto/strategy Q&A with ChromaDB RAG
  - /analyze   POST  — ward-level targeting analysis
  - /content   POST  — generate campaign content (social, WhatsApp, voice)
  - /health    GET   — liveness probe

Env vars:
  LITELLM_URL        — http://litellm-proxy.i3-model-gateway.svc:4000/v1
  LITELLM_KEY        — master key
  LITELLM_MODEL_HEAVY — qwen-heavy (default)
  LITELLM_MODEL_FAST  — qwen-fast (default)
  CHROMA_HOST        — chromadb.i3-ai-lab.svc.cluster.local
  CHROMA_TOKEN       — bearer token
  CHROMA_COLLECTION  — pmaas-manifesto
  KAFKA_BOOTSTRAP    — kafka-bootstrap.i3-messaging.svc:9092
  API_KEY            — shared key for intra-cluster calls (from pmaas-secrets)
"""

import os
import json
import logging
import asyncio
from datetime import datetime, UTC
from typing import Annotated, TypedDict

import httpx
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import chromadb
from chromadb.config import Settings

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("campaign-agent")

# ── Config ───────────────────────────────────────────────────────────────────
LITELLM_URL    = os.getenv("LITELLM_URL",           "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1")
LITELLM_KEY    = os.getenv("LITELLM_KEY",           "")
MODEL_HEAVY    = os.getenv("LITELLM_MODEL_HEAVY",   "qwen-heavy")
MODEL_FAST     = os.getenv("LITELLM_MODEL_FAST",    "qwen-fast")
CHROMA_HOST    = os.getenv("CHROMA_HOST",           "chromadb.i3-ai-lab.svc.cluster.local")
CHROMA_TOKEN   = os.getenv("CHROMA_TOKEN",          "")
CHROMA_COLL    = os.getenv("CHROMA_COLLECTION",     "pmaas-manifesto")
API_KEY        = os.getenv("LITELLM_KEY",           "")   # reuse LiteLLM key for intra-cluster auth
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP",      "")

# ── ChromaDB client ───────────────────────────────────────────────────────────
def get_chroma() -> chromadb.HttpClient:
    return chromadb.HttpClient(
        host=CHROMA_HOST,
        port=8000,
        settings=Settings(anonymized_telemetry=False),
        headers={"Authorization": f"Bearer {CHROMA_TOKEN}"} if CHROMA_TOKEN else {},
    )

# ── LiteLLM helper ────────────────────────────────────────────────────────────
async def llm_chat(prompt: str, model: str = MODEL_HEAVY, max_tokens: int = 1000) -> str:
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {LITELLM_KEY}",
    }
    payload = {
        "model":       model,
        "messages":    [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens":  max_tokens,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{LITELLM_URL}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

# ── RAG helper — retrieve from ChromaDB manifesto collection ─────────────────
async def retrieve_context(query: str, n_results: int = 5) -> str:
    try:
        loop   = asyncio.get_event_loop()
        chroma = await loop.run_in_executor(None, get_chroma)
        coll   = await loop.run_in_executor(None, lambda: chroma.get_or_create_collection(CHROMA_COLL))
        results = await loop.run_in_executor(
            None,
            lambda: coll.query(query_texts=[query], n_results=n_results)
        )
        docs = results.get("documents", [[]])[0]
        return "\n\n---\n\n".join(docs) if docs else ""
    except Exception as exc:
        log.warning("ChromaDB retrieval failed: %s", exc)
        return ""

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="PMaaS Campaign Agent", version="1.0.0")

def verify_api_key(x_api_key: str = Header(default="")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

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

@app.post("/briefing", dependencies=[Depends(verify_api_key)])
async def generate_briefing(req: BriefingRequest):
    """Generate daily campaign briefing with optional manifesto RAG context."""
    # Retrieve relevant manifesto sections
    rag_context = await retrieve_context("campaign strategy ward voter engagement")

    augmented_prompt = req.prompt
    if rag_context:
        augmented_prompt = (
            f"{req.prompt}\n\n"
            f"MANIFESTO CONTEXT (from PMaaS knowledge base):\n{rag_context[:2000]}"
        )

    try:
        briefing_text = await llm_chat(augmented_prompt, model=MODEL_HEAVY, max_tokens=1400)
    except Exception as exc:
        log.error("LLM call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"LLM error: {exc}") from exc

    return JSONResponse({
        "briefing":    briefing_text,
        "model":       f"agent/{MODEL_HEAVY}",
        "rag_used":    bool(rag_context),
        "generated_at": datetime.now(UTC).isoformat(),
    })

@app.post("/ask", dependencies=[Depends(verify_api_key)])
async def ask_manifesto(req: AskRequest):
    """Answer a campaign question using manifesto RAG."""
    rag_context = await retrieve_context(req.question, n_results=4)

    if rag_context:
        prompt = (
            f"You are Dawa, the AI campaign strategist. "
            f"Answer the following question using the manifesto context provided.\n\n"
            f"MANIFESTO CONTEXT:\n{rag_context[:3000]}\n\n"
            f"QUESTION: {req.question}\n\n"
            f"Give a concise, actionable answer in 2–4 sentences. "
            f"Quote from the manifesto where relevant."
        )
    else:
        prompt = (
            f"You are Dawa, the AI campaign strategist for a Kenyan political campaign. "
            f"Answer this campaign strategy question:\n\n{req.question}\n\n"
            f"Give a concise, actionable answer in 2–4 sentences."
        )

    try:
        answer = await llm_chat(prompt, model=MODEL_FAST, max_tokens=500)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"answer": answer, "rag_used": bool(rag_context)}

@app.post("/analyze", dependencies=[Depends(verify_api_key)])
async def analyze_ward(req: AnalyzeRequest):
    """Generate ward-specific targeting analysis and recommendations."""
    rag_context = await retrieve_context(f"{req.ward_name} ward development priorities")

    prompt = (
        f"You are Dawa, the AI campaign strategist.\n\n"
        f"Ward: {req.ward_name}\n"
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
        analysis = await llm_chat(prompt, model=MODEL_HEAVY, max_tokens=600)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"ward": req.ward_name, "analysis": analysis, "model": MODEL_HEAVY}

@app.post("/content", dependencies=[Depends(verify_api_key)])
async def generate_content(req: ContentRequest):
    """Generate campaign content for a specific channel."""
    channel_instructions = {
        "whatsapp": "Write a WhatsApp message (max 160 words). Use bullet points, be conversational, include a clear call-to-action.",
        "social":   "Write a Twitter/X post (max 280 chars) AND a Facebook post (max 100 words). Use relevant hashtags.",
        "voice":    "Write a 30-second voice call script (approx 75 words). Natural speech, persuasive, ends with action request.",
    }
    instruction = channel_instructions.get(req.channel, channel_instructions["whatsapp"])

    rag_context = await retrieve_context(req.ward_name, n_results=3)

    prompt = (
        f"You are Dawa, generating campaign content for {req.campaign_name}.\n\n"
        f"Target Ward: {req.ward_name}\n"
        f"Channel: {req.channel}\n"
        f"Tone: {req.tone}\n"
        f"Key Message: {req.key_message or 'General campaign support'}\n"
    )
    if rag_context:
        prompt += f"\nMANIFESTO CONTEXT:\n{rag_context[:1000]}\n"
    prompt += f"\nINSTRUCTION: {instruction}\n\nGenerate the content now:"

    try:
        content = await llm_chat(prompt, model=MODEL_FAST, max_tokens=400)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "content":   content,
        "channel":   req.channel,
        "ward":      req.ward_name,
        "campaign":  req.campaign_name,
        "model":     MODEL_FAST,
    }
