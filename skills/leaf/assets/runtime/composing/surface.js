/* The anchored response bar: where it stands, what raises it, and the room it keeps.

   Normal reading mode leaves a plain click on unadorned authored content to the
   browser. Visible native and Leaf controls keep their click actions; text selection
   targets words. Alt-click, `s`, and a visual's “Respond to…” proxy are explicit
   Comment gestures. They pass a stable target from `aimTargetAt` or the visual provider
   into this surface. A whole item or picture names its authored id, while a visual part
   adds its declared token. Comment opens the compact field; Tab or its ellipsis extends
   that field with the other response margin elements. Tab, Shift-Tab, and the arrow keys then
   wrap through the visible margin elements. Escape folds the extension; Escape from the field
   hides the draft.
   The same anchor resolves both states against the target's geometry.

   The bar a selection or keyboard-selected item raises is `.lf-fab-bar`: the durable,
   compact `.lf-fab-input` followed by one response ellipsis. An explicit item target
   opens and focuses that field. Selecting a passage leaves the field open but unfocused
   without collapsing the browser selection; the reader can still copy
   the selection or use its native context menu, then enter the field with Comment. The
   field grows in place and never transfers text into a second composer card. A
   one-line note uses the shared action corner. A longer one widens up to a readable
   80ch and then wraps, grows toward the available viewport edge, and finally scrolls.
   The target chooses a placement from the field's minimum footprint once. Later
   content and margin controls cannot re-seat it; Floating UI shifts and sizes that
   placement inside the reading region as either one changes.
   When the target fills the viewport, the viewport still caps the field. When a
   covering panel leaves no usable band for the response bar, placement withdraws it
   without discarding its draft. If the disappearing bar held focus, the visible
   Threads list takes it; an unrelated focused control keeps it. A partially exposed
   page remains interactive whenever the bar fits its actual remaining room. Enter
   inserts a newline; `Mod+Enter` sends. Tab extends the bar with the layer's reaction
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
   Floating UI owns coordinate conversion, overflow, fallback side, and reflow updates;
   CSS owns content sizing within the width and height its middleware supplies.

   Boot supplies composer, travel, and mode commands to one surface owner. Its
   constructor binds no document listeners; mount installs the selection gesture
   lifecycle and field-focus tracking after all capabilities have been composed. */
import { anchoringIsReady, resolveAnchor, visualAt } from "../anchor-resolution.js";
import { sameAnchor } from "../anchor-coordinate.js";
import { shownBox, shownParts, shownRect } from "../geometry.js";
import {
  targetElement,
  targetParts,
  targetPlace,
  targetSegments,
} from "../resolved-target.js";
import { composerOpen, fab, fabBar, fabInput } from "./selection.js";

import { closeReference, referenceOpen } from "../keyboard/reference.js";

import { paintReactionStanding } from "../reaction-standing.js";
import { panel, threadsBox } from "../conversation/panel-elements.js";

import { inChrome, pageRange, pageText, pageWords } from "../passages.js";
import {
  leftThePage,
  pageSelection,
  selectionAnchor,
  snapSelection,
} from "./capture.js";
import { repaint } from "../repaint.js";
import { letGo, takesLetters } from "../focus.js";

import { pointerAt } from "../pointer.js";
import { anchorLabel } from "../conversation/messages.js";

import { reactionsAt } from "../conversation/model.js";
import { allThreads } from "../conversation/state.js";

import { readingRegionFor, shownRegionBounds } from "../reading-regions.js";

export const BANNER_CLEAR = 48;
let floatingUiModule = null;
const floatingUi = () => (floatingUiModule ??= import("/vendor/floating-ui.esm.js"));

export function createResponseSurface({
  panelCovers,
  markAt,
  scrollToElement,
  visualActionAnchor,
  hideComposer,
  openComposer,
  resetResponseOptions,
  responseOptionsAvailable,
  setResponseOptions,
  syncResponseOptions,
  designIsOn,
  designTarget,
  openOnDesign,
  isReactArmed,
  reactionContextContains,
  reactionTokens,
  setReact,
  banner,
  bottomChromeBoxes,
  less,
  closeVersionMenu,
  versionMenuIsOpen,
  openPageThread,
  isDrawing,
  refreshConversation,
}) {
  const hideReference = () => closeReference(false);
  const hasOtherResponses = (anchor) =>
    reactionTokens().length > 0 || Boolean(anchor?.quote && !designIsOn());

  // ---------- selection → comment ----------
  // Floating UI stays inside the document layout shell. Body already ends at a standing
  // right panel's edge through its margin, while the root scrollport owns the browser's
  // gutter. A covering sheet is the one strip body does not yield, so its width comes off
  // here.
  const rightEdge = (bounds = null) =>
    (bounds?.right ??
      (panelCovers()
        ? innerWidth - panel.offsetWidth
        : Math.min(innerWidth, document.body.getBoundingClientRect().right))) - 8;
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
    const left = (bounds?.left ?? 0) + 8;
    const right = rightEdge(bounds);
    const top = topEdge(bounds);
    const bottom = bottomEdge(left, Math.max(0, right - left), bounds);
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
  let fabPlacement = null;
  let fabInlineConnection = null;
  let fabPlacementInput = null;
  let fabMinimumWidth = null;
  let fabMinimumComposer = null;
  let fabPositionEpoch = 0;
  let fabPositionFrame = 0;
  let fabPositionCleanup = null;
  let fabPositionTarget = null;
  let fabPositionWaiters = [];

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

  const answerFabPosition = (positioned) => {
    const waiters = fabPositionWaiters;
    fabPositionWaiters = [];
    for (const resolve of waiters) resolve(positioned);
  };

  // One lifecycle for the one floating surface. Floating UI observes the target's scroll,
  // resize, layout shift, and the bar's own content size. Leaf's explicit layout signals
  // still call placeFab because a document revision can replace the semantic target rather
  // than merely move its old node.
  function stopFabPositioning({ reset = false } = {}) {
    fabPositionEpoch += 1;
    cancelAnimationFrame(fabPositionFrame);
    fabPositionFrame = 0;
    fabPositionCleanup?.();
    fabPositionCleanup = null;
    fabPositionTarget = null;
    if (!reset) return;
    answerFabPosition(false);
    fabPlacement = null;
    fabInlineConnection = null;
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
    fabBar.hasAttribute("data-lf-placement") && fabBar.style.visibility !== "hidden"
      ? Promise.resolve(true)
      : new Promise((resolve) => fabPositionWaiters.push(resolve));

  function scheduleFabPosition() {
    if (fabPositionFrame || !fabAnchor || !fabFloating) return;
    fabPositionFrame = requestAnimationFrame(() => {
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
  // wherever they are; a quote whose words the next version rewrote away does not, with one
  // exception — replacing source data must not close a draft about its prior revision, so an
  // outdated finding falls back to its section. Everything else stands on its element.
  //
  // One rule, because two callers ask it: placement, below, and the route back to a kept
  // draft, which must not offer a passage this version no longer holds.
  const standsIn = (anchor, found) => {
    if (!found) return false;
    if (anchor.quote) {
      if (targetSegments(found).length) return true;
      if (found.status !== "outdated") return false;
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
      // no longer available once the textarea took focus.
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
    const readingRegion = owner && readingRegionFor(owner);
    let regionBounds = readingRegion && shownRegionBounds(readingRegion);
    let boundary = floatBoundary(regionBounds);
    // Keep the response within its pane while that pane can hold the compact control.
    // During a responsive posture change a pane can briefly become narrower than the
    // editor even though the window is not. In that case the response is already a
    // viewport-plane overlay, so let the viewport carry it instead of withdrawing the
    // reader's draft as if its semantic anchor had disappeared.
    if (regionBounds && !fabFits(regionBounds)) {
      regionBounds = null;
      boundary = floatBoundary();
    }
    if (boundary.width <= 0 || boundary.height <= 0) return false;
    const clips = new Map();
    const parts = block ? shownParts(block) : [];
    const keepClear =
      union(parts.map((part) => shownRect(part, clips)).filter(Boolean)) ||
      // Scrolled clear of the viewport, the block keeps its column and loses its shown
      // rect, so the clipped reading has nothing left to say about where the field may
      // stand. Its unclipped bounds answer the question the clipped one was asked. The
      // fall through to the passage did the one thing the rule above forbids: beside a
      // short selection the field took the words after it, left the free margin, and
      // came to rest on the sentences the reader had scrolled to.
      union(parts.map((part) => shownBox(part))) ||
      target;
    // The chosen side is a pure reading of the minimum footprint against external
    // geometry. Cache its answer while those inputs are unchanged so content growth
    // cannot re-seat the response; invalidate it when either the reading boundary or the
    // reference moves enough to alter the available rails.
    const placementInput = [
      boundary.left,
      boundary.top,
      boundary.right,
      boundary.bottom,
      keepClear.left,
      keepClear.top,
      keepClear.right,
      keepClear.bottom,
    ];
    if (
      fabPlacementInput &&
      placementInput.some(
        (value, index) => Math.abs(value - fabPlacementInput[index]) > 0.5,
      )
    ) {
      fabPlacement = null;
      fabInlineConnection = null;
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
    if (fabPlacement === null) setWidth(boundary.width);
    setHeight(boundary.height);
    const minimumHeight = composerOpen
      ? Math.max(0, fabBar.offsetHeight - fabInput.offsetHeight) +
        parseFloat(getComputedStyle(fabInput).minHeight)
      : fabBar.offsetHeight;
    // The choices deliberately wrap inside the response surface, so their intrinsic
    // scroll width is not a fit requirement. Only the compact control's minimum is: a
    // covering panel may genuinely leave less than that, while an ordinary narrow page
    // still has a usable surface once the choices reflow below the field.
    if (boundary.height < minimumHeight || !fabFits(regionBounds)) return false;

    const reference = {
      contextElement: owner ?? document.documentElement,
      getBoundingClientRect: () => keepClear,
    };
    const overflow = { boundary: [], rootBoundary: boundary, padding: 0 };
    const epoch = ++fabPositionEpoch;
    const initial = fabPlacement === null;
    const stillCurrent = () => epoch === fabPositionEpoch && fabAnchor && fabFloating;
    void floatingUi()
      .then(({ autoUpdate, computePosition, flip, offset, shift, size }) => {
        if (!stillCurrent()) return null;
        watchFabPosition(owner ?? document.documentElement, autoUpdate);
        return computePosition(reference, fabBar, {
          placement: fabPlacement ?? "right-start",
          strategy: "fixed",
          middleware: [
            offset(({ placement, rects }) => {
              const beside = /^(left|right)/.test(placement);
              return {
                mainAxis: 6,
                // The paragraph chooses the horizontal lane; the selected line chooses
                // where in that lane the response starts. Above and below, preserve the
                // initial inline start as the field or its choices grow.
                crossAxis: beside
                  ? target.top - keepClear.top - 6
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
              apply({ availableWidth, availableHeight, placement }) {
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
                const laneHeight =
                  side === "top"
                    ? keepClear.top - boundary.top - 6
                    : side === "bottom"
                      ? boundary.bottom - keepClear.bottom - 6
                      : boundary.height;
                setHeight(
                  /^(left|right)$/.test(side)
                    ? boundary.height
                    : Math.max(0, Math.min(availableHeight, laneHeight)),
                );
              },
            }),
            initial &&
              flip({
                ...overflow,
                crossAxis: false,
                fallbackPlacements: ["left-start", "top-end", "bottom-end"],
                fallbackStrategy: "bestFit",
              }),
            shift({ ...overflow, mainAxis: true, crossAxis: true }),
          ],
        });
      })
      .then((position) => {
        if (!position) return;
        const { x, y, placement } = position;
        if (!stillCurrent()) return;
        fabPlacement ??= placement;
        if (!/^(left|right)/.test(placement))
          fabInlineConnection ??= x - keepClear.right;
        fabPlacementInput = placementInput;
        fabBar.dataset.lfPlacement = fabPlacement;
        fabBar.style.left = `${x}px`;
        fabBar.style.top = `${y}px`;
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
  function showFab(
    anchor,
    target = null,
    { returnFocus = "target", origin = null, place = true } = {},
  ) {
    const previous = fabAnchor;
    const previousOrigin = fabOrigin;
    const previousFloating = fabFloating;
    const leavingBar = !anchor && fabBar.contains(document.activeElement);
    const returnToPanel = leavingBar && panelCovers() && !fabFits();
    const returnTarget =
      leavingBar && previous && !previous.quote
        ? previousOrigin?.isConnected
          ? previousOrigin
          : previousOrigin
            ? visualActionAnchor(previous)
            : null
        : null;
    if (!anchor) fabInputTakingFocus = false;
    if (!anchor || (previous && !sameAnchor(previous, anchor))) resetResponseOptions();
    if (!anchor && composerOpen) hideComposer();
    if (
      !anchor ||
      !previous ||
      !sameAnchor(previous, anchor) ||
      !place ||
      !previousFloating
    )
      stopFabPositioning({ reset: true });
    fabAnchor = anchor;
    fabFloating = !fabAnchor || place;
    fabOrigin = fabAnchor && origin?.isConnected ? origin : null;
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
      // A docked margin control can name an item whose rendered box is currently off
      // screen. `e` still needs the durable anchor so it can extend that existing item;
      // in that route the floating bar is never painted and placement is deliberately
      // skipped. Every route that actually shows the bar keeps the geometry gate.
      if (place && !placeFab(target ?? anchorBox(fabAnchor))) {
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
    if (!sameAnchor(previous, fabAnchor)) refreshConversation();
    repaint(); // the c row names this anchor, so the line is one more rendering of it
    if (!fabAnchor && returnFocus !== "none") {
      if (returnToPanel) threadsBox.focus({ preventScroll: true });
      else if (leavingBar && returnFocus === "target" && returnTarget?.isConnected)
        returnTarget.focus({ preventScroll: true });
      else if (
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
    if (composerOpen) hideComposer();
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
  const fabReturnTo = () =>
    fabAnchor && !fabAnchor.quote
      ? fabOrigin?.isConnected
        ? fabOrigin
        : visualActionAnchor(fabAnchor)
      : null;

  // Where a comment about this item is written: the composer, on the item, which is what a
  // click through the ⌥ aim already opens. It reached for the widget's own conversation seat
  // first for a while, on the reasoning that a widget holding a box for its conversation
  // should not be given a second one. That was the wrong shape. `commentOnTarget` writes
  // `{section: item.id}`, which is exactly the anchor `renderConversations` collects into
  // that seat — so the words land in the same conversation by either route, and the seat was
  // buying a focus landing at the price of five separate questions: escaping an
  // author-written id into a selector, whether the box can take focus at all (a settled
  // group's seat is inside `hidden="until-found"` and silently swallowed the press), which
  // box when the seat holds several threads, what design mode files, and where the reader
  // was already standing. One route answers all five by not asking them.
  //
  // Putting a thing in front of the reader before a box is opened about it, for whichever
  // route reaches that box: the item `c` names, and the passage a kept draft comes back to.
  // Both open on a coordinate the reader may have scrolled away from, and a box measured
  // against a passage off screen stands beside nothing.
  //
  // Only where it is not already in front of the reader. Travelling every time moved
  // the page under someone who could see the thing perfectly well: Tab leaves an item at an
  // edge (`block: nearest`), so centring took the page a third of a viewport with nothing on
  // screen to explain it — on the route this press exists for, and where the ⌥ aim it is the
  // twin of moves nothing at all. The travel is for the standing that has gone stale, focus
  // outliving the scroll that put it there: a box about something off screen is a box about
  // nothing the reader can see.
  //
  // What the page shows of it, which is the reading the aim's own paint takes
  // (`refreshAim`) — this being its keyboard twin, the two decide "is this in front of the
  // reader" the same way or they are not twins. An unclipped box alone is the box the item
  // would have: an item scrolled out of a board's sideways scroller still reports one
  // inside the window, so a gate reading that called it showing and opened the box on
  // something off screen, which the unconditional travel it replaced never did. Any part
  // showing is enough, which is also what keeps a box taller than the window from jumping
  // to its top under a reader halfway down it.
  //
  // A collapsed ancestor zeroes its descendants' boxes, so a thing inside a shut
  // disclosure is never showing and takes the travel, `reveal` with it. Standing on the
  // summary itself is the one motion this drops: the disclosure stays shut and the box
  // opens on it where it is, rather than springing it open and reflowing the page under
  // the reader who was looking at it.
  //
  // Instant, and before the box is measured. Placing reads the item's box, so that has to
  // be the box the item keeps; and opening focuses the textarea, whose scroll-into-view
  // cancels a glide already under way — which is what left the item flush against an edge
  // rather than framed, and is not `openComposer`'s to give up, three other presses opening
  // that box against a passage they have not moved.
  function bringForward(item) {
    if (!item) return;
    const seen = shownRect(item, new Map());
    if (!seen || seen.bottom <= BANNER_CLEAR) scrollToElement(item, "instant");
  }

  function commentOnItem(item) {
    bringForward(item);
    commentOnTarget({ anchor: { section: item.id }, element: item });
  }

  // Every explicit target gesture ends here. The gesture has already resolved its stable
  // authored anchor; this command owns the one transition from that target into Comment.
  // Focusing the field drops any older browser selection, and an unsent draft follows the
  // deliberate move. A visual proxy supplies its origin so Escape can return to it.
  function commentOnTarget({ anchor }, { origin = null } = {}) {
    clearTimeout(selectionUpdate);
    selectionUpdate = null;
    targetActivation = true;
    const selection = getSelection();
    if (selection?.rangeCount) selection.removeAllRanges();
    openComment(anchor, "", { carry: true });
    if (origin) showFab(anchor, null, { origin });
    setTimeout(() => {
      targetActivation = false;
    });
  }
  // Focusing text entry collapses a native page selection. Hold that browser-authored
  // selectionchange out of updateFab: the durable anchor is already captured, and letting
  // the collapse re-read it as no selection dismisses the field the reader just entered.
  function focusFabComment() {
    if (!fabAnchor) return;
    clearTimeout(selectionUpdate);
    selectionUpdate = null;
    fabInputTakingFocus = true;
    if (!composerOpen) {
      openComment(structuredClone(fabAnchor), "");
      return;
    }
    const anchor = structuredClone(fabAnchor);
    void fabPositioned().then((positioned) => {
      if (positioned && composerOpen && sameAnchor(anchor, fabAnchor))
        fabInput.focus({ preventScroll: true });
    });
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

  function updateFab() {
    if (!anchoringIsReady()) {
      showFab(null);
      return;
    }
    const sel = pageSelection();
    const anchor = sel ? selectionAnchor(sel) : null;
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
  // the capture reads the one the reader is looking at — and only for the primary
  // button, because a right button's release precedes its context menu, and growing the
  // selection there rewrites what Copy was aimed at.
  //
  // A queued step belongs to the gesture that queued it, and the next press may begin
  // before it runs. Then the selection it would act on is not the one it was queued
  // for: it is the drag under way, and `snapSelection` rewrites that drag mid-gesture.
  // Chromium does not resume extending a selection it has been handed through
  // `setBaseAndExtent`, so the pointer's remaining travel is lost and a sweep from
  // "paragraph" to "carrying" ends up captured as "paragraph" — the reader's own hand
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
  const beginFabFocus = () => {
    fabInputTakingFocus = true;
  };
  function openComment(anchor, text, options = {}) {
    return openComposer(anchor, text, options);
  }
  function fabHoldsCapturedPassage() {
    return (
      fabInputTakingFocus ||
      fabBar.contains(document.activeElement) ||
      reactionContextContains(document.activeElement)
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
  // control the reader is standing on, and until now nothing repainted the line inside a
  // press — the word only became true when the frame the press itself scheduled happened
  // to land after the drag had moved, and stayed a lie for a whole heartbeat when it
  // landed before. Only the crossing is painted: a drag growing a selection that already
  // stands says the same word, and repainting the chrome on every move of a drag would
  // put a whole shared repaint inside every frame of one.
  let selectionStood = false;
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
    if (isDrawing()) return;
    // A mouse pointer is followed by the compatibility mouseup below, which performs the
    // sentence snap before opening the field. Opening from pointerup first would focus the
    // textarea and collapse the still-unsnapped Selection before mouseup can finish it.
    // Touch/pen and cancellation owe us no compatibility mouse event, so they keep this
    // direct route.
    if (
      primaryPointerPressed &&
      ev.type === "pointerup" &&
      ev.pointerType === "mouse"
    ) {
      // Keep selectionchange in the in-progress branch until compatibility mouseup.
      setTimeout(() => {
        actionPress = false;
      });
      return;
    }
    if (primaryPointerPressed) scheduleSelectionUpdate();
    primaryPointerPressed = false;
    pointerSelecting = false;
    selectionGestureClaimed = false;
    setTimeout(() => {
      actionPress = false;
    });
  };

  // Touch handles and browser selection commands do not owe the page a mouseup or keyup.
  // During a pointer drag, the completed gesture below remains the one that snaps and
  // places the passage; presses on the action surface must not retract their own target.

  // Selections made from the keyboard (shift-arrows, ⌘A) deserve the same response bar. Typing in
  // a box never does, whatever is selected elsewhere.

  // Floating chrome getting out of the way of a press somewhere else, which is a fact about
  // the press rather than about who receives it: the aim takes a press away from the page
  // (see claimPress) and must not take this with it, or the keyboard reference stays up over
  // the composer that press just opened. Hence one function, called from both.
  // The two side panels are absent from it on purpose. A float answers the press in front
  // of it and stands down behind it; the thread panel and the leaves tray are
  // workspaces the reader stood up, kept through a reload (PANEL_KEY, TRAY_KEY) and so
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
    if (referenceOpen() && !target.closest?.(".lf-shortcut-reference")) hideReference();
    if (!target.closest?.(".lf-shortcut-reference, .lf-shortcut-bar")) less();
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
    document.addEventListener(
      "pointerdown",
      (ev) => {
        if (isDrawing()) return;
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
        selectionStood = Boolean(pageSelection());
        const selection = pointerSelecting ? pageSelection() : null;
        if (selection && pageRange(selection).intersectsNode(ev.target))
          rememberPointerSelection();
        actionPress = Boolean(ev.target.closest?.(".lf-react-surface, .lf-composer"));
      },
      true,
    );
    document.addEventListener("pointermove", (ev) => {
      if (isDrawing()) return;
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
      if (
        actionPress ||
        targetActivation ||
        fabHoldsCapturedPassage() ||
        takesLetters(document.activeElement)
      )
        return;
      scheduleSelectionUpdate();
    });
    document.addEventListener("mouseup", (ev) => {
      if (isDrawing()) return;
      primaryPointerPressed = false;
      pointerSelecting = false;
      const gestureClaimed = selectionGestureClaimed;
      selectionGestureClaimed = false;
      if (gestureClaimed) {
        selectionRangeDuringPress = null;
        scheduleSelectionUpdate();
        return;
      }
      if (actionPress) return;
      if (!pageWords(ev.target) && !pageSelection()) return;
      const selection = pageSelection();
      const selected = selection ? selectionAnchor(selection) : null;
      // A drag whose far end left the document is the same release as one that ended holding
      // nothing: what the reader meant is what the drag had before the pointer crossed out,
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
          // no words to put back. The browser's own selection stays where it is — the reader
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
      if (!isDrawing()) standDown(ev.composedPath()[0]);
    });
    document.addEventListener("click", (ev) => {
      if (isDrawing()) return;
      if (!pageWords(ev.target)) return;
      // A press design mode did not take at the press is a press on prose: a drag that
      // selected words has the 💬 (updateFab, on the mouseup) and is not a click on the
      // block; a plain click comments on the block it landed in.
      if (designIsOn()) {
        if (pageSelection()) return;
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
      if (threadId) return openPageThread(threadId);
    });
    wireFabInput();
  }
  return {
    fabPositioned,
    beginFabFocus,
    anchorStands,
    showFab,
    dismissFab,
    refreshFab,
    anchorTargetAt,
    fabTargetAt,
    fabReturnTo,
    bringForward,
    commentOnItem,
    commentOnTarget,
    focusFabComment,
    fabOptionsAvailable,
    showFabOptions,
    hasPageSelectionTarget,
    updateFab,
    standDown,
    fabAnchorAt,
    mount,
  };
}
