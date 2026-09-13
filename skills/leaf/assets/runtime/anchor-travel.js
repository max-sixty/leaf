/* Anchor and projected-datum travel.
 *
 * Travel owns effects above readonly resolution and paint. It receives the current
 * semantic threads and the synchronous conversation refresh from the application root;
 * subordinate geometry never imports the presenter.
 */

import {
  currentDatum,
  projectionReferenceDeclared,
  referencedProjection,
  sectionOf,
  suppliedDatum,
} from "./anchor-resolution.js";
import { clippedRect, shownBand, shownBox, shownRect } from "./geometry.js";
import { scrollBehavior } from "./motion.js";
import { scrollerFor } from "./reading-regions.js";
import { moveScrollerBy, pageScroller } from "./scrolling.js";
import { upFrom } from "./shadow.js";
import { closestAcross } from "./passages.js";
import { reveal } from "./widget-elements.js";

export function createAnchorTravel({
  anchors,
  currentThreads,
  refreshConversation,
  announce,
  focused,
}) {
  let threadTravelIntent = 0;
  let mounted = false;
  const leaveThreadTravel = () => threadTravelIntent++;

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
    source = referencedProjection(owner, attribute);
    if (!source) {
      if (missing) announce(missing);
      return false;
    }
    let destination = currentDatum(source, key) ?? suppliedDatum(source, key);

    const url = new URL(window.location.href);
    url.hash = source.id;
    history.pushState(null, "", url);
    if (!destination) {
      scrollToElement(source, scrollBehavior(), "start");
      if (missing) announce(missing);
      return false;
    }

    reveal(destination);
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
    const clear = parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
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

  function scrollToElement(element, behavior = scrollBehavior(), block = "center") {
    reveal(element);
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
        ? clippedRect(destination, holder, new Map())
        : shownRect(where, new Map());
    if (!seen) return false;
    const box = scrollingBoxFor(holder);
    const view = shownBox(box ?? pageScroller);
    const style = box && getComputedStyle(box);
    const clearAbove = parseFloat(style?.scrollPaddingTop) || 0;
    const clearBelow = parseFloat(style?.scrollPaddingBottom) || 0;
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
      const band = shownBand(box);
      if (!band) continue;
      const style = getComputedStyle(box);
      const left = band.left + (parseFloat(style.scrollPaddingLeft) || 0);
      const right = band.right - (parseFloat(style.scrollPaddingRight) || 0);
      const top = band.top + (parseFloat(style.scrollPaddingTop) || 0);
      const bottom = band.bottom - (parseFloat(style.scrollPaddingBottom) || 0);
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
    reveal(holder);
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
    const intent = ++threadTravelIntent;
    const startingFocus = focused();
    const thread = currentThreads().find((candidate) => candidate.root.id === id);
    const anchor = thread?.anchor;
    if (anchor?.datum && anchors.placedAt(id)?.status !== "outdated") {
      const source = sectionOf(anchor);
      const hydration = source?.lfRevealDatum?.(anchor.datum);
      if (hydration?.then) await hydration;
      if (
        intent !== threadTravelIntent ||
        sectionOf(anchor) !== source ||
        (focused() !== startingFocus && focused() !== document.body)
      )
        return false;
      refreshConversation();
    }

    let where = anchors.marksFor(id)[0] ?? anchors.placedAt(id)?.element;
    if (!where) return false;
    let holder = destinationHolder(where);
    if (!holder) return false;
    reveal(holder);
    refreshConversation();
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

  function mount() {
    if (mounted) return;
    mounted = true;
    for (const type of ["pointerdown", "keydown", "input", "wheel"])
      addEventListener(type, leaveThreadTravel, { capture: true, passive: true });
    addEventListener("blur", leaveThreadTravel);
  }

  function destroy() {
    if (!mounted) return;
    mounted = false;
    for (const type of ["pointerdown", "keydown", "input", "wheel"])
      globalThis.removeEventListener(type, leaveThreadTravel, { capture: true });
    globalThis.removeEventListener("blur", leaveThreadTravel);
    threadTravelIntent++;
  }

  return {
    mount,
    destroy,
    navigateToDatum,
    scrollToElement,
    scrollRevealedElement,
    readableDestination,
    scrollToRange,
    scrollToThread,
  };
}
