// @ts-check
/* The change walk: `h` and Shift+`h` step through the changes the version comparison
   marks (features/version.js, `comparisonChanges`), each a hunk of the block diff, in the page's
   order, coming round at either end, while a comparison stands (a Compare in
   Versions, which `g V v` presses, or the return notice's Show changes). A diff
   reader's next and previous hunk, which is what the letter stands for.

   A step starts from the user's place by the rule every page walk shares
   (records/current-target.js, `walkOrigin` and `stepFrom`), and lands on the change: on the
   block it starts with, or, where it only took blocks out, on its gap's stand-in
   (features/margin-bars.js, `removalProxy`), which rings the gap, since the block beside the gap
   didn't change. It brings the change into view where it is not, and says the walk's
   position as every walk says it (records/walk-position.js), a listener hearing after it what
   the version was saved after (features/change-provenance.js). A current location anywhere in a
   change's blocks, or on its gap's stand-in, is on that change, so the next step goes
   on to the following one, even from one of two gaps beside one block to the other;
   from any other origin a step compares only where each change stands, as an editor's
   next-hunk key does. The change's margin entry, and a gap's stand-in, open what it
   replaced over it (features/version.js, `toggleChangeCard`).

   The marks are annotations, so `g H` hides them with the rest, and nothing here stops
   them: a comparison ends with its Compare in Versions, which `g V v` presses again.
   The user decided against a stop of their own, an Escape step and a menu row, which
   no other annotation has. A finger needs no row for the walk (dom/keyboard/AGENTS.md, "Touch
   routes"): every change is marked where it stands, and its margin entry and Page Map
   row reach it with a tap.

   With no comparison standing, or one that marks nothing, a press says "No changes
   marked" in the panel (transport/notifications.js, `notice`), as every page walk with nothing to
   step through says so (dom/keyboard/AGENTS.md, "Page grammar"), so the key is live on
   every page. While a comparison a press started is still loading, its marks aren't
   known yet, so the key isn't taken rather than saying none are marked. */
import {
  comparisonBase,
  comparisonChanges,
  selectedBase,
} from "../features/version.js";
import { versionProvenance } from "../features/change-provenance.js";
import { wordsText } from "../base/voice.js";
import { removalProxy } from "../features/margin-bars.js";
import { pageCommand } from "../dom/keyboard/register.js";
import { cycledRow } from "../dom/keyboard/bindings.js";
import {
  currentLocationOrigin,
  stepFrom,
  walkOrigin,
} from "../records/current-target.js";
import { focusDestination } from "../dom/focus.js";
import { alreadyShown, scrollIntoView } from "../readings/landing-scroll.js";
import { scrollBehavior } from "../dom/motion.js";
import { renderedUnder } from "../lib/shadow-tree.js";
import { announce, notice } from "../transport/notifications.js";
import { beginWalk, listWalkPosition } from "../records/walk-position.js";

/** @typedef {import("../features/version.js").Change} Change */
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

// "Change 1 of 5 since v2". The changes are the comparison's (`about`), which the
// panel's field says while it stands, "5 changes since v2" (floating-panel.js,
// `standing`), so the field says the walk's place alone, "1 of 5".
const position = () => {
  const list = comparisonChanges();
  const base = comparisonBase();
  return listWalkPosition(list, currentChange(list), {
    identity: landing,
    qualifier: base ? `since ${base.name}` : "",
  });
};

/** @param {import("../dom/keyboard/bindings.js").Step} dir */
function step(dir) {
  const list = comparisonChanges();
  const origin = walkOrigin();
  const current = currentChange(list, origin);
  const change = current
    ? cycledRow(list, current, dir)
    : stepFrom(list, origin, dir, start);
  if (!change) return;
  // A gap's stand-in brings the gap into view as it takes focus (features/margin-bars.js).
  if (change.blocks.length && !alreadyShown(change.at, { block: "start" }))
    scrollIntoView(change.at, { behavior: scrollBehavior(), block: "start" });
  focusDestination(landing(change), "move");
  const said = beginWalk("change", "Change", position, { about: "comparison" });
  if (!said) return;
  // A listener hears what the version was saved after too, as the ⇄ entry's label says
  // it under what the change did (features/change-provenance.js).
  const savedAfter = (versionProvenance()?.lines ?? []).map(wordsText).join(" ");
  announce(savedAfter ? `${said}. ${savedAfter}` : said);
}

export function createChangeWalk() {
  pageCommand({
    id: "change.walk",
    ready: () => selectedBase() === comparisonBase(),
    touch: false,
    keys: ["h", "Shift+h"],
    routes: [
      { id: "change.next", binding: "h", title: "Next change" },
      { id: "change.previous", binding: "Shift+h", title: "Previous change" },
    ],
    title: "changes",
    repeat: true,
    travels: true,
    runKey: (binding) =>
      comparisonChanges().length
        ? step(binding === "h" ? 1 : -1)
        : notice("No changes marked", {
            stands: () => !comparisonChanges().length,
          }),
  });
}
