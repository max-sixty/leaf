/** Internal framework facade. Content modules import runtime/widget-api.js. */
export { LitElement, html, svg, mathml, noChange, nothing, render } from "lit";
export { Directive, PartType, directive } from "lit/directive.js";
export { AsyncDirective } from "lit/async-directive.js";
export { classMap } from "lit/directives/class-map.js";
export { guard } from "lit/directives/guard.js";
export { ifDefined } from "lit/directives/if-defined.js";
export { keyed } from "lit/directives/keyed.js";
export { live } from "lit/directives/live.js";
export { createRef, ref } from "lit/directives/ref.js";
export { repeat } from "lit/directives/repeat.js";
export { styleMap } from "lit/directives/style-map.js";
export { unsafeHTML } from "lit/directives/unsafe-html.js";
export { when } from "lit/directives/when.js";
export { createSemanticApplication } from "./application.js";
export {
  createPresentationCoordinator,
  createPresentationSchedule,
  describeFailure,
  PRESENTATION_HELD,
} from "./presentation.js";
export type { EpochPresenter } from "./presentation.js";
export type { ApplicationSnapshot, Immutable, SnapshotReading } from "./snapshot.js";
