/* Core observations and native-browser arrangements share the running kernel.
   This diagnostic entry is separate from package authoring. Pure rules are tested
   at their source owner in Node; optional physical geometry lives in the overlay's
   check-api.js so core checks never load that renderer. */
export { exceptionText } from "./layer-client.js";
export { validationWidgetStates } from "./validation.js";
export { visualPartProblems } from "./visual-parts.js";
export {
  readApplication,
  watchSemantic,
  applicationPresented,
  readApplicationPresentation,
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
  bannerFoot,
  seenRect,
  growthAfterIsSeen,
  stuckBox,
  stackLevel,
} from "./geometry.js";
export { renderedParent, uiInside, upFrom } from "./shadow.js";
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
  pageDocument,
  quoteFrom,
  verbatimBoundaryIdentity,
  verbatimOwnerIdentity,
  pageRange,
  closestAcross,
  pageText,
  fencePassageParts,
  findQuote,
  segmentsIn,
  spanIn,
  settledAway,
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
export {
  whereDraft,
  storedDraft,
  captureDraftEditing,
  draftEditingStands,
} from "./drafts.js";
export { onStanding, releaseFocus, takesLetters, tabStops } from "./focus.js";
export { selectionAnchor } from "./composing/capture.js";
export { TEXT_BLOCK } from "./passage-facts.js";
export { renderingState } from "./rendering.js";
export { readingBlock, blocksOnScreen } from "./reading-place.js";
export { walkOrigin, heldAsk, placeOf } from "./standing-target.js";
export { walkPosition } from "./walk-position.js";
export { nativeLayers } from "./keyboard/layer-stack.js";
export { scrollAxes, elementFrame } from "./element-frame.js";
export { fitsWhole, alreadyShown } from "./landing-scroll.js";
export { pageScopes } from "./keyboard/register.js";
export {
  chromeSheet,
  chromeSharedClasses,
  marksSheet,
  annotationSheets,
  annotationMarkSheets,
} from "./stylesheets.js";
export { surfaceFocusTarget, claimed } from "./thread/surfaces.js";
export { runtimeRootState } from "./root-state.js";
export { tabStore, draftStore, userStore, PAGE_SCOPE } from "./storage.js";
export { sampleVisibility, readSampleVisibility } from "./sample-visibility.js";
export { scrollMotions, followScroll } from "./scroll-motion.js";
export { observeQueuedWork, bindQueuedWork } from "./queued-work.js";
export { createPresentationSchedule } from "/vendor/browser-runtime.js";
export {
  BANNER_CONTROL_RANK,
  registerBannerControl,
  showBannerControl,
  showNews,
  markBannerControl,
  returnToBannerControl,
} from "./banner-toolbar.js";
export { reachScrollers, releaseReachStop } from "./reach.js";
export { reveal, dragHeld } from "./widget-elements.js";
export { flashDuration, agentArrivalDuration } from "./motion.js";
export { replyIsEditing } from "./thread/replies.js";
export { THREAD, SAY_BOX } from "./thread/selectors.js";
export { alignInlineText, sentenceUnits } from "./text-alignment.js";
export { registerSampleCommand } from "./sample-child.js";
export { recordInteraction } from "./interaction-log.js";
export { heldThreadId, replyDestination } from "./thread/focus.js";
export { restrictUserIntent } from "./user-intent.js";
export { bringBackSurfaceOf } from "./off-flow.js";
export { WORKS } from "./control-selectors.js";
export { readingReturn, completeReadingReturn } from "./reading-continuity.js";
