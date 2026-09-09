/* One-stroke drawing gesture controller.
 *
 * Drawing mode claims one primary-pointer drag anywhere on the page. A semantic target
 * under or horizontally alongside its first point remains the conversation coordinate;
 * otherwise the stroke becomes a page comment. The controller owns pointer capture,
 * stroke sampling, and mode state. SVG replay, anchor placement, composers, reactions,
 * and page geometry enter through explicit capabilities.
 */

import { documentPoint, shownBox } from "../geometry.js";
import { closestAcross, elementFromPointAcross, inChrome } from "../passages.js";
import {
  DRAWING_COORDINATE_LIMIT,
  DRAWING_FORMAT,
  MAX_DRAWING_POINTS,
} from "./drawing-record.js";

const MIN_DISTANCE = 2;
const MIN_GESTURE = 4;
const PRESS_EVENTS = ["mousedown", "mouseup", "click", "dblclick"];

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const rounded = (value) => Number(value.toFixed(4));

export function createDrawingController({
  anchors: { aimTargetAt, resolveAnchor, pendingAt },
  pageGeometry: { refreshAim },
  pointer,
  visibleTargets,
  pageDrawing,
  composerDraft,
  openAnchoredDrawing,
  openPageDrawing,
  setDesign,
  stopSelecting,
  closeReactionMode,
  banner,
  announce,
  paintDrawings,
  shiftDrawingPaint,
  repaint,
}) {
  let drawingOn = false;
  let stroke = null;
  let claimThroughClick = false;
  let claimedPointer = null;
  let releaseTimer = null;
  let mounted = false;

  const isDrawing = () => drawingOn;

  function releaseCompatibilityClickSoon() {
    if (releaseTimer !== null) globalThis.clearTimeout(releaseTimer);
    releaseTimer = setTimeout(() => {
      releaseTimer = null;
      claimThroughClick = false;
    });
  }

  function setDrawing(on, { spoken = true, keepPress = false } = {}) {
    on = Boolean(on);
    if (on) {
      setDesign(false, { spoken: false });
      stopSelecting();
      closeReactionMode();
    }
    drawingOn = on;
    if (!on && !keepPress) {
      stroke = null;
      // Escape can leave while the pointer remains down. Keep claiming that physical
      // press through its compatibility click; only the drawing itself stops.
      if (claimedPointer === null) claimThroughClick = false;
    }
    document.body.classList.toggle("lf-drawing", on);
    banner.classList.toggle("lf-drawing", on);
    refreshAim();
    if (spoken)
      announce(
        on
          ? "Draw mode: draw anywhere on the page, then send or add words. Escape leaves."
          : "Draw mode off",
      );
    paintDrawings();
    repaint();
  }

  function targetAlongside({ x, y }) {
    let nearest = null;
    for (const target of visibleTargets()) {
      const box = target.rect;
      if (!box?.width || !box?.height || y < box.top || y > box.bottom) continue;
      const distance = x < box.left ? box.left - x : Math.max(x - box.right, 0);
      const area = box.width * box.height;
      if (
        !nearest ||
        distance < nearest.distance ||
        (distance === nearest.distance && area < nearest.area)
      )
        nearest = { area, distance, target };
    }
    return nearest?.target ?? null;
  }

  function targetAtPointer() {
    const atPointer = pointer();
    if (atPointer.x < 0) return null;
    const at = elementFromPointAcross(atPointer.x, atPointer.y);
    if (!at || inChrome(at)) return null;
    return (
      aimTargetAt(at) ?? targetAlongside(atPointer) ?? { anchor: null, element: null }
    );
  }

  function drawingFrom(points, targetBox) {
    const origin = targetBox
      ? documentPoint(targetBox.left, targetBox.top)
      : { left: 0, top: 0 };
    return {
      format: DRAWING_FORMAT,
      points: points.map(({ left, top }) => [
        rounded(
          clamp(
            left - origin.left,
            -DRAWING_COORDINATE_LIMIT,
            DRAWING_COORDINATE_LIMIT,
          ),
        ),
        rounded(
          clamp(top - origin.top, -DRAWING_COORDINATE_LIMIT, DRAWING_COORDINATE_LIMIT),
        ),
      ]),
    };
  }

  function rememberPoint(x, y) {
    if (!stroke || stroke.invalid) return false;
    if (stroke.anchor) {
      // A projection may replace the target during capture. Resolve the semantic anchor
      // again so the stroke follows a valid replacement and cancels if it disappeared.
      const found = resolveAnchor(stroke.anchor, "");
      const target = found?.status !== "outdated" ? found?.element : null;
      const box = target && shownBox(target);
      if (!box?.width || !box?.height) {
        stroke.invalid = true;
        shiftDrawingPaint();
        return false;
      }
      stroke.target = target;
      stroke.box = box;
    }
    const screen = { x, y };
    const prior = stroke.lastScreen;
    if (prior) {
      const distance = Math.hypot(x - prior.x, y - prior.y);
      if (distance < MIN_DISTANCE) return false;
      stroke.distance += distance;
    }
    stroke.lastScreen = screen;
    // Samples stay in the document plane. One target-relative origin is chosen when the
    // stroke is framed, so layout movement cannot mix coordinate bases.
    stroke.points.push(documentPoint(x, y));
    if (stroke.points.length > MAX_DRAWING_POINTS)
      stroke.points = stroke.points.filter(
        (_point, index, points) => index % 2 === 0 || index === points.length - 1,
      );
    shiftDrawingPaint();
    return true;
  }

  function claim(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }

  function begin(event) {
    if (!drawingOn || !event.isPrimary || event.button !== 0) return;
    const origin = event.composedPath()[0];
    // Inline conversations remain comment controls even when a shadow host seats them
    // in the page, so ownership follows the composed origin.
    if (inChrome(origin) || closestAcross(origin, ".lf-conversation")) return;
    claimThroughClick = true;
    claimedPointer = event.pointerId;
    const target = targetAtPointer();
    const box = target?.element ? shownBox(target.element) : null;
    if (!target || (target.element && (!box?.width || !box?.height))) {
      announce("Draw on the page.");
      claim(event);
      return;
    }
    claim(event);
    event.target.setPointerCapture(event.pointerId);
    stroke = {
      anchor: target.anchor,
      box,
      distance: 0,
      lastScreen: null,
      points: [],
      pointerId: event.pointerId,
      target: target.element,
    };
    rememberPoint(event.clientX, event.clientY);
  }

  function move(event) {
    if (!stroke || event.pointerId !== stroke.pointerId) {
      if (event.pointerId === claimedPointer) claim(event);
      return;
    }
    claim(event);
    rememberPoint(event.clientX, event.clientY);
  }

  function finish(event) {
    if (!stroke || event.pointerId !== stroke.pointerId) {
      if (event.pointerId === claimedPointer) {
        claim(event);
        claimedPointer = null;
        releaseCompatibilityClickSoon();
      }
      return;
    }
    claim(event);
    rememberPoint(event.clientX, event.clientY);
    const completed = stroke;
    stroke = null;
    claimedPointer = null;
    releaseCompatibilityClickSoon();
    if (completed.invalid) {
      shiftDrawingPaint();
      announce("Drawing canceled because its page item changed.");
      return;
    }
    if (completed.distance < MIN_GESTURE || completed.points.length < 2) {
      shiftDrawingPaint();
      announce("Drag to draw; a click leaves no mark.");
      return;
    }
    const drawing = drawingFrom(completed.points, completed.box);
    setDrawing(false, { spoken: false, keepPress: true });
    if (completed.anchor) openAnchoredDrawing(completed.anchor, drawing);
    else openPageDrawing(drawing);
    announce("Drawing captured. Send it or add words to the comment.");
  }

  function cancel(event) {
    if (!stroke || event.pointerId !== stroke.pointerId) {
      if (event.pointerId === claimedPointer) {
        claim(event);
        claimedPointer = null;
        releaseCompatibilityClickSoon();
      }
      return;
    }
    claim(event);
    stroke = null;
    claimedPointer = null;
    releaseCompatibilityClickSoon();
    shiftDrawingPaint();
    announce("Drawing canceled. Draw mode is still on.");
  }

  const compatibilityPress = (event) => {
    if (claimThroughClick) claim(event);
  };

  function activeDrawing() {
    if (!stroke || stroke.points.length < 2) return null;
    return {
      drawing: drawingFrom(stroke.points, stroke.box),
      target: stroke.target,
    };
  }

  function draftDrawings() {
    const drawings = [];
    const page = pageDrawing();
    if (page) drawings.push({ drawing: page, target: null });
    const draft = composerDraft();
    if (!draft.open || !draft.drawing) return drawings;
    if (!draft.anchor) drawings.push({ drawing: draft.drawing, target: null });
    else {
      const place = pendingAt();
      if (place?.status !== "outdated" && place?.target)
        drawings.push({ drawing: draft.drawing, target: place.target });
    }
    return drawings;
  }

  function mount() {
    if (mounted) return;
    mounted = true;
    document.addEventListener("pointerdown", begin, true);
    document.addEventListener("pointermove", move, true);
    document.addEventListener("pointerup", finish, true);
    document.addEventListener("pointercancel", cancel, true);
    for (const type of PRESS_EVENTS)
      document.addEventListener(type, compatibilityPress, true);
  }

  function destroy() {
    if (mounted) {
      document.removeEventListener("pointerdown", begin, true);
      document.removeEventListener("pointermove", move, true);
      document.removeEventListener("pointerup", finish, true);
      document.removeEventListener("pointercancel", cancel, true);
      for (const type of PRESS_EVENTS)
        document.removeEventListener(type, compatibilityPress, true);
    }
    mounted = false;
    if (releaseTimer !== null) globalThis.clearTimeout(releaseTimer);
    releaseTimer = null;
    drawingOn = false;
    stroke = null;
    claimThroughClick = false;
    claimedPointer = null;
    document.body.classList.remove("lf-drawing");
    banner.classList.remove("lf-drawing");
  }

  return {
    mount,
    destroy,
    isDrawing,
    setDrawing,
    activeDrawing,
    draftDrawings,
  };
}
