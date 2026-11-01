/* A composer's drawing preview is a frozen picture of the page beneath its ink.
 *
 * The drawing record remains geometry, independent of this disposable local picture.
 * `pageImage` draws the crop, as region capture does, leaving out Leaf's apparatus so
 * the preview cannot contain itself; a live sample beneath the ink draws its own part.
 * Rendering is requested only for a changed drawing, never on scroll or ordinary input
 * repaint. The compact thumbnail retains bounded native pixels for the shared image
 * inspector; opening it serializes this frozen canvas, never captures the current page
 * again. The renderer loads at the first preview, outside page presentation.
 */
import { describeFailure } from "../exception.js";
import { canvas2D } from "../canvas.js";
import { LEAF_SURFACE } from "../passages.js";
import { nextRender } from "../rendering.js";
import { drawingGeometry } from "./drawing-geometry.js";
import { pageImage, pageRenderer } from "./page-image.js";

const CONTEXT_PAD = 24;
const PREVIEW_WIDTH = 2048;
const PREVIEW_HEIGHT = 1536;

/** @param {import("./drawing-record.js").Drawing} drawing @param {Element | null} target */
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

/** @param {import("./drawing-record.js").Drawing} drawing @param {Element | null} target */
export function drawingThumbnail(drawing, target) {
  const canvas = document.createElement("canvas");
  canvas.setAttribute("aria-hidden", "true");
  canvas.dataset.lfDrawingContext = "pending";
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
    const { strokes, left, top, width, height } = picture;
    const ctx = canvas2D(canvas);
    ctx.save();
    ctx.scale(canvas.width / width, canvas.height / height);
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

  // Freeze geometry and crop together once the renderer arrives. A transform during
  // its download changes the ink's projection as well as its origin.
  pageRenderer()
    .then(async () => {
      if (!target?.isConnected) throw new Error("the drawing's subject is absent");
      picture = readPicture(drawing, target);
      if (!picture.box) throw new Error("the drawing's subject is absent");
      sizeCanvas();
      canvas2D(canvas).clearRect(0, 0, canvas.width, canvas.height);
      paintInk();
      const { box, left, top, width, height } = picture;
      const { blob, warnings } = await pageImage(
        { x: scrollX + box.left + left, y: scrollY + box.top + top, width, height },
        { exclude: [LEAF_SURFACE] },
      );
      const image = await window.createImageBitmap(blob);
      const ctx = canvas2D(canvas);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
      paintInk();
      if (warnings.length) canvas.title = warnings.join(" ");
      canvas.dataset.lfDrawingContext = "ready";
    })
    .catch((error) => {
      // Remote page assets can refuse embedding. The ink remains visible, and the
      // attachment says why the local picture could not be produced.
      canvas.dataset.lfDrawingContext = "unavailable";
      canvas.title = `Page preview unavailable: ${describeFailure(error)}`;
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
