import assert from "node:assert/strict";
import test from "node:test";
import {
  ago,
  shortAgo,
  clocked,
  clockValue,
  tickClock,
} from "../../skills/leaf/assets/runtime/presence.js";

const before = (ms) => new Date(Date.now() - ms).toISOString();
const MINUTE = 60 * 1000;

test("a paint stopped inside its callback stays off the clock until rendered again", async () => {
  const owner = document.createElement("div");
  document.body.append(owner);
  let clock = 0;
  let calls = 0;
  const paint = clocked(owner, () => {
    calls += 1;
    clockValue(() => clock);
    if (calls === 2) paint.stop();
  });
  paint();
  paint();
  clock += 1;
  await tickClock((message) => {
    throw new Error(message);
  });
  assert.equal(calls, 2);
  paint();
  clock += 1;
  await tickClock((message) => {
    throw new Error(message);
  });
  assert.equal(calls, 4);
  paint.stop();
  owner.remove();
});

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
