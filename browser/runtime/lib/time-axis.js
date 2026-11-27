/* A horizontal time axis, shared by the widgets that draw one: its geometry, its ruler
 * and its gridlines. Times are milliseconds from the axis origin; positions are pixels
 * along the drawn span, which starts and ends AXIS_EDGE inside the drawing. Nothing
 * here touches the DOM, so a widget can call it while drawing, before its upgrade as
 * well as after.
 *
 * `axisMarks` returns the ruler's ticks and the gridlines as marks any renderer
 * draws, and `timeAxis` returns them as Lit templates. The widget
 * renders the ticks into its ruler and the gridlines into a layer that spans its
 * lanes, and draws its own marks in the lanes:
 *
 * ```js
 * // `width` is the ruler's, and `span` the part of it the axis is drawn across.
 * const span = width - 2 * AXIS_EDGE;
 * const axis = timeAxis(0, duration, duration, span / duration);
 * html`<div class="my-axis" style="--lf-axis-edge: ${AXIS_EDGE}px">
 *   <div class="my-ruler">${axis.ruler}</div>
 *   <div class="my-grid">${axis.grid}</div>
 *   <div class="my-lane">
 *     <span
 *       class="my-bar lf-on-axis"
 *       style="--lf-axis-at: ${start / duration}; --my-length: ${(end - start) / duration}"
 *     ></span>
 *   </div>
 * </div>`;
 * ```
 *
 * ```css
 * .my-axis { position: relative; font: var(--lf-font-small); line-height: 1; }
 * .my-ruler, .my-lane { position: relative; block-size: 22px; }
 * .my-grid { position: absolute; inset: 22px 0 0; pointer-events: none; }
 * .my-bar {
 *   inset-block: 4px;
 *   inline-size: calc(var(--my-length) * (100% - 2 * var(--lf-axis-edge)));
 *   background: var(--lf-accent);
 * }
 * ```
 *
 * Leaf's stylesheet (`browser/styles/components/controls.css`, "A time axis") draws
 * the ticks and gridlines, and stands each at its time in the nearest positioned box,
 * as it stands a mark of the widget's own (`module-controls.md`, "A time axis"). So
 * the ruler, the layer and each lane are positioned boxes as wide as the axis. A major
 * tick is as tall as the ruler, and a gridline as tall as the layer. The layer comes
 * before the lanes, so their marks paint over its lines, and it lets the pointer
 * through to the drawing it covers. A tick's label takes the drawing's type, so the
 * drawing sets a line that fits the ruler. The labels are words the module writes
 * (`module-plain-elements.md`, "Words it writes").
 *
 * Ruler ticks fall on the smallest step in STEPS that keeps major ticks
 * AXIS_TICK_SPACING apart, with two to five minor ticks between them. Below a second
 * the steps are 1, 2 and 5 × 10^k milliseconds; from a second up they are the clock's
 * round spans, such as 15 s, 30 min and 6 h, as a chart's time axis takes them. A
 * step below a second labels its ticks in seconds with the decimals the step needs,
 * and a longer one as `elapsed` writes a time, such as "1 h 30 min", so a sequence of
 * hours doesn't read in thousands of seconds. An axis given a `start`, the ISO date-time
 * of its origin, reads as a clock instead: its ticks fall on the clock's round times,
 * such as 13:00 and 13:30 after a start of 12:56, and read as times of day with the
 * parts their step needs, or as dates where the step is a day or longer. A clock time
 * reads as the clock `start` is written in, whatever the reader's own time zone, so
 * every reader sees the times the author wrote. A major tick's label reads back from its
 * tick (`flip`) where reading on from it would run past the axis's end, and the major
 * tick before it then goes unlabeled where the two labels would meet. Rows are
 * greedy: an extent takes the first row whose last extent ended at or before its
 * start, so overlapping extents never share a row and the row count is the smallest
 * that greedy order allows.
 */
import { html, nothing, repeat } from "/vendor/lit.js";

/** How far inside the drawing the axis's span starts and ends, in pixels. */
export const AXIS_EDGE = 12;
/** The least distance between major ticks, in pixels. */
export const AXIS_TICK_SPACING = 84;
/** What a mark's label adds to the width of its words: its padding and its stroke. */
export const AXIS_LABEL_CHROME = 12;
/** The least room between two labels in one row, in pixels. */
export const AXIS_LABEL_GAP = 8;
// The room a major tick's label needs between its tick and the axis's end to read on
// from it, for each character it holds: "0.125 s" is about 44 pixels wide.
const LABEL_ROOM_PER_CHAR = 44 / 7;
/** @param {string} label */
const labelRoom = (label) => label.length * LABEL_ROOM_PER_CHAR;
const SECOND = 1000;
const MINUTE = 60 * SECOND;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
/** Each major tick step, in milliseconds, with the step of the minor ticks between,
 * shortest first. */
/** @type {readonly (readonly [number, number])[]} */
const STEPS = [
  [1, 0.2],
  [2, 0.5],
  [5, 1],
  [10, 2],
  [20, 5],
  [50, 10],
  [100, 20],
  [200, 50],
  [500, 100],
  [SECOND, SECOND / 5],
  [2 * SECOND, SECOND / 2],
  [5 * SECOND, SECOND],
  [10 * SECOND, 2 * SECOND],
  [15 * SECOND, 5 * SECOND],
  [30 * SECOND, 10 * SECOND],
  [MINUTE, 15 * SECOND],
  [2 * MINUTE, 30 * SECOND],
  [5 * MINUTE, MINUTE],
  [10 * MINUTE, 2 * MINUTE],
  [15 * MINUTE, 5 * MINUTE],
  [30 * MINUTE, 10 * MINUTE],
  [HOUR, 15 * MINUTE],
  [2 * HOUR, 30 * MINUTE],
  [3 * HOUR, HOUR],
  [6 * HOUR, 2 * HOUR],
  [12 * HOUR, 3 * HOUR],
  [DAY, 6 * HOUR],
  [2 * DAY, 12 * HOUR],
  [5 * DAY, DAY],
];
/** The step of an axis too long for any of STEPS. */
/** @type {readonly [number, number]} */
const LONGEST_STEP = [10 * DAY, 2 * DAY];

/** The major and minor tick steps, in milliseconds, for a scale of `pxPerMs`. */
/** @param {number} pxPerMs */
function tickStep(pxPerMs) {
  return STEPS.find(([step]) => step * pxPerMs >= AXIS_TICK_SPACING) ?? LONGEST_STEP;
}

/** The decimals that show every multiple of a step below a second in seconds. */
/** @param {number} step */
const decimals = (step) => (step >= 100 ? 1 : step >= 10 ? 2 : 3);

/** A time in milliseconds as seconds, such as "1.2 s": with `digits` decimals, or
 * rounded to the millisecond and written with as few decimals as show it. */
/** @param {number} ms @param {number} [digits] */
export function seconds(ms, digits) {
  const s = ms / SECOND;
  return `${digits === undefined ? Number(s.toFixed(3)) : s.toFixed(digits)} s`;
}

/** An ISO date-time's clock reading: the time of day and date it writes, ignoring
 * any offset it gives, as milliseconds of a UTC clock, so formatting it in UTC writes
 * the clock it was written in. */
/** @param {string} start */
const wallClock = (start) =>
  Date.parse(`${start.replace(/(Z|[+-]\d{2}:\d{2})$/, "")}Z`);

/** Whether an ISO date-time names a moment on the calendar, so that an axis can read
 * from it. `Date` carries a date the calendar lacks, such as 30 February, into the
 * next month, so the clock reading must write back the date and time it was given. */
/** @param {string} start */
export const onCalendar = (start) => {
  const ms = wallClock(start);
  return (
    Number.isFinite(ms) && new Date(ms).toISOString().startsWith(start.slice(0, 16))
  );
};

/** The clock time `ms` after `start`, such as "15:46": as a date, such as
 * "2026-11-25", for a `step` of a day or longer, and otherwise with the parts the
 * step needs, or with as few as show the time where no step is given. */
/** @param {number} ms @param {string} start @param {number} [step] */
function clockTime(ms, start, step) {
  const iso = new Date(wallClock(start) + ms).toISOString();
  if (step !== undefined && step >= DAY) return iso.slice(0, 10);
  const [time = "", fraction = ""] = iso.slice(11, -1).split(".");
  if (step === undefined) {
    const digits = fraction.replace(/0+$/, "");
    if (digits) return `${time}.${digits}`;
    return time.endsWith(":00") ? time.slice(0, 5) : time;
  }
  if (step < SECOND) return `${time}.${fraction.slice(0, decimals(step))}`;
  return step < MINUTE ? time : time.slice(0, 5);
}

/** A time in milliseconds from an origin, in the units its length reads in: under a
 * minute as `seconds` writes it, such as "1.2 s", and from a minute up in hours,
 * minutes and whole seconds, leaving out a unit that counts none, such as "2 min 5 s"
 * or "1 h 30 min". Given `start`, the ISO date-time of the origin, it writes the time
 * of day instead, such as "15:46", or "15:46:30" where the time has seconds. */
/** @param {number} ms @param {string | null} [start] */
export function elapsed(ms, start) {
  if (start) return clockTime(ms, start);
  if (ms < MINUTE) return seconds(ms);
  const total = Math.round(ms / SECOND);
  return /** @type {const} */ ([
    [Math.floor(total / 3600), "h"],
    [Math.floor(total / 60) % 60, "min"],
    [total % 60, "s"],
  ])
    .filter(([count]) => count)
    .map(([count, unit]) => `${count} ${unit}`)
    .join(" ");
}

/** The ticks between `from` and `to`, clipped to `[0, duration]`: `{time, major,
 * label, flip, step}`. Only a major tick has a label, in the units its step
 * reads in, and only a major tick's label flips. */
/** @param {number} from @param {number} to @param {number} duration @param {number} pxPerMs
 * @param {string | null} [start] */
function axisTicks(from, to, duration, pxPerMs, start) {
  const [step, minor] = tickStep(pxPerMs);
  // How far the origin stands past a multiple of a step on the clock, so that ticks
  // fall on the clock's round times; an axis without a start counts from its origin.
  const origin = start ? wallClock(start) : 0;
  const past = (/** @type {number} */ span) => ((origin % span) + span) % span;
  const ticks = [];
  for (
    let time = Math.floor((from + past(minor)) / minor) * minor - past(minor);
    time <= to;
    time += minor
  ) {
    const rounded = Math.round(time * 1000) / 1000;
    if (rounded < 0 || rounded > duration) continue;
    const steps = (rounded + past(step)) / step;
    const major = Math.abs(steps - Math.round(steps)) < 1e-6;
    const label = !major
      ? null
      : start
        ? clockTime(rounded, start, step)
        : step < SECOND
          ? seconds(rounded, rounded === 0 ? 0 : decimals(step))
          : elapsed(rounded);
    ticks.push({
      time: rounded,
      major,
      label,
      flip: label !== null && (duration - rounded) * pxPerMs < labelRoom(label),
      step,
    });
  }
  // A label that reads back runs toward the major tick before it, whose label reads
  // on toward it; where the two need more room than lies between their ticks, the
  // earlier one goes, so the axis's last time stays labeled.
  /** @type {(typeof ticks)[number] | undefined} */
  let before;
  for (const tick of ticks) {
    if (tick.label === null) continue;
    if (
      tick.flip &&
      before?.label &&
      !before.flip &&
      (tick.time - before.time) * pxPerMs <
        labelRoom(before.label) + labelRoom(tick.label)
    )
      before.label = null;
    before = tick;
  }
  return ticks;
}

/** The axis from `from` to `to`, as marks a view draws whatever renders it: `ruler`,
 * a tick at each time, and `grid`, a line at each major tick's time. Each mark is a
 * `span` of class `class`, keyed by `key`, with `data-lf-major` and `data-lf-flip`
 * where `major` and `flip` hold, `--lf-axis-at` set to `at`, and `label`, where it
 * has one, as its words. `duration`, above zero, is the time the whole axis spans,
 * and `pxPerMs` its scale. A widget that shows a window of a longer axis, as a zoomed
 * one does, passes the window's times and draws again when the window moves; a tick
 * or line that both windows hold keeps its key. `at` is the time over `duration`.
 * `start`, the ISO date-time of the axis's origin, makes the axis read as a clock. */
/** @param {number} from @param {number} to @param {number} duration @param {number} pxPerMs
 * @param {string | null} [start] */
export function axisMarks(from, to, duration, pxPerMs, start) {
  const ticks = axisTicks(from, to, duration, pxPerMs, start);
  /** @param {(typeof ticks)[number]} tick @param {"lf-axis-tick" | "lf-axis-gridline"} cls */
  const mark = (tick, cls) => {
    const ruler = cls === "lf-axis-tick";
    return {
      key: `${tick.step}:${tick.time}`,
      class: cls,
      major: ruler && tick.major,
      flip: tick.flip,
      at: String(tick.time / duration),
      label: ruler ? tick.label : null,
    };
  };
  return {
    ruler: ticks.map((tick) => mark(tick, "lf-axis-tick")),
    grid: ticks
      .filter((tick) => tick.major)
      .map((tick) => mark(tick, "lf-axis-gridline")),
  };
}

/** `axisMarks` as Lit templates, for a view that Lit draws. */
/** @param {number} from @param {number} to @param {number} duration @param {number} pxPerMs
 * @param {string | null} [start] */
export function timeAxis(from, to, duration, pxPerMs, start) {
  const marks = axisMarks(from, to, duration, pxPerMs, start);
  /** @param {(typeof marks.ruler)[number][]} list */
  const draw = (list) =>
    repeat(
      list,
      (mark) => mark.key,
      (mark) =>
        html`<span
          class=${mark.class}
          ?data-lf-major=${mark.major}
          ?data-lf-flip=${mark.flip}
          style="--lf-axis-at: ${mark.at}"
          >${mark.label ?? nothing}</span
        >`,
    );
  return { ruler: draw(marks.ruler), grid: draw(marks.grid) };
}

/** Greedy rows for extents: a Map from each item's `id` to its row, from 0. */
/** @template {{id: string}} T @param {readonly T[]} items
 * @param {(item: T) => number} start @param {(item: T) => number} end */
export function assignRows(items, start, end) {
  /** @type {number[]} */
  const rows = [];
  const rowOf = new Map();
  for (const item of items.toSorted((a, b) => start(a) - start(b))) {
    let row = rows.findIndex((last) => last <= start(item));
    if (row < 0) row = rows.push(-Infinity) - 1;
    rows[row] = end(item);
    rowOf.set(item.id, row);
  }
  return rowOf;
}
