/* Anchor and projected-datum travel.
 *
 * Travel owns effects above readonly resolution and paint. It receives the current
 * semantic threads and the synchronous conversation refresh from the application root;
 * subordinate geometry never imports the presenter. A trip keeps its original user
 * intent through hydration, reveal and presentation. Newer input or another trip
 * cancels its landing without cancelling the data the page is loading. Every trip, to a
 * thread, an Ask or a datum, goes through `trip`, which clears whatever surface hides
 * the destination and then decides whether the user is already there or departs. A
 * departure leaves a history entry, so browser Back returns the user to where they
 * were reading; a journey, trips each leaving from the last one's landing, is one
 * entry.
 */

import {
  currentDatum,
  projectionReferenceDeclared,
  referencedProjection,
  revealVisualPart,
  sectionOf,
  suppliedDatum,
} from "./anchor-resolution.js";
import {
  clippedContents,
  clipsPast,
  landingBand,
  landingInsets,
  placeHolder,
  shownBox,
  shownRect,
} from "./geometry.js";
import { scrollBehavior } from "./motion.js";
import { scrollerFor } from "./reading-regions.js";
import { pushEntry, replaceEntry } from "./history.js";
import { moveScrollerBy, pageScroller } from "./scrolling.js";
import { renderedParent, upFrom } from "./shadow.js";
import { closestAcross } from "./passages.js";
import { reveal } from "./widget-elements.js";
import { retainUserIntent } from "./user-intent.js";

export function createAnchorTravel({
  anchors,
  surfaces,
  currentThreads,
  refreshConversation,
  announce,
}) {
  let travelIntent = 0;
  const retainTravel = () => {
    const intent = ++travelIntent;
    return retainUserIntent({ available: () => intent === travelIntent });
  };

  // A push leaves the current scroll position on the entry it leaves, and Back
  // restores it there (history.js), so the push comes before the trip moves anything.
  // A destination already readable where the user stands is no departure. A trip that
  // names its `landing` while any of the last trip's landing still shows continues that
  // journey, whether it goes to threads or Asks: it replaces the journey's entry, which
  // already holds where the journey began. Once the user has moved off that landing, the
  // next trip pushes again. A journey is not a walk (the glossary's ordered movement
  // among one kind of destination): steps of a thread walk and of an Ask walk, or a
  // press on a margin marker, can all be trips of one journey. The landing is a lookup
  // rather than a node because the conversation pass repaints marks, and the entry
  // carries a token for this document's journey because only this load holds the
  // lookup.
  const journeyPrefix = `${performance.timeOrigin}:`;
  let trips = 0;
  let journey = null;

  function depart({ url = window.location.href, landing = null } = {}) {
    const continuing = landing && stillLanded();
    journey = landing && { token: journeyPrefix + ++trips, landing };
    const state = journey && { lfJourney: journey.token };
    if (continuing) replaceEntry(url, state);
    else pushEntry(url, state);
  }

  // A trip whose destination is already in front of the user moves nothing and records
  // nothing, but it is still a trip of the journey: the journey now stands on its
  // landing, so the next trip continues from there rather than from the one before it.
  function stay(landing) {
    if (stillLanded()) journey.landing = landing;
  }

  function stillLanded() {
    const where =
      journey && history.state?.lfJourney === journey.token && journey.landing();
    return Boolean(where && seenOf(where));
  }

  // Whether the user already has a destination once whatever hid it is cleared. A trip
  // that promises to show it clears the selected surface hiding it (auxiliary-surfaces.js,
  // `clearFor`); one that `keep`s the surface is one the user takes from inside it (the
  // thread panel's walk and its landings). Whatever surface still stands, kept or not
  // hiding the destination, is read past (`seenOf`): what it stands over no movement of
  // the page can show, so it says nothing about whether the page has to move.
  function arrived(where, keep) {
    if (!keep) surfaces.clearFor(where);
    return readableDestination(where);
  }

  // Travel's one entry. It stays when the user already has the destination and departs
  // otherwise, and answers whether the caller moves the page. A destination not yet
  // placed (a datum a widget has yet to hydrate) is somewhere else. `there` is the
  // caller's reading of already being there where it asks more than the destination's
  // own (an Ask's arrival region), built on the reading it is handed. Clearing a surface
  // can take the focus out of it, so the caller's retained `intent` hands the gesture
  // over to where that leaves the user rather than reading the move as a newer one.
  function trip(
    where,
    {
      landing = null,
      url,
      keep = false,
      intent,
      there = (readable) => readable(where),
    } = {},
  ) {
    if (where && !keep) intent.handoff(() => surfaces.clearFor(where));
    if (where && there(readableDestination)) {
      stay(landing);
      return false;
    }
    depart({ url, landing });
    return true;
  }

  function validateProjectionReference(owner, attribute) {
    if (!(owner instanceof Element))
      throw new TypeError("navigateToDatum owner must be an element");
    if (typeof attribute !== "string" || !projectionReferenceDeclared(owner, attribute))
      throw new TypeError(
        `navigateToDatum ${owner.localName} attribute ${String(attribute)} is not declared by x-refers`,
      );
  }

  async function navigateToDatum(
    owner,
    attribute,
    key,
    { success = "", missing = "" } = {},
  ) {
    const mayArrive = retainTravel();
    validateProjectionReference(owner, attribute);
    if (typeof key !== "string" || !key)
      throw new TypeError("navigateToDatum key must be a non-empty string");
    let source = referencedProjection(owner, attribute);
    if (!source) {
      if (missing) announce(missing);
      return false;
    }

    // The widget owns filters and lazy projection. Ask it to make the semantic key
    // reachable before interpreting DOM presence.
    const hydration = source.lfRevealDatum?.(key);
    if (hydration?.then) await hydration;
    if (!mayArrive()) return false;
    source = referencedProjection(owner, attribute);
    if (!source) {
      if (missing) announce(missing);
      return false;
    }
    let destination = currentDatum(source, key) ?? suppliedDatum(source, key);

    const url = new URL(window.location.href);
    url.hash = source.id;
    const moving = trip(destination, { url, intent: mayArrive });
    if (!destination) {
      reveal(source, mayArrive);
      scrollRevealedElement(source, scrollBehavior(), "start");
      if (missing) announce(missing);
      return false;
    }

    await reveal(destination, mayArrive);
    if (!mayArrive()) return false;
    source = referencedProjection(owner, attribute);
    destination = source && (currentDatum(source, key) ?? suppliedDatum(source, key));
    if (!destination) {
      if (missing) announce(missing);
      return false;
    }
    const disclosure = closestAcross(destination, "details");
    disclosure?.querySelector(":scope > summary")?.focus({ preventScroll: true });
    if (moving) scrollRevealedElement(destination);
    if (success) announce(success);
    return true;
  }

  function centreBy(where, block = "center", box = pageScroller) {
    const rect =
      where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
    const view = shownBox(box);
    const clear = landingInsets(box).top;
    const place =
      where instanceof Range
        ? (view.height - rect.height) / 2
        : block === "start"
          ? clear
          : Math.max((view.height - rect.height) / 2, clear);
    return rect.top - view.top - place;
  }

  // Reading-region membership also covers fixed chrome, but its viewport position does
  // not move with that region. Stop at a fixed boundary before applying scroll arithmetic
  // to it; a scroller inside that boundary still owns its ordinary descendants.
  function scrollingBoxFor(element) {
    const box = scrollerFor(element);
    for (let node = element; node; node = upFrom(node)) {
      if (node === box) return box;
      if (getComputedStyle(node).position === "fixed") return null;
    }
    return null;
  }

  function scrollRevealedElement(
    element,
    behavior = scrollBehavior(),
    block = "center",
  ) {
    element.scrollIntoView({
      block: "nearest",
      inline: "nearest",
      behavior: block === "nearest" ? behavior : "instant",
    });
    if (block === "nearest") return;
    const box = scrollingBoxFor(element);
    // The document and nested reading regions share this path. Only the scroller that
    // actually owns the element receives the final centring move.
    if (!box) return;
    moveScrollerBy(box, centreBy(element, block, box), behavior);
  }

  // Synchronous: the move is the caller's gesture, so its intent is the one standing now.
  function scrollToElement(element, behavior = scrollBehavior(), block = "center") {
    reveal(element, retainUserIntent());
    scrollRevealedElement(element, behavior, block);
  }

  // A destination's box and what of it the user can see, which is that box less the
  // window and whatever clips it, or null when none of it shows. The selected surface is
  // read past, as `arrived` says; any other occluder is not.
  function seenOf(where) {
    const holder = placeHolder(where);
    if (!holder) return null;
    const destination =
      where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
    const standing = surfaces.selectedSurface();
    const clips = standing ? clipsPast([standing]) : new Map();
    const seen =
      where instanceof Range
        ? clippedContents(destination, holder, clips)
        : shownRect(where, clips);
    return seen && { holder, destination, seen };
  }

  function readableDestination(where) {
    const shown = seenOf(where);
    if (!shown) return false;
    const { holder, destination, seen } = shown;
    const box = scrollingBoxFor(holder);
    const view = shownBox(box ?? pageScroller);
    const { top: clearAbove, bottom: clearBelow } = box
      ? landingInsets(box)
      : { top: 0, bottom: 0 };
    const close = (a, b) => Math.abs(a - b) <= 0.5;
    return (
      destination.top >= view.top + clearAbove - 0.5 &&
      destination.bottom <= view.bottom - clearBelow + 0.5 &&
      close(seen.top, destination.top) &&
      close(seen.right, destination.right) &&
      close(seen.bottom, destination.bottom) &&
      close(seen.left, destination.left)
    );
  }

  function scrollRevealedRange(where, behavior = scrollBehavior()) {
    const holder = placeHolder(where);
    if (!holder) return;
    const targetScroller = scrollingBoxFor(holder);
    if (!targetScroller) return;
    // Reveal nested scrollports without writing the document position, then glide the
    // owning reading region once. A wide pre or diagram needs both axes settled first.
    for (let box = holder; box && box !== targetScroller; box = renderedParent(box)) {
      if (box.scrollWidth <= box.clientWidth && box.scrollHeight <= box.clientHeight)
        continue;
      const band = landingBand(box);
      if (!band) continue;
      const { left, right, top, bottom } = band;
      const destination = where.getBoundingClientRect();
      let byX = 0;
      if (destination.left < left && destination.right <= right)
        byX = destination.left - left;
      else if (destination.right > right && destination.left >= left)
        byX = destination.right - right;
      let byY = 0;
      if (destination.top < top && destination.bottom <= bottom)
        byY = destination.top - top;
      else if (destination.bottom > bottom && destination.top >= top)
        byY = destination.bottom - bottom;
      if (byX || byY) box.scrollBy({ left: byX, top: byY, behavior: "instant" });
    }
    moveScrollerBy(targetScroller, centreBy(where, "center", targetScroller), behavior);
  }

  function scrollToRange(where, behavior = scrollBehavior()) {
    const holder = placeHolder(where);
    if (!holder) return;
    reveal(holder, retainUserIntent());
    scrollRevealedRange(where, behavior);
  }

  // Hydration may outlive its gesture. After it settles, validate the retained intent
  // and synchronously repaint before reading placement. The second refresh after reveal
  // handles outlets or fallback placement whose geometry appears only when opened.
  // Where a thread's travel lands: its first mark, or the element its anchor placed.
  const threadDestination = (id) =>
    anchors.marksFor(id)[0] ?? anchors.placedAt(id)?.element ?? null;

  async function scrollToThread(id, { land = null, keep = false } = {}) {
    const mayArrive = retainTravel();
    const thread = currentThreads().find((candidate) => candidate.root.id === id);
    const anchor = thread?.anchor;
    const status = anchors.placedAt(id)?.status;
    const hydrating =
      (anchor?.datum && status !== "outdated") ||
      (anchor?.visual && status === "fallback");
    const standing = threadDestination(id);
    // Decided before the trip awaits anything: a destination that is not readable now,
    // or one a widget has yet to hydrate, is somewhere else.
    const landing = () => threadDestination(id);
    if (standing || hydrating) trip(standing, { landing, keep, intent: mayArrive });
    if (hydrating) {
      const source = sectionOf(anchor);
      // A visual draws the state holding its part synchronously; a lazy datum may load.
      if (anchor.visual) revealVisualPart(source, anchor.visual);
      const hydration = anchor.datum && source?.lfRevealDatum?.(anchor.datum);
      if (hydration?.then) await hydration;
      if (!mayArrive() || sectionOf(anchor) !== source) return false;
      await refreshConversation();
      if (!mayArrive()) return false;
    }

    let where = threadDestination(id);
    if (!where) return false;
    let holder = placeHolder(where);
    if (!holder) return false;
    await reveal(holder, mayArrive);
    if (!mayArrive()) return false;
    // The marks, the placement and the widget outlet this arrival lands in are all
    // written by the conversation pass. Wait for it: a claim is synchronous but its
    // paint is not, so reading the destination in this turn would find the page as the
    // press left it.
    await refreshConversation();
    if (!mayArrive()) return false;
    where = threadDestination(id);
    if (!where) return false;
    holder = placeHolder(where);
    if (!holder) return false;
    land?.();
    if (arrived(where, keep)) return true;
    // Reveal has already had its one chance to replace projection DOM. Scrolling the
    // fresh placement must not emit another lf-reveal before using that identity.
    if (where instanceof Range) scrollRevealedRange(where);
    else scrollRevealedElement(where);
    return true;
  }

  return {
    trip,
    navigateToDatum,
    scrollToElement,
    scrollRevealedElement,
    readableDestination,
    scrollToRange,
    scrollToThread,
    threadDestination,
  };
}
