/**
 * hc7-prompt-guard.mjs — UserPromptSubmit hook
 *
 * Blocks any prompt that attempts to introduce DEV_BYPASS_AUTH=true
 * into the codebase (HC-7 enforcement at the prompt layer).
 *
 * Input:  JSON on stdin with { prompt, session_id, cwd, hook_event_name }
 * Output: Exit 2 + stderr message to block; Exit 0 to allow.
 *
 * Only exit code 2 blocks the prompt. Any other exit allows it through.
 */

let raw = "";
for await (const chunk of process.stdin) raw += chunk;

let input;
try {
  input = JSON.parse(raw);
} catch {
  // Cannot parse input — fail open (allow prompt)
  process.exit(0);
}

const prompt = String(input.prompt ?? "");

// HC-7: Block attempts to write DEV_BYPASS_AUTH=true
const forbidden = [
  /DEV_BYPASS_AUTH\s*=\s*true/i,
  /bypass.{0,20}auth/i,
];

for (const pattern of forbidden) {
  if (pattern.test(prompt)) {
    process.stderr.write(
      `[HC-7] Prompt blocked: contains a forbidden auth bypass pattern (DEV_BYPASS_AUTH=true). ` +
      `This violates Hard Constraint HC-7. Remove the bypass before proceeding.`
    );
    process.exitCode = 2;
    break;
  }
}
