/**
 * retriever.ts
 * RAG retrieval layer.  Wraps ChromaDB similarity search with role-aware
 * metadata filtering so each subagent only sees chunks relevant to it.
 */

import { getCollection } from './chroma-client.js';

export interface RetrievalOptions {
  /** Role tag to filter on (e.g. 'platform_engineer'). Empty = no filter. */
  roleTag?:      string;
  /** Maximum number of chunks to return. Default: 8. */
  topK?:         number;
  /** Minimum cosine similarity (0–1). Default: 0.30. */
  minScore?:     number;
  /** Source types to include (e.g. ['documentation', 'code']). Empty = all. */
  sourceTypes?:  string[];
}

export interface RetrievedChunk {
  id:         string;
  document:   string;
  score:      number;
  filePath:   string;
  sourceType: string;
  roleTags:   string;
  chunkIndex: number;
  title?:     string;
}

/**
 * Retrieve the most relevant chunks for a given query string.
 * Uses ChromaDB's HNSW cosine ANN search; metadata filters applied post-query.
 */
export async function retrieve(
  query:   string,
  options: RetrievalOptions = {},
): Promise<RetrievedChunk[]> {
  const {
    roleTag     = '',
    topK        = 8,
    minScore    = 0.30,
    sourceTypes = [],
  } = options;

  const collection = await getCollection();

  // Build ChromaDB where filter
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const where: any = {};

  if (roleTag) {
    // role_tags is stored as a comma-separated string — use $contains
    where['role_tags'] = { $contains: roleTag };
  }

  if (sourceTypes.length === 1) {
    where['source_type'] = { $eq: sourceTypes[0] };
  } else if (sourceTypes.length > 1) {
    where['source_type'] = { $in: sourceTypes };
  }

  const queryParams: Parameters<typeof collection.query>[0] = {
    queryTexts: [query],
    nResults:   topK * 2,  // fetch extra, filter by score below
  };

  if (Object.keys(where).length > 0) {
    queryParams.where = where;
  }

  const results = await collection.query(queryParams);

  const ids       = results.ids[0]       ?? [];
  const docs      = results.documents[0] ?? [];
  const metas     = results.metadatas[0] ?? [];
  const distances = results.distances?.[0] ?? [];

  const chunks: RetrievedChunk[] = [];

  for (let i = 0; i < ids.length; i++) {
    // ChromaDB cosine distance → similarity: sim = 1 - distance
    const score = 1 - (distances[i] ?? 1);
    if (score < minScore) continue;

    const meta = (metas[i] ?? {}) as Record<string, string | number>;

    chunks.push({
      id:         ids[i],
      document:   docs[i] ?? '',
      score:      Math.round(score * 1000) / 1000,
      filePath:   String(meta['file_path']   ?? ''),
      sourceType: String(meta['source_type'] ?? ''),
      roleTags:   String(meta['role_tags']   ?? ''),
      chunkIndex: Number(meta['chunk_index'] ?? 0),
      title:      meta['title'] ? String(meta['title']) : undefined,
    });
  }

  // Sort descending by score, cap at topK
  return chunks
    .sort((a, b) => b.score - a.score)
    .slice(0, topK);
}

/**
 * Retrieve and format as a single context string for LLM prompts.
 * Each chunk is preceded by a source citation header.
 */
export async function retrieveAsContext(
  query:   string,
  options: RetrievalOptions = {},
): Promise<string> {
  const chunks = await retrieve(query, options);
  if (chunks.length === 0) return '(no relevant context found)';

  return chunks
    .map((c, i) =>
      `### [${i + 1}] ${c.filePath}` +
      (c.title ? ` — ${c.title}` : '') +
      ` (score: ${c.score})\n${c.document}`,
    )
    .join('\n\n---\n\n');
}

/**
 * Batch-retrieve for multiple queries in parallel — used by subagents to
 * gather context for all 5 task areas simultaneously.
 */
export async function retrieveBatch(
  queries:  string[],
  options:  RetrievalOptions = {},
): Promise<Map<string, RetrievedChunk[]>> {
  const results = await Promise.all(
    queries.map(q => retrieve(q, options).then(chunks => [q, chunks] as const)),
  );
  return new Map(results);
}
