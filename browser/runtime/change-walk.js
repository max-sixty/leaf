// @ts-check
/* The change walk: `h` and Shift+`h` step through the blocks the version comparison
   marks (version.js, `comparisonChanges`), in the page's order, coming round at either
   end, whatever started the comparison: a Compare in Versions, or the page marking what
   changed since the user was last shown it (since-seen.js). A diff reader's next and
   previous hunk, which is what the letter stands for.

   A step starts from the user's place by the rule every page walk shares
   (current-target.js, `walkOrigin` and `stepFrom`), and lands on the changed block
   itself, brought whole into view where it is not, with the walk's position said as
   every walk says it (walk-position.js). The change's margin entry opens what the
   block said before (version.js, `toggleInlineComparison`).

   The marks are annotations, so `o` hides them with the rest, and nothing here stops
   them: an offered comparison gives way to the next one a return brings
   (since-seen.js), and a chosen one ends with its Compare in Versions. The user decided
   on 31 October against a stop of their own, an Escape step and a menu row, which no
   other annotation has. A finger needs no row for the walk (keyboard/AGENTS.md, "Touch
   routes"): every change is marked where it stands, and its margin entry and Page Map
   row reach it with a tap. */
import { comparisonBase, comparisonChanges } from "./version.js";
import { effect, untracked } from "/runtime/framework.js";
import { pageCommand } from "./keyboard/register.js";
import { paintKeys } from "./keyboard/scopes.js";
import { cycledRow } from "./keyboard/bindings.js";
import { currentLocationOrigin, stepFrom, walkOrigin } from "./current-target.js";
import { focusDestination } from "./focus.js";
import { alreadyShown, scrollIntoView } from "./landing-scroll.js";
import { scrollBehavior } from "./motion.js";
import { byRenderedOrder, renderedUnder } from "./shadow-tree.js";
import { announce } from "./notifications.js";
import { repaint } from "./repaint.js";
import { beginWalk, listWalkPosition } from "./walk-position.js";

const changes = () =>
  /** @type {Element[]} */ (
    byRenderedOrder(comparisonChanges(), (/** @type {Element} */ block) => block)
  );

// The change the user's current location is in, if any.
/** @param {Element[]} list */
const currentChange = (list, origin = currentLocationOrigin()) =>
  origin?.kind === "current-location"
    ? (list.find((block) => renderedUnder(origin.node, block)) ?? null)
    : null;

const position = () => {
  const list = changes();
  const base = comparisonBase();
  return listWalkPosition(list, currentChange(list), {
    qualifier: base ? `since ${base.name}` : "",
  });
};

/** @param {number} dir */
function step(dir) {
  const list = changes();
  const origin = walkOrigin();
  const current = currentChange(list, origin);
  const next = current
    ? cycledRow(list, current, dir)
    : stepFrom(list, origin, dir, (/** @type {Element} */ block) => block);
  if (!next) return;
  if (!alreadyShown(next))
    scrollIntoView(next, { behavior: scrollBehavior(), block: "start" });
  focusDestination(next, "move");
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
    run: (/** @type {string} */ binding) => step(binding === "h" ? 1 : -1),
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
