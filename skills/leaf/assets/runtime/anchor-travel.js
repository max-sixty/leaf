/* Travel to a place on the page.
 *
 * A place is what an anchor names (anchor-resolution.js): an addressed element, which
 * is what a fragment names too, a passage inside one, or a part of a widget, a projected
 * datum or a visual part. A thread travels to the place its anchor names, a fragment
 * link to its element, an Ask to its own arrival region, and a module's
 * `navigateToDatum` to the part its declared reference addresses. Whichever route names
 * it, a part is drawn through the one `revealAddressed`, what holds the place opens
 * through the one `reveal`, and the surface hiding it is cleared through the one
 * `clearFor`; where focus lands stays each route's own.
 *
 * Travel owns effects above readonly resolution and paint. It receives the current
 * semantic threads and the synchronous thread refresh from the application root;
 * subordinate geometry never imports the presenter. A trip keeps its original user
 * intent through hydration, reveal and presentation. Newer input or another trip
 * cancels its landing without cancelling the data the page is loading. Every trip, to a
 * thread, an Ask or a datum, goes through `trip`, which clears whatever surface hides
 * the destination and then decides whether the user is already there or departs. A
 * departure leaves a history entry, so browser Back returns the user to where they
 * were reading; a journey, trips each leaving from the last one's landing, is one
 * entry. A fragment link's trip (`followFragment`) departs by the browser's own entry,
 * and Back or Forward to a place the page has hidden since (`returnToFragment`) is a
 * trip that departs by none.
 */

import {
  addressedElements,
  fragmentTarget,
  referencedProjection,
  requireReference,
  revealAddressed,
  sectionOf,
} from "./anchor-resolution.js";
import {
  clippedContents,
  clipsPast,
  landingBand,
  placeHolder,
  shownBox,
  shownRect,
} from "./geometry.js";
import { scrollBehavior } from "./motion.js";
import { scrollersOf } from "./reading-regions.js";
import { pushEntry, replaceEntry } from "./history.js";
import { moveScrollerBy, pageScroller, reachable } from "./scrolling.js";
import { renderedParent } from "./shadow.js";
import { closestAcross } from "./passages.js";
import { reveal } from "./widget-elements.js";
import { retainUserIntent } from "./user-intent.js";
import { pointOf } from "./pointed-place.js";
import { threadKey } from "./thread/model.js";

// The browser's rule for landing the element a fragment names: its start at its
// scroller's landing edge, which a sticky header's declared room keeps clear. Travel
// applies it where the browser's own landing does not reach the element: at an arrival
// the page reshapes after the browser landed it (version.js, `aimArrival`), and at a
// traversal, where the browser restores an offset instead (`returnToFragment`).
export function scrollToFragment(element) {
  element.scrollIntoView({ block: "start", inline: "nearest", behavior: "instant" });
}

export function createAnchorTravel({
  anchors,
  surfaces,
  currentThreads,
  refreshThread,
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
  // rather than a node because the thread pass repaints marks, and the entry
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

  // A fragment link naming an element of the page is a trip there whose departure is
  // the browser's: the navigation has already added the entry Back returns to, whoever
  // followed it — a press on a page link or a reply's reference, a Go-to hint. What the
  // platform lacks for a page place is travel's to add, the same as for any other
  // destination: clear the surface hiding it (a covering Threads panel left the page
  // scrolling behind it, the link's own thread still in front), and reveal what holds
  // it, which reaches a widget's own disclosure as well as `hidden="until-found"` (a
  // worker in a shut goal is `display: none`, and the browser landed on nothing). It
  // then lands by the browser's own fragment rule (`land`, history.js), which moves
  // `:target` and the sequential focus starting point with it, so the arrival at a
  // fresh load (version.js, `aimArrival`) and one in session reveal and land alike. A
  // fragment naming nothing here is not claimed, and the browser keeps it.
  function followFragment(url, land) {
    const where = fragmentTarget(url.hash);
    return where && fragmentTrip(where, land);
  }

  // Back or Forward restores the offset the entry was left at (history.js), which is
  // where the user was reading while the page still holds the place the entry's
  // fragment names. Once that place is no longer shown, closed since in a tab, a
  // disclosure or a widget's own shut state, the offset was read over a page that has
  // changed, and restoring it lands on whatever now sits at that pixel. The fragment is
  // then the one thing the entry still says, so the traversal is a trip to it that
  // departs by no new entry: the same clearing and reveal as a followed link. The
  // browser's own landing on a traversal is that offset, so travel lands the place by
  // the fragment rule itself (`scrollToFragment`).
  function returnToFragment(url) {
    const where = fragmentTarget(url.hash);
    return where && !where.checkVisibility()
      ? fragmentTrip(where, () => scrollToFragment(where))
      : null;
  }

  function fragmentTrip(where, land) {
    const mayArrive = retainTravel();
    return async () => {
      mayArrive.handoff(() => surfaces.clearFor(where));
      await reveal(where, mayArrive);
      if (mayArrive()) land();
    };
  }

  async function navigateToDatum(
    owner,
    attribute,
    key,
    { success = "", missing = "" } = {},
  ) {
    const mayArrive = retainTravel();
    requireReference("navigateToDatum", owner, attribute);
    if (typeof key !== "string" || !key)
      throw new TypeError("navigateToDatum key must be a non-empty string");
    let source = referencedProjection(owner, attribute);
    if (!source) {
      if (missing) announce(missing);
      return false;
    }

    // The widget owns filters, lazy projection, and the state a visual draws. Ask it to
    // make the key reachable before interpreting DOM presence.
    const hydration = revealAddressed(source, key);
    if (hydration?.then) await hydration;
    if (!mayArrive()) return false;
    source = referencedProjection(owner, attribute);
    if (!source) {
      if (missing) announce(missing);
      return false;
    }
    let destination = addressedElements(source, key)[0] ?? null;

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
    destination = source && (addressedElements(source, key)[0] ?? null);
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

  // Where in its scroller's landing band a destination's top stands. An element keeps
  // the room its own `scroll-margin-top` asks for, which is the browser's rule for every
  // native landing: a destination wearing the ring outside itself asks for the ring's
  // room, and a landing flush with the band's edge cut the ring off there.
  function centreBy(where, block = "center", box = pageScroller) {
    const rect =
      where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
    const band = landingBand(box);
    const room = band.bottom - band.top;
    const margin =
      where instanceof Range
        ? 0
        : Number.parseFloat(getComputedStyle(where).scrollMarginTop) || 0;
    const place =
      where instanceof Range
        ? (room - rect.height) / 2
        : block === "start"
          ? margin
          : Math.max((room - rect.height) / 2, margin);
    return rect.top - band.top - place;
  }

  // Reading-region membership also covers fixed chrome, but its viewport position does
  // not move with that region, so a fixed boundary ends the scrollers that move it
  // (`scrollersOf`); a scroller inside that boundary still owns its ordinary descendants.
  const scrollingBoxFor = (element) => scrollersOf(element).next().value ?? null;

  // Centre a destination in the box that scrolls it, then bring it into each box around
  // that one only as far as it must: a bounded block the page shows leaves the page
  // still, and one scrolled out of the window comes back with the destination in it.
  // Each move is reckoned from where the moves inside it leave the destination, so a
  // glide in the inner box composes with the one around it.
  function centreThrough(where, holder, block, behavior) {
    const [box, ...around] = scrollersOf(holder);
    if (!box) return;
    const rect =
      where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
    let { top, bottom } = rect;
    const centre = centreBy(where, block, box);
    let moved = reachable(box, centre);
    moveScrollerBy(box, centre, behavior);
    for (const outer of around) {
      top -= moved;
      bottom -= moved;
      const band = landingBand(outer);
      if (!band) return;
      const by =
        top < band.top
          ? top - band.top
          : bottom > band.bottom
            ? Math.min(bottom - band.bottom, top - band.top)
            : 0;
      moved = reachable(outer, by);
      if (Math.abs(moved) >= 1) moveScrollerBy(outer, moved, behavior);
    }
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
    // The document and nested reading regions share this path. Only the scroller that
    // actually owns the element receives the centring move.
    centreThrough(element, element, block, behavior);
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
    const band = box ? landingBand(box) : shownBox(pageScroller);
    const close = (a, b) => Math.abs(a - b) <= 0.5;
    return (
      destination.top >= band.top - 0.5 &&
      destination.bottom <= band.bottom + 0.5 &&
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
    centreThrough(where, holder, "center", behavior);
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
  // A thread pointed into its target is travelled to at the row its own margin row
  // stands by (pointed-place.js), which a target taller than the window would otherwise
  // leave off screen.
  const threadDestination = (id) => {
    const where = anchors.marksFor(id)[0] ?? anchors.placedAt(id)?.element ?? null;
    const thread =
      where instanceof Element &&
      currentThreads().find((candidate) => candidate.id === id);
    return (thread && pointOf(threadKey(thread), where)) || where;
  };

  async function scrollToThread(id, { land = null, keep = false } = {}) {
    const mayArrive = retainTravel();
    const thread = currentThreads().find((candidate) => candidate.id === id);
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
      const hydration =
        source && revealAddressed(source, anchor.visual ?? anchor.datum);
      if (hydration?.then) await hydration;
      if (!mayArrive() || sectionOf(anchor) !== source) return false;
      await refreshThread();
      if (!mayArrive()) return false;
    }

    let where = threadDestination(id);
    if (!where) return false;
    let holder = placeHolder(where);
    if (!holder) return false;
    await reveal(holder, mayArrive);
    if (!mayArrive()) return false;
    // The marks, the placement and the widget outlet this arrival lands in are all
    // written by the thread pass. Wait for it: a claim is synchronous but its
    // paint is not, so reading the destination in this turn would find the page as the
    // press left it.
    await refreshThread();
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
    followFragment,
    returnToFragment,
    navigateToDatum,
    scrollToElement,
    scrollRevealedElement,
    readableDestination,
    scrollToRange,
    scrollToThread,
    threadDestination,
  };
}
