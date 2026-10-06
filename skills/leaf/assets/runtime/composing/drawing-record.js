/* Validation for the drawing payload shared by composers and the drawing controller.
 *
 * `strokes` are offsets from the target's top-left corner and may run past its edges; a
 * page drawing has no target, and its strokes are offsets from the document's origin.
 * `box` is the target's size the strokes were drawn at, and `says` is the page's words
 * the drawing stands over: together the reading for whoever cannot see the page.
 * `viewport` is the layout viewport's width and height, and `scheme` the color scheme,
 * the drawing was made in: with the comment's revision they are the window the user
 * saw, which `leaf page picture` draws again for the agent.
 * `strokesIn` scales the strokes to the target's current size.
 *
 * A draft's drawing also carries `at`, where the target's box stood in the document when
 * it was last drawn on, so the draft's ink can stand there once a revision takes the
 * target away. It is the draft's alone: `sentDrawing` leaves it out of the comment.
 */
export const DRAWING_FORMAT = "leaf-drawing/2";
export const MAX_DRAWING_STROKES = 32;
export const MAX_DRAWING_POINTS = 256;
export const DRAWING_COORDINATE_LIMIT = 33554432;
export const MAX_DRAWING_SAYS_LENGTH = 500; // code points
export const DRAWING_SCHEMES = ["light", "dark"];

const bounded = (coordinate) =>
  Number.isFinite(coordinate) &&
  coordinate >= -DRAWING_COORDINATE_LIMIT &&
  coordinate <= DRAWING_COORDINATE_LIMIT;

const validStroke = (stroke) =>
  Array.isArray(stroke) &&
  stroke.length >= 2 &&
  stroke.length <= MAX_DRAWING_POINTS &&
  stroke.every(
    (point) => Array.isArray(point) && point.length === 2 && point.every(bounded),
  );

// A box or a viewport: a width and a height, each a positive bounded number.
const validSize = (box) =>
  Array.isArray(box) &&
  box.length === 2 &&
  box.every((side) => bounded(side) && side > 0);

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
      ["format", "strokes", "box", "at", "says", "viewport", "scheme"].includes(key),
    ) &&
    drawing.format === DRAWING_FORMAT &&
    Array.isArray(drawing.strokes) &&
    drawing.strokes.length >= 1 &&
    drawing.strokes.length <= MAX_DRAWING_STROKES &&
    drawing.strokes.every(validStroke) &&
    (drawing.box === undefined || validSize(drawing.box)) &&
    (drawing.at === undefined ||
      (Array.isArray(drawing.at) &&
        drawing.at.length === 2 &&
        drawing.at.every(bounded))) &&
    (drawing.says === undefined || validWords(drawing.says)) &&
    validSize(drawing.viewport) &&
    DRAWING_SCHEMES.includes(drawing.scheme),
  );
}

// The drawing as a comment carries it.
export function sentDrawing(drawing) {
  const { at, ...sent } = drawing;
  return sent;
}

// The strokes at the target's current `size`: each axis scales by the target's side over
// the side of the `box` they were drawn in, so a mark keeps its share of the element
// whichever way the element was resized. A page drawing, which has no box, stands as drawn.
export function strokesIn(drawing, size) {
  if (!drawing.box || !size) return drawing.strokes;
  const across = size.width / drawing.box[0];
  const down = size.height / drawing.box[1];
  if (across === 1 && down === 1) return drawing.strokes;
  const at = (value) => Number(value.toFixed(4));
  return drawing.strokes.map((stroke) =>
    stroke.map(([x, y]) => [at(x * across), at(y * down)]),
  );
}
