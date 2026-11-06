/* The points of a chart a reader reads one at a time: which one a pointer or a finger
 * aims at, the next one a key steps to, where each stands, and what each says.
 *
 * Plot's own pointer picks the point a pointer or a finger aims at, the one Plot's
 * `tip` option asks for, by Plot's rules: the nearest within 40px, along the axis a
 * mark's tip names (`pointerX`, `pointerY`) or across both, each facet in its own frame
 * and the facets' nearest compared whole. Plot draws no tip of its own: each mark's tip
 * is given a render that draws nothing and reports the point Plot picked, and the
 * page's preview says it (preview.js). The tip reads each point where its mark draws
 * it, so it takes the mark's `frameAnchor`, which Plot's own tip leaves at the frame's
 * middle: a `dotX` along the foot of its frame is read there. A mark with no tip
 * named reads along the axis its points stand at: a bar along x, a horizontal bar along
 * y, a dot in both. Each move costs what Plot's pointer scans, the points of the chart
 * under it, which the window shows.
 *
 * A key can't move Plot's pointer, so the keyboard steps through the points itself:
 * along a series, in the order the series stands along its axis, and across to the
 * next series, each facet's series its own. It reads each point where Plot's pointer
 * does, from the render Plot gives every mark (its index and channels, scaled and raw:
 * `values.channels`, which Plot exposes for this): the middle of a band or an extent,
 * the mark's frame anchor on an axis it has no channel for, and its facet's offset.
 * Points that stand together and say the same, as a dot drawn on a line's own data,
 * are one point; two that say different things at one place are both read.
 *
 * Which marks say their values: every line, area, bar, cell, dot and rect, the marks
 * that draw data, but not the rules, ticks and text that annotate it; or, where the
 * author gives any mark Plot's `tip` option, exactly those marks, which is how an author
 * takes a tip off a mark or gives one to a rule.
 *
 * What a point says, in its axes' words: the place it stands at, then what it measures
 * there. A place is a category or a time on an axis, a facet, or a series the marks are
 * drawn in, and reads as its value alone ("May 11, 2026 · backend"). Where both axes
 * measure, as in a scatter, x is the place and reads after its label ("week 6"). A
 * measure reads before its label ("8,412 offline sessions"), and a stacked one is the
 * datum's own share of the stack. A mark's `title` channel says something else: its
 * first line in place of the place, the rest beneath. */

const SVG = "http://www.w3.org/2000/svg";
// The scales a datum stands at rather than measures on.
const PLACES = new Set(["band", "point", "ordinal", "utc", "time"]);
const CATEGORIES = new Set(["ordinal", "categorical"]);
// The channels beside position that say something of a datum.
const BESIDE = ["z", "fill", "stroke", "symbol", "r", "opacity"];
// The channels that place a datum, which name it across drawings.
const POSITION = ["x", "x1", "x2", "y", "y1", "y2"];

/** @typedef {typeof import("@observablehq/plot")} PlotModule
 * @typedef {{type?: string, label?: string, bandwidth?: () => number} & ((value: unknown) => number)} Scale
 * @typedef {{value: ArrayLike<any>, scale?: string | null, label?: string, hint?: {length?: boolean}}} Channel
 * @typedef {{[key: string]: ArrayLike<number> | undefined} & {channels: {[key: string]: Channel | undefined}}} Values
 * @typedef {{[key: string]: Scale | undefined}} Scales
 * @typedef {{marginLeft: number, marginRight: number, marginTop: number, marginBottom: number, width: number, height: number}} Dimensions
 * @typedef {{values: Values, scales: Scales, fx: unknown, fy: unknown, left: number, bottom: number, number: (value: number) => string | undefined}} Drawn
 * @typedef {{x: number, y: number, i: number, order: number, drawn: Drawn, series: number, n: number}} Point
 * @typedef {{points: Point[], series: Point[][], axis: "x" | "y", picks: Map<string, Point | null>, whenPicked: (picked: () => void) => void}} Reading
 * @typedef {import("@observablehq/plot").Mark & {tip?: unknown, frameAnchor?: string, render: (...args: any[]) => any}} Drawable */

/** @param {Scale | undefined} scale */
const placed = (scale) => Boolean(scale?.type && PLACES.has(scale.type));

/** @param {PlotModule} Plot @param {unknown} marks @returns {Generator<Drawable>} */
function* marksIn(Plot, marks) {
  if (Array.isArray(marks)) for (const mark of marks) yield* marksIn(Plot, mark);
  else if (marks instanceof Plot.Mark) yield /** @type {Drawable} */ (marks);
}

// The axis a mark's pointer reads along where its author named none.
/** @param {PlotModule} Plot @param {Drawable} mark */
const pointerOf = (Plot, mark) =>
  mark instanceof Plot.BarX ? "y" : mark instanceof Plot.Dot ? "xy" : "x";

// Where a mark stands a datum on an axis it has no channel for: Plot's frame anchor
// (`applyFrameAnchor`), which its pointer and its marks read too.
/** @param {string | undefined} anchor @param {Dimensions} dimensions
 * @returns {[number, number]} */
function frameAnchored(anchor = "middle", dimensions) {
  const { marginLeft, marginRight, marginTop, marginBottom, width, height } =
    dimensions;
  return [
    /left$/.test(anchor)
      ? marginLeft
      : /right$/.test(anchor)
        ? width - marginRight
        : (marginLeft + width - marginRight) / 2,
    /^top/.test(anchor)
      ? marginTop
      : /^bottom/.test(anchor)
        ? height - marginBottom
        : (marginTop + height - marginBottom) / 2,
  ];
}

/** @param {number} order @param {unknown} facet @param {number} i */
const nameOf = (order, facet, i) => `${order}:${String(facet ?? "")}:${i}`;

/** Hooks the marks that say their values, before Plot draws them, so the reading `done`
 * returns holds their points once `Plot.plot` returns, and Plot's pointer reports into
 * its `picks` as the pointer moves.
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
  const number = Plot.formatNumber();
  /** @type {Point[]} */
  const points = [];
  /** @type {Map<string, Point[]>} */
  const series = new Map();
  // Each datum's point by the name Plot's pointer gives it, its mark, facet and index,
  // and the points that stand at each place.
  /** @type {Map<string, Point>} */
  const named = new Map();
  /** @type {Map<string, Point[]>} */
  const standing = new Map();
  /** @type {Map<string, Point | null>} */
  const picks = new Map();
  let picked = () => {};
  /** @type {Scales | null} */
  let chart = null;
  tipped.forEach((mark, order) => {
    const authored = mark.tip;
    const options = authored && typeof authored === "object" ? authored : {};
    mark.tip = {
      frameAnchor: mark.frameAnchor,
      ...options,
      pointer:
        typeof authored === "string"
          ? authored
          : authored
            ? /** @type {{pointer?: string}} */ (options).pointer
            : pointerOf(Plot, mark),
      // Plot's pointer renders the tip again for each point it picks, `I` holding it,
      // and puts what this returns in place of the last: a group naming the point, so
      // each swap writes something.
      render: (/** @type {number[] & {fi?: unknown}} */ I) => {
        const at = I[0];
        const name = at === undefined ? null : nameOf(order, I.fi, at);
        // Each facet's pointer holds its own pick, as Plot shows them.
        picks.set(
          `${order}:${String(I.fi ?? "")}`,
          name === null ? null : (named.get(name) ?? null),
        );
        picked();
        const node = document.createElementNS(SVG, "g");
        if (name !== null) node.setAttribute("data-lf-point", name);
        return node;
      },
    };
    const draw = mark.render;
    /** @this {Drawable} @param {any[]} args */
    mark.render = function (...args) {
      const node = draw.apply(this, args);
      const [index, scales, values, dimensions] =
        /** @type {[any, Scales, Values, Dimensions]} */ (args);
      if (!node || !index) return node;
      chart ??= scales;
      const { x, y, fx, fy } = scales;
      // Where Plot's pointer reads a datum (`pointerK`, `anchorX`, `anchorY`): its
      // facet's offset, the middle of a band, the middle of an extent, or the frame
      // anchor on an axis the mark has no channel for.
      let tx = fx ? fx(index.fx) - dimensions.marginLeft : 0;
      let ty = fy ? fy(index.fy) - dimensions.marginTop : 0;
      if (x?.bandwidth) tx += x.bandwidth() / 2;
      if (y?.bandwidth) ty += y.bandwidth() / 2;
      const [cx, cy] = frameAnchored(this.frameAnchor, dimensions);
      const px = along(values.x1, values.x2, values.x, cx);
      const py = along(values.y1, values.y2, values.y, cy);
      /** @type {Drawn} */
      const drawn = {
        values,
        scales,
        fx: index.fx,
        fy: index.fy,
        left: tx + dimensions.marginLeft,
        bottom: ty + dimensions.height - dimensions.marginBottom,
        number,
      };
      const kind = seriesOf(values, scales);
      for (const i of index) {
        const at = { x: px(i) + tx, y: py(i) + ty };
        if (!Number.isFinite(at.x) || !Number.isFinite(at.y)) continue;
        /** @type {Point} */
        const point = { ...at, i, order, drawn, series: 0, n: 0 };
        const name = nameOf(order, index.fi, i);
        const place = `${at.x},${at.y}`;
        const here = standing.get(place) ?? [];
        const same = here.find((other) => saysAlike(other, point));
        if (same) {
          named.set(name, same);
          continue;
        }
        standing.set(place, [...here, point]);
        named.set(name, point);
        points.push(point);
        const run = `${String(index.fi ?? "")}|${kind ? `series ${String(kind[i])}` : order}`;
        if (!series.has(run)) series.set(run, []);
        series.get(run)?.push(point);
      }
      return node;
    };
  });
  return {
    /** @returns {Reading} */
    done() {
      const axis = placed(chart?.y) && !placed(chart?.x) ? "y" : "x";
      /** @param {Point} a @param {Point} b */
      const order = (a, b) => a[axis] - b[axis];
      const runs = [...series.values()].filter((run) => run.length);
      runs.forEach((run, s) => {
        run.sort(order);
        run.forEach((point, n) => Object.assign(point, { series: s, n }));
      });
      return {
        points,
        series: runs,
        axis,
        picks,
        whenPicked: (then) => (picked = then),
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

/** @param {Point} a @param {Point} b */
const saysAlike = (a, b) => JSON.stringify(sayPoint(a)) === JSON.stringify(sayPoint(b));

// What names a point's datum across drawings: its mark, its facet, its series and
// where its channels place it, as the data says them rather than as a drawing does.
/** @param {Point} point */
function datumOf({ order, i, drawn }) {
  const { channels } = drawn.values;
  const raw = (/** @type {unknown} */ value) =>
    value instanceof Date ? value.getTime() : (value ?? null);
  return JSON.stringify([
    order,
    raw(drawn.fx),
    raw(drawn.fy),
    ...[...POSITION, "z"].map((key) => raw(channels[key]?.value[i])),
  ]);
}

/** The point of `reading` holding the datum `point` held in an earlier drawing, if it
 * still draws it.
 * @param {Reading} reading @param {Point} point */
export function sameDatum(reading, point) {
  const datum = datumOf(point);
  return (
    reading.points.find(
      (other) => other.order === point.order && datumOf(other) === datum,
    ) ?? null
  );
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
// day where it has one, to the second or the millisecond where it is that fine, in the
// zone its scale reads it in.
/** @param {Date} date @param {boolean} utc */
function sayDate(date, utc) {
  const [hours, minutes, seconds] = utc
    ? [date.getUTCHours(), date.getUTCMinutes(), date.getUTCSeconds()]
    : [date.getHours(), date.getMinutes(), date.getSeconds()];
  const fine = date.getMilliseconds();
  const clock = hours || minutes || seconds || fine;
  return date.toLocaleString("en-US", {
    timeZone: utc ? "UTC" : undefined,
    year: "numeric",
    month: "short",
    day: "numeric",
    ...(clock ? { hour: "numeric", minute: "2-digit" } : {}),
    ...(seconds || fine ? { second: "2-digit" } : {}),
    ...(fine ? { fractionalSecondDigits: 3 } : {}),
    ...(clock && utc ? { timeZoneName: "short" } : {}),
  });
}
