/* Drawing coordinates belong to the target's local frame, independent of layout
 * size. Every visual consumer projects through the same current element frame, so
 * ink and its contextual picture follow a scale or rotation without treating text
 * reflow as a transform. */
import { elementFrame } from "../../dom/element-frame.js";
import { leafSurface } from "../../readings/passages.js";
import { shadowHost, under, upFrom } from "../../lib/shadow-tree.js";
import { MAX_DRAWING_FRAME_DEPTH } from "./drawing-record.js";
import type { Drawing, DrawingInk } from "./drawing-record.js";

// These native sources own intrinsic coordinates. A semantic figure, paragraph or
// widget can hold several; its comment identity does not choose one of their frames.
const INTRINSIC_VISUAL = "svg, img, canvas, video";
const contentChildren = (root: ParentNode) =>
  [...root.children].filter((child) => !leafSurface(child));

export function captureDrawingFrame(target: Element, hit: Element | null) {
  let source = hit;
  while (source && !source.matches(INTRINSIC_VISUAL)) source = upFrom(source);
  if (!source || !under(source, target)) return undefined;
  const path = [];
  for (let node = source; node !== target;) {
    const parent = node.parentNode;
    const host = shadowHost(parent);
    const up = host ?? node.parentElement;
    if (!parent || !up) return undefined;
    const children = contentChildren(parent);
    path.unshift({
      tag: node.localName,
      index: children.indexOf(node),
      siblings: children.length,
      ...(host && { shadow: true }),
    });
    if (path.length > MAX_DRAWING_FRAME_DEPTH) return undefined;
    node = up;
  }
  return { root: target.localName, path };
}

// Structural identity is conservative: insertion or removal changes the recorded
// sibling count, so another same-tag visual cannot take over the vanished frame.
// Replacing a node in the same structural seat retains that seat, as a semantic
// target replacement does. There is no search or positional fallback.
export function resolveDrawingFrame(target: Element, reference: Drawing["frame"]) {
  if (!reference) return target;
  if (target.localName !== reference.root) return null;
  let node = target;
  for (const step of reference.path) {
    const root = step.shadow ? node.shadowRoot : node;
    if (!root) return null;
    const children = contentChildren(root);
    if (children.length !== step.siblings) return null;
    const child = children[step.index];
    if (!child || child.localName !== step.tag) return null;
    node = child;
  }
  return node.matches(INTRINSIC_VISUAL) ? node : null;
}

export function drawingGeometry(drawing: DrawingInk, target: Element) {
  const source = resolveDrawingFrame(target, drawing.frame);
  const frame = source && elementFrame(source);
  if (!frame) return null;
  const { box, matrix } = frame;
  const strokes = drawing.strokes.map((stroke) =>
    stroke.map(([x, y]): [number, number] => {
      const point = matrix.transformPoint({ x, y });
      return [point.x - box.left, point.y - box.top];
    }),
  );
  return { box, strokes, target: source };
}
