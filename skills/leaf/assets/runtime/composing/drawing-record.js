/* Validation for the drawing payload shared by composers and the drawing controller. */
export const DRAWING_FORMAT = "leaf-drawing/2";
export const MAX_DRAWING_STROKES = 32;
export const MAX_DRAWING_POINTS = 256;
export const DRAWING_COORDINATE_LIMIT = 33554432;

const validStroke = (stroke) =>
  Array.isArray(stroke) &&
  stroke.length >= 2 &&
  stroke.length <= MAX_DRAWING_POINTS &&
  stroke.every(
    (point) =>
      Array.isArray(point) &&
      point.length === 2 &&
      point.every(
        (coordinate) =>
          Number.isFinite(coordinate) &&
          coordinate >= -DRAWING_COORDINATE_LIMIT &&
          coordinate <= DRAWING_COORDINATE_LIMIT,
      ),
  );

export function validDrawing(drawing) {
  return Boolean(
    drawing &&
    typeof drawing === "object" &&
    !Array.isArray(drawing) &&
    Object.keys(drawing).every((key) => ["format", "strokes"].includes(key)) &&
    drawing.format === DRAWING_FORMAT &&
    Array.isArray(drawing.strokes) &&
    drawing.strokes.length >= 1 &&
    drawing.strokes.length <= MAX_DRAWING_STROKES &&
    drawing.strokes.every(validStroke),
  );
}
