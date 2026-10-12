/* The physical annotation renderer: pins, contextual floating placement, posted
 * drawing paint, marks and annotation visibility.
 * Boot imports this entry only for overlay presentation, so a page that presents its
 * own annotations (`data-annotations=page`) loads none of this closure; no other
 * runtime owner reaches it (`.dependency-cruiser.mjs`, `core-independent-of-overlay`).
 * Its factories share the core runtime's canonical owners.
 *
 * It lives in the kernel. #1652 placed it in the bundled default package, but every
 * module here reads private runtime owners, which no package may import, so the
 * package boundary held only by exempting the default package from it, and composition,
 * the import graph, lint and installation preparation each carried a special case for
 * this directory. The dynamic import above, not the package, is what keeps a page-owned
 * presentation from loading it, and that import is unchanged at the same URL. */
export { createMarginProjection } from "./margin-projection.js";
export { createAnchorPaint } from "./anchor-paint.js";
export { createVisualMarkPaint } from "./visual-mark-paint.js";
export { createFloatingResponsePlacement } from "./composing/floating-response.js";
export { postedDrawings } from "./composing/drawing-paint.js";
export { syncMarginResidency } from "./margin-layout.js";
export { mountAnnotationControls, restoreAnnotations } from "./annotation-layer.js";
export { floatingSelections } from "./floating.js";
