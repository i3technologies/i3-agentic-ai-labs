/**
 * Shared RawArtifact type used across all ingestion connectors.
 * source labels are used for metadata in ChromaDB and for subagent routing.
 */
export type ArtifactSourceType =
  | "platform-doc"    // platform/docs/ markdown files + RUNBOOK.md
  | "platform-code"   // .py, .ts, .yaml, .tf source files
  | "curriculum"      // Directus CMS programme_guides PDFs
  | "evalos-domain"   // EvalOS exam domain weights
  | "readme"          // repo README
  | "adr"             // Architecture Decision Records
  | "issue"           // GitHub closed issues
  | "wiki";           // Confluence / other wiki pages

export interface RawArtifact {
  /** Original source category */
  source:     ArtifactSourceType;
  /** Alias for source — maps to ChromaDB source_type metadata field */
  sourceType: ArtifactSourceType;
  /** Relative file path (used by verify.ts to confirm existence) */
  path:       string;
  /** Alias for path — consumed by chunker and retriever */
  filePath:   string;
  content:    string;
  updatedAt:  string;
  /** Optional human-readable title (used in chunk metadata and Markdown render) */
  title?:     string;
  metadata?:  Record<string, string>;
}

/**
 * Convenience builder — ensures both aliases are always in sync.
 */
export function makeArtifact(
  fields: Omit<RawArtifact, 'sourceType' | 'filePath'> & { sourceType?: ArtifactSourceType; filePath?: string }
): RawArtifact {
  return {
    ...fields,
    sourceType: fields.sourceType ?? fields.source,
    filePath:   fields.filePath   ?? fields.path,
  };
}
