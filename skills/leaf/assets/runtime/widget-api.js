/* The one helper surface behavior modules import. Every capability is reexported from
   its domain owner; leaf.js composes those owners and owns boot only. */
export { ARRANGEMENTS } from "./arrangements.js";
export { itemWord } from "./anchors.js";
export { shownBand, shownBox, shownParts } from "./geometry.js";
export { answeredContext, decisionSource, openDecisions } from "./decisions/model.js";
export { conversationBox } from "./conversation/box.js";
export { conversationInput, landInConversation } from "./conversation/landing.js";
export { DISCLOSE } from "./keyboard/disclosure.js";
export { PRESS, labelOf } from "./keyboard/bindings.js";
export { keys, paintKeys, saying } from "./keyboard/scopes.js";
export { marginAction, registerMarginItem } from "./living-margin.js";
export { scrollerFor } from "./navigation.js";
export { announce, toast } from "./notifications.js";
export { actionAvailable, actionStands, sendAction } from "./outbox.js";
export { requestAvailable, sendRequest, watchRequestLifecycle } from "./requests.js";
export { alignText } from "./text-alignment.js";
export {
  inChrome,
  inUi,
  renderRetired,
  says,
  textNodesUnder,
  uiInside,
  wrote,
} from "./passages.js";
export { ago, quietSince } from "./presence.js";
export { shallowSigs, standingState } from "./projection.js";
export { shadowStage } from "./shadow.js";
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
  LAYOUT,
  dragging,
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
