/* lf-chart: the quantitative picture — bars, stacked bars, lines and dots — drawn from a
 * comma-separated body by the vendored Observable Plot. lf-diagram draws the graphs a page
 * needs (flow, sequence, state); this draws its numbers, which mermaid's xychart cannot:
 * it has no (x, y) pairs at all, x being the array index, so an irregular series is plotted
 * at even spacing and two bar series overdraw each other rather than standing side by side.
 *
 * The body is the data rather than a chart spec. An author writes the numbers once, in the
 * order they think in, and says separately which picture they are (`kind`). It is the shape
 * an author is least able to get wrong — a header row naming the x column and then one
 * column per series, and under it one row per x value — and it is the one a reader can
 * check against the prose beside it, which a spec's nested objects are not.
 *
 * Colour is CSS and never JavaScript. Every mark Plot draws takes `currentColor` unless a
 * colour channel says otherwise, so one class on each mark's group (`lf-series-N`) and one
 * rule per series in the theme paints the whole chart — bars, lines and dots alike. A
 * diagram cannot have that: mermaid takes colours as strings, so lf-diagram resolves the
 * tokens, hands them over, and rewrites the values it gets back into `var(--token, #hex)`
 * to win the scheme flip and the export. That pass works, and what it cannot reach is
 * whatever mermaid derived for itself. Here there is nothing to resolve and nothing to
 * write back.
 *
 * The vendored bundle loads lazily, once, and only on pages that draw something: every
 * x-upgrade module is imported on every page, so a static import would put 384KB in front
 * of every reader of every page for the sake of the few that hold a chart. */
import {
  dataBody,
  failSoft,
  layerFact,
  measure,
  once,
  settle,
} from "/runtime/widget-api.js";

/* A calendar day or month, which is the whole of what an x column may say about time. A
 * finer instant would need a timezone to mean anything, and a page that carries one writes
 * it as a category. The month and day are spelled out rather than left as two digits
 * because a label like 2021-22 — a winter, on a chart of winters — otherwise reads as
 * month 22 and lands in the autumn of the following year. */
const ISO_DATE = /^(\d{4})-(0[1-9]|1[0-2])(?:-(0[1-9]|[12]\d|3[01]))?$/;

let plotReady;
const loadPlot = () => (plotReady ??= import("/vendor/plot.esm.js"));

/* How many series the layer has colours for. The palette is `--series-1…N` in the kernel
 * theme, so its size is the kernel's fact rather than this widget's: a project that
 * restates the palette with a step more raises the cap by doing so, and nothing here has
 * to hear about it. Past the last step a chart is refused rather than painted, because two
 * series in one colour is worse than a drawing that says it will not draw. */
const seriesCap = () => layerFact("$series").steps;

/* The body → {xName, labels, series}. Every refusal here names the row or the cell,
 * because failSoft shows the author this message over their own source. */
function readTable(text) {
  const rows = text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.split(",").map((cell) => cell.trim()));
  if (rows.length < 2)
    throw new Error("a chart body is a header row and then one row per x value");
  const columns = rows[0].length;
  if (columns < 2)
    throw new Error("the header row names the x column and then one column per series");
  const ragged = rows.findIndex((row) => row.length !== columns);
  if (ragged > 0)
    throw new Error(
      `row ${ragged + 1} has ${rows[ragged].length} cells where the header has ${columns}`,
    );

  const names = rows[0].slice(1);
  if (names.some((name) => !name))
    throw new Error("every series column needs a name in the header row");
  if (new Set(names).size !== names.length)
    throw new Error("two series columns share a name");
  const cap = seriesCap();
  if (names.length > cap)
    throw new Error(
      `${names.length} series, and a chart carries at most ${cap} — ` +
        `fold the small ones together or split the chart`,
    );

  const labels = rows.slice(1).map((row) => row[0]);
  if (labels.some((label) => !label))
    throw new Error("every row needs an x value in the first column");
  // The same refusal the series names get, and for a nearer reason: a band scale keeps one
  // slot per distinct label, so a repeated x draws its rows on top of each other — the
  // later one hiding the earlier, at a width the rest of the chart was not drawn to.
  const twice = labels.find((label, i) => labels.indexOf(label) !== i);
  if (twice) throw new Error(`two rows share the x value ${twice}`);

  const series = names.map((name, column) => ({
    name,
    values: rows.slice(1).map((row, index) => {
      const cell = row[column + 1];
      if (!cell) return null; // a gap the author left, drawn as a gap
      const value = Number(cell);
      if (!Number.isFinite(value))
        throw new Error(`row ${index + 2}, ${name}: "${cell}" is not a number`);
      return value;
    }),
  }));
  // Per series rather than over the body: a column of blanks draws no mark and still takes
  // a colour and a line in the key, so the chart claims a series it never shows.
  const empty = series.find((s) => s.values.every((v) => v === null));
  if (empty) throw new Error(`${empty.name} has no numbers in it`);
  return { xName: rows[0][0], labels, series };
}

/* What the x column is, which the column itself answers: every value a calendar date, or
 * every value a number, or neither — and neither is a category. Dates are read into UTC
 * from their own parts rather than through Date's string parsing, which reads a bare
 * `2026-06-01` as UTC midnight and then draws it under May 31 for a reader west of
 * Greenwich. A UTC scale keeps the axis saying what the body says.
 *
 * Only a line and a scatter ask. A bar chart's x is one slot per row by construction, so
 * bars, rows and stack band the labels exactly as written, whatever they look like. */
function readAxis(labels) {
  const dates = labels.map((label) => ISO_DATE.exec(label));
  // All to the same granularity or none: a column holding both 2026-01 and 2026-01-01
  // would read the month as the first of it and put two rows on one instant.
  const months = dates.filter(Boolean).filter(([, , , day]) => !day).length;
  if (dates.every(Boolean) && (months === 0 || months === dates.length))
    return {
      type: "utc",
      values: dates.map(
        ([, year, month, day]) => new Date(Date.UTC(+year, +month - 1, day ? +day : 1)),
      ),
    };
  const numbers = labels.map(Number);
  if (numbers.every(Number.isFinite)) return { type: "linear", values: numbers };
  return { type: "band", values: labels };
}

const ruler = document.createElement("canvas").getContext("2d");
function textWidth(strings, font) {
  ruler.font = font;
  return Math.max(0, ...strings.map((s) => ruler.measureText(String(s)).width));
}

/* A label cut to the room there is, with the ellipsis that says it was cut. Only a row
 * chart's categories reach this: they are the one axis whose labels are the author's words
 * rather than numbers Plot chose, so they are the one that can be wider than the drawing.
 * Cut rather than clipped, because a clipped label is one with its end painted over the
 * bars — and at a narrow enough window, a plot of negative width. */
function clip(label, room, font) {
  if (textWidth([label], font) <= room) return label;
  let cut = label;
  while (cut && textWidth([`${cut}…`], font) > room) cut = cut.slice(0, -1);
  return `${cut}…`;
}

/* Bars are placed rather than dodged. Plot's own answer for a grouped bar chart is to
 * facet the x, which draws a frame per group and breaks the gridlines into one run per
 * group — five short rules at each tick where the reader is trying to carry one across
 * the chart. So the band stays whole and each series takes its own slice of it, which is
 * the same arithmetic a facet would do, done where the numbers are already known.
 *
 * It also puts the bar's thickness under this file's control, and a bar wants a cap. At
 * four categories across a column the band is a third of the chart and a bar filling it
 * is a block of colour: what the reader compares is length, and past about this width the
 * area starts doing the talking instead. Every kind that draws a bar shares the reading,
 * so a row chart and a column chart of the same numbers are the same weight of ink. */
const GAP = 2; // between the bars of one group, and Plot's own inset from the band edge
const THICKEST = 48;
const INNER = 0.2; // of the step, left between one group and the next
const OUTER = 0.1; // and at the two ends, where there is no neighbour to stand off

/* d3's own band arithmetic, because the insets below are measured in the band's units and
 * a second formula for its width would put the bars off centre by however much the two
 * disagreed. */
function slices({ inner, bands, count }) {
  const width = (inner / (bands - INNER + 2 * OUTER)) * (1 - INNER);
  const slice = width / count;
  // The gap comes out of the slice rather than out of the band, so however many series
  // and categories a body has, the group is never wider than the band it is centred in.
  const gap = Math.min(GAP, slice * 0.4);
  const thickness = Math.min(slice - gap, THICKEST);
  const lead = (width - (thickness * count + gap * (count - 1))) / 2;
  return (index) => {
    const before = lead + index * (thickness + gap);
    return [before, width - before - thickness];
  };
}

/* The value axis a bar is measured against. A bar's length is its number, so the axis it
 * runs from is zero whether or not the numbers reach there — Plot's own domain is the
 * data's extent, which for one row reading 0 is [0, 0], a scale with nothing to divide by
 * and a rect drawn the whole height of the plot and below the line it should have sat on.
 * Stated outright, and `nice` widens it to a round number so the tallest bar is not
 * painted against the top edge. */
const barDomain = (values) => {
  const top = Math.max(0, ...values);
  const floor = Math.min(0, ...values);
  return top === floor ? [0, 1] : [floor, top];
};

/* The same trouble one axis over, where a bar's zero is not the answer: a run of numbers
 * that never changes gives Plot a domain of [500, 500], whose one tick it writes as
 * 500.000000 because six decimal places is what it takes to tell that domain apart from
 * itself. A line through the middle of a plain span says the true thing — nothing moved. */
const spread = (values) => {
  const [lo, hi] = [Math.min(...values), Math.max(...values)];
  if (lo !== hi) return undefined; // the ordinary case: Plot reads the extent itself
  const step = values[0] instanceof Date ? 86400000 : 1;
  return values[0] instanceof Date
    ? [new Date(lo - step), new Date(hi + step)]
    : [lo - step, hi + step];
};

/* Where the ticks of a time axis go. Plot chooses an interval from the extent alone, and
 * over four days it chooses hours: a chart of four daily totals came out under eight ticks
 * reading 12 AM and 12 PM, naming instants the body never mentions. A short run says its
 * own ticks — the reader's dates, and no others — in one line: Plot's multi-tier formatter
 * put a month directly under a neighbouring day on Linux. Thin those labels when the room
 * cannot hold them, just as a band axis does. A long run keeps Plot's choosing while being
 * held to a day at the finest. */
const dateLabeler = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  timeZone: "UTC",
});
const dateLabel = (value) => dateLabeler.format(value);
function timeAxis(values, room, font) {
  if (values.length <= 10) {
    const every = Math.ceil(
      (textWidth(values.map(dateLabel), font) + 6) / (room / values.length),
    );
    return {
      ticks: values.filter((_, i) => i % every === 0),
      tickFormat: dateLabel,
    };
  }
  const days = (Math.max(...values) - Math.min(...values)) / 86400000;
  return {
    ticks: days > 730 ? "year" : days > 180 ? "month" : days > 45 ? "week" : "day",
  };
}

/* Which of a band's labels are drawn. Every one, until they stop fitting: five winters
 * across a phone's column give each about as much room as its own name takes, and Plot
 * draws them all whatever happens, so they run into one another and the axis reads as one
 * long word. Thinned, the bars are all still drawn and some go unlabelled, which is what
 * every other chart in the world does with a crowded axis and is a great deal better than
 * a smear. The step is the room one band has; the width is the widest name that has to sit
 * in it. */
const bandTicks = (labels, room, font) => {
  const every = Math.ceil((textWidth(labels, font) + 6) / (room / labels.length));
  return every <= 1 ? undefined : labels.filter((_, i) => i % every === 0);
};

/* The one place a series becomes a mark. Every kind hands Plot the same per-series class
 * and lets the stylesheet colour it, so a kind added here needs no new rule and no new
 * token. */
const marked = (index, options) => ({
  ...options,
  className: `lf-series-${index + 1}`,
});

function build(Plot, { kind, table, axis, label, width, font, line, grow, held }) {
  const { labels, series, xName } = table;
  const points = (s) =>
    axis.values.map((x, i) => ({ x, v: s.values[i] })).filter((d) => d.v !== null);
  const room = (values) =>
    textWidth(
      values.map((v) => `${v}`),
      font,
    );
  const drawn = series.flatMap((s) => s.values.filter((v) => v !== null));
  // Plot's own label arrows ("↑ merged") read as Observable rather than as this page. The
  // axis label says what the numbers are; which way they run is the picture's job.
  const common = {
    width,
    className: "lf-chart-plot",
    marginTop: line + 6 + grow.top,
    marginRight: 8 + grow.right,
  };
  const y = { grid: true, label, labelArrow: "none" };

  if (kind === "rows") {
    // Horizontal bars: the shape for long category names and for a ranking, because a
    // name gets a whole line to itself instead of a band one bar wide. Its labels are the
    // one axis this file cannot bound, so they are the one it cuts.
    const height = labels.length * Math.max(26, series.length * 18 + 12);
    // Two lines, because this is the one kind whose value axis is the x: Plot hangs the
    // axis label off the bottom margin and anchors it right, which puts it on top of the
    // last tick at every width the corpus is read at. A line of its own is the same room
    // the scatter's x label already gets.
    const marginBottom = line + 16 + line + grow.bottom;
    // The reservation is the measurement plus slack, and the cut is the reservation less
    // the tick and its gap — so a name that fits is never cut. Measured flush, it was: a
    // canvas ruler and the browser's own text layout agree to about a pixel, and the one
    // that decides is the one that draws.
    const marginLeft = Math.min(
      Math.round(textWidth(labels, font)) + 16 + grow.left,
      Math.round(width * 0.45),
    );
    const inset = slices({ inner: height, bands: labels.length, count: series.length });
    return Plot.plot({
      ...common,
      height: height + common.marginTop + marginBottom,
      marginBottom,
      marginLeft,
      x: {
        grid: true,
        label,
        labelArrow: "none",
        nice: true,
        domain: barDomain(drawn),
      },
      y: {
        domain: labels,
        label: null,
        paddingInner: INNER,
        paddingOuter: OUTER,
        tickFormat: (d) => clip(d, marginLeft - 14, font),
      },
      marks: [
        ...series.map((s, i) => {
          const [before, after] = inset(i);
          return Plot.barX(
            points(s),
            marked(i, { y: "x", x: "v", insetTop: before, insetBottom: after }),
          );
        }),
        Plot.ruleX([0]),
      ],
    });
  }

  const height = held ?? Math.min(340, Math.max(190, Math.round(width * 0.46)));
  // The x axis names itself where its values are bare numbers and nowhere else: dates and
  // categories say what they are, and "quarter" written under Q1…Q4 is the page repeating
  // itself in the one place it has least room.
  const xLabel = axis.type === "linear" ? xName : null;
  const marginBottom = line + 16 + (xLabel ? line : 0) + grow.bottom;

  if (kind === "bars" || kind === "stack") {
    // One column per x value, and the series either stand beside each other in the band or
    // stack up it. Stacking is arithmetic here rather than Plot's stack transform, which
    // stacks inside one mark and colours by a channel — and colouring by a channel is the
    // one thing this widget will not do, since the colour has to stay the stylesheet's.
    if (kind === "stack" && drawn.some((value) => value < 0))
      throw new Error("a stack is a total, so its numbers cannot be negative");
    const floors = labels.map(() => 0);
    const columns = series.map((s) =>
      labels.flatMap((x, row) => {
        const value = s.values[row];
        if (value === null) return [];
        const bar = { x, lo: floors[row], hi: floors[row] + value };
        if (kind === "stack") floors[row] += value;
        return [bar];
      }),
    );
    // Capped for the same reason a row chart's names are: a body of twenty-digit numbers
    // asks for more room than the widget has, and an axis wider than the drawing leaves a
    // plot of negative width — which flips every sign in the band arithmetic below and
    // paints the bars outside the canvas, in a box that otherwise looks merely empty.
    const marginLeft = Math.min(
      Math.round(room(kind === "stack" ? floors : drawn)) + 14 + grow.left,
      Math.round(width * 0.45),
    );
    const inset = slices({
      inner: width - marginLeft - common.marginRight,
      bands: labels.length,
      count: kind === "stack" ? 1 : series.length,
    });
    return Plot.plot({
      ...common,
      height,
      marginBottom,
      marginLeft,
      x: {
        domain: labels,
        label: xLabel,
        labelArrow: "none",
        paddingInner: INNER,
        paddingOuter: OUTER,
        ticks: bandTicks(labels, width - marginLeft - common.marginRight, font),
      },
      y: { ...y, nice: true, domain: barDomain(kind === "stack" ? floors : drawn) },
      marks: [
        ...columns.map((bars, i) => {
          const [before, after] = inset(kind === "stack" ? 0 : i);
          return Plot.barY(
            bars,
            marked(i, {
              x: "x",
              y1: "lo",
              y2: "hi",
              insetLeft: before,
              insetRight: after,
              // A hairline of paper between one segment and the next, so a stack reads as
              // parts rather than as one bar someone striped.
              ...(kind === "stack" ? { insetTop: 1 } : {}),
            }),
          );
        }),
        Plot.ruleY([0]),
      ],
    });
  }

  const marginLeft = Math.round(room(drawn)) + 14 + grow.left;
  // A band domain is stated rather than left to Plot, which sorts an ordinal domain it was
  // not given: a run written Nov, Dec, Jan, Feb came out Dec, Feb, Jan, Nov — drawn in an
  // order the chart's own spoken reading contradicted. Sorting the marks by x is right for
  // a continuous axis and wrong for this one, which is the same fact from the other side.
  const x = {
    label: xLabel,
    labelArrow: "none",
    ...(axis.type === "band"
      ? {
          domain: labels,
          ticks: bandTicks(labels, width - marginLeft - common.marginRight, font),
        }
      : {}),
    ...(axis.type === "utc"
      ? {
          type: "utc",
          ...timeAxis(axis.values, width - marginLeft - common.marginRight, font),
        }
      : {}),
  };

  if (kind === "line")
    return Plot.plot({
      ...common,
      height,
      marginBottom,
      marginLeft,
      x: { ...x, domain: axis.type === "band" ? labels : spread(axis.values) },
      y: { ...y, domain: spread(drawn) },
      marks: series.map((s, i) =>
        Plot.lineY(
          points(s),
          marked(i, {
            x: "x",
            y: "v",
            strokeWidth: 2,
            ...(axis.type === "band" ? {} : { sort: { x: "x" } }),
          }),
        ),
      ),
    });

  if (kind === "dots") {
    if (axis.type === "band")
      throw new Error(
        `dots plots two numbers against each other, and the ${xName} column is not numeric`,
      );
    return Plot.plot({
      ...common,
      height,
      // Both axes carry numbers here and neither says what they are, so both are named —
      // a dated x included, where the dates say which day and not which measurement.
      marginBottom: line + 16 + line + grow.bottom,
      marginLeft,
      x: { ...x, label: xName, grid: true, nice: true, domain: spread(axis.values) },
      y: { ...y, domain: spread(drawn) },
      marks: series.map((s, i) =>
        Plot.dot(
          points(s),
          marked(i, { x: "x", y: "v", r: 3.2, fill: "currentColor" }),
        ),
      ),
    });
  }

  throw new Error(`no such chart kind: ${kind}`);
}

/* How far the drawing's own words fall outside it, which is a question only the browser can
 * answer. The margins above are an estimate from the data, and the ticks are not the data:
 * Plot rounds a domain outwards, groups thousands, and for a domain with no extent at all
 * writes six decimal places where the estimate reserved three characters. Rather than a
 * second guess at each of those, the estimate draws once and this reads what landed. */
function overhang(svg) {
  const frame = svg.getBoundingClientRect();
  const over = { left: 0, right: 0, top: 0, bottom: 0 };
  for (const text of svg.querySelectorAll("text")) {
    const box = text.getBoundingClientRect();
    if (!box.width) continue;
    over.left = Math.max(over.left, frame.left - box.left);
    over.right = Math.max(over.right, box.right - frame.right);
    over.top = Math.max(over.top, frame.top - box.top);
    over.bottom = Math.max(over.bottom, box.bottom - frame.bottom);
  }
  return over;
}

/* The legend, in HTML rather than inside the drawing: real text at the page's own size,
 * which a screen reader reads and the theme sets in the apparatus face. Generated, because
 * the file-side reading of an upgraded data body is a fence — these words are the module's,
 * not the version's. One series needs none: the axis label already names it. */
function legend(series) {
  const keys = document.createElement("div");
  keys.className = "lf-chart-keys";
  keys.setAttribute("data-lf-gen", "");
  series.forEach((s, i) => {
    const key = document.createElement("span");
    key.className = "lf-chart-key";
    const swatch = document.createElement("span");
    // The series class goes on the swatch alone. Worn by the key it would take the name
    // with it, and a name set in its own mark's colour is a fainter second copy of the
    // swatch beside it.
    swatch.className = `lf-chart-swatch lf-series-${i + 1}`;
    key.append(swatch, s.name);
    keys.append(key);
  });
  return keys;
}

/* What a reader who cannot see the drawing is given in its place. The numbers, not a
 * summary of them: the body they came from is the widget's own <pre>, which the module
 * has already replaced, so this label is the only place they still exist as words. */
const chartLabel = (el, { xName, labels, series }) =>
  `${el.getAttribute("kind")} chart. ${el.getAttribute("y")} by ${xName}. ` +
  series
    .map(
      (s) =>
        `${s.name}: ` +
        labels
          .map((label, i) => (s.values[i] === null ? null : `${label} ${s.values[i]}`))
          .filter(Boolean)
          .join(", "),
    )
    .join(". ") +
  ".";

customElements.define(
  "lf-chart",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      // A chart is drawn to the room it has, so the first draw waits for a box. On the
      // page that box is there already and this settles inside the upgrade, holding the
      // view restore and the first anchor pass until the drawing is in and the page's
      // geometry is final. In a shut panel there is no box at all and measure holds the
      // draw instead of the page.
      measure(this, () => settle(this.draw()));
    }

    disconnectedCallback() {
      this.watching?.disconnect();
    }

    async draw() {
      // Inside the try with everything else: dataBody reaches for a <pre> both markup
      // doors require, and a version file hand-edited past them threw out of here instead
      // of failing soft, leaving the reader the body's raw text and no error at all.
      let source = "";
      try {
        source = dataBody(this).trim();
        const table = readTable(source);
        const axis = readAxis(table.labels);
        const Plot = await loadPlot();
        // The widget's own children, built once: the key, then the box each drawing goes
        // in. A redraw replaces what is in that box and nothing else, because by then the
        // runtime may have hung its own words on the widget — the line saying a comment
        // stands on this chart is a child of the element, and replacing the element's
        // children took it away at the moment the reader opened the panel to read it.
        this.drawing = document.createElement("div");
        this.drawing.className = "lf-chart-drawing";
        this.replaceChildren(
          ...(table.series.length > 1 ? [legend(table.series)] : []),
          this.drawing,
        );
        this.paint(Plot, table, axis);
        this.classList.add("lf-rendered");
        // Everything after the first draw is the room changing under it: a window
        // resized, the comment panel opening and taking its strip out of the column. The
        // drawing would scale with the box and take its labels below legibility with it,
        // which is what a diagram has to live with and a chart does not — it can simply
        // be drawn again. Only the width is watched, and only when it lands on a new
        // whole pixel: redrawing changes the height, and a height this heard would be a
        // loop.
        let drawn = Math.round(this.clientWidth);
        this.watching = new ResizeObserver(() => {
          const width = Math.round(this.clientWidth);
          if (!width || width === drawn) return;
          drawn = width;
          try {
            this.paint(Plot, table, axis);
          } catch (err) {
            this.watching.disconnect();
            failSoft(this, err, source);
          }
        });
        this.watching.observe(this);
      } catch (err) {
        failSoft(this, err, source);
      }
    }

    paint(Plot, table, axis) {
      // The theme's --lf-chart-font, not this element's own computed font: the element
      // wears the mono source face until its body is replaced, and the margins have to be
      // reserved before there is anything to replace it with. A custom property resolves
      // its var()s wherever it is read, so what comes back is the drawing's real font in
      // the shape a canvas ruler measures in.
      const font = getComputedStyle(this).getPropertyValue("--lf-chart-font").trim();
      const spec = {
        kind: this.getAttribute("kind"),
        label: this.getAttribute("y"),
        table,
        axis,
        width: Math.round(this.clientWidth),
        font,
        line: Math.round(parseFloat(font) * 1.35),
        held: this.held,
      };
      let built = this.show(Plot, spec, { left: 0, right: 0, top: 0, bottom: 0 });
      // The height the first draw chose, kept for every later one. A height derived from
      // the width is a path from a redraw back to the width that caused it: where a
      // scrollbar takes room from the page rather than floating over it, a chart that
      // grows past the viewport takes the scrollbar, loses the width the scrollbar cost,
      // shrinks, gives it back, and alternates two widths for as long as the tab is open.
      // Held, there is no path at all — and a chart that keeps its height while the window
      // narrows is the better drawing anyway.
      this.held ??= Number(built.getAttribute("height"));
      // One correction and no more. What it grows is room the axis text needs, and taking
      // that room can only make the plot narrower, never its own labels wider — so a
      // second reading would find the drawing this one already fixed.
      const over = overhang(built);
      if (Object.values(over).some((px) => px > 0.5))
        built = this.show(Plot, spec, over);
      // The drawing is one picture and takes a whole-widget comment through x-visual, so
      // nothing inside it needs to be reachable on its own; the label is what a reader
      // hears in its place. `role="img"` closes the tree under it, and Plot has named
      // every group inside — `aria-label="bar"`, `"rule"`, `"x-axis tick label"` — on
      // `<g>` elements carrying no role, which axe reports as a serious WCAG failure and
      // which name nothing a reader of the label needs. Swept rather than refused per
      // mark, because the axis and rule groups are Plot's own and take no options here.
      // Kept as data, because what Plot calls each group is the only thing that names one:
      // it is how a test asks for the x axis's words and how anyone reading the drawing in
      // a devtools pane tells the ticks from the marks.
      for (const named of built.querySelectorAll("[aria-label]")) {
        named.dataset.lfPart = named.getAttribute("aria-label");
        named.removeAttribute("aria-label");
      }
      built.setAttribute("role", "img");
      built.setAttribute("aria-label", chartLabel(this, table));
    }

    show(Plot, spec, grow) {
      const built = build(Plot, { ...spec, grow });
      this.drawing.replaceChildren(built);
      return built;
    }
  },
);
