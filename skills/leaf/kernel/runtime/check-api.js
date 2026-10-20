import {
  availableCommandRoutes,
  executeCommand,
  registerSampleCommand,
  stack
} from "./bundle-sample-child.js";
import {
  USER_VIEW_RESTORE_CASES
} from "./bundle-restore-state.js";
import {
  shallowSigs
} from "./bundle-projection~presentation.js";
import {
  PAGE_SCOPE,
  SAY_BOX,
  THREAD,
  alreadyShown,
  blocksOnScreen,
  bringBackSurfaceOf,
  captureDraftEditing,
  claimed,
  completeReadingReturn,
  draftStore,
  fitsWhole,
  heldObligation,
  pageScopes,
  placeOf,
  readingBlock,
  readingReturn,
  replyIsEditing,
  selectionAnchor,
  storedDraft,
  surfaceFocusTarget,
  tabStore,
  userStore,
  walkOrigin,
  walkPosition,
  whereDraft
} from "./bundle-user-intent.js";
import {
  domValue
} from "./bundle-widget-upgrade.js";
import "./bundle-media.js";
import {
  agentArrivalDuration,
  flashDuration
} from "./bundle-motion.js";
import {
  ADDRESSABLE,
  aimTargetAt,
  aimTargets,
  anchorForRange,
  elementFrame,
  resolveAnchor,
  scrollAxes,
  visualPartProblems
} from "./bundle-chrome.js";
import "./bundle-initial-render.js";
import {
  effectiveScroller,
  reachScrollers,
  readingRegion,
  readingRegionFor,
  readingRegions,
  releaseReachStop,
  scrollersOf,
  shownRegionBounds,
  unconcealedReadingRegions,
  userReadingRegion
} from "./bundle-presence.js";
import {
  annotationMarkSheets,
  annotationSheets,
  chromeSharedClasses,
  chromeSheet,
  marksSheet
} from "./bundle-stylesheets.js";
import {
  TEXT_BLOCK,
  alignInlineText,
  closestAcross,
  elementById,
  fencePassageParts,
  findQuote,
  layoutBox,
  pageDocument,
  pageRange,
  pageText,
  quoteFrom,
  segmentsIn,
  sentenceUnits,
  settledAway,
  spanIn,
  verbatimBoundaryIdentity,
  verbatimOwnerIdentity
} from "./bundle-passage-facts.js";
import {
  allBindings,
  commandDeclarationsWithin,
  commandEntries,
  commandPresentations,
  commandRoutes,
  dragHeld,
  exceptionText,
  growthAfterIsSeen,
  landingBand,
  live,
  nativeLayers,
  recordInteraction,
  reveal,
  runtimeRootState,
  seenRect,
  shownBand,
  shownBox,
  shownRect,
  stackLevel,
  stuckBox,
  uiInside,
  userScrollport,
  visibleBand
} from "./bundle-page-paint.js";
import {
  applicationPresented,
  readApplication,
  readApplicationPresentation,
  selectWidgets,
  watchSemantic,
  whenApplicationPresented,
  whenApplicationRegionsPresented,
  whenDocumentPresented
} from "./bundle-semantic-state.js";
import {
  WORKS,
  frameVisibility,
  onFrameVisibility,
  onStanding,
  readSampleVisibility,
  releaseFocus,
  renderedParent,
  renderingState,
  tabStops,
  takesLetters,
  upFrom
} from "./bundle-frame-visibility.js";
import {
  bindQueuedWork,
  createPresentationSchedule,
  observeQueuedWork
} from "./bundle-queued-work.js";
import "./bundle-__export.js";

// runtime/validation.js
function validationWidgetStates(eventIds = null) {
  return [...selectWidgets(eventIds)].map(([id, { state, specs }]) => ({
    id,
    get widget() {
      return elementById(id);
    },
    state,
    read: () => [...specs].filter(([, spec]) => spec.record?.kind === "body").map(([verb, spec]) => [verb, domValue(elementById(id), spec.record)])
  }));
}
export {
  ADDRESSABLE,
  PAGE_SCOPE,
  SAY_BOX,
  TEXT_BLOCK,
  THREAD,
  USER_VIEW_RESTORE_CASES,
  WORKS,
  agentArrivalDuration,
  aimTargetAt,
  aimTargets,
  alignInlineText,
  allBindings,
  alreadyShown,
  anchorForRange,
  annotationMarkSheets,
  annotationSheets,
  applicationPresented,
  availableCommandRoutes,
  bindQueuedWork,
  blocksOnScreen,
  bringBackSurfaceOf,
  captureDraftEditing,
  chromeSharedClasses,
  chromeSheet,
  claimed,
  closestAcross,
  commandDeclarationsWithin,
  commandEntries,
  commandPresentations,
  commandRoutes,
  completeReadingReturn,
  createPresentationSchedule,
  draftStore,
  dragHeld,
  effectiveScroller,
  elementFrame,
  exceptionText,
  executeCommand,
  fencePassageParts,
  findQuote,
  fitsWhole,
  flashDuration,
  frameVisibility,
  growthAfterIsSeen,
  heldObligation,
  landingBand,
  layoutBox,
  live,
  marksSheet,
  nativeLayers,
  observeQueuedWork,
  onFrameVisibility,
  onStanding,
  pageDocument,
  pageRange,
  pageScopes,
  pageText,
  placeOf,
  quoteFrom,
  reachScrollers,
  readApplication,
  readApplicationPresentation,
  readSampleVisibility,
  readingBlock,
  readingRegion,
  readingRegionFor,
  readingRegions,
  readingReturn,
  recordInteraction,
  registerSampleCommand,
  releaseFocus,
  releaseReachStop,
  renderedParent,
  renderingState,
  replyIsEditing,
  resolveAnchor,
  reveal,
  runtimeRootState,
  scrollAxes,
  scrollersOf,
  seenRect,
  segmentsIn,
  selectionAnchor,
  sentenceUnits,
  settledAway,
  shallowSigs,
  shownBand,
  shownBox,
  shownRect,
  shownRegionBounds,
  spanIn,
  stack,
  stackLevel,
  storedDraft,
  stuckBox,
  surfaceFocusTarget,
  tabStops,
  tabStore,
  takesLetters,
  uiInside,
  unconcealedReadingRegions,
  upFrom,
  userReadingRegion,
  userScrollport,
  userStore,
  validationWidgetStates,
  verbatimBoundaryIdentity,
  verbatimOwnerIdentity,
  visibleBand,
  visualPartProblems,
  walkOrigin,
  walkPosition,
  watchSemantic,
  whenApplicationPresented,
  whenApplicationRegionsPresented,
  whenDocumentPresented,
  whereDraft
};
