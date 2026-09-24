/**
 * session-context.mjs — SessionStart hook
 *
 * Injects the current git branch and last commit into Bob's context
 * on every new task startup so Bob always knows which phase branch
 * it is working on.
 *
 * Output goes to stdout → added to Bob's model context (SessionStart).
 * Exit 0 always — this hook is informational only.
 */

import { spawnSync } from "node:child_process";

const branch = spawnSync("git", ["branch", "--show-current"], { encoding: "utf8" }).stdout.trim();
const commit = spawnSync("git", ["log", "-1", "--oneline"], { encoding: "utf8" }).stdout.trim();
const status = spawnSync("git", ["status", "--short"], { encoding: "utf8" }).stdout.trim();
const modifiedCount = status ? status.split("\n").length : 0;

process.stdout.write(
  `--- i3 Platform Git Context ---\n` +
  `Branch: ${branch || "(unknown)"}\n` +
  `Last commit: ${commit || "(none)"}\n` +
  `Modified files: ${modifiedCount}\n` +
  `-------------------------------\n`
);
