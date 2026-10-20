/* The page's commands a finger reaches, as rows of the page's controls (page-controls.js).
 * `touch` names a row a finger needs; the same row serves a mouse. Page commands stand in
 * the floating panel's menu, and the innermost active scope supplies gesture steps,
 * which stand in its row. A scope with a row marked `exit` is a stance, such as page
 * search or Draw mode: while the innermost one stands, the panel's row offers that row
 * as its one way out (`stance`), and the panel says the scope's title
 * (status-context.js). Words, availability and activation all come from the same row as
 * keyboard dispatch.
 *
 * A command's words and liveness are read in the repaint frame (`paintTouchControls`),
 * where the register is read, rather than in a presentation's paint: a liveness
 * predicate may read the whole log, which a paint that follows what it reads must not
 * (projection-watch.js). A change in what stands is said with `pageControlsChanged`.
 */
import {
  PAGE_CONTROL_RANK,
  pageControlsChanged,
  registerPageControl,
} from "../page-controls.js";
import { returnPlace } from "../history.js";
import { bindings, live, spell, titleOf, word } from "./bindings.js";
import { invokePress, standing } from "./dispatch.js";
import { touchPresses } from "./register.js";

// Each press's latest reading, by the command it invokes, and how its row reads now.
const presses = new Map();
const faces = new Map();

function place(press, gesture) {
  const known = presses.has(press.id);
  presses.set(press.id, press);
  if (known) return press.id;
  const face = () => faces.get(press.id);
  registerPageControl({
    key: `command:${press.id}`,
    rank: gesture ? PAGE_CONTROL_RANK.steps : PAGE_CONTROL_RANK.commands,
    gesture,
    label: () => face()?.label ?? "",
    shortcut: () => face()?.shortcut ?? [],
    // A page command says which of a menu's groups it belongs with (`menu`).
    group: press.row.menu ?? "page",
    offered: () => Boolean(face()),
    disabled: () => face()?.disabled ?? true,
    // A command that acts on where the reader stood gets that place back before it runs.
    press: (held) => {
      const current = presses.get(press.id);
      if (current.row.retainStanding && held) returnPlace(held);
      if (live(current.row)) invokePress(current);
    },
  });
  return press.id;
}

// The stance the user stands in now: its scope's title, and its exit row's words and
// latest press.
let stance = null;
let stanceRegistered = false;
/** The title of the stance the user stands in, or null. */
export const stanceReading = () => stance?.title ?? null;

function placeStanceExit() {
  if (stanceRegistered) return;
  stanceRegistered = true;
  registerPageControl({
    key: "stance:exit",
    rank: PAGE_CONTROL_RANK.steps,
    exit: true,
    label: () => stance?.label ?? "",
    group: "page",
    offered: () => Boolean(stance),
    disabled: () => stance?.disabled ?? true,
    press: () => {
      if (stance && live(stance.press.row)) invokePress(stance.press);
    },
  });
}

const sameStance = (a, b) =>
  a?.title === b?.title && a?.label === b?.label && a?.disabled === b?.disabled;

const same = (a, b) =>
  a?.label === b?.label &&
  a?.disabled === b?.disabled &&
  a?.shortcut.join(" ") === b?.shortcut.join(" ");

export function paintTouchControls() {
  const { commands, steps, exits } = touchPresses();
  // Every step is placed before any is shown, so the row orders them as they are declared
  // rather than by which the user happened to reach first.
  for (const { presses: scoped } of steps)
    for (const press of scoped) place(press, true);
  const innermost = steps.find(({ scope }) => standing(scope));
  const shown = new Set([
    ...commands.map((press) => place(press, false)),
    ...(innermost?.presses.map((press) => press.id) ?? []),
  ]);
  let changed = false;
  if (exits.length) placeStanceExit();
  const exit = exits.find(({ scope }) => standing(scope));
  const title = exit && titleOf(exit.press.row);
  const nextStance = exit
    ? {
        title: word(exit.scope.title),
        label: title[0].toUpperCase() + title.slice(1),
        disabled: !live(exit.press.row),
        press: exit.press,
      }
    : null;
  if (!sameStance(nextStance, stance)) changed = true;
  stance = nextStance;
  for (const [id, press] of presses) {
    const [binding] = bindings(press.row);
    const next = shown.has(id)
      ? {
          label: word(press.words),
          shortcut: binding ? [spell(binding)] : [],
          disabled: !live(press.row),
        }
      : undefined;
    if (same(next, faces.get(id))) continue;
    changed = true;
    if (next) faces.set(id, next);
    else faces.delete(id);
  }
  if (changed) pageControlsChanged();
}
