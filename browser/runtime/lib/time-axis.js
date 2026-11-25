/* A horizontal time axis, shared by the widgets that draw one: its geometry, its ruler
 * and its gridlines. Times are milliseconds from the axis origin; positions are pixels
 * along the drawn span, which starts and ends AXIS_EDGE inside the drawing. Nothing
 * here touches the DOM, so a widget can call it while drawing, before its upgrade as
 * well as after.
 *
 * `timeAxis` returns the ruler's ticks and the gridlines as Lit templates. The widget
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
 * Ruler ticks fall on 1, 2 and 5 × 10^k milliseconds, the smallest step that keeps
 * major ticks AXIS_TICK_SPACING apart, with three or four minor ticks between them. A
 * major tick's label reads back from its tick (`flip`) where reading on from it would
 * run past the axis's end. Rows are greedy: an extent takes the first row whose last
 * extent ended at or before its start, so overlapping extents never share a row and
 * the row count is the smallest that greedy order allows.
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
function axisTicks(from, to, duration, pxPerMs) {
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

/** The axis from `from` to `to`, as templates: `ruler`, a tick at each time, and
 * `grid`, a line at each major tick's time. `duration`, above zero, is the time the
 * whole axis spans, and `pxPerMs` its scale. A widget that shows a window of a longer
 * axis, as a zoomed one does, passes the window's times and draws again when the
 * window moves; a tick or line that both windows hold stays the element it was. Each
 * states its time as `--lf-axis-at`, the time over `duration`. */
/** @param {number} from @param {number} to @param {number} duration @param {number} pxPerMs */
export function timeAxis(from, to, duration, pxPerMs) {
  const ticks = axisTicks(from, to, duration, pxPerMs);
  /** @param {(typeof ticks)[number]} tick */
  const key = (tick) => `${tick.step}:${tick.time}`;
  /** @param {(typeof ticks)[number]} tick */
  const at = (tick) => `--lf-axis-at: ${tick.time / duration}`;
  return {
    ruler: repeat(
      ticks,
      key,
      (tick) =>
        html`<span
          class="lf-axis-tick"
          ?data-lf-major=${tick.major}
          ?data-lf-flip=${tick.flip}
          style=${at(tick)}
          >${tick.label ?? nothing}</span
        >`,
    ),
    grid: repeat(
      ticks.filter((tick) => tick.major),
      key,
      (tick) =>
        html`<span
          class="lf-axis-gridline"
          ?data-lf-flip=${tick.flip}
          style=${at(tick)}
        ></span>`,
    ),
  };
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
