/* The points of a chart a reader reads one at a time: where each datum stands as Plot
 * drew it, which one a pointer or a finger aims at, the next one a key steps to, and
 * what each says.
 *
 * Plot draws the chart and owns its geometry; this reads it once per drawing, from the
 * render Plot gives every mark (its index and channels, scaled and raw:
 * `values.channels`, which Plot exposes for this), and keeps one point per datum under
 * the name Plot's render gives it, its mark, facet and index. A point stands where
 * Plot's pointer reads a datum (`anchorX`, `anchorY`): the middle of a band or an
 * extent, the mark's `frameAnchor` on an axis it has no channel for, and its facet's
 * offset; and then where the mark draws it, moved by its `dx` and `dy`, which Plot's
 * pointer leaves out.
 *
 * The pointer and a finger pick by Plot's pointer's rule (`pointerK`), each mark by its
 * own tip: the nearest of its points within 40px (the tip's `maxRadius`), along the
 * axis the tip names, or the axis its points stand at where it names none (a bar along
 * x, a horizontal bar along y, a dot in both), the other axis counting a hundredth
 * inside a facet's frame and whole outside it, each point measured from the tip's `px`
 * and `py` where it names them; then the marks' and facets' nearest compared whole, the
 * first of equals winning. Plot gets no tip to draw, and the page's preview says the
 * point (preview.js). Each move reads every point of the chart under the pointer, as
 * Plot's pointer does, and of no other.
 *
 * Plot's own pointer could do the picking. It would run against a stand-in for the svg
 * it listens on (`context.ownerSVGElement`) that hears only the pointer's moves, so it
 * never pins a pick on a press, and the chart would read each pick from the render the
 * pointer calls with it. That drives the pointer through a context Plot doesn't
 * document, and a faceted pick arrives a frame late, so this module copies the rule
 * instead. If Plot called a function with each pick, the chart could run Plot's own
 * pointer and delete the copy.
 *
 * A key steps through the points a reader reads: along a series, in the order its
 * points stand along the chart's axis in their facet, and across to the next series at
 * the place nearest along that axis, each facet's series its own. Points that stand
 * together and say the same, as a dot drawn on a line's own data, are one reading.
 * Each mark still picks its own points by its own rule, and a pick of any of them reads
 * as the first mark's point. Two points that say different things at one place are
 * both read. A datum keeps its point across drawings by its mark, its facet and its
 * channels' values, so a resize that drops other data leaves the reader where they
 * were.
 *
 * Which marks say their values: every line, area, bar, cell, dot and rect, the marks
 * that draw data, but not the rules, ticks and text that annotate it; or, where the
 * author gives any mark Plot's `tip` option, exactly those marks, which is how an author
 * takes a tip off a mark or gives one to a rule.
 *
 * What a point says: each channel Plot's tip would say, in its axes' words, the place
 * it stands at, then what it measures there. A place is a category or a time on an
 * axis, a facet, a series the marks are drawn in, or any value that isn't a number,
 * and reads as its value alone ("May 11, 2026 · backend"). Where both axes measure, as
 * in a scatter, x is the place and reads after its label ("week 6"). A measure reads
 * before its label ("8,412 offline sessions"), and a stacked one is the datum's own
 * share of the stack. A mark's `title` channel says something else: its first line in
 * place of the place, the rest beneath. A mark's tip `format` words its channels as
 * Plot's tip does: false leaves a channel out, and a function or a d3 format string
 * gives its words. The words keep their own order, the place first, rather than the
 * order of the format's keys. */

// The scales a datum stands at rather than measures on.
const PLACES = new Set(["band", "point", "ordinal", "utc", "time"]);
const CATEGORIES = new Set(["ordinal", "categorical"]);
// The channels a point says in their own way, its title and position, and those
// Plot's tip says nothing of (`ignoreChannels`).
const UNSAID = new Set([
  ...["title", "x", "x1", "x2", "y", "y1", "y2", "fx", "fy"],
  ...["geometry", "href", "src", "ariaLabel", "scales"],
]);
// Plot's pointer: how far a point may stand from the aim, and how little the axis a tip
// doesn't read along counts inside a frame.
const RADIUS = 40;
const SQUASH = 0.01;

/** @typedef {typeof import("/vendor/plot.esm.js")} PlotModule
 * @typedef {{type?: string, label?: string, bandwidth?: () => number, domain?: () => unknown[]} & ((value: unknown) => number)} Scale
 * @typedef {{value: ArrayLike<any>, scale?: string | null, defaultScale?: string, label?: string, hint?: {length?: boolean}, source?: Channel | null}} Channel
 * @typedef {{[key: string]: ArrayLike<number> | undefined} & {channels: {[key: string]: Channel | undefined}}} Values
 * @typedef {{[key: string]: Scale | undefined}} Scales
 * @typedef {{marginLeft: number, marginRight: number, marginTop: number, marginBottom: number, width: number, height: number}} Dimensions
 * @typedef {{[key: string]: false | ((value: any, i: number) => unknown)}} Format
 * @typedef {{values: Values, scales: Scales, fx: unknown, fy: unknown, left: number, bottom: number, number: (value: number) => string | undefined, format: Format}} Drawn
 * @typedef {{tx: number, ty: number, kx: number, ky: number, reach: number, frame: Dimensions, points: Point[]}} Frame
 * @typedef {{x: number, y: number, px: number, py: number, ax: number, ay: number, i: number, order: number, drawn: Drawn, series: number, n: number, said?: string, same?: Point}} Point
 * @typedef {{points: Point[], series: Point[][], frames: Frame[], axis: "x" | "y"}} Reading
 * @typedef {{maxRadius?: number, px?: unknown, py?: unknown, format?: unknown}} TipOptions
 * @typedef {import("@observablehq/plot").Mark & {data?: any, tip?: unknown, frameAnchor?: string, dx?: number, dy?: number, render: (...args: any[]) => any}} Drawable */

/** @param {Scale | undefined} scale */
const placed = (scale) => Boolean(scale?.type && PLACES.has(scale.type));

/** @param {PlotModule} Plot @param {unknown} marks @returns {Generator<Drawable>} */
function* marksIn(Plot, marks) {
  if (Array.isArray(marks)) for (const mark of marks) yield* marksIn(Plot, mark);
  else if (marks instanceof Plot.Mark) yield /** @type {Drawable} */ (marks);
}

// How much each axis counts in the distance to a mark's points: the axis its author's
// tip names (`pointerX`, `pointerY`, or both for `true`), or the axis its points stand
// at where it names none.
/** @param {PlotModule} Plot @param {Drawable} mark @param {unknown} tip @returns {[number, number]} */
function weights(Plot, mark, tip) {
  const pointer =
    typeof tip === "string"
      ? tip
      : tip
        ? /** @type {{pointer?: string}} */ (tip).pointer
        : mark instanceof Plot.BarX
          ? "y"
          : mark instanceof Plot.Dot
            ? "xy"
            : "x";
  return /^x$/i.test(pointer ?? "")
    ? [1, SQUASH]
    : /^y$/i.test(pointer ?? "")
      ? [SQUASH, 1]
      : [1, 1];
}

// Where a mark stands a datum on an axis it has no channel for: Plot's frame anchor
// (`applyFrameAnchor`), which its marks and its pointer read too.
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

/** Hooks the marks that say their values, before Plot draws them, so the reading `done`
 * returns holds their points once `Plot.plot` returns. Plot draws no tip for them.
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
  /** @type {Frame[]} */
  const frames = [];
  /** @type {Map<string, Point[]>} */
  const series = new Map();
  // The readings standing at each place, and once a second point stands there, each
  // by what it says, so a place many points share costs one reading of each.
  /** @type {Map<string, {first: Point, said?: Map<string, Point>}>} */
  const standing = new Map();
  /** @type {Scales | null} */
  let chart = null;
  tipped.forEach((mark, order) => {
    const option = mark.tip;
    mark.tip = null;
    const [kx, ky] = weights(Plot, mark, option);
    /** @type {TipOptions} */
    const tip = option && typeof option === "object" ? option : {};
    const radius = Number(tip.maxRadius ?? RADIUS);
    // The values a tip's `px` and `py` pick the mark's data by in place of where each
    // datum stands, read over its data as Plot's tip reads them.
    const [PX, PY] = [tip.px, tip.py].map((aim) =>
      aim == null ? null : Plot.valueof(mark.data, /** @type {any} */ (aim)),
    );
    const draw = mark.render;
    /** @this {Drawable} @param {any[]} args */
    mark.render = function (...args) {
      const node = draw.apply(this, args);
      const [index, scales, values, dimensions] =
        /** @type {[any, Scales, Values, Dimensions]} */ (args);
      if (!node || !index) return node;
      chart ??= scales;
      const { x, y, fx, fy } = scales;
      let tx = fx ? fx(index.fx) - dimensions.marginLeft : 0;
      let ty = fy ? fy(index.fy) - dimensions.marginTop : 0;
      if (x?.bandwidth) tx += x.bandwidth() / 2;
      if (y?.bandwidth) ty += y.bandwidth() / 2;
      const [cx, cy] = frameAnchored(this.frameAnchor, dimensions);
      const px = along(values.x1, values.x2, values.x, cx);
      const py = along(values.y1, values.y2, values.y, cy);
      const [dx, dy] = [Number(this.dx) || 0, Number(this.dy) || 0];
      /** @type {Frame} */
      const frame = {
        tx,
        ty,
        kx,
        ky,
        reach: radius * radius,
        frame: dimensions,
        points: [],
      };
      frames.push(frame);
      /** @type {Drawn} */
      const drawn = {
        values,
        scales,
        fx: index.fx,
        fy: index.fy,
        left: tx + dimensions.marginLeft,
        bottom: ty + dimensions.height - dimensions.marginBottom,
        number,
        format: formatting(Plot, tip.format, values.channels, scales),
      };
      const kind = seriesOf(values, scales);
      for (const i of index) {
        const local = { px: px(i), py: py(i) };
        const at = { x: local.px + tx + dx, y: local.py + ty + dy };
        if (!Number.isFinite(at.x) || !Number.isFinite(at.y)) continue;
        // Where an aim measures it from in its frame: the tip's own values, scaled as
        // Plot scales them, or where the mark draws it, its offsets included.
        const aim = {
          ax: PX && x ? x(PX[i]) : local.px + dx,
          ay: PY && y ? y(PY[i]) : local.py + dy,
        };
        /** @type {Point} */
        const point = { ...at, ...local, ...aim, i, order, drawn, series: 0, n: 0 };
        frame.points.push(point);
        const place = `${at.x},${at.y}`;
        const here = standing.get(place);
        if (!here) standing.set(place, { first: point });
        else {
          here.said ??= new Map([[saying(here.first), here.first]]);
          const same = here.said.get(saying(point));
          if (same) {
            point.same = same;
            continue;
          }
          here.said.set(saying(point), point);
        }
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
      const local = axis === "x" ? "px" : "py";
      /** @param {Point} a @param {Point} b */
      const order = (a, b) => a[local] - b[local];
      const runs = [...series.values()].filter((run) => run.length);
      runs.forEach((run, s) => {
        run.sort(order);
        run.forEach((point, n) => Object.assign(point, { series: s, n }));
      });
      return { points, series: runs, frames, axis };
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

// The words a tip's `format` gives the channels it names, as Plot's tip makes them
// (`getSourceChannels`): false or null leaves a channel out, a function says its
// value, and a string is d3's format for a number or its UTC format for a time. A
// format given alone is the title's.
/** @param {PlotModule} Plot @param {unknown} given @param {Values["channels"]} channels
 * @param {Scales} scales @returns {Format} */
function formatting(Plot, given, channels, scales) {
  /** @type {{[key: string]: unknown}} */
  const named =
    typeof given === "string" || typeof given === "function"
      ? { title: given }
      : { .../** @type {object} */ (given) };
  /** @type {Format} */
  const format = {};
  for (const [key, spec] of Object.entries(named)) {
    if (spec === false || spec === null) format[key] = false;
    else if (typeof spec === "function")
      format[key] = /** @type {(value: any, i: number) => unknown} */ (spec);
    else if (typeof spec === "string") {
      const values =
        (channels[key] ?? channels[`${key}1`] ?? channels[`${key}2`])?.value ??
        scales[key]?.domain?.() ??
        [];
      format[key] = /** @type {(value: any) => string} */ (
        temporal(values) ? Plot.d3UtcFormat(spec) : Plot.d3Format(spec)
      );
    }
  }
  return format;
}

// Whether a channel's values are times: its first that has one is (`isTemporal`).
/** @param {ArrayLike<unknown>} values */
function temporal(values) {
  for (let n = 0; n < values.length; n++)
    if (values[n] != null) return values[n] instanceof Date;
  return false;
}

// What a point says, kept on it once read.
/** @param {Point} point */
const saying = (point) => (point.said ??= JSON.stringify(sayPoint(point)));

/** The point nearest `x`, `y`, in the drawing's coordinates, by Plot's pointer's rule,
 * or null where none stands near enough.
 * @param {Reading} reading @param {number} x @param {number} y */
export function nearest({ frames }, x, y) {
  /** @type {Point | null} */
  let best = null;
  let bestReach = Infinity;
  for (const { tx, ty, kx, ky, reach, frame, points } of frames) {
    // The aim in its facet's frame as Plot's pointer measures it, and how much each
    // axis counts there.
    const [xf, yf] = [x - tx, y - ty];
    const kpx = xf < frame.marginLeft || xf > frame.width - frame.marginRight ? 1 : kx;
    const kpy = yf < frame.marginTop || yf > frame.height - frame.marginBottom ? 1 : ky;
    /** @type {Point | null} */
    let near = null;
    let within = reach;
    for (const point of points) {
      const ox = kpx * (point.ax - xf);
      const oy = kpy * (point.ay - yf);
      const distance = ox * ox + oy * oy;
      if (distance <= within) ((near = point), (within = distance));
    }
    if (!near) continue;
    const whole = (near.ax - xf) ** 2 + (near.ay - yf) ** 2;
    if (whole < bestReach) ((best = near), (bestReach = whole));
  }
  return best?.same ?? best;
}

// What names a point's datum across drawings: its mark, its facet and the values of
// its channels, as the data says them rather than as a drawing places them.
/** @param {Point} point */
function datumOf({ order, i, drawn }) {
  /** @param {unknown} value */
  const raw = (value) => (value instanceof Date ? value.getTime() : (value ?? null));
  return JSON.stringify([
    order,
    raw(drawn.fx),
    raw(drawn.fy),
    ...Object.entries(drawn.values.channels).map(([key, channel]) => [
      key,
      raw(channel?.value[i]),
    ]),
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

// Where `at` falls along `run`, sorted along `local`: the index of its first point
// there or beyond.
/** @param {Point[]} run @param {"px" | "py"} local @param {number} at */
function seek(run, local, at) {
  let lo = 0;
  for (let hi = run.length; lo < hi;) {
    const mid = (lo + hi) >>> 1;
    if (/** @type {Point} */ (run[mid])[local] < at) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/** The point `by` steps along `from`'s series, the first of the chart's where there is
 * none, or the series' first or last.
 * @param {Reading} reading @param {Point | null} from @param {number | "first" | "last"} by */
export function step({ series }, from, by) {
  const run = series[from?.series ?? 0] ?? [];
  const n =
    by === "first" ? 0 : by === "last" ? run.length - 1 : from ? from.n + by : 0;
  return run[Math.max(0, Math.min(run.length - 1, n))] ?? null;
}

/** The point of the series `by` away from `from`'s that stands nearest it along the
 * chart's axis, in its own facet, so a key crossing facets keeps its place.
 * @param {Reading} reading @param {Point | null} from @param {number} by */
export function cross(reading, from, by) {
  if (!from) return step(reading, null, 0);
  const run = reading.series[from.series + by];
  if (!run) return from;
  const local = reading.axis === "x" ? "px" : "py";
  const lo = seek(run, local, from[local]);
  const [before, after] = [run[lo - 1], run[lo]];
  if (!before) return after ?? from;
  if (!after) return before;
  return from[local] - before[local] <= after[local] - from[local] ? before : after;
}

/** What a point says: its name, where it stands, and its detail, what it measures
 * there, a line each.
 * @param {Point} point @returns {{name: string, detail: string[]}} */
export function sayPoint({ i, drawn }) {
  const { values, scales, format } = drawn;
  const { channels } = values;
  // A channel as Plot's tip reads it: the one an initializer moved it from, or none
  // where the initializer says it has none (`getSource`).
  /** @param {string} key */
  const source = (key) => {
    let channel = channels[key];
    while (channel?.source) channel = channel.source;
    return channel?.source === null ? undefined : channel;
  };
  // The author's format for a channel, an axis's naming its two ends too.
  /** @param {string} key */
  const formatOf = (key) => format[key] ?? format[key.replace(/^([xy])[12]$/, "$1")];
  /** @param {string} key @param {unknown} value @param {Scale} [scale] */
  const say = (key, value, scale) => {
    const given = formatOf(key);
    if (given) return String(given(value, i) ?? "");
    const temporal = scale?.type === "utc" || scale?.type === "time";
    if (value instanceof Date || (temporal && value != null))
      return sayDate(new Date(/** @type {any} */ (value)), scale?.type !== "time");
    // A number a category names, such as a year on a band, reads as written.
    if (typeof value === "number" && !placed(scale)) return drawn.number(value) ?? "";
    return value == null ? "" : String(value);
  };
  const title = formatOf("title") === false ? undefined : source("title");
  if (title) {
    const [first = "", ...rest] = say("title", title.value[i]).split("\n");
    return { name: first, detail: rest };
  }
  /** @type {Set<string>} */
  const places = new Set();
  /** @type {Set<string>} */
  const measures = new Set();
  /** @param {string} words @param {string | null | undefined} label */
  const measured = (words, label) => (label ? `${words} ${label}` : words);
  for (const [key, facet] of /** @type {const} */ ([
    ["fx", drawn.fx],
    ["fy", drawn.fy],
  ])) {
    const scale = scales[key];
    if (scale && formatOf(key) !== false) places.add(say(key, facet, scale));
  }
  const across = placed(scales.y) && !placed(scales.x);
  const [first, second] = across ? ["y", "x"] : ["x", "y"];
  for (const axis of [first, second]) {
    const scale = scales[axis];
    const ends = [`${axis}1`, `${axis}2`];
    const [low, high] = ends.map((key) =>
      formatOf(key) === false ? undefined : source(key),
    );
    const one = formatOf(axis) === false ? undefined : source(axis);
    const label = scale?.label ?? (one ?? high ?? low)?.label;
    /** @type {string} */
    let words;
    if (low && high)
      words = high.hint?.length
        ? say(`${axis}2`, high.value[i] - low.value[i])
        : `${say(`${axis}2`, low.value[i], scale)}–${say(`${axis}2`, high.value[i], scale)}`;
    else if (one) words = say(axis, one.value[i], scale);
    else if (low ?? high)
      words = say(low ? `${axis}1` : `${axis}2`, (low ?? high)?.value[i], scale);
    else continue;
    if (placed(scale)) places.add(words);
    else if (axis === first) places.add(label ? `${label} ${words}` : words);
    else measures.add(measured(words, label));
  }
  for (const key of Object.keys(channels)) {
    const channel =
      UNSAID.has(key) || formatOf(key) === false ? undefined : source(key);
    // A colour written as a colour says nothing of the datum.
    if (!channel || (channel.scale == null && channel.defaultScale === "color"))
      continue;
    const value = channel.value[i];
    if (value == null && channel.scale == null) continue;
    const scale = channel.scale ? scales[channel.scale] : undefined;
    const words = say(key, value, scale);
    if (
      key === "z" ||
      key === "symbol" ||
      typeof value !== "number" ||
      CATEGORIES.has(scale?.type ?? "")
    )
      places.add(words);
    else measures.add(measured(words, scale?.label ?? channel.label ?? key));
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
