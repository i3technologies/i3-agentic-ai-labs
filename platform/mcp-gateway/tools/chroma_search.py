"""
MCP Tool: chroma.search — Tier 0 (read-only)

Input schema:
  { query: str, collection: str, n_results?: int }

Output:
  { documents: [{ content: str, source: str, page: str }] }
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import chromadb
from chromadb.config import Settings

from main import register_tool
from schemas import McpToolSpec

log = logging.getLogger("mcp.chroma.search")

CHROMA_HOST  = os.environ.get("CHROMA_HOST",  "chromadb.i3-admissions.svc.cluster.local")
CHROMA_PORT  = int(os.environ.get("CHROMA_PORT", "8000"))
CHROMA_TOKEN = os.environ.get("CHROMA_TOKEN", "")

SPEC = McpToolSpec(
    name="chroma.search",
    description="Semantic similarity search over a ChromaDB collection.",
    version="1.0.0",
    tenant_scope="single",
    read_write="read",
    side_effect_class="none",
    risk_tier=0,
    rate_limit=120,
    timeout_ms=8_000,
    audit_required=False,
)


def _get_client() -> chromadb.HttpClient:
    headers = {"Authorization": f"Bearer {CHROMA_TOKEN}"} if CHROMA_TOKEN else {}
    return chromadb.HttpClient(
        host=CHROMA_HOST,
        port=CHROMA_PORT,
        settings=Settings(anonymized_telemetry=False),
        headers=headers,
    )


async def handle(payload: dict[str, Any], *, tenant_id: str) -> dict:
    query      = payload.get("query", "")
    collection = payload.get("collection", "admissions-docs")
    n_results  = min(int(payload.get("n_results", 5)), 20)

    if not query:
        return {"documents": []}

    loop = asyncio.get_event_loop()

    def _search():
        client = _get_client()
        coll   = client.get_or_create_collection(collection)
        return coll.query(query_texts=[query], n_results=n_results)

    results = await loop.run_in_executor(None, _search)
    docs    = results.get("documents", [[]])[0]
    metas   = results.get("metadatas", [[]])[0]

    items = []
    for doc, meta in zip(docs, metas):
        items.append({
            "content": doc,
            "source":  meta.get("file_name", "unknown"),
            "page":    meta.get("page_label", "?"),
        })

    log.info("chroma.search: %d results from collection=%s", len(items), collection)
    return {"documents": items}


register_tool(SPEC, handle)
