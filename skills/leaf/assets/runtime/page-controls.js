/* The page's controls as the lines of a menu, which the floating panel's menu draws
 * (floating-panel.js) without naming any of them.
 *
 * A module registers each control it offers once, as one row: its `label` (for a row
 * that copies, the text it copies named as it reads mid-sentence, such as "link", which a
 * presentation puts after "Copy" and capitalizes to head a line), a terse `value` such as
 * a count, the `shortcut` that reaches it from the keyboard as its steps, each spelled as
 * a key chip spells it (keyboard/control-keys.js, `commandSteps`), the `group` of
 * controls it belongs with, the text it copies where it copies one (`copies`), whether
 * it is `offered` now, whether its news is `urgent` (the words that say so, or null),
 * whether it is `disabled`, and the `press` that runs it, given the place the
 * presentation held when the user opened it (history.js, `readPlace`). A row that is a
 * view of the panel's own, such as Threads, has no press: the panel opens the view.
 *
 * A `gesture` row is the next step of something the user is doing right now, such as
 * commenting on the words a touch just selected, or a finger's way out of the mode it
 * stands in. It stands in the panel's row while that gesture holds it, and the higher
 * rank is the nearer gesture: one contributor's steps stand at a time.
 *
 * Each field may be a value or a function read when the rows are read, so a paint that
 * reads them through `watchProjection` (projection-watch.js) follows what they read.
 * A row whose answer moves outside the page's readings, such as a mode's steps, says
 * so with `pageControlsChanged`, and `watchPageControls` hears it. */
import { afterScript } from "./rendering.js";

const EMPTY = Object.freeze([]);

// Where each contributor's rows stand, among the others'.
export const PAGE_CONTROL_RANK = Object.freeze({
  session: 10,
  preview: 20,
  layer: 30,
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
  // The next steps in the mode or picker the user stands in.
  steps: 120,
  commentSelection: 130,
});

// What a row is about, which decides where a menu built from rows puts it: on the menu
// itself (`page`), behind its Navigate, Annotations or About entry, or, for a keyboard's
// convenience for where the reader stands, such as Resume writing (`keys`), behind
// Navigate only where no keyboard is there to reach it, so the menu a keyboard user
// reads stays short and a finger keeps a way to each.
const GROUPS = Object.freeze(["page", "navigate", "annotate", "about", "keys"]);

const rows = new Map();
let sequence = 0;
const listeners = new Set();

const read = (value) => (typeof value === "function" ? value() : value);

/**
 * Register one row of the page's controls.
 *
 * @param {{
 *   key: string,
 *   rank: number,
 *   label: string | (() => string),
 *   group: string,
 *   value?: string | (() => string),
 *   shortcut?: readonly string[] | (() => readonly string[]),
 *   copies?: string | (() => string),
 *   offered?: boolean | (() => boolean),
 *   urgent?: string | null | (() => string | null),
 *   disabled?: boolean | (() => boolean),
 *   gesture?: boolean,
 *   press?: (held?: any) => void,
 * }} row
 */
export function registerPageControl(row) {
  if (
    !row.key ||
    !Number.isFinite(row.rank) ||
    !row.label ||
    !GROUPS.includes(row.group)
  )
    throw new TypeError(
      `Page control ${row.key} needs a key, a numeric rank, a label and one of the groups ${GROUPS.join(", ")}`,
    );
  if (rows.has(row.key)) throw new TypeError(`Page control ${row.key} is registered`);
  rows.set(row.key, Object.freeze({ ...row, sequence: sequence++ }));
  pageControlsChanged();
}

/** The rows offered now, in rank order, each read as it reads now. Of the gesture rows,
 * only the nearest gesture's stand. */
export function pageControls() {
  const offered = [...rows.values()]
    .sort((a, b) => a.rank - b.rank || a.sequence - b.sequence)
    .filter((row) => read(row.offered) ?? true);
  const nearest = Math.max(
    ...offered.filter((row) => row.gesture).map((row) => row.rank),
  );
  return offered
    .filter((row) => !row.gesture || row.rank === nearest)
    .map((row) =>
      Object.freeze({
        key: row.key,
        label: read(row.label),
        value: read(row.value) ?? "",
        shortcut: read(row.shortcut) ?? EMPTY,
        group: row.group,
        copies: read(row.copies) ?? "",
        urgent: read(row.urgent) ?? null,
        gesture: Boolean(row.gesture),
        disabled: Boolean(read(row.disabled)),
        press: row.press ?? null,
      }),
    );
}

/** Say that a row's answer moved outside the page's readings. Several in one script are
 * heard once, when it ends. */
export const pageControlsChanged = () => afterScript(tell);
function tell() {
  for (const listener of listeners) listener();
}

/** Call `listener` after each change `pageControlsChanged` reports; returns the way to
 * stop. */
export function watchPageControls(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
