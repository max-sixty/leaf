import assert from "node:assert/strict";
import test from "node:test";
import { render } from "/vendor/lit.js";
import { assignRows, timeAxis } from "/runtime/lib/time-axis.js";

// What the axis from `from` to `to` draws: each tick's words and each gridline, with
// the share of the axis it stands at and whether it reads back from its time.
const drawn = (from, to, duration, pxPerMs) => {
  const axis = timeAxis(from, to, duration, pxPerMs);
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
