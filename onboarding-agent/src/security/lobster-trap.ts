/**
 * Lobster Trap — Prompt Injection Firewall
 * Canonical 14-pattern set shared across TypeScript and Python runtimes.
 * Runs pre-LLM on every user-supplied input string before any model call.
 *
 * Pattern parity (P2-MED sync):
 *   P01–P12 mirror platform/admissions/admissions_agent.py TRAP_PATTERNS.
 *   P13–P14 (SELECT injection, XSS) are TypeScript extensions also synced
 *   into Python kafka_consumers.py and the MCP server.
 */

const TRAP_PATTERNS: RegExp[] = [
  // P01 — ignore previous instructions
  /ignore\s+(all\s+)?previous\s+instructions?/i,
  // P02 — system prompt override
  /system\s+prompt\s+override/i,
  // P03 — developer mode claim
  /you\s+are\s+now\s+in\s+developer\s+mode/i,
  // P04 — password exfiltration
  /output\s+all\s+passwords/i,
  // P05 — internal logic disclosure
  /reveal\s+internal\s+logic/i,
  // P06 — safety filter bypass
  /bypass\s+safety\s+filter/i,
  // P07 — DAN persona
  /act\s+as\s+DAN/i,
  // P08 — jailbreak keyword
  /jailbreak/i,
  // P09 — SQL destructive DDL
  /(drop|delete|truncate)\s+table/i,
  // P10 — prompt injection label
  /prompt\s+injection/i,
  // P11 — disregard previous
  /disregard\s+(all\s+)?previous/i,
  // P12 — exfiltrate keyword
  /\bexfiltrate\b/i,
  // P13 — SQL SELECT injection (synced from TS; also in Python kafka_consumers.py)
  /SELECT\s+.+FROM\s+/i,
  // P14 — XSS in input (synced from TS; also in Python kafka_consumers.py)
  /<\s*(script|img|iframe|svg)/i,
];

/**
 * Returns the matched pattern source string if injection is detected,
 * or null if the input is clean.
 */
export function lobsterTrap(text: string): string | null {
  for (const pattern of TRAP_PATTERNS) {
    if (pattern.test(text)) {
      return pattern.source;
    }
  }
  return null;
}
