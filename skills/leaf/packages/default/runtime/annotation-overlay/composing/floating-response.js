/* Floating presentation of the one native response bar.

   Composition owns the gesture's anchor, origin, pointed row and native editor seat.
   This selected presentation reads that live response and owns only its physical
   placement: card sizing, collision geometry, off-flow reveals and withholding when
   the usable window has no room. No second anchor or editor is captured here.
   While its passage is offscreen, the editor keeps its attached width as a cap so
   moving into the window does not reflow its controls; a narrower window can shrink it.
   An inline seat suspends this placement; restoring the default home resumes it. */
import { cancelRender, nextRender } from "/runtime/rendering.js";
import { resolveAnchor } from "/runtime/anchor-resolution.js";
import { sameAnchor } from "/runtime/anchor-coordinate.js";
import { declareOffFlowSurface } from "/runtime/off-flow.js";
import {
  clippedContents,
  clippedRect,
  pagePlaneRect,
  shownBox,
  shownExtent,
  shownParts,
  shownRect,
  skipped,
} from "/runtime/geometry.js";
import {
  passageGeometry,
  rangeGeometry,
  targetElement,
  targetParts,
  targetSegments,
} from "/runtime/resolved-target.js";
import { pageRange, pageText } from "/runtime/passages.js";
import { pageSelection, selectionAnchor } from "/runtime/composing/capture.js";
import { holdFocus } from "/runtime/focus.js";
import { coarsePointer } from "/runtime/pointer.js";
import { overlaps, union } from "/runtime/rect.js";
import {
  containingReadingRegionFor,
  effectiveScroller,
  shownRegionBounds,
} from "/runtime/reading-regions.js";
import { floatingPlacement, floatingUi, heldByWindow } from "../floating.js";
import {
  cardMinimum,
  cardMeasure,
  commentBoundary,
  commentPlacement,
  makeRoom,
  reachableRoom,
} from "../comment-placement.js";
import { marginSpot } from "../margin-layout.js";
import { pointBand } from "/runtime/pointed-place.js";
import { keeps } from "/runtime/keeps.js";

export function createFloatingResponsePlacement({
  nodes: { bar: fabBar, input: fabInput, composer, options: fabOptions },
  response,
  panel,
  panelIsOpen,
  threadsBox,
  positioned,
  dismiss,
  standsIn,
  scrollToElement,
}) {
  const floatBoundary = (region = null) =>
    commentBoundary({ region, right: panel.open ? panel.offsetLeft : Infinity });
  // The side the bar holds and its inline start, by the rule the thread card it becomes
  // stands by too (comment-placement.js).
  const fabPlacement = commentPlacement();
  let fabPositionFrame = 0;
  // Whether the bar the user has is waiting out of view for room to stand
  // (withholdFab), and where it takes them back to when it stands again.
  let fabWithheld = false;
  let fabWithheldFocus = null;
  const fabPosition = floatingPlacement({
    floating: fabBar,
    update: () => scheduleFabPosition(),
  });
  let fabContentHeight = null;
  let unanchoredWidth = null;
  // The compact row's occupied space beside the field, in CSS pixels. The frame's
  // minimum may leave spare space, so subtracting the field from the frame mistakes
  // that space for controls and makes successive fits widen the field in steps.
  // Choices wrap on their own row; media shares the compact row and its footprint.
  const fabControlsWidth = () => {
    const style = getComputedStyle(fabBar);
    const items = [...fabBar.children]
      .flatMap((node) => (node === composer ? [...node.children] : [node]))
      .filter((node) => node !== fabOptions && node.getClientRects().length);
    return (
      parseFloat(style.paddingInlineStart) +
      parseFloat(style.paddingInlineEnd) +
      parseFloat(style.columnGap) * Math.max(0, items.length - 1) +
      items.reduce(
        (width, node) => width + (node.contains(fabInput) ? 0 : node.offsetWidth),
        0,
      )
    );
  };
  const fabFrameAt = () =>
    response.open && response.floating && !panelIsOpen()
      ? {
          box: fabBar.getBoundingClientRect().toJSON(),
          width: parseFloat(getComputedStyle(fabBar).width),
          placement: fabPlacement.capture(),
        }
      : null;
  const minimumFabWidth = () =>
    response.open
      ? parseFloat(
          getComputedStyle(fabInput).getPropertyValue("--lf-response-min-width"),
        ) + fabControlsWidth()
      : fabBar.scrollWidth;
  const fabFits = (bounds = null) => {
    const boundary = floatBoundary(bounds);
    return (
      boundary.width > 0 && Math.ceil(boundary.width) >= Math.ceil(minimumFabWidth())
    );
  };
  const minimumFabHeight = () =>
    response.open
      ? Math.max(0, fabBar.offsetHeight - fabInput.offsetHeight) +
        parseFloat(getComputedStyle(fabInput).minHeight)
      : fabBar.offsetHeight;

  // One lifecycle for the one floating surface. Floating UI observes the target's scroll,
  // resize, layout shift, and the bar's own content size. Leaf's explicit layout signals
  // still call placeFab because a document revision can replace the semantic target rather
  // than merely move its old node.
  // Native-seat readiness belongs to composition; stopping this presenter retires
  // only its observers and geometry, never a handoff waiting for an inline seat.
  function stopFabPositioning({ reset = false } = {}) {
    fabPosition.stop();
    cancelRender(fabPositionFrame);
    fabPositionFrame = 0;
    fabContentHeight = null;
    if (!reset) return;
    unanchoredWidth = null;
    fabPlacement.forget();
    fabBar.removeAttribute("data-lf-placement");
    for (const property of ["--lf-float-w", "--lf-response-room", "--lf-float-h"])
      fabBar.style.removeProperty(property);
    fabBar.style.visibility = "hidden";
  }

  function scheduleFabPosition() {
    if (fabPositionFrame || !response.anchor || !response.floating) return;
    fabPositionFrame = nextRender(() => {
      fabPositionFrame = 0;
      placeFab();
    });
  }

  function watchFabPosition(target, autoUpdate) {
    const reference = {
      contextElement: response.pointIn(target) ?? target,
      getBoundingClientRect: () =>
        anchorGeometry(response.anchor)?.box ?? target.getBoundingClientRect(),
    };
    fabPosition.watch(target, reference, autoUpdate);
  }
  // A visual's durable anchor is also the geometry authority. Resolve it again after a
  // reflow instead of remembering where the pointer happened to land; what a pointing
  // gesture keeps is the row it landed on, an element whose box is read afresh here, and
  // the bar stands level with it (pointed-place.js).
  function anchorGeometry(anchor) {
    if (anchor?.quote) {
      const selection = pageSelection();
      const current = selection ? selectionAnchor(selection) : null;
      if (current && sameAnchor(anchor, current))
        return rangeGeometry(pageRange(selection));
      // Entering the compact field deliberately collapses the browser selection after
      // its durable passage has been captured. Resolve that passage again so layout can
      // keep the field beside it; an ordinary selection collapse still returns null and
      // lets updateFab dismiss the response surface.
      // The reactions palette temporarily owns focus and may itself be re-seated during
      // a responsive layout change. The open composer is the durable proof that this
      // captured passage still belongs to the response transaction; native selection is
      // no longer available once the field took focus.
      if (!response.open && !response.captured) return null;
    }
    const found = anchor ? resolveAnchor(anchor, pageText()) : null;
    if (!anchor || !standsIn(anchor, found)) return null;
    const words = anchor.quote ? passageGeometry(found) : null;
    if (words) return words;
    // In the page's plane, as the quoted words above are: the page's own boxes cut it (a
    // pane or a board scrolled past it), and the window does not, so an item the user
    // scrolls off screen still has an attachment box. `placeFab` reads whether that
    // attachment is visible before choosing page or window placement.
    const clips = new Map();
    const box = union(
      targetParts(found)
        .map((part) => pagePlaneRect(shownBox(part), part, clips))
        .filter(Boolean),
    );
    // A pointed row is small enough to stand by whole. An element has no passage
    // fragment, so it supplies only the box the shared placement policy reads.
    const point = box && response.pointIn(targetElement(found));
    const elementBox = point
      ? pointBand(union(targetParts(found).map((part) => shownBox(part))), point)
      : box;
    return elementBox ? { box: elementBox, attachment: null } : null;
  }
  // The passage remains the exact anchor, but its resolved place is not spare space: a
  // short selection cannot lend the words around it to the response field. Keep the bar
  // beside that whole place, or above/below it when the rail is too narrow.
  function placeFab() {
    if (!response.anchor) return false;
    const geometry = anchorGeometry(response.anchor);
    const target = geometry?.box;
    const attachment = geometry?.attachment;
    const owner = response.target;
    // An open editor stays in front of its writer. Its subject still owns the draft
    // when a resize, disclosure or scroll removes the subject's visible box; only its
    // placement becomes unanchored, in the window, until that box returns.
    const clips = new Map();
    const visible =
      target &&
      owner &&
      !skipped(owner) &&
      (response.anchor.quote
        ? clippedContents(target, owner, clips)
        : clippedRect(target, owner, clips));
    const windowBoundary = floatBoundary();
    const unanchored = Boolean(
      response.open && owner && !(visible && overlaps(visible, windowBoundary)),
    );
    if (unanchored) {
      unanchoredWidth ??= fabBar.getBoundingClientRect().width || null;
    } else {
      unanchoredWidth = null;
    }
    if (!target && !unanchored) return false;
    const block = response.anchor.quote && owner;
    const readingRegion = !unanchored && owner && containingReadingRegionFor(owner);
    const boundary = readingRegion
      ? floatBoundary(shownRegionBounds(readingRegion))
      : windowBoundary;
    if (boundary.width <= 0 || boundary.height <= 0) return false;
    const point = !response.anchor.quote && owner && response.pointIn(owner);
    const holder = block || (!point && owner);
    const parts = holder ? shownParts(holder) : [];
    // Room is a reading of the whole block or element, as the card reads it; clipping
    // changes as the user scrolls. Attachment uses the visible part so the field still
    // meets what is on screen. A pointed row is read whole already.
    const roomRect = unanchored ? null : (holder && shownExtent(holder)) || target;
    const keepClear = unanchored
      ? null
      : union(parts.map((part) => shownRect(part, clips)).filter(Boolean)) ||
        (block ? roomRect : target);
    const scroller = effectiveScroller(readingRegion ?? owner);
    const verticalRoom = (side) =>
      reachableRoom(side, roomRect, boundary, scroller).reachable;
    // Width before coordinates: the side is chosen from the card's minimum, then the size
    // pass gives CSS that side's actual inline room. If a later resize makes the chosen
    // side narrower than the bar's minimum, use the whole boundary and let shift overlap
    // the target instead of silently moving the draft.
    const setWidth = (available) => {
      const minimum = minimumFabWidth();
      // Leaving the passage does not give the user's editor a new measure.
      const room = unanchoredWidth ? Math.min(available, unanchoredWidth) : available;
      const width =
        Math.ceil(room) >= Math.ceil(minimum) ? room : Math.max(0, boundary.width);
      fabBar.style.setProperty("--lf-float-w", `${width}px`);
      if (!response.open) return;
      fabBar.style.setProperty(
        "--lf-response-room",
        `${Math.max(0, Math.min(width, cardMeasure()) - fabControlsWidth())}px`,
      );
    };
    const setHeight = (available) => {
      if (!response.open) return;
      const extra = Math.max(0, fabBar.offsetHeight - fabInput.offsetHeight);
      fabBar.style.setProperty("--lf-float-h", `${Math.max(0, available - extra)}px`);
    };
    // A side under or over is chosen from the room the page can make there, and the
    // travel below makes it, so the bar is given that room to grow into; beside, or where
    // that side cannot hold the bar, the whole boundary.
    const vertical = (side) => /^(top|bottom)$/.test(side);
    const heightFor = (side) => {
      const room = !unanchored && vertical(side) ? verticalRoom(side) : 0;
      return room >= minimumFabHeight() ? room : boundary.height;
    };
    const { side, fresh } = fabPlacement.choose({
      clear: keepClear,
      extent: roomRect,
      boundary,
      minimumWidth: cardMinimum(),
      scroller,
      coarse: coarsePointer.matches,
    });
    if (fresh) {
      fabContentHeight = null;
      setWidth(boundary.width);
    }
    setHeight(heightFor(side));
    // The choices deliberately wrap inside the response surface, so their intrinsic
    // scroll width is not a fit requirement. Only the compact control's minimum is: a
    // covering panel may genuinely leave less than that, while an ordinary narrow page
    // still has a usable surface once the choices reflow below the field.
    if (
      boundary.height < minimumFabHeight() ||
      Math.ceil(boundary.width) < Math.ceil(minimumFabWidth())
    )
      return false;

    const epoch = fabPosition.begin();
    const stillCurrent = () =>
      fabPosition.current(epoch) && response.anchor && response.floating;
    void floatingUi()
      .then((ui) => {
        if (!stillCurrent()) return null;
        watchFabPosition(owner ?? document.documentElement, ui.autoUpdate);
        const { reference, placement, middleware, heldIn } = fabPlacement.options(ui, {
          clear: keepClear,
          row: (attachment ?? target)?.top,
          column: attachment?.left ?? null,
          margin: !unanchored && owner && marginSpot(owner, response.pointIn(owner)),
          boundary,
          minimumWidth: cardMinimum(),
          fit({ side: placed, width, scale }) {
            if (!stillCurrent()) return;
            setWidth(width);
            setHeight(heightFor(placed) / scale.y);
            // Wrapping at the fitted width determines the height that spends scroll
            // travel. Opening or re-seating preserves the reading position; later
            // intrinsic growth may use the reading region's remaining travel before
            // the field scrolls. Content, rather than placed height, keeps clipping
            // during a wheel gesture from spending that travel again.
            const height = fabBar.offsetHeight;
            const contentHeight = response.open
              ? fabInput.scrollHeight + Math.max(0, height - fabInput.offsetHeight)
              : fabBar.scrollHeight;
            const contentChanged =
              fabContentHeight !== null &&
              Math.abs(contentHeight - fabContentHeight) > 0.5;
            fabContentHeight = contentHeight;
            if (
              !unanchored &&
              vertical(placed) &&
              contentChanged &&
              makeRoom(placed, keepClear, roomRect, height, boundary, scroller)
            ) {
              fabPlacement.scrolled();
              // The scroll changed the attachment geometry. A fresh placement
              // supersedes this answer before its old coordinates can stand.
              placeFab();
            }
          },
        });
        // Held at a reading region's edge, the bar goes where the page takes the region.
        const plane = (answer) =>
          unanchored ||
          (heldIn(answer) && heldByWindow(answer.y, answer.y + fabBar.offsetHeight, 8))
            ? "window"
            : "page";
        return fabPosition.position(
          ui.computePosition,
          {
            contextElement: owner ?? document.documentElement,
            getBoundingClientRect: () => reference,
          },
          { placement, middleware },
          plane,
          owner ?? document.documentElement,
        );
      })
      .then((position) => {
        if (!position || !stillCurrent()) return;
        fabPlacement.landed(position);
        keeps(fabBar, "data-lf-placement", position.placement);
        fabPosition.stand(position);
        fabBar.style.removeProperty("visibility");
        positioned(true);
        stoodAgain();
        return true;
      })
      .catch((error) => {
        if (!stillCurrent()) return;
        dismiss();
        throw error;
      });
    return true;
  }
  // Withholds the bar while the usable window cannot contain it, keeping its draft,
  // anchor, side, and caret. Hiding a focused bar drops focus to nowhere, so it keeps
  // the user's place (`holdFocus`) and returns focus when room comes back, unless they
  // focused something else meanwhile. Where a covering panel took the room, its
  // Threads list takes focus. While the bar waits, its composer scope and selection
  // rung stand down; `c` brings it back.
  function withholdFab() {
    if (fabWithheld) return;
    fabWithheld = true;
    const held = holdFocus(fabBar);
    const toPanel = held && panelIsOpen() && !fabFits();
    stopFabPositioning({ reset: false });
    fabBar.style.visibility = "hidden";
    if (toPanel) threadsBox.focus({ preventScroll: true });
    else fabWithheldFocus = held;
  }
  // The bar is in view again, by whichever placement put it there.
  function stoodAgain() {
    if (!fabWithheld) return;
    fabWithheld = false;
    const returning = fabWithheldFocus;
    fabWithheldFocus = null;
    returning?.();
  }
  function mount() {
    // Floating, the box is carried away with its passage and comes back with it, by the
    // passage's first line, which a block taller than the window would not bring back;
    // inline, it is in flow and the browser's own reveals reach it.
    declareOffFlowSurface(fabBar, {
      floats: () => Boolean(response.anchor && response.floating),
      away: () => fabWithheld,
      bringBack: (behavior) => {
        const found = resolveAnchor(response.anchor, pageText());
        const start = response.anchor.quote && found && targetSegments(found)[0]?.node;
        const target = response.target;
        const line = start?.parentElement ?? response.pointIn(target) ?? target;
        if (line) scrollToElement(line, behavior, "nearest");
      },
    });
  }
  return {
    place: placeFab,
    stop: stopFabPositioning,
    frame: fabFrameAt,
    fits: fabFits,
    withhold: withholdFab,
    stoodAgain,
    withheld: () => fabWithheld,
    release: () => {
      fabWithheld = false;
      fabWithheldFocus = null;
    },
    ready: () =>
      fabBar.hasAttribute("data-lf-placement") && fabBar.style.visibility !== "hidden",
    mount,
  };
}
