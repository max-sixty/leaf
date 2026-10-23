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
export { renderCommit, afterRender } from "./rendering.js";
export { For, Show, onCleanup } from "solid-js";
export { default as html } from "@solidjs/html";
export { createSemanticApplication } from "./application.js";
export { share, untracked } from "./snapshot.js";
export {
  createPresentationCoordinator,
  createPresentationFlow,
  describeFailure,
} from "./presentation.js";
