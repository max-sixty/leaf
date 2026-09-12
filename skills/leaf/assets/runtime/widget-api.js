/* The one helper surface behavior modules import. Every capability is reexported from
   its domain owner; owners import one another, and leaf.js only boots. */
import { requestAvailable, sendRequest, watchRequestLifecycle } from "./application.js";
import { createDefineRequestElement } from "./request-elements.js";

export { READER_VIEW_RESTORE_CASES } from "./restore-state.js";
export {
  arrangeReadingElement,
  defineReadingPaneElement,
  fitRootReadingElement,
  registerReadingElement,
} from "./reading-layout.js";
export { addressableWord } from "./anchor-resolution.js";
export { navigateToDatum } from "./application.js";
export { shownBand, shownBox, shownParts } from "./geometry.js";
export { inUi, uiInside } from "./shadow.js";
export { answeredContext, askSource } from "./asks/model.js";
export { openAsks, watchAsks } from "./application.js";
export { registerVisualParts } from "./visual-parts.js";
export { conversationBox, registerThreadSurface } from "./application.js";
export { conversationInput } from "./conversation/landing.js";
export { landInConversation } from "./application.js";
export { wireInput } from "./application.js";
export { DISCLOSE } from "./keyboard/disclosure.js";
export { PRESS, labelOf, walkRows } from "./keyboard/bindings.js";
export { focused, keys as commands, paintKeys, saying } from "./keyboard/scopes.js";
export { repaint } from "./repaint.js";
export { beginWalk, listWalkPosition } from "./walk-position.js";
export {
  MARGIN_ENTRY_SCHEMA,
  marginEntry,
  setMarginEntryState,
  syncMarginAgentPhase,
  syncMarginEntrySelection,
  registerMarginContribution,
} from "./margin-entries.js";
export { loadMarkdown, renderMarkdown } from "./markdown.js";
export { isCanonicalMediaUrl, scopedMediaUrl } from "./media.js";
export { pageScroller } from "./scrolling.js";
export {
  compoundReadingRegionId,
  effectiveScroller,
  readingAllocation,
  readingPosture,
  readingRegion,
  readingRegionFor,
  readingRegions,
  registerReadingArrangement,
  registerReadingRegion,
  scrollerFor,
  shownRegionBounds,
  watchReadingRegionTransitions,
} from "./reading-regions.js";
export { announce, notice } from "./notifications.js";
export { actionAvailable, actionStands, sendAction } from "./application.js";
export { requestAvailable, sendRequest, watchRequestLifecycle };
export const defineRequestElement = createDefineRequestElement({
  requestAvailable,
  sendRequest,
  watchRequestLifecycle,
});
export { alignText, alignedNodes } from "./text-alignment.js";
export {
  inChrome,
  quoteFrom,
  renderRetired,
  says,
  textNodesUnder,
  verbatimBoundaryIdentity,
  verbatimOwnerIdentity,
  wrote,
} from "./passages.js";
export { ago, clocked, clockValue, quietSince } from "./presence.js";
export {
  shallowSigs,
  standingState,
  undoableAction,
  withdraw,
  withdrawableAction,
} from "./application.js";
export { shadowStage } from "./shadow-stage.js";
export { agentName, revisionLabel } from "./context.js";
export { loadDataFragment, watchData } from "./data.js";
export { clearDraft, loadDraft, saveDraft, sendDraft, watchDraft } from "./drafts.js";
export {
  declarationFor,
  elementsDeclaring,
  layerFact,
  matchesWhen,
} from "./registry.js";
export {
  FOLD_MS,
  motion,
  onMotionPreferenceChange,
  reducedMotion,
  scrollBehavior,
} from "./motion.js";
export { PRESENTATION, quietWord } from "./presentation.js";
export { projectData } from "./application.js";
export { tabStore } from "./storage.js";
export {
  highlightBlocks,
  langForPath,
  synNodes,
  syntax,
  tokenLines,
} from "./syntax.js";
export { dataBody, failSoft, once, settle } from "./widget-upgrade.js";
export { actionSequence, watchActions, watchUpdates } from "./application.js";
export { publishedAt, saidAt, updateSequence, watchHistory } from "./updates.js";
export {
  HIDDEN,
  LAYOUT,
  dragging,
  keeps,
  layoutChanged,
  measure,
  offer,
  projectionChanged,
  quoted,
  reachedForWords,
  relabel,
  reserve,
  selectableOffer,
  worksInside,
} from "./widget-elements.js";
