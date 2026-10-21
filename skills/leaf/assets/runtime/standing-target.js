/* Where the user stands: the page node a focused node stands at, one reading every
   feature takes (glossary, Standing target).

   An ordinary node on the page stands at itself. So does a node inside any obligation source in the inventory,
   answered or not, wherever it is drawn: an obligation frozen into a reply is where a user
   working it is, never the page obligation its thread is about. A presentation can stand at the
   source target it shows in authored flow or chrome, as its owner declares (`declareSide`): the margin for its
   cluster controls and the thread card; the details shelf for the elements that name its notes; the
   floating panel for a thread's view, at what the thread is about, open or resolved, and an On
   card, at its obligation. A side's answer drawn in the chrome itself, such as a margin
   control's widget frozen into a reply, is where the user stands only where an obligation
   holds it; else the user stands where that answer does, by the same reading, so a control
   on a widget in a reply the panel or a card shows stands at what the thread is about,
   whichever side is asked first. Chrome no side
   claims — the floating panel's row, menu and lists — stands nowhere, and a
   press made from it means the page whole.

   Each feature takes what it needs from that place by its own rule: the obligation view the
   obligation source or unique enclosing widget holding it, `c` and `e` its semantic target, the walks its place
   in the page's order. Every side answers alike: an open obligation stood at from its card still wears its
   ring and takes its digits, `c` at an element whose own thread is shown continues it,
   and `m` and `t` step from the target.

   Standing is not arriving. The floating panel shows its thread or obligation beside
   the page (`declareSide`'s `beside`), so the user in it has not arrived at the target,
   and what follows an arrival, the margin's card and its folded pins, reads `arrivalOf`,
   which leaves such sides out.

   The chrome stands over the page rather than in it and is appended after it,
   so a chrome node measured as a place would put the user behind every obligation and thread
   there is; no reader measures from one that does not stand in an obligation.

   `standingOrigin` reads focus, then the selection's ends, returning null when
   neither names a place on the page.
   Page walks share `walkOrigin`, which starts at that standing or the first visible
   reading block. A selected tab starts a walk at its controlled panel,
   where the user is reading, without changing comment targets.
   Every press reads the browser afresh; no walk remembers a
   destination to use as the user's current place. They step from it by one rule,
   `stepFrom`, in the page's rendered order (`renderedOrder`, shadow-tree.js), so a place
   inside a widget's shadow tree is ordered among the places beside it there rather than
   at its host. */
import { cycledRow } from "./keyboard/bindings.js";
import { focused, standingNodes } from "./focus.js";
import { inChrome } from "./passages.js";
import { readObligations } from "./obligations/model.js";
import { obligationPlace } from "./obligations/place.js";
import { renderedOrder, renderedUnder, under } from "./shadow.js";
import { pageReadingBlock } from "./reading-place.js";

// Each side's reading, and whether it shows its target beside the page.
const sides = new Map();

// A presentation owner's reading of the source target one of its nodes shows, or null.
// A side is asked of the node the user stands on, inside any shadow tree it is in, so
// each climbs across shadow roots to its own surface. A side `beside` the page, as the
// floating panel is, shows its target away from it: the user there stands at the target
// but has not arrived at it (`arrivalOf`).
export function declareSide(bridge, { beside = false } = {}) {
  sides.set(bridge, beside);
  return () => sides.delete(bridge);
}

// The innermost obligation whose source, or whose own enclosing widget, is or holds `node`.
// An enclosing widget shared by several sources cannot identify one of them on its own,
// so only a source stands for such an obligation (`obligationPlace`). Obligations nest, as a question
// inside a proposal's new text does, so the nearest place holding the node names the
// obligation rather than the kind of place: on the inner question's enclosing widget the user
// stands on that question, not on the proposal whose source holds it.
export function obligationHolding(items, node) {
  if (!node) return null;
  const holds = (element) => element && under(node, element);
  let held = null;
  for (const item of items) {
    if (item.source.kind !== "widget") continue;
    const { source, node: stands } = obligationPlace(item, items);
    const at = holds(source) ? source : holds(stands) ? stands : null;
    if (at && (!held || under(at, held.at))) held = { item, at };
  }
  return held?.item ?? null;
}

export const placeOf = (node) => placeFrom(node, new Set(), true);
// Where the user has arrived on the page: where they stand, unless a side beside the
// page shows the node, which arrives nowhere.
export const arrivalOf = (node) => placeFrom(node, new Set(), false);

function placeFrom(node, visited, countBeside) {
  const at = node?.nodeType === 1 ? node : node?.parentElement;
  if (!at || at === document.body || visited.has(at)) return null;
  visited.add(at);
  // An obligation is the user's current action wherever it is rendered. A source-linked
  // presentation may otherwise stand in authored flow as well as fixed chrome.
  if (obligationHolding(readObligations().all, at)) return at;
  for (const [side, beside] of sides) {
    const place = side(at);
    if (place && beside && !countBeside) return null;
    if (place)
      return inChrome(place) && !obligationHolding(readObligations().all, place)
        ? placeFrom(place, visited, countBeside)
        : place;
  }
  return inChrome(at) ? null : at;
}

// A standing origin can step off its current stop. An `at` origin arrives at
// its place; an `enter` origin starts inside its region, from either direction.
// A selected tab enters its panel instead of standing on an obligation it may hold.
export function standingOrigin() {
  for (const node of standingNodes()) {
    const place = placeOf(node);
    if (place) {
      const tab = place.closest('[role="tab"][aria-selected="true"]');
      const panel = tab?.ariaControlsElements?.[0];
      return panel ? { place: panel, kind: "enter" } : { place, kind: "standing" };
    }
  }
  return null;
}

// A walk can start at what the viewport shows even when the user stands on nothing.
export const walkOrigin = () =>
  standingOrigin() ?? { place: pageReadingBlock(), kind: "standing" };

// The item a walk over `list` steps to in direction `dir` from `here`, a place on the
// page, and whether it came round an end to reach it. `list` is in page order with its
// unplaced items last, and `placeOfItem` reads an item's place, or null. The step takes
// the nearest item on its side of `here`, else comes round to the far end. An item whose
// place holds `here`, such as a thread on the paragraph the caret is in, is the nearest
// either way: the user is at it without standing on it, so the press arrives there. An
// item with no place stands after every placed one, so it is ahead of any place. A
// caller whose user stands on an item steps off it with `cycledRow` instead; with no
// `here` the walk enters at the end it faces. An `enter` origin reaches its
// contained stops first, from the end the direction faces, before leaving it.
export function stepFrom(list, { place: here, kind }, dir, placeOfItem) {
  if (!here) return cycledRow(list, null, dir);
  if (kind === "enter") {
    const inside = list.filter((item) => {
      const place = placeOfItem(item);
      return place && renderedUnder(place, here);
    });
    if (inside.length) return cycledRow(inside, null, dir);
  }
  const reach = list.filter((item) => {
    const place = placeOfItem(item);
    if (!place) return dir > 0;
    return renderedUnder(here, place) || Math.sign(renderedOrder(here, place)) === -dir;
  });
  const row = dir > 0 ? reach[0] : reach.at(-1);
  return row
    ? { row, wrapped: false }
    : { row: dir > 0 ? list[0] : list.at(-1), wrapped: true };
}

// The obligation the user stands in, answered or not: where letting go lands, and the extent
// of what `c` counts as the element they stand at.
export function heldObligation(node = focused()) {
  const item = obligationHolding(readObligations().all, placeOf(node));
  return obligationPlace(item).node;
}
