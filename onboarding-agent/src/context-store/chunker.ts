/**
 * chunker.ts
 * Converts RawArtifact objects into ChromaDB-ready chunks.
 *
 * Strategy:
 *  - Markdown / docs  → split on H2/H3 headings, then 800-token windows
 *  - Code files       → split on top-level declarations every 60 lines
 *  - SQL              → split per statement (semicolon-delimited)
 *  - YAML / JSON      → treat each top-level key block as a chunk
 *  - Small files (<400 chars) → kept as a single chunk
 */

import { RawArtifact } from '../ingestion/types';

export interface Chunk {
  id:        string;      // stable deterministic ID: sha1(source:offset)
  document:  string;      // text content for embedding
  metadata:  ChunkMeta;
}

export interface ChunkMeta {
  source:      string;
  source_type: string;
  role_tags:   string;    // comma-sep roles this chunk is relevant to
  file_path:   string;
  chunk_index: number;
  total_chunks: number;
  title?:      string;
}

// Approx token estimate: 1 token ≈ 4 chars
const TOKEN_LIMIT  = 800;
const CHAR_LIMIT   = TOKEN_LIMIT * 4;      // 3200 chars
const CODE_LINES   = 60;

/** Deterministic chunk ID — no external deps. */
function chunkId(source: string, index: number): string {
  const raw   = `${source}::${index}`;
  let hash    = 5381;
  for (let i = 0; i < raw.length; i++) {
    hash = ((hash << 5) + hash) ^ raw.charCodeAt(i);
    hash = hash >>> 0;
  }
  return `chunk_${hash.toString(16).padStart(8, '0')}`;
}

/** Infer which onboarding roles a chunk is most relevant to. */
function inferRoleTags(artifact: RawArtifact, text: string): string {
  const tags = new Set<string>();
  const low  = `${artifact.filePath} ${text}`.toLowerCase();

  if (/evalos|quiz|exam|bloom|enrolment|curriculum/.test(low)) tags.add('bootcamp_student');
  if (/k8s|kubernetes|argocd|tekton|dockerfile|helm|openshift|roks/.test(low)) tags.add('platform_engineer');
  if (/litellm|chroma|rag|llm|granite|mistral|langchain|agent|subagent/.test(low)) tags.add('ai_ml_engineer');
  if (/express|route|controller|middleware|api|endpoint/.test(low)) tags.add('backend_engineer');
  if (/secret|vault|openbao|keycloak|rbac|cert-manager|lobster/.test(low)) tags.add('security_engineer');

  // YAML infra/gitops files are always relevant to platform engineers
  if (artifact.filePath.includes('gitops') || artifact.filePath.includes('terraform') ||
      artifact.filePath.endsWith('.yaml') || artifact.filePath.endsWith('.yml')) {
    tags.add('platform_engineer');
  }
  if (tags.size === 0) tags.add('general');

  return [...tags].join(',');
}

// ──────────────────────────────────────────────────────────────────────────────
// Splitter functions
// ──────────────────────────────────────────────────────────────────────────────

function splitMarkdown(text: string): string[] {
  if (text.length < CHAR_LIMIT) return [text];

  // Split on H2/H3 headings first
  const sections = text.split(/(?=\n#{2,3} )/);
  const chunks: string[] = [];

  for (const section of sections) {
    if (section.length <= CHAR_LIMIT) {
      chunks.push(section.trim());
    } else {
      // Further split long sections into CHAR_LIMIT windows
      let offset = 0;
      while (offset < section.length) {
        chunks.push(section.slice(offset, offset + CHAR_LIMIT).trim());
        offset += CHAR_LIMIT;
      }
    }
  }

  return chunks.filter(c => c.length > 40);
}

function splitCode(text: string): string[] {
  if (text.length < CHAR_LIMIT) return [text];

  const lines  = text.split('\n');
  const chunks: string[] = [];
  let   block: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    block.push(lines[i]);
    if (block.length >= CODE_LINES) {
      chunks.push(block.join('\n').trim());
      block = [];
    }
  }
  if (block.length > 0) chunks.push(block.join('\n').trim());

  return chunks.filter(c => c.length > 40);
}

function splitSql(text: string): string[] {
  return text
    .split(';')
    .map(s => s.trim())
    .filter(s => s.length > 20)
    .map(s => s + ';');
}

function splitYaml(text: string): string[] {
  if (text.length < CHAR_LIMIT) return [text];

  // Split on YAML document separators or top-level keys
  const sections = text.split(/^(?=\w)/m);
  const chunks: string[] = [];

  for (const section of sections) {
    if (section.length <= CHAR_LIMIT) {
      if (section.trim()) chunks.push(section.trim());
    } else {
      let offset = 0;
      while (offset < section.length) {
        chunks.push(section.slice(offset, offset + CHAR_LIMIT).trim());
        offset += CHAR_LIMIT;
      }
    }
  }

  return chunks.filter(c => c.length > 20);
}

// ──────────────────────────────────────────────────────────────────────────────
// Public API
// ──────────────────────────────────────────────────────────────────────────────

export function chunkArtifact(artifact: RawArtifact): Chunk[] {
  const text = artifact.content.trim();
  if (!text) return [];

  let rawChunks: string[];

  switch (artifact.sourceType) {
    case 'platform-doc':
      rawChunks = splitMarkdown(text); break;
    case 'evalos-domain':
      rawChunks = splitSql(text); break;
    case 'platform-code':
      // YAML/SQL files → specialised splitters; everything else → code lines
      if (artifact.filePath.endsWith('.yaml') || artifact.filePath.endsWith('.yml')) {
        rawChunks = splitYaml(text);
      } else if (artifact.filePath.endsWith('.sql')) {
        rawChunks = splitSql(text);
      } else {
        rawChunks = splitCode(text);
      }
      break;
    default:
      rawChunks = text.length < CHAR_LIMIT ? [text] : splitMarkdown(text);
  }

  const total    = rawChunks.length;
  const roleTags = inferRoleTags(artifact, text);

  return rawChunks.map((doc, idx): Chunk => ({
    id:       chunkId(artifact.filePath, idx),
    document: doc,
    metadata: {
      source:       artifact.source,
      source_type:  artifact.sourceType,
      role_tags:    roleTags,
      file_path:    artifact.filePath,
      chunk_index:  idx,
      total_chunks: total,
      title:        artifact.title,
    },
  }));
}

/** Chunk multiple artifacts, deduplicating by chunk ID. */
export function chunkAll(artifacts: RawArtifact[]): Chunk[] {
  const seen  = new Set<string>();
  const result: Chunk[] = [];

  for (const artifact of artifacts) {
    for (const chunk of chunkArtifact(artifact)) {
      if (!seen.has(chunk.id)) {
        seen.add(chunk.id);
        result.push(chunk);
      }
    }
  }

  return result;
}
