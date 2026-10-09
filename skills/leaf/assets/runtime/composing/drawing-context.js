/* A composer's drawing preview is a frozen picture of the page beneath its ink.
 *
 * The drawing record remains geometry, independent of this disposable local picture.
 * The dependency clones computed presentation, including open shadow roots and scrolled
 * content; it excludes Leaf's apparatus so the preview cannot contain itself. Rendering
 * is requested only for a changed drawing, never on scroll or ordinary input repaint.
 * The optional renderer loads at the first preview, outside page presentation.
 */
import { leafSurface } from "../passages.js";
import { elementBorderFrame, paintClips } from "../geometry.js";
import { nextRender } from "../rendering.js";
import { renderedParent, under } from "../shadow.js";
import { drawingGeometry } from "./drawing-geometry.js";

const CONTEXT_PAD = 24;
const PREVIEW_WIDTH = 320;
const PREVIEW_HEIGHT = 240;

// Capture the painted island that contains the crop, rather than making every widget
// and offscreen image in a long page participate in one tiny attachment. Positioned
// islands keep their own origin; clipping ancestors join only when they cut this crop.
function contextSource(target, region) {
  const fits = (box) =>
    box.left <= region.left &&
    box.top <= region.top &&
    box.right >= region.right &&
    box.bottom >= region.bottom;
  let root = target;
  while (root !== document.body && !fits(elementBorderFrame(root).box)) {
    if (["fixed", "sticky"].includes(getComputedStyle(root).position)) break;
    root = renderedParent(root) ?? document.body;
  }
  const { bands } = paintClips(target, region, new Map(), false);
  for (const { box, band, axes } of bands) {
    if (
      band &&
      under(root, box) &&
      ((axes.x && (region.left < band.left || region.right > band.right)) ||
        (axes.y && (region.top < band.top || region.bottom > band.bottom)))
    )
      root = box;
  }
  // Solid inherited backing can be composited without cloning distant content.
  // A gradient or image needs its actual box and positioning, which the renderer owns.
  for (let owner = renderedParent(root); owner; owner = renderedParent(owner)) {
    const style = getComputedStyle(owner);
    if (style.backgroundImage !== "none") {
      root = owner;
      break;
    }
    if (
      style.backgroundColor !== "rgba(0, 0, 0, 0)" &&
      style.backgroundColor !== "transparent"
    )
      break;
  }
  return root;
}

function backingColors(source) {
  const colors = [];
  for (let node = renderedParent(source); node; node = renderedParent(node))
    colors.push(getComputedStyle(node).backgroundColor);
  return colors.reverse();
}

function paintBacking(canvas, colors) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (const color of colors) {
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }
}

function readPicture(drawing, target) {
  const geometry = target && drawingGeometry(drawing, target);
  const strokes = geometry?.strokes ?? drawing.strokes;
  const points = strokes.flat();
  const left = Math.min(...points.map(([x]) => x)) - CONTEXT_PAD;
  const top = Math.min(...points.map(([, y]) => y)) - CONTEXT_PAD;
  const width = Math.max(...points.map(([x]) => x)) - left + CONTEXT_PAD;
  const height = Math.max(...points.map(([, y]) => y)) - top + CONTEXT_PAD;
  const scale = Math.min(1, PREVIEW_WIDTH / width, PREVIEW_HEIGHT / height);
  return {
    strokes,
    box: geometry?.box,
    target: geometry?.target,
    left,
    top,
    width,
    height,
    scale,
  };
}

export function drawingThumbnail(drawing, target) {
  const canvas = document.createElement("canvas");
  canvas.setAttribute("aria-hidden", "true");
  canvas.style.color = "var(--accent)";
  let picture = readPicture(drawing, target);
  const sizeCanvas = () => {
    const width = Math.ceil(picture.width * picture.scale);
    const height = Math.ceil(picture.height * picture.scale);
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;
  };
  sizeCanvas();
  const paintInk = () => {
    const { strokes, left, top, scale } = picture;
    const ctx = canvas.getContext("2d");
    ctx.save();
    ctx.scale(scale, scale);
    ctx.translate(-left, -top);
    ctx.strokeStyle = getComputedStyle(canvas).color;
    ctx.lineWidth = 3;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    for (const stroke of strokes) {
      stroke.forEach(([x, y], index) => (index ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    }
    ctx.stroke();
    ctx.restore();
  };
  nextRender(() => {
    if (canvas.isConnected) paintInk();
  });

  // Freeze geometry, crop and backing together once the optional renderer arrives.
  // A transform during its download changes the ink's projection as well as its origin.
  import("../../vendor/drawing-context.esm.js")
    .then(async ({ domToCanvas }) => {
      if (!target?.isConnected) throw new Error("the drawing's subject is absent");
      picture = readPicture(drawing, target);
      if (!picture.box) throw new Error("the drawing's subject is absent");
      sizeCanvas();
      canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
      paintInk();
      const { box, left, top, width, height, scale } = picture;
      const region = {
        left: box.left + left,
        top: box.top + top,
        right: box.left + left + width,
        bottom: box.top + top + height,
      };
      const source = contextSource(picture.target, region);
      const frame = elementBorderFrame(source);
      const matrix = frame.matrix;
      const colors = backingColors(source);
      const image = await domToCanvas(source, {
        width,
        height,
        scale,
        style: {
          width: `${frame.width}px`,
          height: `${frame.height}px`,
          // The crop is a new containing block. Its dimensions must not reapply
          // responsive constraints to the root whose painted size we just froze.
          minWidth: "0",
          minHeight: "0",
          maxWidth: "none",
          maxHeight: "none",
          minInlineSize: "0",
          minBlockSize: "0",
          maxInlineSize: "none",
          maxBlockSize: "none",
          boxSizing: "border-box",
          position: "relative",
          left: "auto",
          right: "auto",
          top: "auto",
          bottom: "auto",
          margin: "0",
          rotate: "none",
          scale: "none",
          translate: "none",
          zoom: "1",
          transformOrigin: "0 0",
          transform: `matrix(${matrix.a},${matrix.b},${matrix.c},${matrix.d},${matrix.e - region.left},${matrix.f - region.top})`,
        },
        filter: (node) => !leafSurface(node),
        features: { restoreScrollPosition: true },
      });
      paintBacking(canvas, colors);
      canvas.getContext("2d").drawImage(image, 0, 0);
      paintInk();
      canvas.dataset.lfDrawingContext = "ready";
    })
    .catch((error) => {
      // Remote page assets can refuse embedding. The ink remains visible, and the
      // attachment says why the local picture could not be produced.
      canvas.dataset.lfDrawingContext = "unavailable";
      canvas.title = `Page preview unavailable: ${error.message}`;
      if (canvas.parentElement) {
        const status = document.createElement("span");
        status.className = "lf-drawing-context-status";
        status.textContent = "Page preview unavailable";
        canvas.parentElement.append(status);
        const label = canvas.parentElement.getAttribute("aria-label");
        canvas.parentElement.setAttribute(
          "aria-label",
          `${label}; page preview unavailable`,
        );
      }
    });
  return canvas;
}
