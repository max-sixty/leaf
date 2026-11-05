// @ts-check
/* The change walk: `h` and Shift+`h` step through the changes the version comparison
   marks (version.js, `comparisonChanges`), each a hunk of the block diff, in the page's
   order, coming round at either end, while a comparison stands (`v`, or a Compare in
   Versions). A diff reader's next and previous hunk, which is what the letter stands
   for.

   A step starts from the user's place by the rule every page walk shares
   (current-target.js, `walkOrigin` and `stepFrom`), and lands on the change: on the
   block it starts with, or, where it only took blocks out, on its gap's stand-in
   (margin-bars.js, `removalProxy`), which rings the gap, since the block beside the gap
   didn't change. It brings the change into view where it is not, and says the walk's
   position as every walk says it (walk-position.js). A current location anywhere in a
   change's blocks, or on its gap's stand-in, is on that change, so the next step goes
   on to the following one, even from one of two gaps beside one block to the other;
   from any other origin a step compares only where each change stands, as an editor's
   next-hunk key does. The change's margin entry, and a gap's stand-in, open what it
   replaced over it (version.js, `toggleChangeCard`).

   The marks are annotations, so `o` hides them with the rest, and nothing here stops
   them: a comparison ends with `v` or its Compare in Versions. The user decided
   on 31 October against a stop of their own, an Escape step and a menu row, which no
   other annotation has. A finger needs no row for the walk (keyboard/AGENTS.md, "Touch
   routes"): every change is marked where it stands, and its margin entry and Page Map
   row reach it with a tap. */
import { comparisonBase, comparisonChanges } from "./version.js";
import { removalProxy } from "./margin-bars.js";
import { effect, untracked } from "/runtime/framework.js";
import { pageCommand } from "./keyboard/register.js";
import { paintKeys } from "./keyboard/scopes.js";
import { cycledRow } from "./keyboard/bindings.js";
import { currentLocationOrigin, stepFrom, walkOrigin } from "./current-target.js";
import { focusDestination } from "./focus.js";
import { alreadyShown, scrollIntoView } from "./landing-scroll.js";
import { scrollBehavior } from "./motion.js";
import { renderedUnder } from "./shadow-tree.js";
import { announce } from "./notifications.js";
import { repaint } from "./repaint.js";
import { beginWalk, listWalkPosition } from "./walk-position.js";

/** @typedef {import("./version.js").Change} Change */
// Where a change stands in the page's order.
const start = (/** @type {Change} */ change) => change.at;
// Where a step puts the user: the change's first block, or its gap's stand-in.
/** @param {Change} change */
const landing = (change) => change.blocks[0] ?? removalProxy(change) ?? change.at;

// The change the user's current location is on, if any.
/** @param {readonly Change[]} list */
const currentChange = (list, origin = currentLocationOrigin()) =>
  origin?.kind === "current-location"
    ? (list.find((change) =>
        change.blocks.length
          ? change.blocks.some((block) => renderedUnder(origin.node, block))
          : origin.node === removalProxy(change),
      ) ?? null)
    : null;

const position = () => {
  const list = comparisonChanges();
  const base = comparisonBase();
  return listWalkPosition(list, currentChange(list), {
    identity: landing,
    qualifier: base ? `since ${base.name}` : "",
  });
};

/** @param {import("./keyboard/bindings.js").Step} dir */
function step(dir) {
  const list = comparisonChanges();
  const origin = walkOrigin();
  const current = currentChange(list, origin);
  const change = current
    ? cycledRow(list, current, dir)
    : stepFrom(list, origin, dir, start);
  if (!change) return;
  // A gap's stand-in brings the gap into view as it takes focus (margin-bars.js).
  if (change.blocks.length && !alreadyShown(change.at, { block: "start" }))
    scrollIntoView(change.at, { behavior: scrollBehavior(), block: "start" });
  focusDestination(landing(change), "move");
  const said = beginWalk("change", "Change", position);
  if (said) announce(said);
}

export function createChangeWalk() {
  const offered = () => comparisonChanges().length > 0;
  let wasOffered = false;
  let watching = null;
  pageCommand({
    id: "change.walk",
    touch: false,
    keys: ["h", "Shift+h"],
    routes: [
      { id: "change.next", binding: "h", title: "Next change" },
      { id: "change.previous", binding: "Shift+h", title: "Previous change" },
    ],
    title: "changes",
    when: offered,
    repeat: true,
    travels: true,
    runKey: (binding) => step(binding === "h" ? 1 : -1),
  });
  // The row stands while a comparison marks anything, so the surfaces reading the keys
  // are repainted where the marks come or go.
  return {
    mount() {
      watching ??= effect(() => {
        if (offered() === wasOffered) return;
        wasOffered = offered();
        untracked(() => {
          paintKeys();
          repaint();
        });
      });
    },
  };
}
