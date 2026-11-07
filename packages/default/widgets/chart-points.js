/* The points of a chart a reader reads one at a time: where each datum stands as Plot
 * drew it, which one a pointer or a finger aims at, the next one a key steps to, and
 * what each says.
 *
 * Plot draws the chart and owns its geometry, and what a mark's tip reads of it. So
 * each mark that says its values gets the tip Plot would give it (`inferTips`), built
 * from Plot's own `tip`, `pointer` and `initializer`, except that Plot's pointer gives
 * it no listener and it draws nothing: the mark itself has no `tip`, so Plot draws
 * none, and the page's preview says the point (preview.js). Plot hands that tip what
 * it hands its own: the mark's index and channels, scaled and raw (`values.channels`),
 * and its tip's `px` and `py` channels with every transform their scale applies. This
 * reads them once per drawing and keeps one point per datum under the name Plot gives
 * it, its mark, facet and index. A point stands where Plot's pointer reads a datum
 * (`anchorX`, `anchorY`): the middle of a band or an extent, the mark's `frameAnchor`
 * on an axis it has no channel for, and its facet's offset; and then where the mark
 * draws it, moved by its `dx` and `dy`, which Plot's pointer leaves out.
 *
 * The pointer and a finger pick by Plot's pointer's rule (`pointerK`), each mark by its
 * own tip: the nearest of its points within 40px (the tip's `maxRadius`), along the
 * axis the tip names, or the axis its points stand at where it names none (a bar along
 * x, a horizontal bar along y, a dot in both), the other axis counting a hundredth
 * inside a facet's frame and whole outside it, each point measured from the tip's `px`
 * and `py` where it names them; then the marks' and facets' nearest compared whole, the
 * first of equals winning. Each move reads every point of the chart under the pointer,
 * as Plot's pointer does, and of no other.
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
 * What a point says: the rows Plot's tip says (`tipSources` and `tipRows`, Plot's
 * `getSourceChannels` and `formatChannels`), a line each, its label then its value as
 * Plot's tip draws it ("week 6", "offline sessions 8,412"), each label said once as
 * Plot's tip says it. Where the point stands comes first, its facets, the axis it
 * stands along and the series it is drawn in; then what it measures, a number on a
 * scale it doesn't stand at, a stacked one the datum's own share of the stack. Where
 * both axes measure, as in a scatter, x is where it stands. A mark's `title` channel
 * says something else: its first line as the name, the rest beneath. A channel the
 * tip's `format` words reads as that format, which Plot turns into a function as it
 * does for its own tip; the others read as a reader says them, a time as a date rather
 * than Plot's ISO date.
 *
 * Rejected: a measure's value before its label ("8,412 offline sessions"). A chart with
 * generic labels then alternated "x 2" with "2 y", a long label such as "share of
 * checkout traffic (%)" read awkwardly after its number, and the author had to label
 * each axis by what it counts for the line to read at all. */

// The scales a datum stands at rather than measures on.
const PLACES = new Set(["band", "point", "ordinal", "utc", "time"]);
const CATEGORIES = new Set(["ordinal", "categorical"]);
// Plot's pointer: how far a point may stand from the aim, and how little the axis a tip
// doesn't read along counts inside a frame.
const RADIUS = 40;
const SQUASH = 0.01;

/** @typedef {typeof import("/vendor/plot.esm.js")} PlotBundle
 * @typedef {PlotBundle["Plot"]} PlotModule
 * @typedef {{type?: string, label?: string, bandwidth?: () => number} & ((value: unknown) => number)} Scale
 * @typedef {{value: ArrayLike<any>, scale?: string | null, label?: string, hint?: {length?: boolean}}} Channel
 * @typedef {{[key: string]: ArrayLike<number> | undefined} & {channels: {[key: string]: Channel | undefined}}} Values
 * @typedef {{[key: string]: Scale | undefined}} Scales
 * @typedef {{marginLeft: number, marginRight: number, marginTop: number, marginBottom: number, width: number, height: number}} Dimensions
 * @typedef {{[key: string]: Channel | true | undefined}} Sources
 * @typedef {{[key: string]: unknown}} Format
 * @typedef {{key: string, label?: string | null, value?: unknown}} Row
 * @typedef {{values: Values, scales: Scales, fx: unknown, fy: unknown, left: number, bottom: number, number: (value: number) => string | undefined, sources: Sources, format: Format, authored: Format, rows: (this: {format: Format}, i: number, index: {fx?: unknown, fy?: unknown}, sources: Sources, scales: Scales, values: Values) => Iterable<Row>}} Drawn
 * @typedef {{tx: number, ty: number, kx: number, ky: number, reach: number, frame: Dimensions, points: Point[]}} Frame
 * @typedef {{x: number, y: number, px: number, py: number, ax: number, ay: number, i: number, order: number, drawn: Drawn, series: number, n: number, said?: string, same?: Point}} Point
 * @typedef {{points: Point[], series: Point[][], frames: Frame[], axis: "x" | "y"}} Reading
 * @typedef {import("@observablehq/plot").Mark & {data?: any, tip?: unknown, facet?: unknown, facetAnchor?: unknown, format: Format, frameAnchor?: string, dx?: number, dy?: number}} Drawable */

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

/** The marks that read the points of `marks` that say their values, to draw beside
 * them, so the reading `done` returns holds their points once `Plot.plot` returns.
 * Plot draws no tip for them.
 * @param {PlotBundle} bundle @param {unknown} marks */
export function readPoints({ Plot, tipSources, tipRows }, marks) {
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
  // Each mark's tip as Plot builds it from the mark's `tip` option (`inferTips`): the
  // mark's data and, through an initializer, its channels; Plot's pointer's `px` and
  // `py` channels, without the pointer itself; and in place of its drawing, a reading.
  const readers = tipped.map((mark, order) => {
    const given = mark.tip;
    mark.tip = null;
    const [kx, ky] = weights(Plot, mark, given);
    /** @type {{[key: string]: unknown}} */
    const options =
      typeof given === "string"
        ? { pointer: given }
        : given === true || !given
          ? {}
          : { ...given };
    const reach = Number(options.maxRadius ?? RADIUS) ** 2;
    const derived = Plot.initializer(
      { ...options, x: null, y: null },
      (data, facets, channels, scales, dimensions, context) =>
        /** @type {any} */ (context).getMarkState(mark),
    );
    const {
      render: _pointer,
      channels,
      ...tipOptions
    } = /** @type {{render?: unknown, channels?: {[key: string]: any}}} */ (
      Plot.pointer(derived)
    );
    // A datum with no `px` or `py` is drawn all the same, so it stays in the reading,
    // for the keys to reach; only the pointer passes it by, as Plot's does.
    const { px, py } = channels ?? {};
    const reader = Plot.tip(mark.data, {
      ...tipOptions,
      channels: {
        ...channels,
        ...(px && { px: { ...px, filter: null } }),
        ...(py && { py: { ...py, filter: null } }),
      },
      title: null,
      render: /** @type {any} */ (read),
    });
    const tip = /** @type {Drawable} */ (/** @type {unknown} */ (reader));
    tip.facet = mark.facet;
    tip.facetAnchor = mark.facetAnchor;
    const authored = { ...tip.format };
    return reader;

    /** @this {Drawable} @param {any} index @param {Scales} scales @param {Values} values
     * @param {Dimensions} dimensions */
    function read(index, scales, values, dimensions) {
      if (!index) return null;
      chart ??= scales;
      const { x, y, fx, fy } = scales;
      let tx = fx ? fx(index.fx) - dimensions.marginLeft : 0;
      let ty = fy ? fy(index.fy) - dimensions.marginTop : 0;
      if (x?.bandwidth) tx += x.bandwidth() / 2;
      if (y?.bandwidth) ty += y.bandwidth() / 2;
      const [cx, cy] = frameAnchored(mark.frameAnchor, dimensions);
      const px = along(values.x1, values.x2, values.x, cx);
      const py = along(values.y1, values.y2, values.y, cy);
      const [dx, dy] = [Number(mark.dx) || 0, Number(mark.dy) || 0];
      const { px: PX, py: PY } = values;
      /** @type {Frame} */
      const frame = { tx, ty, kx, ky, reach, frame: dimensions, points: [] };
      frames.push(frame);
      const { channels } = values;
      /** @type {Drawn} */
      const drawn = {
        values,
        scales,
        fx: index.fx,
        fy: index.fy,
        left: tx + dimensions.marginLeft,
        bottom: ty + dimensions.height - dimensions.marginBottom,
        number,
        // As Plot's tip reads them: its title alone where the mark has one.
        sources: /** @type {Sources} */ (
          tipSources.call(
            this,
            "title" in values ? { title: channels.title } : channels,
            scales,
          )
        ),
        format: this.format,
        authored,
        rows: tipRows,
      };
      const kind = seriesOf(values, scales);
      for (const i of index) {
        const local = { px: px(i), py: py(i) };
        const at = { x: local.px + tx + dx, y: local.py + ty + dy };
        if (!Number.isFinite(at.x) || !Number.isFinite(at.y)) continue;
        // Where an aim measures it from in its frame: the tip's own values, scaled as
        // Plot scales them, or where the mark draws it, its offsets included.
        const aim = {
          ax: PX ? (PX[i] ?? NaN) : local.px + dx,
          ay: PY ? (PY[i] ?? NaN) : local.py + dy,
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
      return null;
    }
  });
  return {
    marks: readers,
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
  const { scales, sources, format, authored } = drawn;
  /** @param {string} key */
  const axisOf = (key) => /^([xy])[12]?$/.exec(key)?.[1];
  // The scale a channel's value stands on: its axis's, its facet's or its own.
  /** @param {string} key */
  const scaleOf = (key) => {
    const channel = sources[key];
    const name = axisOf(key) ?? (channel === true ? key : channel?.scale);
    return name ? scales[name] : undefined;
  };
  /** @param {unknown} value @param {Scale} [scale] */
  const say = (value, scale) => {
    const temporal = scale?.type === "utc" || scale?.type === "time";
    if (value instanceof Date || (temporal && value != null))
      return sayDate(new Date(/** @type {any} */ (value)), scale?.type !== "time");
    // A number a category names, such as a year on a band, reads as written.
    if (typeof value === "number" && !placed(scale)) return drawn.number(value) ?? "";
    return value == null ? "" : String(value);
  };
  // The words for each channel the tip says: those of the author's tip `format`, which
  // Plot made a function of, an axis's two ends taking the axis's; else the reader's
  // words above, a time as a reader says it rather than as Plot's ISO date.
  /** @type {Format} */
  const words = {};
  for (const key of Object.keys(sources)) {
    const given = authored[key] ?? authored[key.replace(/^([xy])[12]$/, "$1")];
    const own = format[key];
    words[key] =
      (typeof given === "string" || typeof given === "function") &&
      typeof own === "function"
        ? own
        : (/** @type {unknown} */ value) => say(value, scaleOf(key));
  }
  const title = sources.title;
  if (title && title !== true) {
    const said = /** @type {(value: unknown, i: number) => unknown} */ (words.title);
    const [first = "", ...rest] = String(said(title.value[i], i) ?? "").split("\n");
    return { name: first, detail: rest };
  }
  const across = placed(scales.y) && !placed(scales.x);
  const [first, second] = across ? ["y", "x"] : ["x", "y"];
  // A row measures where it says a number on a scale it doesn't stand at; the axis a
  // point stands along, its facets and its series name where it stands, and come first.
  /** @param {Row} row */
  const measures = ({ key }) => {
    const axis = axisOf(key);
    const scale = scaleOf(key);
    if (key === "fx" || key === "fy" || axis === first || placed(scale)) return false;
    if (axis) return true;
    const channel = sources[key];
    const raw = channel === true ? undefined : channel?.value[i];
    return !(
      key === "z" ||
      key === "symbol" ||
      typeof raw !== "number" ||
      CATEGORIES.has(scale?.type ?? "")
    );
  };
  // Where it stands first, its facets, the axis it stands along and the rest, then
  // what it measures, each kind in Plot's order.
  /** @param {Row} row */
  const rank = (row) =>
    (measures(row) ? 4 : 0) +
    (row.key === "fx" || row.key === "fy"
      ? 0
      : axisOf(row.key) === first
        ? 1
        : axisOf(row.key) === second
          ? 2
          : 3);
  // Plot's tip says each label once, as its drawing does.
  /** @type {Set<string>} */
  const labelled = new Set();
  const lines = [
    ...drawn.rows.call(
      { format: words },
      i,
      { fx: drawn.fx, fy: drawn.fy },
      sources,
      scales,
      drawn.values,
    ),
  ]
    .filter(({ label }) => !label || (!labelled.has(label) && labelled.add(label)))
    .sort((a, b) => rank(a) - rank(b))
    // A line as Plot's tip draws it: the label, then the value, a nullish one as none
    // (its `renderLine`).
    .map(({ label, value }) =>
      [label, value]
        .map((part) => String(part ?? ""))
        .filter(Boolean)
        .join(" "),
    );
  const [name = "", ...detail] = lines;
  return { name, detail };
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
