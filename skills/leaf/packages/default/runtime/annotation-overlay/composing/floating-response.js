/* Floating presentation of the one native response bar.

   Composition owns its durable target and native editor. This owner chooses its initial
   side, measure and CSS attachment. While editing, the browser carries that attachment
   through every ancestor scroll; generic repaint and scroll publications do not solve
   another position. Target or field resize, viewport resize and declared layout
   changes invalidate the attachment. Replacing its target or native seat retires it. The compact response strip retains ordinary
   collision placement and scroll observation.

   An editing field follows its passage out of view. The existing Resume writing route
   reveals that same field; no window seat or duplicate input stands in for it. */
import { cancelRender, nextRender } from "/runtime/rendering.js";
import { resolveAnchor } from "/runtime/anchor-resolution.js";
import { sameAnchor } from "/runtime/anchor-coordinate.js";
import { declareOffFlowSurface } from "/runtime/off-flow.js";
import { shownBox } from "/runtime/geometry.js";
import {
  passageGeometry,
  rangeGeometry,
  targetElement,
  targetParts,
  targetRange,
} from "/runtime/resolved-target.js";
import { pageRange, pageText } from "/runtime/passages.js";
import { pageSelection, selectionAnchor } from "/runtime/composing/capture.js";
import { holdFocus } from "/runtime/focus.js";
import { coarsePointer } from "/runtime/pointer.js";
import { LAYOUT } from "/runtime/widget-elements.js";
import { under } from "/runtime/shadow.js";
import { union } from "/runtime/rect.js";
import { floatingPlacement, floatingUi } from "../floating.js";
import {
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
  scrollToRange,
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
  let nativeAttachment = false;
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
  const fabFits = () => {
    const boundary = floatBoundary();
    return (
      boundary.width > 0 &&
      Math.ceil(boundary.width) >= Math.ceil(fabBar.getBoundingClientRect().width)
    );
  };

  // The editing observer reports size and authored target style changes: CSS anchors
  // own scroll following, while a target transformed without resizing must let
  // the shared placement rule choose its side again. Layout-shift observation
  // also hears scroll, which would re-place the native attachment on wheel frames.
  // A compact strip still observes scroll and layout shifts. Explicit publication may
  // replace a target or editor seat; composition stops this owner for that handoff.
  // Native-seat readiness belongs to composition; stopping this presenter retires
  // only its observers and geometry, never a handoff waiting for an inline seat.
  function stopFabPositioning({ reset = false } = {}) {
    nativeAttachment = false;
    fabBar.style.removeProperty("height");
    fabPosition.stop();
    cancelRender(fabPositionFrame);
    fabPositionFrame = 0;
    fabContentHeight = null;
    if (!reset) return;
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

  let observationModes = null;
  function watchFabPosition(target, autoUpdate) {
    const reference = {
      contextElement: response.pointIn(target) ?? target,
      getBoundingClientRect: () =>
        anchorGeometry(response.anchor)?.box ?? target.getBoundingClientRect(),
    };
    if (!observationModes) {
      observationModes = {
        editing: (reference, floating, update) => {
          const invalidate = () => {
            nativeAttachment = false;
            update();
          };
          const stopSize = autoUpdate(reference, floating, invalidate, {
            ancestorScroll: !fabPosition.nativeAvailable(),
            layoutShift: false,
          });
          const style = document.createElement("span").style;
          const authoredStyle = (css) => {
            style.cssText = css ?? "";
            style.removeProperty("anchor-name");
            return style.cssText;
          };
          const changed = new MutationObserver((records) => {
            // The native attachment writes anchor-name on its own target. That
            // change does not move the target and must not start another solve.
            if (
              records.some(
                (record) =>
                  authoredStyle(record.oldValue) !==
                  authoredStyle(record.target.getAttribute("style")),
              )
            )
              invalidate();
          });
          changed.observe(reference.contextElement, {
            attributes: true,
            attributeOldValue: true,
            attributeFilter: ["style"],
          });
          return () => {
            changed.disconnect();
            stopSize();
          };
        },
        compact: autoUpdate,
      };
    }
    const observes = observationModes;
    fabPosition.watch(
      target,
      reference,
      response.open ? observes.editing : observes.compact,
    );
  }
  // A visual's durable anchor is also the geometry authority. Resolve it again after a
  // reflow instead of remembering where the pointer happened to land; what a pointing
  // gesture keeps is the row it landed on, an element whose box is read afresh here, and
  // the bar stands level with it (pointed-place.js).
  function anchorGeometry(anchor) {
    if (anchor?.quote) {
      const selection = pageSelection();
      const current = selection ? selectionAnchor(selection) : null;
      if (current && sameAnchor(anchor, current)) {
        const range = pageRange(selection);
        return rangeGeometry(range);
      }
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
    // The full authored box supplies the attachment even when an ancestor clips it.
    // Its visibility is presentation, and cannot make Resume writing reject the target.
    const box = union(
      targetParts(found)
        .map((part) => shownBox(part))
        .filter(Boolean),
    );
    // A pointed row is small enough to stand by whole. An element has no passage
    // fragment, so it supplies only the box the shared placement policy reads.
    const point = box && response.pointIn(targetElement(found));
    const elementBox = point
      ? pointBand(union(targetParts(found).map((part) => shownBox(part))), point)
      : box;
    return elementBox
      ? {
          box: elementBox,
          attachment: null,
          contextNode: point ?? targetElement(found),
        }
      : null;
  }
  // The passage remains the exact anchor, but its resolved place is not spare space: a
  // short selection cannot lend the words around it to the response field. Keep the bar
  // beside that whole place, or above/below it when the rail is too narrow.
  function placeFab() {
    if (!response.anchor) return false;
    if (response.open && nativeAttachment) return true;
    const geometry = anchorGeometry(response.anchor);
    const target = geometry?.box;
    const owner = response.target;
    if (!target) return false;
    const windowBoundary = floatBoundary();
    const place = commentAttachment({
      target: owner,
      point: response.anchor.quote ? null : response.pointIn(owner),
      passage: geometry,
    });
    const boundary = place.region ? floatBoundary(place.region) : windowBoundary;
    if (boundary.width <= 0 || boundary.height <= 0) return false;
    const roomRect = place.extent;
    const keepClear = place.clear;
    const scroller = place.scroller;
    const verticalRoom = (side) =>
      reachableRoom(side, roomRect, boundary, scroller).reachable;
    // Width before coordinates: the side is chosen from the card's minimum, then the size
    // pass gives CSS that side's actual inline room. If a later resize makes the chosen
    // side narrower than the bar's minimum, use the whole boundary and let shift overlap
    // the target instead of silently moving the draft.
    const setWidth = (available, scale) => {
      const room = available;
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
      const room = vertical(side) ? verticalRoom(side) : boundary.height;
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
          lastRow: place.lastRow,
          column: place.column,
          margin: place.margin,
          boundary,
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
            contextNode: place.contextNode,
            getBoundingClientRect: () => reference,
          },
          { placement, middleware },
          response.open ? () => "page" : plane,
          owner ?? document.documentElement,
        );
      })
      .then((position) => {
        if (!position || !stillCurrent()) return;
        fabPlacement.landed(position);
        keeps(fabBar, "data-lf-placement", position.placement);
        // An auto-height absolute box borrows its inset-modified available height.
        // Intrinsic sizing keeps moving that inset from masquerading as content resize.
        fabBar.style.height = response.open ? "max-content" : "";
        fabPosition.stand(position);
        nativeAttachment = response.open && fabPosition.follows();
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
    // Widgets declare moves inside a stable outer box here. Scroll has its own
    // mechanical owner and never emits this geometry-invalidating publication.
    document.addEventListener(LAYOUT, (event) => {
      if (!response.anchor || !under(response.target, event.target)) return;
      nativeAttachment = false;
      scheduleFabPosition();
    });
    // Floating, the box is carried away with its passage and comes back with it, by the
    // passage's first line, which a block taller than the window would not bring back;
    // inline, it is in flow and the browser's own reveals reach it.
    declareOffFlowSurface(fabBar, {
      floats: () => Boolean(response.anchor && response.floating),
      away: () => fabWithheld,
      bringBack: (behavior) => {
        const found = resolveAnchor(response.anchor, pageText());
        const range = response.anchor.quote && targetRange(found);
        if (range) return scrollToRange(range, behavior);
        const target = response.target;
        const line = response.pointIn(target) ?? target;
        if (line) scrollToElement(line, behavior, "nearest");
      },
    });
  }
  return {
    holdsHome: fabPosition.holdsHome,
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
