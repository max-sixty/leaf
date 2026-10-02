/* Passive replay of user drawings.
 *
 * Gesture capture supplies the active and draft drawings. Thread presentation
 * supplies threads and readonly anchor placement. This module owns only SVG paint,
 * retained node identity, resize observation, and its scheduled geometry refresh.
 *
 * Each mark is fixed and anchored (CSS anchor positioning) to the box its target
 * anchors through, or to `main` for a drawing on the page as a whole, with its frame
 * written as insets from that anchor. The browser carries it through every scroll that
 * moves the anchor, a fixed box adds nothing to the document's scrollable overflow
 * however far a stroke reaches, and a repaint after a scroll finds every mark's
 * description unchanged and keeps the node it has.
 */

import { cancelRender, nextRender, sizeObserver } from "../rendering.js";
import { setChildren } from "../dom-children.js";
import { shownBox } from "../geometry.js";
import { atLayoutPrecision } from "../keeps.js";
import { el } from "../widget-elements.js";
import { anchorElement, anchorName } from "../anchor-names.js";
import { targetElement, targetPlace } from "../resolved-target.js";
import { validDrawing } from "./drawing-record.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const FRAME_MIN = 1;

function drawingFrame(drawing) {
  const points = drawing.strokes.flat();
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
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

// One path, one subpath per stroke: each stroke lifts the pen with its own move.
const pathData = (drawing) =>
  drawing.strokes
    .flatMap((stroke) =>
      stroke.map(
        ([x, y], index) => `${index ? "L" : "M"} ${x.toFixed(4)} ${y.toFixed(4)}`,
      ),
    )
    .join(" ");

function pathFor(data) {
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", data);
  path.setAttribute("fill", "none");
  path.setAttribute("vector-effect", "non-scaling-stroke");
  return path;
}

export function createDrawingPaint({ anchors, activeDrawing, draftDrawings }) {
  // The ordinary thread is the accessible and interactive representation of this paint.
  const layer = el("div", "lf-ui lf-drawings lf-page-paint");
  layer.setAttribute("aria-hidden", "true");
  let lastThreads = [];
  let paintFrame = 0;
  let mounted = new Map();
  let mounting = new Map();
  const observed = new Set();
  const sizes = sizeObserver(() => shifted());

  // The complete description is the retained-node key. Two equal marks in one pass
  // still consume distinct prior nodes in order.
  function mark(drawing, target, className, id = "") {
    if (!validDrawing(drawing)) return null;
    const box = target ? shownBox(target) : { left: -scrollX, top: -scrollY };
    if (target && (!box?.width || !box?.height)) return null;
    const frame = drawingFrame(drawing);
    const { width, height } = frame;
    if (!width || !height) return null;
    const holder = target
      ? anchorElement(target)
      : (document.querySelector("main") ?? document.body);
    const at = holder.getBoundingClientRect();
    const anchor = anchorName(holder);
    const left = atLayoutPrecision(box.left + frame.x - at.left);
    const top = atLayoutPrecision(box.top + frame.y - at.top);
    const data = pathData(drawing);
    const described = JSON.stringify([
      className,
      id,
      anchor,
      left,
      top,
      width,
      height,
      frame.x,
      frame.y,
      data,
    ]);
    const standing = mounted.get(described)?.shift();
    if (standing) {
      const next = mounting.get(described) ?? [];
      next.push(standing);
      mounting.set(described, next);
      return standing;
    }
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.classList.add("lf-drawing-mark", className);
    if (id) svg.dataset.thread = id;
    svg.setAttribute("viewBox", `${frame.x} ${frame.y} ${frame.width} ${frame.height}`);
    svg.setAttribute("preserveAspectRatio", "none");
    svg.setAttribute("aria-hidden", "true");
    Object.assign(svg.style, {
      positionAnchor: anchor,
      left: `calc(anchor(left) + ${left}px)`,
      top: `calc(anchor(top) + ${top}px)`,
      width: `${width}px`,
      height: `${height}px`,
    });
    svg.append(pathFor(data));
    const next = mounting.get(described) ?? [];
    next.push(svg);
    mounting.set(described, next);
    return svg;
  }

  function paint(threads = lastThreads) {
    lastThreads = threads;
    const nextObserved = new Set();
    const marks = [];
    mounting = new Map();
    for (const thread of threads) {
      if (thread.resolved || !thread.root.drawing) continue;
      const place = thread.root.anchor ? anchors.placedAt(thread.id) : null;
      if (thread.root.anchor && (!place || place.status === "outdated")) continue;
      const target = targetElement(place) ?? targetPlace(place);
      const painted = mark(thread.root.drawing, target, "lf-drawing-posted", thread.id);
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
      for (const draft of draftDrawings()) {
        const painted = mark(draft.drawing, draft.target, "lf-drawing-pending");
        if (painted) {
          marks.push(painted);
          if (draft.target) nextObserved.add(draft.target);
        }
      }
    }

    // Reconciliation leaves unchanged ink and anything holding it in the document.
    setChildren(layer, marks);
    mounted = mounting;
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

  function shifted() {
    if (paintFrame) return;
    paintFrame = nextRender(() => {
      paintFrame = 0;
      paint();
    });
  }

  function destroy() {
    if (paintFrame) cancelRender(paintFrame);
    paintFrame = 0;
    sizes.disconnect();
    observed.clear();
    mounted.clear();
    mounting.clear();
    lastThreads = [];
    layer.replaceChildren();
  }

  return { layer, paint, shifted, destroy };
}
