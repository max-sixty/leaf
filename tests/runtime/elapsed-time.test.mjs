import assert from "node:assert/strict";
import test from "node:test";
import {
  collectReads,
  createPresentationCoordinator,
  createPresentationSchedule,
} from "../../skills/leaf/assets/vendor/browser-runtime.js";
import {
  readApplication,
  readPart,
} from "../../skills/leaf/assets/runtime/semantic-state.js";
import {
  projectionDeferred,
  setProjectionDeferred,
} from "../../skills/leaf/assets/runtime/projection/state.js";
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

test("a clocked paint follows its time and leaves the publication's parts to its caller", async () => {
  const owner = document.createElement("div");
  document.body.append(owner);
  let clock = 0;
  const phase = readPart((root) => root.phase);
  let calls = 0;
  const paint = clocked(owner, (whole) => {
    calls += 1;
    clockValue(() => clock);
    phase();
    // Called by its caller outside any collection, it may read the root whole.
    if (whole) readApplication();
  });
  paint(true);
  const { reads } = collectReads(() => paint(false));
  assert.deepEqual(
    [...reads.keys()].map((reading) => Boolean(reading.outside)),
    [false],
  );
  clock += 1;
  await tickClock((message) => {
    throw new Error(message);
  });
  assert.equal(calls, 3);
  paint.stop();
  owner.remove();
});

test("a paint another stops during a tick stays stopped", async () => {
  const owner = document.createElement("div");
  document.body.append(owner);
  let clock = 0;
  const calls = { first: 0, second: 0 };
  let second;
  const first = clocked(owner, () => {
    calls.first += 1;
    clockValue(() => clock);
    if (calls.first > 1) second.stop();
  });
  second = clocked(owner, () => {
    calls.second += 1;
    clockValue(() => clock);
  });
  first();
  second();
  for (const _ of [1, 2]) {
    clock += 1;
    await tickClock((message) => {
      throw new Error(message);
    });
  }
  assert.deepEqual(calls, { first: 3, second: 1 });
  first.stop();
  owner.remove();
});

test("a clocked paint follows each change of what else it read outside the publication", () => {
  const owner = document.createElement("div");
  document.body.append(owner);
  const shown = [];
  const paint = clocked(owner, () => shown.push(projectionDeferred()));
  paint();
  setProjectionDeferred(true);
  setProjectionDeferred(false);
  assert.deepEqual(shown, [false, true, false]);
  paint.stop();
  owner.remove();
});

test("a clocked paint that moved the time it read paints again at the next tick", async () => {
  const owner = document.createElement("div");
  document.body.append(owner);
  let clock = 0;
  let calls = 0;
  const paint = clocked(owner, () => {
    calls += 1;
    clockValue(() => clock);
    if (calls === 1) clock += 1;
    return calls;
  });
  // Never inside its own paint, so its caller waits on the paint it called.
  assert.equal(paint(), 1);
  await tickClock((message) => {
    throw new Error(message);
  });
  assert.equal(calls, 2);
  paint.stop();
  owner.remove();
});

test("a clocked paint that moves what it follows does not paint again inside itself", () => {
  const owner = document.createElement("div");
  document.body.append(owner);
  let calls = 0;
  const paint = clocked(owner, () => {
    calls += 1;
    projectionDeferred();
    if (calls === 2) setProjectionDeferred(true);
    return calls;
  });
  paint();
  assert.equal(paint(), 2);
  assert.equal(calls, 2);
  // A later round that moves it from what this paint read paints it again.
  setProjectionDeferred(false);
  setProjectionDeferred(true);
  assert.equal(calls, 3);
  paint.stop();
  setProjectionDeferred(false);
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
