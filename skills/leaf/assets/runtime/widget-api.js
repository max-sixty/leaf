/* The one helper surface behavior modules import. Every capability is reexported from
   its domain owner; owners import one another, and leaf.js only boots. */
export { ARRANGEMENTS } from "./arrangements.js";
export { itemWord, navigateToDatum } from "./anchors.js";
export { shownBand, shownBox, shownParts } from "./geometry.js";
export { inUi, uiInside } from "./shadow.js";
export { answeredContext, askSource, openAsks, watchAsks } from "./asks/model.js";
export { registerVisualParts } from "./visual-parts.js";
export { conversationBox } from "./conversation/box.js";
export { registerThreadSurface } from "./conversation/surfaces.js";
export { conversationInput, landInConversation } from "./conversation/landing.js";
export { DISCLOSE } from "./keyboard/disclosure.js";
export { PRESS, labelOf, walkRows } from "./keyboard/bindings.js";
export { focused, keys as commands, paintKeys, saying } from "./keyboard/scopes.js";
export {
  marginButton,
  marginButtonState,
  registerMarginItem,
} from "./living-margin.js";
export { loadMarkdown, renderMarkdown } from "./markdown.js";
export { scrollerFor } from "./navigation.js";
export { pageScroller } from "./scrolling.js";
export { announce, notice } from "./notifications.js";
export { actionAvailable, actionStands, sendAction } from "./outbox.js";
export { requestAvailable, sendRequest, watchRequestLifecycle } from "./requests.js";
export { alignText, alignedNodes } from "./text-alignment.js";
export { inChrome, renderRetired, says, textNodesUnder, wrote } from "./passages.js";
export { ago, clocked, clockValue, quietSince } from "./presence.js";
export { shallowSigs, undoableAction, withdraw } from "./projection.js";
export { standingState } from "./projection/fold.js";
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
export { quietWord } from "./presentation.js";
export { projectData } from "./projection/data.js";
export { tabStore } from "./storage.js";
export {
  highlightBlocks,
  langForPath,
  synNodes,
  syntax,
  tokenLines,
} from "./syntax.js";
export { dataBody, failSoft, once, settle } from "./widget-upgrade.js";
export {
  actionSequence,
  publishedAt,
  saidAt,
  updateSequence,
  watchActions,
  watchHistory,
  watchUpdates,
} from "./updates.js";
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
