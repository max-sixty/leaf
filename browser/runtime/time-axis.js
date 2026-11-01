/* Geometry for a horizontal time axis, shared by the widgets that draw one: the
 * Playwright recording timeline (`packages/playwright/widgets/timeline.js`) and
 * `lf-timeline` (`packages/timeline/widgets/timeline-view.js`). Times are milliseconds from the axis origin; positions are
 * pixels along the drawn span. Nothing here touches the DOM except the canvas
 * that measures text, so each widget can call it while drawing.
 *
 * Ruler ticks fall on 1, 2 and 5 × 10^k milliseconds, the smallest step that keeps
 * major ticks TICK_SPACING apart, with four or five minor ticks between them. Rows
 * are greedy: an extent takes the first row whose last extent ended at or before
 * its start, so overlapping extents never share a row and the row count is the
 * smallest that greedy order allows.
 */

import { canvas2D } from "./canvas.js";

const TICK_SPACING = 84;
const STEPS = [1, 2, 5];

/** The major tick step, in milliseconds, for a scale of `pxPerMs`. */
/** @param {number} pxPerMs */
function tickStep(pxPerMs) {
  for (let power = 1; power < 1e9; power *= 10)
    for (const step of STEPS)
      if (step * power * pxPerMs >= TICK_SPACING) return step * power;
  return 1e9;
}

/** A major tick's words: seconds, with as many decimals as the step needs. */
/** @param {number} time @param {number} step */
function tickLabel(time, step) {
  if (time === 0) return "0 s";
  const digits = step >= 1000 ? 0 : step >= 100 ? 1 : step >= 10 ? 2 : 3;
  return `${(time / 1000).toFixed(digits)} s`;
}

/** The ticks between `from` and `to`, clipped to `[0, duration]`: `{time, major,
 * label, step}`, where only a major tick has a label. */
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
      label: major ? tickLabel(rounded, step) : null,
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
