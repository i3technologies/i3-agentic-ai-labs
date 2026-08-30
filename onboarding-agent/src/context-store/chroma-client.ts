/**
 * chroma-client.ts
 * Thin wrapper around the ChromaDB HTTP client scoped to the
 * `onboarding-corpus` collection.  Reuses the same cluster-internal
 * endpoint already used by the admissions agent:
 *   chromadb.i3-admissions.svc.cluster.local:8000
 *
 * CHROMA_DISABLED=true  — set this env var to skip ChromaDB entirely.
 * The retriever will return empty context and the mock LiteLLM drives
 * all responses locally.  Useful on Windows x64 where the chromadb
 * npm CLI does not ship a pre-built binary.
 */

// ── Graceful no-op stub used when CHROMA_DISABLED=true ───────────────────────

const DISABLED = process.env.CHROMA_DISABLED === 'true';

if (DISABLED) {
  console.warn('[chroma-client] CHROMA_DISABLED=true — ChromaDB skipped. RAG context will be empty; mock LiteLLM provides canned responses.');
}

// Lazy-import ChromaDB so the process starts even if the package has no
// native binary on the current platform (e.g. Windows x64 + Node 24).
type ChromaClientType   = import('chromadb').ChromaClient;
type CollectionType     = import('chromadb').Collection;

const COLLECTION_NAME = process.env.CHROMA_COLLECTION ?? 'onboarding-corpus';
const CHROMA_HOST     = process.env.CHROMA_HOST ?? 'chromadb.i3-admissions.svc.cluster.local';
const CHROMA_PORT     = parseInt(process.env.CHROMA_PORT ?? '8000', 10);
const CHROMA_TOKEN    = process.env.CHROMA_TOKEN;

let _client:     ChromaClientType | null = null;
let _collection: CollectionType   | null = null;

export async function getChromaClient(): Promise<ChromaClientType> {
  if (_client) return _client;

  const { ChromaClient } = await import('chromadb');
  _client = new ChromaClient({
    path: `http://${CHROMA_HOST}:${CHROMA_PORT}`,
    auth: CHROMA_TOKEN
      ? { provider: 'token', credentials: CHROMA_TOKEN }
      : undefined,
  });

  return _client;
}

export async function getCollection(): Promise<CollectionType> {
  if (_collection) return _collection;

  const { OpenAIEmbeddingFunction } = await import('chromadb');

  process.env.OPENAI_API_BASE = process.env.LITELLM_URL ?? 'http://localhost:4000/v1';
  const embedder = new OpenAIEmbeddingFunction({
    openai_api_key: process.env.LITELLM_KEY ?? 'no-key',
    openai_model:   process.env.LITELLM_MODEL_FAST ?? 'granite-nano',
  });

  const client = await getChromaClient();
  _collection  = await client.getOrCreateCollection({
    name:     COLLECTION_NAME,
    metadata: {
      description:    'i3 platform onboarding corpus — code, docs, curriculum',
      created_by:     'onboarding-agent',
      hnsw_space:     'cosine',
    },
    embeddingFunction: embedder,
  });

  return _collection;
}

/** Utility: wipe the collection (use only during re-ingestion, never in prod). */
export async function resetCollection(): Promise<void> {
  if (DISABLED) return;
  const client = await getChromaClient();
  try {
    await client.deleteCollection({ name: COLLECTION_NAME });
  } catch {
    // collection may not exist yet — that's fine
  }
  _collection = null;
  await getCollection(); // re-create empty
}

/** Health check — resolves true if ChromaDB is reachable (or disabled). */
export async function chromaHealthy(): Promise<boolean> {
  if (DISABLED) return true; // report healthy so /ready passes locally
  try {
    const client = await getChromaClient();
    await client.heartbeat();
    return true;
  } catch {
    return false;
  }
}

export { DISABLED as chromaDisabled };
