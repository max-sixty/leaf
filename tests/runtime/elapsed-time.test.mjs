import assert from "node:assert/strict";
import test from "node:test";
import { ago, shortAgo } from "../../skills/leaf/assets/runtime/presence.js";

const before = (ms) => new Date(Date.now() - ms).toISOString();
const MINUTE = 60 * 1000;

test("the sentence and compact elapsed readings name the same figure", (t) => {
  t.mock.timers.enable({ apis: ["Date"], now: Date.parse("2026-10-03T12:00:00Z") });
  // Ninety minutes rounds to two hours in both, where a floor put "1h" beside "2h ago".
  for (const [elapsed, compact] of [
    [10 * 1000, "now"],
    [5 * MINUTE, "5m"],
    [90 * MINUTE, "2h"],
    [89 * MINUTE, "1h"],
    [36 * 60 * MINUTE, "2d"],
  ]) {
    const ts = before(elapsed);
    assert.equal(shortAgo(ts), compact);
    assert.equal(ago(ts), compact === "now" ? "just now" : `${compact} ago`);
  }
});
