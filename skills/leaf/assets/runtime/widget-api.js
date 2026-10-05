/* The one helper surface behavior modules import. Capabilities come from their
   domain owners; optional hosts load when requested. Owners import one another,
   and leaf.js only boots.

   The runtime tree is not the set of importers. Package widget modules and the render
   gate's probes under `leaf/render-checks/` both reach this file over HTTP from the
   served page, as `/runtime/widget-api.js`, so a search of `runtime/` for a re-export's
   importer comes back empty whether or not the export is reachable. What answers that
   question is the browser gate, which fails to parse every probe module at once. */
export { LitElement, html } from "../vendor/browser-runtime.js";
export { widgetController } from "./widget-controller.js";
// The rank a position record carries for a unit dropped at an index in a container.
export { rankAt } from "./projection/model.js";
export async function mountSample(frame, options) {
  const owner = await import("./sample.js");
  return owner.mountSample(frame, options);
}
export { dressSamples, wear } from "./dress.js";

export { USER_VIEW_RESTORE_CASES } from "./restore-state.js";
export { ADDRESSABLE, addressableLabel, addressableWord } from "./anchor-resolution.js";
// The name Threads, the margin, and reactions give a comment's anchor.
export { anchorLabel } from "./thread/messages.js";
// The page's `main`, or the body of the message whose markup a node stands in.
export { authoredScope } from "./passages.js";
export { navigateToDatum } from "./application.js";
// Experimental: one widget marking part of another (indication.js).
export { indicate } from "./indication.js";
export { landingInsets, shownBand, shownBox, shownParts } from "./geometry.js";
// Holding the user's place in a scroller whose contents a widget re-renders.
export { placeKeeper } from "./user-place.js";
export { inUi, uiInside, upFrom } from "./shadow.js";
// Putting the user on an element that may be no tab stop of its own, which is what a
// widget landing them anywhere but a control needs: the lend leaves when they move off.
// Holding the user's place, caret included, across a move or re-render of the node they
// stand on. TEXT_FIELD is the tag of the box a widget offers for the user to write
// Markdown in; TEXT_BOX matches it and any native textarea.
export { focusDestination, holdFocus } from "./focus.js";
export { TEXT_BOX, TEXT_FIELD } from "./control-selectors.js";
// Making an element's children a list, moving only what is out of place and keeping the
// user standing in a node it moves.
export { setChildren, setRenderedChildren } from "./dom-children.js";
export { openAsks, watchAsks } from "./application.js";
export { answersWithin } from "./asks/answer.js";
export { registerVisualParts } from "./visual-parts.js";
export {
  threadBox,
  consumeThreads,
  consumePageThreads,
  consumeAnnotations,
  mountThreadViews,
  threadActions,
} from "./application.js";
export { readThreads } from "./thread/state.js";
export { watchThreads } from "./thread/watch.js";
export { turns as threadTurns, threadSummary } from "./thread/model.js";
export { threadInput } from "./thread/landing.js";
// Holding a region's rows the log or the clock decides while their growth would be seen
// (assets/AGENTS.md, "Stability").
export { HeldReading } from "./thread/held-news.js";
export { landInThread, openThread } from "./application.js";
export { wireInput } from "./application.js";
export { DISCLOSE } from "./keyboard/disclosure.js";
export { PRESS, labelOf, submitBindings, submitLabel } from "./keyboard/bindings.js";
export {
  commandScope,
  focused,
  keys as commands,
  paintKeys,
  saying,
} from "./keyboard/scopes.js";
export { repaint } from "./repaint.js";
export {
  afterScript,
  cancelRender,
  nextFrame,
  nextRender,
  sizeObserver,
} from "./rendering.js";
export { beginWalk, listWalkPosition, rowWalk } from "./walk-position.js";
export {
  CONTRIBUTION_ENTRY_SCHEMA,
  contributionItemKey,
} from "./contribution-model.js";
export {
  contributionEntry,
  presentContributionEntry,
} from "./contribution-controls.js";
export { registerContribution } from "./contributions.js";
export {
  inlineMarkdownFragment,
  loadMarkdown,
  markdownReady,
  markdownWords,
  renderInlineMarkdown,
  renderMarkdown,
} from "./markdown.js";
export { isCanonicalMediaUrl, scopedMediaUrl } from "./media.js";
// Where two images differ, gathered into regions (image-difference.js).
export {
  compareImages,
  countAreas,
  describeDifference,
  differenceKind,
} from "./image-difference.js";
export { pageScroller } from "./scrolling.js";
export { scrollIntoReadingBand } from "./landing-scroll.js";
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
export { ago, clocked, clockValue, quietSince, shortAgo } from "./presence.js";
export { shallowSigs } from "./application.js";
export { shadowStage } from "./shadow-stage.js";
export { inBaseLayer } from "./stylesheets.js";
export { revisionLabel, annotationMode } from "./context.js";
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
export {
  PAGE_INTERFACE,
  PRESENTATION,
  afterPresentation,
  quietWord,
} from "./presentation.js";
export {
  captureTargetReference,
  resolveTargetReference,
  targetCandidates,
} from "./target-references.js";
export { projectData } from "./application.js";
export { copyCodeBlock } from "./code-copy.js";
export { retainUserIntent } from "./user-intent.js";
export { keepView, openingView, tabStore } from "./storage.js";
export {
  highlightBlocks,
  langForPath,
  synNodes,
  syntax,
  tokenLines,
} from "./syntax.js";
export { bodyText, dataBody, failSoft, once } from "./widget-upgrade.js";
export { watchUpdates } from "./application.js";
export { saidAt, updateSequence, watchHistory } from "./updates.js";
export {
  HIDDEN,
  LAYOUT,
  dragging,
  el,
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
export { atLayoutPrecision, keeps, keepsHidden, keepsText, layoutPx } from "./keeps.js";
