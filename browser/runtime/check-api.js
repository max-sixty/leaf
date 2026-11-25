/* Core observations and native-browser arrangements share the running kernel.
   This diagnostic entry is separate from package authoring. Pure rules are tested
   at their source owner in Node; optional physical geometry lives in the overlay's
   check-api.js so core checks never load that renderer. */
export { startNearWork } from "./presentation.js";
export { clockValue } from "./presence.js";
export { declarationFor } from "./registry.js";
export { validationWidgetStates } from "./validation.js";
export { visualPartProblems } from "./visual-parts.js";
export {
  readApplication,
  watchSemantic,
  applicationPresented,
  readApplicationPresentation,
  presentDocument,
  projectionRegionsPresented,
  whenApplicationPresented,
  whenApplicationRegionsPresented,
  whenDocumentPresented,
} from "./semantic-state.js";
export { USER_VIEW_RESTORE_CASES, THREADS_IN_PANEL_KEY } from "./restore-state.js";
export { restoreThreadsInPanel } from "./thread/threads-in-panel.js";
export {
  ADDRESSABLE,
  anchorForRange,
  resolveAnchor,
  aimTargets,
  aimTargetAt,
  captured,
  visualParts,
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
  growthIsSeen,
  landingInsets,
  shownWindow,
  stuckBox,
  stackLevel,
  shownParts,
} from "./geometry.js";
export { inChrome, uiInside } from "./ui-marks.js";
export { anchoringIsReady } from "./anchor-resolution.js";
export { windowHoldsRail } from "./content-layout.js";
export { CONTRIBUTION_ENTRY_SCHEMA } from "./contribution-model.js";
export { presentContributionEntry } from "./contribution-controls.js";
export { NOTICE_MS, notice } from "./notifications.js";
export { raiseError } from "./errors.js";
export {
  readingRegions,
  scrollerFor,
  shownRegionBounds,
  userReadingRegion,
  scrollersOf,
  readingRegionFor,
  effectiveScroller,
  readingRegion,
  unconcealedReadingRegions,
  regionScrollBehavior,
  preserveReadingRegions,
  watchReadingRegionTransitions,
} from "./reading-regions.js";
export { carriersOf } from "./scroll-containers.js";
export {
  layoutBox,
  pageDocument,
  inPage,
  quoteFrom,
  verbatimBoundaryIdentity,
  verbatimOwnerIdentity,
  pageText,
  fencePassageParts,
  findQuote,
  segmentsIn,
  spanIn,
  settledAway,
  textNodesUnder,
} from "./passages.js";
export { shallowSigs } from "./projection/presentation.js";
export {
  commandDeclarationsWithin,
  commandsUnread,
  paintKeys,
} from "./keyboard/scopes.js";
export {
  commandRoutes,
  allBindings,
  commandEntries,
  commandPresentations,
  live,
} from "./keyboard/bindings.js";
export { availableCommandRoutes, stack, executeCommand } from "./keyboard/dispatch.js";
export { captureDraftEditing, draftHasContent, draftsWaiting } from "./drafts.js";
export {
  focused,
  handBack,
  onCurrentLocation,
  releaseFocus,
  ringBox,
  takesLetters,
  tabStops,
} from "./focus.js";
export { selectionAnchor } from "./composing/capture.js";
// A range's owner's word of where the pointer rests, as a passage mark's is.
export { PREVIEW_TIMERS, pointRange } from "./preview.js";
export { TEXT_BLOCK } from "./kernel-facts.js";
export { afterScript, renderingState } from "./rendering.js";
export { pageScroller } from "./scrolling.js";
export {
  readingBlock,
  blocksOnScreen,
  capturePlace,
  placeNode,
  restorePlace,
} from "./reading-place.js";
export { replaceEntry } from "./history.js";
export { walkOrigin, heldObligation, placeOf } from "./current-target.js";
export { beginWalk, walkPosition } from "./walk-position.js";
export { threadCounts } from "./thread/model.js";
export {
  closeNativeLayer,
  nativeLayers,
  showNativeLayer,
} from "./keyboard/layer-stack.js";
export { scrollAxes, elementFrame } from "./element-frame.js";
export { carriedBox, elementBorderFrame, innerBox } from "./element-axes.js";
export { fitsWhole, alreadyShown } from "./landing-scroll.js";
export {
  browserScrolls,
  holdScroll,
  scrolling,
  setScroll,
  watchScrollEnds,
} from "./arrivals.js";
export { pageScopes } from "./keyboard/register.js";
export {
  chromeSheet,
  chromeSharedClasses,
  marksSheet,
  annotationSheets,
} from "./stylesheets.js";
export { claimed } from "./thread/surfaces.js";
export { writingStore, userStore, PAGE_SCOPE } from "./storage.js";
export { tabStore } from "./tab-store.js";
export {
  frameVisibility,
  onFrameVisibility,
  readSampleVisibility,
} from "./frame-visibility.js";
export { createPresentationSchedule } from "/runtime/framework.js";
export { reachScrollers, releaseReachStop } from "./reach.js";
export { reveal, dragHeld } from "./widget-elements.js";
export { replyIsEditing } from "./thread/replies.js";
export { THREAD, SAY_BOX } from "./thread/selectors.js";
export { anchorLabel } from "./thread/messages.js";
export { registerSampleCommand } from "./sample-child.js";
export { recordInteraction } from "./interaction-log.js";
export { bringBackSurfaceOf } from "./off-flow.js";
export { TEXT_BOX, WORKS } from "./control-selectors.js";
export { readingReturn, completeReadingReturn } from "./reading-continuity.js";

export { servedElements } from "./version.js";
export { versionPicker } from "./version-picker.js";
export { colourableAs, colouredAs } from "./syntax.js";

export { pageRange } from "./native-selection.js";
export { leavesOffered } from "./live-leaves.js";
