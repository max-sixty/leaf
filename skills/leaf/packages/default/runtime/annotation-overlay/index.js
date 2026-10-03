/* The default package's physical annotation renderer.
 * Boot imports this entry only for overlay presentation. Its factories share the
 * core runtime's canonical owners; page-owned controls do not load this closure. */
export { createMarginProjection } from "./margin-projection.js";
export { createAnchorPaint } from "./anchor-paint.js";
export { createVisualMarkPaint } from "./visual-mark-paint.js";
export { createFloatingResponsePlacement } from "./composing/floating-response.js";
export { postedDrawings } from "./composing/drawing-paint.js";
export { syncMarginResidency } from "./margin-layout.js";
export { mountAnnotationControls, restoreAnnotations } from "./annotation-layer.js";
