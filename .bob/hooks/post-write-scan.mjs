/**
 * post-write-scan.mjs — PostToolUse hook
 *
 * Runs a fast credential / bypass-auth scan after every file write
 * (write_file, apply_diff, search_and_replace, insert_content).
 *
 * Findings are written to stdout → added to Bob's context alongside
 * the tool result so Bob can self-correct immediately.
 *
 * Input:  JSON on stdin with { tool_name, tool_input: { path }, tool_response, ... }
 * Output: Exit 0 always (PostToolUse exit 2 is logged but cannot undo a write).
 *         Stdout findings are injected into model context.
 */

import { spawnSync } from "node:child_process";

let raw = "";
for await (const chunk of process.stdin) raw += chunk;

let input;
try {
  input = JSON.parse(raw);
} catch {
  process.exit(0);
}

const filePath = String(input.tool_input?.path ?? "");

// Only scan files with relevant extensions
const SCAN_EXTS = /\.(py|ts|tsx|js|mjs|yaml|yml|json|sh|env|md)$/i;
if (!filePath || !SCAN_EXTS.test(filePath)) {
  process.exit(0);
}

// Patterns to scan for in the written file
const DANGER_PATTERNS = [
  { id: "HC-7",  pattern: "DEV_BYPASS_AUTH=true" },
  { id: "CRED",  pattern: "password" },
  { id: "CRED",  pattern: "api_key" },
  { id: "CRED",  pattern: "secret_key" },
  { id: "HC-6",  pattern: "nationalId" },
  { id: "HC-6",  pattern: "idNumber" },
  { id: "HC-6",  pattern: ".nid" },
];

const findings = [];

for (const { id, pattern } of DANGER_PATTERNS) {
  const result = spawnSync(
    "grep",
    ["-in", "--", pattern, filePath],
    { encoding: "utf8" }
  );
  if (result.status === 0 && result.stdout.trim()) {
    const lines = result.stdout.trim().split("\n").slice(0, 3); // first 3 matches
    for (const line of lines) {
      findings.push(`  [${id}] ${filePath}: ${line}`);
    }
  }
}

if (findings.length > 0) {
  process.stdout.write(
    `⚠️  Post-write scan found ${findings.length} potential issue(s) in ${filePath}:\n` +
    findings.join("\n") + "\n" +
    `Review these findings before proceeding. Use i3-audit mode for a full compliance review.\n`
  );
}

// Always exit 0 — PostToolUse cannot undo the write; we only surface findings.
process.exit(0);
