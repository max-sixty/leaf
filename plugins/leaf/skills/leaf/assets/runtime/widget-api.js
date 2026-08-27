/* The one helper surface behavior modules import.

   Domain owners stay directly importable to the browser entry while this module
   decides which of their capabilities widgets may rely on. The entry module still
   contains helper implementations; these explicit reexports are temporary until those
   implementations move to their owners. */
export {
  ARRANGEMENTS,
  DISCLOSE,
  PRESS,
  actionAvailable,
  actionStands,
  ago,
  alignText,
  announce,
  answeredContext,
  askSource,
  conversationBox,
  conversationInput,
  dragging,
  inChrome,
  inUi,
  itemWord,
  keys,
  labelOf,
  landInConversation,
  openAsks,
  paintKeys,
  quietSince,
  renderRetired,
  saying,
  says,
  scrollerFor,
  sendAction,
  shadowStage,
  shallowSigs,
  shownBand,
  shownBox,
  shownParts,
  standingState,
  textNodesUnder,
  toast,
  uiInside,
  wrote,
} from "../leaf.js";
export { agentName, revisionLabel } from "./context.js";
export { watchData } from "./data.js";
export { clearDraft, loadDraft, saveDraft, sendDraft, watchDraft } from "./drafts.js";
export {
  closestDeclaring,
  declarationFor,
  elementsDeclaring,
  layerFact,
  matchesWhen,
} from "./registry.js";
export { FOLD_MS, REDUCED, SCROLL, motion } from "./motion.js";
export { quietWord } from "./presentation.js";
export { projectData } from "./projection/data.js";
export { tabStore } from "./storage.js";
export { langForPath, synNodes, syntax, tokenLines } from "./syntax.js";
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
  measure,
  offer,
  quoted,
  reachedForWords,
  relabel,
  reserve,
  worksInside,
} from "./widget-elements.js";
