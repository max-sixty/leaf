/** Internal framework bundle. Content modules import runtime/widget-api.js. */
export { LitElement, html, nothing, render } from "lit";
export { repeat } from "lit/directives/repeat.js";
export { createSemanticApplication } from "./application.js";
export {
  createPresentationCoordinator,
  createPresentationSchedule,
  describeFailure,
  PRESENTATION_HELD,
} from "./presentation.js";
export type { EpochPresenter } from "./presentation.js";
export type { ApplicationSnapshot, Immutable, SnapshotReading } from "./snapshot.js";
