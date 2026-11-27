/* The physical annotation renderer: pins, contextual floating placement, posted
 * drawing paint.
 * Boot imports this entry only for overlay presentation, so a page that presents its
 * own annotations (`data-annotations=page`) loads none of this closure; no other
 * runtime owner reaches it (`.config/dependency-cruiser.mjs`, `core-independent-of-overlay`).
 * Its factories share the core runtime's canonical owners.
 *
 * It lives in the kernel rather than the bundled default package: every
 * module here reads private runtime owners, which no package may import, so the
 * package boundary would hold only by exempting the default package from it, and
 * composition, the import graph, lint and installation preparation would each carry a
 * special case for this directory. The dynamic import above, not the package, is what
 * keeps a page-owned presentation from loading it. */
export { createMarginProjection } from "./margin-projection.js";
export { createFloatingResponsePlacement } from "./composing/floating-response.js";
export { postedDrawings } from "./composing/drawing-paint.js";
export { syncMarginContentLayout } from "./margin-layout.js";
export { floatingSelections } from "./floating.js";
