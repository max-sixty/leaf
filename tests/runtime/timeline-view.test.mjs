import assert from "node:assert/strict";
import test from "node:test";
import { initialRender } from "/runtime/initial-render.js";
import { assignRows } from "/runtime/time-axis.js";
import "../../packages/timeline/initial/lf-timeline.js";

const timeline = (lanes) => {
  const host = document.createElement("lf-timeline");
  host.id = `timeline-${Math.random().toString(36).slice(2)}`;
  host.setAttribute("aria-label", "Race");
  host.innerHTML = lanes
    .map(
      ([label, events]) =>
        `<lf-lane label="${label}">${events
          .map(
            ([id, at, end]) =>
              `<lf-event id="${id}" label="${id}" at="${at}"${end === undefined ? "" : ` end="${end}"`}></lf-event>`,
          )
          .join("")}</lf-lane>`,
    )
    .join("");
  document.body.append(host);
  return initialRender(host);
};

test("Steps visit starts in order: ties share a step and a span's end is no step", () => {
  const drawing = timeline([
    [
      "A",
      [
        ["a-read", 0],
        ["a-work", 200, 4200],
        ["a-write", 4200],
      ],
    ],
    [
      "B",
      [
        ["b-read", 1000],
        ["b-work", 1200, 5200],
      ],
    ],
    ["Store", [["store-start", 0]]],
  ]);
  const steps = drawing.model.steps.map((step) => [
    step.time,
    step.events.map((event) => event.id),
  ]);
  assert.deepEqual(steps, [
    [0, ["a-read", "store-start"]],
    [200, ["a-work"]],
    [1000, ["b-read"]],
    [1200, ["b-work"]],
    [4200, ["a-write"]],
  ]);
  assert.equal(drawing.rows.length, steps.length);
});

test("A step paints what came before as done and leaves later events open", () => {
  const drawing = timeline([
    [
      "A",
      [
        ["s-read", 0],
        ["s-work", 1000, 3000],
        ["s-write", 3000],
      ],
    ],
    ["B", [["s-late", 2000]]],
  ]);
  const states = () =>
    Object.fromEntries(
      [...drawing.chart.querySelectorAll(".lf-timeline-event")].map((event) => [
        event.dataset.event,
        event.dataset.state,
      ]),
    );
  const controls = drawing.controls;
  const row = drawing.rows[1];
  const mark = drawing.eventElement("s-work");
  row.focus();
  assert.equal(drawing.show(2), 2);
  assert.equal(drawing.controls, controls);
  assert.equal(drawing.rows[1], row);
  assert.equal(drawing.eventElement("s-work"), mark);
  assert.equal(document.activeElement, row, "stepping retains the focused row");
  assert.deepEqual(states(), {
    "s-read": "past",
    "s-work": "running",
    "s-write": "future",
    "s-late": "current",
  });
  // Half the span is done when the playhead stands at 2000 of 1000..3000.
  const work = drawing.chart.querySelector('[data-event="s-work"] .lf-timeline-mark');
  assert.match(work.getAttribute("style"), /--lf-timeline-done: 0\.5/);
  assert.equal(drawing.rows[2].getAttribute("aria-current"), "step");
  assert.equal(drawing.previous.getAttribute("aria-disabled"), null);
  assert.equal(drawing.show(99), 3, "a step past the end clamps to the last");
  assert.equal(drawing.next.getAttribute("aria-disabled"), "true");
});

test("A span that ends before it starts is reported and drawn as an instant", () => {
  const drawing = timeline([["A", [["bad-span", 500, 100]]]]);
  assert.equal(drawing.model.problems.length, 1);
  assert.equal(drawing.model.events[0].end, null);
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
