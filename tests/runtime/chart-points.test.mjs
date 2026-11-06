import assert from "node:assert/strict";
import test from "node:test";
import * as bundle from "../../packages/default/vendor/plot.esm.js";
import {
  cross,
  nearest,
  readPoints,
  sameDatum,
  sayPoint,
  step,
} from "../../packages/default/widgets/chart-points.js";

const { Plot } = bundle;

// The points Plot draws for `marks`, as lf-chart reads them, beside the drawing.
/** @param {any} marks */
function reading(marks) {
  const points = readPoints(bundle, marks);
  return { points, marks: [marks, points.marks] };
}
// The points Plot draws for `options`, as lf-chart reads them, and the drawing.
/** @param {any} options */
function drawn(options) {
  const { points, marks } = reading(options.marks);
  const svg = Plot.plot({ width: 640, height: 400, ...options, marks });
  return { reading: points.done(), svg };
}
/** @param {any} options */
const read = (options) => drawn(options).reading;
/** @param {import("../../packages/default/widgets/chart-points.js").Point | null} point */
const said = (point) => (point ? sayPoint(point) : null);

const HOURS = [
  { week: "w1", kind: "features", hours: 21 },
  { week: "w2", kind: "features", hours: 18 },
  { week: "w1", kind: "fixes", hours: 9 },
  { week: "w2", kind: "fixes", hours: 14 },
];

test("a point says where it stands, then its value before its axis label", () => {
  const stack = read({
    y: { label: "hours" },
    marks: [Plot.barY(HOURS, { x: "week", y: "hours", fill: "kind" })],
  });
  // A stacked segment measures its own share of the stack.
  assert.deepEqual(
    stack.series.map((run) => run.map(said)),
    [
      [
        { name: "w1 · features", detail: ["21 hours"] },
        { name: "w2 · features", detail: ["18 hours"] },
      ],
      [
        { name: "w1 · fixes", detail: ["9 hours"] },
        { name: "w2 · fixes", detail: ["14 hours"] },
      ],
    ],
  );

  const line = read({
    x: { type: "utc" },
    y: { label: "hours to first review" },
    marks: [
      Plot.lineY(
        [
          { week: "2026-05-04", team: "backend", hours: 31 },
          { week: "2026-05-11", team: "backend", hours: 26 },
          { week: "2026-06-01T14:00Z", team: "frontend", hours: 8412 },
        ],
        { x: "week", y: "hours", stroke: "team" },
      ),
    ],
  });
  assert.deepEqual(
    line.series.map((run) => run.map(said)),
    [
      [
        { name: "May 4, 2026 · backend", detail: ["31 hours to first review"] },
        { name: "May 11, 2026 · backend", detail: ["26 hours to first review"] },
      ],
      [
        {
          name: "Jun 1, 2026, 2:00 PM UTC · frontend",
          detail: ["8,412 hours to first review"],
        },
      ],
    ],
  );

  // Where both axes measure, x is the place, named by its label.
  const scatter = read({
    marks: [Plot.dot([{ lines: 90, minutes: 26 }], { x: "lines", y: "minutes" })],
  });
  assert.deepEqual(said(scatter.points[0] ?? null), {
    name: "lines 90",
    detail: ["26 minutes"],
  });

  // A horizontal chart stands its points at their categories on y.
  const rows = read({
    x: { label: "open issues" },
    marks: [Plot.barX([{ area: "billing", open: 19 }], { x: "open", y: "area" })],
  });
  assert.equal(rows.axis, "y");
  assert.deepEqual(said(rows.points[0] ?? null), {
    name: "billing",
    detail: ["19 open issues"],
  });

  const titled = read({
    marks: [
      Plot.dot([{ x: 1, y: 2 }], {
        x: "x",
        y: "y",
        title: () => "Release w3\nshipped on time\nby Friday",
      }),
    ],
  });
  assert.deepEqual(said(titled.points[0] ?? null), {
    name: "Release w3",
    detail: ["shipped on time", "by Friday"],
  });
});

test("a chart's data marks say their values unless the author picks others", () => {
  const rows = [
    { x: 1, y: 2 },
    { x: 2, y: 3 },
  ];
  const drawn = read({
    marks: [
      Plot.lineY(rows, { x: "x", y: "y" }),
      Plot.ruleY([0]),
      Plot.text(rows, { x: "x", y: "y", text: "y" }),
    ],
  });
  // The line's points, and nothing of the rule or the labels.
  assert.deepEqual(
    drawn.points.map((point) => point.i),
    [0, 1],
  );
  // A dot drawn on the line's own rows adds no point.
  const marked = read({
    marks: [Plot.lineY(rows, { x: "x", y: "y" }), Plot.dot(rows, { x: "x", y: "y" })],
  });
  assert.equal(marked.points.length, 2);
  const picked = read({
    marks: [Plot.lineY(rows, { x: "x", y: "y" }), Plot.ruleY([0], { tip: true })],
  });
  assert.deepEqual(picked.points.map(said), [{ name: "0 y", detail: [] }]);
});

// Where Plot drew each circle of `svg`, its facet's offset included, and whether a
// reading's points stand there: within the half pixel Plot shifts a mark by for crisp
// edges, which its pointer doesn't count either.
/** @param {SVGSVGElement} svg */
const circles = (svg) =>
  [...svg.querySelectorAll("circle")].map((circle) => {
    let [x, y] = [Number(circle.getAttribute("cx")), Number(circle.getAttribute("cy"))];
    for (let at = circle.parentElement; at && at !== svg; at = at.parentElement) {
      const moved = /translate\(([-\d.]+),([-\d.]+)\)/.exec(
        at.getAttribute("transform") ?? "",
      );
      if (moved) ((x += Number(moved[1])), (y += Number(moved[2])));
    }
    return [x, y];
  });
/** @param {{reading: import("../../packages/default/widgets/chart-points.js").Reading, svg: SVGSVGElement}} drawing @param {string} [what] */
function standsWherePlotDraws({ reading, svg }, what) {
  const drawnAt = circles(svg);
  assert.equal(reading.points.length, drawnAt.length, what);
  for (const point of reading.points)
    assert.ok(
      drawnAt.some(
        ([x, y]) => Math.abs(x - point.x) <= 1 && Math.abs(y - point.y) <= 1,
      ),
      `${what}: nothing drawn at ${point.x}, ${point.y} of ${JSON.stringify(drawnAt)}`,
    );
}

test("each point stands where Plot draws it, in its facet, at its frame anchor and offset", () => {
  const anchored = drawn({ marks: [Plot.dotX([1, 2], { frameAnchor: "bottom" })] });
  standsWherePlotDraws(anchored, "a frame-anchored dot");
  assert.equal(anchored.reading.points[0]?.y, 370);
  const moved = drawn({
    marks: [Plot.dot([{ x: 5, y: 5 }], { x: "x", y: "y", dx: 70, dy: -20, r: 6 })],
  });
  standsWherePlotDraws(moved, "a dot moved by dx and dy");
  for (const facet of ["fx", "fy"])
    standsWherePlotDraws(
      drawn({
        marks: [
          Plot.dot(
            [
              { k: "a", x: 1, y: 2 },
              { k: "a", x: 2, y: 5 },
              { k: "b", x: 1, y: 3 },
              { k: "b", x: 3, y: 1 },
            ],
            { x: "x", y: "y", [facet]: "k" },
          ),
        ],
      }),
      facet,
    );
});

test("each mark reads along the axis its author's tip names, or its points stand at", () => {
  const marks = [
    Plot.barY(HOURS, { x: "week", y: "hours" }),
    Plot.barX(HOURS, { x: "hours", y: "week" }),
    Plot.dot(HOURS, { x: "hours", y: "hours" }),
    Plot.lineY(HOURS, { x: "week", y: "hours", tip: "y" }),
    Plot.dot(HOURS, { x: "hours", y: "hours", tip: { maxRadius: 80 } }),
  ];
  const points = reading(marks.slice(0, 3));
  Plot.plot({ marks: points.marks });
  assert.deepEqual(
    points.points.done().frames.map(({ kx, ky, reach }) => [kx, ky, reach]),
    [
      [1, 0.01, 1600],
      [0.01, 1, 1600],
      [1, 1, 1600],
    ],
  );
  const named = reading(marks.slice(3));
  Plot.plot({ marks: named.marks });
  assert.deepEqual(
    named.points.done().frames.map(({ kx, ky, reach }) => [kx, ky, reach]),
    [
      [0.01, 1, 1600],
      [1, 1, 6400],
    ],
  );
  // Plot draws no tip of its own for them.
  assert.ok(marks.every((mark) => !mark.tip));
});

test("each mark picks by its own tip, and a pick of a point another stands on is the first's", () => {
  const rows = [
    { id: "a", x: 1, y: 1 },
    { id: "b", x: 9, y: 9 },
  ];
  /** @param {unknown} first @param {unknown} second */
  const twice = (first, second) =>
    read({
      marks: [
        Plot.dot(rows, { x: "x", y: "y", title: "id", tip: first }),
        Plot.dot(rows, { x: "x", y: "y", title: "id", tip: second }),
      ],
    });
  // The second mark reads along x only, so it picks far above the point, beyond the
  // first's reach.
  const along = twice(true, "x");
  const a = along.points[0];
  assert.ok(a);
  assert.equal(along.points.length, 2);
  assert.equal(nearest(along, a.x, a.y - 110), a);
  // Its reach is its own.
  const reach = twice({ maxRadius: 1 }, { maxRadius: 80 });
  const first = reach.points[0];
  assert.ok(first);
  assert.equal(nearest(reach, first.x + 20, first.y), first);

  // A tip's px picks each datum by its own value, wherever the datum stands.
  const picked = read({
    marks: [
      Plot.dot(
        [
          { id: "left", x: 2, y: 5, pickX: 8 },
          { id: "right", x: 8, y: 5, pickX: 2 },
        ],
        { x: "x", y: "y", title: "id", tip: { px: "pickX" } },
      ),
    ],
  });
  const [left, right] = picked.points;
  assert.ok(left && right);
  assert.equal(said(nearest(picked, left.x, left.y))?.name, "right");
  assert.equal(said(nearest(picked, right.x, right.y))?.name, "left");
  // A datum with no px is drawn, so the keys still reach it; only the pointer, as
  // Plot's, passes it by.
  const unpicked = read({
    marks: [
      Plot.dot(
        [
          { id: "a", x: 1, y: 1, p: 1 },
          { id: "b", x: 2, y: 2, p: null },
        ],
        { x: "x", y: "y", title: "id", tip: { px: "p" } },
      ),
    ],
  });
  const b = unpicked.points.find((point) => said(point)?.name === "b");
  assert.ok(b);
  assert.notEqual(nearest(unpicked, b.x, b.y), b);
});

test("a tip's format and a mark's own channels say what Plot's tip would", () => {
  const formatted = read({
    marks: [
      Plot.dot(
        [
          {
            when: new Date("2026-05-04T00:00Z"),
            share: 0.256,
            team: "backend",
            lead: "Ada",
          },
        ],
        {
          x: "when",
          y: "share",
          fill: "team",
          channels: { lead: "lead" },
          tip: {
            format: {
              x: "%b %Y",
              y: ".0%",
              fill: false,
              lead: (/** @type {string} */ name) => `led by ${name}`,
            },
          },
        },
      ),
    ],
  });
  assert.deepEqual(said(formatted.points[0] ?? null), {
    name: "May 2026 · led by Ada",
    detail: ["26% share"],
  });
  // A channel the author adds is said as Plot's tip says it: a name as a place, a
  // number before its label.
  const added = read({
    marks: [
      Plot.dot([{ x: 1, y: 2, lead: "Ada", cost: 3 }], {
        x: "x",
        y: "y",
        channels: { lead: "lead", cost: "cost" },
      }),
    ],
  });
  assert.deepEqual(said(added.points[0] ?? null), {
    name: "x 1 · Ada",
    detail: ["2 y · 3 cost"],
  });
  // A format given alone is the title's.
  const titled = read({
    marks: [
      Plot.dot([{ x: 1, y: 2, id: "w3" }], {
        x: "x",
        y: "y",
        title: "id",
        tip: { format: (/** @type {string} */ id) => `release ${id}` },
      }),
    ],
  });
  assert.equal(said(titled.points[0] ?? null)?.name, "release w3");
});

test("a facet's points are a series of their own", () => {
  const reading = read({
    marks: [
      Plot.lineY(
        [
          { k: "a", x: 1, y: 2 },
          { k: "a", x: 2, y: 4 },
          { k: "b", x: 1, y: 3 },
          { k: "b", x: 2, y: 1 },
        ],
        { x: "x", y: "y", fy: "k" },
      ),
    ],
  });
  assert.deepEqual(
    reading.series.map((run) => run.map((point) => said(point)?.name)),
    [
      ["a · x 1", "a · x 2"],
      ["b · x 1", "b · x 2"],
    ],
  );
  const first = step(reading, null, "first");
  assert.equal(said(step(reading, first, 1))?.name, "a · x 2");
  assert.equal(said(cross(reading, first, 1))?.name, "b · x 1");
  // Side by side, a key crossing to the next facet keeps its place in the facet.
  const beside = read({
    marks: [
      Plot.lineY(
        [
          { k: "a", x: 1, y: 2 },
          { k: "a", x: 2, y: 4 },
          { k: "b", x: 1, y: 3 },
          { k: "b", x: 2, y: 1 },
        ],
        { x: "x", y: "y", fx: "k" },
      ),
    ],
  });
  const end = step(beside, null, "last");
  assert.equal(said(end)?.name, "a · x 2");
  assert.equal(said(cross(beside, end, 1))?.name, "b · x 2");
});

test("points at one place that say different things are each read", () => {
  const reading = read({
    marks: [
      Plot.dot(
        [
          { x: 1, y: 2, said: "one" },
          { x: 1, y: 2, said: "two" },
        ],
        { x: "x", y: "y", title: "said" },
      ),
    ],
  });
  assert.deepEqual(
    reading.points.map((point) => said(point)?.name),
    ["one", "two"],
  );
});

test("a redraw finds the datum the reader was on, wherever the data moved it", () => {
  const rows = (/** @type {number[]} */ xs) => xs.map((x) => ({ x, y: x * 10 }));
  const before = read({ marks: [Plot.lineY(rows([1, 2, 3]), { x: "x", y: "y" })] });
  const on = before.points.find((point) => said(point)?.name === "x 2");
  assert.ok(on);
  const after = read({ marks: [Plot.lineY(rows([2, 3]), { x: "x", y: "y" })] });
  assert.deepEqual(said(sameDatum(after, on)), { name: "x 2", detail: ["20 y"] });
  const gone = read({ marks: [Plot.lineY(rows([3]), { x: "x", y: "y" })] });
  assert.equal(sameDatum(gone, on), null);
  // Two readings at one place are two data across drawings too.
  const together = (/** @type {string} */ by) =>
    read({
      marks: [
        Plot.dot(
          [
            { x: 1, y: 2, said: "one", kind: "a" },
            { x: 1, y: 2, said: "two", kind: "b" },
          ],
          { x: "x", y: "y", [by]: by === "title" ? "said" : "kind" },
        ),
      ],
    });
  for (const by of ["title", "fill"]) {
    const two = together(by).points[1];
    assert.ok(two);
    assert.deepEqual(said(sameDatum(together(by), two)), said(two), by);
  }
});

test("a time reads to the second or millisecond its datum has", () => {
  const reading = read({
    x: { type: "utc" },
    marks: [
      Plot.lineY(
        [
          { t: "2026-01-01T00:00:01Z", v: 1 },
          { t: "2026-01-01T00:00:02.500Z", v: 2 },
          { t: "2026-01-01T09:30Z", v: 3 },
        ],
        { x: "t", y: "v" },
      ),
    ],
  });
  assert.deepEqual(
    reading.points.map((point) => said(point)?.name),
    [
      "Jan 1, 2026, 12:00:01 AM UTC",
      "Jan 1, 2026, 12:00:02.500 AM UTC",
      "Jan 1, 2026, 9:30 AM UTC",
    ],
  );
});

test("the arrows step along a series and across to the next at the nearest place", () => {
  const reading = read({
    marks: [Plot.barY(HOURS, { x: "week", y: "hours", fill: "kind" })],
  });
  const first = step(reading, null, "first");
  assert.deepEqual(said(first), { name: "w1 · features", detail: ["21 hours"] });
  const next = step(reading, first, 1);
  assert.equal(said(next)?.name, "w2 · features");
  assert.equal(step(reading, next, 1), next, "a series' end holds");
  const across = cross(reading, next, 1);
  assert.equal(said(across)?.name, "w2 · fixes");
  assert.equal(cross(reading, across, 1), across, "the last series holds");
  assert.equal(said(step(reading, across, "first"))?.name, "w1 · fixes");
  assert.equal(said(cross(reading, across, -1))?.name, "w2 · features");
});
