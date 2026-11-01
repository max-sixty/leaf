/* The page's controls as the lines of a menu, which the floating panel's menu draws
 * (floating-panel.js) without naming any of them.
 *
 * A module registers each control it offers once, as one row: its `label` (for a row
 * that copies, the text it copies named as it reads mid-sentence, such as "link", which a
 * presentation puts after "Copy" and capitalizes to head a line), a terse `value` such as
 * a count, the `shortcut` that reaches it from the keyboard as its steps, each spelled as
 * a key chip spells it (keyboard/control-keys.js, `commandSteps`), the `group` of
 * controls it belongs with, the whole words a pointer resting on it reads where its
 * label may be cut, or, for a row that copies, what its text grants that the text
 * doesn't say, which About shows under it (`title`), the text it copies where it
 * copies one (`copies`), whether
 * it is `offered` now, whether its news is `urgent` (the words that say so, or null),
 * whether it is `disabled`, and the `press` that runs it, given the place the
 * presentation held when the user opened it (history.js, `readPlace`). A row that is a
 * view of the panel's own, such as Threads, has no press: the panel opens the view.
 *
 * An `exit` row is the way out of the stance the user is in, such as page search or
 * Draw mode, or the Done of a to-do they stand on (keyboard/touch-controls.js), which
 * stands at the row's end beside its counts as its `action`'s symbol. No other row stands in the panel's row: what a gesture does next, a finger
 * does on what the gesture acts on (keyboard/AGENTS.md, "Touch routes").
 *
 * Each field may be a value or a function read when the rows are read, so a paint that
 * reads them follows their native signals.
 * A row whose answer moves outside the page's readings, such as a stance's way out, says
 * so with `pageControlsChanged`, which publishes that invalidation as a signal. */
import { signal } from "/runtime/framework.js";
import { afterScript } from "./rendering.js";

/** @type {readonly string[]} */
const EMPTY = Object.freeze([]);

// Where each contributor's rows stand, among the others'.
export const PAGE_CONTROL_RANK = Object.freeze({
  session: 10,
  claimant: 15,
  preview: 20,
  layer: 30,
  inspection: 32,
  share: 35,
  leaves: 40,
  latest: 50,
  map: 70,
  // The page's commands reached by pointer here (touch-controls.js), among themselves
  // in the register's order.
  commands: 75,
  blanket: 80,
  versions: 90,
  keyboard: 95,
  // The way out of the stance the user is in.
  exit: 120,
});

// What a row is about, which decides where a menu built from rows puts it: on the menu
// itself (`page`), behind its Navigate or Annotations entry, or, for a keyboard's
// convenience for where the reader stands, such as Resume writing (`keys`), behind
// Navigate only where no keyboard is there to reach it, so the menu a keyboard user
// reads stays short and a finger keeps a way to each.
/** @typedef {"page" | "navigate" | "annotate" | "keys"} PageControlGroup */

/** @type {Map<string, PageControl & {sequence: number}>} */
const rows = new Map();
let sequence = 0;
const revision = signal(0);

/** @template {string | boolean | readonly string[] | null | undefined} T
 * @param {T | (() => T)} value @returns {T} */
const read = (value) => (typeof value === "function" ? value() : value);

/**
 * Register one row of the page's controls.
 *
 * @typedef {{
 *   key: string,
 *   rank: number,
 *   label: string | (() => string),
 *   group: PageControlGroup | (() => PageControlGroup),
 *   value?: string | (() => string),
 *   title?: string | (() => string),
 *   shortcut?: readonly string[] | (() => readonly string[]),
 *   copies?: string | (() => string),
 *   offered?: boolean | (() => boolean),
 *   urgent?: string | null | (() => string | null),
 *   disabled?: boolean | (() => boolean),
 *   exit?: boolean,
 *   action?: string | (() => string),
 *   press?: (held: import("./history.js").WorkingPlace | null) => unknown,
 * }} PageControl
 */
/** @param {PageControl} row */
export function registerPageControl(row) {
  if (!row.key || !Number.isFinite(row.rank) || !row.label || !row.group)
    throw new TypeError(
      `Page control ${row.key} needs a key, a numeric rank, a label and a group`,
    );
  if (rows.has(row.key)) throw new TypeError(`Page control ${row.key} is registered`);
  rows.set(row.key, Object.freeze({ ...row, sequence: sequence++ }));
  pageControlsChanged();
}

/** The rows offered now, in rank order, each read as it reads now. */
export function pageControls() {
  revision.value;
  return [...rows.values()]
    .sort((a, b) => a.rank - b.rank || a.sequence - b.sequence)
    .filter((row) => read(row.offered) ?? true)
    .map((row) =>
      Object.freeze({
        key: row.key,
        label: read(row.label),
        value: read(row.value) ?? "",
        title: read(row.title) ?? "",
        shortcut: read(row.shortcut) ?? EMPTY,
        group: read(row.group),
        copies: read(row.copies) ?? "",
        urgent: read(row.urgent) ?? null,
        exit: Boolean(row.exit),
        action: read(row.action) ?? null,
        disabled: Boolean(read(row.disabled)),
        press: row.press ?? null,
      }),
    );
}

/** Say that a row's answer moved outside the page's readings. Several in one script are
 * heard once, when it ends. */
export const pageControlsChanged = () => afterScript(tell);
function tell() {
  revision.value = revision.peek() + 1;
}
