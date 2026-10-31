import assert from "node:assert/strict";
import test from "node:test";
import { render } from "/runtime/widget-api.js";
import { assignRows } from "/runtime/time-axis.js";
import {
  render as timelineView,
  timelineModel,
} from "../../packages/timeline/widgets/timeline-view.js";

const lanes = (list) =>
  list
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

const run = (label, list) => `<lf-run label="${label}">${lanes(list)}</lf-run>`;

const timeline = (markup) => {
  const host = document.createElement("lf-timeline");
  host.id = `timeline-${Math.random().toString(36).slice(2)}`;
  host.setAttribute("aria-label", "Race");
  host.innerHTML = markup;
  document.body.append(host);
  const model = timelineModel(host);
  let current = 0;
  const drawing = {
    model,
    get current() {
      return current;
    },
    set current(value) {
      current = Math.max(0, Math.min(model.steps.length - 1, value));
    },
    render: () => timelineView(host, current, model, null),
    get rows() {
      return [...host.querySelectorAll(".lf-timeline-step")];
    },
    get controls() {
      return host.querySelector(".lf-timeline-controls");
    },
    get chart() {
      return host.querySelector(".lf-timeline-chart");
    },
    get previous() {
      return host.querySelector(".lf-timeline-previous");
    },
    get next() {
      return host.querySelector(".lf-timeline-next");
    },
    eventElement: (id) => host.querySelector(`[data-event="${id}"]`),
  };
  render(drawing.render(), host, { host });
  return drawing;
};

test("Steps visit starts in order: ties share a step and a span's end is no step", () => {
  const drawing = timeline(
    lanes([
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
    ]),
  );
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
  const drawing = timeline(
    lanes([
      [
        "A",
        [
          ["s-read", 0],
          ["s-work", 1000, 3000],
          ["s-write", 3000],
        ],
      ],
      ["B", [["s-late", 2000]]],
    ]),
  );
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
  drawing.current = 2;
  const host = controls.closest("lf-timeline");
  render(drawing.render(), host, { host });
  assert.equal(drawing.current, 2);
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
  drawing.current = 99;
  render(drawing.render(), host, { host });
  assert.equal(drawing.current, 3, "a step past the end clamps to the last");
  assert.equal(drawing.next.getAttribute("aria-disabled"), "true");
});

test("Compared runs share one axis and one playhead, each headed by its name", () => {
  const drawing = timeline(
    run("Before", [
      ["A", [["before-write", 4000]]],
      ["B", [["before-done", 5000]]],
    ]) +
      run("After", [
        ["A", [["after-write", 4000]]],
        ["B", [["after-done", 8000]]],
      ]),
  );
  // The longer run scales the axis for both, so the shorter run draws shorter.
  const at = (id) =>
    drawing
      .eventElement(id)
      .querySelector(".lf-timeline-mark")
      .getAttribute("style")
      .match(/--lf-timeline-at: ([\d.]+)/)[1];
  assert.deepEqual(
    ["before-write", "after-write", "before-done", "after-done"].map(at),
    ["0.5", "0.5", "0.625", "1"],
  );
  // One step holds every run's event at that moment.
  assert.deepEqual(
    drawing.model.steps.map((step) => step.events.map((event) => event.id)),
    [["before-write", "after-write"], ["before-done"], ["after-done"]],
  );
  // Each run's name takes the grid row just above its lanes.
  const rows = [
    ...drawing.chart.querySelectorAll(".lf-timeline-run, .lf-timeline-name"),
  ]
    .map((cell) => [
      cell.getAttribute("style").match(/grid-row: (\d+)/)[1],
      cell.textContent,
    ])
    .toSorted((a, b) => a[0] - b[0])
    .map(([, text]) => text);
  assert.deepEqual(rows, ["Before", "A", "B", "After", "A", "B"]);
  assert.deepEqual(
    [...drawing.rows[0].querySelectorAll(".lf-timeline-step-event")].map(
      (event) => event.textContent,
    ),
    ["Before · A: before-write", "After · A: after-write"],
  );
});

test("A span that ends before it starts is reported and drawn as an instant", () => {
  const drawing = timeline(lanes([["A", [["bad-span", 500, 100]]]]));
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
