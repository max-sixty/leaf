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
import { shownRegionBounds } from "/runtime/reading-regions.js";
import { floatingPlacement, floatingUi } from "../floating.js";
import {
  cardMinimum,
  commentAttachment,
  commentBoundary,
  commentPlacement,
  makeRoom,
  reachableRoom,
} from "../comment-placement.js";
import { pointBand } from "/runtime/pointed-place.js";
import { keeps, layoutPx } from "/runtime/keeps.js";

export function createFloatingResponsePlacement({
  nodes: { bar: fabBar, input: fabInput },
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
  const fabFrameAt = () =>
    response.open && response.floating && !panelIsOpen()
      ? {
          box: fabBar.getBoundingClientRect().toJSON(),
          width: parseFloat(getComputedStyle(fabBar).width),
          placement: fabPlacement.capture(),
        }
      : null;
  // Used grid tracks exclude transformed descendant paint. A directional fit
  // reserves the future card's footer; withholding requires only the current
  // controls to fit, so they may borrow that transparent footer when space is short.
  const nativeFrameSize = () => {
    const style = getComputedStyle(fabBar);
    const rows = style.gridTemplateRows.split(" ").map(parseFloat);
    const rowEnd =
      rows.reduce((height, row) => height + row, 0) +
      parseFloat(style.rowGap) * (rows.length - 1) +
      parseFloat(style.paddingTop);
    return {
      rowEnd: Math.round(rowEnd),
      reservedHeight: Math.round(rowEnd + parseFloat(style.paddingBottom)),
    };
  };
  const fabFits = (bounds = null) => {
    const boundary = floatBoundary(bounds);
    return (
      boundary.width > 0 &&
      Math.ceil(boundary.width) >= Math.ceil(fabBar.getBoundingClientRect().width)
    );
  };

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
    for (const property of ["--lf-float-w", "--lf-float-h"])
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
    const place = commentAttachment({
      target: owner,
      point: response.anchor.quote ? null : response.pointIn(owner),
      passage: geometry,
    });
    const boundary =
      !unanchored && place.region
        ? floatBoundary(shownRegionBounds(place.region))
        : windowBoundary;
    if (boundary.width <= 0 || boundary.height <= 0) return false;
    const roomRect = unanchored ? null : place.extent;
    const keepClear = unanchored ? null : place.clear;
    const scroller = place.scroller;
    const verticalRoom = (side) =>
      reachableRoom(side, roomRect, boundary, scroller).reachable;
    // Width before coordinates: the side is chosen from the card's minimum, then the size
    // pass gives CSS that side's actual inline room. If a later resize makes the chosen
    // side narrower than the bar's minimum, use the whole boundary and let shift overlap
    // the target instead of silently moving the draft.
    const setWidth = (available, scale) => {
      // Leaving the passage does not give the user's editor a new measure.
      const room = unanchoredWidth
        ? Math.min(available, unanchoredWidth / scale)
        : available;
      fabBar.style.setProperty("--lf-float-w", layoutPx(Math.max(0, room)));
      if (Math.ceil(fabBar.offsetWidth) > Math.ceil(room))
        fabBar.style.setProperty(
          "--lf-float-w",
          layoutPx(Math.max(0, boundary.width / scale)),
        );
    };
    // The whole frame receives the room on its side. Native tracks reserve the
    // furniture and give the editor what remains; a side too small for the minimum
    // row uses the whole reading boundary, where shift can keep the surface visible.
    const vertical = (side) => /^(top|bottom)$/.test(side);
    const setHeight = (side, scale) => {
      if (!response.open) return;
      const room = !unanchored && vertical(side) ? verticalRoom(side) : boundary.height;
      const height =
        nativeFrameSize().reservedHeight > Math.round(room / scale)
          ? boundary.height
          : room;
      fabBar.style.setProperty("--lf-float-h", layoutPx(Math.max(0, height / scale)));
    };
    const { fresh } = fabPlacement.choose({
      clear: keepClear,
      extent: roomRect,
      boundary,
      minimumWidth: cardMinimum(),
      scroller,
      coarse: coarsePointer.matches,
    });
    if (fresh) fabContentHeight = null;

    const epoch = fabPosition.begin();
    const stillCurrent = () =>
      fabPosition.current(epoch) && response.anchor && response.floating;
    void floatingUi()
      .then((ui) => {
        if (!stillCurrent()) return null;
        watchFabPosition(owner ?? document.documentElement, ui.autoUpdate);
        const { reference, placement, middleware, plane } = fabPlacement.options(ui, {
          clear: keepClear,
          row: place.row,
          column: place.column,
          margin: !unanchored && place.margin,
          boundary,
          minimumWidth: cardMinimum(),
          fit({ side: placed, width, scale }) {
            if (!stillCurrent()) return;
            setWidth(width, scale.x);
            setHeight(placed, scale.y);
            const frame = fabBar.getBoundingClientRect();
            if (
              Math.ceil(frame.width) > Math.ceil(boundary.width) ||
              Math.ceil(frame.height) > Math.ceil(boundary.height) ||
              (response.open && nativeFrameSize().rowEnd > fabBar.clientHeight)
            ) {
              withholdFab();
              return;
            }
            // Wrapping at the fitted width determines the height that spends scroll
            // travel. Opening or re-seating preserves the reading position; later
            // intrinsic growth may use the reading region's remaining travel before
            // the field scrolls. Content, rather than placed height, keeps clipping
            // during a wheel gesture from spending that travel again.
            const height = fabBar.getBoundingClientRect().height;
            const contentHeight = response.open
              ? parseFloat(getComputedStyle(fabBar).height) +
                Math.max(0, fabInput.scrollHeight - fabInput.clientHeight)
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
    stopFabPositioning({ reset: false });
    if (fabWithheld) return;
    fabWithheld = true;
    const held = holdFocus(fabBar);
    const toPanel = held && panelIsOpen() && !fabFits();
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
