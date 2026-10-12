/* Browser render checks share these observations with the running kernel. This
   diagnostic entry is separate from the package authoring API. */
export { exceptionText } from "./layer-client.js";
export { validationWidgetStates } from "./validation.js";
export { unrevealedVisualParts, visualPartProblems } from "./visual-parts.js";
export {
  readApplication,
  watchSemantic,
  applicationPresented,
} from "./semantic-state.js";
export { USER_VIEW_RESTORE_CASES } from "./restore-state.js";
export { ADDRESSABLE } from "./anchor-resolution.js";
export { shownBand, shownBox } from "./geometry.js";
export { renderedParent, uiInside, upFrom } from "./shadow.js";
export { readingRegions, shownRegionBounds } from "./reading-regions.js";
export {
  quoteFrom,
  verbatimBoundaryIdentity,
  verbatimOwnerIdentity,
} from "./passages.js";
export { shallowSigs } from "./projection/presentation.js";
export { commandDeclarationsWithin } from "./keyboard/scopes.js";
export { commandRoutes } from "./keyboard/bindings.js";
