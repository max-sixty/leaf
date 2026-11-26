/* The current target: the page node represented by the current browser location.
   Every feature reads this interpretation (glossary, Current target).

   An ordinary page node represents itself. So does a node inside any obligation source,
   answered or not: an obligation in a reply is the user's current target when
   they work on it, rather than the page obligation the thread discusses.

   A presentation can represent its source target in authored flow or chrome, as its
   owner declares with `declareSide`: a margin cluster or thread card, a details shelf's
   note, a floating panel's thread target, or an On card's obligation. A control inside
   such a presentation resolves through that declaration unless it belongs to an
   obligation of its own. Unclaimed chrome, including the panel's row, menu and lists,
   has no page target; a comment from there addresses the whole page.

   Each feature derives its answer from that target: the obligation view finds the
   obligation source or the group it stands at alone; `c` and `e` use its semantic
   target; walks use its position in page order. An open obligation represented by its
   card still wears its ring and takes its digits. At an element represented by its own
   thread, `c` continues the thread, `r` settles it, and `m` and `t` step from the target.
   A thread's view stands at the thread's target but is in the question the thread asks
   now, where it asks one (`questionAsked`): that question wears the ring, takes the
   digits and is the walk's stop the user is on, from anywhere in the view.

   Current location does not imply arrival at the target. The floating panel shows a
   thread or obligation beside the page (`declareSide`'s `beside`). Features that follow
   an arrival, such as the margin card and its folded pins, use `arrivalOf`, which
   excludes those presentations. Chrome is appended after the page, so measuring its
   DOM position would incorrectly place the user after every obligation and thread.

   `currentLocationOrigin` reads focus, then the caret (dom/native-selection.js,
   `userCaret`), then the page place the floating panel holds while the user stands in it
   (`holdPagePlace`), returning null when none identifies a page location. A selected
   tab starts a walk inside its controlled panel without changing comment targets.

   Every walk (`t`, `m`, a tally's Next On Me) pages through its stops by one rule, read
   from one origin (`walkOrigin`): the node the user's place was read from, the place
   it stands for, and whether that is a current location. The user is on a stop while
   their current location is in the stop's destination, where the walk's own arrival
   puts them: an obligation's place or a presentation of it, a thread's view. A press
   steps off that stop to its neighbour. Anywhere else the user is at most at a stop,
   and the press arrives at the stop at their place (`stepFrom`), else at the nearest
   one in the press's direction. A thread's target, with the thread's card open beside
   it, is at the thread and not on it. With no current location, a walk starts at what
   the user let go of (dom/focus.js, `onLetGo`) while they still see it, since letting go
   leaves them beside it rather than anywhere else, until they go on from there by
   standing on another page place or by pressing, wheeling or touching the page; failing
   that, at what they see, from the block they read (readings/reading-place.js,
   `pageReadingBlock`), or a stop on screen ahead of it (`stepFrom`). Only what they saw as
   they let go leaves them beside it: a key pressed after scrolling away lets go of focus
   they no longer see (panel/page-keys/controller.js), and scrolling back to it doesn't put
   them there again. Neither is on a stop. Stepping into Leaf's
   panel from either keeps it, the panel holding no other page place. So a walk, Escape
   and the walk again returns to the stop the user left, and a second press goes on from
   it. Each press reads the origin afresh. `stepFrom` orders destinations by rendered
   position (`renderedOrder`, lib/shadow-tree.js), including positions within a widget's
   shadow tree rather than substituting its host. */
import { cycledRow } from "../dom/keyboard/bindings.js";
import { userCaret } from "../dom/native-selection.js";
import { focused, onCurrentLocation, onLetGo, onUserInput } from "../dom/focus.js";
import { seenAhead } from "../readings/scroll-containers.js";
import { drawnThreadId, THREAD, wholeThread } from "./thread/selectors.js";
import { isReaction } from "../state/thread/model.js";
import { threadNamed } from "./thread/state.js";
import { keptEach } from "../state/kept.js";
import {
  obligationPlace,
  obligationsByRegion,
  readObligations,
} from "./obligations/place.js";
import { ON_CARD } from "./obligations/view-elements.js";
import {
  byRenderedOrder,
  isElement,
  composedParentNode,
  renderedOrder,
  renderedUnder,
  under,
  closestAcross,
} from "../lib/shadow-tree.js";
import { eventSource } from "../base/pointer.js";
import { pageReadingBlock, seenWhereRead } from "../readings/reading-place.js";
import { inChrome } from "../base/ui-marks.js";

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

// The innermost obligation whose source, or whose own place, is or holds `node`: the
// group the author declares round a widget, or the element a to-do is on. A group
// holding several sources cannot identify one of them on its own, so only a source
// stands for such an obligation (`obligationPlace`). Obligations nest, as a question
// inside a proposal's new text does, so the nearest place holding the node names the
// obligation rather than the kind of place: in the inner question's group the user is
// on that question, not on the proposal whose source holds it. Of two standing at one
// place, the first the inventory lists names it. `items` may be a selection, such as
// those waiting on the user, placed as the whole `inventory` places them. Only the
// obligations whose place names one of the node's ancestors are placed
// (`namedPlaces`), so a keystroke, which asks this many times, costs the node's depth
// rather than the inventory. The names are read once per list, so that holds for a
// list the state keeps, such as the inventory, and not for one built for the call.
/** @template {import("../state/semantic-application.js").ObligationRecord} T
 * @param {readonly T[]} items @param {Node | null} node
 * @param {readonly import("../state/semantic-application.js").ObligationRecord[]} inventory */
export function obligationHolding(items, node, inventory = items) {
  if (!node) return null;
  const names = namedPlaces(items);
  /** @type {Map<T, number>} */
  const near = new Map();
  for (let at = /** @type {Node | null} */ (node); at; at = composedParentNode(at)) {
    if (!isElement(at) || !at.id) continue;
    for (const [order, item] of names.get(at.id) || []) near.set(item, order);
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

// The obligations of a list that could stand at an element, by the ids that name their
// places (`obligationPlace`): the id of a widget's source and of its context. Each id
// keeps the list's order. Read from the records alone, once per list (state/kept.js), so it
// holds however the document changes; an id finds candidates, and placing each says
// whether it stands there.
const placeNames = keptEach(
  /** @param {readonly import("../state/semantic-application.js").ObligationRecord[]} items */
  (items) => {
    /** @type {Map<string, [number, import("../state/semantic-application.js").ObligationRecord][]>} */
    const names = new Map();
    /** @param {string} name @param {number} order
     * @param {import("../state/semantic-application.js").ObligationRecord} item */
    const add = (name, order, item) => {
      const listed = names.get(name);
      if (!listed) names.set(name, [[order, item]]);
      else if (listed.at(-1)?.[1] !== item) listed.push([order, item]);
    };
    items.forEach((item, order) => {
      const { source } = item;
      if (source.kind === "widget") {
        add(source.id, order, item);
        if (item.prompt.target) add(item.prompt.target, order, item);
      }
    });
    return names;
  },
);
/** @template {import("../state/semantic-application.js").ObligationRecord} T
 * @param {readonly T[]} items @returns {Map<string, [number, T][]>} */
const namedPlaces = (items) =>
  /** @type {Map<string, [number, T][]>} */ (placeNames(items));

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

// The obligation, answered or not, the user at `node` is in: the question a thread's view
// asks them (`questionAsked`), else the one holding the place the node stands for
// (`obligationAt`). The location ring and the digits read it.
/** @param {Node | null | undefined} node */
export const obligationIn = (node) => questionAsked(node) ?? obligationAt(node);

// The question a thread asks the user at `node`, where `node` is in a view of the thread
// outside any obligation drawn there: the first still open of those drawn in the agent's
// latest message in it. A thread and the question it asks are one target, as an
// obligation and the thread about it are, and the question comes before the obligation
// the thread is about: it is what the thread asks of the user now, drawn where they are
// reading, while the obligation stands on the page, where they answer it. A message
// asking several moves the user on to the next one still open as they answer, as a form
// does. Once none is open the thread asks nothing, and the view stands for the
// obligation it is about again, whose ring shows the user where the next digit goes, so
// a digit there never revises an answer given in the thread; Tab and a click reach the
// question for that. The thread asks what its newest agent message asks: a question an
// older message left open stays in On Me, where `m` reaches it.
/** @param {Node | null | undefined} node */
export function questionAsked(node) {
  const view = closestAcross(node ?? null, THREAD);
  if (!view) return null;
  const whole = wholeThread(view);
  const all = readObligations().all;
  const held = obligationHolding(all, node ?? null);
  if (held && under(obligationPlace(held, all).source, whole)) return null;
  const thread = threadNamed(drawnThreadId(view) ?? "");
  const latest = thread?.msgs.findLast(
    (message) => message.author === "agent" && !isReaction(message),
  );
  const asked =
    (latest && thread?.obligations.filter((item) => item.message === latest.id)) || [];
  const drawn = byRenderedOrder(
    obligationsByRegion([whole], asked).get(whole) ?? [],
    (item) => obligationPlace(item, all).source,
  );
  return drawn.find((item) => item.state !== "done") ?? null;
}

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
/** @type {() => import("../base/held-place.js").WorkingPlace | null} */
let heldPlace = () => null;
/** @param {typeof heldPlace} read */
export function holdPagePlace(read) {
  heldPlace = read;
}
export const heldPagePlace = () => heldPlace()?.focus?.deref() ?? null;

// A current location origin can step off its current stop. An `at` origin arrives at
// its place; a `view` origin, read from what the window shows, arrives at a stop the
// user sees before it (`stepFrom`); an `enter` origin starts inside its region, from
// either direction.
// A selected tab enters its panel instead of being on an obligation it may hold. Each
// names the element it was read from, `node`, which is in a thread's view where the
// user is in that thread; `place` is null for a thread with no place on the page.
/** @typedef {{node: Element | null, place: Element | null, kind: "at" | "view" | "enter" | "current-location"}} WalkOrigin */
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
// for. The focused node comes first, unless focus rests on the body. The caret comes
// next (`userCaret`), since a selection names where a reader is as surely as focus does.
// Last comes the place the panel's hold read as the user stepped in, since what showed
// it then, such as a margin card, may be put away by the step.
/** @returns {Generator<[Element, Element | null]>} */
function* locations() {
  const at = focused();
  for (const node of [at === document.body ? null : at, userCaret()?.element])
    if (node) yield [node, placeOf(node)];
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
// leave it (readings/scroll-containers.js, `seenAhead`; readings/reading-place.js, `readingBlock`). Only a
// current location can be on a stop; the others are `at` one, and the viewport's is a
// `view`.
/** @returns {WalkOrigin} */
export function walkOrigin() {
  const here = currentLocationOrigin();
  if (here) return here;
  const node = letGone?.deref();
  const left = node?.isConnected ? placeOf(node) : null;
  if (node && left && seenAhead(left)) return { node, place: left, kind: "at" };
  const block = pageReadingBlock();
  return { node: block, place: block, kind: "view" };
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
// contained stops first, from the end the direction faces, before leaving it. `at` is
// an item the caller finds the user at by a reading of its own, as a thread drawn
// with the place they stand at is (thread/destination.js, `threadAtCurrentLocation`),
// and the press arrives there.
//
// A `view` origin is the block the user reads, the first of the window's words in their
// column, but a stop is something the user sees whatever its words: a question of
// options alone, a figure, a widget drawing its own. So the first stop ahead of that
// block that they see where they read it (readings/reading-place.js, `seenWhereRead`) is where they
// are, and either press arrives there rather than passing a question in view for the
// paragraph below it. Only the stops ahead of the block are measured.
/** @template T @param {readonly T[]} list @param {WalkOrigin} origin
 * @param {import("../dom/keyboard/bindings.js").Step} dir @param {(item: T) => Element | null} placeOfItem
 * @param {T | null} [at] */
export function stepFrom(list, { place: here, kind }, dir, placeOfItem, at = null) {
  if (kind === "view" && here) {
    const seen = seenWhereRead(here);
    /** @type {[T, Element] | null} */
    let first = null;
    for (const item of list) {
      const place = placeOfItem(item);
      if (
        place &&
        renderedOrder(place, here) < 0 &&
        (!first || renderedOrder(place, first[1]) < 0) &&
        seen(place)
      )
        first = [item, place];
    }
    if (first) return first[0];
  }
  if (at !== null) return at;
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

// The obligation holding the user's place, answered or not: where letting go lands, and
// the extent of what `c` counts as the element they are at.
export function heldObligation(node = focused()) {
  return obligationPlace(obligationAt(node)).node;
}
