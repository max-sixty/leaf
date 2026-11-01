/* Native affine axes of an element and its scroll space, independent of runtime
 * presentation. Frame geometry and the browser shift sensor share this reading. */
import { isElement, renderedParent } from "./shadow-tree.js";

// The composed affine basis of an element's own layout units in the viewport.
// Translation and transform origins enter `elementFrame`; this basis also carries
// local scroll distances through every transformed ancestor, including shadow hosts.
/** @param {Element} source */
export function elementAxes(source) {
  let matrix = new window.DOMMatrix();
  /** @type {Node | null} */
  let node = source;
  for (; isElement(node); node = renderedParent(node)) {
    const style = getComputedStyle(node);
    let local = new window.DOMMatrix();
    if (style.rotate !== "none") {
      const split = style.rotate.lastIndexOf(" ");
      const angle = style.rotate.slice(split + 1);
      const parts = style.rotate
        .slice(0, split + 1)
        .trim()
        .split(" ");
      const degrees =
        parseFloat(angle) *
        (angle.endsWith("turn")
          ? 360
          : angle.endsWith("grad")
            ? 0.9
            : angle.endsWith("rad")
              ? 180 / Math.PI
              : 1);
      /** @type {[number, number, number]} */
      const axis =
        parts.length === 3
          ? [Number(parts[0]), Number(parts[1]), Number(parts[2])]
          : parts[0] === "x"
            ? [1, 0, 0]
            : parts[0] === "y"
              ? [0, 1, 0]
              : [0, 0, 1];
      local = local.rotateAxisAngle(...axis, degrees);
    }
    if (style.scale !== "none") {
      const scale = style.scale.split(" ").map(Number);
      local = local.scale(scale[0], scale[1] ?? scale[0], scale[2] ?? 1);
    }
    if (style.transform !== "none")
      local = local.multiply(new window.DOMMatrix(style.transform));
    const zoom = Number(style.zoom);
    local = local.scale(zoom, zoom);
    matrix = local.multiply(matrix);
  }
  return { x: { x: matrix.a, y: matrix.b }, y: { x: matrix.c, y: matrix.d } };
}

// One local scroll pixel's viewport displacement. The root's scroll is already
// measured in viewport units, independently of transforms on its content.
/** @param {Element} source */
export function scrollAxes(source) {
  return source === source.ownerDocument.scrollingElement
    ? { x: { x: 1, y: 0 }, y: { x: 0, y: 1 } }
    : elementAxes(source);
}
