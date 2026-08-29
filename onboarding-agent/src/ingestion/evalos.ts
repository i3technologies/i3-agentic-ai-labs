/**
 * EvalOS Domain Ingestion
 *
 * Queries the EvalOS API for the live exam domain distribution.
 * This gives the onboarding agent accurate data about what topics
 * matter most in the IBM C1000-207 certification exam so it can
 * calibrate first-week learning tasks to actual exam weights.
 *
 * EvalOS schema (evalos_db):
 *   questions table → topic, subtopic, difficulty, bloom_level
 *   exams table     → draw_spec [{topic, count, difficulty_min, difficulty_max}]
 */

import "dotenv/config";
import { RawArtifact, makeArtifact } from "./types.js";

export interface ExamDomain {
  topic: string;
  questionCount: number;
  avgDifficulty: number;
  bloomLevels: string[];
}

export async function ingestEvalosDomains(): Promise<RawArtifact[]> {
  const evalosUrl =
    process.env.EVALOS_API_URL ??
    "http://evalos-api.i3-evalos.svc.cluster.local:8080";
  const apiKey = process.env.EVALOS_API_KEY;

  if (!apiKey) {
    console.warn("[evalos-ingest] EVALOS_API_KEY not set — using fallback domain list");
    return buildFallbackDomains();
  }

  try {
    const resp = await fetch(`${evalosUrl}/api/domains/summary`, {
      headers: { Authorization: `Bearer ${apiKey}` },
    });

    if (!resp.ok) {
      console.warn(`[evalos-ingest] EvalOS API returned ${resp.status} — using fallback`);
      return buildFallbackDomains();
    }

    const domains = (await resp.json()) as ExamDomain[];
    return domainsToArtifacts(domains);
  } catch {
    console.warn("[evalos-ingest] EvalOS unreachable — using fallback domain list");
    return buildFallbackDomains();
  }
}

function domainsToArtifacts(domains: ExamDomain[]): RawArtifact[] {
  return domains.map((d) => makeArtifact({
    source: "evalos-domain" as const,
    path: `evalos/domains/${d.topic.replace(/\s+/g, "-").toLowerCase()}`,
    title: d.topic,
    content: [
      `Exam Domain: ${d.topic}`,
      `Question Count: ${d.questionCount}`,
      `Average Difficulty: ${d.avgDifficulty.toFixed(1)}/10`,
      `Bloom Levels Assessed: ${d.bloomLevels.join(", ")}`,
      `Study Recommendation: Focus on this domain — it has ${d.questionCount} questions in the exam bank.`,
    ].join("\n"),
    updatedAt: new Date().toISOString(),
    metadata: {
      topic: d.topic,
      questionCount: String(d.questionCount),
    },
  }));
}

/**
 * Fallback: IBM C1000-207 watsonx Orchestrate AI Engineer exam domains
 * sourced from the official exam blueprint (Master Technical Guide §6.1).
 */
function buildFallbackDomains(): RawArtifact[] {
  const fallback: ExamDomain[] = [
    {
      topic: "Agent Integration and Development",
      questionCount: 23,
      avgDifficulty: 4.2,
      bloomLevels: ["apply", "analyze", "evaluate"],
    },
    {
      topic: "Platform Architecture and Deployment",
      questionCount: 14,
      avgDifficulty: 3.8,
      bloomLevels: ["understand", "apply"],
    },
    {
      topic: "AI Model Management and Serving",
      questionCount: 12,
      avgDifficulty: 4.0,
      bloomLevels: ["apply", "analyze"],
    },
    {
      topic: "Security, Identity, and Governance",
      questionCount: 11,
      avgDifficulty: 3.5,
      bloomLevels: ["understand", "apply"],
    },
  ];

  console.log("[evalos-ingest] Using fallback C1000-207 domain list");
  return domainsToArtifacts(fallback);
}
