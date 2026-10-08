import assert from "node:assert/strict";
import test from "node:test";
import {
  createPresentationCoordinator,
  createPresentationSchedule,
} from "../../skills/leaf/assets/vendor/browser-runtime.js";
import {
  ago,
  shortAgo,
  clocked,
  clockValue,
  tickClock,
} from "../../skills/leaf/assets/runtime/presence.js";

const before = (ms) => new Date(Date.now() - ms).toISOString();
const MINUTE = 60 * 1000;

test("a clock invalidation leaves an unrecovered paint failure with its presenter", async () => {
  const owner = document.createElement("div");
  document.body.append(owner);
  const reports = [];
  let clock = 0;
  let claimed;
  const coordinator = createPresentationCoordinator({
    reportFailure: (error) => reports.push(error.message),
  });
  const schedule = createPresentationSchedule((callback) => callback);
  const publication = coordinator.begin({}, 0);
  const paint = clocked(
    owner,
    () => {
      clockValue(() => clock);
      if (clock) throw new Error("paint and retention both failed");
      return clock;
    },
    () => (claimed = presenter.sync(clock)),
  );
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("queue", owner),
    paint,
    failSoft: (error) => {
      throw error;
    },
  });
  const initial = presenter.sync(0);
  coordinator.seal(publication);
  await initial;
  clock = 1;
  await tickClock((message) => reports.push(message));
  await assert.rejects(claimed, /paint and retention both failed/);
  assert.deepEqual(reports, ["paint and retention both failed"]);
  assert.deepEqual(coordinator.read().pending, ["queue"]);
  paint.stop();
  owner.remove();
});

test("clock invalidation retains dependencies until a deferred paint replaces them", async () => {
  const owner = document.createElement("div");
  document.body.append(owner);
  let clock = 0;
  let invalidations = 0;
  const shown = [];
  const paint = clocked(
    owner,
    () => shown.push(clockValue(() => Math.floor(clock / 10))),
    () => invalidations++,
  );
  const tick = () =>
    tickClock((message) => {
      throw new Error(message);
    });
  paint();
  clock = 9;
  await tick();
  assert.equal(invalidations, 0);
  clock = 10;
  await tick();
  clock = 20;
  await tick();
  assert.equal(invalidations, 2);
  assert.deepEqual(shown, [0], "claiming work must not paint it");
  paint();
  await tick();
  assert.equal(invalidations, 2, "the actual paint replaces its prior readings");
  clock = 30;
  await tick();
  assert.equal(invalidations, 3);
  paint.stop();
  clock = 40;
  await tick();
  assert.equal(invalidations, 3);
  owner.remove();
});

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
