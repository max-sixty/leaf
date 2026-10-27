/* Later's times and words on the user's clock (obligations/later-model.js), read in one
   zone with daylight saving, so a Sunday, the evening cutoff and a change of clocks
   each land where the user expects. */
import assert from "node:assert/strict";
import process from "node:process";
import test from "node:test";
import {
  laterTimes,
  setAside,
  untilWords,
  withoutLaters,
} from "../../browser/runtime/obligations/later-model.js";

// Node reads the zone afresh when TZ changes, and nothing here has read a date yet.
process.env.TZ = "America/Los_Angeles";

const local = (text) => new Date(text);
const labels = (now) => laterTimes(now).map(({ label }) => label);
const instants = (now) =>
  Object.fromEntries(
    laterTimes(now).map(({ label, until }) => [label, until.getTime()]),
  );

test("this evening is offered until five, and Monday unless it is tomorrow", () => {
  // A Wednesday afternoon.
  assert.deepEqual(labels(local("2026-10-28T16:59:00")), [
    "In an hour",
    "This evening, 6:00 PM",
    "Tomorrow, 9:00 AM",
    "Monday, 9:00 AM",
  ]);
  assert.deepEqual(labels(local("2026-10-28T17:00:00")), [
    "In an hour",
    "Tomorrow, 9:00 AM",
    "Monday, 9:00 AM",
  ]);
  // A Sunday: tomorrow is Monday, offered once.
  assert.deepEqual(labels(local("2026-11-08T10:00:00")), [
    "In an hour",
    "This evening, 6:00 PM",
    "Tomorrow, 9:00 AM",
  ]);
});

test("tomorrow at nine keeps the wall clock across a change of daylight saving", () => {
  // Clocks go back at 2:00 on Sunday 1 November 2026.
  const at = instants(local("2026-10-31T20:00:00"));
  assert.equal(at["Tomorrow, 9:00 AM"], local("2026-11-01T09:00:00").getTime());
  assert.equal(new Date(at["Tomorrow, 9:00 AM"]).getHours(), 9);
  // Just before midnight, tomorrow is the next calendar day, not the one after.
  const late = instants(local("2026-10-28T23:59:00"));
  assert.equal(late["Tomorrow, 9:00 AM"], local("2026-10-29T09:00:00").getTime());
});

test("a Later's time is said from now", () => {
  const now = local("2026-10-31T20:00:00");
  assert.equal(
    untilWords(local("2026-10-31T22:30:00").toISOString(), now),
    "Back at 10:30 PM",
  );
  assert.equal(
    untilWords(local("2026-11-01T09:00:00").toISOString(), now),
    "Back tomorrow at 9:00 AM",
  );
  assert.equal(
    untilWords(local("2026-11-02T09:00:00").toISOString(), now),
    "Back Monday at 9:00 AM",
  );
  assert.equal(
    untilWords(local("2026-11-20T09:00:00").toISOString(), now),
    "Back Nov 20 at 9:00 AM",
  );
});

test("a record is set aside while its Later stands, and an undo drops it from the chain", () => {
  const first = {
    event: { id: "a" },
    until: "x",
    after: null,
    returned: false,
    beneath: null,
  };
  const second = { ...first, event: { id: "b" }, beneath: first };
  assert.equal(setAside({ status: "open", next_actor: null, later: second }), true);
  assert.equal(
    setAside({
      status: "open",
      next_actor: null,
      later: { ...second, returned: true },
    }),
    false,
  );
  assert.equal(
    setAside({ status: "answered", next_actor: null, later: second }),
    false,
  );
  assert.deepEqual(withoutLaters(second, new Set(["b"])), first);
  assert.equal(withoutLaters(second, new Set(["a", "b"])), null);
  assert.deepEqual(withoutLaters(second, new Set(["a"])), { ...second, beneath: null });
});
