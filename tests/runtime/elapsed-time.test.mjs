import assert from "node:assert/strict";
import process from "node:process";
import test from "node:test";
import {
  ago,
  shortAgo,
  atClock,
  clockTime,
  clockValue,
  saidAt,
  tickClock,
} from "../../browser/runtime/state/presence.js";
import { noChange } from "/vendor/lit.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";

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
  // Ninety minutes rounds to two hours in both, where a floor put "1h" beside "2h ago";
  // and the rounded figure picks the unit, so the minute before an hour reads "1h",
  // where it read "60m".
  for (const [elapsed, compact] of [
    [10 * 1000, "now"],
    [5 * MINUTE, "5m"],
    [59 * MINUTE + 40 * 1000, "1h"],
    [90 * MINUTE, "2h"],
    [89 * MINUTE, "1h"],
    [23 * 60 * MINUTE + 40 * MINUTE, "1d"],
    [36 * 60 * MINUTE, "2d"],
  ]) {
    const ts = before(elapsed);
    assert.equal(shortAgo(ts), compact);
    assert.equal(ago(ts), compact === "now" ? "just now" : `${compact} ago`);
  }
  // A timestamp that names no moment has no age.
  for (const ts of ["", null, "yesterday", "1795543200000"]) {
    assert.equal(ago(ts), "");
    assert.equal(shortAgo(ts), "");
  }
});

// Dates and times read as the reader's platform writes them, so these cases hold where
// the platform reads American English, as Node does under an en_US locale.
const american = Intl.DateTimeFormat().resolvedOptions().locale === "en-US";
const platform = { skip: !american && "the platform doesn't read American English" };

test("an age's preview says its clock time in the reader's own zone", platform, (t) => {
  const zone = process.env.TZ;
  t.after(() => {
    process.env.TZ = zone;
  });
  process.env.TZ = "America/Los_Angeles";
  assert.equal(clockTime("2026-08-15T21:02:00Z"), "Sat, Aug 15, 2026, 2:02 PM PT");
  // The zone as the platform names it where it has no initials.
  process.env.TZ = "Europe/London";
  assert.equal(
    clockTime("2026-08-15T08:05:00Z"),
    "Sat, Aug 15, 2026, 9:05 AM United Kingdom Time",
  );
  assert.equal(clockTime(null), "");
});

test(
  "a message says how long ago within the hour, then its time and day",
  platform,
  (t) => {
    const zone = process.env.TZ;
    t.after(() => {
      process.env.TZ = zone;
    });
    process.env.TZ = "America/Los_Angeles";
    // Sunday 15 November 2026, 7:20 PM in Los Angeles.
    const said = (/** @type {string} */ ts) =>
      atClock(Date.parse("2026-11-16T03:20:00Z"), () => saidAt(ts));
    assert.deepEqual(said("2026-11-16T03:19:40Z"), { day: "", time: "just now" });
    assert.deepEqual(said("2026-11-16T03:08:00Z"), { day: "", time: "12m ago" });
    assert.deepEqual(said("2026-11-16T02:21:00Z"), { day: "", time: "59m ago" });
    // From the hour, an age would round, so the message says its time.
    assert.deepEqual(said("2026-11-16T02:20:00Z"), { day: "", time: "6:20 PM" });
    assert.deepEqual(said("2026-11-14T23:35:00Z"), {
      day: "Yesterday",
      time: "3:35 PM",
    });
    // The day is the reader's: 07:59 UTC on the 15th is still the 14th in Los Angeles.
    assert.deepEqual(said("2026-11-15T07:59:00Z"), {
      day: "Yesterday",
      time: "11:59 PM",
    });
    assert.deepEqual(said("2026-11-13T23:29:00Z"), { day: "Nov 13", time: "3:29 PM" });
    assert.deepEqual(said("2025-11-15T23:29:00Z"), {
      day: "Nov 15, 2025",
      time: "3:29 PM",
    });
    // A moment the browser's clock puts ahead of the server's is just now.
    assert.deepEqual(said("2026-11-16T03:21:00Z"), { day: "", time: "just now" });
    assert.equal(said(""), null);
  },
);
