/**
 * Curriculum Ingestion — Directus CMS
 *
 * Pulls the programme_guides collection from Directus CMS
 * (cms.i3technologies.co.ke). These are the PDF programme guides that
 * the Admissions Agent already uses. We ingest them as plain-text content
 * for the onboarding corpus so new students know about fees, schedules,
 * and course structure from Day 1.
 *
 * Documents are uploaded to Directus by instructors and automatically
 * indexed by the existing n8n workflow within 5 minutes.
 * Here we simply fetch the text content that Directus has already extracted.
 */

import "dotenv/config";
import { RawArtifact, makeArtifact } from "./types.js";

interface DirectusItem {
  id: string;
  title?: string;
  description?: string;
  content?: string;  // extracted text from Docling preprocessing
  status: string;
  date_updated?: string;
}

export async function ingestCurriculum(): Promise<RawArtifact[]> {
  const directusUrl = process.env.DIRECTUS_URL ?? "https://cms.i3technologies.co.ke";
  const token = process.env.DIRECTUS_TOKEN;

  if (!token) {
    console.warn("[curriculum-ingest] DIRECTUS_TOKEN not set — skipping curriculum ingestion");
    return [];
  }

  const artifacts: RawArtifact[] = [];

  try {
    const resp = await fetch(
      `${directusUrl}/items/programme_guides?filter[status][_eq]=published&fields=id,title,description,content,date_updated`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      }
    );

    if (!resp.ok) {
      console.warn(`[curriculum-ingest] Directus returned ${resp.status} — skipping`);
      return [];
    }

    const body = (await resp.json()) as { data: DirectusItem[] };

    for (const item of body.data ?? []) {
      if (!item.content) continue;
      artifacts.push(makeArtifact({
        source: "curriculum",
        path: `directus/programme_guides/${item.id}`,
        content: [item.title, item.description, item.content]
          .filter(Boolean)
          .join("\n\n"),
        updatedAt: item.date_updated ?? new Date().toISOString(),
        title: item.title,
        metadata: { title: item.title ?? "Untitled" },
      }));
    }

    console.log(`[curriculum-ingest] Fetched ${artifacts.length} programme guides`);
  } catch (err) {
    console.error("[curriculum-ingest] Error:", err);
  }

  return artifacts;
}
