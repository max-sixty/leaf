/* The points of a chart a reader reads one at a time: where Plot drew each datum of the
 * marks that say their values, the one nearest the pointer or a finger, the next one a
 * key steps to, and what each says.
 *
 * Plot decides where each datum stands, and tells this module through the render
 * transform it gives every mark: the index the mark draws and its channels, scaled and
 * raw (`values.channels`, which Plot exposes for this). The nearest point is found here
 * rather than by Plot's pointer transform, the one `tip: true` adds, which can't serve
 * three of the chart's needs: a key can't move it, it scans every point on every move,
 * and a press pins it until the next, where a press on Leaf puts a preview away. Its
 * rule is kept: the nearest point within 40px, measured mostly along the axis the
 * points stand at (Plot's `pointerX`), or across both in a scatter, dots on two
 * measures. The points are sorted along that axis once per drawing, so a move or a
 * step costs the same on a chart of fifty points as of five thousand: a binary search
 * and the few points as near along the axis as the nearest yet. A column of thousands
 * of dots at one place, as in a strip plot, still reads each of them.
 *
 * Which marks say their values: every line, area, bar, cell, dot and rect, the marks
 * that draw data, but not the rules, ticks and text that annotate it; or, where the
 * author gives any mark Plot's `tip` option, exactly those marks, which is how an author
 * takes a tip off a mark or gives one to a rule. Plot draws no tip of its own for them:
 * the page's preview says it (preview.js).
 *
 * What a point says, in its axes' words: the place it stands at, then what it measures
 * there. A place is a category or a time on an axis, a facet, or a series the marks are
 * drawn in, and reads as its value alone ("May 11, 2026 · backend"). Where both axes
 * measure, as in a scatter, x is the place and reads after its label ("week 6"). A
 * measure reads before its label ("8,412 offline sessions"), and a stacked one is the
 * datum's own share of the stack. A mark's `title` channel says something else: its
 * first line in place of the place, the rest beneath. */

// Plot's pointer: how far from the pointer a point may stand, and how little the other
// axis counts where the points stand along one.
const RADIUS = 40;
const SQUASH = 0.01;
// The scales a datum stands at rather than measures on.
const PLACES = new Set(["band", "point", "ordinal", "utc", "time"]);
const CATEGORIES = new Set(["ordinal", "categorical"]);
// The channels beside position that say something of a datum.
const BESIDE = ["z", "fill", "stroke", "symbol", "r", "opacity"];

/** @typedef {typeof import("@observablehq/plot")} PlotModule
 * @typedef {{type?: string, label?: string, bandwidth?: () => number} & ((value: unknown) => number)} Scale
 * @typedef {{value: ArrayLike<any>, scale?: string | null, label?: string, hint?: {length?: boolean}}} Channel
 * @typedef {{[key: string]: ArrayLike<number> | undefined} & {channels: {[key: string]: Channel | undefined}}} Values
 * @typedef {{[key: string]: Scale | undefined}} Scales
 * @typedef {{values: Values, scales: Scales, fx: unknown, fy: unknown, left: number, bottom: number, number: (value: number) => string | undefined}} Drawn
 * @typedef {{x: number, y: number, i: number, drawn: Drawn, series: number, n: number}} Point
 * @typedef {{points: Point[], series: Point[][], axis: "x" | "y", k: [number, number]}} Reading
 * @typedef {import("@observablehq/plot").Mark & {tip?: unknown, render: (...args: any[]) => any}} Drawable */

/** @param {Scale | undefined} scale */
const placed = (scale) => Boolean(scale?.type && PLACES.has(scale.type));

/** @param {PlotModule} Plot @param {unknown} marks @returns {Generator<Drawable>} */
function* marksIn(Plot, marks) {
  if (Array.isArray(marks)) for (const mark of marks) yield* marksIn(Plot, mark);
  else if (marks instanceof Plot.Mark) yield /** @type {Drawable} */ (marks);
}

/** Hooks the marks that say their values, before Plot draws them, so the reading this
 * returns holds their points once `Plot.plot` returns; `done` then orders them.
 * @param {PlotModule} Plot @param {unknown} marks */
export function readPoints(Plot, marks) {
  const all = [...marksIn(Plot, marks)];
  const asked = all.filter((mark) => mark.tip);
  const drawsData = [
    Plot.Area,
    Plot.BarX,
    Plot.BarY,
    Plot.Cell,
    Plot.Dot,
    Plot.Line,
    Plot.Rect,
  ];
  const tipped = asked.length
    ? asked
    : all.filter((mark) => drawsData.some((kind) => mark instanceof kind));
  for (const mark of asked) mark.tip = null;
  const number = Plot.formatNumber();
  /** @type {Point[]} */
  const points = [];
  /** @type {Map<unknown, Point[]>} */
  const series = new Map();
  const seen = new Set();
  /** @type {Scales | null} */
  let chart = null;
  tipped.forEach((mark, order) => {
    const draw = mark.render;
    /** @this {Drawable} @param {any[]} args */
    mark.render = function (...args) {
      const node = draw.apply(this, args);
      const [index, scales, values, dimensions] =
        /** @type {[any, Scales, Values, any]} */ (args);
      if (!node || !index) return node;
      chart ??= scales;
      const { x, y, fx, fy } = scales;
      const { marginLeft, marginRight, marginTop, marginBottom, width, height } =
        dimensions;
      // Where Plot's pointer takes a datum to stand (its `anchorX`, `anchorY`): a facet's
      // offset, the middle of a band, the middle of an extent, or the frame's middle
      // on an axis the mark has no channel for.
      let tx = fx ? fx(index.fx) - marginLeft : 0;
      let ty = fy ? fy(index.fy) - marginTop : 0;
      if (x?.bandwidth) tx += x.bandwidth() / 2;
      if (y?.bandwidth) ty += y.bandwidth() / 2;
      const px = along(
        values.x1,
        values.x2,
        values.x,
        (marginLeft + width - marginRight) / 2,
      );
      const py = along(
        values.y1,
        values.y2,
        values.y,
        (marginTop + height - marginBottom) / 2,
      );
      /** @type {Drawn} */
      const drawn = {
        values,
        scales,
        fx: index.fx,
        fy: index.fy,
        left: tx + marginLeft,
        bottom: ty + height - marginBottom,
        number,
      };
      const kind = seriesOf(values, scales);
      for (const i of index) {
        const at = { x: px(i) + tx, y: py(i) + ty };
        if (!Number.isFinite(at.x) || !Number.isFinite(at.y)) continue;
        const one = kind ? kind[i] : undefined;
        // A dot drawn on a line's own data, or a second mark over the same rows, adds no
        // point a reader could tell from the first.
        const key = `${at.x},${at.y},${String(one)}`;
        if (seen.has(key)) continue;
        seen.add(key);
        const run = kind ? `series ${String(one)}` : order;
        if (!series.has(run)) series.set(run, []);
        const point = { ...at, i, drawn, series: 0, n: 0 };
        points.push(point);
        series.get(run)?.push(point);
      }
      return node;
    };
  });
  return {
    /** @returns {Reading} */
    done() {
      const across = placed(chart?.y) && !placed(chart?.x);
      // A scatter, dots on two measures, reads the dot nearest in both.
      const scatter =
        !placed(chart?.x) &&
        !placed(chart?.y) &&
        tipped.every((mark) => mark instanceof Plot.Dot);
      const axis = across ? "y" : "x";
      /** @param {Point} a @param {Point} b */
      const order = (a, b) => a[axis] - b[axis];
      const runs = [...series.values()].filter((run) => run.length);
      runs.forEach((run, s) => {
        run.sort(order);
        run.forEach((point, n) => Object.assign(point, { series: s, n }));
      });
      return {
        points: points.sort(order),
        series: runs,
        axis,
        k: scatter ? [1, 1] : across ? [SQUASH, 1] : [1, SQUASH],
      };
    },
  };
}

/** @param {ArrayLike<number> | undefined} V1 @param {ArrayLike<number> | undefined} V2
 * @param {ArrayLike<number> | undefined} V @param {number} middle */
const along = (V1, V2, V = V1, middle) =>
  V1 && V2
    ? (/** @type {number} */ i) => ((V1[i] ?? NaN) + (V2[i] ?? NaN)) / 2
    : V
      ? (/** @type {number} */ i) => V[i] ?? NaN
      : () => middle;

// The series a mark's datum is drawn in: its z, or the category its colour names.
/** @param {Values} values @param {Scales} scales */
function seriesOf({ channels }, scales) {
  if (channels.z) return channels.z.value;
  for (const key of ["fill", "stroke"]) {
    const channel = channels[key];
    const type = channel?.scale ? scales[channel.scale]?.type : undefined;
    if (channel && type && CATEGORIES.has(type)) return channel.value;
  }
  return null;
}

// Where `at` falls along `run`, sorted along `axis`: the index of its first point there
// or beyond.
/** @param {Point[]} run @param {"x" | "y"} axis @param {number} at */
function seek(run, axis, at) {
  let lo = 0;
  for (let hi = run.length; lo < hi;) {
    const mid = (lo + hi) >>> 1;
    if (/** @type {Point} */ (run[mid])[axis] < at) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/** The point nearest `x`, `y` in the drawing's own coordinates, within Plot's reach.
 * @param {Reading} reading @param {number} x @param {number} y */
export function nearest({ points, axis, k: [kx, ky] }, x, y) {
  const at = axis === "x" ? x : y;
  const lo = seek(points, axis, at);
  /** @type {Point | null} */
  let best = null;
  let reach = RADIUS * RADIUS;
  // Outward from where the pointer stands along the axis, until a point is further
  // along it than the nearest yet is in all.
  /** @param {number} j */
  const near = (j) => {
    const point = /** @type {Point} */ (points[j]);
    const off = point[axis] - at;
    if (off * off > reach) return false;
    const dx = kx * (point.x - x);
    const dy = ky * (point.y - y);
    const distance = dx * dx + dy * dy;
    if (distance <= reach) ((best = point), (reach = distance));
    return true;
  };
  for (let j = lo; j < points.length && near(j); j++);
  for (let j = lo - 1; j >= 0 && near(j); j--);
  return best;
}

/** The point `by` steps along `from`'s series, the first of the chart's where there is
 * none, or the series' first or last.
 * @param {Reading} reading @param {Point | null} from @param {number | "first" | "last"} by */
export function step({ series }, from, by) {
  const run = series[from?.series ?? 0] ?? [];
  const n = by === "first" || !from ? 0 : by === "last" ? run.length - 1 : from.n + by;
  return run[Math.max(0, Math.min(run.length - 1, n))] ?? null;
}

/** The point of the series `by` away from `from`'s that stands nearest it along the axis.
 * @param {Reading} reading @param {Point | null} from @param {number} by */
export function cross(reading, from, by) {
  if (!from) return step(reading, null, 0);
  const run = reading.series[from.series + by];
  if (!run) return from;
  const { axis } = reading;
  const lo = seek(run, axis, from[axis]);
  const [before, after] = [run[lo - 1], run[lo]];
  if (!before) return after ?? from;
  if (!after) return before;
  return from[axis] - before[axis] <= after[axis] - from[axis] ? before : after;
}

/** What a point says: its name, where it stands, and its detail, what it measures
 * there, a line each.
 * @param {Point} point @returns {{name: string, detail: string[]}} */
export function sayPoint({ i, drawn }) {
  const { values, scales } = drawn;
  const { channels } = values;
  /** @param {unknown} value @param {Scale} [scale] */
  const say = (value, scale) => {
    const temporal = scale?.type === "utc" || scale?.type === "time";
    if (value instanceof Date || (temporal && value != null))
      return sayDate(new Date(/** @type {any} */ (value)), scale?.type !== "time");
    // A number a category names, such as a year on a band, reads as written.
    if (typeof value === "number" && !placed(scale)) return drawn.number(value) ?? "";
    return value == null ? "" : String(value);
  };
  if (channels.title) {
    const [first = "", ...rest] = say(channels.title.value[i]).split("\n");
    return { name: first, detail: rest };
  }
  /** @type {Set<string>} */
  const places = new Set();
  /** @type {Set<string>} */
  const measures = new Set();
  /** @param {string} words @param {string | null | undefined} label */
  const measured = (words, label) => (label ? `${words} ${label}` : words);
  for (const [facet, scale] of [
    [drawn.fx, scales.fx],
    [drawn.fy, scales.fy],
  ])
    if (scale) places.add(say(facet, /** @type {Scale} */ (scale)));
  const across = placed(scales.y) && !placed(scales.x);
  const [first, second] = across ? ["y", "x"] : ["x", "y"];
  for (const axis of [first, second]) {
    const scale = scales[axis];
    const one = channels[axis];
    const low = channels[`${axis}1`];
    const high = channels[`${axis}2`];
    const label = scale?.label ?? (one ?? high ?? low)?.label;
    /** @type {string} */
    let words;
    if (low && high)
      words = high.hint?.length
        ? say(high.value[i] - low.value[i])
        : `${say(low.value[i], scale)}–${say(high.value[i], scale)}`;
    else if (one ?? low ?? high) words = say((one ?? low ?? high)?.value[i], scale);
    else continue;
    if (placed(scale)) places.add(words);
    else if (axis === first) places.add(label ? `${label} ${words}` : words);
    else measures.add(measured(words, label));
  }
  for (const key of BESIDE) {
    const channel = channels[key];
    // A colour written as a colour says nothing of the datum.
    if (!channel || ((key === "fill" || key === "stroke") && !channel.scale)) continue;
    const scale = channel.scale ? scales[channel.scale] : undefined;
    const words = say(channel.value[i], scale);
    if (key === "z" || key === "symbol" || CATEGORIES.has(scale?.type ?? ""))
      places.add(words);
    else measures.add(measured(words, scale?.label ?? channel.label));
  }
  places.delete("");
  measures.delete("");
  const place = [...places].join(" · ");
  const measure = [...measures].join(" · ");
  if (!place) return { name: measure, detail: [] };
  return { name: place, detail: measure ? [measure] : [] };
}

// A time as a reader says it, at the precision the datum has: the day, and the time of
// day where it has one, in the zone its scale reads it in.
/** @param {Date} date @param {boolean} utc */
function sayDate(date, utc) {
  const clock = utc
    ? date.getUTCHours() + date.getUTCMinutes() + date.getUTCSeconds()
    : date.getHours() + date.getMinutes() + date.getSeconds();
  return date.toLocaleString("en-US", {
    timeZone: utc ? "UTC" : undefined,
    year: "numeric",
    month: "short",
    day: "numeric",
    ...(clock ? { hour: "numeric", minute: "2-digit" } : {}),
    ...(clock && utc ? { timeZoneName: "short" } : {}),
  });
}
