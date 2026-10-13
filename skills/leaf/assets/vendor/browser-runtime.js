/** Internal framework facade. Content modules import runtime/widget-api.js. */
export { LitElement, html, noChange, nothing, render } from "./lit.js";
export { Directive, PartType, directive } from "./lit.js";
export { AsyncDirective } from "./lit.js";
export { classMap } from "./lit.js";
export { guard } from "./lit.js";
export { keyed } from "./lit.js";
export { live } from "./lit.js";
export { createRef, ref } from "./lit.js";
export { repeat } from "./lit.js";
export { styleMap } from "./lit.js";
export { unsafeHTML } from "./lit.js";
export { effect, signal } from "./browser-runtime/signals-core.js";
export { createSemanticApplication } from "./browser-runtime/application.js";
export {
  createPresentationCoordinator,
  createPresentationSchedule,
  describeFailure,
  PRESENTATION_HELD,
} from "./browser-runtime/presentation.js";
// Generated from build/browser/index.ts by build/browser/build.mjs.
