import assert from "node:assert/strict";
import test from "node:test";
import { render } from "/vendor/lit.js";
import { assignRows, elapsed, timeAxis } from "/runtime/lib/time-axis.js";

// What the axis from `from` to `to` draws: each tick's words and each gridline, with
// the share of the axis it stands at and whether it reads back from its time.
const drawn = (from, to, duration, pxPerMs, start) => {
  const axis = timeAxis(from, to, duration, pxPerMs, start);
  const ruler = document.createElement("div");
  const grid = document.createElement("div");
  render(axis.ruler, ruler);
  render(axis.grid, grid);
  const at = (mark) => Number(mark.style.getPropertyValue("--lf-axis-at"));
  const read = (mark) => ({
    at: at(mark),
    flip: mark.hasAttribute("data-lf-flip"),
  });
  return {
    ticks: [...ruler.children],
    major: [...ruler.querySelectorAll("[data-lf-major]")].map((tick) => ({
      label: tick.textContent,
      ...read(tick),
    })),
    lines: [...grid.children].map(read),
  };
};

test("A time axis draws a labeled tick and a gridline at each major time", () => {
  // Two seconds across 400 pixels: a tick each tenth of a second, and each fifth
  // of them major.
  const { ticks, major, lines } = drawn(0, 2000, 2000, 0.2);
  assert.equal(ticks.length, 21);
  assert.ok(ticks.every((tick) => tick.matches(".lf-axis-tick")));
  // The last label has no room to read on from its tick, so it reads back.
  assert.deepEqual(major, [
    { label: "0 s", at: 0, flip: false },
    { label: "0.5 s", at: 0.25, flip: false },
    { label: "1.0 s", at: 0.5, flip: false },
    { label: "1.5 s", at: 0.75, flip: false },
    { label: "2.0 s", at: 1, flip: true },
  ]);
  assert.deepEqual(
    lines,
    major.map(({ at, flip }) => ({ at, flip })),
  );
});

test("A window of a longer axis draws only its own times, at their place on the whole", () => {
  const { major } = drawn(900, 1600, 2000, 0.2);
  assert.deepEqual(
    major.map(({ label, at }) => [label, at]),
    [
      ["1.0 s", 0.5],
      ["1.5 s", 0.75],
    ],
  );
});

test("An axis of hours reads in hours and minutes on the clock's round steps", () => {
  // A session from 12:56 to 17:28, across 800 pixels.
  const duration = (4 * 60 + 32) * 60_000;
  const { major } = drawn(0, duration, duration, 800 / duration);
  assert.deepEqual(
    major.map(({ label }) => label),
    [
      "0 s",
      "30 min",
      "1 h",
      "1 h 30 min",
      "2 h",
      "2 h 30 min",
      "3 h",
      "3 h 30 min",
      "4 h",
      "4 h 30 min",
    ],
  );
});

test("An axis of minutes steps by round spans of seconds", () => {
  // The last label reads back, and the 120 pixels before it hold only one of
  // "2 min 15 s" and "2 min 30 s", so the earlier goes unlabeled.
  const { major } = drawn(0, 150_000, 150_000, 1200 / 150_000);
  assert.deepEqual(
    major.map(({ label }) => label),
    [
      "0 s",
      "15 s",
      "30 s",
      "45 s",
      "1 min",
      "1 min 15 s",
      "1 min 30 s",
      "1 min 45 s",
      "2 min",
      "",
      "2 min 30 s",
    ],
  );
});

test("A label that reads back leaves its predecessor's out where the two would meet", () => {
  // 105 minutes across 588 pixels: a major tick each 84 pixels, and "1 h 30 min"
  // reading on from 504 pixels would run into "1 h 45 min" reading back from 588.
  const duration = 105 * 60_000;
  const { major } = drawn(0, duration, duration, 588 / duration);
  assert.deepEqual(
    major.map(({ label, flip }) => [label, flip]),
    [
      ["0 s", false],
      ["15 min", false],
      ["30 min", false],
      ["45 min", false],
      ["1 h", false],
      ["1 h 15 min", false],
      ["", false],
      ["1 h 45 min", true],
    ],
  );
});

test("A time reads in seconds under a minute and in larger units past it", () => {
  assert.equal(elapsed(0), "0 s");
  assert.equal(elapsed(1200), "1.2 s");
  assert.equal(elapsed(59_999), "59.999 s");
  assert.equal(elapsed(60_000), "1 min");
  assert.equal(elapsed(125_400), "2 min 5 s");
  assert.equal(elapsed(10_200_000), "2 h 50 min");
  assert.equal(elapsed(3_600_000 + 7_000), "1 h 7 s");
});

test("An axis given a start reads as a clock, its ticks on the clock's round times", () => {
  // The session from 12:56 to 17:28 again: the first tick is the half hour after
  // the start, and every label is a time of day on the clock the start is written in.
  const duration = (4 * 60 + 32) * 60_000;
  const { major } = drawn(
    0,
    duration,
    duration,
    800 / duration,
    "2026-11-25T12:56+09:00",
  );
  assert.deepEqual(
    major.map(({ label }) => label),
    ["13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00", "16:30", "17:00"],
  );
  assert.equal(major[0].at, 4 / (4 * 60 + 32));
  // A clock of seconds shows them, and a step below a second its decimals.
  const seconds = drawn(0, 60_000, 60_000, 900 / 60_000, "2026-11-25T23:59:30");
  assert.deepEqual(
    seconds.major.map(({ label }) => label),
    [
      "23:59:30",
      "23:59:40",
      "23:59:50",
      "00:00:00",
      "00:00:10",
      "00:00:20",
      "00:00:30",
    ],
  );
  const fractions = drawn(0, 2000, 2000, 0.2, "2026-11-25T12:56:00.25Z");
  assert.deepEqual(fractions.major.map(({ label }) => label).slice(0, 2), [
    "12:56:00.5",
    "12:56:01.0",
  ]);
});

test("A time from a start reads as the time of day, with as few parts as show it", () => {
  const start = "2026-11-25T12:56";
  assert.equal(elapsed(0, start), "12:56");
  assert.equal(elapsed(10_200_000, start), "15:46");
  assert.equal(elapsed(30_000, start), "12:56:30");
  assert.equal(elapsed(1_250, start), "12:56:01.25");
  assert.equal(elapsed(0, "2026-11-25T12:56:00.000Z"), "12:56");
  assert.equal(elapsed(0, null), "0 s");
});

test("Overlapping extents never share a row", () => {
  const extents = [
    { id: "a", start: 0, end: 50 },
    { id: "b", start: 40, end: 90 },
    { id: "c", start: 50, end: 60 },
    { id: "d", start: 85, end: 120 },
  ];
  const rows = assignRows(
    extents,
    (item) => item.start,
    (item) => item.end,
  );
  assert.deepEqual(Object.fromEntries(rows), { a: 0, b: 1, c: 0, d: 0 });
});
