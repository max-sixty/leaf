/* Passive replay of reader drawings.
 *
 * Gesture capture supplies the active and draft drawings. Conversation presentation
 * supplies threads and readonly anchor placement. This module owns only SVG paint,
 * retained node identity, resize observation, and its scheduled geometry refresh.
 */

import { setChildren } from "../dom-children.js";
import { shownBox } from "../geometry.js";
import { el } from "../widget-elements.js";
import { validDrawing } from "./drawing-record.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const FRAME_MIN = 1;

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

const pathData = (drawing) =>
  drawing.points
    .map(([x, y], index) => `${index ? "L" : "M"} ${x.toFixed(4)} ${y.toFixed(4)}`)
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
  const sizes = new ResizeObserver(() => shifted());

  // The complete description is the retained-node key. Two equal marks in one pass
  // still consume distinct prior nodes in order.
  function mark(drawing, target, className, id = "") {
    if (!validDrawing(drawing)) return null;
    const box = target ? shownBox(target) : { left: -scrollX, top: -scrollY };
    if (target && (!box?.width || !box?.height)) return null;
    const frame = drawingFrame(drawing);
    const { width, height } = frame;
    if (!width || !height) return null;
    const left = box.left + frame.x;
    const top = box.top + frame.y;
    const data = pathData(drawing);
    const described = JSON.stringify([
      className,
      id,
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
      left: `${left}px`,
      top: `${top}px`,
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
      const place = thread.root.anchor ? anchors.placedAt(thread.root.id) : null;
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
    paintFrame = requestAnimationFrame(() => {
      paintFrame = 0;
      paint();
    });
  }

  function destroy() {
    if (paintFrame) cancelAnimationFrame(paintFrame);
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
