/* Native drawing ink, independent of saved annotation presentation.
 *
 * The supplied reading names current drawings and their targets. This owner alone
 * reconciles SVG nodes, anchors their frames, observes their geometry and schedules
 * repaint. Every repaint rereads its producers, including active pointer strokes and
 * unsent drafts. Optional saved ink joins the same reading without another layer,
 * cache or observer; a page without that producer still draws its live gestures.
 *
 * Paint stands follow each source through scroll and its ancestors' clipping bands
 * without extending document overflow. Equal descriptions retain the actual SVG node.
 *
 * A mark is drawn at its target's current size (`strokesIn`), so it stays on its element
 * in a narrower window. It scales with the element's box only, so text that reflows
 * moves under the mark and a circled word can leave its circle.
 */

import { cancelRender, nextRender, sizeObserver } from "../rendering.js";
import { setChildren } from "../dom-children.js";
import { shownBox } from "../geometry.js";
import { el } from "../widget-elements.js";
import { anchorElement, anchorName } from "../anchor-names.js";
import {
  anchoredBy,
  dropStand,
  paintStand,
  placement,
  standBox,
  standIn,
} from "../target-paint-geometry.js";
import { strokesIn, validDrawing } from "./drawing-record.js";

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

// The drawing as a picture of itself, fitted to whatever box holds it: what a composer
// shows of the drawing its comment carries.
export function drawingThumbnail(drawing) {
  const svg = document.createElementNS(SVG_NS, "svg");
  const { x, y, width, height } = drawingFrame(drawing.strokes);
  svg.setAttribute("viewBox", `${x} ${y} ${width} ${height}`);
  svg.setAttribute("aria-hidden", "true");
  svg.append(pathFor(pathData(drawing.strokes)));
  return svg;
}

export function createDrawingInk({ drawings }) {
  // The draft or ordinary Thread is the accessible representation of its ink.
  const layer = el("div", "lf-ui lf-drawings lf-page-paint");
  layer.setAttribute("aria-hidden", "true");
  let paintFrame = 0;
  let mounted = new Map();
  let mounting = new Map();
  const observed = new Set();
  const sizes = sizeObserver(() => shifted());

  // The complete description is the retained-node key. Two equal marks in one pass
  // still consume distinct prior nodes in order.
  function mark(drawing, target, className, id, clips) {
    if (!validDrawing(drawing)) return null;
    const box = shownBox(target);
    if (!box?.width || !box?.height) return null;
    const strokes = strokesIn(drawing, box);
    const frame = drawingFrame(strokes);
    const { width, height } = frame;
    if (!width || !height) return null;
    const anchor = anchorName(anchorElement(target));
    const data = pathData(strokes);
    const described = JSON.stringify([
      className,
      id,
      anchor,
      width,
      height,
      frame.x,
      frame.y,
      data,
    ]);
    let standing = mounted.get(described)?.shift();
    if (!standing) {
      const svg = document.createElementNS(SVG_NS, "svg");
      svg.classList.add("lf-drawing-mark", className);
      if (id) svg.dataset.thread = id;
      svg.setAttribute(
        "viewBox",
        `${frame.x} ${frame.y} ${frame.width} ${frame.height}`,
      );
      svg.setAttribute("preserveAspectRatio", "none");
      svg.setAttribute("aria-hidden", "true");
      svg.append(pathFor(data));
      standing = paintStand(svg);
    }
    const next = mounting.get(described) ?? [];
    next.push(standing);
    mounting.set(described, next);
    const placed = placement(target, false, false, clips);
    return { standing, placed, frame, box };
  }

  function paint() {
    const nextObserved = new Set();
    const marks = [];
    const clips = new Map();
    mounting = new Map();
    for (const { drawing, target, className, id } of drawings()) {
      const painted = mark(drawing, target, className, id, clips);
      if (painted) {
        marks.push(painted);
        nextObserved.add(target);
      }
    }

    // Reconciliation leaves unchanged ink and anything holding it in the document.
    // Mount before resolving CSS anchors: a stand must follow its target in
    // document order for the browser's anchoring plane to reach it.
    setChildren(
      layer,
      marks.map(({ standing }) => standing.root),
    );
    for (const { standing, placed, frame, box } of marks) {
      const anchor = anchoredBy(placed.surface, standing.root);
      const stood = standIn(standing, placed, Boolean(anchor));
      standBox(
        standing.box,
        {
          left: box.left + frame.x,
          top: box.top + frame.y,
          right: box.left + frame.x + frame.width,
          bottom: box.top + frame.y + frame.height,
        },
        stood,
        anchor,
      );
    }
    for (const stands of mounted.values()) for (const stand of stands) dropStand(stand);
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
    for (const stands of mounted.values()) for (const stand of stands) dropStand(stand);
    mounted.clear();
    mounting.clear();
    layer.replaceChildren();
  }

  return { layer, paint, shifted, destroy };
}
