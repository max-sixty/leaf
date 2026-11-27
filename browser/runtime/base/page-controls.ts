/* The page's controls as the lines of a menu, which the floating panel's menu draws
 * (panel/floating-panel.js) without naming any of them.
 *
 * A module registers each control it offers once, as one row: its `label` (for a row
 * that copies, the text it copies named as it reads mid-sentence, such as "link", which a
 * presentation puts after "Copy" and capitalizes to head a line), a terse `value` such as
 * a count, the `command` its press runs, whose Go-to key the row wears
 * (panel/page-keys/go-to-sequence.js, `data-lf-command`), the `shortcut` that reaches it
 * from the keyboard as its steps, each spelled as a key chip spells it, where it isn't
 * that command's own (dom/keyboard/control-keys.js, `commandSteps`), the `group` of
 * controls it belongs with, what a row that copies grants that its text doesn't say,
 * which a pointer resting on the row reads and About shows under it (`title`), the text
 * it copies where it copies one (`copies`), whether
 * it is `offered` now, whether its news is `urgent` (the words that say so, or null),
 * whether it is `disabled`, and the `press` that runs it, given the place the
 * presentation held when the user opened it (records/history.js, `readPlace`). A row that is a
 * view of the panel's own, such as Threads, has no press: the panel opens the view.
 *
 * An `exit` row is the way out of the stance the user is in, such as page search or
 * Draw mode (panel/page-keys/touch-controls.js), which stands in the panel's row before the
 * leaf as a ✕. No other row stands in the panel's row: what a gesture does next, a
 * finger does on what the gesture acts on (dom/keyboard/AGENTS.md, "Touch routes").
 *
 * Each field may be a value or a function read when the rows are read, so a paint that
 * reads them follows their native signals.
 * A row whose answer moves outside the page's readings, such as a stance's way out, says
 * so with `pageControlsChanged`, which publishes that invalidation as a signal. */
import { signal } from "/vendor/signals-core.js";
import { afterScript } from "./rendering.js";
import type { WorkingPlace } from "./held-place.js";

const EMPTY: readonly string[] = Object.freeze([]);

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
// reads stays short and a finger keeps a way to each. A row that says which session,
// preview or Leaf the page runs (`about`) stands in About this page alone, which lists
// every row that copies (panel/page-inspection.js); the user chose that over
// each such copy also standing in the menu.
export type PageControlGroup = "page" | "navigate" | "annotate" | "keys" | "about";

const rows: Map<string, PageControl & { sequence: number }> = new Map();
let sequence = 0;
const revision = signal(0);

const read = <T extends string | boolean | readonly string[] | null | undefined>(
  value: T | (() => T),
): T => (typeof value === "function" ? value() : value);

type PageControl = {
  key: string;
  rank: number;
  label: string | (() => string);
  group: PageControlGroup | (() => PageControlGroup);
  value?: string | (() => string);
  title?: string | (() => string);
  command?: string;
  shortcut?: readonly string[] | (() => readonly string[]);
  copies?: string | (() => string);
  offered?: boolean | (() => boolean);
  urgent?: string | null | (() => string | null);
  disabled?: boolean | (() => boolean);
  exit?: boolean;
  action?: string | (() => string);
  press?: (held: WorkingPlace | null) => unknown;
};

/** Register one row of the page's controls. */
export function registerPageControl(row: PageControl) {
  if (!row.key || !Number.isFinite(row.rank) || !row.label)
    throw new TypeError(
      `Page control ${row.key} needs a key, a numeric rank and a label`,
    );
  if (rows.has(row.key)) throw new TypeError(`Page control ${row.key} is registered`);
  rows.set(row.key, Object.freeze({ ...row, sequence: sequence++ }));
  pageControlsChanged();
}

/** The rows offered now, in rank order, each read as it reads now. A row's group is
 * read when asked, since the panel takes these rows on each paint to find its way out
 * and only a menu asks for the group, which can force a layout. */
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
        command: row.command ?? null,
        shortcut: read(row.shortcut) ?? EMPTY,
        get group() {
          return read(row.group);
        },
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
