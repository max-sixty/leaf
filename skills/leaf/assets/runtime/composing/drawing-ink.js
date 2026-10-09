/* Native drawing ink, independent of saved annotation presentation.
 *
 * The supplied reading names current drawings and their targets. This owner alone
 * reconciles SVG nodes, anchors their frames, observes their geometry and schedules
 * repaint. Every repaint rereads its producers, including active pointer strokes and
 * unsent drafts. Optional saved ink joins the same reading without another layer,
 * cache or observer; a page without that producer still draws its live gestures.
 *
 * Each mark stands in the frames that cut its target, anchored to it (paint stands,
 * target-paint-geometry.js), so every scroll that moves the target carries it without
 * extending the document's overflow, and a pane scrolling its target away cuts it at
 * its edge. Ink still being drawn is cut by nothing, since the pen goes where the
 * user puts it. Equal complete descriptions retain the actual SVG node.
 *
 * A mark keeps its local offsets from the target's origin through affine transforms.
 * Intrinsic visuals carry ink as their contents resize. HTML layout growth does not
 * stretch ink; text that reflows moves under a mark and can leave its circle.
 */

import { cancelRender, nextRender, sizeObserver } from "../rendering.js";
import { el } from "../widget-elements.js";
import { paintSet } from "../target-paint-geometry.js";
import { validDrawing } from "./drawing-record.js";
import { drawingGeometry } from "./drawing-geometry.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const FRAME_MIN = 1;

function drawingFrame(strokes) {
  const points = strokes.flat();
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
const pathData = (strokes) =>
  strokes
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

export function createDrawingInk({ drawings }) {
  // The draft or ordinary Thread is the accessible representation of its ink.
  const layer = el("div", "lf-ui lf-drawings");
  layer.setAttribute("aria-hidden", "true");
  const ink = paintSet(layer);
  let paintFrame = 0;
  let mounted = new Map();
  let mounting = new Map();
  const observed = new Set();
  const sizes = sizeObserver(() => shifted());

  // The complete description is the retained-node key. Two equal marks in one pass
  // still consume distinct prior nodes in order.
  function mark(drawing, target, className, id = "") {
    if (!validDrawing(drawing)) return null;
    const geometry = drawingGeometry(drawing, target);
    if (!geometry) return null;
    const { box, strokes } = geometry;
    const frame = drawingFrame(strokes);
    const { width, height } = frame;
    if (!width || !height) return null;
    const rect = {
      left: box.left + frame.x,
      top: box.top + frame.y,
      right: box.left + frame.x + width,
      bottom: box.top + frame.y + height,
    };
    const data = pathData(strokes);
    const described = JSON.stringify([className, id, frame, data]);
    const item = {
      target: geometry.target,
      rect,
      cut: className !== "lf-drawing-active",
    };
    const standing = mounted.get(described)?.shift();
    const svg = standing ?? document.createElementNS(SVG_NS, "svg");
    const next = mounting.get(described) ?? [];
    next.push(svg);
    mounting.set(described, next);
    if (standing) return { ...item, node: svg };
    svg.classList.add("lf-drawing-mark", className);
    if (id) svg.dataset.thread = id;
    svg.setAttribute("viewBox", `${frame.x} ${frame.y} ${frame.width} ${frame.height}`);
    svg.setAttribute("preserveAspectRatio", "none");
    svg.setAttribute("aria-hidden", "true");
    svg.append(pathFor(data));
    return { ...item, node: svg };
  }

  function paint() {
    const nextObserved = new Set();
    const marks = [];
    mounting = new Map();
    for (const { drawing, target, className, id } of drawings()) {
      const painted = mark(drawing, target, className, id);
      if (painted) {
        marks.push(painted);
        nextObserved.add(painted.target);
      }
    }

    // Unchanged ink keeps its node, and the set writes only where it moved.
    ink.place(marks);
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
    ink.clear();
  }

  return { layer, paint, shifted, destroy };
}
