/** Internal framework facade. Content modules import runtime/widget-api.js. */
export { LitElement, html, noChange, nothing, render } from "lit";
export { Directive, PartType, directive } from "lit/directive.js";
export { AsyncDirective } from "lit/async-directive.js";
export { classMap } from "lit/directives/class-map.js";
export { guard } from "lit/directives/guard.js";
export { keyed } from "lit/directives/keyed.js";
export { live } from "lit/directives/live.js";
export { createRef, ref } from "lit/directives/ref.js";
export { repeat } from "lit/directives/repeat.js";
export { styleMap } from "lit/directives/style-map.js";
export { unsafeHTML } from "lit/directives/unsafe-html.js";
export { effect, signal } from "@preact/signals-core";
export { createSemanticApplication } from "./application.js";
export { collectReads, share, untracked } from "./snapshot.js";
export {
  createPresentationCoordinator,
  createPresentationSchedule,
  describeFailure,
  PRESENTATION_HELD,
} from "./presentation.js";
