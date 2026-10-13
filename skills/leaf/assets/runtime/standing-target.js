/* Where the user stands: the page node a focused node stands at, one reading every
   feature takes (glossary, Standing target).

   An ordinary node on the page stands at itself. So does a node inside any ask source in the inventory,
   answered or not, wherever it is drawn: an ask frozen into a reply is where a user
   working it is, never the page ask its thread is about. A presentation can stand at the
   source target it shows in authored flow or chrome, as its owner declares (`declareSide`): the margin for its
   cluster controls, the thread card, and a thread in the Threads panel; the Questions panel
   for its rows; the details shelf for the elements that name its notes. A side's answer
   drawn in the chrome itself, such as a margin control on a widget frozen into a reply,
   stands only where an ask holds it. Chrome no side
   claims — the banner, a drawer's own controls, the panel's list — stands nowhere, and a
   press made from it means the page whole.

   Each feature takes what it needs from that place by its own rule: the ask view the
   ask source or unique context holding it, `c` and `e` its semantic target, the walks its place
   in the page's order. Every side answers alike: an open ask stood at from its card still wears its
   ring and takes its digits, `c` at an element whose own thread is shown continues it,
   and `q` and `t` step from the target.

   The chrome stands over the page rather than in it and is appended after it,
   so a chrome node measured as a place would put the user behind every ask and thread
   there is; no reader measures from one that does not stand in an ask.

   Page walks share `walkOrigin`: focus, then the selection's ends, then the first
   visible reading block. Every press reads the browser afresh; no walk remembers a
   destination to use as the user's current place. They step from it by one rule,
   `stepFrom`, in the page's rendered order (`renderedOrder`, shadow-tree.js), so a place
   inside a widget's shadow tree is ordered among the places beside it there rather than
   at its host. */
import { cycledRow } from "./keyboard/bindings.js";
import { focused, standingNodes } from "./focus.js";
import { inChrome } from "./passages.js";
import { readAsks } from "./asks/model.js";
import { askPlace } from "./asks/place.js";
import { renderedOrder, renderedUnder, under } from "./shadow.js";
import { pageReadingBlock } from "./reading-place.js";

const sides = new Set();

// A presentation owner's reading of the source target one of its nodes shows, or null.
export function declareSide(bridge) {
  sides.add(bridge);
  return () => sides.delete(bridge);
}

// Source containment identifies the ask before its context does. A context
// shared by several sources cannot identify one of them on its own.
export function askHolding(asks, node) {
  if (!node) return null;
  const places = asks
    .filter((ask) => ask.source.kind === "widget")
    .map((ask) => ({ ask, ...askPlace(ask, asks) }));
  const holds = (element) => element && (element === node || under(node, element));
  const source = places.findLast((place) => holds(place.source));
  if (source) return source.ask;
  const contexts = places.filter((place) => holds(place.node));
  return contexts.length === 1 ? contexts[0].ask : null;
}

// The source target a presentation node shows, by its owner's declaration, or null
// for a node no side claims. A side is asked of the node the user stands on, inside any
// shadow tree it is in, so each climbs across shadow roots to its own surface.
export function sideOf(node) {
  for (const side of sides) {
    const place = side(node);
    if (place) return place;
  }
  return null;
}

export function placeOf(node) {
  const at = node?.nodeType === 1 ? node : node?.parentElement;
  if (!at || at === document.body) return null;
  // An ask is the user's current action wherever it is rendered. A source-linked
  // presentation may otherwise stand in authored flow as well as fixed chrome.
  if (askHolding(readAsks().all, at)) return at;
  for (const side of sides) {
    const place = side(at);
    if (place)
      return inChrome(place) && !askHolding(readAsks().all, place) ? null : place;
  }
  return inChrome(at) ? null : at;
}

// Where the user stands now: the first place on the page among where they stand
// (`standingNodes`, focus.js), focus before a selection's ends.
function standingPlace() {
  for (const node of standingNodes()) {
    const place = placeOf(node);
    if (place) return place;
  }
  return null;
}

// A page walk still has an origin when focus and selection name no page place.
export const walkOrigin = () => standingPlace() ?? pageReadingBlock();

// The item a walk over `list` steps to in direction `dir` from `here`, a place on the
// page, and whether it came round an end to reach it. `list` is in page order with its
// unplaced items last, and `placeOfItem` reads an item's place, or null. The step takes
// the nearest item on its side of `here`, else comes round to the far end. An item whose
// place holds `here`, such as a thread on the paragraph the caret is in, is the nearest
// either way: the user is at it without standing on it, so the press arrives there. An
// item with no place stands after every placed one, so it is ahead of any place. A
// caller whose user stands on an item steps off it with `cycledRow` instead; with no
// `here` the walk enters at the end it faces.
export function stepFrom(list, here, dir, placeOfItem) {
  if (!here) return cycledRow(list, null, dir);
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

// The ask the user stands in, answered or not: where letting go lands, and the extent
// of what `c` counts as the element they stand at.
export function heldAsk(node = focused()) {
  const ask = askHolding(readAsks().all, placeOf(node));
  return askPlace(ask).node;
}
