// @ts-check
/** Internal framework facade. Content modules import runtime/widget-api.js. */
export {
  AsyncDirective,
  Directive,
  LitElement,
  PartType,
  classMap,
  createRef,
  directive,
  guard,
  html,
  keyed,
  live,
  noChange,
  nothing,
  ref,
  render,
  repeat,
  styleMap,
  unsafeHTML,
} from "/vendor/lit.js";
export {
  SignalWatcher,
  batch,
  computed,
  effect,
  signal,
} from "/vendor/signals-core.js";
export { createSemanticApplication } from "./framework/application.js";
export { share, untracked } from "./framework/snapshot.js";
export {
  createPresentationCoordinator,
  createPresentationSchedule,
  describeFailure,
} from "./framework/presentation.js";
