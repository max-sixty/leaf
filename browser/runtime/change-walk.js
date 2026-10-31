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

   The marks stand until the reader stops them, with Escape once nothing nearer is
   open or with Stop marking changes in the leaf's menu. That is not a stance
   (keyboard/touch-controls.js): marks can stand a whole visit, and a stance's ✕ would
   hold the panel's On me chip for all of it. A finger needs no row for the walk
   (keyboard/AGENTS.md, "Touch routes"): every change is marked where it stands, and
   its margin entry and Page Map row reach it with a tap. */
import { comparisonBase, comparisonChanges, stopComparison } from "./version.js";
import { effect, untracked } from "/runtime/framework.js";
import { pageCommand, pageRung } from "./keyboard/register.js";
import { paintKeys } from "./keyboard/scopes.js";
import { nativeLayers } from "./keyboard/layer-stack.js";
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
  // Marks stand until the reader stops them: Escape, once nothing nearer is open, and a
  // row of the leaf's menu for a pointer or a finger. Under an open native layer, as
  // under the page's own rung, Escape is that layer's.
  pageRung("changes", () =>
    offered() && !nativeLayers().length
      ? { title: "stop marking changes", out: stopComparison }
      : null,
  );
  pageCommand({
    id: "change.marks.stop",
    keys: [],
    title: "stop marking changes",
    touch: "Stop marking changes",
    when: offered,
    run: stopComparison,
  });
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
