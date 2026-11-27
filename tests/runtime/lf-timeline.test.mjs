/* What lf-timeline reads from its authored lanes and what it draws from them, mounted
   as the element on a page with no Leaf behind it. Nothing is laid out here, so the
   labels' layout and the ruler are the browser suite's; what a press asks of Leaf is
   the story's (lf-timeline-story.test.mjs). */
import assert from "node:assert/strict";
import test from "node:test";
import { readTimeline } from "../../packages/timeline/widgets/lf-timeline.js";

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

/** Draws the timeline whose authored content is `markup`, as a page would. */
const timeline = (markup, start) => {
  const host = document.createElement("lf-timeline");
  host.id = `timeline-${Math.random().toString(36).slice(2)}`;
  host.setAttribute("aria-label", "Race");
  if (start) host.setAttribute("start", start);
  host.innerHTML = markup;
  /** @type {string[]} */
  const problems = [];
  host.addEventListener("error", (event) => problems.push(event.error.message));
  document.body.append(host);
  return {
    host,
    problems,
    reading: readTimeline(host),
    get rows() {
      return [...host.querySelectorAll(".lf-timeline-step")];
    },
    get controls() {
      return host.querySelector(".lf-timeline-controls");
    },
    get chart() {
      return host.querySelector(".lf-timeline-chart");
    },
    get list() {
      return host.querySelector(".lf-timeline-steps");
    },
    get previous() {
      return host.querySelector(".lf-timeline-previous");
    },
    get next() {
      return host.querySelector(".lf-timeline-next");
    },
    eventElement: (id) => host.querySelector(`[data-lf-event="${id}"]`),
  };
};

// A press draws in Effect UI's flush, a microtask after it.
const drawn = () => new Promise((resolve) => setTimeout(resolve));

const ids = (drawing, step) =>
  step.events.map((index) => drawing.reading.events[index].id);

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
  const steps = drawing.reading.steps.map((step) => [step.time, ids(drawing, step)]);
  assert.deepEqual(steps, [
    [0, ["a-read", "store-start"]],
    [200, ["a-work"]],
    [1000, ["b-read"]],
    [1200, ["b-work"]],
    [4200, ["a-write"]],
  ]);
  assert.equal(drawing.rows.length, steps.length);
  // Bare lanes share the list's one column, which needs no head.
  assert.equal(drawing.list.querySelector(".lf-timeline-steps-head"), null);
  const [cell, ...others] = drawing.rows[0].querySelectorAll(".lf-timeline-step-cell");
  assert.deepEqual(others, []);
  assert.equal(cell.style.gridColumn, "");
  assert.equal(cell.dataset.lfQuiet, undefined);
  assert.equal(cell.textContent, "A: a-readStore: store-start");
  // The drawing stands in the authored lanes' place, which stay where the author put
  // them.
  assert.equal(drawing.host.querySelectorAll(":scope > lf-lane").length, 3);
});

test("A step paints what came before as done and leaves later events open", async () => {
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
        event.dataset.lfEvent,
        event.dataset.lfState,
      ]),
    );
  const controls = drawing.controls;
  const row = drawing.rows[1];
  const mark = drawing.eventElement("s-work");
  assert.equal(drawing.previous.getAttribute("aria-disabled"), "true");
  row.focus();
  drawing.rows[2].click();
  await drawn();
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
  const work = drawing.chart.querySelector(
    '[data-lf-event="s-work"] .lf-timeline-mark',
  );
  assert.equal(work.style.getPropertyValue("--lf-timeline-done"), "0.5");
  assert.equal(drawing.rows[2].getAttribute("aria-current"), "step");
  assert.equal(drawing.rows[3].dataset.lfAhead, "");
  assert.equal(drawing.previous.getAttribute("aria-disabled"), null);
  // A press on a mark goes to its event's step, and Next ends at the last.
  drawing.eventElement("s-write").click();
  await drawn();
  assert.equal(drawing.rows[3].getAttribute("aria-current"), "step");
  assert.equal(drawing.next.getAttribute("aria-disabled"), "true");
  drawing.next.click();
  await drawn();
  assert.equal(drawing.rows[3].getAttribute("aria-current"), "step");
});

test("Previous and Next are buttons that wear their action's symbol and name", () => {
  const drawing = timeline(lanes([["A", [["only", 0]]]]));
  for (const [button, name] of [
    [drawing.previous, "Previous"],
    [drawing.next, "Next"],
  ]) {
    assert.equal(button.localName, "button");
    assert.equal(button.getAttribute("aria-label"), name);
    assert.ok(button.querySelector("svg[data-lf-icon]"), button.outerHTML);
  }
  assert.equal(drawing.controls.getAttribute("role"), "group");
  assert.equal(drawing.controls.getAttribute("aria-label"), "Race");
});

test("A timeline given a start shows its steps and position as times of day", async () => {
  const drawing = timeline(
    lanes([
      [
        "User",
        [
          ["user-ask", 0],
          ["user-reply", 10_200_000],
        ],
      ],
      ["Session", [["session-work", 30_000, 16_320_000]]],
    ]),
    "2026-11-25T12:56",
  );
  const times = drawing.rows.map(
    (row) => row.querySelector(".lf-timeline-step-time").textContent,
  );
  assert.deepEqual(times, ["12:56", "12:56:30", "15:46"]);
  drawing.rows[2].click();
  await drawn();
  assert.match(drawing.controls.textContent, /Step 3 of 3 · 15:46/);
});

test("Compared runs share one axis and one playhead, each headed by its name", () => {
  const drawing = timeline(
    run("Before", [
      ["A", [["before-write", 4000]]],
      [
        "B",
        [
          ["before-start", 4000],
          ["before-done", 5000],
        ],
      ],
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
      .style.getPropertyValue("--lf-axis-at");
  assert.deepEqual(
    ["before-write", "after-write", "before-done", "after-done"].map(at),
    ["0.5", "0.5", "0.625", "1"],
  );
  // One step holds every run's event at that moment.
  assert.deepEqual(
    drawing.reading.steps.map((step) => ids(drawing, step)),
    [["before-write", "before-start", "after-write"], ["before-done"], ["after-done"]],
  );
  // Each run's name takes the grid row just above its lanes.
  const rows = [
    ...drawing.chart.querySelectorAll(".lf-timeline-run, .lf-timeline-name"),
  ]
    .map((cell) => [Number(cell.style.gridRow), cell.textContent])
    .toSorted((a, b) => a[0] - b[0])
    .map(([, text]) => text);
  assert.deepEqual(rows, ["Before", "A", "B", "After", "A", "B"]);
  // The step list names each run once, over its column, and a row puts each run's
  // events in that run's column, its name a word for listeners.
  assert.deepEqual(
    [...drawing.list.querySelectorAll(".lf-timeline-steps-run")].map((head) => [
      head.style.gridColumn,
      head.textContent,
    ]),
    [
      ["2", "Before"],
      ["3", "After"],
    ],
  );
  const cells = (row) =>
    [...row.querySelectorAll(".lf-timeline-step-cell")].map((cell) => [
      cell.style.gridColumn,
      cell.dataset.lfQuiet,
      [...cell.querySelectorAll(".lf-timeline-step-event")].map(
        (event) => event.textContent,
      ),
    ]);
  assert.deepEqual(cells(drawing.rows[0]), [
    ["2", "Before", ["A: before-write", "B: before-start"]],
    ["3", "After", ["A: after-write"]],
  ]);
  assert.deepEqual(cells(drawing.rows[2]), [["3", "After", ["B: after-done"]]]);
});

test("The step list names a run or lane by its short form, and the chart by its label", () => {
  const drawing = timeline(
    `<lf-run label="Before the fix" abbr="Before">` +
      `<lf-lane label="Main thread" abbr="M"><lf-event id="short-busy" label="Busy" at="0"></lf-event></lf-lane>` +
      `<lf-lane label="Fork"><lf-event id="short-work" label="Works" at="0"></lf-event></lf-lane>` +
      `</lf-run>`,
  );
  assert.deepEqual(
    [...drawing.chart.querySelectorAll(".lf-timeline-run, .lf-timeline-name")].map(
      (name) => name.textContent,
    ),
    ["Before the fix", "Main thread", "Fork"],
  );
  const head = drawing.list.querySelector(".lf-timeline-steps-run");
  assert.equal(head.textContent, "Before");
  assert.deepEqual(head.lfPreview(), { name: "Before the fix" });
  // Listeners hear a short form's label instead.
  const [short, full] = drawing.rows[0].querySelectorAll(".lf-timeline-step-lane");
  assert.equal(short.dataset.lfQuiet, "Main thread");
  const form = short.querySelector('[aria-hidden="true"]');
  assert.equal(form.textContent, "M");
  assert.deepEqual(form.lfPreview(), { name: "Main thread" });
  assert.equal(short.textContent, "M: ");
  assert.equal(full.dataset.lfQuiet, undefined);
  assert.equal(full.textContent, "Fork: ");
  // Focus on the row previews what its short forms stand for; a pointer, nothing.
  assert.deepEqual(drawing.rows[0].lfPreview("focus"), {
    name: "M = Main thread",
    detail: [],
  });
  assert.equal(drawing.rows[0].lfPreview("pointer"), false);
});

test("A run with no lanes keeps its heading, and a lane beside runs is reported", () => {
  const drawing = timeline(
    run("Before", [["A", [["solo-write", 0]]]]) +
      lanes([["Reference", [["solo-mark", 100]]]]) +
      run("After", []),
  );
  assert.deepEqual(
    [...drawing.chart.querySelectorAll(".lf-timeline-run")].map(
      (heading) => heading.textContent,
    ),
    ["Before", "After"],
  );
  const problem = 'lf-lane "Reference" stands beside lf-run elements; put it in a run';
  assert.deepEqual(drawing.reading.problems, [problem]);
  // The element reports each problem as its `error`.
  assert.deepEqual(drawing.problems, [problem]);
});

test("A start off the calendar is reported and the timeline reads elapsed time", () => {
  const drawing = timeline(
    lanes([
      [
        "A",
        [
          ["a-mark", 0],
          ["a-late", 90_000],
        ],
      ],
    ]),
    "2026-13-25T12:56",
  );
  assert.deepEqual(drawing.reading.problems, [
    'lf-timeline start "2026-13-25T12:56" is not a date and time on the calendar',
  ]);
  assert.deepEqual(
    drawing.rows.map((row) => row.querySelector(".lf-timeline-step-time").textContent),
    ["0 s", "1 min 30 s"],
  );
  assert.equal(timeline("", "2026-02-30T12:56").reading.start, null);
  assert.equal(
    timeline("", "2026-02-28T12:56+05:00").reading.start,
    "2026-02-28T12:56+05:00",
  );
});

test("A span that ends before it starts is reported and drawn as an instant", () => {
  const drawing = timeline(lanes([["A", [["bad-span", 500, 100]]]]));
  assert.equal(drawing.reading.problems.length, 1);
  assert.equal(drawing.reading.events[0].end, null);
  assert.equal(
    drawing.eventElement("bad-span").querySelector(".lf-timeline-mark").dataset.lfKind,
    "instant",
  );
});

test("A timeline with no events says so and offers no step", () => {
  const drawing = timeline("");
  assert.match(drawing.controls.textContent, /No events/);
  assert.equal(drawing.rows.length, 0);
  assert.equal(drawing.next.getAttribute("aria-disabled"), "true");
});
