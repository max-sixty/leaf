/* Floating presentation of the one native response bar.

   Composition owns its durable target and native editor. This owner chooses its initial
   side, measure and CSS attachment. While editing, the browser carries that attachment
   through every ancestor scroll; generic repaint and scroll publications do not solve
   another position. Target or field resize, viewport resize, horizontal target motion,
   and declared layout changes invalidate the attachment. Replacing its target or native seat retires it. The compact response strip retains ordinary
   collision placement and scroll observation.

   A detached draft uses the shared unanchored window posture, preserving its original
   anchor and native editor. Resume writing can recover it even after that passage is gone.
   An attached editing field follows its passage out of view. The existing Resume writing route
   reveals that same field; no window seat or duplicate input stands in for it. A modal
   side panel withholds the page's response bar and takes its focus until the page is
   available again. */
import { cancelRender, nextRender } from "/runtime/rendering.js";
import { sameAnchor } from "/runtime/anchor-coordinate.js";
import { declareOffFlowSurface } from "/runtime/off-flow.js";
import { rightCover, shownBox } from "/runtime/geometry.js";
import {
  passageGeometry,
  rangeGeometry,
  targetElement,
  targetParts,
  targetRange,
} from "/runtime/resolved-target.js";
import {
  blockAt,
  pageRange,
  quoteFrom,
  segmentsIn,
} from "/runtime/passages.js";
import { pageSelection, selectionAnchor } from "/runtime/composing/capture.js";
import { closeLayer, holdFocus, focusDestination } from "/runtime/focus.js";
import { coarsePointer } from "/runtime/pointer.js";
import { LAYOUT } from "/runtime/widget-elements.js";
import { under } from "/runtime/shadow.js";
import { union } from "/runtime/rect.js";
import { floatingPlacement, floatingUi } from "../floating.js";
import {
  commentAttachment,
  commentReference,
  commentBoundary,
  commentPlacement,
} from "../comment-placement.js";
import { pointBand } from "/runtime/pointed-place.js";
import { keeps, layoutPx } from "/runtime/keeps.js";

export function createFloatingResponsePlacement({
  bar: fabBar,
  input: fabInput,
  response,
  panelIsOpen,
  threadsBox,
  positioned,
  dismiss,
  scrollToElement,
  scrollToRange,
}) {
  const floatBoundary = (region = null) =>
    commentBoundary({ region, right: rightCover() });
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
  let nativeAttachment = false;
  // The browser's selected Range is a mechanical place even when its durable quote
  // is ambiguous. Keep it for this response transaction, only while its original
  // endpoints survive. A revision replacing them retires it; semantic resolution
  // is the only way to identify that passage again after the node lifetime ends.
  // The detached draft itself remains reachable in the unanchored window posture.
  let selectedPassage = null;
  const fabFrameAt = () => {
    if (!response.open || !response.floating || panelIsOpen()) return null;
    const bar = fabBar.getBoundingClientRect();
    const field = fabInput.getBoundingClientRect();
    const style = getComputedStyle(fabBar);
    const scaleX = bar.width / parseFloat(style.width);
    const scaleY = bar.height / parseFloat(style.height);
    const left = parseFloat(style.paddingLeft);
    const top = parseFloat(style.paddingTop);
    const width = field.width / scaleX + left + parseFloat(style.paddingRight);
    const height = field.height / scaleY + top + parseFloat(style.paddingBottom);
    // The reserved header and footer surround the words the user sends. Attachment
    // shelves and options disappear on Send, so their tracks are not the card's origin.
    return {
      box: new DOMRect(
        field.left - left * scaleX,
        field.top - top * scaleY,
        width * scaleX,
        height * scaleY,
      ).toJSON(),
      width,
      placement: fabPlacement.capture(),
    };
  };
  // Where the frame's native rows end. Used grid tracks exclude transformed descendant
  // paint. Withholding requires only the current controls to fit, so they may borrow the
  // transparent footer reserved for the future card when space is short.
  const nativeRowEnd = () => {
    const style = getComputedStyle(fabBar);
    const rows = style.gridTemplateRows.split(" ").map(parseFloat);
    return Math.round(
      rows.reduce((height, row) => height + row, 0) +
        parseFloat(style.rowGap) * (rows.length - 1) +
        parseFloat(style.paddingTop),
    );
  };
  const fabFits = () => {
    const boundary = floatBoundary();
    return (
      boundary.width > 0 &&
      Math.ceil(boundary.width) >= Math.ceil(fabBar.getBoundingClientRect().width)
    );
  };
  const panelCoversPage = () =>
    panelIsOpen() && threadsBox.closest("dialog")?.matches(":modal");

  // The editing observer reports size and horizontal target movement: CSS anchors
  // own scroll following, while a target moved without resizing must let the shared
  // placement rule choose its side again. Movement observation also hears scroll,
  // which must leave the native attachment alone.
  // A compact strip still observes scroll and layout shifts. Explicit publication may
  // replace a target or editor seat; composition stops this owner for that handoff.
  // Native-seat readiness belongs to composition; stopping this presenter retires
  // only its observers and geometry, never a handoff waiting for an inline seat.
  function stopFabPositioning({ reset = false } = {}) {
    nativeAttachment = false;
    if (fabBar.style.height) fabBar.style.removeProperty("height");
    fabPosition.stop();
    cancelRender(fabPositionFrame);
    fabPositionFrame = 0;
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
  function watchFabPosition(target, autoUpdate, getOverflowAncestors) {
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
          let x = reference.getBoundingClientRect().left;
          const scrollers = getOverflowAncestors(reference.contextElement);
          const scrollPose = () =>
            scrollers.map((node) => [
              node.scrollX ?? node.scrollLeft,
              node.scrollY ?? node.scrollTop,
            ]);
          let pose = scrollPose();
          const stopMotion = autoUpdate(
            reference,
            floating,
            () => {
              const next = reference.getBoundingClientRect().left;
              const now = scrollPose();
              const scrolled = now.some((axes, i) =>
                axes.some((value, axis) => value !== pose[i][axis]),
              );
              pose = now;
              if (scrolled) {
                x = next;
                return;
              }
              if (next === x) return;
              x = next;
              invalidate();
            },
            {
              ancestorScroll: false,
              ancestorResize: false,
              elementResize: false,
              layoutShift: true,
            },
          );
          return () => {
            stopMotion();
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
  // A retained native Range and a resolved passage are two routes to geometry. Only
  // the former is allowed to outlive a selection's focus handoff, not its endpoints
  // or words. Recovery and placement ask the same validity rule.
  function selectedRange(anchor) {
    if (
      selectedPassage &&
      sameAnchor(anchor, selectedPassage.anchor) &&
      selectedPassage.start.isConnected &&
      selectedPassage.end.isConnected &&
      quoteFrom(segmentsIn(selectedPassage.range)) === anchor.quote
    )
      return selectedPassage.range;
    selectedPassage = null;
    return null;
  }
  // The native selected place owns a live response transaction; after replacement,
  // only the durable coordinate can find it again. A pointed element keeps the row
  // the hand named and reads its current box (pointed-place.js).
  function anchorGeometry(anchor) {
    if (anchor?.quote) {
      const selection = pageSelection();
      const current = selection ? selectionAnchor(selection) : null;
      if (current && sameAnchor(anchor, current)) {
        const range = pageRange(selection).cloneRange();
        selectedPassage = {
          anchor,
          range,
          start: range.startContainer,
          end: range.endContainer,
        };
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
      const retained = selectedRange(anchor);
      if (retained) return rangeGeometry(retained);
    }
    const found = response.resolved;
    if (!anchor || !found) return null;
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
    if (panelCoversPage()) {
      withholdFab();
      return false;
    }
    const geometry = anchorGeometry(response.anchor);
    if (response.open && nativeAttachment && geometry) return true;
    if (!geometry && !response.open) return false;
    // Placement needs the actual block holding the native selection, independently
    // of whether those words can be uniquely named by a durable anchor.
    const context = geometry?.contextNode;
    const owner =
      response.target ??
      blockAt(context) ??
      (context?.nodeType === Node.ELEMENT_NODE ? context : context?.parentElement) ??
      null;
    const windowBoundary = floatBoundary();
    const place = commentAttachment({
      target: owner,
      point: response.anchor.quote ? null : response.pointIn(owner),
      passage: geometry,
      boundary: windowBoundary,
    });
    const boundary = place.region ? floatBoundary(place.region) : windowBoundary;
    if (boundary.width <= 0 || boundary.height <= 0) return false;
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
    // The frame may grow to the whole boundary on any side, past the room its held edge
    // leaves, since shift slides it inside. Native tracks reserve the furniture and give
    // the editor what remains. Typing never scrolls the page to make room. The box grows
    // from the edge that holds it, then slides inside the window, over its passage if it
    // must, and once it fills the window scrolls its own words.
    const setHeight = (scale) => {
      if (!response.open) return;
      fabBar.style.setProperty(
        "--lf-float-h",
        layoutPx(Math.max(0, boundary.height / scale)),
      );
    };
    fabPlacement.choose({
      clear: place.clear,
      column: place.column,
      extent: place.extent,
      boundary,
      scroller: place.scroller,
      coarse: coarsePointer.matches,
    });

    const epoch = fabPosition.begin();
    const stillCurrent = () =>
      fabPosition.current(epoch) && response.anchor && response.floating;
    void floatingUi()
      .then((ui) => {
        if (!stillCurrent()) return null;
        watchFabPosition(
          owner ?? document.documentElement,
          ui.autoUpdate,
          ui.getOverflowAncestors,
        );
        const { reference, placement, middleware, plane } = fabPlacement.options(ui, {
          clear: place.clear,
          row: place.row,
          lastRow: place.lastRow,
          column: place.column,
          margin: place.margin,
          boundary,
          fit({ width, scale }) {
            if (!stillCurrent()) return;
            setWidth(width, scale.x);
            setHeight(scale.y);
            const frame = fabBar.getBoundingClientRect();
            if (
              Math.ceil(frame.width) > Math.ceil(boundary.width) ||
              Math.ceil(frame.height) > Math.ceil(boundary.height) ||
              (response.open && nativeRowEnd() > fabBar.clientHeight)
            )
              withholdFab();
          },
        });
        return fabPosition.position(
          ui.computePosition,
          commentReference(place, reference),
          { placement, middleware },
          response.open && owner ? () => "page" : plane,
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
    const covered = panelCoversPage();
    stopFabPositioning({ reset: false });
    if (fabWithheld) return;
    fabWithheld = true;
    const held = holdFocus(fabBar);
    const toPanel = held && panelIsOpen() && (!fabFits() || covered);
    closeLayer(
      () => {
        if (fabBar.style.visibility !== "hidden") fabBar.style.visibility = "hidden";
      },
      toPanel && (() => focusDestination(threadsBox, "return")),
    );
    if (!toPanel) fabWithheldFocus = held;
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
      const geometry = anchorGeometry(response.anchor);
      const target = response.target ?? geometry?.contextNode;
      if (!response.anchor || !under(target, event.target)) return;
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
        const found = response.resolved;
        const range =
          response.anchor.quote &&
          (targetRange(found) ?? selectedRange(response.anchor));
        if (range) return scrollToRange(range, behavior);
        const target = response.target;
        const line = response.pointIn(target) ?? target;
        if (line) scrollToElement(line, behavior, "nearest");
      },
    });
  }
  return {
    holdsHome: fabPosition.holdsHome,
    stands: () => response.open || Boolean(anchorGeometry(response.anchor)),
    place: placeFab,
    stop: stopFabPositioning,
    frame: fabFrameAt,
    fits: fabFits,
    withhold: withholdFab,
    stoodAgain,
    withheld: () => fabWithheld,
    release: () => {
      selectedPassage = null;
      fabWithheld = false;
      fabWithheldFocus = null;
    },
    ready: () =>
      fabBar.hasAttribute("data-lf-placement") && fabBar.style.visibility !== "hidden",
    mount,
  };
}
