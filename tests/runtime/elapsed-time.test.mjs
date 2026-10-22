import assert from "node:assert/strict";
import test from "node:test";
import {
  ago,
  shortAgo,
  clockValue,
  tickClock,
} from "../../browser/runtime/presence.js";
import { watchProjection } from "../../browser/runtime/projection-watch.js";

const before = (ms) => new Date(Date.now() - ms).toISOString();
const MINUTE = 60 * 1000;

test("a watcher another stops during a tick stays stopped", async () => {
  const owner = document.createElement("div");
  document.body.append(owner);
  let clock = 0;
  const calls = { first: 0, second: 0 };
  let second;
  const first = watchProjection(owner, () => {
    calls.first += 1;
    clockValue(() => clock);
    if (calls.first > 1) second();
  });
  second = watchProjection(owner, () => {
    calls.second += 1;
    clockValue(() => clock);
  });
  await Promise.resolve();
  for (let round = 0; round < 2; round += 1) {
    clock += 1;
    await tickClock((message) => {
      throw new Error(message);
    });
    await Promise.resolve();
  }
  assert.deepEqual(calls, { first: 3, second: 1 });
  first();
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
