/* The one helper surface behavior modules import. Every capability is reexported from
   its domain owner; owners import one another, and leaf.js only boots. */
export { ARRANGEMENTS } from "./arrangements.js";
export {
  arrangeReadingElement,
  defineReadingPaneElement,
  fitRootReadingElement,
  registerArrangedElement,
} from "./reading-layout.js";
export { itemWord } from "./anchor-resolution.js";
export { navigateToDatum } from "./application.js";
export { shownBand, shownBox, shownParts } from "./geometry.js";
export { inUi, uiInside } from "./shadow.js";
export { answeredContext, askSource, openAsks, watchAsks } from "./asks/model.js";
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
  MARGIN_ELEMENT_SCHEMA,
  marginElement,
  marginElementState,
  registerMarginContribution,
} from "./margin-elements.js";
export { loadMarkdown, renderMarkdown } from "./markdown.js";
export { pageScroller } from "./scrolling.js";
export {
  compoundReadingRegionId,
  effectiveScroller,
  readingAllocation,
  readingPosture,
  readingRegion,
  readingRegionFor,
  readingRegions,
  registerArrangement,
  registerReadingRegion,
  scrollerFor,
  shownRegionBounds,
  watchReadingRegionTransitions,
} from "./reading-regions.js";
export { announce, notice } from "./notifications.js";
export {
  actionAvailable,
  actionStands,
  requestAvailable,
  sendAction,
  sendRequest,
} from "./application.js";
export { watchRequestLifecycle } from "./requests.js";
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
export { shallowSigs, standingState, undoableAction, withdraw } from "./application.js";
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
  quoted,
  reachedForWords,
  relabel,
  reserve,
  selectableOffer,
  worksInside,
} from "./widget-elements.js";
