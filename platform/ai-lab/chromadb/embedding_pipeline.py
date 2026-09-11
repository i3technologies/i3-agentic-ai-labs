#!/usr/bin/env python3
"""
embedding_pipeline.py
=====================
Embedding pipeline for i3 Platform RAG corpora.

Reads source documents, generates 768-dim embeddings via Ollama
nomic-embed-text:v1.5, and upserts them into ChromaDB.

Collections built:
  - i3-exam-corpus       EvalOS questions + explanations (from evalos_db)
  - onboarding-docs      Platform docs, HR policies, how-to guides (from files)

Run as a Kubernetes Job (see embedding-pipeline-job.yaml) or
locally for development:

    pip install chromadb requests psycopg2-binary python-dotenv
    python3 platform/ai-lab/chromadb/embedding_pipeline.py --collection i3-exam-corpus

Env vars (set via Secret in K8s):
    CHROMA_HOST       chromadb.i3-ai-lab.svc.cluster.local
    CHROMA_PORT       8000
    CHROMA_TOKEN      <from chromadb-secrets>
    OLLAMA_URL        http://ollama-service.i3-model-gateway.svc.cluster.local:11434
    DB_URL            postgresql://... (evalos_db pgbouncer URL)
    COLLECTION        i3-exam-corpus | onboarding-docs
"""

import os
import sys
import json
import time
import argparse
import logging
from typing import Optional

import requests
import chromadb
from chromadb.config import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# ── Config from env ───────────────────────────────────────────
CHROMA_HOST  = os.getenv("CHROMA_HOST", "chromadb.i3-ai-lab.svc.cluster.local")
CHROMA_PORT  = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_TOKEN = os.getenv("CHROMA_TOKEN", "")
OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://ollama-service.i3-model-gateway.svc.cluster.local:11434")
EMBED_MODEL  = "nomic-embed-text:v1.5"
DB_URL       = os.getenv("DB_URL", "")
BATCH_SIZE   = 50


def get_chroma_client() -> chromadb.HttpClient:
    settings = Settings(
        chroma_client_auth_provider="chromadb.auth.token_authn.TokenAuthClientProvider",
        chroma_client_auth_credentials=CHROMA_TOKEN,
    ) if CHROMA_TOKEN else Settings()

    return chromadb.HttpClient(
        host=CHROMA_HOST,
        port=CHROMA_PORT,
        settings=settings,
    )


def embed(texts: list[str]) -> list[list[float]]:
    """Generate embeddings via Ollama nomic-embed-text."""
    embeddings: list[list[float]] = []
    for text in texts:
        resp = requests.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": text},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings.append(data["embeddings"][0])
    return embeddings


def upsert_batch(
    collection: chromadb.Collection,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    """Upsert a batch into ChromaDB with auto-generated embeddings."""
    log.info("  Embedding %d docs …", len(documents))
    vectors = embed(documents)
    collection.upsert(
        ids=ids,
        embeddings=vectors,
        documents=documents,
        metadatas=metadatas,
    )
    log.info("  ✓ Upserted %d documents", len(documents))


# ── Collection: i3-exam-corpus (from evalos_db) ───────────────
def build_exam_corpus(client: chromadb.HttpClient) -> None:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    log.info("Building collection: i3-exam-corpus")
    collection = client.get_or_create_collection(
        name="i3-exam-corpus",
        metadata={"hnsw:space": "cosine"},
    )

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT id, set_number, domain_number, domain_name, topic,
               text, type, correct_answers, explanation
        FROM questions
        WHERE is_active = TRUE
        ORDER BY set_number, domain_number, id
    """)
    rows = cur.fetchall()
    conn.close()

    log.info("  Found %d active questions", len(rows))

    ids, docs, metas = [], [], []
    for i, row in enumerate(rows):
        # Build a rich document string for each question
        correct = ", ".join(row["correct_answers"]) if row["correct_answers"] else ""
        doc = (
            f"Domain: {row['domain_name']}\n"
            f"Topic: {row['topic']}\n"
            f"Question: {row['text']}\n"
            f"Correct answer: {correct}\n"
            f"Explanation: {row['explanation'] or ''}"
        )
        ids.append(str(row["id"]))
        docs.append(doc)
        metas.append({
            "set_number":    row["set_number"],
            "domain_number": row["domain_number"],
            "domain_name":   row["domain_name"],
            "topic":         row["topic"],
            "question_type": row["type"],
        })

        # Flush in batches
        if len(ids) >= BATCH_SIZE:
            upsert_batch(collection, ids, docs, metas)
            ids, docs, metas = [], [], []
            time.sleep(0.5)  # rate-limit Ollama

    if ids:
        upsert_batch(collection, ids, docs, metas)

    count = collection.count()
    log.info("  ✓ i3-exam-corpus: %d vectors total", count)


# ── Collection: onboarding-docs (from flat files) ─────────────
def build_onboarding_docs(client: chromadb.HttpClient, docs_dir: str = "/docs") -> None:
    import hashlib

    log.info("Building collection: onboarding-docs from %s", docs_dir)
    collection = client.get_or_create_collection(
        name="onboarding-docs",
        metadata={"hnsw:space": "cosine"},
    )

    supported_exts = {".txt", ".md", ".json"}
    ids, docs, metas = [], [], []

    for root, _, files in os.walk(docs_dir):
        for filename in sorted(files):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in supported_exts:
                continue

            path = os.path.join(root, filename)
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().strip()
                if not content:
                    continue

                # Chunk large files into 800-char overlapping windows
                chunks = chunk_text(content, size=800, overlap=100)
                for j, chunk in enumerate(chunks):
                    doc_id = hashlib.sha256(f"{path}:{j}".encode()).hexdigest()[:16]
                    ids.append(doc_id)
                    docs.append(chunk)
                    metas.append({
                        "filename": filename,
                        "path":     path,
                        "chunk":    j,
                        "total":    len(chunks),
                    })

                    if len(ids) >= BATCH_SIZE:
                        upsert_batch(collection, ids, docs, metas)
                        ids, docs, metas = [], [], []
                        time.sleep(0.5)

            except Exception as e:
                log.warning("  Skipping %s: %s", path, e)

    if ids:
        upsert_batch(collection, ids, docs, metas)

    count = collection.count()
    log.info("  ✓ onboarding-docs: %d vectors total", count)


def chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


# ── Entry point ───────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="i3 RAG embedding pipeline")
    parser.add_argument(
        "--collection",
        choices=["i3-exam-corpus", "onboarding-docs", "all"],
        default="all",
        help="Which collection to build (default: all)",
    )
    parser.add_argument(
        "--docs-dir",
        default="/docs",
        help="Directory of onboarding docs (default: /docs)",
    )
    args = parser.parse_args()

    log.info("i3 Embedding Pipeline — start")
    log.info("  ChromaDB: %s:%s", CHROMA_HOST, CHROMA_PORT)
    log.info("  Ollama:   %s", OLLAMA_URL)
    log.info("  Model:    %s", EMBED_MODEL)

    client = get_chroma_client()

    # Quick connectivity check
    client.heartbeat()
    log.info("  ✓ ChromaDB connected")

    if args.collection in ("i3-exam-corpus", "all"):
        if not DB_URL:
            log.error("DB_URL not set — cannot build i3-exam-corpus")
        else:
            build_exam_corpus(client)

    if args.collection in ("onboarding-docs", "all"):
        build_onboarding_docs(client, args.docs_dir)

    log.info("Pipeline complete.")


if __name__ == "__main__":
    main()
