/* One-stroke drawing comments.
 *
 * Drawing mode claims one primary-pointer drag anywhere on the page. A semantic target
 * under or horizontally alongside its first point remains the conversation coordinate;
 * otherwise the drawing is a page comment. A stroke-sized frame may extend anywhere
 * across the page plane. The stroke then enters the existing comment composer, so drafts,
 * admission, delivery, replies, and settlement stay on the one conversation path. Its
 * words are optional because the drawing is itself content.
 *
 * Ink is always rendered by Leaf. Events carry no SVG, colour, width, or style supplied
 * by the browser. The current theme's accent is the only brush. */

import {
  aimTargetAt,
  pendingAt,
  placedAt,
  refreshAim,
  resolveAnchor,
} from "../anchors.js";
import { banner } from "../banner.js";
import { openPageDrawing, pageComposerDrawing } from "../conversation/panel.js";
import { setDesign } from "../design.js";
import { documentPoint, shownBox } from "../geometry.js";
import { paintHere } from "../keyboard/scopes.js";
import { announce } from "../notifications.js";
import { closestAcross, elementFromPointAcross, inChrome } from "../passages.js";
import { pointerAt } from "../pointer.js";
import { setReact } from "../reactions.js";
import { el } from "../widget-elements.js";
import {
  composerOpen,
  openComposer,
  pendingAnchor,
  pendingDrawing,
} from "./selection.js";
import { stopSelecting, visibleTargets } from "./targets.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const FORMAT = "leaf-drawing/1";
const MAX_POINTS = 256;
const MIN_DISTANCE = 2;
const MIN_GESTURE = 4;
// Chromium caps one layout dimension at 2^25 CSS pixels. The event boundary shares
// that limit, which covers every point the browser can place while still bounding SVG
// geometry supplied to replay.
const COORDINATE_LIMIT = 33554432;
const FRAME_MIN = 1;

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const rounded = (value) => Number(value.toFixed(4));

export function validDrawing(drawing) {
  return Boolean(
    drawing &&
    typeof drawing === "object" &&
    !Array.isArray(drawing) &&
    Object.keys(drawing).every((key) => ["format", "points"].includes(key)) &&
    drawing.format === FORMAT &&
    Array.isArray(drawing.points) &&
    drawing.points.length >= 2 &&
    drawing.points.length <= MAX_POINTS &&
    drawing.points.every(
      (point) =>
        Array.isArray(point) &&
        point.length === 2 &&
        point.every(
          (coordinate) =>
            Number.isFinite(coordinate) &&
            coordinate >= -COORDINATE_LIMIT &&
            coordinate <= COORDINATE_LIMIT,
        ),
    ),
  );
}

function drawingFrame(drawing) {
  const xs = drawing.points.map(([x]) => x);
  const ys = drawing.points.map(([, y]) => y);
  const left = Math.min(...xs);
  const right = Math.max(...xs);
  const top = Math.min(...ys);
  const bottom = Math.max(...ys);
  const width = Math.max(right - left, FRAME_MIN);
  const height = Math.max(bottom - top, FRAME_MIN);
  return {
    x: (left + right - width) / 2,
    y: (top + bottom - height) / 2,
    width,
    height,
  };
}

function pathData(drawing) {
  return drawing.points
    .map(([x, y], index) => `${index ? "L" : "M"} ${x.toFixed(4)} ${y.toFixed(4)}`)
    .join(" ");
}

function pathFor(drawing) {
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", pathData(drawing));
  path.setAttribute("fill", "none");
  path.setAttribute("vector-effect", "non-scaling-stroke");
  return path;
}

// Reader-drawn evidence is paint only. The ordinary thread remains its accessible and
// interactive representation.
export const drawingLayer = el("div", "lf-ui lf-drawings lf-page-paint");
drawingLayer.setAttribute("aria-hidden", "true");

export let drawingOn = false;
export function isDrawing() {
  return drawingOn;
}
let stroke = null;
let claimThroughClick = false;
let claimedPointer = null;
let lastThreads = [];
let paintFrame = 0;
const observed = new Set();
const sizes = new ResizeObserver(() => queuePaint());

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
  const pointer = pointerAt();
  if (pointer.x < 0) return null;
  const at = elementFromPointAcross(pointer.x, pointer.y);
  if (!at || inChrome(at)) return null;
  return aimTargetAt(at) ?? targetAlongside(pointer) ?? { anchor: null, element: null };
}

export function setDrawing(on, { spoken = true, keepPress = false } = {}) {
  on = Boolean(on);
  if (on) {
    setDesign(false, { spoken: false });
    stopSelecting();
    setReact(false);
  }
  drawingOn = on;
  if (!on && !keepPress) {
    stroke = null;
    // Escape may leave the mode while the pointer is still down. Keep claiming that
    // physical press through its compatibility click; only the drawing itself stops.
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
  paintHere();
}

function drawingFrom(points, targetBox) {
  const origin = targetBox
    ? documentPoint(targetBox.left, targetBox.top)
    : { left: 0, top: 0 };
  const targetPoints = points.map(({ left, top }) => [
    rounded(clamp(left - origin.left, -COORDINATE_LIMIT, COORDINATE_LIMIT)),
    rounded(clamp(top - origin.top, -COORDINATE_LIMIT, COORDINATE_LIMIT)),
  ]);
  return {
    format: FORMAT,
    points: targetPoints,
  };
}

function rememberPoint(x, y) {
  if (!stroke || stroke.invalid) return false;
  if (stroke.anchor) {
    // A data or widget projection may replace the target during pointer capture. Resolve
    // the semantic anchor again so the stroke follows a valid replacement and cancels
    // instead of deriving coordinates from a disconnected element.
    const found = resolveAnchor(stroke.anchor, "");
    const target = found?.status !== "outdated" ? found?.element : null;
    const box = target && shownBox(target);
    if (!box?.width || !box?.height) {
      stroke.invalid = true;
      queuePaint();
      return false;
    }
    stroke.target = target;
    stroke.box = box;
  }
  const screen = { x, y };
  const prior = stroke.lastScreen;
  if (prior) {
    const distance = Math.hypot(x - prior.x, y - prior.y);
    if (distance < MIN_DISTANCE) return;
    stroke.distance += distance;
  }
  stroke.lastScreen = screen;
  // Keep every sample in the document plane, then choose one target-relative
  // origin when the drawing is framed. If layout moves the target during the
  // drag, old and new samples therefore never mix coordinate bases.
  stroke.points.push(documentPoint(x, y));
  // Keep the whole gesture while progressively lowering its sampling resolution.
  // The latest point always survives, so a long stroke cannot turn into a line from
  // its beginning to wherever the first 256 pointer events happened to end.
  if (stroke.points.length > MAX_POINTS)
    stroke.points = stroke.points.filter(
      (_point, index, points) => index % 2 === 0 || index === points.length - 1,
    );
  queuePaint();
  return true;
}

function claim(event) {
  event.preventDefault();
  event.stopImmediatePropagation();
}

function begin(event) {
  if (!drawingOn || !event.isPrimary || event.button !== 0) return;
  const origin = event.composedPath()[0];
  // An inline conversation is Leaf's comment surface even when a widget's shadow root
  // seats it in the page. Document dispatch retargets that press to the widget host, so
  // ownership must follow the composed origin across the shadow boundary.
  if (inChrome(origin) || closestAcross(origin, ".lf-conversation")) return;
  claimThroughClick = true;
  claimedPointer = event.pointerId;
  // Resolve at the exact point that begins the stroke. Event dispatch and
  // elementFromPoint have different seam tie-breaks, so event.target could attach a
  // stroke along a joined-option seam to its neighbour.
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
      setTimeout(() => {
        claimThroughClick = false;
      });
    }
    return;
  }
  claim(event);
  rememberPoint(event.clientX, event.clientY);
  const completed = stroke;
  stroke = null;
  claimedPointer = null;
  setTimeout(() => {
    claimThroughClick = false;
  });
  if (completed.invalid) {
    queuePaint();
    announce("Drawing canceled because its page item changed.");
    return;
  }
  if (completed.distance < MIN_GESTURE || completed.points.length < 2) {
    queuePaint();
    announce("Drag to draw; a click leaves no mark.");
    return;
  }
  const drawing = drawingFrom(completed.points, completed.box);
  setDrawing(false, { spoken: false, keepPress: true });
  if (completed.anchor) openComposer(completed.anchor, "", { carry: true, drawing });
  else openPageDrawing(drawing);
  announce("Drawing captured. Send it or add words to the comment.");
}

function cancel(event) {
  if (!stroke || event.pointerId !== stroke.pointerId) {
    if (event.pointerId === claimedPointer) {
      claim(event);
      claimedPointer = null;
      setTimeout(() => {
        claimThroughClick = false;
      });
    }
    return;
  }
  claim(event);
  stroke = null;
  claimedPointer = null;
  setTimeout(() => {
    claimThroughClick = false;
  });
  queuePaint();
  announce("Drawing canceled. Draw mode is still on.");
}

document.addEventListener("pointerdown", begin, true);
document.addEventListener("pointermove", move, true);
document.addEventListener("pointerup", finish, true);
document.addEventListener("pointercancel", cancel, true);
for (const type of ["mousedown", "mouseup", "click", "dblclick"])
  document.addEventListener(
    type,
    (event) => {
      if (claimThroughClick) claim(event);
    },
    true,
  );

function mark(drawing, target, className, id = "") {
  if (!validDrawing(drawing)) return null;
  const box = target ? shownBox(target) : { left: -scrollX, top: -scrollY };
  if (target && (!box?.width || !box?.height)) return null;
  const frame = drawingFrame(drawing);
  const { width, height } = frame;
  if (!width || !height) return null;
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.classList.add("lf-drawing-mark", className);
  if (id) svg.dataset.thread = id;
  svg.setAttribute("viewBox", `${frame.x} ${frame.y} ${frame.width} ${frame.height}`);
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("aria-hidden", "true");
  Object.assign(svg.style, {
    left: `${box.left + frame.x}px`,
    top: `${box.top + frame.y}px`,
    width: `${width}px`,
    height: `${height}px`,
  });
  svg.append(pathFor(drawing));
  return svg;
}

function activeDrawing() {
  if (!stroke || stroke.points.length < 2) return null;
  return {
    drawing: drawingFrom(stroke.points, stroke.box),
    target: stroke.target,
  };
}

function draftDrawing() {
  if (pageComposerDrawing()) return { drawing: pageComposerDrawing(), target: null };
  if (!composerOpen || !pendingDrawing) return null;
  if (!pendingAnchor) return { drawing: pendingDrawing, target: null };
  const place = pendingAt();
  return place?.status !== "outdated" && place?.target
    ? { drawing: pendingDrawing, target: place.target }
    : null;
}

export function paintDrawings(threads = lastThreads) {
  lastThreads = threads;
  const nextObserved = new Set();
  const marks = [];
  for (const thread of threads) {
    if (thread.resolved || !thread.root.drawing) continue;
    const place = thread.root.anchor ? placedAt(thread.root.id) : null;
    if (thread.root.anchor && (!place || place.status === "outdated")) continue;
    const target = place ? (place.target ?? place.element) : null;
    const painted = mark(
      thread.root.drawing,
      target,
      "lf-drawing-posted",
      thread.root.id,
    );
    if (painted) {
      marks.push(painted);
      if (target) nextObserved.add(target);
    }
  }
  const active = activeDrawing();
  if (active) {
    const painted = mark(active.drawing, active.target, "lf-drawing-active");
    if (painted) {
      marks.push(painted);
      if (active.target) nextObserved.add(active.target);
    }
  } else {
    const draft = draftDrawing();
    if (draft) {
      const painted = mark(draft.drawing, draft.target, "lf-drawing-pending");
      if (painted) {
        marks.push(painted);
        if (draft.target) nextObserved.add(draft.target);
      }
    }
  }
  drawingLayer.replaceChildren(...marks);
  for (const target of observed)
    if (!nextObserved.has(target)) {
      sizes.unobserve(target);
      observed.delete(target);
    }
  for (const target of nextObserved)
    if (!observed.has(target)) {
      sizes.observe(target);
      observed.add(target);
    }
}

function queuePaint() {
  if (paintFrame) return;
  paintFrame = requestAnimationFrame(() => {
    paintFrame = 0;
    paintDrawings();
  });
}

export function drawingShifted() {
  queuePaint();
}
