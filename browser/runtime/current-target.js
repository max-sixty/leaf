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

   `currentLocationOrigin` reads focus, then the selection's ends, then the page place
   the floating panel holds while the user stands in it (`holdPagePlace`), returning
   null when none identifies a page location. A selected tab starts a walk inside its
   controlled panel without changing comment targets.

   Every walk (`t`, `m`, a tally's Next On Me) pages through its stops by one rule, read
   from one origin (`walkOrigin`): the node the user's place was read from, the place
   it stands for, and whether that is a current location. The user is on a stop while
   their current location is in the stop's destination, where the walk's own arrival
   puts them: an obligation's place or a presentation of it, a thread's view. A press
   steps off that stop to its neighbour. Anywhere else the user is at most at a stop,
   and the press arrives at the stop at their place (`stepFrom`), else at the nearest
   one in the press's direction. A thread's target, with the thread's card open beside
   it, is at the thread and not on it. With no current location, a walk starts at what
   the user let go of (focus.js, `onLetGo`) while they still see it, since letting go
   leaves them beside it rather than anywhere else, until they go on from there by
   standing on another page place or by pressing, wheeling or touching the page; failing
   that, at what they read (reading-place.js, `pageReadingBlock`). Only what they saw as
   they let go leaves them beside it: a key pressed after scrolling away lets go of focus
   they no longer see (keyboard/controller.js), and scrolling back to it doesn't put
   them there again. Neither is on a stop. Stepping into Leaf's
   panel from either keeps it, the panel holding no other page place. So a walk, Escape
   and the walk again returns to the stop the user left, and a second press goes on from
   it. Each press reads the origin afresh. `stepFrom` orders destinations by rendered
   position (`renderedOrder`, shadow-tree.js), including positions within a widget's
   shadow tree rather than substituting its host. */
import { cycledRow } from "./keyboard/bindings.js";
import {
  focused,
  currentLocationNodes,
  onCurrentLocation,
  onLetGo,
  onUserInput,
} from "./focus.js";
import { seenAhead } from "./scroll-containers.js";
import { closestAcross, inChrome } from "./passages.js";
import { THREAD } from "./thread/selectors.js";
import { readObligations } from "./obligations/model.js";
import { obligationPlace } from "./obligations/place.js";
import { ON_CARD } from "./obligations/view-elements.js";
import { composedParentNode, renderedOrder, renderedUnder, under } from "./shadow.js";
import { isElement } from "./shadow-tree.js";
import { eventSource } from "./pointer.js";
import { pageReadingBlock } from "./reading-place.js";

// Each side's reading, and whether it shows its target beside the page.
/** @type {Map<(node: Element) => Element | null, boolean>} */
const sides = new Map();

// A presentation owner's reading of the source target one of its nodes shows, or null.
// A side is asked of the node the user is on, inside any shadow tree it is in, so
// each climbs across shadow roots to its own surface. A side `beside` the page, as the
// floating panel is, shows its target away from it: the user’s current target is that page target
// but has not arrived at it (`arrivalOf`).
/** @param {(node: Element) => Element | null} bridge */
export function declareSide(bridge, { beside = false } = {}) {
  sides.set(bridge, beside);
  return () => sides.delete(bridge);
}

// The innermost obligation whose source, or whose own place, is or holds `node`: a
// widget's enclosing widget, or the element a to-do is on. An enclosing widget shared
// by several sources cannot identify one of them on its own, so only a source stands for
// such an obligation (`obligationPlace`). Obligations nest, as a question
// inside a proposal's new text does, so the nearest place holding the node names the
// obligation rather than the kind of place: on the inner question's enclosing widget the user
// is on that question, not on the proposal whose source holds it. Of two standing at one
// place, the first the inventory lists names it. `items` may be a selection, such as
// those waiting on the user, placed as the whole `inventory` places them. Only the
// obligations whose place names one of the node's ancestors are placed
// (`namedPlaces`), so a keystroke, which asks this many times, costs the node's depth
// rather than the inventory. The names are read once per list, so that holds for a
// list the state keeps, such as the inventory, and not for one built for the call.
/** @template {import("./framework/application.js").ObligationRecord} T
 * @param {readonly T[]} items @param {Node | null} node
 * @param {readonly import("./framework/application.js").ObligationRecord[]} inventory */
export function obligationHolding(items, node, inventory = items) {
  if (!node) return null;
  const names = namedPlaces(items);
  /** @type {Map<T, number>} */
  const near = new Map();
  for (let at = /** @type {Node | null} */ (node); at; at = composedParentNode(at)) {
    if (!isElement(at)) continue;
    const datum = at.getAttribute("data-lf-datum");
    const owner = at.getAttribute("data-lf-projection");
    for (const name of [at.id && `#${at.id}`, datum !== null && `@${owner} ${datum}`])
      for (const [order, item] of (name && names.get(name)) || [])
        near.set(item, order);
  }
  /** @param {Element | null} element */
  const holds = (element) => element && under(node, element);
  /** @type {{item: T, at: Element} | null} */
  let held = null;
  for (const [item] of [...near].sort((a, b) => a[1] - b[1])) {
    const { source, node: target } = obligationPlace(item, inventory);
    const at = holds(source) ? source : holds(target) ? target : null;
    if (at && (!held || (at !== held.at && under(at, held.at)))) held = { item, at };
  }
  return held?.item ?? null;
}

// The obligations of a list that could stand at an element, by what names their places
// (`obligationPlace`): the id of a widget's source and of its context; for a record unit,
// which stands only at its datum, the widget's id with the datum's key, as the datum
// carries them (`data-lf-projection`, `data-lf-datum`). Each name keeps the list's
// order. Read from the records alone, once per list, so it
// holds however the document changes; a name finds candidates, and placing each says
// whether it stands there.
/** @type {WeakMap<readonly import("./framework/application.js").ObligationRecord[], Map<string, [number, any][]>>} */
const placeNames = new WeakMap();
/** @template {import("./framework/application.js").ObligationRecord} T
 * @param {readonly T[]} items @returns {Map<string, [number, T][]>} */
function namedPlaces(items) {
  const held = placeNames.get(items);
  if (held) return held;
  /** @type {Map<string, [number, T][]>} */
  const names = new Map();
  /** @param {string} name @param {number} order @param {T} item */
  const add = (name, order, item) => {
    const listed = names.get(name);
    if (!listed) names.set(name, [[order, item]]);
    else if (listed.at(-1)?.[1] !== item) listed.push([order, item]);
  };
  items.forEach((item, order) => {
    const { source } = item;
    if (source.kind === "widget" && source.unit) {
      add(`@${source.id} ${source.unit}`, order, item);
    } else if (source.kind === "widget") {
      add(`#${source.id}`, order, item);
      if (item.prompt.target) add(`#${item.prompt.target}`, order, item);
    }
  });
  placeNames.set(items, names);
  return names;
}

/** @param {Node | null | undefined} node */
export const placeOf = (node) => placeFrom(node, new Set(), true);
// Where the user has arrived on the page: where they are, unless a side beside the
// page shows the node, which arrives nowhere.
/** @param {Node | null | undefined} node */
export const arrivalOf = (node) => placeFrom(node, new Set(), false);
// The obligation, answered or not, holding the place `node` stands for, read from the
// inventory the state publishes, which keeps its identity between readings, so the
// lookup costs the node's depth (`obligationHolding`). DOM containment says where the
// node is; it never decides whether the obligation belongs to that inventory.
/** @param {Node | null | undefined} node */
export const obligationAt = (node) =>
  obligationHolding(readObligations().all, placeOf(node));

/** @param {Node | null | undefined} node @param {Set<Element>} visited
 * @param {boolean} countBeside @returns {Element | null} */
function placeFrom(node, visited, countBeside) {
  const at = node instanceof Element ? node : node?.parentElement;
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

// The panel's views of one thread or one obligation, where a user stands even when the
// thread or obligation has no place on the page.
const PLACELESS = `${THREAD}, ${ON_CARD}`;

// The page place a surface beside the page holds while the user stands in it, as the
// floating panel holds where they stepped in from (`readPlace`, history.js). It is still
// their place on the page, so `z` aligns it and a walk pressed there starts on it.
/** @type {() => import("./history.js").WorkingPlace | null} */
let heldPlace = () => null;
/** @param {typeof heldPlace} read */
export function holdPagePlace(read) {
  heldPlace = read;
}
export const heldPagePlace = () => heldPlace()?.focus?.deref() ?? null;

// A current location origin can step off its current stop. An `at` origin arrives at
// its place; an `enter` origin starts inside its region, from either direction.
// A selected tab enters its panel instead of being on an obligation it may hold. Each
// names the element it was read from, `node`, which is in a thread's view where the
// user is in that thread; `place` is null for a thread with no place on the page.
/** @typedef {{node: Element | null, place: Element | null, kind: "at" | "enter" | "current-location"}} WalkOrigin */
/** @returns {WalkOrigin | null} */
export function currentLocationOrigin() {
  for (const [node, place] of locations()) {
    // A thread or an obligation with no page place, such as a general thread open in the
    // panel or a to-do on the whole page on its On card, is still where a user in it is.
    if (place?.isConnected || closestAcross(node, PLACELESS)) {
      const tab = place?.closest('[role="tab"][aria-selected="true"]');
      const panel = tab?.ariaControlsElements?.[0];
      return panel
        ? { node, place: panel, kind: "enter" }
        : { node, place, kind: "current-location" };
    }
  }
  return null;
}

// Each node the user's place can be read from, nearest first, with the place it stands
// for. The panel's hold read its place as the user stepped in, since what showed it then,
// such as a margin card, may be put away by the step.
/** @returns {Generator<[Element, Element | null]>} */
function* locations() {
  for (const at of currentLocationNodes()) {
    const node = at instanceof Element ? at : at.parentElement;
    if (!node) continue;
    yield [node, placeOf(node)];
  }
  const held = heldPlace();
  const node = held?.focus?.deref();
  if (held && node) yield [node, held.place?.deref() ?? null];
}

// What the user let go of, until they go on from it. Chrome holding no page place,
// such as On Me's list or the comment field, is not somewhere else on the page.
/** @type {WeakRef<Element> | null} */
let letGone = null;
onLetGo((node) => {
  const place = placeOf(node);
  letGone = place && seenAhead(place) ? new WeakRef(node) : null;
});
onCurrentLocation((node) => {
  if (node && placeOf(node)) letGone = null;
});
// A key is a command at the user's place rather than a move away from it.
const LEAVING = new Set(["pointerdown", "wheel", "touchstart"]);
onUserInput((event) => {
  if (LEAVING.has(event.type) && !inChrome(eventSource(event))) letGone = null;
});

// Where a walk starts: the user's current location, else what they let go of while
// they still see it, else what the viewport shows, each read where the glides under way
// leave it (scroll-containers.js, `seenAhead`; reading-place.js, `readingBlock`). Only a
// current location can be on a stop; the others are `at` one.
/** @returns {WalkOrigin} */
export function walkOrigin() {
  const here = currentLocationOrigin();
  if (here) return here;
  const node = letGone?.deref();
  const left = node?.isConnected ? placeOf(node) : null;
  if (node && left && seenAhead(left)) return { node, place: left, kind: "at" };
  const block = pageReadingBlock();
  return { node: block, place: block, kind: "at" };
}

// The item a walk over `list` steps to in direction `dir` from `here`, a place on the
// page. `list` is in page order with its
// unplaced items last, and `placeOfItem` reads an item's place, or null. The step takes
// the nearest item on its side of `here`, else comes round to the far end. An item whose
// place holds `here`, such as a thread on the paragraph the caret is in, is the nearest
// either way: the user is at it without being on it, so the press arrives there. An
// item with no place stands after every placed one, so it is ahead of any place. A
// caller whose user is on an item steps off it with `cycledRow` instead; with no
// `here` the walk enters at the end it faces. An `enter` origin reaches its
// contained stops first, from the end the direction faces, before leaving it.
/** @template T @param {readonly T[]} list @param {WalkOrigin} origin
 * @param {import("./keyboard/bindings.js").Step} dir @param {(item: T) => Element | null} placeOfItem */
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
  return (dir > 0 ? reach[0] : reach.at(-1)) ?? (dir > 0 ? list[0] : list.at(-1));
}

// The obligation the user is in, answered or not: where letting go lands, and the extent
// of what `c` counts as the element they are at.
export function heldObligation(node = focused()) {
  return obligationPlace(obligationAt(node)).node;
}
