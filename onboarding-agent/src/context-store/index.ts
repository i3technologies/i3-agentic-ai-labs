/**
 * index.ts
 * Ingestion pipeline: takes RawArtifacts → chunks → upserts into ChromaDB.
 * Called by the /api/onboarding/ingest endpoint and the CLI ingestion scripts.
 * When CHROMA_DISABLED=true the ingest is a no-op (local dev without ChromaDB).
 */

import { getCollection, chromaDisabled } from './chroma-client';
import { chunkAll, Chunk } from './chunker';
import { RawArtifact }     from '../ingestion/types';

/** Batch size for ChromaDB upsert calls (stay within HTTP body limits). */
const UPSERT_BATCH = 200;

export interface IndexResult {
  totalArtifacts: number;
  totalChunks:    number;
  upsertedChunks: number;
  skippedChunks:  number;
  durationMs:     number;
}

/**
 * Index an array of raw artifacts into the onboarding-corpus collection.
 * Safe to call incrementally — ChromaDB upsert is idempotent on chunk ID.
 */
export async function indexArtifacts(
  artifacts: RawArtifact[],
  options: { verbose?: boolean } = {},
): Promise<IndexResult> {
  const t0 = Date.now();

  // No-op when ChromaDB is disabled (local dev without a running instance)
  if (chromaDisabled) {
    console.warn('[context-store] CHROMA_DISABLED=true — ingest skipped');
    return { totalArtifacts: artifacts.length, totalChunks: 0, upsertedChunks: 0, skippedChunks: 0, durationMs: Date.now() - t0 };
  }

  const collection = await getCollection();
  const chunks     = chunkAll(artifacts);

  let upserted = 0;
  let skipped  = 0;

  for (let i = 0; i < chunks.length; i += UPSERT_BATCH) {
    const batch = chunks.slice(i, i + UPSERT_BATCH);

    // Filter out empty documents — ChromaDB rejects them
    const valid = batch.filter(c => c.document.trim().length > 0);
    skipped    += batch.length - valid.length;

    if (valid.length === 0) continue;

    await collection.upsert({
      ids:        valid.map(c => c.id),
      documents:  valid.map(c => c.document),
      metadatas:  valid.map(c => c.metadata as unknown as Record<string, string | number | boolean>),
    });

    upserted += valid.length;

    if (options.verbose) {
      console.log(
        `[context-store] upserted batch ${Math.floor(i / UPSERT_BATCH) + 1}` +
        ` (${upserted}/${chunks.length} chunks)`,
      );
    }
  }

  return {
    totalArtifacts: artifacts.length,
    totalChunks:    chunks.length,
    upsertedChunks: upserted,
    skippedChunks:  skipped,
    durationMs:     Date.now() - t0,
  };
}

/**
 * Return collection stats — used by /health and /api/onboarding/status.
 */
export async function getIndexStats(): Promise<{
  collectionName: string;
  count:          number;
  healthy:        boolean;
}> {
  try {
    const collection = await getCollection();
    const count      = await collection.count();
    return { collectionName: collection.name, count, healthy: true };
  } catch (err) {
    return { collectionName: 'onboarding-corpus', count: 0, healthy: false };
  }
}
