import assert from "node:assert/strict";
import test from "node:test";
import * as Plot from "../../packages/default/vendor/plot.esm.js";
import {
  cross,
  nearest,
  readPoints,
  sayPoint,
  step,
} from "../../packages/default/widgets/chart-points.js";

// The points Plot draws for `options`, as lf-chart reads them.
/** @param {any} options */
function read(options) {
  const points = readPoints(Plot, options.marks);
  Plot.plot({ width: 640, height: 400, ...options });
  return points.done();
}
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
  assert.deepEqual(stack.points.map(said), [
    { name: "w1 · features", detail: ["21 hours"] },
    { name: "w1 · fixes", detail: ["9 hours"] },
    { name: "w2 · features", detail: ["18 hours"] },
    { name: "w2 · fixes", detail: ["14 hours"] },
  ]);

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

test("the nearest point is the one Plot's pointer rule picks, at any size", () => {
  let seed = 7;
  const random = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  for (const [scatter, count] of [
    [false, 50],
    [false, 5000],
    [true, 50],
    [true, 5000],
  ]) {
    const data = Array.from({ length: count }, (_, t) => ({
      t: scatter ? random() * 100 : t,
      v: Math.sin(t / 40) * 100 + random() * 30,
    }));
    const mark = scatter ? Plot.dot : Plot.lineY;
    const reading = read({ marks: [mark(data, { x: "t", y: "v" })] });
    const [kx, ky] = reading.k;
    assert.deepEqual(reading.k, scatter ? [1, 1] : [1, 0.01]);
    for (let probe = 0; probe < 200; probe++) {
      const x = random() * 640;
      const y = random() * 400;
      let best = null;
      let reach = 40 * 40;
      for (const point of reading.points) {
        const distance = (kx * (point.x - x)) ** 2 + (ky * (point.y - y)) ** 2;
        if (distance <= reach) ((best = point), (reach = distance));
      }
      const found = nearest(reading, x, y);
      const distance = (point) =>
        point && (kx * (point.x - x)) ** 2 + (ky * (point.y - y)) ** 2;
      assert.equal(distance(found), distance(best), `${count} at ${x}, ${y}`);
    }
  }
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
