/* The anchored response bar: where it stands, what raises it, and the room it keeps.

   Normal reading mode leaves a plain click on unadorned authored content to the
   browser. Visible native and Leaf controls keep their click actions; text selection
   targets words. Alt-click, `s`, and a visual's “Respond to…” proxy are explicit
   Comment gestures. They pass a stable target from `aimTargetAt` or the visual provider
   into this surface. A whole item or picture names its authored id, while a visual part
   adds its declared token. Comment opens the compact field; Tab or its ellipsis extends
   that field with the other response margin entries. Tab, Shift-Tab, and the arrow keys then
   wrap through the visible margin entries. Escape folds the extension; Escape from the field
   hides the draft.
   The same anchor resolves both states against the target's geometry.

   The bar a selection or keyboard-selected addressable raises is `.lf-fab-bar`: the
   durable, compact `.lf-fab-input` followed by one response ellipsis. An explicit
   addressable target
   opens and focuses that field. On desktop, selecting a passage leaves the field open
   but unfocused. On touch screens, selection offers Comment on selection in the banner;
   its press captures the passage, clears the native selection menu, and opens the field.
   Until that press the native handles and menu have the passage to themselves. The
   field grows in place and never transfers text into a second composer card. A
   one-line note uses the shared action corner. A longer one widens up to a readable
   80ch and then wraps. Without a horizontal rail, a quoted passage chooses the
   vertical side with more reachable room; on a touch screen it prefers below whenever
   the page can make room there. The field keeps that side and moves the reading
   region only enough to keep the passage
   and field visible together; it finally scrolls internally. Beside a target, the
   action-bearing foot stays in place while the field grows upward, until the visible
   boundary limits it.
   The target chooses a placement from the field's minimum footprint once. Later
   content and margin controls cannot re-seat it. A region too small for
   the compact control yields to the viewport so the user keeps their response.
   When the target fills the viewport, the viewport still caps the field. When a
   thread panel leaves no usable band for the response bar, placement withdraws it
   without discarding its draft. If the disappearing bar held focus, the visible
   Threads list takes it; an unrelated focused control keeps it. A partially exposed
   page remains interactive whenever the bar fits its actual remaining room. Shift+Enter
   inserts a newline; Enter sends. Tab extends the bar with the layer's reaction
   tokens. A layer with no reaction vocabulary keeps the bar's Comment and Suggest
   fallback.

   `showFab` places the bar; `openComposer` (composing/selection.js) binds its field to
   the durable draft and takes the focus decision. Every explicit item and visual route
   passes its resolved anchor to `commentOnTarget`, which focuses the field and carries an
   unsent draft to the new target. Automatic passage selection opens that passage's own
   durable draft without moving focus. Submitted words still in flight remain owned by
   their original anchor, while a later target starts clean and keeps focus.

   A quoted passage keeps its resolved block clear when choosing the initial side, while
   the exact words supply its vertical attachment. The reading region and fixed Leaf
   chrome are the only collision boundary: page and margin content may be overlaid.
   Leaf chooses the stable side from the block and its reachable reading room. Floating
   UI owns coordinate conversion, overflow, and reflow updates; CSS owns content sizing
   within the width and height its middleware supplies. The viewport holds the bar in
   only while its target is on screen, so a target scrolled away takes the bar with it.

   Boot supplies composer, travel, and mode commands to one surface owner. Its
   constructor binds no document listeners; mount installs the selection gesture
   lifecycle and field-focus tracking after all capabilities have been composed. */
import { cancelRender, nextRender } from "../rendering.js";
import {
  addressableWord,
  anchoringIsReady,
  resolveAnchor,
  visualAt,
} from "../anchor-resolution.js";
import { sameAnchor } from "../anchor-coordinate.js";
import {
  BANNER_CONTROL_RANK,
  dismissBannerControls,
  registerBannerControl,
  showBannerControl,
} from "../banner-shelf.js";
import { shellRight, shownBox, shownParts, shownRect } from "../geometry.js";
import {
  targetElement,
  targetParts,
  targetPlace,
  targetSegments,
} from "../resolved-target.js";
import { composerOpen, fab, fabBar, fabInput } from "./selection.js";

import {
  closeCommandReference,
  commandReferenceOpen,
} from "../keyboard/command-reference.js";

import { paintReactionStanding } from "../reaction-standing.js";
import { generalInput, panel, threadsBox } from "../thread/panel-elements.js";
import { threadInput, standingThread } from "../thread/landing.js";
import { activeCommandLabel } from "../keyboard/dispatch.js";
import { pageCommand, pageRung, pageScope } from "../keyboard/register.js";

import { elementById, inChrome, pageRange, pageText, pageWords } from "../passages.js";
import {
  leftThePage,
  pageSelection,
  selectionAnchor,
  snapSelection,
} from "./capture.js";
import { repaint } from "../repaint.js";
import { focusDestination, letGo, readCaret, takesLetters } from "../focus.js";
import { focused } from "../keyboard/scopes.js";

import { pointerAt } from "../pointer.js";
import { anchorLabel } from "../thread/messages.js";

import { reactionsAt } from "../thread/model.js";
import { allThreads } from "../thread/state.js";

import {
  containingReadingRegionFor,
  effectiveScroller,
  shownRegionBounds,
} from "../reading-regions.js";
import { moveScrollerBy } from "../scrolling.js";

// The two routes to one Comment capability: the page's own, and the Threads list's local
// one. The destination box's placeholder names whichever of them dispatch would answer.
const COMMENT_COMMANDS = ["comment.create", "comment.write"];

const BANNER_CLEAR = 48;
// Whether the user's primary pointer is a finger, as the theme's --aim-floor asks it.
const coarsePointer = matchMedia("(pointer: coarse)");
let floatingUiModule = null;
const floatingUi = () => (floatingUiModule ??= import("/vendor/floating-ui.esm.js"));

export function createResponseSurface({
  panelIsOpen,
  landIn,
  setPanel,
  activeInlineThread,
  standingElement,
  composerHolds,
  responseOptionsAreOpen,
  markAt,
  scrollToElement,
  scrollRevealedElement,
  visualActionAnchor,
  hideComposer,
  openComposer,
  resetResponseOptions,
  responseOptionsAvailable,
  setResponseOptions,
  syncResponseOptions,
  designModeActive,
  designTarget,
  openOnDesign,
  isReactArmed,
  reactionContextContains,
  reactionTokens,
  setReact,
  banner,
  bottomChromeBoxes,
  closeShortcutShelf,
  closeVersionMenu,
  versionMenuIsOpen,
  openPageThread,
  drawModeActive,
  refreshThread,
  responseHome,
}) {
  const hideReference = () => closeCommandReference(false);
  const hasOtherResponses = (anchor) =>
    reactionTokens().length > 0 || Boolean(anchor?.quote && !designModeActive());

  // ---------- selection → comment ----------
  // Floating UI stays inside the document page shell, whose right edge stops short of the
  // root scrollport's gutter. The panel stands over the page, so an open panel's own left
  // edge bounds it too: where it stands, which offsetLeft reads through its slide.
  const rightEdge = (bounds = null) =>
    (bounds?.right ??
      Math.min(shellRight(), panel.open ? panel.offsetLeft : Infinity)) - 8;
  // The response surface lives in the viewport plane and Floating UI follows the passage
  // through every scroll ancestor. Every caller therefore reasons in the same coordinates:
  // rects, the pointer, and the banner's own band. The fixed floor covers the ordinary
  // one-line banner; its live box takes over when compact chrome wraps to a second line.
  const topEdge = (bounds = null) =>
    bounds?.top ?? Math.max(BANNER_CLEAR, banner.getBoundingClientRect().bottom + 6);
  const bottomEdge = (left, width, bounds = null) => {
    if (bounds) return bounds.bottom - 8;
    const tops = bottomChromeBoxes()
      .filter((box) => left < box.right && left + width > box.left)
      .map((box) => box.top - 8);
    return tops.length ? Math.min(...tops) : innerHeight - 8;
  };
  const floatBoundary = (bounds = null) => {
    // Pinch zoom and a software keyboard change the visible viewport without resizing
    // the document's layout viewport. Intersect the reading room with that visible band
    // before choosing a side or sizing the field; autoUpdate follows its resize/scroll.
    const viewport = window.visualViewport;
    const visibleLeft = viewport?.offsetLeft ?? 0;
    const visibleTop = viewport?.offsetTop ?? 0;
    const left = Math.max(bounds?.left ?? 0, visibleLeft) + 8;
    const right = Math.min(
      rightEdge(bounds),
      visibleLeft + (viewport?.width ?? innerWidth) - 8,
    );
    const top = Math.max(topEdge(bounds), visibleTop + 8);
    const bottom = Math.min(
      bottomEdge(left, Math.max(0, right - left), bounds),
      visibleTop + (viewport?.height ?? innerHeight) - 8,
    );
    return {
      x: left,
      y: top,
      left,
      top,
      right,
      bottom,
      width: Math.max(0, right - left),
      height: Math.max(0, bottom - top),
    };
  };
  let fabAnchor = null;
  let fabOrigin = null;
  let fabFloating = true;
  let fabInlineOutlet = null;
  let fabPlacement = null;
  let fabInlineConnection = null;
  let fabSideFootOffset = null;
  let fabPlacementInput = null;
  let fabMinimumWidth = null;
  let fabMinimumComposer = null;
  let fabPositionEpoch = 0;
  let fabPositionFrame = 0;
  let fabPositionCleanup = null;
  let fabPositionTarget = null;
  let fabContentHeight = null;
  let fabPositionWaiters = [];
  const fabFocused = () => (fabInlineOutlet ? focused() : document.activeElement);

  // Measure the compact response once per anchor/state. Expanded choices are designed to
  // wrap and therefore cannot redefine whether the response surface fits at all.
  const minimumFabWidth = () => {
    if (fabMinimumWidth === null || fabMinimumComposer !== composerOpen) {
      fabMinimumComposer = composerOpen;
      fabMinimumWidth = composerOpen
        ? parseFloat(
            getComputedStyle(fabInput).getPropertyValue("--lf-response-min-width"),
          ) + Math.max(0, fabBar.offsetWidth - fabInput.offsetWidth)
        : fabBar.scrollWidth;
    }
    return fabMinimumWidth;
  };
  const fabFits = (bounds = null) => {
    const boundary = floatBoundary(bounds);
    return (
      boundary.width > 0 && Math.ceil(boundary.width) >= Math.ceil(minimumFabWidth())
    );
  };
  const minimumFabHeight = () =>
    composerOpen
      ? Math.max(0, fabBar.offsetHeight - fabInput.offsetHeight) +
        parseFloat(getComputedStyle(fabInput).minHeight)
      : fabBar.offsetHeight;

  const answerFabPosition = (positioned) => {
    const waiters = fabPositionWaiters;
    fabPositionWaiters = [];
    for (const resolve of waiters) resolve(positioned);
  };

  // One lifecycle for the one floating surface. Floating UI observes the target's scroll,
  // resize, layout shift, and the bar's own content size. Leaf's explicit layout signals
  // still call placeFab because a document revision can replace the semantic target rather
  // than merely move its old node.
  // `repositioning` is the caller saying it is moving the bar rather than putting it
  // away: it answers the waiters itself once the bar has landed. Answering here would
  // take them out of the list — one answer drains it — and tell a user waiting to be
  // put in the field that the bar has no position, in the middle of giving it one.
  function stopFabPositioning({ reset = false, repositioning = false } = {}) {
    fabPositionEpoch += 1;
    cancelRender(fabPositionFrame);
    fabPositionFrame = 0;
    fabPositionCleanup?.();
    fabPositionCleanup = null;
    fabPositionTarget = null;
    fabContentHeight = null;
    if (!reset) return;
    if (!repositioning) answerFabPosition(false);
    fabPlacement = null;
    fabInlineConnection = null;
    fabSideFootOffset = null;
    fabPlacementInput = null;
    fabMinimumWidth = null;
    fabMinimumComposer = null;
    fabBar.removeAttribute("data-lf-placement");
    for (const property of [
      "--lf-float-w",
      "--lf-response-room",
      "--lf-float-h",
      "left",
      "top",
    ])
      fabBar.style.removeProperty(property);
    fabBar.style.visibility = "hidden";
  }

  const fabPositioned = () =>
    ((fabInlineOutlet?.isConnected && fabBar.parentElement === fabInlineOutlet) ||
      fabBar.hasAttribute("data-lf-placement")) &&
    fabBar.style.visibility !== "hidden"
      ? Promise.resolve(true)
      : new Promise((resolve) => fabPositionWaiters.push(resolve));

  const captureFabFocus = () => {
    const element = focused();
    if (!(element instanceof HTMLElement) || !fabBar.contains(element)) return null;
    return { element, caret: readCaret(element) };
  };

  const restoreFabFocus = (held) => {
    if (!held || focused() === held.element || !held.element.isConnected) return;
    focusDestination(held.element, held.caret);
  };

  // Reparenting the canonical response bar is presentation, not a composer transition.
  // Preserve the exact typing position across light/shadow DOM moves; Chromium may put
  // focus on the shadow host while a focused field is adopted into its tree.
  function moveFab(parent) {
    if (fabBar.parentElement === parent) return;
    const held = captureFabFocus();
    parent.append(fabBar);
    restoreFabFocus(held);
  }

  function seatFab(outlet) {
    if (!(outlet instanceof Element) || !fabAnchor || !composerOpen) return false;
    if (fabInlineOutlet !== outlet || fabBar.parentElement !== outlet) {
      stopFabPositioning({ reset: true, repositioning: true });
      fabInlineOutlet = outlet;
      fabFloating = false;
      moveFab(outlet);
    }
    fabBar.dataset.lfPresentation = "inline";
    fabBar.style.display = "inline-flex";
    fabBar.style.removeProperty("visibility");
    answerFabPosition(true);
    return true;
  }

  function restoreFab({ place = true } = {}) {
    if (!fabInlineOutlet && fabBar.parentElement === responseHome) return false;
    // Resetting the inline presentation hides the response before moving it back to the
    // viewport plane. Capture the exact focused control first; hiding a focused subtree
    // makes Chromium move focus to body before moveFab can observe what was held.
    const held = captureFabFocus();
    stopFabPositioning({ reset: true, repositioning: place });
    fabInlineOutlet = null;
    fabFloating = true;
    delete fabBar.dataset.lfPresentation;
    moveFab(responseHome);
    if (place && fabAnchor) {
      const displacedFocus = focused();
      if (!placeFab()) showFab(null);
      else if (held)
        void fabPositioned().then((positioned) => {
          if (positioned && focused() === displacedFocus) restoreFabFocus(held);
        });
    }
    return true;
  }

  function scheduleFabPosition() {
    if (fabPositionFrame || !fabAnchor || !fabFloating) return;
    fabPositionFrame = nextRender(() => {
      fabPositionFrame = 0;
      placeFab();
    });
  }

  function watchFabPosition(target, autoUpdate) {
    if (target === fabPositionTarget) return;
    fabPositionCleanup?.();
    fabPositionTarget = target;
    const reference = {
      contextElement: target,
      getBoundingClientRect: () =>
        anchorBox(fabAnchor) ?? target.getBoundingClientRect(),
    };
    fabPositionCleanup = autoUpdate(reference, fabBar, scheduleFabPosition);
  }
  const union = (rects) => {
    if (!rects.length) return null;
    const left = Math.min(...rects.map((rect) => rect.left));
    const top = Math.min(...rects.map((rect) => rect.top));
    const right = Math.max(...rects.map((rect) => rect.right));
    const bottom = Math.max(...rects.map((rect) => rect.bottom));
    return { left, top, right, bottom, width: right - left, height: bottom - top };
  };
  // Whether a resolution is one this document can still put a box beside, which is not the
  // same question as whether it is on screen. Quoted words that resolve to segments stand
  // wherever they are. A source replacement must not close a draft about its prior
  // revision: an outdated finding falls back to its section, while an identified
  // subject keeps the draft beside its current datum even if the quoted words changed.
  // Everything else stands on its element.
  //
  // One rule, because two callers ask it: placement, below, and the route back to a kept
  // draft, which must not offer a passage this version no longer holds.
  const standsIn = (anchor, found) => {
    if (!found) return false;
    if (anchor.quote) {
      if (targetSegments(found).length) return true;
      if (found.status !== "outdated" && !(anchor.identity && found.datumElement))
        return false;
    }
    return Boolean(targetElement(found));
  };
  // Asked of a stored anchor from outside a live response transaction, where the composer
  // is down and there is no native selection to read the passage off.
  const anchorStands = (anchor) =>
    Boolean(anchor) && standsIn(anchor, resolveAnchor(anchor, pageText()));
  // A visual's durable anchor is also the geometry authority. Resolve it again after a
  // reflow instead of remembering where inside the target the pointer happened to land.
  function anchorBox(anchor) {
    if (anchor?.quote) {
      const selection = pageSelection();
      const current = selection ? selectionAnchor(selection) : null;
      if (current && sameAnchor(anchor, current))
        return pageRange(selection).getBoundingClientRect();
      // Entering the compact field deliberately collapses the browser selection after
      // its durable passage has been captured. Resolve that passage again so layout can
      // keep the field beside it; an ordinary selection collapse still returns null and
      // lets updateFab dismiss the response surface.
      // The reactions palette temporarily owns focus and may itself be re-seated during
      // a responsive layout change. The open composer is the durable proof that this
      // captured passage still belongs to the response transaction; native selection is
      // no longer available once the field took focus.
      if (!composerOpen && !fabHoldsCapturedPassage()) return null;
    }
    const found = anchor ? resolveAnchor(anchor, pageText()) : null;
    if (!anchor || !standsIn(anchor, found)) return null;
    const segments = anchor.quote ? targetSegments(found) : [];
    if (segments.length) {
      const range = document.createRange();
      range.setStart(segments[0].node, segments[0].start);
      range.setEnd(segments.at(-1).node, segments.at(-1).end);
      return range.getBoundingClientRect();
    }
    const clips = new Map();
    return union(
      targetParts(found)
        .map((part) => shownRect(part, clips))
        .filter(Boolean),
    );
  }
  // The passage remains the exact anchor, but its resolved place is not spare space: a
  // short selection cannot lend the words around it to the response field. Keep the bar
  // beside that whole place, or above/below it when the rail is too narrow.
  function placeFab(target = anchorBox(fabAnchor)) {
    if (!fabAnchor || !target) return false;
    const owner = fabTargetAt();
    const block = fabAnchor.quote && owner;
    const readingRegion = owner && containingReadingRegionFor(owner);
    let regionBounds = readingRegion && shownRegionBounds(readingRegion);
    let boundary = floatBoundary(regionBounds);
    // Keep the response within its pane while that pane can hold the compact control.
    // A resize can narrow the pane; scrolling can leave only a short visible strip.
    // The response is already a viewport-plane overlay, so let the viewport carry it
    // instead of withdrawing the draft and dropping focus while the user types.
    if (
      regionBounds &&
      (!fabFits(regionBounds) || boundary.height < minimumFabHeight())
    ) {
      regionBounds = null;
      boundary = floatBoundary();
    }
    if (boundary.width <= 0 || boundary.height <= 0) return false;
    const clips = new Map();
    const parts = block ? shownParts(block) : [];
    // Room is a reading of the whole block; clipping changes as the user scrolls.
    // Attachment uses the visible part so the field still meets what is on screen.
    const roomRect =
      union(parts.map((part) => shownBox(part)).filter(Boolean)) || target;
    const keepClear =
      union(parts.map((part) => shownRect(part, clips)).filter(Boolean)) || roomRect;
    const scroller = effectiveScroller(readingRegion ?? owner);
    const visibleVerticalRoom = (side) =>
      side === "top"
        ? roomRect.top - boundary.top - 6
        : boundary.bottom - roomRect.bottom - 6;
    const verticalRoom = (side) => {
      const travel =
        side === "top"
          ? scroller.scrollTop
          : Math.max(
              0,
              scroller.scrollHeight - scroller.clientHeight - scroller.scrollTop,
            );
      return Math.max(
        0,
        Math.min(
          boundary.height - roomRect.height - 6,
          visibleVerticalRoom(side) + travel,
        ),
      );
    };
    const sideRoom = (side) =>
      side === "right"
        ? boundary.right - keepClear.right - 6
        : keepClear.left - boundary.left - 6;
    const initialPlacement = () => {
      if (!block) return "right-start";
      const minimum = minimumFabWidth();
      if (Math.ceil(sideRoom("right")) >= Math.ceil(minimum)) return "right-start";
      if (Math.ceil(sideRoom("left")) >= Math.ceil(minimum)) return "left-start";
      const below = verticalRoom("bottom");
      const above = verticalRoom("top");
      // Prefer below on touch screens. This keeps Leaf away from a native selection menu
      // above the passage, but the browser does not expose that menu's actual bounds.
      if (coarsePointer.matches && below >= minimumFabHeight()) return "bottom-end";
      return below > above ||
        (below === above && visibleVerticalRoom("bottom") > visibleVerticalRoom("top"))
        ? "bottom-end"
        : "top-end";
    };
    // Choose once for the target's horizontal geometry within a reading boundary. Its
    // vertical position moves whenever the user scrolls, but its reachable room does
    // not: visible room and remaining travel trade one-for-one. Keeping that movement
    // out of the cache key prevents scrolling and content growth from re-seating the
    // response while still reconsidering a resized pane or a changed margin rail.
    const placementInput = [
      boundary.left,
      boundary.top,
      boundary.right,
      boundary.bottom,
      keepClear.left,
      keepClear.right,
    ];
    if (
      fabPlacementInput &&
      placementInput.some(
        (value, index) => Math.abs(value - fabPlacementInput[index]) > 0.5,
      )
    ) {
      fabPlacement = null;
      fabInlineConnection = null;
      fabSideFootOffset = null;
      fabContentHeight = null;
    }

    // Width before coordinates: Floating UI chooses a side from the compact surface,
    // then its size pass gives CSS that attachment's actual inline room. If a later
    // resize makes the chosen side narrower than the minimum control, use the whole
    // boundary and let shift overlap the target instead of silently moving the draft.
    const setWidth = (available) => {
      const minimum = minimumFabWidth();
      const width =
        Math.ceil(available) >= Math.ceil(minimum)
          ? available
          : Math.max(0, boundary.width);
      fabBar.style.setProperty("--lf-float-w", `${width}px`);
      if (!composerOpen) return;
      const controls = Math.max(0, fabBar.offsetWidth - fabInput.offsetWidth);
      fabBar.style.setProperty(
        "--lf-response-room",
        `${Math.max(0, width - controls)}px`,
      );
    };
    const setHeight = (available) => {
      if (!composerOpen) return;
      const extra = Math.max(0, fabBar.offsetHeight - fabInput.offsetHeight);
      fabBar.style.setProperty("--lf-float-h", `${Math.max(0, available - extra)}px`);
    };
    const requestedPlacement = fabPlacement ?? initialPlacement();
    const requestedSide = requestedPlacement.split("-", 1)[0];
    const quotedVertical = block && /^(top|bottom)$/.test(requestedSide);
    const fallbackPlacements = {
      "right-start": ["left-start", "top-end", "bottom-end"],
      "left-start": ["right-start", "top-end", "bottom-end"],
      "top-end": ["bottom-end", "right-start", "left-start"],
      "bottom-end": ["top-end", "right-start", "left-start"],
    }[requestedPlacement];
    if (fabPlacement === null) setWidth(boundary.width);
    const room = quotedVertical ? verticalRoom(requestedSide) : boundary.height;
    // A passage's vertical side is chosen from the room the page can make there, and the
    // travel below makes it, so only a side that cannot hold the bar is left to Floating
    // UI's flip. Flipping a settled side on pixels re-decided it over the pixel between
    // the bar as measured here and the bar as laid out.
    const settledSide = quotedVertical && room >= minimumFabHeight();
    setHeight(settledSide ? room : boundary.height);
    // The choices deliberately wrap inside the response surface, so their intrinsic
    // scroll width is not a fit requirement. Only the compact control's minimum is: a
    // covering panel may genuinely leave less than that, while an ordinary narrow page
    // still has a usable surface once the choices reflow below the field.
    if (boundary.height < minimumFabHeight() || !fabFits(regionBounds)) return false;

    // A vertical passage comment belongs beyond the passage, not shifted back across it.
    // When its intrinsic content height changes, use the reading region's remaining
    // travel before asking the field to scroll. The placed height also changes when the
    // passage clips at a boundary; keying this to the content keeps that wheel gesture as
    // navigation rather than undoing it on the next frame.
    const height = fabBar.offsetHeight;
    const contentHeight = composerOpen
      ? fabInput.scrollHeight + Math.max(0, height - fabInput.offsetHeight)
      : fabBar.scrollHeight;
    const contentChanged =
      fabContentHeight === null || Math.abs(contentHeight - fabContentHeight) > 0.5;
    fabContentHeight = contentHeight;
    if (quotedVertical && contentChanged) {
      const overflow =
        requestedSide === "top"
          ? boundary.top - (keepClear.top - 6 - height)
          : keepClear.bottom + 6 + height - boundary.bottom;
      const available =
        requestedSide === "top"
          ? scroller.scrollTop
          : Math.max(
              0,
              scroller.scrollHeight - scroller.clientHeight - scroller.scrollTop,
            );
      const movement = Math.max(0, Math.min(overflow, available));
      if (movement > 0.5) {
        const before = scroller.scrollTop;
        moveScrollerBy(scroller, requestedSide === "top" ? -movement : movement);
        if (Math.abs(scroller.scrollTop - before) > 0.5) {
          fabPlacementInput = null;
          return placeFab();
        }
      }
    }

    const reference = {
      contextElement: owner ?? document.documentElement,
      getBoundingClientRect: () => keepClear,
    };
    const overflow = { boundary: [], rootBoundary: boundary, padding: 0 };
    const epoch = ++fabPositionEpoch;
    const initial = fabPlacement === null;
    const stillCurrent = () => epoch === fabPositionEpoch && fabAnchor && fabFloating;
    const sideTop = (height) =>
      fabSideFootOffset === null
        ? target.top - 6
        : target.top + fabSideFootOffset - height;
    void floatingUi()
      .then(
        ({ autoUpdate, computePosition, flip, limitShift, offset, shift, size }) => {
          if (!stillCurrent()) return null;
          watchFabPosition(owner ?? document.documentElement, autoUpdate);
          return computePosition(reference, fabBar, {
            placement: requestedPlacement,
            strategy: "fixed",
            middleware: [
              offset(({ placement, rects }) => {
                const beside = /^(left|right)/.test(placement);
                return {
                  mainAxis: 6,
                  // The paragraph chooses the horizontal lane. Beside it, keep the
                  // action-bearing foot at its initial attachment as the field grows;
                  // above or below, preserve the initial inline start.
                  crossAxis: beside
                    ? sideTop(rects.floating.height) - keepClear.top
                    : fabInlineConnection === null
                      ? 0
                      : fabInlineConnection + rects.floating.width,
                };
              }),
              // Size precedes the one initial flip so the decision sees the width into
              // which the compact control can actually shrink. This is Floating UI's
              // documented initial-placement composition; putting size last makes a
              // fractional CSS pixel look like a missing margin rail.
              size({
                ...overflow,
                apply({ availableWidth, placement }) {
                  if (!stillCurrent()) return;
                  const side = placement.split("-", 1)[0];
                  const laneWidth =
                    side === "right"
                      ? boundary.right - keepClear.right - 6
                      : side === "left"
                        ? keepClear.left - boundary.left - 6
                        : fabInlineConnection === null
                          ? availableWidth
                          : boundary.right - (keepClear.right + fabInlineConnection);
                  // A side placement consumes its current rail. Above or below, the
                  // relative connection preserves the field's inline start as its content
                  // grows while allowing target reflow to carry that start with it.
                  setWidth(Math.max(0, Math.min(availableWidth, laneWidth)));
                  const vertical = block && /^(top|bottom)$/.test(side);
                  const available = vertical ? verticalRoom(side) : boundary.height;
                  setHeight(
                    vertical && available >= minimumFabHeight()
                      ? available
                      : boundary.height,
                  );
                },
              }),
              initial &&
                !settledSide &&
                flip({
                  ...overflow,
                  crossAxis: false,
                  fallbackPlacements,
                  fallbackStrategy: "bestFit",
                }),
              // The viewport holds the bar in only while its target is still there: past
              // that the bar leaves with it, rather than staying pinned to the viewport's
              // edge over whatever the user scrolled to. Only the block axis is limited;
              // the reading boundary still holds the bar in across it.
              shift({
                ...overflow,
                mainAxis: true,
                crossAxis: true,
                limiter: limitShift(({ placement, rects }) => {
                  const vertical = /^(top|bottom)/.test(placement);
                  // A short field may sit below the reference's own bottom while its
                  // action stays at the established foot. Keep just that extra room in
                  // the attachment limit; the bar still leaves with its passage.
                  return {
                    mainAxis: !vertical,
                    crossAxis: vertical,
                    offset: vertical
                      ? 0
                      : {
                          mainAxis: -Math.max(
                            0,
                            sideTop(rects.floating.height) - keepClear.bottom,
                          ),
                        },
                  };
                }),
              }),
            ],
          });
        },
      )
      .then((position) => {
        if (!position) return;
        const { x, y, placement } = position;
        if (!stillCurrent()) return;
        fabPlacement ??= placement;
        const beside = /^(left|right)/.test(placement);
        const height = fabBar.getBoundingClientRect().height;
        if (beside) fabSideFootOffset ??= y + height - target.top;
        else fabInlineConnection ??= x - keepClear.right;
        fabPlacementInput = placementInput;
        fabBar.dataset.lfPlacement = fabPlacement;
        fabBar.style.left = `${x}px`;
        fabBar.style.top = `${y + (beside ? height : 0)}px`;
        fabBar.style.removeProperty("visibility");
        answerFabPosition(true);
        return true;
      })
      .catch((error) => {
        if (!stillCurrent()) return;
        showFab(null, null, { returnFocus: "page" });
        throw error;
      });
    return true;
  }
  // Where a bar on this anchor hands the user back: the control the gesture stood them
  // on, or the margin's own proxy for the same anchor where that control has gone, found
  // by identity so a repaint cannot strand it. A bar no gesture stood them on has nowhere
  // of its own and the user lands on the page — the element the bar is about is not a
  // landing merely for being named, an ⌥-aimed press having never stood them on it.
  const handBackTo = (anchor, origin) =>
    anchor && !anchor.quote && origin
      ? origin.isConnected
        ? origin
        : visualActionAnchor(anchor)
      : null;
  function showFab(
    anchor,
    target = null,
    { returnFocus = "target", origin = null, place = true } = {},
  ) {
    const previous = fabAnchor;
    const previousOrigin = fabOrigin;
    const previousFloating = fabFloating;
    const leavingBar = !anchor && fabBar.contains(fabFocused());
    const returnToPanel = leavingBar && panelIsOpen() && !fabFits();
    const returnTarget = leavingBar ? handBackTo(previous, previousOrigin) : null;
    const keptInline = Boolean(
      fabInlineOutlet?.isConnected &&
      anchor &&
      previous &&
      sameAnchor(previous, anchor),
    );
    if (!anchor || (fabInlineOutlet && !keptInline)) restoreFab({ place: false });
    if (!anchor) fabInputTakingFocus = false;
    if (!anchor || (previous && !sameAnchor(previous, anchor))) resetResponseOptions();
    if (!anchor && composerOpen) hideComposer();
    if (
      !anchor ||
      !previous ||
      !sameAnchor(previous, anchor) ||
      !place ||
      (!previousFloating && !keptInline)
    )
      stopFabPositioning({ reset: true });
    fabAnchor = anchor;
    fabFloating = !fabAnchor || (place && !keptInline);
    // A call that names the anchor already standing and supplies no control is the same
    // bar being re-placed — the other-responses toggle, leaving react mode, a scroll —
    // rather than a fresh gesture that stood the user nowhere. It keeps the control the
    // opening gesture stood them on; otherwise the way out of a bar the user opened
    // from a proxy would depend on what they did inside it.
    fabOrigin =
      fabAnchor && origin?.isConnected
        ? origin
        : fabAnchor && previous && sameAnchor(previous, fabAnchor)
          ? previousOrigin
          : null;
    fabBar.toggleAttribute("data-lf-target-only", Boolean(fabAnchor && !composerOpen));
    fabBar.style.display = fabAnchor ? "inline-flex" : "none";
    fabInput.style.display = fabAnchor && composerOpen ? "block" : "none";
    syncResponseOptions(fabAnchor);
    // Comment returns from the bar's choice state to this same field. With only a target
    // chosen, the button is the affordance; once Comment is open, the input replaces it.
    fab.style.display = fabAnchor ? "" : "none";
    if (fabAnchor) {
      const label = anchorLabel(fabAnchor).replace(/^§\s*/, "");
      fabBar.setAttribute("aria-label", label ? `Respond to ${label}` : "Respond");
      fabInput.setAttribute("aria-label", label ? `Comment on ${label}` : "Comment");
      // The tokens already standing on this very anchor read pressed, and a press on one
      // takes it back (reactHere): the bar is the strip's shape on the page.
      paintReactionStanding(fabBar, reactionsAt(allThreads(), fabAnchor));
      // A margin control can name an item whose rendered box is currently off
      // screen. `e` still needs the durable anchor so it can extend that existing item;
      // in that route the floating bar is never painted and placement is deliberately
      // skipped. Every route that actually shows the bar keeps the geometry gate.
      if (place && fabFloating && !placeFab(target ?? anchorBox(fabAnchor))) {
        fabAnchor = null;
        fabOrigin = null;
        stopFabPositioning({ reset: true });
        resetResponseOptions();
        fabBar.removeAttribute("data-lf-target-only");
        fabInputTakingFocus = false;
        if (composerOpen) hideComposer();
        fabBar.style.display = "none";
        fabInput.style.display = "none";
        fab.style.display = "none";
      }
    }
    if (!sameAnchor(previous, fabAnchor)) refreshThread();
    repaint(); // the c row names this anchor, so the line is one more rendering of it
    if (!fabAnchor && returnFocus !== "none") {
      if (returnToPanel) threadsBox.focus({ preventScroll: true });
      else if (leavingBar && returnFocus === "target" && returnTarget?.isConnected) {
        returnTarget.focus({ preventScroll: true });
        // The proxy may have gone hidden since the gesture opened the box — a fold that
        // closed under it, a row that re-rendered — and focus on a hidden control does
        // nothing and reports nothing. The page is the landing then, as it is for a box
        // that had no proxy to begin with.
        if (!returnTarget.matches(":focus")) letGo();
      } else if (
        leavingBar ||
        (returnFocus === "page" && document.activeElement === previousOrigin)
      )
        letGo();
    }
  }
  let dismissedSelectionKeyup = false;
  function dismissFab() {
    dismissedSelectionKeyup = Boolean(pageSelection() || fabAnchor?.quote);
    pageSelection()?.removeAllRanges();
    showFab(null);
  }
  function refreshFab() {
    // A target row holds its anchor without floating the bar; layout cannot reject that
    // semantic place merely because the target's rendered box has scrolled away.
    if (!fabAnchor || !fabFloating) return;
    if (fabAnchor.quote && (composerOpen || fabHoldsCapturedPassage())) {
      if (!placeFab() && fabBar.hasAttribute("data-lf-placement"))
        showFab(null, null, { returnFocus: "page" });
    } else if (fabAnchor.quote) updateFab();
    else if (!placeFab() && fabBar.hasAttribute("data-lf-placement"))
      showFab(null, null, { returnFocus: "page" });
  }
  // The durable anchor names the authored coordinate an event can replay, while the
  // margin needs the rendered block the gesture is visibly on. Those are deliberately
  // different for selected words inside a paragraph without an ID: the event names its
  // enclosing section, but both the temporary picker and the standing receipt sit at
  // the paragraph. Match seatReactions' shadow-boundary rule so live and replay agree.
  //
  // Asked of any anchor rather than only of the standing one: a draft the composer put
  // away carries its own anchor and nothing else in the runtime can say which block that
  // draft is about, which is what the route back to it has to travel to.
  const anchorTargetAt = (anchor) => {
    if (!anchor) return null;
    const found = resolveAnchor(anchor, pageText());
    if (!found) return null;
    if (!anchor.quote) return targetElement(found);
    const place = targetPlace(found);
    if (!place) return null;
    const root = place.getRootNode();
    return root instanceof ShadowRoot ? root.host : place;
  };
  const fabTargetAt = () => anchorTargetAt(fabAnchor);
  const fabReturnTo = () => handBackTo(fabAnchor, fabOrigin);

  // Where a comment about this item is written: the composer, on the item, which is what a
  // click through the ⌥ aim already opens. It reached for the widget's own thread seat
  // first for a while, on the reasoning that a widget holding a box for its thread
  // should not be given a second one. That was the wrong shape. `commentOnTarget` writes
  // `{section: item.id}`, which is exactly the anchor `renderSeats` collects into
  // that seat — so the words land in the same thread by either route, and the seat was
  // buying a focus landing at the price of five separate questions: escaping an
  // author-written id into a selector, whether the box can take focus at all (a settled
  // group's seat is inside `hidden="until-found"` and silently swallowed the press), which
  // box when the seat holds several threads, what design mode files, and where the user
  // was already standing. One route answers all five by not asking them.
  //
  // Putting a thing in front of the user before a box is opened about it, for whichever
  // route reaches that box: the item `c` names, and the passage a kept draft comes back to.
  // Both open on a coordinate the user may have scrolled away from, and a box measured
  // against a passage off screen stands beside nothing.
  //
  // Only where it is not already in front of the user. Travelling every time moved
  // the page under someone who could see the thing perfectly well: Tab leaves an item at an
  // edge (`block: nearest`), so centring took the page a third of a viewport with nothing on
  // screen to explain it — on the route this press exists for, and where the ⌥ aim it is the
  // twin of moves nothing at all. The travel is for the standing that has gone stale, focus
  // outliving the scroll that put it there: a box about something off screen is a box about
  // nothing the user can see.
  //
  // What the page shows of it, which is the reading the aim's own paint takes
  // (`refreshAim`) — this being its keyboard twin, the two decide "is this in front of the
  // user" the same way or they are not twins. An unclipped box alone is the box the item
  // would have: an item scrolled out of a board's sideways scroller still reports one
  // inside the window, so a gate reading that called it showing and opened the box on
  // something off screen, which the unconditional travel it replaced never did. A clipped
  // part is enough to offer a target, but not enough to place a response box against; the
  // nearest reveal brings the rest in without moving an item already wholly in view.
  //
  // A collapsed ancestor zeroes its descendants' boxes, so a thing inside a shut
  // disclosure is never showing and takes the travel, `reveal` with it. Standing on the
  // summary itself is the one motion this drops: the disclosure stays shut and the box
  // opens on it where it is, rather than springing it open and reflowing the page under
  // the user who was looking at it.
  //
  // Instant, and before the box is measured. Placing reads the addressable's box, so that has
  // to be the box the addressable keeps; and opening focuses the field, whose
  // scroll-into-view cancels a glide already under way — which is what left the addressable flush against an edge
  // rather than framed, and is not `openComposer`'s to give up, three other presses opening
  // that box against a passage they have not moved.
  function bringForward(addressable) {
    if (!addressable) return;
    const seen = shownRect(addressable, new Map());
    if (!seen || seen.bottom <= BANNER_CLEAR) {
      scrollToElement(addressable, "instant");
      return;
    }
    // A clipped sliver can be enough to offer a viewport-local hint, but not enough to
    // place a response box against. `nearest` reveals it while leaving a target already
    // in front of the user exactly where it is.
    scrollRevealedElement(addressable, "instant", "nearest");
  }

  function commentOnAddressable(addressable) {
    commentOnTarget({ anchor: { section: addressable.id }, element: addressable });
  }

  // Every explicit target gesture ends here. The gesture has already resolved its stable
  // authored anchor; this command owns the one transition from that target into Comment.
  // Focusing the field drops any older browser selection, and an unsent draft follows the
  // deliberate move. A visual proxy supplies its origin so Escape can return to it.
  function commentOnTarget({ anchor, element = null }, { origin = null } = {}) {
    clearTimeout(selectionUpdate);
    selectionUpdate = null;
    bringForward(element);
    targetActivation = true;
    const selection = getSelection();
    if (selection?.rangeCount) selection.removeAllRanges();
    openComment(anchor, "", { carry: true });
    if (origin) showFab(anchor, null, { origin });
    setTimeout(() => {
      targetActivation = false;
      // A browser command or touch handle can replace the visual target while its
      // selectionchange is held out above. Re-read once the explicit activation is
      // complete so that real later selection is not discarded with the focus collapse.
      scheduleSelectionUpdate();
    });
  }
  // Focusing text entry collapses a native page selection. Hold that browser-authored
  // selectionchange out of updateFab: the durable anchor is already captured, and letting
  // the collapse re-read it as no selection dismisses the field the user just entered.
  function focusFabComment() {
    if (!fabAnchor) return;
    clearTimeout(selectionUpdate);
    selectionUpdate = null;
    const handoff = beginFabFocus();
    if (!composerOpen) {
      openComment(structuredClone(fabAnchor), "");
      return;
    }
    const anchor = structuredClone(fabAnchor);
    landFabFocus(handoff, anchor, () => sameAnchor(anchor, fabAnchor));
  }
  const fabOptionsAvailable = () =>
    Boolean(fabAnchor && hasOtherResponses(fabAnchor) && responseOptionsAvailable());
  const showFabOptions = ({ reaction = false } = {}) =>
    setResponseOptions(true, { focus: reaction ? "reaction" : "first" });
  // The response field follows any selection that stores page words. Even a one-character
  // quote carries its section and exact surrounding context, so the resolver can identify
  // its occurrence without guessing from quote length.
  const hasQuote = (anchor) => Boolean(anchor?.quote?.trim());
  const hasPageSelectionTarget = () => {
    const selection = pageSelection();
    const anchor = selection ? selectionAnchor(selection) : null;
    return hasQuote(anchor);
  };

  // Touch selection belongs to the native handles and menu until Comment is pressed.
  // That menu can stand on either side of the words; never compete with it by raising
  // a second adjacent surface. Capture the passage for the banner's explicit action.
  let touchSelectionAnchor = null;
  const selectionComment = document.createElement("button");
  selectionComment.className = "lf-btn primary";
  selectionComment.type = "button";
  selectionComment.textContent = "Comment on selection";
  registerBannerControl({
    key: "comment-selection",
    control: selectionComment,
    rank: BANNER_CONTROL_RANK.commentSelection,
    seat: "gesture",
    present: false,
  });
  const offerTouchSelection = (anchor) => {
    touchSelectionAnchor = anchor;
    showBannerControl(selectionComment, Boolean(anchor));
  };
  const commentOnTouchSelection = () => {
    const anchor = touchSelectionAnchor;
    if (!anchor) return;
    dismissBannerControls();
    clearTimeout(selectionUpdate);
    selectionUpdate = null;
    getSelection()?.removeAllRanges();
    offerTouchSelection(null);
    openComment(anchor, "");
  };

  function updateFab() {
    if (!anchoringIsReady()) {
      offerTouchSelection(null);
      showFab(null);
      return;
    }
    const sel = pageSelection();
    const anchor = sel ? selectionAnchor(sel) : null;
    if (
      coarsePointer.matches &&
      hasQuote(anchor) &&
      (!fabHoldsCapturedPassage() || !sameAnchor(anchor, fabAnchor))
    ) {
      showFab(null);
      offerTouchSelection(anchor);
      return;
    }
    offerTouchSelection(null);
    if (hasQuote(anchor)) {
      // A fast keyboard action can capture this completed native selection before the
      // pointer gesture's queued update arrives. That later update is the same target,
      // not a request to reopen its Comment composer: reopening calls closeReactions
      // and used to collapse choices immediately after `e` exposed them.
      if (sameAnchor(anchor, fabAnchor)) {
        placeFab();
        return;
      }
      // Selecting words is still the browser's gesture. Open Leaf's response field beside
      // them without moving focus into it, so the live Selection remains available to Copy
      // and the native context menu. An explicit Comment press uses the same field and
      // focuses it through focusFabComment below.
      openComment(anchor, "", { focus: false });
    } else if (fabAnchor?.quote && !fabHoldsCapturedPassage()) showFab(null);
  }
  // Where the pointer stopped is not the question; where the selection is, is. The guard
  // exists so a mouseup inside the runtime's layer — a click in the panel, the composer —
  // can't re-decide the response surface out from under an open draft. A drag that ends on a widget's
  // control is the opposite case: the user was selecting that control's label, and a
  // tab's name runs to within a few pixels of the strip button's padding, so the mouseup
  // lands on chrome while the selection is the page's. The snap runs in the same queued
  // step that raises the field, so the bar lands beside the selection as snapped and
  // the capture reads the one the user is looking at — and only for the primary
  // button, because a right button's release precedes its context menu, and growing the
  // selection there rewrites what Copy was aimed at.
  //
  // A queued step belongs to the gesture that queued it, and the next press may begin
  // before it runs. Then the selection it would act on is not the one it was queued
  // for: it is the drag under way, and `snapSelection` rewrites that drag mid-gesture.
  // Chromium does not resume extending a selection it has been handed through
  // `setBaseAndExtent`, so the pointer's remaining travel is lost and a sweep from
  // "paragraph" to "carrying" ends up captured as "paragraph" — the user's own hand
  // is slow enough that the step always ran first, and a loaded machine hands out that
  // ordering freely. The press under way owns the selection and queues its own step on
  // its own release, so standing down here drops no work.
  //
  // Which press is under way is asked as "has one begun since this was queued" rather
  // than as "is one down now". A press whose release never reaches the document — a
  // handler that stops it, a button let go off-window — leaves a pressed flag standing
  // for the rest of the page's life, and read here that would put every later selection
  // out too: the next drag would raise no field and read as a drag that selected
  // nothing. A count compared against the one this step was queued behind cannot get
  // stuck, because the step queued by the next release carries the count it finds.
  let selectionUpdate = null;
  let pressesBegun = 0;
  const deferSelectionUpdate = (update) => {
    const queuedBehind = pressesBegun;
    clearTimeout(selectionUpdate);
    selectionUpdate = setTimeout(() => {
      selectionUpdate = null;
      if (pressesBegun !== queuedBehind) return;
      update();
    });
  };
  const scheduleSelectionUpdate = () => {
    if (selectionUpdate) return;
    deferSelectionUpdate(updateFab);
  };
  let pointerSelecting = false;
  let selectionDragged = false;
  let selectionRangeDuringPress = null;
  let selectionPressPoint = null;
  // A widget may turn a press over page words into a different gesture after pointerdown.
  // `preventDefault` on its bubbling pointermove is the shared claim boundary: the
  // selection surface must not restore the range it captured before that claim.
  let selectionGestureClaimed = false;
  let actionPress = false;
  let targetActivation = false;
  let fabInputTakingFocus = false;
  // Which handoff the mark belongs to. The mark itself is one bit, so a landing that only
  // read the bit could not tell its own handoff's mark from a later one's, and releasing
  // on the way out would drop a mark still being held for a focus yet to land.
  let fabFocusHandoff = 0;
  const beginFabFocus = () => {
    fabInputTakingFocus = true;
    return ++fabFocusHandoff;
  };
  const endFabFocus = () => {
    fabInputTakingFocus = false;
  };
  // Every handoff lands here. It is marked at once and lands a frame or more later, and
  // the user owns the page for the whole of that gap: a passage standing when it lands
  // that this composer did not open on is theirs, taken since, and focusing the field
  // would collapse it before anything could read it. Standing down releases the mark with
  // it, so the collapse the mark holds out cannot outlive the focus it was holding it for.
  function landFabFocus(handoff, anchor, stands) {
    void fabPositioned().then((positioned) => {
      if (handoff !== fabFocusHandoff) return;
      const taken = pageSelection();
      const words = taken ? selectionAnchor(taken) : null;
      if (
        positioned &&
        composerOpen &&
        stands() &&
        (!hasQuote(words) || sameAnchor(words, anchor))
      )
        fabInput.focus({ preventScroll: true });
      else endFabFocus();
    });
  }
  function openComment(anchor, text, options = {}) {
    return openComposer(anchor, text, options);
  }
  function fabHoldsCapturedPassage() {
    return (
      fabInputTakingFocus ||
      fabBar.contains(fabFocused()) ||
      reactionContextContains(fabFocused())
    );
  }
  // Wired once the chrome is mounted (leaf.js): the box is selection.js's, an owner that
  // imports this module back.
  function wireFabInput() {
    fabInput.addEventListener("focus", () => {
      clearTimeout(selectionUpdate);
      selectionUpdate = null;
      fabInputTakingFocus = true;
    });
    fabInput.addEventListener("blur", () => {
      fabInputTakingFocus = false;
    });
  }
  let primaryPointerPressed = false;
  // Whether the page's own words stood selected when the shortcut bar was last painted for
  // this press. The bar waits for the release; the Escape rung cannot, because from the
  // first glyph a drag takes, Escape clears the selection rather than letting go of the
  // control the user is standing on, and until now nothing repainted the line inside a
  // press — the word only became true when the frame the press itself scheduled happened
  // to land after the drag had moved, and stayed a lie for a whole heartbeat when it
  // landed before. Only the crossing is painted: a drag growing a selection that already
  // stands says the same word, and repainting the chrome on every move of a drag would
  // put a whole shared repaint inside every frame of one.
  let selectionStood = false;
  // The page's own words this press began with, against the ones it ends holding: what
  // tells a gesture that took words from a press that merely landed in some (the click
  // door below). Read beside `selectionStood`, ahead of the browser's own collapse, for
  // the same reason.
  let wordsAtPress = "";
  // What this drag has had inside the document, kept against a release that ends holding
  // something else. Only while both ends are still in it: `pageSelection` answers for the
  // end the press began at, which stays in the page for the whole of a drag that leaves it,
  // so without the far end this remembered the runaway range itself and had nothing to put
  // back.
  const rememberPointerSelection = () => {
    const selection = pageSelection();
    if (!selection || leftThePage(selection)) return;
    const anchor = selectionAnchor(selection);
    if (hasQuote(anchor)) selectionRangeDuringPress = pageRange(selection).cloneRange();
  };

  const finishPointerSelection = (ev) => {
    if (drawModeActive()) return;
    // A mouse pointer is followed by the compatibility mouseup below, which performs the
    // sentence snap before opening the field. Opening from pointerup first would focus the
    // field and collapse the still-unsnapped Selection before mouseup can finish it.
    // Touch/pen and cancellation owe us no compatibility mouse event, so they keep this
    // direct route.
    // Released on the next task either way, which keeps selectionchange in the
    // in-progress branch until the compatibility mouseup has been and gone.
    const releasePress = () =>
      setTimeout(() => {
        actionPress = false;
      });
    // Opening or acting in chrome is a route away from the page, not a new selection
    // gesture. Keep the already-captured touch passage verbatim while focus moves
    // through the banner, its sibling popovers, and their controls.
    if (touchSelectionAnchor && inChrome(ev.target)) {
      primaryPointerPressed = false;
      pointerSelecting = false;
      selectionGestureClaimed = false;
      releasePress();
      return;
    }
    if (
      primaryPointerPressed &&
      ev.type === "pointerup" &&
      ev.pointerType === "mouse"
    ) {
      releasePress();
      return;
    }
    if (primaryPointerPressed) scheduleSelectionUpdate();
    primaryPointerPressed = false;
    pointerSelecting = false;
    selectionGestureClaimed = false;
    releasePress();
  };

  // Touch handles and browser selection commands do not owe the page a mouseup or keyup.
  // During a pointer drag, the completed gesture below remains the one that snaps and
  // places the passage; presses on the action surface must not retract their own target.

  // Selections made from the keyboard (shift-arrows, ⌘A) deserve the same response bar. Typing in
  // a box never does, whatever is selected elsewhere.

  // Floating chrome getting out of the way of a press somewhere else, which is a fact about
  // the press rather than about who receives it: the aim takes a press away from the page
  // (see claimPress) and must not take this with it, or the command reference stays up over
  // the composer that press just opened. Hence one function, called from both.
  // The two side panels are absent from it on purpose. A float answers the press in front
  // of it and stands down behind it; the thread panel and the leaves tray are
  // auxiliary surfaces the user stood up, kept through a reload (AUXILIARY_SURFACE_KEY) and so
  // through a click all the more — a tray any press removes cannot be watched while
  // working, which is the tray's point. Each closes by its own button, its key, or Esc.
  function standDown(target) {
    const visual = visualAt(target);
    const sameVisual =
      visual &&
      !fabAnchor?.quote &&
      fabAnchor?.section === visual.id &&
      fabAnchor?.visual === visual.part?.id;
    if (
      !sameVisual &&
      !target.closest?.(".lf-fab-bar, .lf-react-surface, .lf-composer") &&
      !reactionContextContains(target)
    ) {
      if (composerOpen) hideComposer();
      showFab(null, null, { returnFocus: "page" });
      // The armed react press goes with the bar it was armed on.
      setReact(false);
    }
    if (commandReferenceOpen() && !target.closest?.(".lf-command-reference"))
      hideReference();
    if (!target.closest?.(".lf-command-reference, .lf-shortcut-bar"))
      closeShortcutShelf();
    // The press on the button itself is its own toggle, so it is not an outside click;
    // without that the open and this close would both run and the menu could never open.
    if (versionMenuIsOpen() && !target.closest?.(".lf-version-menu, .lf-version"))
      closeVersionMenu();
  }
  // Document listeners see a shadow-tree press retargeted to its host. Read the
  // composed origin so core controls seated in a widget surface remain inside their
  // own composer/reaction layer instead of being dismissed before `click` can fire.

  // What a plain click on the page means, decided once. Design mode explicitly changes the
  // grammar, and a visible mark opens its thread. Unadorned authored content keeps the
  // browser's native meaning; Comment targeting belongs to Alt-click, `s`, and the visual
  // proxies instead.
  //
  // Once, because the hit-test reads layout and opening the panel rewrites it. Two handlers
  // each asking `markAt` looked independent and were not: the first one's setPanel() reflowed
  // the document out from under the second, which then missed the very mark it had just
  // opened and raised the comment field on top of it — leaving an element anchor set, which
  // midComposition() reads, so the page quietly stopped following new versions. The rule this
  // file already carries covers it: a guard that reads state another function wrote is a sign
  // the two are one function.

  const fabAnchorAt = () => fabAnchor;

  function mount() {
    // Keep the native selection through the button's press; focusing the actual
    // comment field performs the handoff after the passage has been captured.
    selectionComment.addEventListener("mousedown", (event) => event.preventDefault());
    selectionComment.addEventListener("click", commentOnTouchSelection);
    coarsePointer.addEventListener("change", scheduleSelectionUpdate);
    document.addEventListener(
      "pointerdown",
      (ev) => {
        if (drawModeActive()) return;
        primaryPointerPressed = ev.isPrimary && ev.button === 0;
        if (primaryPointerPressed) pressesBegun++;
        pointerSelecting = primaryPointerPressed && pageWords(ev.target);
        selectionDragged = false;
        selectionRangeDuringPress = null;
        selectionGestureClaimed = false;
        selectionPressPoint = pointerSelecting
          ? { x: ev.clientX, y: ev.clientY }
          : null;
        // Read here, ahead of the browser's own collapse, so the first crossing this press
        // makes is measured against what the line already says rather than against nothing.
        const stood = pageSelection();
        selectionStood = Boolean(stood);
        wordsAtPress = stood ? stood.toString() : "";
        const selection = pointerSelecting ? stood : null;
        if (selection && pageRange(selection).intersectsNode(ev.target))
          rememberPointerSelection();
        actionPress =
          (touchSelectionAnchor && inChrome(ev.target)) ||
          ev.target === selectionComment ||
          Boolean(ev.target.closest?.(".lf-react-surface, .lf-composer"));
      },
      true,
    );
    document.addEventListener("pointermove", (ev) => {
      if (drawModeActive()) return;
      if (!pointerSelecting || !selectionPressPoint) return;
      if (ev.defaultPrevented) {
        selectionGestureClaimed = true;
        return;
      }
      selectionDragged ||=
        Math.hypot(
          ev.clientX - selectionPressPoint.x,
          ev.clientY - selectionPressPoint.y,
        ) > 3;
    });
    document.addEventListener("pointerup", finishPointerSelection);
    document.addEventListener("pointercancel", finishPointerSelection);
    document.addEventListener("selectionchange", () => {
      if (primaryPointerPressed) {
        rememberPointerSelection();
        const stands = Boolean(pageSelection());
        if (stands !== selectionStood) {
          selectionStood = stands;
          repaint();
        }
        return;
      }
      // The captured passage is not asked about here. What the handoff has to survive is
      // the collapse focusing the field causes, and `updateFab` holds that out at the one
      // branch that acts on an empty selection. Restated here it also swallowed the
      // opposite event: a passage the user went on to select, arriving while the bar
      // still held focus or while its focus was in flight, read as the collapse and was
      // dropped — and the handoff then landed on the field and collapsed the selection,
      // so nothing was left to re-read and the target never moved.
      if (actionPress || targetActivation || takesLetters(document.activeElement))
        return;
      scheduleSelectionUpdate();
    });
    document.addEventListener("mouseup", (ev) => {
      if (drawModeActive()) return;
      const selectedOnPage = pointerSelecting;
      primaryPointerPressed = false;
      pointerSelecting = false;
      const gestureClaimed = selectionGestureClaimed;
      selectionGestureClaimed = false;
      if (gestureClaimed) {
        selectionRangeDuringPress = null;
        scheduleSelectionUpdate();
        return;
      }
      // Only a gesture begun in page words owns their selection. A release from
      // chrome (such as resizing a panel) must not snap an existing passage.
      if (actionPress || !selectedOnPage) return;
      const selection = pageSelection();
      const selected = selection ? selectionAnchor(selection) : null;
      // A drag whose far end left the document is the same release as one that ended holding
      // nothing: what the user meant is what the drag had before the pointer crossed out,
      // and the range this press remembered is that. Without it, a hand five words along a
      // paragraph overshooting the layer by 40px captured 14,387 characters, marked 22,140,
      // and named the whole document in the field — because past the page's last words the
      // browser extends through everything between (leftThePage, composing/capture.js).
      //
      // Asked here and nowhere shared, because the gesture is what tells this from ⌘A: select
      // all means the document and lands its far end past the page by definition, and it
      // arrives through the keyboard's route, which never comes past this line.
      const escaped = selectionDragged && leftThePage();
      const completed =
        selectionDragged && (escaped || !hasQuote(selected))
          ? selectionRangeDuringPress
          : null;
      deferSelectionUpdate(() => {
        if (completed) {
          const restored = getSelection();
          restored.removeAllRanges();
          restored.addRange(completed);
        } else if (escaped) {
          // A drag that crossed out before it covered anything has no passage to offer and
          // no words to put back. The browser's own selection stays where it is — the user
          // can still copy it — and the response surface says nothing about it.
          showFab(null);
          return;
        }
        if (ev.button === 0) snapSelection();
        updateFab();
      });
    });
    document.addEventListener("keyup", (ev) => {
      if (dismissedSelectionKeyup) {
        dismissedSelectionKeyup = false;
        if (ev.key === "Escape") return;
      }
      if (isReactArmed()) return;
      if (takesLetters(ev.target) || inChrome(ev.target)) return;
      if (!pageWords(ev.target) && !pageSelection()) return;
      scheduleSelectionUpdate();
    });
    document.addEventListener("mousedown", (ev) => {
      if (!drawModeActive()) standDown(ev.composedPath()[0]);
    });
    document.addEventListener("click", (ev) => {
      if (drawModeActive()) return;
      if (!pageWords(ev.target)) return;
      // A press that ends holding words it did not begin with took them, and is that
      // selection's mouseup rather than a click on whatever lies under it: the user was
      // reaching for the words, and the 💬 is already up on them (updateFab, on the same
      // mouseup). The same complaint `offer` answers for a press on a control and the
      // thread list for a press on a card (reachedForWords), and it governs the whole of
      // what a click on prose means — the block design mode comments on, and the thread a
      // mark opens. Marked words are where it showed: a gesture inside one travelled to its
      // thread, and with Threads open the reply box it landed in collapsed the selection
      // the user had just made, so the words and the 💬 went with it.
      //
      // Asked of what this press changed rather than of the standing selection those two
      // have to read, because a mark is a painted range with no element to put the question
      // to — and because the state alone is too strict: a press landing inside words
      // already selected keeps them through its own mousedown, so it would refuse the press
      // that opens the very mark the user just picked out. That press is also the only
      // way the two readings can come out the same, since every other gesture moves the
      // selection before its click.
      //
      // Changed, and not "dragged": how far the pointer travelled covers one of the three
      // ways a user takes words, and a double-click's second press and a shift-click's
      // extension both arrive here having just taken some without moving it at all.
      const words = pageSelection();
      if (words && words.toString() !== wordsAtPress) return;
      // A plain click comments on the block it landed in.
      if (designModeActive()) {
        const target = designTarget(ev.target);
        if (target) openOnDesign(target);
        return;
      }
      // The record rather than this event's own coordinates, for the reason the record is
      // kept from a pointer event at all (pointer.js): `click` is a legacy mouse event and
      // carries the pointer's place rounded to a whole pixel, while markAt measures against
      // getClientRects, whose edges are floats. Asked at the rounded point this answered a
      // different thread than refreshHover had just promised at the true one — a quote lit
      // up under the hand and a press on it opening nothing.
      //
      // A click with no press behind it carries 0,0 rather than a position — `offer` calls
      // click() to supply the keys a span doesn't come with — and the record would answer
      // for wherever the pointer is parked, so that one keeps reading the event.
      const point = ev.detail ? pointerAt() : { x: ev.clientX, y: ev.clientY };
      const threadId = markAt(point.x, point.y);
      if (threadId)
        return openPageThread(threadId, {
          focus: panel.classList.contains("open") ? "reply" : "thread",
          travel: false,
        });
    });
    wireFabInput();
  }

  // ---------- where "comment" goes ----------
  // The thread the user is standing in, and the box it is written in. Three
  // containers hold one and the user can stand in any of them: the panel's thread, a
  // thread seated on the page (x-thread-seat), and each thread inside that seat.
  // They are one question — a press meaning "say something about this" belongs to the box
  // of the thread the user is already in — so they get one reading rather than a
  // rule for the panel and a different one for the page.
  //
  // One of the three is in the chrome, which is not the exception it looks like: page scope
  // already crosses there. A page key that takes the user somewhere owes them an answer
  // once they are standing there.
  //
  // One aim and then one climb, rather than four cases. The pointer's aim outranks
  // position, being the more recent thing the user said; below it the answer walks
  // outward from where they are standing — the nearest thread's box, then the nearest
  // addressable element, then the page, which is what is left when they are standing
  // nowhere in it. An element anchor answers in its own word (a figure, a card), the way
  // the panel names one. Every destination is a box to write in and says so in the same
  // sentence; the word is what varies.
  const commenting = (word) => ({
    does: `Comment on the ${word}`,
    line: `comment on the ${word}`,
  });
  function commentDestination() {
    if (touchSelectionAnchor)
      return {
        ...commenting("selection"),
        box: selectionComment,
        go: commentOnTouchSelection,
      };
    const anchor = fabAnchorAt();
    if (anchor)
      return {
        ...commenting(
          anchor.quote
            ? "selection"
            : addressableWord(elementById(anchor.section)) || "element",
        ),
        box: fabInput,
        go: focusFabComment,
      };
    const inline = activeInlineThread();
    const inlineBox = inline && threadInput(inline);
    const said =
      standingThread() ?? (inlineBox ? { held: inline, box: inlineBox } : null);
    if (said)
      return {
        ...commenting("thread"),
        box: said.box,
        go: () => landIn(said),
      };
    const here = standingElement();
    if (here)
      return {
        ...commenting(addressableWord(here)),
        box: fabInput,
        go: () => commentOnAddressable(here),
      };
    return {
      ...commenting("page"),
      box: generalInput,
      // Two steps down and two back: the box hands the user to the list it belongs
      // to, and the panel hands them to the page.
      go: () => {
        setPanel(true);
        generalInput.focus({ preventScroll: true });
      },
    };
  }

  // The destination's box is the identity chrome uses to place a contextual binding badge,
  // and the label is whichever Comment route dispatch would answer from here. Dispatch
  // still decides whether either row can be reached from the current scope.
  const commentHint = () => ({
    box: commentDestination().box,
    label: activeCommandLabel(COMMENT_COMMANDS),
  });

  // c goes where commenting happens: a live selection gets the composer (what the floating
  // button does), an element click's pending 💬 gets that, an open thread the user is
  // standing in gets its own reply box, the item they are standing in gets the box
  // belonging to it, and otherwise the page's general box. That box lives in Threads, but c
  // names and focuses the box directly; g T independently names the list. Never the panel's
  // collapse: c doubled as the toggle once, so with the panel standing open the key that
  // promised “comment” answered “close”. Backing out is whatever the box is standing in.
  //
  // Standing outranks the page and not the pointer: a user who has just selected words or
  // raised the 💬 on something has said what they mean more recently than the focus they
  // left behind, which is the order the destination reading above uses.
  pageCommand({
    id: "comment.create",
    keys: ["c"],
    // The surfaces name the destination in front of the user rather than the capability:
    // "Comment" covered all four and so promised none of them.
    does: () => commentDestination().does,
    line: () => commentDestination().line,
    // A selection made before the anchor pass has run can't be quoted yet, and commenting
    // on the page instead is not what the user asked for — so the press waits, and the
    // row's own liveness is where that is said rather than a refusal inside run that no
    // surface can see.
    when: () => anchoringIsReady() || !pageSelection(),
    run: () => {
      updateFab(); // the selection may be newer than the mouseup that last placed the bar
      commentDestination().go();
    },
  });

  // The composer's own rung is its own scope rather than the box's, because the box may not
  // have focus — the user clicked away and the composer still stands, holding their draft.
  pageScope("composer", {
    title: "In the composer",
    at: () => composerOpen,
    rows: [
      {
        id: "comment.options",
        keys: ["Tab"],
        does: "Show other responses",
        line: "other responses",
        when: () => fabOptionsAvailable() && !responseOptionsAreOpen(),
        run: () => showFabOptions(),
      },
      {
        id: "composer.close",
        keys: ["Escape"],
        does: () =>
          composerHolds()
            ? "Close the composer, keeping the draft"
            : "Close the composer",
        line: () => (composerHolds() ? "close — draft kept" : "close"),
        promoteEscape: false,
        when: () => !responseOptionsAreOpen(),
        run: () => dismissFab(),
      },
    ],
  });

  // The first step of the page's Escape ladder: a selection or a captured target is the
  // innermost thing the user is holding, and letting it go is one press. Clearing a
  // captured target is still available while c and r are the two actions on the thing the
  // user just chose, so it keeps its binding and its place in the reference while
  // yielding the short line's promoted slot to them.
  pageRung("selection", () =>
    pageSelection() || fabAnchorAt()
      ? {
          says: "unselect",
          does: "Clear the selection",
          promoteEscape: !Boolean(fabAnchorAt()) || reactionTokens().length === 0,
          out: dismissFab,
        }
      : null,
  );

  return {
    commentHint,
    fabPositioned,
    beginFabFocus,
    endFabFocus,
    landFabFocus,
    anchorStands,
    showFab,
    dismissFab,
    refreshFab,
    anchorTargetAt,
    fabTargetAt,
    fabReturnTo,
    bringForward,
    commentOnAddressable,
    commentOnTarget,
    focusFabComment,
    fabOptionsAvailable,
    showFabOptions,
    hasPageSelectionTarget,
    updateFab,
    standDown,
    fabAnchorAt,
    seatFab,
    restoreFab,
    fabInlineOutlet: () => fabInlineOutlet,
    mount,
  };
}
