/* Floating presentation of the one native response bar.

   Composition owns its durable target and native editor. This owner chooses its initial
   side, measure and CSS attachment. Each scroll around its words solves the box again,
   as it does the card, so the room's edges can hold it in (`scroll-held-in`). Beside
   its words the answer writes nothing, and the browser carries the box by its anchor;
   held in by an edge, the box stands in that edge's plane (floating.js). While the open
   box stands beside its words, a repaint solves no new position for it
   (`nativeAttachment`); a scroll, a target resize, a change of the field's height, a
   viewport or pane resize, horizontal target motion and a declared layout change end
   that attachment, and the field widening with its words stays inside the room the
   attachment gave it. Replacing its target or native seat retires it. The compact
   response strip keeps ordinary collision placement, and a layout shift invalidates it
   too. A seated editor carries its frame through attachment changes under the shared
   rule in comment-placement.js; its durable anchor and native editor stay intact.

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
   a visibility behind for the other to undo.

   The box at rest beside a target (`response.rests`; annotations/composing/surface.js, `restFab`)
   stands where its editor will and is carried as its editor is, so opening it moves
   nothing. It has no editor yet, so it has no height to fit and no motion to follow.
   It stands only in the room beside what it is about, the margin its rail stands in
   (margin-layout.js, `railStandsBeside`, `railEdge`), whatever rows stand there
   already. Under or over its target, on its left, beside a target that ends short of
   the column's edge, slid across a target with no room beside it, or beside a target
   the rail doesn't stand by, as a workspace pane whose neighbour fills the window
   beside it, it would lie on the page's own words and controls, the one just pressed
   among them, and the next press there would open it (browser/AGENTS.md, "Controls
   stay where the user aims"), so there it waits for `c`. */
import { pageRange } from "../../../dom/native-selection.js";
import { cancelRender, nextRender, sizeObserver } from "../../../lib/frame-pass.js";
import { boxMotion } from "../../../dom/box-motion.js";
import { sameAnchor } from "../../../base/anchor-coordinate.js";
import { declareOffFlowSurface } from "../../../readings/off-flow.js";
import { shownBox } from "../../../dom/geometry.js";
import {
  passageGeometry,
  rangeGeometry,
  targetElement,
  targetParts,
  targetRange,
  targetSegments,
} from "../../../readings/resolved-target.js";
import { blockAt, quoteFrom, segmentsIn } from "../../../readings/passages.js";
import { pageSelection, selectionAnchor } from "../../composing/capture.js";
import { closeLayer, drawn, holdFocus } from "../../../dom/focus.js";
import { coarsePointer } from "../../../base/pointer.js";
import { LAYOUT } from "../../../lib/widget-events.js";
import { under } from "../../../lib/shadow-tree.js";
import { union } from "../../../dom/rect.js";
import { floatingPlacement, floatingUi } from "../floating.js";
import { surfaceGrip } from "../surface-grip.js";
import {
  cardMeasure,
  commentAttachment,
  commentReference,
  commentBoundary,
  commentPlacement,
} from "../comment-placement.js";
import { railEdge, railStandsBeside } from "../margin-layout.js";
import { pointBand } from "../../../readings/pointed-place.js";
import { keeps, roomPx } from "../../../lib/keeps.js";
import { pageScroller } from "../../../dom/scrolling.js";

/** @typedef {import("../../../../types/domain.js").Anchor} Anchor */
/** @param {{bar: HTMLElement, input: HTMLElement,
 * response: import("../../composing/surface.js").ResponseState,
 * positioned: (ready: boolean) => void, dismiss: () => void,
 * scrollToElement: (element: Element, behavior: ScrollBehavior, block: ScrollLogicalPosition) => unknown,
 * scrollToPassage: ReturnType<typeof import("../../../features/anchor-travel.js").createAnchorTravel>["scrollToPassage"],
 * scrollToRange: (range: Range, behavior: ScrollBehavior) => unknown,
 * }} capabilities */
export function createFloatingResponsePlacement({
  bar: fabBar,
  input: fabInput,
  response,
  positioned,
  dismiss,
  scrollToElement,
  scrollToPassage,
  scrollToRange,
}) {
  /** @param {Element} [scroller] */
  const floatBoundary = (scroller) => commentBoundary({ scroller });
  // The side the bar holds and its inline start, by the rule the thread card it becomes
  // stands by too (comment-placement.js).
  const fabPlacement = commentPlacement();
  let fabPositionFrame = 0;
  // Whether the bar the user has is waiting out of view for room to stand
  // (withholdFab), and where it takes them back to when it stands again.
  let fabWithheld = false;
  /** @type {ReturnType<typeof holdFocus> | null} */
  let fabWithheldFocus = null;
  // What invalidates the placement, a scroll included, invalidates the attachment too.
  const fabPosition = floatingPlacement({
    floating: fabBar,
    update: () => {
      nativeAttachment = false;
      scheduleFabPosition();
    },
  });
  let nativeAttachment = false;
  // The attachment the seated editor last landed on, separate from whichever
  // geometry a later read resolves. Only a completed placement advances this tenure.
  /** @type {{owner: Node | null, passage: boolean} | null} */
  let editingAttachment = null;
  // An explicit open on a hidden subject retains a window seat until it returns.
  let windowPosture = false;
  // The box that scrolled the box's row at its last placement, whose boundary holds a
  // carry in.
  /** @type {Element} */
  let fabScroller = pageScroller;
  // The element whose box bounds that placement, as a workspace pane does, or the page
  // scroller where the window does (`commentBoundary`).
  /** @type {Element} */
  let fabRegion = pageScroller;
  // The editing watch's size observer and the region it observes, which follows
  // `fabRegion`: a workspace's layout can hand the box's text from the page's scroll
  // to a pane's and back while the box stays open.
  /** @type {{sizes: ResizeObserver, region: Element} | null} */
  let watchedRegion = null;
  function watchRegion() {
    if (!watchedRegion || watchedRegion.region === fabRegion) return;
    const { sizes, region } = watchedRegion;
    if (region !== pageScroller) sizes.unobserve(region);
    if (fabRegion !== pageScroller) sizes.observe(fabRegion);
    watchedRegion.region = fabRegion;
  }
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
  const fabField = () => response.composition().field;
  // The box follows every change of its layout as the panel and the card do
  // (dom/box-motion.js): a line the field gains or loses, the measure it widens into, which
  // a key changes at once but for a line it takes away (dom/box-motion.js, "Whose change
  // it is"). The field's frame is the box, drawn by a surface behind it, and the
  // composer holding the field and the pictures hanging off it is what moves, so the
  // grip beside it, whose clip opens its middle to the field's presses, is never cut.
  // It reads in the plane its placement stands it in, so a scroll or a carry that moves
  // it whole moves nothing in it, and a change of the open box's size asks for its
  // placement first (dom/box-motion.js, `placed`). A box no placement stands has nothing
  // to move from, and one seated in a widget's outlet stands in that widget's flow.
  /** @type {ReturnType<typeof boxMotion> | null} */
  let following = null;
  // The open box a placement stands, whose motion asks that placement again when the
  // box's size changes.
  const followedOpen = () =>
    following !== null && response.open && fabBar.hasAttribute("data-lf-placement");
  function fabMotion() {
    const box = fabField();
    // The composer holding the composition is the root, since the composition's frame is
    // a wrapper with no box of its own (`display: contents`), whose empty rectangle
    // carries nothing with the plane.
    const composer = /** @type {HTMLElement} */ (
      response.composition().frame.parentElement
    );
    const motion = boxMotion({
      root: composer,
      box,
      surface: "lf-fab-ground",
      lift: 1,
      outset: 0,
      placement: {
        held: fabPosition.held,
        place: () => {
          if (!followedOpen()) return false;
          nativeAttachment = false;
          return placeFab();
        },
      },
    });
    fabBar.prepend(motion.ground);
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
  /** @type {{anchor: Anchor, range: Range, start: Node, end: Node} | null} */
  let selectedPassage = null;
  // The box's frame as its rectangles read, shifted back by `lag`.
  /** @param {{x: number, y: number}} lag
   * @returns {import("../../../records/thread/destination.js").SendFrame | null} */
  const frameShifted = (lag) => {
    if (!response.open || !response.floating) return null;
    /** @param {import("../../../base/box.js").Box} rect */
    const shown = (rect) =>
      new DOMRect(
        rect.left - lag.x,
        rect.top - lag.y,
        rect.right - rect.left,
        rect.bottom - rect.top,
      );
    const bar = shown(fabBar.getBoundingClientRect());
    const field = shown(fabField().getBoundingClientRect());
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
      ),
      placement: fabPlacement.capture(),
      // The frame's width in its own CSS pixels, which the card Send opens starts at
      // (thread-preview.js, `size-width`), whatever scales the page after Send.
      width,
      // The field the card grows out of (dom/box-motion.js, `drawnAt`).
      field: following ? shown(following.outline()) : field,
      // How far the words stand above their end: where the user was reading them,
      // which the card Send opens keeps (thread-preview.js, `showArrival`).
      fromEnd: fabInput.scrollHeight - fabInput.clientHeight - fabInput.scrollTop,
    };
  };
  // Where the box paints, which a scroll in this task leaves its rectangles behind
  // (floating.js, `lag`). Send opens its card from this frame.
  const fabFrameAt = () => frameShifted(fabPosition.lag());
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
  // Which side of its field a draft's pictures hang on (annotation-chrome.css). The
  // marks on the pictures' top corners, such as Remove, are what the user presses next.
  // Under the field, those corners face the field and stand inside the reply row the
  // box's frame keeps, and the placement keeps the whole box inside its boundary, so
  // the marks stay in the window even where a picture runs past its foot. Over the
  // field, those corners are the shelf's far edge. So a box over its passage hangs its
  // pictures over the field only where the room there holds the whole shelf, and under
  // the field otherwise, as when the window's top edge holds the box on its passage.
  // Over the field, the shelf reaches its own height past it, or a few pixels less
  // where its offset takes back more of its padding. `mediaSide` reads the shelf
  // before the placement writes, and the function it returns chooses the side for the
  // box where the placement stands it.
  /** @param {import("@floating-ui/dom").Placement} placement
   * @param {ReturnType<typeof floatBoundary>} boundary */
  function mediaSide(placement, boundary) {
    if (!placement.startsWith("top")) return () => "bottom";
    const shelf = response
      .composition()
      .frame.querySelector(":scope > .lf-composer-media");
    const height = shelf instanceof HTMLElement ? shelf.offsetHeight : 0;
    const frame = {
      height: fabBar.offsetHeight,
      top: parseFloat(getComputedStyle(fabBar).paddingTop),
    };
    /** @param {DOMRectReadOnly} box */
    return (box) => {
      if (!height || !frame.height) return "top";
      const scale = box.height / frame.height;
      const room = boundary.across({ left: box.left, right: box.right });
      return box.top + frame.top * scale - room.top >= height * scale
        ? "top"
        : "bottom";
    };
  }
  const fabFits = () => {
    const boundary = floatBoundary();
    return (
      boundary.width > 0 &&
      Math.ceil(boundary.width) >= Math.ceil(fabBar.getBoundingClientRect().width)
    );
  };
  // The editing observer reports size and horizontal target movement: a target moved
  // without resizing must let the shared placement rule choose its side again, while
  // one moved only vertically is carried by its anchor. A compact strip observes layout
  // shifts as well. Explicit publication may
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
    editingAttachment = null;
    windowPosture = false;
    fabPlacement.forget();
    fabBar.removeAttribute("data-lf-placement");
    fabBar.removeAttribute("data-lf-media-side");
    fabBar.removeAttribute("data-lf-card-width");
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

  /** @typedef {(reference: import("@floating-ui/dom").VirtualElement & {contextElement: Element},
   * floating: HTMLElement, update: () => void,
   * options: import("@floating-ui/dom").AutoUpdateOptions) => () => void} EditingObserver */
  /** @type {{editing: EditingObserver, compact: typeof import("@floating-ui/dom").autoUpdate} | null} */
  let observationModes = null;
  // Built outside `watchFabPosition`, whose scope holds the target it watches: the
  // modes outlive every watch, and a closure made there would keep its first target
  // alive for the session, after a revision removed it.
  /** @param {typeof import("@floating-ui/dom").autoUpdate} autoUpdate
   * @returns {EditingObserver} */
  function editingObserver(autoUpdate) {
    return (reference, floating, update, options) => {
      // The placement stands the box by the window's size, its region's and its
      // reference's, and by the box's own. The open box a placement stands asks for
      // it through its motion as its size changes (`fabMotion`), so a change of that
      // box alone is the motion's; this watch hears every other.
      const stopSize = autoUpdate(reference, floating, update, {
        ...options,
        elementResize: false,
        layoutShift: false,
      });
      const sizes = sizeObserver((entries) => {
        if (followedOpen() && entries.every(({ target }) => target === floating))
          return;
        update();
      });
      sizes.observe(reference.contextElement);
      sizes.observe(floating);
      watchedRegion = { sizes, region: pageScroller };
      watchRegion();
      let x = reference.getBoundingClientRect().left;
      const stopMotion = autoUpdate(
        reference,
        floating,
        () => {
          const next = reference.getBoundingClientRect().left;
          if (next === x) return;
          x = next;
          update();
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
        sizes.disconnect();
        if (watchedRegion?.sizes === sizes) watchedRegion = null;
      };
    };
  }
  /** @param {Element} target
   * @param {Pick<typeof import("@floating-ui/dom"), "autoUpdate" | "getOverflowAncestors">} ui */
  function watchFabPosition(target, { autoUpdate, getOverflowAncestors }) {
    const reference = {
      contextElement: response.pointIn(target) ?? target,
      getBoundingClientRect: () => {
        const box = anchorGeometry(response.anchor)?.box;
        return box
          ? new DOMRect(box.left, box.top, box.width, box.height)
          : target.getBoundingClientRect();
      },
    };
    observationModes ??= {
      editing: editingObserver(autoUpdate),
      compact: autoUpdate,
    };
    const observes = observationModes;
    fabPosition.watch(
      target,
      reference,
      response.open || response.rests ? observes.editing : observes.compact,
      getOverflowAncestors,
    );
  }
  // A retained native Range and a resolved passage are two routes to geometry. Only
  // the former is allowed to outlive a selection's focus handoff, not its endpoints
  // or words. Recovery and placement ask the same validity rule.
  /** @param {Anchor} anchor */
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
  // the hand named and reads its current box (readings/pointed-place.js).
  /** @param {Anchor | null} anchor */
  function anchorGeometry(anchor) {
    if (anchor?.quote) {
      const selection = pageSelection();
      const current = selection ? selectionAnchor(selection) : null;
      if (selection && current && sameAnchor(anchor, current)) {
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
        .map(/** @param {Element} part */ (part) => shownBox(part))
        .filter(Boolean),
    );
    // A pointed row is small enough to stand by whole. An element has no passage
    // fragment, so it supplies only the box the shared placement policy reads.
    const point = box && response.pointIn(targetElement(found));
    const elementBox = box && point ? pointBand(box, point) : box;
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
      blockAt(context ?? null) ??
      (context instanceof Element ? context : context?.parentElement) ??
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
      // Its rectangles as read: `lag` measures from the anchor's box read now, which
      // the saved state has just moved, so it would count that move as a scroll.
      const frame = frameShifted({ x: 0, y: 0 });
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
    fabRegion = boundary.scroller;
    watchRegion();
    // Width before coordinates: the side is chosen from the card's minimum, then the size
    // pass gives CSS that side's actual inline room. The box's frame is no wider than the
    // card's measure (annotation-chrome.css), so its room is written up to that measure,
    // as the card's width is, and a scroll that carries its words across a wider room
    // writes nothing. If a later resize makes the chosen side narrower than the bar's
    // minimum, use the whole boundary and let shift overlap the target instead of
    // silently moving the draft.
    /** @param {number} available @param {number} scale */
    const setWidth = (available, scale) => {
      const room =
        response.open || response.rests
          ? Math.min(available, cardMeasure())
          : available;
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
    /** @param {{height: number}} room @param {number} scale */
    const setHeight = (room, scale) => {
      if (!response.open) return;
      fabBar.style.setProperty(
        "--lf-float-h",
        roomPx(Math.max(0, room.height / scale)),
      );
    };
    const seat = fabPlacement.choose({
      clear: place.clear,
      room: place.room,
      row: place.row,
      column: place.column,
      extent: place.extent,
      boundary,
      scroller: boundary.scroller,
      element: place.element,
      coarse: coarsePointer.matches,
    });
    if (
      response.rests &&
      (!railStandsBeside(place.element) ||
        seat.side !== "right" ||
        !place.clear ||
        place.clear.right < railEdge() - 1)
    ) {
      withholdFab();
      return false;
    }

    const epoch = fabPosition.begin();
    const stillCurrent = () =>
      fabPosition.current(epoch) && response.anchor && response.floating;
    void floatingUi()
      .then((ui) => {
        if (!stillCurrent()) return null;
        watchFabPosition(owner ?? document.documentElement, ui);
        const { reference, placement, middleware, plane } = seat.options(ui, {
          clear: place.clear,
          room: place.room,
          row: place.row,
          lastRow: place.lastRow,
          column: place.column,
          margin: place.margin,
          boundary,
          fit({ width, room, scale, widens }) {
            if (!stillCurrent()) return;
            // A box its placement can't widen from the edge its words start at takes
            // its widest at once (annotation-chrome.css).
            keeps(fabBar, "data-lf-card-width", widens ? null : "");
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
          plane,
          seatedOwner ?? document.documentElement,
        );
      })
      .then((position) => {
        if (!position || !stillCurrent()) return;
        fabPlacement.landed(position);
        editingAttachment = response.open ? attachment : null;
        // A scroll carries the box beside its words by CSS anchors, and its solve moves
        // it only where an edge takes it in or lets it go; what a placement moves
        // travels when it follows a change of the box's size (dom/box-motion.js, `placed`).
        // The open box's first spot is the first reading its motion follows from. A
        // drag the grip carried ends where the placement stands the box.
        const hang = mediaSide(position.placement, boundary);
        const stand = () => {
          keeps(fabBar, "data-lf-placement", position.placement);
          const moved = fabPosition.stand(position);
          keeps(fabBar, "data-lf-media-side", hang(fabPosition.clientBox(position)));
          carry.placed();
          return moved;
        };
        if (response.open) following ??= fabMotion();
        if (following && response.open) following.placed(stand);
        else stand();
        nativeAttachment = response.open && fabPosition.follows();
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
      box: fabField,
      bringBack: /** @param {ScrollBehavior} behavior */ (behavior) => {
        const found = response.resolved;
        const anchor = response.anchor;
        if (anchor?.quote && targetRange(found))
          return scrollToPassage(targetSegments(found), behavior);
        const selected = anchor?.quote && selectedRange(anchor);
        if (selected) return scrollToRange(selected, behavior);
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
