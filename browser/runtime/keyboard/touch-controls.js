/* The page's commands a finger reaches, as rows of the page's controls (page-controls.js).
 * `touch` names a page command a finger needs a row for; the same row serves a mouse, and
 * stands in the floating panel's menu. A scope with a row marked `exit` is a stance, such
 * as page search or Draw mode, or a to-do the user stands on, whose Done ends it: while
 * the innermost one stands (dispatch.js, `innermostStance`), the panel's row offers
 * that row as its one way out, drawn as the row's `action` (Close's ✕ unless it names one), and
 * the panel says the scope's `says`, else its title (status-context.js). Words,
 * availability and activation all come from the same row as keyboard dispatch.
 *
 * A command's words and liveness are read in the repaint frame (`paintTouchControls`),
 * where the register is read, rather than in a presentation's paint: a liveness
 * predicate may read the whole log, which a paint that follows what it reads must not
 * (leaf-element.js). A change in what stands is said with `pageControlsChanged`.
 */
import {
  PAGE_CONTROL_RANK,
  pageControlsChanged,
  registerPageControl,
} from "../page-controls.js";
import { returnPlace } from "../history.js";
import { bindings, descriptionOf, live, spell, titleOf, word } from "./bindings.js";
import { innermostStance, invokePress } from "./dispatch.js";
import { touchPresses } from "./register.js";

// Each press's latest reading, by the command it invokes, and how its row reads now.
/** @typedef {ReturnType<typeof touchPresses>[number]} TouchPress
 * @typedef {{label: string, shortcut: string[], disabled: boolean}} Face
 * @typedef {{label: string, action: keyof typeof import("../icon-paths.js").ACTIONS, disabled: boolean, press: {id: string, row: import("./bindings.js").Command, binding: undefined}}} StanceFace
 */
/** @type {Map<string, {press: TouchPress, face: Face | undefined}>} */
const presses = new Map();

/** @param {TouchPress} press */
function place(press) {
  const known = presses.get(press.id);
  if (known) {
    known.press = press;
    return press.id;
  }
  /** @type {{press: TouchPress, face: Face | undefined}} */
  const record = { press, face: undefined };
  presses.set(press.id, record);
  const face = () => record.face;
  registerPageControl({
    key: `command:${press.id}`,
    rank: PAGE_CONTROL_RANK.commands,
    label: () => face()?.label ?? "",
    // The row's value and its description, as the reference's tooltip says it, whole
    // where the menu's row cuts its words, are read where the menu paints, so one that
    // says how long ago, as Undo's does, follows the page's clock (presence.js,
    // `clockValue`) rather than standing as the repaint frame last read it.
    value: () => (face() ? (word(record.press.row.touchValue) ?? "") : ""),
    title: () => (face() ? descriptionOf(record.press.row) : ""),
    shortcut: () => face()?.shortcut ?? [],
    // A page command says which of a menu's groups it belongs with (`menu`).
    group: press.row.menu ?? "page",
    offered: () => Boolean(face()),
    disabled: () => face()?.disabled ?? true,
    // A command that acts on where the reader stood gets that place back before it runs.
    press: /** @param {Parameters<typeof returnPlace>[0] | null} held */ (held) => {
      const current = record.press;
      if (current.row.retainCurrentLocation && held) returnPlace(held);
      if (live(current.row)) invokePress(current);
    },
  });
  return press.id;
}

// The way out of the stance the user is in now: its row's words and latest press.
/** @type {StanceFace | null} */
let stance = null;
let stanceRegistered = false;

function placeStanceExit() {
  if (stanceRegistered) return;
  stanceRegistered = true;
  registerPageControl({
    key: "stance:exit",
    rank: PAGE_CONTROL_RANK.exit,
    exit: true,
    label: () => stance?.label ?? "",
    action: () => stance?.action ?? "close",
    group: "page",
    offered: () => Boolean(stance),
    disabled: () => stance?.disabled ?? true,
    press: () => {
      if (stance && live(stance.press.row)) invokePress(stance.press);
    },
  });
}

/** @param {StanceFace | null} a @param {StanceFace | null} b */
const sameStance = (a, b) =>
  a?.label === b?.label && a?.disabled === b?.disabled && a?.action === b?.action;

/** @param {Face | undefined} a @param {Face | undefined} b */
const same = (a, b) =>
  a?.label === b?.label &&
  a?.disabled === b?.disabled &&
  a?.shortcut.join(" ") === b?.shortcut.join(" ");

export function paintTouchControls() {
  const shown = new Set(touchPresses().map(place));
  let changed = false;
  const held = innermostStance();
  if (held) placeStanceExit();
  const title = held ? titleOf(held.exit) : "";
  /** @type {StanceFace | null} */
  const nextStance = held
    ? {
        label: title.charAt(0).toUpperCase() + title.slice(1),
        action: held.exit.action ?? "close",
        disabled: !live(held.exit),
        press: { id: held.exit.id, row: held.exit, binding: undefined },
      }
    : null;
  if (!sameStance(nextStance, stance)) changed = true;
  stance = nextStance;
  for (const [id, record] of presses) {
    const { press } = record;
    const [binding] = bindings(press.row);
    const next = shown.has(id)
      ? {
          label: word(press.words),
          shortcut: binding ? [spell(binding)] : [],
          disabled: !live(press.row),
        }
      : undefined;
    if (same(next, record.face)) continue;
    changed = true;
    record.face = next;
  }
  if (changed) pageControlsChanged();
}
