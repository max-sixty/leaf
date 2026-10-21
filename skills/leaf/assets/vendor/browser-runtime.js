/** Internal framework facade. Content modules import runtime/widget-api.js. */
export {
  createSignal,
  createMemo,
  createRoot,
  createEffect,
  createTrackedEffect,
  flush,
  untrack,
} from "./solid.js";
export { watchEffect } from "./browser-runtime/observe.js";
export { createView, resetViewsWithin } from "./browser-runtime/views.js";
export { For, Show, onCleanup } from "./solid.js";
export { default as html } from "./solid.js";
export { createSemanticApplication } from "./browser-runtime/application.js";
export { collectReads, outsideReading, share, untracked } from "./browser-runtime/snapshot.js";
export {
  createPresentationCoordinator,
  createPresentationSchedule,
  describeFailure,
} from "./browser-runtime/presentation.js";
// Generated from build/browser/index.ts by build/browser/build.mjs.
