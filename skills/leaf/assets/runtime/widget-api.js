/* The one helper surface behavior modules import. Capabilities come from their
   domain owners; optional hosts load when requested. Owners import one another,
   and leaf.js only boots.

   The runtime tree is not the set of importers: package widget modules reach this file
   over HTTP from the served page, as `/runtime/widget-api.js`. What only the render
   gate's probes read belongs in check-api.js instead.

   Every export above the `// Internal:` comment is the authoring API, and
   references/module-authoring.md documents each one; the exports below it serve Leaf's
   bundled packages and kernel widgets alone (tests/runtime/widget-api.test.mjs). */
export {
  html,
  nothing,
  render,
  classMap,
  createRef,
  guard,
  keyed,
  live,
  ref,
  repeat,
  styleMap,
  unsafeHTML,
} from "../vendor/browser-runtime.js";
export { move } from "./dom-move.js";
export { iconElement, iconTemplate } from "./icons.js";
export { widgetController } from "./widget-controller.js";
export { quoted } from "./widget-descriptors.js";
export { initialRender } from "./initial-render.js";
export { whileConnected, frameFor } from "./arrivals.js";
export { aborted } from "./abort.js";
// The rank a position record carries for a unit dropped at an index in a container.
export { rankAt } from "./projection/model.js";

// `fragmentTarget(hash)` is the page element a URL fragment names, read as Leaf's own
// arrivals and links read it.
export { fragmentTarget, projectedDatum } from "./anchor-resolution.js";
export { addressableLabel, addressableWord } from "./addressable-names.js";
// The name Threads, the margin, and reactions give a comment's anchor.
export { anchorLabel } from "./thread/messages.js";
// The page's `main`, or the body of the message whose markup a node stands in.
export { authoredScope, elementById } from "./passages.js";
export { navigateToDatum } from "./application.js";
// Experimental: one widget marking part of another (indication.js).
export { indicate } from "./indication.js";
export { landingInsets, shownWindow } from "./geometry.js";
// Holding the user's place in a scroller whose contents a widget re-renders.
export { placeKeeper } from "./user-place.js";
export { under } from "./shadow.js";
// Putting the user on an element, saying what moved them there; holding their place,
// caret included, across a move or re-render of the node they stand on, by key in a
// list; where they stand and whether it is in a scope; recording where a layer opened
// from and handing them back as it closes; running something once they move off an
// element; and a group's roving Tab stop. TEXT_FIELD is the tag of the box a widget offers for the user to write
// Markdown in; TEXT_BOX matches it and any native textarea.
export {
  closeLayer,
  focusDestination,
  focused,
  handBack,
  holdFocus,
  openLayer,
  openerOf,
  rove,
  standingIn,
  whenLeft,
} from "./focus.js";
export { TEXT_BOX, TEXT_FIELD } from "./control-selectors.js";
// Making an element's children a list, moving only what is out of place.
export { setChildren, setRenderedChildren } from "./dom-children.js";
export { readQuestions, watchQuestions } from "./questions/model.js";
export { comparisonChanges, watchComparison } from "./version.js";
export { questionWords } from "./questions/answer.js";
export {
  readWork,
  workRole,
  workElements,
  directWorkElements,
  workAncestor,
} from "./work.js";
export { questionActions } from "./application.js";
export { readQueues, watchQueues, queueItemKey } from "./queue-api.js";
export { queueTitle } from "./queue-title.js";
export { queueActions } from "./application.js";
export { registerVisualParts } from "./visual-parts.js";
export {
  threadBox,
  placeThreads,
  placePageThreads,
  consumeAnnotations,
  mountThreadViews,
  registerThreadPresentation,
  threadActions,
} from "./application.js";
export { readThreads } from "./thread/state.js";
export { watchThreads } from "./thread/watch.js";
export { turns as threadTurns, threadSummary } from "./thread/model.js";
// Holding a region's rows the log or the clock decides while their growth would be seen
// (assets/AGENTS.md, "Stability").
export { HeldReading } from "./thread/held-news.js";
export { wireInput } from "./application.js";
export { DISCLOSE } from "./keyboard/disclosure.js";
export { showNativeLayer, closeNativeLayer } from "./keyboard/layer-stack.js";
export { HOLDS_WORD } from "./held-word.js";
// `rowArrows(node)` is the `[back, ahead]` arrow pair along a row, in its text direction.
export { PRESS, labelOf, rowArrows } from "./keyboard/bindings.js";
export {
  commandScope,
  commandsOn,
  keys as commands,
  paintKeys,
  saying,
} from "./keyboard/scopes.js";
export {
  afterScript,
  cancelRender,
  cancelAnimation,
  nextAnimation,
  nextFrame,
  nextRender,
  sizeObserver,
} from "./rendering.js";
export { beginWalk, listWalkPosition, rowWalk } from "./walk-position.js";
export { excerptWords } from "./words.js";
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
  markdownSourceOffset,
  paintMarkdown,
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
export { atScrollEnd, pageScroller, scrollLimit } from "./scrolling.js";
export { scrollIntoReadingBand, scrollIntoView } from "./landing-scroll.js";
// The user's place as a landmark, and the history entries a widget adds.
export { capturePlace, restorePlace } from "./reading-place.js";
export { claimTraversals, pushEntry, replaceEntry } from "./history.js";
export {
  compoundReadingRegionId,
  preserveReadingRegions,
  readingPosture,
  readingRegion,
  registerReadingRegion,
  scrollerFor,
  watchReadingRegionTransitions,
} from "./reading-regions.js";
export { announce, notice } from "./notifications.js";
export { alignText, alignedNodes } from "./text-alignment.js";
export { inChrome, says, wrote } from "./passages.js";
export { ago, clocked, clockValue, quietSince, shortAgo } from "./presence.js";
export { shadowStage } from "./shadow-stage.js";
export { inBaseLayer } from "./stylesheets.js";
export { revisionLabel } from "./context.js";
export { loadDeferred, watchData } from "./data.js";
export { boundFile } from "./file-api.js";
export { clearDraft, loadDraft, saveDraft, sendDraft, watchDraft } from "./drafts.js";
export {
  declarationFor,
  elementsDeclaring,
  layerFact,
  matchesWhen,
} from "./registry.js";
export {
  foldDuration,
  backgroundFlash,
  motion,
  onMotionPreferenceChange,
  reducedMotion,
  scrollBehavior,
} from "./motion.js";
// `afterPresentation` is the package's whole route past presentation: it waits and
// declares the arrival in one call, so a widget cannot defer without the page knowing.
export { PAGE_INTERFACE, PRESENTATION, afterPresentation } from "./presentation.js";
export { quietWord } from "./declared-words.js";
export { projectData } from "./application.js";
export { copyCodeBlock } from "./code-copy.js";
export { retainUserIntent } from "./user-intent.js";
// Whether a press is the plain one a control claims: the primary button, no modifier.
export { plainPress } from "./pointer.js";
export { onUserInput } from "./focus.js";
export { keepView, openingView, tabStore } from "./storage.js";
export {
  ensureSyntaxLanguage,
  highlightBlocks,
  langForPath,
  synNodes,
  syntax,
  tokenLines,
} from "./syntax.js";
export { bodyText, dataBody, failSoft, once } from "./widget-upgrade.js";
export { saidAt, reportSequence, watchHistory, watchReports } from "./reports.js";
export {
  HIDDEN,
  LAYOUT,
  dragging,
  el,
  layoutChanged,
  measure,
  motionPreview,
  offer,
  offered,
  reachedForWords,
  relabel,
  reserve,
  searchField,
  selectableOffer,
  worksInside,
} from "./widget-elements.js";
export { atLayoutPrecision, keeps, keepsHidden, keepsText, layoutPx } from "./keeps.js";

export { LeafEditorView } from "./editor-view.js";

// Internal: what Leaf's own bundled packages and kernel widgets import beyond the
// authoring API module-authoring.md documents. Package authors do not use these.
export async function mountSample(frame, options) {
  const owner = await import("./sample.js");
  return owner.mountSample(frame, options);
}
export { dressSamples, wear } from "./dress.js";
export { landInThread } from "./application.js";
export { threadInput } from "./thread/landing.js";
export { removeRuntimeRootStyle, setRuntimeRootStyle } from "./root-state.js";
export { shownParts } from "./geometry.js";
export { renderRetired, textNodesUnder } from "./passages.js";
export { isPagePaint } from "./declared-words.js";
