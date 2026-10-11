/* Validation for the drawing payload shared by composers and the drawing controller.
 *
 * `strokes` are coordinates in one local frame and may run past its edges. HTML uses
 * CSS pixels; SVG uses user units; images, canvases and video use intrinsic
 * pixels. SVG points retain their user-space origin when the viewBox pans.
 * geometry.elementFrame projects all of them through composed affine transforms.
 * `frame`, when present, identifies the native visual under the stroke inside the
 * semantic comment target. Its bounded structural path counts authored element siblings,
 * including a shadow-root step, and detaches on insertion/removal rather than guessing.
 * Leaf apparatus never enters the path. An empty path names a native semantic target.
 * Without `frame`, the semantic target itself supplies the local frame.
 * `box` is that frame's size at the latest capture, and `says` the page's words the
 * drawing stands over. `viewport` and `scheme` record the window for `leaf page picture`.
 * Layout growth adds HTML pixels without stretching existing ink. Resizing an intrinsic
 * visual scales its content and ink together. Scroll and transforms carry either frame.
 *
 * A draft's drawing also carries `at`, the affine matrix from its local frame into
 * its anchor's section when last drawn on, so the draft's ink can stand there once a revision
 * takes the target away. It is the draft's alone: `sentDrawing` leaves it out of the
 * comment.
 */
import { drawingSchema } from "./drawing-schema.js";

// The bounds are read from the schema admission holds a comment's drawing to,
// generated from registry.json, so a bound changes there alone.
const FIELDS = drawingSchema.properties;
const PATH = FIELDS.frame.properties.path;
const STEP = PATH.items.properties;
export const DRAWING_FORMAT = FIELDS.format.const;
export const MAX_DRAWING_STROKES = FIELDS.strokes.maxItems;
export const MAX_DRAWING_FRAME_DEPTH = PATH.maxItems;
export const MAX_DRAWING_POINTS = FIELDS.strokes.items.maxItems;
export const DRAWING_COORDINATE_LIMIT =
  FIELDS.strokes.items.items.prefixItems[0].maximum;
export const MAX_DRAWING_SAYS_LENGTH = FIELDS.says.maxLength; // code points
const TAG_PATTERN = new RegExp(STEP.tag.pattern);

const bounded = (coordinate) =>
  Number.isFinite(coordinate) &&
  coordinate >= -DRAWING_COORDINATE_LIMIT &&
  coordinate <= DRAWING_COORDINATE_LIMIT;

const validStroke = (stroke) =>
  Array.isArray(stroke) &&
  stroke.length >= FIELDS.strokes.items.minItems &&
  stroke.length <= MAX_DRAWING_POINTS &&
  stroke.every(
    (point) => Array.isArray(point) && point.length === 2 && point.every(bounded),
  );

// A box or a viewport: a width and a height, each a positive bounded number.
const validSize = (box) =>
  Array.isArray(box) &&
  box.length === 2 &&
  box.every((side) => bounded(side) && side > 0);

const validTag = (tag) =>
  typeof tag === "string" && tag.length <= STEP.tag.maxLength && TAG_PATTERN.test(tag);
const validFrame = (frame) =>
  frame &&
  !Array.isArray(frame) &&
  typeof frame === "object" &&
  Object.keys(frame).every((key) => ["root", "path"].includes(key)) &&
  validTag(frame.root) &&
  Array.isArray(frame.path) &&
  frame.path.length <= MAX_DRAWING_FRAME_DEPTH &&
  frame.path.every(
    (step) =>
      step &&
      !Array.isArray(step) &&
      typeof step === "object" &&
      Object.keys(step).every((key) =>
        ["tag", "index", "siblings", "shadow"].includes(key),
      ) &&
      validTag(step.tag) &&
      Number.isInteger(step.index) &&
      step.index >= STEP.index.minimum &&
      step.index <= STEP.index.maximum &&
      Number.isInteger(step.siblings) &&
      step.siblings >= STEP.siblings.minimum &&
      step.siblings <= STEP.siblings.maximum &&
      (step.shadow === undefined || typeof step.shadow === "boolean"),
  );

const validWords = (says) =>
  typeof says === "string" &&
  says !== "" &&
  [...says].length <= MAX_DRAWING_SAYS_LENGTH;

// A drawing is read whole and never changed in place, and the page's ink asks of each
// one on every paint, so each object is checked once.
const checked = new WeakMap();

export function validDrawing(drawing) {
  if (!drawing || typeof drawing !== "object") return false;
  if (!checked.has(drawing)) checked.set(drawing, wellFormed(drawing));
  return checked.get(drawing);
}

function wellFormed(drawing) {
  return Boolean(
    !Array.isArray(drawing) &&
    Object.keys(drawing).every((key) =>
      [
        "format",
        "strokes",
        "box",
        "at",
        "frame",
        "says",
        "viewport",
        "scheme",
      ].includes(key),
    ) &&
    drawing.format === DRAWING_FORMAT &&
    Array.isArray(drawing.strokes) &&
    drawing.strokes.length >= FIELDS.strokes.minItems &&
    drawing.strokes.length <= MAX_DRAWING_STROKES &&
    drawing.strokes.every(validStroke) &&
    (drawing.box === undefined || validSize(drawing.box)) &&
    (drawing.frame === undefined || validFrame(drawing.frame)) &&
    (drawing.at === undefined ||
      (Array.isArray(drawing.at) &&
        drawing.at.length === 6 &&
        drawing.at.every(bounded))) &&
    (drawing.says === undefined || validWords(drawing.says)) &&
    validSize(drawing.viewport) &&
    FIELDS.scheme.enum.includes(drawing.scheme),
  );
}

// The drawing as a comment carries it.
export function sentDrawing(drawing) {
  const { at, ...sent } = drawing;
  return sent;
}
