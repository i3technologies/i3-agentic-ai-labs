/**
 * Platform Ingestion — reads the i3 platform/ directory.
 *
 * The platform/ repo IS the seed repo. It contains:
 *   - platform/docs/          → architecture docs, RUNBOOK.md
 *   - platform/**\/*.yaml     → Kubernetes manifests
 *   - platform/**\/*.py       → Python agent source (admissions, evalos)
 *   - platform/**\/*.ts       → TypeScript source (exam-engine)
 *   - platform/**\/*.tf       → Terraform modules
 *   - platform/**\/*.md       → Runbooks and guides
 *
 * Usage:
 *   ts-node src/ingestion/platform.ts
 *   npm run ingest
 */

import * as fs from "fs";
import * as path from "path";
import "dotenv/config";
import { RawArtifact } from "./types.js";

// File extensions to ingest
const INGEST_EXTENSIONS = new Set([
  ".md", ".yaml", ".yml", ".py", ".ts", ".tf", ".json", ".sql",
]);

// Paths to skip entirely
const SKIP_DIRS = new Set([
  "node_modules", ".terraform", ".git", "dist", "__pycache__",
  "solution-01", "solution-02", "solution-03", "solution-04",
  "solution-05", "solution-06", "solution-07", "solution-08",
]);

// Max file size to ingest (bytes) — skip large binary/generated files
const MAX_FILE_BYTES = 256_000;

function classifySource(filePath: string): RawArtifact["source"] {
  const lower = filePath.toLowerCase();
  if (lower.endsWith(".md")) return "platform-doc";
  if (lower.includes("docs/") || lower.includes("RUNBOOK")) return "platform-doc";
  if (lower.includes("adr") || lower.includes("decisions")) return "adr";
  return "platform-code";
}

function walkDir(dir: string): string[] {
  const results: string[] = [];
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return results;
  }
  for (const entry of entries) {
    if (SKIP_DIRS.has(entry.name)) continue;
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...walkDir(fullPath));
    } else if (entry.isFile()) {
      const ext = path.extname(entry.name).toLowerCase();
      if (INGEST_EXTENSIONS.has(ext)) {
        results.push(fullPath);
      }
    }
  }
  return results;
}

export async function ingestPlatform(
  platformPath: string = process.env.PLATFORM_REPO_PATH ?? "../platform"
): Promise<RawArtifact[]> {
  const resolvedPath = path.resolve(platformPath);
  console.log(`[platform-ingest] Scanning: ${resolvedPath}`);

  const files = walkDir(resolvedPath);
  const artifacts: RawArtifact[] = [];

  for (const filePath of files) {
    try {
      const stat = fs.statSync(filePath);
      if (stat.size > MAX_FILE_BYTES) {
        console.log(`[platform-ingest] Skip (too large): ${filePath}`);
        continue;
      }
      const content = fs.readFileSync(filePath, "utf-8");
      const relPath = path.relative(resolvedPath, filePath);

      const src = classifySource(relPath);
      artifacts.push({
        source:     src,
        sourceType: src,
        path:       relPath,
        filePath:   relPath,
        content,
        updatedAt: stat.mtime.toISOString(),
        title:     path.basename(relPath),
        metadata: {
          module: relPath.split(path.sep)[0] ?? "root",
        },
      });
    } catch {
      // Skip unreadable files silently
    }
  }

  const bySource = artifacts.reduce<Record<string, number>>((acc, a) => {
    acc[a.source] = (acc[a.source] ?? 0) + 1;
    return acc;
  }, {});

  console.log("[platform-ingest] Artifact counts by source:");
  for (const [src, count] of Object.entries(bySource)) {
    console.log(`  ${src}: ${count}`);
  }

  return artifacts;
}

// ── CLI entry-point ──────────────────────────────────────────────────────────
if (require.main === module) {
  ingestPlatform()
    .then((arts) =>
      console.log(`[platform-ingest] Total artifacts: ${arts.length}`)
    )
    .catch(console.error);
}
