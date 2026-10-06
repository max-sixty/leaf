/* Drawing gesture controller.
 *
 * Draw mode claims primary-pointer drags anywhere on the page until the user leaves it.
 * Every drawing belongs to a comment draft. A semantic target under or horizontally
 * alongside a stroke's first point names its anchored draft and remains the thread
 * coordinate; a stroke with none belongs to the page draft. A stroke joins the drawing its
 * draft already holds, in that drawing's frame, so neither putting the box away nor
 * leaving Draw mode loses ink; once the draft is sent or its drawing removed, the next
 * stroke starts another. Within one Draw mode session, each stroke after the first goes
 * to the first stroke's draft wherever it starts, while that draft holds a drawing.
 *
 * Ink the user has drawn and not sent stands on the page until they send it or take it
 * back, whether or not its composer is up and whether or not Draw mode is: a drawing that
 * vanished with its box and came back whole with the next stroke read as one deleted and
 * then one that could not be. The open composer's drawing is drawn as pending, the others
 * as parked. `z` or ⌘Z in Draw mode takes back the last stroke drawn; a composer's ⌘Z,
 * while strokes are its draft's latest change, and its own control take back its own
 * drawing's. Taking back the last stroke removes the drawing, as the composer's removal
 * does at once.
 *
 * The controller owns pointer capture, stroke sampling, mode state and stroke undo. SVG
 * replay, anchor placement, composers, reactions, and page geometry enter through
 * explicit capabilities, and the drafts are the one record of the strokes already drawn.
 * As each stroke lifts or is taken back, the controller also reads the page's words the
 * drawing stands over into the record, for whoever reads the comment without the page.
 */

import { targetElement, targetPlace } from "../resolved-target.js";
import { clippedContents, documentPoint, shownBox } from "../geometry.js";
import { clamp, overlaps } from "../rect.js";
import { COLLAPSE } from "../collapse.js";
import {
  cut,
  elementFromPointAcross,
  elementOver,
  leafSurface,
  pageText,
  quoteFrom,
} from "../passages.js";
import { anchoringIsReady } from "../anchor-resolution.js";
import { coarsePointer, pressIsKeyboardActivation } from "../pointer.js";
import { shownScheme } from "../color-scheme.js";
import { pageCommand, pageRung, pageScope } from "../keyboard/register.js";
import {
  DRAWING_COORDINATE_LIMIT,
  DRAWING_FORMAT,
  MAX_DRAWING_POINTS,
  MAX_DRAWING_STROKES,
  MAX_DRAWING_SAYS_LENGTH,
  strokesIn,
} from "./drawing-record.js";

const MIN_DISTANCE = 2;
const MIN_GESTURE = 4;
const PRESS_EVENTS = ["mousedown", "mouseup", "click", "dblclick"];
const UNDO_STROKE = ["z", "Mod+z"];

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
  const { segments } = pageText();
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
    segments.slice(first.at, last.at + 1).map((segment, index, all) => ({
      ...segment,
      start: index ? segment.start : first.start,
      end: index === all.length - 1 ? last.end : segment.end,
    })),
  );
}

export function createDrawingController({
  anchors: { aimTargetAt, resolveAnchor },
  pageGeometry: { refreshAim },
  pointer,
  visibleTargets,
  pageDrawing,
  pageComposerOpen,
  anchoredDrawing,
  heldDrawings,
  watchHeldDrawings,
  draftKey,
  openAnchoredDrawing,
  openPageDrawing,
  replaceDrawing,
  setDesignMode,
  closeTargetPicker,
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
  // The draft the latest stroke went to, which an undo takes it back from. Unlike the
  // session, it outlasts Draw mode: leaving the mode does not change what was drawn last.
  let lastDrawn = null;
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
      closeTargetPicker();
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
    document.documentElement.toggleAttribute("data-lf-draw-mode", on);
    banner.toggleAttribute("data-lf-draw-mode", on);
    refreshAim();
    if (spoken)
      announce(
        on
          ? `Draw mode: draw anywhere on the page; each stroke adds to one drawing, and z takes one back. ${
              coarsePointer.matches
                ? "Exit Draw mode on the banner leaves."
                : "Escape leaves."
            }`
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
    if (!at || leafSurface(at)) return null;
    return (
      aimTargetAt(at) ?? targetAlongside(atPointer) ?? { anchor: null, element: null }
    );
  }

  // The drawing a draft already holds: the anchored draft's, or the page draft's. Read off
  // the durable drafts rather than remembered here or read off a box on screen, because a
  // send, a removal or another tab can settle a draft between strokes, and putting its box
  // away or leaving Draw mode does not.
  const heldDrawing = (anchor) => (anchor ? anchoredDrawing(anchor) : pageDrawing());
  const sameDraft = (left, right) =>
    left === right || Boolean(left && right && draftKey(left) === draftKey(right));

  // Where an anchored drawing stands now: its target, or null once the target has gone or
  // its data moved on, which leaves the drawing nowhere to be drawn or reframed.
  function targetOf(anchor) {
    const found = resolveAnchor(anchor, "");
    return found && found.status !== "outdated"
      ? (targetElement(found) ?? targetPlace(found))
      : null;
  }

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

  // A stroke's points after the drawing its draft holds. Strokes drawn before the target
  // resized are scaled to its current size, so all the strokes share one box.
  const strokesWith = (held, { points, box }) => [
    ...(held ? strokesIn(held, box) : []),
    strokeFrom(points, box),
  ];

  // The drawing's geometry, and the size of the box its offsets were drawn in, which is
  // what places a mark on a picture that has no words. The window is read with the box,
  // so the two describe the same layout: the one the agent's picture of the comment lays
  // the page out in again.
  function drawingOf(strokes, box) {
    const { clientWidth, clientHeight } = document.documentElement;
    return {
      format: DRAWING_FORMAT,
      strokes,
      ...(box && { box: [rounded(box.width), rounded(box.height)] }),
      viewport: [clientWidth, clientHeight],
      scheme: shownScheme(),
    };
  }

  // What the drawing stands over is read as each stroke lifts or is taken back, over
  // every stroke it then holds: the reading walks the page's text, and the geometry above
  // is rebuilt on every frame of a stroke.
  function captured(strokes, box) {
    const drawing = drawingOf(strokes, box);
    const origin = box ?? { left: -scrollX, top: -scrollY };
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
    // Runtime surfaces remain operable wherever their owner seats them.
    if (leafSurface(origin)) return;
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
        `A drawing holds ${MAX_DRAWING_STROKES} strokes. Undo a stroke, or send or remove this drawing to start another.`,
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
    const drawing = captured(strokesWith(held, completed), completed.box);
    session = { anchor: completed.anchor };
    lastDrawn = { anchor: completed.anchor };
    if (completed.anchor) openAnchoredDrawing(completed.anchor, drawing);
    else openPageDrawing(drawing);
    announce(
      held
        ? "Stroke added to the drawing."
        : "Drawing captured. Draw more strokes, add words, or send it.",
    );
  }

  // The draft Draw mode's undo takes a stroke from: the one the latest stroke went to,
  // while its ink stands on the page, or else the drawing an open composer carries. A
  // composer's own undo takes from its own draft.
  function undoTarget() {
    if (
      lastDrawn &&
      heldDrawing(lastDrawn.anchor) &&
      (!lastDrawn.anchor || targetOf(lastDrawn.anchor))
    )
      return lastDrawn;
    const open = heldDrawings().find((held) => held.open);
    if (open) return { anchor: open.anchor };
    return pageComposerOpen() && pageDrawing() ? { anchor: null } : null;
  }

  // Take back a drawing's last stroke: the named draft's, from its composer's control, or
  // the undo target's. The record loses its last stroke in its own frame, so a drawing
  // whose element has gone can still be taken apart from its box. Where the element is
  // shown, the remaining strokes are reframed in its current box and read again for the
  // words they stand over; where it is not, the words go, since they spoke for strokes
  // that are no longer all there. The last stroke taken back takes the drawing with it.
  function undoStroke(anchor = undoTarget()?.anchor) {
    const held = anchor !== undefined && heldDrawing(anchor);
    if (!held) {
      announce("No stroke to undo.");
      return;
    }
    const target = anchor ? targetOf(anchor) : null;
    const box = target && shownBox(target);
    const shown = !anchor || Boolean(box?.width && box?.height);
    const strokes = (shown ? strokesIn(held, box) : held.strokes).slice(0, -1);
    const { says, ...unread } = held;
    replaceDrawing(
      anchor,
      !strokes.length ? null : shown ? captured(strokes, box) : { ...unread, strokes },
    );
    announce(
      strokes.length
        ? `Stroke undone; ${strokes.length} left.`
        : "Last stroke undone; drawing removed.",
    );
  }

  function removeDrawing(anchor) {
    if (!heldDrawing(anchor)) return;
    replaceDrawing(anchor, null);
    announce("Drawing removed.");
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
      drawing: drawingOf(strokesWith(heldDrawing(stroke.anchor), stroke), stroke.box),
      target: stroke.target,
      className: "lf-drawing-active",
    };
  }

  // Every unsent drawing but the one `drawing` is adding to, which that stroke draws.
  function draftDrawings(drawing) {
    const drawings = [];
    const state = (open) => (open ? "lf-drawing-pending" : "lf-drawing-parked");
    const page = pageDrawing();
    if (page && drawing?.anchor !== null)
      drawings.push({
        drawing: page,
        target: null,
        className: state(pageComposerOpen()),
      });
    for (const { anchor, drawing: held, open } of heldDrawings()) {
      if (drawing && sameDraft(anchor, drawing.anchor)) continue;
      const target = targetOf(anchor);
      if (target) drawings.push({ drawing: held, target, className: state(open) });
    }
    return drawings;
  }

  // Another tab's change to any draft's drawing, put away here or not, repaints its ink.
  let stopWatching = () => {};

  function mount() {
    if (mounted) return;
    mounted = true;
    stopWatching = watchHeldDrawings(() => shiftDrawingPaint());
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
      stopWatching();
    }
    mounted = false;
    if (releaseTimer !== null) globalThis.clearTimeout(releaseTimer);
    releaseTimer = null;
    drawModeOn = false;
    stroke = null;
    session = null;
    lastDrawn = null;
    claimThroughClick = false;
    claimedPointer = null;
    document.documentElement.removeAttribute("data-lf-draw-mode");
    banner.removeAttribute("data-lf-draw-mode");
  }

  // Draw mode claims pointer strokes and hands their marks to an ordinary comment. Its own
  // scope keeps the toggle and Escape as the two ways out while the page underneath
  // remains the drawing surface rather than receiving the drag.
  pageScope("draw mode", {
    title: "In Draw mode",
    at: drawModeActive,
    // Undo here is the stroke's, so with no stroke to take back the press does nothing
    // rather than falling through to undo a gesture the user made outside the mode.
    claims: (binding) => UNDO_STROKE.includes(binding),
    rows: [
      {
        id: "draw.mode.stroke",
        keys: [],
        label: "drag",
        title: "Draw on the page",
        description: "Each stroke adds to one drawing",
        line: false,
      },
      {
        id: "draw.mode.undo",
        keys: UNDO_STROKE,
        title: "undo stroke",
        description: "Take back the last stroke drawn",
        touch: "Undo stroke",
        when: () => Boolean(undoTarget()),
        run: () => undoStroke(),
      },
      {
        id: "draw.mode.exit",
        keys: ["w"],
        title: "exit Draw mode",
        touch: "Exit Draw mode",
        // Escape's step says the same on the line.
        line: false,
        run: () => setDrawMode(false),
      },
    ],
  });
  // As Design mode's: the drawing surface is state over the page, so it comes off the
  // ladder after anything standing over it and before the page itself.
  pageRung("draw mode", () =>
    drawModeActive()
      ? {
          title: "exit Draw mode",

          out: () => setDrawMode(false),
        }
      : null,
  );
  pageCommand({
    id: "draw.mode.enter",
    keys: ["w"],
    description: "Draw on the page and attach the drawing to a comment",
    title: "draw mode",
    touch: "Draw mode",
    when: () => anchoringIsReady() && !drawModeOn,
    run: () => setDrawMode(true),
  });

  return {
    mount,
    destroy,
    drawModeActive,
    setDrawMode,
    undoStroke,
    removeDrawing,
    drawings: () => {
      const active = activeDrawing();
      return [...draftDrawings(active && stroke), ...(active ? [active] : [])];
    },
  };
}
