/* Native affine axes of an element and its scroll space, independent of runtime
 * presentation, and the frame they place its border box in. Frame geometry, the
 * readings of what a box shows and the browser shift sensor share this reading: it
 * is the one answer to how an element's layout pixels map to the viewport, so a
 * reading that needs that map asks here rather than dividing a bounding rect by an
 * offset size, which a turn defeats: a box turned a quarter reads its layout height
 * across. A motion path's turn is not read, nor a perspective's foreshortening: a box
 * on a path reads as though it stood unturned, and one under a perspective as though
 * seen square on. */
import { isElement, isHTML, isSVG, renderedParent } from "../lib/shadow-tree.js";
import { union } from "./rect.js";

const IDENTITY = new window.DOMMatrixReadOnly();

// Elements CSS draws as one atomic box even where they compute `display: inline`:
// replaced content and form controls (HTML, "Replaced elements" and "Widgets").
const ATOMIC_INLINE =
  "img, video, audio, canvas, iframe, embed, object, input, select, textarea, button";

// What `node`'s own box adds to the map of the layout pixels it holds: its rotate, scale
// and transform, where CSS transforms its box, and its zoom, which scales what it holds
// whatever box it draws. CSS transforms only a box of its own that is block-level or
// atomic inline (CSS Transforms, "transformable element"), so an element drawing no box
// (`display: contents`), an inline box of words and a table column take none of theirs.
// Null where the box adds nothing, as most boxes do, so a climb builds a matrix only for
// those that add something. An element the browser computes no style for, one out of
// the document or in a document no window shows, draws no box and reads every property
// as an empty string, from which no turn can be read, so it adds nothing, as its empty
// bounding rect says.
/** @param {Element} node */
function ownTransform(node) {
  const style = getComputedStyle(node);
  if (!style.display) return null;
  const zoom = Number(style.zoom);
  const turns =
    (style.rotate !== "none" || style.scale !== "none" || style.transform !== "none") &&
    style.display !== "contents" &&
    !style.display.startsWith("table-column") &&
    (style.display !== "inline" || isSVG(node, "svg") || node.matches(ATOMIC_INLINE));
  if (zoom === 1 && !turns) return null;
  let local = new window.DOMMatrix();
  if (turns && style.rotate !== "none") {
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
  if (turns && style.scale !== "none") {
    const scale = style.scale.split(" ").map(Number);
    local = local.scale(scale[0], scale[1] ?? scale[0], scale[2] ?? 1);
  }
  if (turns && style.transform !== "none")
    local = local.multiply(new window.DOMMatrix(style.transform));
  return local.scale(zoom, zoom);
}

// The linear map of `source`'s own layout units into the viewport, through every
// transform and zoom on it and on the boxes around it, shadow hosts included: the map
// of the box it stands in, `above` where the caller already holds it and read by
// climbing otherwise, turned by what its own box adds (`ownTransform`). Inside an SVG
// drawing the browser's own map of the element's user units answers (`getScreenCTM`),
// the viewBoxes and transforms around it included. Translation and transform origins
// enter `elementBorderFrame`. The map it returns may be the one it was handed, so a
// caller copies it before changing it.
/** @param {Element} source @param {DOMMatrixReadOnly} [above] @returns {DOMMatrixReadOnly} */
export function elementMatrix(source, above) {
  // Only an SVG element that draws has a screen matrix: a `<stop>` or `<title>` has none.
  const drawn =
    isSVG(source) && source.ownerSVGElement
      ? /** @type {SVGElement & Partial<SVGGraphicsElement>} */ (
          source
        ).getScreenCTM?.()
      : null;
  if (drawn)
    return new window.DOMMatrixReadOnly([drawn.a, drawn.b, drawn.c, drawn.d, 0, 0]);
  const parent = renderedParent(source);
  const outer = above ?? (isElement(parent) ? elementMatrix(parent) : IDENTITY);
  const own = ownTransform(source);
  return own ? outer.multiply(own) : outer;
}

/** @param {DOMMatrixReadOnly} matrix */
const axesOf = ({ a, b, c, d }) => ({ x: { x: a, y: b }, y: { x: c, y: d } });

// The composed affine basis of an element's own layout units in the viewport
// (`elementMatrix`); this basis also carries local scroll distances through every
// transformed ancestor.
/** @param {Element} source */
export const elementAxes = (source) => axesOf(elementMatrix(source));

// The axes a box's own `translate` moves it along: those of the box it stands in, at the
// box's own zoom, since CSS applies the translate outside the box's own rotate, scale
// and transform.
/** @param {Element} source */
export function translateAxes(source) {
  const parent = renderedParent(source);
  const zoom = Number(getComputedStyle(source).zoom);
  return axesOf(
    (isElement(parent) ? elementMatrix(parent) : IDENTITY).scale(zoom, zoom),
  );
}

// The element's CSS border box in the viewport: its width and height in its own layout
// pixels, and the affine map from those pixels, counted from the border box's top-left
// corner, to the viewport, its linear map (`elementMatrix`, or `matrix` where the caller
// holds it) placed where `box`, the box's bounding rect, puts that corner. The computed
// size gives the box to a fraction of a pixel; where it is the content box, it leaves out
// the room a scrollbar's gutter takes from it, which the offset and client sizes, whole
// pixels both, differ by beside the borders. An unturned box's size is its bounding
// rect's over the map's scale instead, which is exact: Chromium serializes a computed
// size to six significant figures, and a size written back from it, as a hold writes
// one, can lose a layout unit. A box with no CSS width of its own to read, such as an
// SVG shape, has none.
/** @typedef {{width: number, height: number, matrix: DOMMatrix}} BorderFrame */
/** @overload @param {HTMLElement} source @param {DOMRectReadOnly} [box] @param {DOMMatrixReadOnly} [matrix] @returns {BorderFrame} */
/** @overload @param {Element} source @param {DOMRectReadOnly} [box] @param {DOMMatrixReadOnly} [matrix] @returns {BorderFrame | null} */
/** @param {Element} source @param {DOMRectReadOnly} [box] @param {DOMMatrixReadOnly} [matrix] @returns {BorderFrame | null} */
export function elementBorderFrame(
  source,
  box = source.getBoundingClientRect(),
  matrix = elementMatrix(source),
) {
  const style = getComputedStyle(source);
  // An element that draws no box, under `display: contents` or inside an undisplayed
  // box, has only its bounding rect, whatever width and height its style computes.
  if (!source.getClientRects().length)
    return {
      width: box.width,
      height: box.height,
      matrix: new window.DOMMatrix().translate(box.left, box.top),
    };
  /** @param {string} value */
  const px = (value) => Number.parseFloat(value);
  /** @param {"width" | "height"} side @param {"Left" | "Top"} start @param {"Right" | "Bottom"} end */
  const borderSize = (side, start, end) => {
    const [offset, client] = !isHTML(source)
      ? [undefined, undefined]
      : side === "width"
        ? [source.offsetWidth, source.clientWidth]
        : [source.offsetHeight, source.clientHeight];
    const size = px(style[side]);
    if (!Number.isFinite(size)) return offset;
    if (style.boxSizing === "border-box") return size;
    const borders = px(style[`border${start}Width`]) + px(style[`border${end}Width`]);
    const gutter =
      offset === undefined ? 0 : Math.max(0, Math.round(offset - client - borders));
    return (
      size +
      px(style[`padding${start}`]) +
      px(style[`padding${end}`]) +
      borders +
      gutter
    );
  };
  const read = {
    width: borderSize("width", "Left", "Right"),
    height: borderSize("height", "Top", "Bottom"),
  };
  if (read.width === undefined || read.height === undefined) return null;
  const { a, b, c, d } = matrix;
  const unturned = b === 0 && c === 0 && a !== 0 && d !== 0;
  const width = unturned ? box.width / Math.abs(a) : read.width;
  const height = unturned ? box.height / Math.abs(d) : read.height;
  const left = box.left - Math.min(0, width * a, height * c, width * a + height * c);
  const top = box.top - Math.min(0, width * b, height * d, width * b + height * d);
  return { width, height, matrix: new window.DOMMatrix([a, b, c, d, left, top]) };
}

// Where `inner`, a box of `source`'s own pixels inside its border box, stands on screen:
// the box's bounding rect, drawn by the browser, brought in on each side by how far the
// frame (`elementBorderFrame`, on `matrix` where the caller holds it) carries `inner`'s
// edge in from the border box's. Where the frame is the browser's own map this is
// `inner` carried; where the browser turns the box in a way the frame doesn't read, as a
// motion path or a perspective does, the rect keeps the answer within those insets of
// where the box is drawn. Null for a box with no frame.
/** @typedef {import("../base/box.js").Box} Box */
/** @overload @param {HTMLElement} source @param {Box} inner @param {DOMMatrixReadOnly} [matrix] @returns {Box} */
/** @overload @param {Element} source @param {Box} inner @param {DOMMatrixReadOnly} [matrix] @returns {Box | null} */
/** @param {Element} source @param {Box} inner @param {DOMMatrixReadOnly} [matrix] @returns {Box | null} */
export function innerBox(source, inner, matrix) {
  const box = source.getBoundingClientRect();
  const frame = elementBorderFrame(source, box, matrix);
  if (!frame) return null;
  const outer = carriedBox(frame.matrix, {
    left: 0,
    top: 0,
    right: frame.width,
    bottom: frame.height,
  });
  const carried = carriedBox(frame.matrix, inner);
  return {
    left: box.left + carried.left - outer.left,
    top: box.top + carried.top - outer.top,
    right: box.right - outer.right + carried.right,
    bottom: box.bottom - outer.bottom + carried.bottom,
  };
}

// The box `box` covers once `matrix` carries it: the bounds of its four corners. A
// frame's matrix carries a box of its pixels into the viewport, and its inverse a box
// of the viewport into the frame.
/** @param {DOMMatrixReadOnly} matrix @param {import("../base/box.js").Box} box */
export function carriedBox(matrix, { left, top, right, bottom }) {
  /** @param {number} x @param {number} y */
  const corner = (x, y) => {
    const point = matrix.transformPoint({ x, y });
    return { left: point.x, right: point.x, top: point.y, bottom: point.y };
  };
  return union([
    corner(left, top),
    corner(right, top),
    corner(right, bottom),
    corner(left, bottom),
  ]);
}

// One local scroll pixel's viewport displacement. The root's scroll is already
// measured in viewport units, independently of transforms on its content.
/** @param {Element} source */
export function scrollAxes(source) {
  return source === source.ownerDocument.scrollingElement
    ? { x: { x: 1, y: 0 }, y: { x: 0, y: 1 } }
    : elementAxes(source);
}
