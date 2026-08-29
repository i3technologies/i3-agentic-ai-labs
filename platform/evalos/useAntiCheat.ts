/**
 * useAntiCheat — React hook for EvalOS anti-cheat event capture
 *
 * Tracks: focus_lost, clipboard, fullscreen_exit, tab_switch, paste_event
 * Reports events to /api/exam/[attemptId]/anticheat every 30s and on unmount.
 *
 * Usage:
 *   const { violations } = useAntiCheat({ attemptId, enabled: true });
 */

import { useCallback, useEffect, useRef, useState } from "react";

export type AntiCheatEventType =
  | "focus_lost"
  | "clipboard"
  | "fullscreen_exit"
  | "tab_switch"
  | "paste_event";

interface AntiCheatEvent {
  eventType: AntiCheatEventType;
  timestamp: number;
  metadata?: Record<string, unknown>;
}

interface UseAntiCheatOptions {
  attemptId: string;
  enabled?: boolean;
  reportIntervalMs?: number;
}

interface UseAntiCheatResult {
  violations: AntiCheatEvent[];
  violationCount: number;
}

async function reportEvents(
  attemptId: string,
  events: AntiCheatEvent[]
): Promise<void> {
  if (!events.length) return;
  try {
    await fetch(`/api/exam/${attemptId}/anticheat/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events }),
      keepalive: true,
    });
  } catch {
    // Non-fatal — events are stored locally; server sync best-effort
  }
}

export function useAntiCheat({
  attemptId,
  enabled = true,
  reportIntervalMs = 30_000,
}: UseAntiCheatOptions): UseAntiCheatResult {
  const [violations, setViolations] = useState<AntiCheatEvent[]>([]);
  const pendingRef = useRef<AntiCheatEvent[]>([]);

  const record = useCallback((event: AntiCheatEvent) => {
    setViolations((prev) => [...prev, event]);
    pendingRef.current = [...pendingRef.current, event];
  }, []);

  useEffect(() => {
    if (!enabled) return;

    // ── Focus / Tab visibility ───────────────────────────────
    const handleVisibilityChange = () => {
      if (document.hidden) {
        record({
          eventType: "tab_switch",
          timestamp: Date.now(),
          metadata: { hidden: true },
        });
      }
    };

    const handleBlur = () => {
      record({ eventType: "focus_lost", timestamp: Date.now() });
    };

    // ── Clipboard intercept ──────────────────────────────────
    const handleCopy = (e: ClipboardEvent) => {
      e.preventDefault();
      record({
        eventType: "clipboard",
        timestamp: Date.now(),
        metadata: { action: "copy" },
      });
    };

    const handleCut = (e: ClipboardEvent) => {
      e.preventDefault();
      record({
        eventType: "clipboard",
        timestamp: Date.now(),
        metadata: { action: "cut" },
      });
    };

    const handlePaste = (e: ClipboardEvent) => {
      e.preventDefault();
      record({
        eventType: "paste_event",
        timestamp: Date.now(),
        metadata: { action: "paste" },
      });
    };

    // ── Keyboard shortcuts ───────────────────────────────────
    const handleKeyDown = (e: KeyboardEvent) => {
      // Block Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+A (select all)
      if (e.ctrlKey && ["c", "v", "x", "a"].includes(e.key.toLowerCase())) {
        e.preventDefault();
        record({
          eventType: "clipboard",
          timestamp: Date.now(),
          metadata: { key: `Ctrl+${e.key.toUpperCase()}` },
        });
      }
    };

    // ── Fullscreen exit ──────────────────────────────────────
    const handleFullscreenChange = () => {
      if (!document.fullscreenElement) {
        record({ eventType: "fullscreen_exit", timestamp: Date.now() });
      }
    };

    // ── Right-click intercept ────────────────────────────────
    const handleContextMenu = (e: MouseEvent) => {
      e.preventDefault();
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("blur", handleBlur);
    document.addEventListener("copy", handleCopy as EventListener);
    document.addEventListener("cut", handleCut as EventListener);
    document.addEventListener("paste", handlePaste as EventListener);
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    document.addEventListener("contextmenu", handleContextMenu);

    // ── Periodic flush ───────────────────────────────────────
    const intervalId = setInterval(() => {
      const toSend = pendingRef.current.splice(0);
      reportEvents(attemptId, toSend);
    }, reportIntervalMs);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("blur", handleBlur);
      document.removeEventListener("copy", handleCopy as EventListener);
      document.removeEventListener("cut", handleCut as EventListener);
      document.removeEventListener("paste", handlePaste as EventListener);
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      document.removeEventListener("contextmenu", handleContextMenu);
      clearInterval(intervalId);
      // Final flush on unmount
      const remaining = pendingRef.current.splice(0);
      reportEvents(attemptId, remaining);
    };
  }, [attemptId, enabled, record, reportIntervalMs]);

  return {
    violations,
    violationCount: violations.length,
  };
}
