/* The current target: the page node represented by the current browser location.
   Every feature reads this interpretation (glossary, Current target).

   An ordinary page node represents itself. So does a node inside any obligation source,
   answered or not: an obligation frozen into a reply is the user's current target when
   they work on it, rather than the page obligation the thread discusses.

   A presentation can represent its source target in authored flow or chrome, as its
   owner declares with `declareSide`: a margin cluster or thread card, a details shelf's
   note, a floating panel's thread target, or an On card's obligation. A control inside
   such a presentation resolves through that declaration unless it belongs to an
   obligation of its own. Unclaimed chrome, including the panel's row, menu and lists,
   has no page target; a comment from there addresses the whole page.

   Each feature derives its answer from that target: the obligation view finds the
   obligation source or unique enclosing widget; `c` and `e` use its semantic target;
   walks use its position in page order. An open obligation represented by its card
   still wears its ring and takes its digits. At an element represented by its own
   thread, `c` continues the thread, `r` settles it, and `m` and `t` step from the target.

   Current location does not imply arrival at the target. The floating panel shows a
   thread or obligation beside the page (`declareSide`'s `beside`). Features that follow
   an arrival, such as the margin card and its folded pins, use `arrivalOf`, which
   excludes those presentations. Chrome is appended after the page, so measuring its
   DOM position would incorrectly place the user after every obligation and thread.

   `currentLocationOrigin` reads focus, then the selection's ends, returning null when
   neither identifies a page location. `walkOrigin` falls back to the first visible
   reading block. A selected tab starts a walk inside its controlled panel without
   changing comment targets. Every press reads the browser afresh. `stepFrom` orders
   destinations by rendered position (`renderedOrder`, shadow-tree.js), including
   positions within a widget's shadow tree rather than substituting its host. */
import { cycledRow } from "./keyboard/bindings.js";
import { focused, currentLocationNodes } from "./focus.js";
import { inChrome } from "./passages.js";
import { readObligations } from "./obligations/model.js";
import { obligationPlace } from "./obligations/place.js";
import { renderedOrder, renderedUnder, under } from "./shadow.js";
import { pageReadingBlock } from "./reading-place.js";

// Each side's reading, and whether it shows its target beside the page.
const sides = new Map();

// A presentation owner's reading of the source target one of its nodes shows, or null.
// A side is asked of the node the user is on, inside any shadow tree it is in, so
// each climbs across shadow roots to its own surface. A side `beside` the page, as the
// floating panel is, shows its target away from it: the user’s current target is that page target
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
// is on that question, not on the proposal whose source holds it.
export function obligationHolding(items, node) {
  if (!node) return null;
  const holds = (element) => element && under(node, element);
  let held = null;
  for (const item of items) {
    if (item.source.kind !== "widget") continue;
    const { source, node: target } = obligationPlace(item, items);
    const at = holds(source) ? source : holds(target) ? target : null;
    if (at && (!held || under(at, held.at))) held = { item, at };
  }
  return held?.item ?? null;
}

export const placeOf = (node) => placeFrom(node, new Set(), true);
// Where the user has arrived on the page: where they are, unless a side beside the
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

// A current location origin can step off its current stop. An `at` origin arrives at
// its place; an `enter` origin starts inside its region, from either direction.
// A selected tab enters its panel instead of being on an obligation it may hold.
export function currentLocationOrigin() {
  for (const node of currentLocationNodes()) {
    const place = placeOf(node);
    if (place) {
      const tab = place.closest('[role="tab"][aria-selected="true"]');
      const panel = tab?.ariaControlsElements?.[0];
      return panel
        ? { place: panel, kind: "enter" }
        : { place, kind: "current-location" };
    }
  }
  return null;
}

// A walk can start at what the viewport shows even when the user has no current location.
export const walkOrigin = () =>
  currentLocationOrigin() ?? { place: pageReadingBlock(), kind: "current-location" };

// The item a walk over `list` steps to in direction `dir` from `here`, a place on the
// page, and whether it came round an end to reach it. `list` is in page order with its
// unplaced items last, and `placeOfItem` reads an item's place, or null. The step takes
// the nearest item on its side of `here`, else comes round to the far end. An item whose
// place holds `here`, such as a thread on the paragraph the caret is in, is the nearest
// either way: the user is at it without being on it, so the press arrives there. An
// item with no place stands after every placed one, so it is ahead of any place. A
// caller whose user is on an item steps off it with `cycledRow` instead; with no
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

// The obligation the user is in, answered or not: where letting go lands, and the extent
// of what `c` counts as the element they are at.
export function heldObligation(node = focused()) {
  const item = obligationHolding(readObligations().all, placeOf(node));
  return obligationPlace(item).node;
}
