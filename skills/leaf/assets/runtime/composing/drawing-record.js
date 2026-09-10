/* Validation for the drawing payload shared by composers and the drawing controller. */
export const DRAWING_FORMAT = "leaf-drawing/1";
export const MAX_DRAWING_POINTS = 256;
export const DRAWING_COORDINATE_LIMIT = 33554432;

export function validDrawing(drawing) {
  return Boolean(
    drawing &&
    typeof drawing === "object" &&
    !Array.isArray(drawing) &&
    Object.keys(drawing).every((key) => ["format", "points"].includes(key)) &&
    drawing.format === DRAWING_FORMAT &&
    Array.isArray(drawing.points) &&
    drawing.points.length >= 2 &&
    drawing.points.length <= MAX_DRAWING_POINTS &&
    drawing.points.every(
      (point) =>
        Array.isArray(point) &&
        point.length === 2 &&
        point.every(
          (coordinate) =>
            Number.isFinite(coordinate) &&
            coordinate >= -DRAWING_COORDINATE_LIMIT &&
            coordinate <= DRAWING_COORDINATE_LIMIT,
        ),
    ),
  );
}
