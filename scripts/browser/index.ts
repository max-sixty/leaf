/** Internal framework bundle. Content modules import runtime/widget-api.js. */
export { LitElement, html } from "lit";
export { createApplicationPublisher } from "./snapshot.js";
export type {
  ApplicationSnapshot,
  Immutable,
  SnapshotReading,
} from "./snapshot.js";
