"""
AfroERP AI Agent — Business intelligence & automation agent for ERPNext.

Capabilities:
  - /health         GET  — liveness probe
  - /analyze        POST — financial / operational analysis
  - /automate       POST — generate ERPNext document drafts (invoice, PO, Journal)
  - /report         POST — AI narrative summary of an ERPNext report
  - /chat           POST — general ERP Q&A grounded in frappe schema

Env vars:
  LITELLM_URL         — LiteLLM gateway
  LITELLM_KEY         — master key
  ERP_URL             — http://afroerp-web.i3-erp.svc.cluster.local:8080
  ERP_API_KEY         — ERPNext API key
  ERP_API_SECRET      — ERPNext API secret
  CHROMA_HOST         — ChromaDB for ERP knowledge base
  CHROMA_TOKEN        — ChromaDB bearer token
"""

import os
import logging
from datetime import datetime, UTC

import httpx
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("afroerp-agent")

LITELLM_URL  = os.getenv("LITELLM_URL",  "http://litellm-proxy.i3-model-gateway.svc.cluster.local:4000/v1")
LITELLM_KEY  = os.getenv("LITELLM_KEY",  "")
MODEL_HEAVY  = os.getenv("LITELLM_MODEL_HEAVY", "qwen-heavy")
MODEL_FAST   = os.getenv("LITELLM_MODEL_FAST",  "qwen-fast")
ERP_URL      = os.getenv("ERP_URL",      "http://afroerp-web.i3-erp.svc.cluster.local:8080")
ERP_API_KEY  = os.getenv("ERP_API_KEY",  "")
ERP_SECRET   = os.getenv("ERP_API_SECRET", "")
API_KEY      = os.getenv("LITELLM_KEY",  "")   # shared intra-cluster key

# ── LiteLLM helper ────────────────────────────────────────────
async def llm(prompt: str, model: str = MODEL_HEAVY, max_tokens: int = 800) -> str:
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {LITELLM_KEY}",
    }
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            f"{LITELLM_URL}/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": max_tokens,
            },
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

# ── ERPNext helper ────────────────────────────────────────────
async def erp_get(endpoint: str, params: dict | None = None) -> dict:
    headers = {
        "Authorization": f"token {ERP_API_KEY}:{ERP_SECRET}",
        "Content-Type":  "application/json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{ERP_URL}{endpoint}", params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()

# ── App ────────────────────────────────────────────────────────
app = FastAPI(title="AfroERP AI Agent", version="1.0.0")

def verify_key(x_api_key: str = Header(default="")):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

# ── Models ────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    doctype:     str          # e.g. "Sales Invoice", "Purchase Order"
    date_range:  str = "this month"
    question:    str = "Summarise key trends and flag anomalies"

class AutomateRequest(BaseModel):
    doctype:     str
    description: str          # natural-language description of the document to draft
    context:     dict = {}

class ReportRequest(BaseModel):
    report_name: str
    filters:     dict = {}

class ChatRequest(BaseModel):
    message: str

# ── Endpoints ─────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "afroerp-agent", "ts": datetime.now(UTC).isoformat()}

@app.post("/analyze", dependencies=[Depends(verify_key)])
async def analyze(req: AnalyzeRequest):
    """Fetch ERP data and generate an AI narrative analysis."""
    # Attempt to pull recent records from ERPNext
    erp_data: dict = {}
    try:
        erp_data = await erp_get(
            "/api/resource/" + req.doctype.replace(" ", "%20"),
            params={
                "filters": f'[["creation", ">=", "2024-01-01"]]',
                "fields":  '["name","total","status","customer","supplier","posting_date"]',
                "limit":   20,
            }
        )
    except Exception as exc:
        log.warning("ERP fetch failed: %s", exc)

    context = f"ERP Data ({req.doctype}, {req.date_range}):\n{erp_data}\n\n" if erp_data else ""

    prompt = (
        f"You are Mfumo, the AfroERP AI business analyst.\n\n"
        f"{context}"
        f"Question: {req.question}\n\n"
        f"Analyse the data and provide:\n"
        f"1. KEY METRICS: Top 3 metrics that matter\n"
        f"2. TRENDS: Notable patterns or changes\n"
        f"3. ANOMALIES: Any figures that look unusual\n"
        f"4. RECOMMENDATIONS: 2-3 concrete actions\n\n"
        f"Be concise — max 250 words. Use KES currency where relevant."
    )

    try:
        analysis = await llm(prompt, model=MODEL_HEAVY, max_tokens=600)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"doctype": req.doctype, "analysis": analysis, "model": MODEL_HEAVY}

@app.post("/automate", dependencies=[Depends(verify_key)])
async def automate(req: AutomateRequest):
    """Generate an ERPNext document draft as structured JSON from a natural-language description."""
    prompt = (
        f"You are Mfumo, the AfroERP automation assistant.\n\n"
        f"Generate a valid ERPNext {req.doctype} JSON document from this description:\n"
        f"\"{req.description}\"\n\n"
        f"Additional context: {req.context}\n\n"
        f"Return ONLY valid JSON matching the ERPNext {req.doctype} doctype schema. "
        f"Use KES as the default currency. "
        f"Include all required fields. Set status to 'Draft'. "
        f"Use today's date {datetime.now(UTC).strftime('%Y-%m-%d')} for posting_date."
    )

    try:
        draft_json_str = await llm(prompt, model=MODEL_HEAVY, max_tokens=800)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Try to parse the JSON — strip markdown fences if present
    import json, re
    clean = re.sub(r"```(?:json)?|```", "", draft_json_str).strip()
    try:
        draft = json.loads(clean)
    except Exception:
        draft = {"raw": draft_json_str}

    return {"doctype": req.doctype, "draft": draft, "model": MODEL_HEAVY}

@app.post("/report", dependencies=[Depends(verify_key)])
async def report_narrative(req: ReportRequest):
    """Generate an AI narrative summary of an ERPNext report."""
    report_data: dict = {}
    try:
        report_data = await erp_get(
            "/api/method/frappe.desk.query_report.run",
            params={"report_name": req.report_name, "filters": str(req.filters)},
        )
    except Exception as exc:
        log.warning("ERP report fetch failed: %s", exc)

    prompt = (
        f"You are Mfumo, the AfroERP business analyst.\n\n"
        f"Report: {req.report_name}\n"
        f"Data: {str(report_data)[:2000]}\n\n"
        f"Write a 3-paragraph executive summary of this report for a Kenyan business owner. "
        f"Highlight top performing areas, concerns, and 2 actionable recommendations. "
        f"Use KES currency notation."
    )

    try:
        narrative = await llm(prompt, model=MODEL_FAST, max_tokens=500)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"report": req.report_name, "narrative": narrative}

@app.post("/chat", dependencies=[Depends(verify_key)])
async def chat(req: ChatRequest):
    """General ERP Q&A — answers questions about ERPNext usage in Kenyan context."""
    prompt = (
        f"You are Mfumo, an expert ERPNext consultant specialised in Kenyan business operations.\n\n"
        f"User question: {req.message}\n\n"
        f"Give a concise, practical answer. If the question is about a specific ERPNext feature, "
        f"explain how to use it step by step. Keep it under 200 words."
    )
    try:
        answer = await llm(prompt, model=MODEL_FAST, max_tokens=400)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"answer": answer}
