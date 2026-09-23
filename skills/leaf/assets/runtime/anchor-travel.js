/* Anchor and projected-datum travel.
 *
 * Travel owns effects above readonly resolution and paint. It receives the current
 * semantic threads and the synchronous conversation refresh from the application root;
 * subordinate geometry never imports the presenter. A trip keeps its original user
 * intent through hydration, reveal and presentation. Newer input or another trip
 * cancels its landing without cancelling the data the page is loading. A trip to a
 * thread or datum somewhere else leaves one history entry per run of trips, so browser
 * Back returns the user to where they were reading before the run.
 */

import {
  currentDatum,
  projectionReferenceDeclared,
  referencedProjection,
  sectionOf,
  suppliedDatum,
} from "./anchor-resolution.js";
import {
  clippedContents,
  landingBand,
  landingInsets,
  shownBox,
  shownRect,
} from "./geometry.js";
import { scrollBehavior } from "./motion.js";
import { scrollerFor } from "./reading-regions.js";
import { moveScrollerBy, pageScroller } from "./scrolling.js";
import { upFrom } from "./shadow.js";
import { closestAcross } from "./passages.js";
import { reveal } from "./widget-elements.js";
import { retainUserIntent } from "./user-intent.js";

export function createAnchorTravel({
  anchors,
  currentThreads,
  refreshConversation,
  announce,
}) {
  let travelIntent = 0;
  const retainTravel = () => {
    const intent = ++travelIntent;
    return retainUserIntent({ available: () => intent === travelIntent });
  };

  // The browser saves the current scroll position onto the entry a push leaves and
  // restores it when Back traverses to it, which is the native restoration history
  // travel keeps (version.js). A push therefore comes before the trip moves anything.
  // A thread already readable where the user stands is no trip and records nothing.
  // A trip from where another trip landed replaces that landing's entry, so a walk of
  // any length is one step back to where the user was reading before it began.
  function depart(url = window.location.href) {
    if (history.state?.lfTrip) history.replaceState(history.state, "", url);
    else history.pushState({ lfTrip: true }, "", url);
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
    depart(url);
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
    scrollRevealedElement(destination);
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

  function readableDestination(where) {
    const holder =
      where instanceof Range
        ? where.startContainer instanceof Element
          ? where.startContainer
          : where.startContainer.parentElement
        : where;
    if (!holder) return false;
    const destination =
      where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
    const seen =
      where instanceof Range
        ? clippedContents(destination, holder, new Map())
        : shownRect(where, new Map());
    if (!seen) return false;
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
    const holder =
      where.startContainer instanceof Element
        ? where.startContainer
        : where.startContainer.parentElement;
    if (!holder) return;
    const targetScroller = scrollingBoxFor(holder);
    if (!targetScroller) return;
    // Reveal nested scrollports without writing the document position, then glide the
    // owning reading region once. A wide pre or diagram needs both axes settled first.
    for (
      let box = holder;
      box && box !== targetScroller;
      box = box.assignedSlot ?? box.parentElement ?? box.getRootNode()?.host ?? null
    ) {
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
    const holder = destinationHolder(where);
    if (!holder) return;
    reveal(holder, retainUserIntent());
    scrollRevealedRange(where, behavior);
  }

  const destinationHolder = (where) =>
    where instanceof Range
      ? where.startContainer instanceof Element
        ? where.startContainer
        : where.startContainer.parentElement
      : where;

  // Hydration may outlive its gesture. After it settles, validate the retained intent
  // and synchronously repaint before reading placement. The second refresh after reveal
  // handles outlets or fallback placement whose geometry appears only when opened.
  async function scrollToThread(id, { land = null } = {}) {
    const mayArrive = retainTravel();
    const thread = currentThreads().find((candidate) => candidate.root.id === id);
    const anchor = thread?.anchor;
    const hydrating = anchor?.datum && anchors.placedAt(id)?.status !== "outdated";
    const standing = anchors.marksFor(id)[0] ?? anchors.placedAt(id)?.element;
    // Decided before the trip awaits anything: a destination that is not readable now,
    // or one a widget has yet to hydrate, is somewhere else.
    if ((standing || hydrating) && !(standing && readableDestination(standing)))
      depart();
    if (hydrating) {
      const source = sectionOf(anchor);
      const hydration = source?.lfRevealDatum?.(anchor.datum);
      if (hydration?.then) await hydration;
      if (!mayArrive() || sectionOf(anchor) !== source) return false;
      await refreshConversation();
      if (!mayArrive()) return false;
    }

    let where = anchors.marksFor(id)[0] ?? anchors.placedAt(id)?.element;
    if (!where) return false;
    let holder = destinationHolder(where);
    if (!holder) return false;
    await reveal(holder, mayArrive);
    if (!mayArrive()) return false;
    // The marks, the placement and the widget outlet this arrival lands in are all
    // written by the conversation pass. Wait for it: a claim is synchronous but its
    // paint is not, so reading the destination in this turn would find the page as the
    // press left it.
    await refreshConversation();
    if (!mayArrive()) return false;
    where = anchors.marksFor(id)[0] ?? anchors.placedAt(id)?.element;
    if (!where) return false;
    holder = destinationHolder(where);
    if (!holder) return false;
    land?.();
    if (readableDestination(where)) return true;
    // Reveal has already had its one chance to replace projection DOM. Scrolling the
    // fresh placement must not emit another lf-reveal before using that identity.
    if (where instanceof Range) scrollRevealedRange(where);
    else scrollRevealedElement(where);
    return true;
  }

  return {
    navigateToDatum,
    scrollToElement,
    scrollRevealedElement,
    readableDestination,
    scrollToRange,
    scrollToThread,
  };
}
