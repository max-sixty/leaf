/* The drawing payload shared by composers and the drawing controller.
 *
 * `strokes` are coordinates in one local frame and may run past its edges. HTML uses
 * CSS pixels; SVG uses user units; images, canvases and video use intrinsic
 * pixels. SVG points retain their user-space origin when the viewBox pans.
 * element-frame.js `elementFrame` projects all of them through composed affine transforms.
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

// Every bound is read from the schema admission holds a comment's drawing to,
// generated from registry.json, each field from its own declaration, so a bound
// changes there alone.
const FIELDS = drawingSchema.properties;
export const DRAWING_FORMAT = FIELDS.format.const;
export const MAX_DRAWING_STROKES = FIELDS.strokes.maxItems;
export const MAX_DRAWING_FRAME_DEPTH = FIELDS.frame.properties.path.maxItems;
export const MAX_DRAWING_POINTS = FIELDS.strokes.items.maxItems;
export const DRAWING_COORDINATE_LIMIT =
  FIELDS.strokes.items.items.prefixItems[0].maximum;
export const MAX_DRAWING_SAYS_LENGTH = FIELDS.says.maxLength; // code points

// Whether a stored value is a drawing this runtime draws. Admission holds a comment's
// drawing to its schema, and drawing.js clamps a draft's to the same bounds as it
// draws, so only the format, which separates a draft saved by an older runtime, is
// asked here.
export const validDrawing = (drawing) => drawing?.format === DRAWING_FORMAT;

// The drawing as a comment carries it.
export function sentDrawing(drawing) {
  const { at, ...sent } = drawing;
  return sent;
}
