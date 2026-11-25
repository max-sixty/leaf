/* The members a widget shows one at a time (`views`), and what Leaf keeps of the one
 * it shows: which it is, its name in the address, and the user's place in it.
 *
 * A tag declares which of its direct children are its members. Delivery carries that
 * selector to the prepaint, which shows the opening member before the first paint and
 * hears each member the browser reveals (prepaint.js, `lfViews`). A holder a module
 * creates, or one in a message, is marked from the registry's same declaration as its
 * module first asks about it (`markViews`). The prepaint keeps the member's `hidden`
 * and remembers the member last shown for this tab, so a reload opens on it.
 *
 * A module shows a member with `keepView`, and Leaf shows one itself as the browser's
 * find, a fragment, travel, or Back and Forward reveals it (`beforematch`). Each switch
 * therefore passes through here before the member it leaves is hidden, which is the
 * last moment the page can say where the user was in it. From that reading Leaf keeps
 * two things a module would otherwise keep itself.
 *
 * The address. A holder that says its views are the page's (`data-lf-page-views`, as
 * the first tab set in `main` says) has its open member named in the address, by the
 * member's id. A switch the element makes itself, a `keepView` of a member other than
 * the one showing, is the user's step, as a followed link is. It adds an entry, which
 * history writes with where the user was in the view they leave (history.js,
 * `pushEntry`); a module has no way to switch such a view without one. A reveal adds
 * none: the route that revealed the member owns its own entry, so the entry the user
 * is on is renamed, unless its fragment already names a place inside the member. An arrival at an address with no fragment renames its entry
 * too. Back or Forward to an entry whose fragment names a place in another of these
 * views reveals that view (`entryView`), and the entry's record returns the user to
 * where they were in it.
 *
 * The place. Where the members stand in the page's flow, since the holder draws no box
 * of its own (`flow`) or is the page's parts, each member with an id is a view with a
 * place of its own. As the element switches from one that the user has read past its
 * start, Leaf keeps that place as a landmark in the page's words (readings/reading-place.js),
 * per tab, as the open member is kept, so it survives a resize, a revision and a
 * reload. The member opened returns to its place. One without a place leaves the page
 * where it stands, unless the page is scrolled past the member's start, and then it
 * opens at its start: flush under the headers stuck over it (dom/geometry.js,
 * `visibleBand`), so a strip stuck over the views stays stuck. A reveal places nothing,
 * since whoever revealed the member lands the user in it, as the entry's record does
 * on Back and Forward. A member of any other holder is a box in the page, and a switch
 * leaves the page where it stands.
 *
 * Rejected: learning of a switch by watching `hidden` on the members, so that a module
 * states the open member only by showing it. A watcher hears the switch once the member
 * left is hidden. Neither the user's place in that member nor the record of the entry
 * they leave can be read then, so the address and the place would stay each module's to
 * keep, behind history and reading-place functions of the package API. */
import { setScroll } from "../dom/arrivals.js";
import { elementNamed } from "../readings/anchor-resolution.js";
import { visibleBand } from "../dom/geometry.js";
import { pushEntry, replaceEntry } from "./history.js";
import { marks } from "../state/kernel-facts.js";
import { keeps } from "../lib/keeps.js";
import { under } from "../lib/shadow-tree.js";
import { PAGE_PAINT_ATTRIBUTE } from "../base/page-paint.js";
import { capturePlace, restorePlace } from "../readings/reading-place.js";
import { preserveReadingRegions } from "../readings/reading-regions.js";
import { registry } from "../state/registry.js";
import { pageScroller } from "../dom/scrolling.js";
import { tabStore } from "../state/tab-store.js";
import { reveal } from "../dom/widget-elements.js";

const PAGE_VIEWS = "data-lf-page-views";
const PLACE_KEY = "lf-view-place:";

// The member each holder shows, or null where it shows none: what the next switch
// leaves. A holder absent from it has shown nothing through here, so its first member
// is an arrival rather than a switch.
/** @type {WeakMap<Element, Element | null>} */
const shown = new WeakMap();

// Reading members or the opening choice changes no DOM.
/** @param {Element} holder */
const memberSelector = (holder) => registry[holder.localName]?.views?.members;
/** @param {Element} holder */
export function viewMembers(holder) {
  return window.lfViews.members(holder, memberSelector(holder));
}
/** @param {Element} holder @param {Element | null} [fallback] */
export function openingView(holder, fallback = undefined) {
  return window.lfViews.opening(holder, fallback, memberSelector(holder));
}
/** @param {Element} holder */
export function markViews(holder) {
  const declaration = registry[holder.localName]?.views;
  if (!declaration) return;
  keeps(holder, marks.views.attribute, declaration.parts ? "parts" : "");
  keeps(holder, PAGE_PAINT_ATTRIBUTE.viewMembers, declaration.members);
}
// Show `member` and remember it, or show none where it is null, without forgetting the
// last member. `leaving` keeps one outgoing member visible too, for its exit.
/** @param {Element} holder @param {Element | null} member @param {Element | null} [leaving] */
export function keepView(holder, member, leaving = null) {
  markViews(holder);
  show(holder, member, leaving, false);
}
// The prepaint hands each member the browser or Leaf reveals to this module as the
// member's `beforematch` reaches the document, before the member's own listeners hear
// it. A module's listener that then shows the member with `keepView`, as it does for a
// press, finds it showing and switches nothing.
window.lfViews.reveal = (holder, member) => show(holder, member, null, true);

/** @param {Element} holder @param {Element | null} member @param {Element | null} leaving
 * @param {boolean} revealed */
function show(holder, member, leaving, revealed) {
  const previous = shown.get(holder);
  const switched = member !== null && previous !== undefined && member !== previous;
  if (member && holder.hasAttribute(PAGE_VIEWS))
    name(member, switched && !revealed, revealed);
  // The member left, where it and the one shown are views with places, each kept by
  // its id.
  const left =
    switched && previous?.id && member.id && inPageFlow(holder) ? previous : null;
  const swap = () => {
    const from = pageScroller.scrollTop;
    if (left) leave(holder, left);
    window.lfViews.keep(holder, member, leaving);
    shown.set(holder, member);
    if (left && member && !revealed) open(holder, member, from);
  };
  // The switch hides and shows the reading regions the members hold.
  if (left) void preserveReadingRegions(holder, swap);
  else swap();
}

// Name `member` in the address (the header): a new entry for the user's step to it,
// and otherwise a rename of the entry they are on, where that entry names no place, or
// a reveal took them out of the view its fragment names.
/** @param {Element} member @param {boolean} stepped @param {boolean} revealed */
function name(member, stepped, revealed) {
  if (!member.id) return;
  const url = new URL(location.href);
  url.hash = member.id;
  if (stepped) {
    if (location.hash !== `#${member.id}`) pushEntry(url);
  } else if (!location.hash || (revealed && !holds(member, location.hash)))
    replaceEntry(url);
}

// Whether `member` holds the place a fragment names, which reaches inside a widget's
// shadow tree as Leaf's own arrival does.
/** @param {Element} member @param {string} fragment */
const holds = (member, fragment) => {
  const target = elementNamed(fragment);
  return Boolean(target) && under(target, member);
};

// Whether the holder's members stand in the page's flow, each a view with a place of
// its own (the header).
/** @param {Element} holder */
const inPageFlow = (holder) =>
  holder.hasAttribute(marks.flow.attribute) ||
  (holder.getAttribute(marks.views.attribute) === "parts" &&
    holder.hasAttribute(PAGE_VIEWS));

/** @param {Element} holder @param {Element} member */
const placeKey = (holder, member) => `${PLACE_KEY}${holder.id}:${member.id}`;

// How far the page is scrolled past `member`'s start (the header), negative short of
// it: how far the member's top stands above the band the headers over it leave.
/** @param {Element} member */
const pastStart = (member) =>
  (visibleBand(pageScroller, member)?.top ?? 0) - member.getBoundingClientRect().top;

// A member read past its start keeps that place; one left at its start keeps none.
/** @param {Element} holder @param {Element} member */
function leave(holder, member) {
  tabStore.set(
    placeKey(holder, member),
    pastStart(member) > 0.5 ? JSON.stringify(capturePlace()) : null,
  );
}

// `from` is where the page stood before the switch, which hiding the member left can
// clamp.
/** @param {Element} holder @param {Element} member @param {number} from */
function open(holder, member, from) {
  let place = null;
  try {
    const stored = tabStore.get(placeKey(holder, member));
    if (stored !== null) place = JSON.parse(stored);
  } catch {
    // An unreadable place is no place.
  }
  const start = pageScroller.scrollTop - pastStart(member);
  setScroll(pageScroller, {
    top: place ? start : Math.min(from, start),
    behavior: "instant",
  });
  if (place) restorePlace(place);
}

// Back or Forward to an entry whose fragment names a place inside another of the
// page's views: the handler that reveals that view, as travel reveals one, and leaves
// the page to the entry's record (history.js, `mountHistory`). Nothing where the entry
// names no such place, or the view already shows.
/** @param {URL} url @param {() => boolean} mayReveal */
export function entryView(url, mayReveal) {
  const holder = document.querySelector(`[${PAGE_VIEWS}]`);
  const target = holder && elementNamed(url.hash);
  const member =
    holder && target && viewMembers(holder).find((each) => under(target, each));
  if (!holder || !member || member === shown.get(holder)) return null;
  return async () => {
    await reveal(member, mayReveal).ready;
    return false;
  };
}
