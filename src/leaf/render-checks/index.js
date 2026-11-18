/* Browser programs used by the render gate.
 *
 * This module is served by the Leaf running the check, like its runtime. Its static
 * imports are deliberate: the browser module loader verifies the public widget API
 * and check-only observations before any probe runs. Both entries share the running
 * kernel rather than constructing another runtime. */
export * from "./framing.js";
export * from "./layout.js";
export * from "./motion.js";
export * from "./reachability.js";
export * from "./replay.js";
export * from "./runtime.js";
export * from "./widgets.js";
export * from "./words.js";
export * from "./view.js";
export * from "./scrollbars.js";
export * from "./outputs.js";
