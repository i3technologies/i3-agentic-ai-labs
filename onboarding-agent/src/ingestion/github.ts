/**
 * GitHub Ingestion — pulls README, ADRs, and closed issues from a GitHub repo.
 * Used for external repos (not the local platform/ directory).
 * For the i3 platform repo itself, prefer platform.ts (faster, no API quota).
 */

import { Octokit } from "@octokit/rest";
import "dotenv/config";
import { RawArtifact, makeArtifact } from "./types.js";

export async function ingestRepo(
  owner: string,
  repo: string
): Promise<RawArtifact[]> {
  const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });
  const artifacts: RawArtifact[] = [];

  // ── File tree: README + ADRs + docs ─────────────────────────
  const { data: tree } = await octokit.git.getTree({
    owner,
    repo,
    tree_sha: "main",
    recursive: "true",
  });

  const docPaths = tree.tree.filter(
    (e) =>
      e.type === "blob" &&
      e.path != null &&
      /README|ADR|docs?\//i.test(e.path) &&
      /\.(md|txt|rst)$/i.test(e.path)
  );

  for (const entry of docPaths) {
    try {
      const { data: content } = await octokit.repos.getContent({
        owner,
        repo,
        path: entry.path!,
      });
      if ("content" in content && typeof content.content === "string") {
        const decoded = Buffer.from(content.content, "base64").toString("utf-8");
        artifacts.push(makeArtifact({
          source: entry.path!.toLowerCase().includes("adr") ? "adr" : "readme",
          path: entry.path!,
          content: decoded,
          updatedAt: new Date().toISOString(),
        }));
      }
    } catch {
      // Skip files that return 404 or binary content
    }
  }

  // ── Closed issues ─────────────────────────────────────────────
  const issues = await octokit.paginate(octokit.issues.listForRepo, {
    owner,
    repo,
    state: "closed",
    per_page: 100,
  });

  for (const issue of issues) {
    artifacts.push(makeArtifact({
      source: "issue",
      path: `issue-${issue.number}`,
      title: issue.title,
      content: `${issue.title}\n${issue.body ?? ""}`,
      updatedAt: issue.updated_at,
      metadata: {
        labels: issue.labels
          .map((l) => (typeof l === "string" ? l : l.name ?? ""))
          .join(","),
      },
    }));
  }

  const counts = { readme: 0, adr: 0, issue: 0 };
  for (const a of artifacts) {
    if (a.source === "readme") counts.readme++;
    else if (a.source === "adr") counts.adr++;
    else if (a.source === "issue") counts.issue++;
  }
  console.log(
    `[github-ingest] ${owner}/${repo} → README:${counts.readme} ADR:${counts.adr} issues:${counts.issue}`
  );

  return artifacts;
}
