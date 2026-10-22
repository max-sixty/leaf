import assert from "node:assert/strict";
import test from "node:test";
import {
  ago,
  shortAgo,
  clockValue,
  tickClock,
} from "../../browser/runtime/presence.js";
import { LeafElement, noChange } from "/runtime/widget-api.js";

const before = (ms) => new Date(Date.now() - ms).toISOString();
const MINUTE = 60 * 1000;

test("an element removed by another clock render stays disconnected", async () => {
  let clock = 0;
  const calls = { first: 0, second: 0 };
  let second;
  customElements.define(
    "leaf-first-clock",
    class extends LeafElement {
      render() {
        calls.first += 1;
        clockValue(() => clock);
        if (calls.first > 1) second.remove();
        return noChange;
      }
    },
  );
  customElements.define(
    "leaf-second-clock",
    class extends LeafElement {
      render() {
        calls.second += 1;
        clockValue(() => clock);
        return noChange;
      }
    },
  );
  const first = document.createElement("leaf-first-clock");
  second = document.createElement("leaf-second-clock");
  document.body.append(first, second);
  const settle = async () => {
    await new Promise((resolve) => setTimeout(resolve));
    await first.updateComplete;
  };
  try {
    await settle();
    for (let round = 0; round < 2; round += 1) {
      clock += 1;
      await tickClock((message) => {
        throw new Error(message);
      });
      await settle();
    }
    assert.deepEqual(calls, { first: 3, second: 1 });
  } finally {
    first.remove();
    second.remove();
  }
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
