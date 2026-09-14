/** Internal framework bundle. Content modules import runtime/widget-api.js. */
export { LitElement, html, render } from "lit";
export { repeat } from "lit/directives/repeat.js";
export { createApplicationPublisher } from "./snapshot.js";
export { createSemanticApplication } from "./application.js";
export {
  createPresentationCoordinator,
  describeFailure,
} from "./presentation.js";
export type {
  ApplicationSnapshot,
  Immutable,
  SnapshotReading,
} from "./snapshot.js";
