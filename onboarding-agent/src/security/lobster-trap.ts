/**
 * Lobster Trap — Prompt Injection Firewall
 * TypeScript port of platform/admissions/admissions_agent.py TRAP_PATTERNS.
 * Runs pre-LLM on every user-supplied input string before any model call.
 */

const TRAP_PATTERNS: RegExp[] = [
  /ignore\s+(all\s+)?previous\s+instructions?/i,
  /you\s+are\s+now\s+(?!an?\s+(onboarding|platform|i3))/i,
  /act\s+as\s+(?!an?\s+(onboarding|platform|i3))/i,
  /system\s*(prompt|message|instruction)/i,
  /jailbreak/i,
  /DAN\s+mode/i,
  /<\s*(script|img|iframe|svg)/i,
  /(drop|delete|truncate)\s+table/i,
  /SELECT\s+.+FROM\s+/i,
  /prompt\s+injection/i,
  /disregard\s+(all\s+)?previous/i,
  /\bexfiltrate\b/i,
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
