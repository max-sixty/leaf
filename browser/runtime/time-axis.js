/* Geometry for a horizontal time axis, shared by the widgets that draw one: the
 * Playwright recording timeline (`packages/playwright/widgets/timeline.js`) and
 * `lf-timeline` (`packages/timeline/widgets/timeline-view.js`). Times are milliseconds from the axis origin; positions are
 * pixels along the drawn span, which starts and ends AXIS_EDGE inside the drawing.
 * Nothing here touches the DOM except the canvas that measures text, so each widget
 * can call it while drawing. The ruler's look is one rule, `.lf-axis-tick`
 * (`styles/components/controls.css`).
 *
 * Ruler ticks fall on 1, 2 and 5 × 10^k milliseconds, the smallest step that keeps
 * major ticks AXIS_TICK_SPACING apart, with four or five minor ticks between them. A
 * major tick's label reads back from its tick (`flip`) where reading on from it would
 * run past the axis's end. Rows are greedy: an extent takes the first row whose last
 * extent ended at or before its start, so overlapping extents never share a row and
 * the row count is the smallest that greedy order allows.
 */

import { canvas2D } from "./canvas.js";

/** How far inside the drawing the axis's span starts and ends, in pixels. */
export const AXIS_EDGE = 12;
/** The least distance between major ticks, in pixels. */
export const AXIS_TICK_SPACING = 84;
/** What a mark's label adds to the width of its words: its padding and its stroke. */
export const AXIS_LABEL_CHROME = 12;
/** The least room between two labels in one row, in pixels. */
export const AXIS_LABEL_GAP = 8;
// The room a major tick's label needs between its tick and the axis's end to read on
// from it: a three-decimal label, such as "0.125 s", is about that wide.
const LABEL_ROOM = 44;
const STEPS = [1, 2, 5];

/** The major tick step, in milliseconds, for a scale of `pxPerMs`. */
/** @param {number} pxPerMs */
function tickStep(pxPerMs) {
  for (let power = 1; power < 1e9; power *= 10)
    for (const step of STEPS)
      if (step * power * pxPerMs >= AXIS_TICK_SPACING) return step * power;
  return 1e9;
}

/** The decimals that show every multiple of a tick step in seconds. */
/** @param {number} step */
const decimals = (step) => (step >= 1000 ? 0 : step >= 100 ? 1 : step >= 10 ? 2 : 3);

/** A time in milliseconds as seconds, such as "1.2 s": with `digits` decimals, or
 * rounded to the millisecond and written with as few decimals as show it. */
/** @param {number} ms @param {number} [digits] */
export function seconds(ms, digits) {
  const s = ms / 1000;
  return `${digits === undefined ? Number(s.toFixed(3)) : s.toFixed(digits)} s`;
}

/** The ticks between `from` and `to`, clipped to `[0, duration]`: `{time, major,
 * label, flip, step}`. Only a major tick has a label, with the decimals the step
 * needs, and only a major tick's label flips. */
/** @param {number} from @param {number} to @param {number} duration @param {number} pxPerMs */
export function axisTicks(from, to, duration, pxPerMs) {
  const step = tickStep(pxPerMs);
  const minor = step / (String(step)[0] === "2" ? 4 : 5);
  const ticks = [];
  for (let time = Math.floor(from / minor) * minor; time <= to; time += minor) {
    const rounded = Math.round(time * 1000) / 1000;
    if (rounded < 0 || rounded > duration) continue;
    const major = Math.abs(rounded / step - Math.round(rounded / step)) < 1e-6;
    ticks.push({
      time: rounded,
      major,
      label: major ? seconds(rounded, rounded === 0 ? 0 : decimals(step)) : null,
      flip: major && (duration - rounded) * pxPerMs < LABEL_ROOM,
      step,
    });
  }
  return ticks;
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

/** @type {ReturnType<typeof canvas2D> | null} */
let measuring = null;
/** The advance width of `text` set in a CSS `font` shorthand. */
/** @param {string} text @param {string} font */
export function textWidth(text, font) {
  measuring ??= canvas2D(document.createElement("canvas"));
  measuring.font = font;
  return measuring.measureText(text).width;
}
