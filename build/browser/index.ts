/** Internal framework facade. Content modules import runtime/widget-api.js. */
export {
  getObserver,
  runWithOwner,
  createSignal,
  createMemo,
  createRoot,
  createEffect,
  flush,
  untrack,
} from "@solidjs/signals";
export { subscribe, watchReaction } from "./observe.js";
export { createView, resetViewsWithin } from "./views.js";
export { For, Show, onCleanup } from "solid-js";
export { default as html } from "@solidjs/html";
export { createSemanticApplication } from "./application.js";
export { share, untracked } from "./snapshot.js";
export {
  createPresentationCoordinator,
  createPresentationSchedule,
  describeFailure,
} from "./presentation.js";
