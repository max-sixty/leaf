/* Drawing gesture controller.
 *
 * Draw mode claims primary-pointer drags anywhere on the page until the reader leaves it.
 * The first stroke of a Draw mode session starts a drawing: a semantic target under or
 * horizontally alongside its first point remains the conversation coordinate; otherwise
 * the stroke becomes a page comment. Each later stroke joins that drawing, in its frame,
 * while the draft it opened still holds it, box on screen or not; once that draft is sent
 * or discarded, the next stroke starts another. The controller owns pointer capture,
 * stroke sampling, and mode state. SVG replay, anchor placement, composers, reactions,
 * and page geometry enter through explicit capabilities, and the composer's draft is the
 * one record of the strokes already drawn.
 */

import { documentPoint, shownBox } from "../geometry.js";
import { closestAcross, elementFromPointAcross, inChrome } from "../passages.js";
import { anchoringIsReady } from "../anchor-resolution.js";
import { pageCommand, pageRung, pageScope } from "../keyboard/register.js";
import {
  DRAWING_COORDINATE_LIMIT,
  DRAWING_FORMAT,
  MAX_DRAWING_POINTS,
  MAX_DRAWING_STROKES,
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
  anchoredDrawing,
  composerDraft,
  openAnchoredDrawing,
  openPageDrawing,
  setDesignMode,
  closeTargetChooser,
  closeReactionMode,
  banner,
  announce,
  paintDrawings,
  shiftDrawingPaint,
  repaint,
}) {
  let drawModeOn = false;
  let stroke = null;
  // The draft this session's first stroke opened: its anchor, or null for a page drawing.
  let session = null;
  let claimThroughClick = false;
  let claimedPointer = null;
  let releaseTimer = null;
  let mounted = false;

  const drawModeActive = () => drawModeOn;

  function releaseCompatibilityClickSoon() {
    if (releaseTimer !== null) globalThis.clearTimeout(releaseTimer);
    releaseTimer = setTimeout(() => {
      releaseTimer = null;
      claimThroughClick = false;
    });
  }

  function setDrawMode(on, { spoken = true } = {}) {
    on = Boolean(on);
    if (on) {
      setDesignMode(false, { spoken: false });
      closeTargetChooser();
      closeReactionMode();
    }
    drawModeOn = on;
    session = null;
    if (!on) {
      stroke = null;
      // Escape can leave while the pointer remains down. Keep claiming that physical
      // press through its compatibility click; only the drawing itself stops.
      if (claimedPointer === null) claimThroughClick = false;
    }
    document.body.toggleAttribute("data-lf-draw-mode", on);
    banner.toggleAttribute("data-lf-draw-mode", on);
    refreshAim();
    if (spoken)
      announce(
        on
          ? "Draw mode: draw anywhere on the page; each stroke adds to one drawing. Escape leaves."
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

  // The drawing the session's draft holds: the draft on the session's anchor, or the page
  // draft. Read off the durable drafts rather than remembered here or read off a box on
  // screen, because a send, a discard or another tab can settle a draft between strokes,
  // and putting its box away does not.
  function heldDrawing() {
    if (!session) return null;
    return session.anchor ? anchoredDrawing(session.anchor) : pageDrawing();
  }

  // A joining stroke keeps the drawing's frame wherever it starts: the session's anchor, or
  // the document for a page drawing. When that anchor's element has gone the drawing
  // cannot be extended, so there is no frame and the stroke starts a drawing of its own.
  function sessionTarget() {
    if (!session.anchor) return { anchor: null, element: null };
    const found = resolveAnchor(session.anchor, "");
    return found?.status !== "outdated" && found?.element
      ? { anchor: session.anchor, element: found.element }
      : null;
  }

  function strokeFrom(points, targetBox) {
    const origin = targetBox
      ? documentPoint(targetBox.left, targetBox.top)
      : { left: 0, top: 0 };
    return points.map(({ left, top }) => [
      rounded(
        clamp(left - origin.left, -DRAWING_COORDINATE_LIMIT, DRAWING_COORDINATE_LIMIT),
      ),
      rounded(
        clamp(top - origin.top, -DRAWING_COORDINATE_LIMIT, DRAWING_COORDINATE_LIMIT),
      ),
    ]);
  }

  const drawingOf = (held, { points, box }) => ({
    format: DRAWING_FORMAT,
    strokes: [...(held?.strokes ?? []), strokeFrom(points, box)],
  });

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
    if (!drawModeOn || !event.isPrimary || event.button !== 0) return;
    const origin = event.composedPath()[0];
    // Inline conversations remain comment controls even when a shadow host seats them
    // in the page, so ownership follows the composed origin.
    if (inChrome(origin) || closestAcross(origin, ".lf-conversation")) return;
    claimThroughClick = true;
    claimedPointer = event.pointerId;
    claim(event);
    const held = heldDrawing();
    if (held && held.strokes.length >= MAX_DRAWING_STROKES) {
      announce(
        `A drawing holds ${MAX_DRAWING_STROKES} strokes. Send this one to start another.`,
      );
      return;
    }
    const joined = held ? sessionTarget() : null;
    const target = joined ?? targetAtPointer();
    const box = target?.element ? shownBox(target.element) : null;
    if (!target || (target.element && (!box?.width || !box?.height))) {
      announce("Draw on the page.");
      return;
    }
    event.target.setPointerCapture(event.pointerId);
    stroke = {
      anchor: target.anchor,
      box,
      distance: 0,
      joins: Boolean(joined),
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
      announce("Stroke canceled because its page element changed.");
      return;
    }
    if (completed.distance < MIN_GESTURE || completed.points.length < 2) {
      shiftDrawingPaint();
      announce("Drag to draw; a click leaves no mark.");
      return;
    }
    // Read again at the release: a draft settled mid-stroke leaves this stroke to start
    // a drawing of its own, in the frame it was already drawn in.
    const held = completed.joins ? heldDrawing() : null;
    const drawing = drawingOf(held, completed);
    session = { anchor: completed.anchor };
    if (completed.anchor) openAnchoredDrawing(completed.anchor, drawing);
    else openPageDrawing(drawing);
    announce(
      held
        ? "Stroke added to the drawing."
        : "Drawing captured. Draw more strokes, add words, or send it.",
    );
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
    announce("Stroke canceled. Draw mode is still on.");
  }

  const compatibilityPress = (event) => {
    if (claimThroughClick) claim(event);
  };

  // The drawing as it will stand when this stroke lifts, earlier strokes included, so the
  // strokes already drawn stay on screen while the next one is drawn.
  function activeDrawing() {
    if (!stroke || stroke.points.length < 2) return null;
    return {
      drawing: drawingOf(stroke.joins ? heldDrawing() : null, stroke),
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
    drawModeOn = false;
    stroke = null;
    session = null;
    claimThroughClick = false;
    claimedPointer = null;
    document.body.removeAttribute("data-lf-draw-mode");
    banner.removeAttribute("data-lf-draw-mode");
  }

  // Draw mode claims pointer strokes and hands their marks to an ordinary comment. Its own
  // scope keeps the toggle and Escape as the two ways out while the page underneath
  // remains the drawing surface rather than receiving the drag.
  pageScope("draw mode", {
    title: "In Draw mode",
    at: drawModeActive,
    rows: [
      {
        id: "draw.mode.stroke",
        keys: [],
        label: "drag",
        does: "Draw anywhere on the page; each stroke adds to one drawing",
      },
      {
        id: "draw.mode.exit",
        keys: ["w"],
        does: "Exit Draw mode",
        line: "exit Draw mode",
        run: () => setDrawMode(false),
      },
    ],
  });
  // As Design mode's: the drawing surface is state over the page, so it comes off the
  // ladder after anything standing over it and before the page itself.
  pageRung("draw mode", () =>
    drawModeActive()
      ? {
          says: "exit Draw mode",
          does: "Exit Draw mode",
          out: () => setDrawMode(false),
        }
      : null,
  );
  pageCommand({
    id: "draw.mode.enter",
    keys: ["w"],
    does: "Draw on the page and attach the drawing to a comment",
    line: "draw",
    when: () => anchoringIsReady(),
    run: () => setDrawMode(true),
  });

  return {
    mount,
    destroy,
    drawModeActive,
    setDrawMode,
    activeDrawing,
    draftDrawings,
  };
}
