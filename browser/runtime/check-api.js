/* Core observations and native-browser arrangements share the running kernel.
   This diagnostic entry is separate from package authoring. Pure rules are tested
   at their source owner in Node; optional physical geometry lives in the overlay's
   check-api.js so core checks never load that renderer. */
export { exceptionText } from "./exception.js";
export { validationWidgetStates } from "./validation.js";
export { visualPartProblems } from "./visual-parts.js";
export {
  readApplication,
  watchSemantic,
  applicationPresented,
  readApplicationPresentation,
  presentDocument,
  whenApplicationPresented,
  whenApplicationRegionsPresented,
  whenDocumentPresented,
} from "./semantic-state.js";
export { USER_VIEW_RESTORE_CASES } from "./restore-state.js";
export {
  ADDRESSABLE,
  anchorForRange,
  resolveAnchor,
  aimTargets,
  aimTargetAt,
} from "./anchor-resolution.js";
export {
  shownBand,
  shownBox,
  shownRect,
  visibleBand,
  landingBand,
  userScrollport,
  seenRect,
  growthAfterIsSeen,
  stuckBox,
  stackLevel,
  shownParts,
} from "./geometry.js";
export { skipped } from "./shown-box.js";
export { renderedParent, uiInside, upFrom } from "./shadow.js";
export { authoredBody } from "./widget-elements.js";
export {
  readingRegions,
  shownRegionBounds,
  userReadingRegion,
  scrollersOf,
  readingRegionFor,
  effectiveScroller,
  readingRegion,
  unconcealedReadingRegions,
} from "./reading-regions.js";
export {
  layoutBox,
  pageDocument,
  inPage,
  quoteFrom,
  verbatimBoundaryIdentity,
  verbatimOwnerIdentity,
  closestAcross,
  pageText,
  fencePassageParts,
  findQuote,
  segmentsIn,
  spanIn,
  settledAway,
  textNodesUnder,
} from "./passages.js";
export { shallowSigs } from "./projection/presentation.js";
export { commandDeclarationsWithin } from "./keyboard/scopes.js";
export {
  commandRoutes,
  allBindings,
  commandEntries,
  commandPresentations,
  live,
} from "./keyboard/bindings.js";
export { availableCommandRoutes, stack, executeCommand } from "./keyboard/dispatch.js";
export { whereDraft, storedDraft, captureDraftEditing } from "./drafts.js";
export { onCurrentLocation, releaseFocus, takesLetters, tabStops } from "./focus.js";
export { selectionAnchor } from "./composing/capture.js";
export { TEXT_BLOCK } from "./kernel-facts.js";
export { renderingState } from "./rendering.js";
export {
  readingBlock,
  blocksOnScreen,
  capturePlace,
  placeNode,
} from "./reading-place.js";
export { walkOrigin, heldObligation, placeOf } from "./current-target.js";
export { walkPosition } from "./walk-position.js";
export { threadCounts } from "./thread/model.js";
export { nativeLayers } from "./keyboard/layer-stack.js";
export { scrollAxes, elementFrame } from "./element-frame.js";
export { fitsWhole, alreadyShown } from "./landing-scroll.js";
export { scrollGlides, scrolling, watchScrollEnds } from "./arrivals.js";
export { pageScopes } from "./keyboard/register.js";
export {
  chromeSheet,
  chromeSharedClasses,
  marksSheet,
  annotationSheets,
  annotationMarkSheets,
} from "./stylesheets.js";
export { claimed } from "./thread/surfaces.js";
export { runtimeRootState } from "./root-state.js";
export { draftStore, userStore, PAGE_SCOPE } from "./storage.js";
export { tabStore } from "./tab-store.js";
export {
  frameVisibility,
  onFrameVisibility,
  readSampleVisibility,
} from "./frame-visibility.js";
export { observeQueuedWork, bindQueuedWork } from "./queued-work.js";
export { createPresentationSchedule } from "/runtime/framework.js";
export { reachScrollers, releaseReachStop } from "./reach.js";
export { reveal, dragHeld } from "./widget-elements.js";
export { flashDuration, agentArrivalDuration } from "./motion.js";
export { replyIsEditing } from "./thread/replies.js";
export { THREAD, SAY_BOX } from "./thread/selectors.js";
export { alignInlineText, sentenceUnits } from "./text-alignment.js";
export { registerSampleCommand } from "./sample-child.js";
export { recordInteraction } from "./interaction-log.js";
export { bringBackSurfaceOf } from "./off-flow.js";
export { WORKS } from "./control-selectors.js";
export { readingReturn, completeReadingReturn } from "./reading-continuity.js";

export { observeOutputs } from "./data.js";
export { servedElements } from "./version.js";

export { pageRange } from "./native-selection.js";
