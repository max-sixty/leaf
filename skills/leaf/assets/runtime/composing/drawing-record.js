/* Validation for the drawing payload shared by composers and the drawing controller.
 *
 * `strokes` are offsets from the target's top-left corner and may run past its edges; a
 * page drawing has no target, and its strokes are offsets from the document's origin.
 * `box` is an anchored drawing's target size when drawn, and `says` is the page's words
 * the drawing stands over: together the reading for whoever cannot see the page.
 */
export const DRAWING_FORMAT = "leaf-drawing/2";
export const MAX_DRAWING_STROKES = 32;
export const MAX_DRAWING_POINTS = 256;
export const DRAWING_COORDINATE_LIMIT = 33554432;
export const MAX_DRAWING_SAYS_LENGTH = 500; // code points

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

const validBox = (box) =>
  Array.isArray(box) &&
  box.length === 2 &&
  box.every((side) => bounded(side) && side > 0);

const validWords = (says) =>
  typeof says === "string" &&
  says !== "" &&
  [...says].length <= MAX_DRAWING_SAYS_LENGTH;

export function validDrawing(drawing) {
  return Boolean(
    drawing &&
    typeof drawing === "object" &&
    !Array.isArray(drawing) &&
    Object.keys(drawing).every((key) =>
      ["format", "strokes", "box", "says"].includes(key),
    ) &&
    drawing.format === DRAWING_FORMAT &&
    Array.isArray(drawing.strokes) &&
    drawing.strokes.length >= 1 &&
    drawing.strokes.length <= MAX_DRAWING_STROKES &&
    drawing.strokes.every(validStroke) &&
    (drawing.box === undefined || validBox(drawing.box)) &&
    (drawing.says === undefined || validWords(drawing.says)),
  );
}
