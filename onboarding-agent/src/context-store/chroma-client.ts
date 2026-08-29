/**
 * chroma-client.ts
 * Thin wrapper around the ChromaDB HTTP client scoped to the
 * `onboarding-corpus` collection.  Reuses the same cluster-internal
 * endpoint already used by the admissions agent:
 *   chromadb.i3-admissions.svc.cluster.local:8000
 */

import { ChromaClient, Collection, OpenAIEmbeddingFunction } from 'chromadb';

const COLLECTION_NAME = process.env.CHROMA_COLLECTION ?? 'onboarding-corpus';
const CHROMA_HOST     = process.env.CHROMA_HOST ?? 'chromadb.i3-admissions.svc.cluster.local';
const CHROMA_PORT     = parseInt(process.env.CHROMA_PORT ?? '8000', 10);
const CHROMA_TOKEN    = process.env.CHROMA_TOKEN;

// Embedding function — routes through the LiteLLM gateway so we never hit
// OpenAI directly; granite-nano handles embeddings cheaply (Tier 3).
// chromadb v1.9 OpenAIEmbeddingFunction constructor takes { openai_api_key, openai_model_name }
// and reads the base URL from OPENAI_API_BASE env var.
process.env.OPENAI_API_BASE = process.env.LITELLM_URL ?? 'http://localhost:4000/v1';
const embedder = new OpenAIEmbeddingFunction({
  openai_api_key: process.env.LITELLM_KEY ?? 'no-key',
  openai_model:   process.env.LITELLM_MODEL_FAST ?? 'granite-nano',
});

let _client: ChromaClient | null     = null;
let _collection: Collection | null   = null;

export async function getChromaClient(): Promise<ChromaClient> {
  if (_client) return _client;

  const authHeaders: Record<string, string> = {};
  if (CHROMA_TOKEN) {
    authHeaders['Authorization'] = `Bearer ${CHROMA_TOKEN}`;
  }

  _client = new ChromaClient({
    path: `http://${CHROMA_HOST}:${CHROMA_PORT}`,
    auth: CHROMA_TOKEN
      ? { provider: 'token', credentials: CHROMA_TOKEN }
      : undefined,
  });

  return _client;
}

export async function getCollection(): Promise<Collection> {
  if (_collection) return _collection;

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
  const client = await getChromaClient();
  try {
    await client.deleteCollection({ name: COLLECTION_NAME });
  } catch {
    // collection may not exist yet — that's fine
  }
  _collection = null;
  await getCollection(); // re-create empty
}

/** Health check — resolves true if ChromaDB is reachable. */
export async function chromaHealthy(): Promise<boolean> {
  try {
    const client = await getChromaClient();
    await client.heartbeat();
    return true;
  } catch {
    return false;
  }
}
