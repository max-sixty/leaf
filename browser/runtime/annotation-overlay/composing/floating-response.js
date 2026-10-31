/* Floating presentation of the one native response bar.

   Composition owns its durable target and native editor. This owner chooses its initial
   side, measure and CSS attachment. While editing, the browser carries that attachment
   through every ancestor scroll; generic repaint and scroll publications do not solve
   another position. Target or field resize, viewport resize, horizontal target motion,
   and declared layout changes invalidate the attachment. Replacing its target or native seat retires it. The compact response strip retains ordinary
   collision placement and scroll observation. A seated editor carries its frame
   through attachment changes under the shared rule in comment-placement.js;
   its durable anchor and native editor stay intact.

   A detached draft stands beside the words the user selected while the browser Range
   that selected them still holds them (`selectedPassage`), so a refused send's box
   comes back where it stood; past that, it uses the shared unanchored window posture,
   preserving its original anchor and native editor. An explicit open uses that same posture while its existing
   subject is hidden; a seated editor withholds instead. Resume writing can recover it
   even after that passage is gone.
   An attached editing field follows its passage out of view. The existing Resume writing route
   reveals that same field; no window seat or duplicate input stands in for it.

   The floating bar shows while a placement stands it (`data-lf-placement`) and no lack of
   room withholds it (`data-lf-withheld`); annotation-chrome.css hides it otherwise. This
   presenter writes those attributes and never the bar's visibility, and composition
   writes only whether the bar stands inline (`data-lf-presentation`), so neither leaves
   a visibility behind for the other to undo. */
import { pageRange } from "../../native-selection.js";
import { setScroll } from "../../arrivals.js";
import { cancelRender, nextFrame, nextRender, sizeObserver } from "../../rendering.js";
import { boxMotion } from "../../box-motion.js";
import { sameAnchor } from "../../anchor-coordinate.js";
import { declareOffFlowSurface } from "../../off-flow.js";
import { rightCover, shownBox } from "../../geometry.js";
import {
  passageGeometry,
  rangeGeometry,
  targetElement,
  targetParts,
  targetRange,
} from "../../resolved-target.js";
import { blockAt, quoteFrom, segmentsIn } from "../../passages.js";
import { pageSelection, selectionAnchor } from "../../composing/capture.js";
import { closeLayer, drawn, holdFocus } from "../../focus.js";
import { coarsePointer } from "../../pointer.js";
import { LAYOUT } from "../../widget-upgrade.js";
import { under } from "../../shadow.js";
import { union } from "../../rect.js";
import { floatingPlacement, floatingUi, heldEdges } from "../floating.js";
import { surfaceGrip } from "../surface-grip.js";
import {
  commentAttachment,
  commentReference,
  commentBoundary,
  commentPlacement,
} from "../comment-placement.js";
import { pointBand } from "../../pointed-place.js";
import { keeps, roomPx } from "../../keeps.js";
import { pageScroller, placeKept } from "../../scrolling.js";

export function createFloatingResponsePlacement({
  bar: fabBar,
  input: fabInput,
  response,
  positioned,
  dismiss,
  scrollToElement,
  scrollToRange,
}) {
  const floatBoundary = (scroller) =>
    commentBoundary({ scroller, right: rightCover() });
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
  // The attachment the seated editor last landed on, separate from whichever
  // geometry a later read resolves. Only a completed placement advances this tenure.
  let editingAttachment = null;
  // An explicit open on a hidden subject retains a window seat until it returns.
  let windowPosture = false;
  // The box that scrolled the box's row at its last placement, whose boundary holds a
  // carry in.
  let fabScroller = pageScroller;
  // Carried by its grip, the box stands where the user drops it, relative to its
  // passage, and its card opens there on Send.
  const carry = surfaceGrip({
    surface: fabBar,
    bounds: () => floatBoundary(fabScroller),
    dropped(box) {
      if (!response.anchor || !response.floating) return;
      if (box && response.open)
        fabPlacement.adopt({
          box,
          placement: { ...fabPlacement.capture(), moved: true },
        });
      nativeAttachment = false;
      placeFab();
    },
  });
  fabBar.append(carry.grip);
  // The field's frame, which `wireInput` builds around the editor as the composer
  // mounts: the box the user sees.
  const fabField = () => fabInput.parentElement;
  // The box follows every change of its layout as the panel and the card do
  // (box-motion.js): a line the field gains or loses, the measure it widens into. The
  // field's frame is the box, drawn by a surface behind it, and the composer holding
  // the field and the pictures hanging off it is what moves, so the grip beside it,
  // whose clip opens its middle to the field's presses, is never cut. It reads in the
  // plane its placement stands it in (floating.js, `heldEdges`), so a scroll or a carry
  // that moves it whole moves nothing in it. A box no placement stands has nothing to
  // move from, and one seated in a widget's outlet stands in that widget's flow.
  let following = null;
  const readFab = () => {
    if (!following && !response.open) return;
    if (!response.floating || !fabBar.hasAttribute("data-lf-placement"))
      return following?.forget();
    following ??= fabMotion();
    following.follow();
  };
  // A change of the open box's size can move its placement too, as a line taking it
  // past the window's edge shifts it. That placement lands asynchronously, but before
  // this frame paints, so the reading waits for it and the box travels once, from
  // where it was drawn to where it then stands. Read first, the box set out for where
  // its old placement stood it and turned back a frame later.
  const followed = sizeObserver(() => {
    if (following && response.open && fabBar.hasAttribute("data-lf-placement")) {
      nativeAttachment = false;
      if (placeFab()) return;
    }
    readFab();
  });
  function fabMotion() {
    const box = fabField();
    const motion = boxMotion({
      root: box.parentElement,
      box,
      surface: "lf-fab-ground",
      lift: 1,
      outset: 0,
      observer: followed,
      held: () => heldEdges(fabBar),
    });
    fabBar.prepend(motion.ground);
    followed.observe(box.parentElement);
    return motion;
  }
  // The browser's selected Range is a mechanical place even when its durable quote
  // is ambiguous. Keep it for its anchor, only while its original endpoints survive,
  // across the box's tenures: the box coming back to that draft, as a refused send's
  // words or Resume writing bring it, stands beside the words it was written on, which
  // a detached anchor alone cannot find again. A revision replacing them retires it;
  // semantic resolution is the only way to identify that passage again after the node
  // lifetime ends. The detached draft itself remains reachable in the unanchored window
  // posture.
  let selectedPassage = null;
  const fabFrameAt = () => {
    if (!response.open || !response.floating) return null;
    const bar = fabBar.getBoundingClientRect();
    const field = fabField().getBoundingClientRect();
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
      placement: fabPlacement.capture(),
      // The field the card grows out of (thread-preview.js, `followCard`).
      field: following?.outline() ?? field.toJSON(),
      // How far the words stand above their end: where the user was reading them,
      // which the card Send opens keeps (thread-preview.js, `showArrival`).
      fromEnd: fabInput.scrollHeight - fabInput.clientHeight - fabInput.scrollTop,
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
  // The editing observer reports size and horizontal target movement: CSS anchors
  // own scroll following, while a target moved without resizing must let the shared
  // placement rule choose its side again. Movement observation also hears scroll,
  // which must leave the native attachment alone.
  // A compact strip still observes scroll and layout shifts. Explicit publication may
  // replace a target or editor seat; composition stops this owner for that handoff.
  // Native-seat readiness belongs to composition; stopping this presenter retires
  // only its observers and geometry, never a handoff waiting for an inline seat.
  function stopFabPositioning({ reset = false } = {}) {
    carry.placed();
    nativeAttachment = false;
    fabPosition.stop();
    cancelRender(fabPositionFrame);
    fabPositionFrame = 0;
    if (!reset) return;
    following?.forget();
    editingAttachment = null;
    windowPosture = false;
    fabPlacement.forget();
    fabBar.removeAttribute("data-lf-placement");
    for (const property of ["--lf-float-w", "--lf-float-h"])
      fabBar.style.removeProperty(property);
  }

  function scheduleFabPosition() {
    if (
      fabPositionFrame ||
      !response.anchor ||
      !response.floating ||
      fabBar.hasAttribute("data-lf-carried")
    )
      return;
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
            ancestorScroll: false,
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
  function placeFab({ reveal = false } = {}) {
    if (!response.anchor) return false;
    const geometry = anchorGeometry(response.anchor);
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
    let place = commentAttachment({
      target: owner,
      point: response.anchor.quote ? null : response.pointIn(owner),
      passage: geometry,
      boundary: windowBoundary,
    });
    if (place) windowPosture = false;
    else if (response.open && (reveal || windowPosture)) {
      windowPosture = true;
      place = commentAttachment({ target: null, boundary: windowBoundary });
    } else {
      withholdFab();
      return false;
    }
    const seatedOwner = windowPosture ? null : owner;
    const attachment = { owner: seatedOwner, passage: Boolean(geometry?.attachment) };
    const changedAttachment =
      editingAttachment &&
      (editingAttachment.owner !== attachment.owner ||
        editingAttachment.passage !== attachment.passage);
    if (response.open && changedAttachment && drawn(fabInput)) {
      // Resolution may move from quoted words to their subject after saved state
      // arrives, including for a resumed draft with no retained native Range. Carry
      // the seated editor's frame through that handoff, before choosing its new seat.
      const frame = fabFrameAt();
      if (frame) {
        fabPlacement.adopt(frame);
        nativeAttachment = false;
      }
    }
    if (response.open && nativeAttachment && geometry && !windowPosture) return true;
    const boundary =
      place.scroller === pageScroller ? windowBoundary : floatBoundary(place.scroller);
    if (boundary.width <= 0 || boundary.height <= 0) return false;
    fabScroller = place.scroller;
    // Width before coordinates: the side is chosen from the card's minimum, then the size
    // pass gives CSS that side's actual inline room. If a later resize makes the chosen
    // side narrower than the bar's minimum, use the whole boundary and let shift overlap
    // the target instead of silently moving the draft.
    const setWidth = (available, scale) => {
      const room = available;
      fabBar.style.setProperty("--lf-float-w", roomPx(Math.max(0, room)));
      if (Math.ceil(fabBar.offsetWidth) > Math.ceil(room))
        fabBar.style.setProperty(
          "--lf-float-w",
          roomPx(Math.max(0, boundary.width / scale)),
        );
    };
    // The frame may grow to its whole room (`fit`'s) on any side, past the room its held edge
    // leaves, since shift slides it inside. Native tracks reserve the furniture and give
    // the editor what remains. Typing never scrolls the page to make room. The box grows
    // from the edge that holds it, then slides inside the window, over its passage if it
    // must, and once it fills the window scrolls its own words.
    const setHeight = (room, scale) => {
      if (!response.open) return;
      fabBar.style.setProperty(
        "--lf-float-h",
        roomPx(Math.max(0, room.height / scale)),
      );
    };
    fabPlacement.choose({
      clear: place.clear,
      row: place.row,
      column: place.column,
      extent: place.extent,
      boundary,
      scroller: boundary.scroller,
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
          fit({ width, room, scale }) {
            if (!stillCurrent()) return;
            setWidth(width, scale.x);
            setHeight(room, scale.y);
            const frame = fabBar.getBoundingClientRect();
            if (
              Math.ceil(frame.width) > Math.ceil(room.width) ||
              Math.ceil(frame.height) > Math.ceil(room.height) ||
              (response.open && nativeRowEnd() > fabBar.clientHeight)
            )
              withholdFab();
          },
        });
        return fabPosition.position(
          ui.computePosition,
          commentReference(place, reference),
          { placement, middleware },
          response.open && seatedOwner ? () => "page" : plane,
          seatedOwner ?? document.documentElement,
        );
      })
      .then((position) => {
        if (!position || !stillCurrent()) return;
        fabPlacement.landed(position);
        editingAttachment = response.open ? attachment : null;
        // An open box's placement moves it only for a change of layout, as a line
        // taking it past the window's edge shifts it, and never for a scroll, which
        // carries it by CSS anchors (`watchFabPosition`), so what it moves travels.
        const stand = () => {
          keeps(fabBar, "data-lf-placement", position.placement);
          fabPosition.stand(position);
        };
        if (following) following.placed(stand);
        else stand();
        carry.placed();
        nativeAttachment = response.open && fabPosition.follows();
        positioned(true);
        stoodAgain();
        // The box's spot is the first reading its motion follows from.
        readFab();
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
  // focused something else meanwhile. While the bar waits, its composer scope and
  // selection rung stand down; `c` brings it back.
  function withholdFab() {
    // Keep the target watch and its native frame: hiding retires the solve, not the
    // subject's lifetime. Its next visibility or geometry change can seat it again.
    nativeAttachment = false;
    fabPosition.supersede();
    if (fabWithheld) return;
    fabWithheld = true;
    const held = holdFocus(fabBar);
    closeLayer(() => fabBar.toggleAttribute("data-lf-withheld", true));
    fabWithheldFocus = held;
  }
  // The bar is in view again, by whichever placement put it there.
  function stoodAgain() {
    if (!fabWithheld) return;
    fabWithheld = false;
    fabBar.removeAttribute("data-lf-withheld");
    const returning = fabWithheldFocus;
    fabWithheldFocus = null;
    returning?.();
  }
  function mount() {
    // Chromium can reveal the caret by scrolling the document before it delivers
    // `input`, even though this editor is in a fixed frame that will fit the new
    // text inside the window. Keep the reader's page place in that same input task;
    // a deliberate wheel or navigation is a separate gesture.
    let beforeInputScroll = null;
    let inputEpoch = 0;
    fabInput.addEventListener("lf-before-edit", () => {
      beforeInputScroll =
        response.open && response.floating ? pageScroller.scrollTop : null;
      const epoch = ++inputEpoch;
      nextFrame(() => {
        if (inputEpoch === epoch) beforeInputScroll = null;
      });
    });
    fabInput.addEventListener("input", () => {
      if (beforeInputScroll === null) return;
      if (pageScroller.scrollTop !== beforeInputScroll) {
        setScroll(pageScroller, { top: beforeInputScroll, behavior: "instant" });
        placeKept(pageScroller);
      }
    });
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
    stands: () => response.open || Boolean(anchorGeometry(response.anchor)),
    place: placeFab,
    stop: stopFabPositioning,
    frame: fabFrameAt,
    fits: fabFits,
    withhold: withholdFab,
    stoodAgain,
    withheld: () => fabWithheld,
    release: () => {
      editingAttachment = null;
      windowPosture = false;
      fabWithheld = false;
      fabBar.removeAttribute("data-lf-withheld");
      fabWithheldFocus = null;
    },
    ready: () => fabBar.hasAttribute("data-lf-placement") && !fabWithheld,
    mount,
  };
}
