/* Validation for the drawing payload shared by composers and the drawing controller.
 *
 * `strokes` are offsets from the target's top-left corner. `box` is that target's
 * size when they were drawn, which is what lets a replay in a box of another size
 * keep the ink over the same part of it. `says` is the page's words under the ink at
 * that moment: the reading of the drawing for whoever cannot see the page.
 */
export const DRAWING_FORMAT = "leaf-drawing/2";
export const MAX_DRAWING_STROKES = 32;
export const MAX_DRAWING_POINTS = 256;
export const DRAWING_COORDINATE_LIMIT = 33554432;
export const MAX_DRAWING_WORDS = 500;

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
  typeof says === "string" && says !== "" && [...says].length <= MAX_DRAWING_WORDS;

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

export const rounded = (value) => Number(value.toFixed(4));
const clamped = (value) =>
  Math.max(-DRAWING_COORDINATE_LIMIT, Math.min(DRAWING_COORDINATE_LIMIT, value));

// Strokes drawn in a box of one size, as offsets in the same box at another. Each axis
// scales alone: a picture keeps its proportions, and a paragraph that reflowed narrower
// grew taller, where the same share of its height is the nearest thing to the same line.
export const scaledStrokes = (strokes, from, to) =>
  from[0] === to[0] && from[1] === to[1]
    ? strokes
    : strokes.map((stroke) =>
        stroke.map(([x, y]) => [
          rounded(clamped((x * to[0]) / from[0])),
          rounded(clamped((y * to[1]) / from[1])),
        ]),
      );
