/* The one helper surface behavior modules import. Capabilities come from their
   domain owners; optional hosts load when requested. Owners import one another,
   and leaf.js only boots.

   The runtime tree is not the set of importers. Package widget modules and the render
   gate's probes under `leaf/render-checks/` both reach this file over HTTP from the
   served page, as `/runtime/widget-api.js`, so a search of `runtime/` for a re-export's
   importer comes back empty whether or not the export is reachable. What answers that
   question is the browser gate, which fails to parse every probe module at once. */
import { defineRequestElement } from "./request-elements.js";

export { LitElement, html } from "../vendor/browser-runtime.js";
export { widgetController } from "./widget-controller.js";
// The rank a position record carries for a unit dropped at an index in a container.
export { rankAt } from "./projection/model.js";
export async function mountSpecimen(frame, options) {
  const owner = await import("./specimen.js");
  return owner.mountSpecimen(frame, options);
}

export { USER_VIEW_RESTORE_CASES } from "./restore-state.js";
export {
  addressableName,
  addressableSays,
  addressableWord,
} from "./anchor-resolution.js";
// The name Threads, the margin, and reactions give a comment's anchor.
export { anchorLabel } from "./conversation/messages.js";
// The page's `main`, or the body of the message whose markup a node stands in.
export { authoredScope } from "./conversation/messages.js";
export { navigateToDatum } from "./application.js";
export {
  declareCoverRoom,
  landingInsets,
  shownBand,
  shownBox,
  shownParts,
} from "./geometry.js";
// Holding the user's place in a scroller whose contents a widget re-renders.
export { placeKeeper } from "./user-place.js";
export { inUi, uiInside, upFrom } from "./shadow.js";
// Putting the user on an element that may be no tab stop of its own, which is what a
// widget landing them anywhere but a control needs: the lend leaves with the first blur.
export { focusDestination } from "./focus.js";
export { openAsks, watchAsks } from "./application.js";
export { registerVisualParts } from "./visual-parts.js";
export { conversationBox, consumeThreads } from "./application.js";
export { readThreads } from "./conversation/state.js";
export { turns as threadTurns, threadSummary } from "./conversation/model.js";
export { conversationInput } from "./conversation/landing.js";
export { landInConversation, openThread } from "./application.js";
export { wireInput } from "./application.js";
export { DISCLOSE } from "./keyboard/disclosure.js";
export {
  PRESS,
  labelOf,
  submitBindings,
  submitLabel,
  walkRows,
} from "./keyboard/bindings.js";
export {
  commandScope,
  focused,
  keys as commands,
  paintKeys,
  saying,
} from "./keyboard/scopes.js";
export { repaint } from "./repaint.js";
export { beginWalk, listWalkPosition } from "./walk-position.js";
export {
  MARGIN_ENTRY_SCHEMA,
  marginEntry,
  presentMarginEntry,
  registerMarginContribution,
} from "./margin-entries.js";
export {
  inlineMarkdownFragment,
  loadMarkdown,
  markdownReady,
  markdownWords,
  renderInlineMarkdown,
  renderMarkdown,
} from "./markdown.js";
export { isCanonicalMediaUrl, scopedMediaUrl } from "./media.js";
export { pageScroller } from "./scrolling.js";
// The user's place as a landmark, and the history entries a widget adds.
export { capturePlace, restorePlace } from "./reading-place.js";
export { claimTraversals, pushEntry, replaceEntry } from "./history.js";
export { removeRuntimeRootStyle, setRuntimeRootStyle } from "./root-state.js";
export {
  compoundReadingRegionId,
  effectiveScroller,
  preserveReadingRegions,
  readingPosture,
  readingRegion,
  readingRegionFor,
  readingRegions,
  registerReadingRegion,
  scrollerFor,
  shownRegionBounds,
  watchReadingRegionTransitions,
} from "./reading-regions.js";
export { announce, notice } from "./notifications.js";
export { defineRequestElement };
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
export { shallowSigs } from "./application.js";
export { shadowStage } from "./shadow-stage.js";
export { agentName, revisionLabel } from "./context.js";
export { loadDeferred, watchData } from "./data.js";
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
// `afterPresentation` is the package's whole route past presentation: it waits and
// declares the arrival in one call, so a widget cannot defer without the page knowing.
export { PRESENTATION, afterPresentation, quietWord } from "./presentation.js";
export {
  captureTargetReference,
  resolveTargetReference,
  targetCandidates,
} from "./target-references.js";
export { projectData } from "./application.js";
export { retainUserIntent } from "./user-intent.js";
export { tabStore } from "./storage.js";
export {
  highlightBlocks,
  langForPath,
  synNodes,
  syntax,
  tokenLines,
} from "./syntax.js";
export { dataBody, failSoft, once } from "./widget-upgrade.js";
export { watchUpdates } from "./application.js";
export { saidAt, updateSequence, watchHistory } from "./updates.js";
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
