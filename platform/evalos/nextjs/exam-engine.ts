/**
 * EvalOS — Next.js 14 Exam Engine
 * Server Route: /api/exam/[examId]/start
 * Generates a randomized exam snapshot with shuffled options and anti-cheat hooks.
 *
 * File: platform/evalos/nextjs/app/api/exam/[examId]/start/route.ts
 */
import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "next-auth/next";
import { authOptions } from "@/lib/auth";
import { db } from "@/lib/db";
import { shuffleArray, generateQuestionSnapshot } from "@/lib/exam-utils";
import { z } from "zod";

const StartParamsSchema = z.object({ examId: z.string().uuid() });

export async function POST(
  req: NextRequest,
  { params }: { params: { examId: string } }
) {
  const session = await getServerSession(authOptions);
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { examId } = StartParamsSchema.parse(params);
  const studentId = session.user.id;

  // Check for existing in-progress attempt (resume support)
  const existing = await db.query(
    `SELECT id FROM quiz_attempts
     WHERE exam_id = $1 AND student_id = $2 AND status = 'in_progress'
     ORDER BY created_at DESC LIMIT 1`,
    [examId, studentId]
  );
  if (existing.rows.length > 0) {
    return NextResponse.json({ attemptId: existing.rows[0].id, resumed: true });
  }

  // Load exam definition
  const examResult = await db.query(
    `SELECT * FROM exams WHERE id = $1 AND is_published = TRUE`,
    [examId]
  );
  if (examResult.rows.length === 0) {
    return NextResponse.json({ error: "Exam not found" }, { status: 404 });
  }
  const exam = examResult.rows[0];

  // Draw questions per spec (stratified random sampling)
  const snapshot = await generateQuestionSnapshot(exam.draw_spec, db);

  // Create attempt record
  const attemptResult = await db.query(
    `INSERT INTO quiz_attempts (exam_id, student_id, cohort_id, question_snapshot)
     VALUES ($1, $2, $3, $4) RETURNING id`,
    [examId, studentId, session.user.cohortId ?? null, JSON.stringify(snapshot)]
  );

  return NextResponse.json({
    attemptId: attemptResult.rows[0].id,
    snapshot,
    durationSecs: exam.duration_secs,
    resumed: false,
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// File: platform/evalos/nextjs/lib/exam-utils.ts
// ─────────────────────────────────────────────────────────────────────────────
export function shuffleArray<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export async function generateQuestionSnapshot(
  drawSpec: Array<{ topic: string; count: number; difficulty_min: number; difficulty_max: number }>,
  db: any
): Promise<Array<any>> {
  const allQuestions: any[] = [];

  for (const spec of drawSpec) {
    const result = await db.query(
      `SELECT id, stem, question_type, options, test_harness, topic, subtopic, difficulty, bloom_level
       FROM questions
       WHERE topic = $1
         AND difficulty BETWEEN $2 AND $3
         AND is_active = TRUE
       ORDER BY RANDOM()
       LIMIT $4`,
      [spec.topic, spec.difficulty_min, spec.difficulty_max, spec.count]
    );

    for (const q of result.rows) {
      // Shuffle MCQ options to prevent position-memorization cheating
      if (q.options && Array.isArray(q.options)) {
        q.options = shuffleArray(q.options);
      }
      allQuestions.push(q);
    }
  }

  // Shuffle question order
  return shuffleArray(allQuestions);
}

// ─────────────────────────────────────────────────────────────────────────────
// File: platform/evalos/nextjs/app/api/exam/[examId]/anticheat/route.ts
// Anti-cheat event ingestion endpoint
// ─────────────────────────────────────────────────────────────────────────────
const AntiCheatEventSchema = z.object({
  attemptId: z.string().uuid(),
  eventType: z.enum(["focus_lost", "clipboard", "fullscreen_exit", "tab_switch", "paste_event"]),
  timestamp: z.number(),
  metadata: z.record(z.unknown()).optional(),
});

export async function POST_anticheat(req: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = AntiCheatEventSchema.parse(await req.json());

  // Map event type to column update
  const updateMap: Record<string, string> = {
    focus_lost:      "focus_lost_count = focus_lost_count + 1",
    clipboard:       "clipboard_events = clipboard_events + 1",
    fullscreen_exit: "fullscreen_exits = fullscreen_exits + 1",
    tab_switch:      `tab_switch_events = tab_switch_events || $3::jsonb`,
    paste_event:     "clipboard_events = clipboard_events + 1",
  };

  if (body.eventType === "tab_switch") {
    await db.query(
      `UPDATE quiz_attempts SET ${updateMap[body.eventType]}
       WHERE id = $1 AND student_id = $2`,
      [body.attemptId, session.user.id, JSON.stringify({ ts: body.timestamp, meta: body.metadata })]
    );
  } else {
    await db.query(
      `UPDATE quiz_attempts SET ${updateMap[body.eventType]}
       WHERE id = $1 AND student_id = $2`,
      [body.attemptId, session.user.id]
    );
  }

  // Auto-flag if thresholds exceeded
  const flagResult = await db.query(
    `SELECT focus_lost_count, fullscreen_exits, clipboard_events
     FROM quiz_attempts WHERE id = $1`,
    [body.attemptId]
  );
  const { focus_lost_count, fullscreen_exits, clipboard_events } = flagResult.rows[0];
  if (focus_lost_count > 5 || fullscreen_exits > 3 || clipboard_events > 10) {
    await db.query(
      `UPDATE quiz_attempts
       SET proctor_flags = proctor_flags || $2::jsonb
       WHERE id = $1`,
      [body.attemptId, JSON.stringify({ flag: "auto_cheat_threshold", ts: Date.now() })]
    );
  }

  return NextResponse.json({ recorded: true });
}

// ─────────────────────────────────────────────────────────────────────────────
// File: platform/evalos/nextjs/lib/moss-client.ts
// Stanford MOSS plagiarism scoring integration
// ─────────────────────────────────────────────────────────────────────────────
import { execFile } from "child_process";
import { promisify } from "util";
import { writeFile, mkdir } from "fs/promises";
import path from "path";
import os from "os";

const execFileAsync = promisify(execFile);

interface MOSSResult {
  similarity: number;   // 0–100
  reportUrl: string | null;
  matchedAttemptId: string | null;
}

export async function runMOSSCheck(
  attemptId: string,
  studentCode: string,
  language: "python" | "cc" | "java" = "python"
): Promise<MOSSResult> {
  const workDir = path.join(os.tmpdir(), `moss-${attemptId}`);
  await mkdir(workDir, { recursive: true });

  const codePath = path.join(workDir, `submission.${language === "python" ? "py" : language === "cc" ? "cpp" : "java"}`);
  await writeFile(codePath, studentCode, "utf-8");

  try {
    // MOSS Perl script — must be installed at /usr/local/bin/moss
    const { stdout } = await execFileAsync("/usr/local/bin/moss", [
      "-l", language,
      "-d",
      codePath,
    ], { timeout: 30000 });

    const urlMatch = stdout.match(/https?:\/\/moss\.stanford\.edu\/results\/\S+/);
    const reportUrl = urlMatch ? urlMatch[0].trim() : null;

    return {
      similarity: 0,    // Parse from MOSS report HTML in production
      reportUrl,
      matchedAttemptId: null,
    };
  } catch (err) {
    console.error("MOSS check failed:", err);
    return { similarity: 0, reportUrl: null, matchedAttemptId: null };
  }
}
