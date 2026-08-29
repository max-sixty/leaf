/* Browser programs used by the render and export gates.
 *
 * This module is served by Leaf itself rather than vendored into a page. Its static
 * import is deliberate: the browser module loader verifies the public widget API
 * before any probe runs, and ESLint holds this file to that one runtime boundary. */
export * from "./framing.js";
export * from "./layout.js";
export * from "./reachability.js";
export * from "./replay.js";
export * from "./runtime.js";
export * from "./widgets.js";
export * from "./words.js";
export { bake } from "./standalone.js";
