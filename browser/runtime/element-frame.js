/* This module owns an element's local coordinate frame in the viewport: the composed
 * affine axes of its own layout units, through every transformed ancestor; the frame
 * its content's coordinates live in (CSS border box, intrinsic pixels of replaced
 * content, or SVG user units); and the conversion of a viewport movement into a
 * scroller's own offsets. Drawing records points in these frames, so ink follows a
 * transformed, zoomed or resized target. */
import { shownBox } from "./geometry.js";
import { renderedParent } from "./shadow.js";

// The composed affine basis of an element's own layout units in the viewport.
// Translation and transform origins enter `elementFrame`; this basis also carries
// local scroll distances through every transformed ancestor, including shadow hosts.
export function elementAxes(source) {
  let matrix = new window.DOMMatrix();
  for (let node = source; node instanceof Element; node = renderedParent(node)) {
    const style = getComputedStyle(node);
    let local = new window.DOMMatrix();
    if (style.rotate !== "none") {
      const parts = style.rotate.split(" ");
      const angle = parts.pop();
      const degrees =
        parseFloat(angle) *
        (angle.endsWith("turn")
          ? 360
          : angle.endsWith("grad")
            ? 0.9
            : angle.endsWith("rad")
              ? 180 / Math.PI
              : 1);
      const axis =
        parts.length === 3
          ? parts.map(Number)
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

// Resolve the browser's computed two-component <position> in the free space left
// around replaced content. Only percentage units acquire a signed pixel basis here;
// the browser still parses and evaluates CSS math, including min/max/clamp. A cover
// fit can leave negative space, which a CSS containing block cannot represent.
const nativePositions = new WeakMap();
let positionProbe;
function nativePosition(source, position, horizontal, vertical) {
  const key = JSON.stringify([position, horizontal, vertical]);
  const prior = nativePositions.get(source);
  if (prior?.key === key) return prior.offset;
  const components = [];
  let depth = 0;
  let start = 0;
  for (let at = 0; at <= position.length; at++) {
    const character = position[at];
    if (character === "(") depth++;
    if (character === ")") depth--;
    if (at === position.length || (character === " " && !depth)) {
      if (at > start) components.push(position.slice(start, at));
      start = at + 1;
    }
  }
  const pixels = (value, space) =>
    value.replace(
      /([-+]?(?:\d*\.)?\d+(?:e[-+]?\d+)?)%/gi,
      (_unit, percent) => `${(Number(percent) * space) / 100}px`,
    );
  if (!positionProbe) {
    const measure = document.createElement("div");
    measure.className = "lf-ui";
    measure.dataset.lfRuntime = "";
    measure.inert = true;
    measure.style.cssText =
      "all:initial;position:fixed;visibility:hidden;contain:strict;width:0;height:0;left:0;top:0;pointer-events:none";
    const point = document.createElement("div");
    point.style.cssText = "all:initial;position:absolute;width:0;height:0";
    measure.append(point);
    positionProbe = { measure, point };
  }
  const { measure, point } = positionProbe;
  point.style.left = pixels(components[0], horizontal);
  point.style.top = pixels(components[1], vertical);
  document.body.append(measure);
  const resolved = getComputedStyle(point);
  const offset = [Number.parseFloat(resolved.left), Number.parseFloat(resolved.top)];
  measure.remove();
  nativePositions.set(source, { key, offset });
  return offset;
}

// Local content coordinates in the viewport. HTML uses its CSS border box; native
// visuals use intrinsic pixels or SVG user units, so resizing scales their ink
// with the picture. SVG's native user-space matrix carries viewBox camera pans as
// well as scale; its viewport origin never rebases stored points. Text reflow adds pixels
// to an HTML frame instead of stretching the points already held there.
export function elementFrame(source) {
  const box = shownBox(source);
  if (!box?.width || !box?.height) return null;
  if (source instanceof window.SVGGraphicsElement) {
    const view = source instanceof window.SVGSVGElement && source.viewBox.baseVal;
    const local =
      source instanceof window.SVGSVGElement
        ? view.width && view.height
          ? view
          : {
              x: 0,
              y: 0,
              width: Number.parseFloat(getComputedStyle(source).width),
              height: Number.parseFloat(getComputedStyle(source).height),
            }
        : source.getBBox();
    const screen = source.getScreenCTM();
    if (!screen) return null;
    return {
      box,
      width: local.width,
      height: local.height,
      matrix: new window.DOMMatrix([
        screen.a,
        screen.b,
        screen.c,
        screen.d,
        screen.e,
        screen.f,
      ]),
    };
  }
  const layout = elementBorderFrame(source);
  if (!layout) return null;
  const { width, height, matrix } = layout;
  const style = getComputedStyle(source);
  // Replaced visual content has its own coordinate space. Layout resizing scales
  // that content, unlike an ordinary HTML box whose extra lines add local pixels.
  const native =
    source instanceof window.HTMLImageElement
      ? [source.naturalWidth, source.naturalHeight]
      : source instanceof window.HTMLCanvasElement
        ? [source.width, source.height]
        : source instanceof window.HTMLVideoElement
          ? [source.videoWidth, source.videoHeight]
          : null;
  if (native) {
    if (!native[0] || !native[1]) return null;
    const edge = (side) =>
      Number.parseFloat(style[`border${side}Width`]) +
      Number.parseFloat(style[`padding${side}`]);
    const contentWidth = width - edge("Left") - edge("Right");
    const contentHeight = height - edge("Top") - edge("Bottom");
    let sx = contentWidth / native[0];
    let sy = contentHeight / native[1];
    if (style.objectFit !== "fill") {
      const scale =
        style.objectFit === "cover"
          ? Math.max(sx, sy)
          : style.objectFit === "none"
            ? 1
            : Math.min(sx, sy, style.objectFit === "scale-down" ? 1 : Infinity);
      sx = sy = scale;
    }
    const [dx, dy] = nativePosition(
      source,
      style.objectPosition,
      contentWidth - native[0] * sx,
      contentHeight - native[1] * sy,
    );
    if (![sx, sy, dx, dy].every(Number.isFinite) || !sx || !sy) return null;
    return {
      box,
      width: native[0],
      height: native[1],
      matrix: matrix.translate(edge("Left") + dx, edge("Top") + dy).scale(sx, sy),
    };
  }
  return { box, width, height, matrix };
}

// The element's CSS border box, for consumers cloning its computed presentation.
// Intrinsic content coordinates are a separate reading supplied by elementFrame.
function elementBorderFrame(source) {
  const box = shownBox(source);
  if (!box?.width || !box?.height) return null;
  const style = getComputedStyle(source);
  if (style.display === "contents")
    return {
      box,
      width: box.width,
      height: box.height,
      matrix: new window.DOMMatrix().translate(box.left, box.top),
    };
  const borderSize = (side, edges, fallback) => {
    const size = Number.parseFloat(style[side]);
    if (!Number.isFinite(size)) return fallback;
    return style.boxSizing === "border-box"
      ? size
      : size +
          edges.reduce(
            (sum, edge) =>
              sum +
              Number.parseFloat(style[`padding${edge}`]) +
              Number.parseFloat(style[`border${edge}Width`]),
            0,
          );
  };
  const width = borderSize("width", ["Left", "Right"], source.offsetWidth);
  const height = borderSize("height", ["Top", "Bottom"], source.offsetHeight);
  const { x, y } = elementAxes(source);
  const left =
    box.left - Math.min(0, width * x.x, height * y.x, width * x.x + height * y.x);
  const top =
    box.top - Math.min(0, width * x.y, height * y.y, width * x.y + height * y.y);
  const matrix = new window.DOMMatrix([x.x, x.y, y.x, y.y, left, top]);
  return { box, width, height, matrix };
}

// One local scroll pixel's viewport displacement. The root's scroll is already
// measured in viewport units, independently of transforms on its content.
export function scrollAxes(source) {
  return source === source.ownerDocument.scrollingElement
    ? { x: { x: 1, y: 0 }, y: { x: 0, y: 1 } }
    : elementAxes(source);
}

// Convert a viewport reveal movement into the scrollport's own layout offsets, as far
// as the scrollport can still travel, so a reveal past its edge asks for nothing. A
// one-axis scroller uses that axis's projected displacement; a two-axis scroller uses
// the inverse basis. At an edge the browser clamps one offset, so the other axis must
// take the remaining projected movement or a rotated scroller leaves words clipped.
export function localScrollBy(source, { x, y }) {
  const axes = scrollAxes(source);
  const horizontal = source.scrollWidth > source.clientWidth;
  const vertical = source.scrollHeight > source.clientHeight;
  const along = (axis) => {
    const amounts = [
      ...(x && axis.x ? [x / axis.x] : []),
      ...(y && axis.y ? [y / axis.y] : []),
    ];
    return amounts.reduce(
      (move, amount) => (Math.abs(amount) > Math.abs(move) ? amount : move),
      0,
    );
  };
  const reach = (offset, current, minimum, maximum) =>
    Math.max(minimum - current, Math.min(maximum - current, offset));
  const horizontalLimit = source.scrollWidth - source.clientWidth;
  const rtl = getComputedStyle(source).direction === "rtl";
  const reachLeft = (offset) =>
    reach(
      offset,
      source.scrollLeft,
      rtl ? -horizontalLimit : 0,
      rtl ? 0 : horizontalLimit,
    );
  const reachTop = (offset) =>
    reach(offset, source.scrollTop, 0, source.scrollHeight - source.clientHeight);
  if (!horizontal) return { left: 0, top: vertical ? reachTop(along(axes.y)) : 0 };
  if (!vertical) return { left: reachLeft(along(axes.x)), top: 0 };
  const determinant = axes.x.x * axes.y.y - axes.x.y * axes.y.x;
  const left = (x * axes.y.y - y * axes.y.x) / determinant;
  const top = (y * axes.x.x - x * axes.x.y) / determinant;
  const reachableLeft = reachLeft(left);
  const reachableTop = reachTop(top);
  if (reachableLeft !== left && axes.y.y)
    return {
      left: reachableLeft,
      top: reachTop((y - reachableLeft * axes.x.y) / axes.y.y),
    };
  if (reachableTop !== top && axes.x.x)
    return {
      left: reachLeft((x - reachableTop * axes.y.x) / axes.x.x),
      top: reachableTop,
    };
  return { left, top };
}
