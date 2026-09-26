/* Drawing gesture controller.
 *
 * Draw mode claims primary-pointer drags anywhere on the page until the user leaves it.
 * Every drawing belongs to a comment draft. A semantic target under or horizontally
 * alongside a stroke's first point names its anchored draft and remains the thread
 * coordinate; a stroke with none belongs to the page draft. A stroke joins the drawing its
 * draft already holds, in that drawing's frame, so neither putting the box away nor
 * leaving Draw mode loses ink; once the draft is sent or discarded, the next stroke starts
 * another. Within one Draw mode session, each stroke after the first goes to the first
 * stroke's draft wherever it starts, while that draft holds a drawing. The controller owns
 * pointer capture, stroke sampling, and mode state. SVG replay, anchor placement,
 * composers, reactions, and page geometry enter through explicit capabilities, and the
 * drafts are the one record of the strokes already drawn. As each stroke lifts, the
 * controller also reads the page's words the drawing stands over into the record, for
 * whoever reads the comment without the page.
 */

import { clippedContents, documentPoint, shownBox } from "../geometry.js";
import { clamp, overlaps } from "../rect.js";
import {
  closestAcross,
  COLLAPSE,
  cut,
  elementFromPointAcross,
  elementOver,
  inChrome,
  quoteFrom,
  textNodesUnder,
} from "../passages.js";
import { anchoringIsReady } from "../anchor-resolution.js";
import { pressIsKeyboardActivation } from "../pointer.js";
import { pageCommand, pageRung, pageScope } from "../keyboard/register.js";
import {
  DRAWING_COORDINATE_LIMIT,
  DRAWING_FORMAT,
  MAX_DRAWING_POINTS,
  MAX_DRAWING_STROKES,
  MAX_DRAWING_SAYS_LENGTH,
} from "./drawing-record.js";

const MIN_DISTANCE = 2;
const MIN_GESTURE = 4;
const PRESS_EVENTS = ["mousedown", "mouseup", "click", "dblclick"];

const rounded = (value) => Number(value.toFixed(4));

// Where each word of a text node starts and ends, split on the class the page's own
// reading collapses, so a word here is a word in a quote.
function wordsOf(data) {
  const words = [];
  let from = 0;
  for (const gap of data.matchAll(COLLAPSE)) {
    if (gap.index > from) words.push([from, gap.index]);
    from = gap.index + gap[0].length;
  }
  if (from < data.length) words.push([from, data.length]);
  return words;
}

// How far above its ink a drawing reaches for words: an underline stands below its word.
const UNDERLINE_REACH = 8;

// The page's words a drawing stands over, for whoever reads the comment without the page
// in front of them: from the first shown word inside the ink's extents to the last, as the
// page reads a quote. That is more than the ink marked, since an arrow says the paragraph
// it crosses, and the user's own words say which part they meant. A word counts by the
// part of it the page shows: a row scrolled out of its container lies under the ink's
// coordinates and under none of its pixels.
function wordsUnder(ink) {
  const xs = ink.map(([x]) => x);
  const ys = ink.map(([, y]) => y);
  const extent = {
    left: Math.min(...xs),
    right: Math.max(...xs),
    top: Math.min(...ys) - UNDERLINE_REACH,
    bottom: Math.max(...ys),
  };
  const clips = new Map();
  const range = document.createRange();
  const segments = textNodesUnder(document.body);
  let first = null;
  let last = null;
  segments.forEach(({ node }, at) => {
    range.selectNodeContents(node);
    if (![...range.getClientRects()].some((rect) => overlaps(extent, rect))) return;
    const holder = elementOver(node);
    for (const [start, end] of wordsOf(node.data)) {
      range.setStart(node, start);
      range.setEnd(node, end);
      const shown = [...range.getClientRects()].some((rect) => {
        const box = clippedContents(rect, holder, clips);
        return box && overlaps(extent, box);
      });
      if (!shown) continue;
      last = { at, start, end };
      first ??= last;
    }
  });
  if (!first) return "";
  return quoteFrom(
    segments.slice(first.at, last.at + 1).map(({ node }, index, all) => ({
      node,
      start: index ? 0 : first.start,
      end: index === all.length - 1 ? last.end : node.data.length,
    })),
  );
}

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
  // The draft this session's first stroke went to: its anchor, or null for the page draft.
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

  // The drawing a draft already holds: the anchored draft's, or the page draft's. Read off
  // the durable drafts rather than remembered here or read off a box on screen, because a
  // send, a discard or another tab can settle a draft between strokes, and putting its box
  // away or leaving Draw mode does not.
  const heldDrawing = (anchor) => (anchor ? anchoredDrawing(anchor) : pageDrawing());

  // A later stroke of the session goes to the first stroke's draft wherever it starts, in
  // that drawing's frame, while the draft holds it. Null leaves the stroke to the draft
  // under the pointer: before the session's first stroke, once its draft has settled, or
  // when its anchor's element has gone and the frame with it.
  function sessionTarget() {
    if (!session || !heldDrawing(session.anchor)) return null;
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

  // The drawing's geometry, and the size of the box its offsets were drawn in, which is
  // what places a mark on a picture that has no words.
  function drawingOf(held, { points, box }) {
    return {
      format: DRAWING_FORMAT,
      strokes: [...(held?.strokes ?? []), strokeFrom(points, box)],
      ...(box && { box: [rounded(box.width), rounded(box.height)] }),
    };
  }

  // What the drawing stands over is read as each stroke lifts, over every stroke so far:
  // the reading walks the page's text, and the geometry above is rebuilt on every frame of
  // a stroke.
  function captured(held, completed) {
    const drawing = drawingOf(held, completed);
    const origin = completed.box ?? { left: -scrollX, top: -scrollY };
    const said = wordsUnder(
      drawing.strokes.flat().map(([x, y]) => [origin.left + x, origin.top + y]),
    );
    if (!said) return drawing;
    const says =
      [...said].length > MAX_DRAWING_SAYS_LENGTH
        ? `${cut(said, 0, MAX_DRAWING_SAYS_LENGTH - 1)}…`
        : said;
    return { ...drawing, says };
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
    if (!drawModeOn || !event.isPrimary || event.button !== 0) return;
    const origin = event.composedPath()[0];
    // Inline threads remain comment controls even when a shadow host seats them
    // in the page, so ownership follows the composed origin.
    if (inChrome(origin) || closestAcross(origin, ".lf-thread-seat")) return;
    claimThroughClick = true;
    claimedPointer = event.pointerId;
    claim(event);
    const target = sessionTarget() ?? targetAtPointer();
    const box = target?.element ? shownBox(target.element) : null;
    if (!target || (target.element && (!box?.width || !box?.height))) {
      announce("Draw on the page.");
      return;
    }
    if (heldDrawing(target.anchor)?.strokes.length >= MAX_DRAWING_STROKES) {
      announce(
        `A drawing holds ${MAX_DRAWING_STROKES} strokes. Send this one to start another.`,
      );
      return;
    }
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
      announce("Stroke canceled because its page element changed.");
      return;
    }
    if (completed.distance < MIN_GESTURE || completed.points.length < 2) {
      shiftDrawingPaint();
      announce("Drag to draw; a click leaves no mark.");
      return;
    }
    // Read at the release: a draft settled mid-stroke leaves this stroke to start a
    // drawing of its own, in the frame it was already drawn in.
    const held = heldDrawing(completed.anchor);
    const drawing = captured(held, completed);
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

  // The presses a claimed pointer's own sequence still owes the page, swallowed so a
  // stroke that ended over a control does not also activate it. The claim stands over
  // the whole document until the stroke's compatibility events have passed, so it has to
  // say which presses it is for: a keyboard activation is not one of them (pointer.js).
  // Eating it silently lost the user's press — Ctrl+Enter on the composer the stroke
  // had just opened sent nothing, and nothing said so.
  const compatibilityPress = (event) => {
    if (claimThroughClick && !pressIsKeyboardActivation(event)) claim(event);
  };

  // The drawing as it will stand when this stroke lifts, earlier strokes included, so the
  // strokes already drawn stay on screen while the next one is drawn.
  function activeDrawing() {
    if (!stroke || stroke.points.length < 2) return null;
    return {
      drawing: drawingOf(heldDrawing(stroke.anchor), stroke),
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
