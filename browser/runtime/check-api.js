/* Core observations and native-browser arrangements share the running kernel.
   This diagnostic entry is separate from package authoring. Pure rules are tested
   at their source owner in Node; optional physical geometry lives in the overlay's
   check-api.js so core checks never load that renderer. */
export { startNearWork } from "./readings/presentation.js";
export { declarationFor } from "./state/registry.js";
export { validationWidgetStates } from "./validation.js";
export { drawsAbsentParts, visualPartProblems } from "./state/visual-parts.js";
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
} from "./state/semantic-state.js";
export {
  USER_VIEW_RESTORE_CASES,
  THREADS_IN_PANEL_KEY,
} from "./state/restore-state.js";
export { restoreThreadsInPanel } from "./records/thread/threads-in-panel.js";
export {
  ADDRESSABLE,
  anchorForRange,
  resolveAnchor,
  aimTargets,
  aimTargetAt,
  captured,
  visualParts,
} from "./readings/anchor-resolution.js";
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
} from "./dom/geometry.js";
export { inChrome, uiInside } from "./base/ui-marks.js";
export { anchoringIsReady } from "./readings/anchor-resolution.js";
export { windowHoldsRail } from "./readings/content-layout.js";
export { CONTRIBUTION_ENTRY_SCHEMA } from "./base/contribution-model.js";
export { NOTICE_MS, notice } from "./transport/notifications.js";
export { raiseError } from "./transport/errors.js";
export {
  readingRegions,
  shownRegionBounds,
  userReadingRegion,
  scrollersOf,
  readingRegionFor,
  effectiveScroller,
  readingRegion,
  unconcealedReadingRegions,
  regionScrollBehavior,
  watchReadingRegionTransitions,
} from "./readings/reading-regions.js";
export { carriersOf } from "./readings/scroll-containers.js";
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
} from "./readings/passages.js";
export { shallowSigs } from "./records/projection/presentation.js";
export {
  commandDeclarationsWithin,
  commandsUnread,
  paintKeys,
} from "./dom/keyboard/scopes.js";
export {
  commandRoutes,
  allBindings,
  commandEntries,
  commandPresentations,
  live,
} from "./dom/keyboard/bindings.js";
export {
  availableCommandRoutes,
  stack,
  executeCommand,
} from "./dom/keyboard/dispatch.js";
export {
  captureDraftEditing,
  draftHasContent,
  draftsWaiting,
} from "./records/drafts.js";
export {
  focused,
  handBack,
  onCurrentLocation,
  releaseFocus,
  ringBox,
  takesLetters,
  tabStops,
} from "./dom/focus.js";
export { selectionAnchor } from "./annotations/composing/capture.js";
// A range's owner's word of where the pointer rests, as a passage mark's is.
export { PREVIEW_TIMERS, pointRange } from "./annotations/preview.js";
export { TEXT_BLOCK } from "./state/kernel-facts.js";
export { afterScript, renderingState } from "./base/rendering.js";
export { pageScroller } from "./dom/scrolling.js";
export {
  readingBlock,
  blocksOnScreen,
  capturePlace,
  placeNode,
  restorePlace,
} from "./readings/reading-place.js";
export { replaceEntry } from "./records/history.js";
export { walkOrigin, heldObligation, placeOf } from "./records/current-target.js";
export { beginWalk, walkPosition } from "./records/walk-position.js";
export { threadCounts } from "./state/thread/model.js";
export {
  closeNativeLayer,
  nativeLayers,
  showNativeLayer,
} from "./dom/keyboard/layer-stack.js";
export { scrollAxes, elementFrame } from "./dom/element-frame.js";
export { carriedBox, elementBorderFrame, innerBox } from "./dom/element-axes.js";
export { fitsWhole, alreadyShown } from "./readings/landing-scroll.js";
export {
  browserScrolls,
  holdScroll,
  scrolling,
  setScroll,
  watchScrollEnds,
} from "./dom/arrivals.js";
export { pageScopes } from "./dom/keyboard/register.js";
export {
  chromeSheet,
  chromeSharedClasses,
  marksSheet,
  annotationSheets,
} from "./base/stylesheets.js";
export { claimed } from "./records/thread/surfaces.js";
export { writingStore, userStore, PAGE_SCOPE } from "./state/storage.js";
export { tabStore } from "./state/tab-store.js";
export {
  frameVisibility,
  onFrameVisibility,
  readSampleVisibility,
} from "./base/frame-visibility.js";
export { createPresentationSchedule } from "./base/presentation.js";
export { reachScrollers, releaseReachStop } from "./dom/reach.js";
export { reveal, dragHeld } from "./dom/widget-elements.js";
export { replyIsEditing } from "./records/thread/replies.js";
export { THREAD, SAY_BOX } from "./records/thread/selectors.js";
export { registerSampleCommand } from "./host/sample-child.js";
export { recordInteraction } from "./transport/interaction-log.js";
export { bringBackSurfaceOf } from "./readings/off-flow.js";
export { TEXT_BOX, WORKS } from "./dom/control-selectors.js";
export { readingReturn, completeReadingReturn } from "./base/reading-continuity.js";

export { servedElements } from "./features/version.js";
export { versionPicker } from "./features/version-picker.js";
export { colourableAs, colouredAs } from "./readings/syntax.js";

export { pageRange } from "./dom/native-selection.js";
export { leavesOffered } from "./host/live-leaves.js";
