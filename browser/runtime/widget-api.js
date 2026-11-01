/* The one helper surface behavior modules import. Capabilities come from their
   domain owners; optional hosts load when requested. Owners import one another,
   and leaf.js only boots.

   The runtime tree is not the set of importers: package widget modules reach this file
   over HTTP from the served page, as `/runtime/widget-api.js`. What only the render
   gate's probes read belongs in check-api.js instead.

   Every export is supported for independent and bundled packages alike; the
   references/module-*.md files document each one. Kernel widgets import private
   capabilities from their owners rather than lending them through this surface.

   The helpers that load in any document are portable-api.js's, re-exported here whole,
   so a widget that must also run off a Leaf page imports from there and every other
   widget keeps importing from here. */
import "./element-integration.js";
export * from "./portable-api.js";
export { signal } from "/runtime/framework.js";
export { move } from "./dom-move.js";
export { iconElement, iconTemplate } from "./icons.js";
export { widgetController } from "./widget-controller.js";
export { quoted } from "./widget-descriptors.js";
export { holdAuthoredBody } from "./widget-elements.js";
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
// `growthIsSeen(element)`: whether the element changing size now would move what the
// user sees, as scroll anchoring and the chrome leave it.
export { growthIsSeen, landingInsets, shownWindow } from "./geometry.js";
export { registerRootHeader } from "./page-layout.js";
// Holding the user's place in a scroller whose contents a widget re-renders.
export { placeKeeper } from "./user-place.js";
export { under } from "./shadow.js";
// Putting the user on an element, saying what moved them there; holding their place,
// caret included, across a move or re-render of the node they stand on, by key in a
// list; their current location and whether it is in a scope; recording where a layer opened
// from and handing them back as it closes; running something once they move off an
// element, or once a press lands away from it (`onPressAway`); and a group's roving Tab
// stop. TEXT_FIELD is the tag of the box a widget offers for the user to write
// Markdown in; TEXT_BOX matches it and any native textarea.
export {
  closeLayer,
  focusDestination,
  focused,
  handBack,
  holdFocus,
  onCurrentLocation,
  onPress,
  onPressAway,
  openLayer,
  openerOf,
  rove,
  currentLocationIn,
  whenLeft,
} from "./focus.js";
export { TEXT_BOX, TEXT_FIELD } from "./control-selectors.js";
// Making an element's children a list, moving only what is out of place.
export { setChildLists, setChildren, setRenderedChildren } from "./dom-children.js";
export { answeredInWords, readObligations } from "./obligations/model.js";
// The obligations a region of the page holds, by the rule every count and walk of them reads.
export { obligationsIn } from "./obligations/place.js";
export { comparisonChanges } from "./version.js";
export { answerWords } from "./obligations/answer.js";
// A view's reading and writing of another widget's answer (x-shows).
export { shownAnswer } from "./shown-answer.js";
export {
  readWork,
  workRole,
  workElements,
  directWorkElements,
  workAncestor,
} from "./work.js";
export { obligationActions } from "./application.js";
export { readQueues, queueItemKey } from "./queue-api.js";
export { queueTitle } from "./queue-title.js";
export { queueActions } from "./application.js";
export {
  threadBox,
  placePageThreads,
  consumeAnnotations,
  registerThreadPresentation,
  threadActions,
} from "./application.js";
export { readThreads } from "./thread/state.js";
export { turns as threadTurns } from "./thread/model.js";
export { threadSummary } from "./thread/messages.js";
// Holding a region's rows the log or the clock decides while their growth would be seen
// (browser/AGENTS.md, "The page holds still under the user's aim").
export { HeldReading, heldGrowth } from "./thread/held-news.js";
export { wireInput } from "./application.js";
export { DISCLOSE } from "./keyboard/disclosure.js";
export { showNativeLayer, closeNativeLayer } from "./keyboard/layer-stack.js";
export { isNativeLayer } from "./shadow-tree.js";
export { HOLDS_WORD } from "./held-word.js";
// `rowArrows(node)` is the `[back, ahead]` arrow pair along a row, in its text direction.
export { PRESS, cycledRow, labelOf, rowArrows } from "./keyboard/bindings.js";
export { commandScope, commandsOn, saying } from "./keyboard/scopes.js";
// The claim of a scope standing over the page: every key but the command reference's.
export { allButCommandReference } from "./keyboard/register.js";
export { beginWalk, listWalkPosition, rowWalk } from "./walk-position.js";
export { excerptWords } from "./words.js";
export {
  CONTRIBUTION_ENTRY_SCHEMA,
  contributionItemKey,
} from "./contribution-model.js";
export {
  contributionEntry,
  presentContributionEntry,
  presentContributionReceipts,
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
export { atScrollEnd, pageScroller, scrollLimit } from "./scrolling.js";
export { fitsWhole, scrollIntoReadingBand, scrollIntoView } from "./landing-scroll.js";
// The user's place as a landmark, and the history entries a widget adds.
export { capturePlace, restorePlace } from "./reading-place.js";
export { claimTraversals, pushEntry, replaceEntry } from "./history.js";
export {
  compoundReadingRegionId,
  preserveReadingRegions,
  regionScrollBehavior,
  registerReadingRegion,
  scrollerFor,
  showReadingSubject,
  watchReadingRegionTransitions,
} from "./reading-regions.js";
export { notice } from "./notifications.js";
export { raiseError } from "./errors.js";
export { alignText } from "./text-alignment.js";
export { inChrome, says, wrote } from "./passages.js";
export { ago, clockValue, quietSince, shortAgo } from "./presence.js";
export { revisionLabel } from "./context.js";
export { boundFile } from "./file-api.js";
export { RequestError } from "./layer-client.js";
export { generate } from "./llm-api.js";
export { connection } from "./http-api.js";
export { clearDraft, loadDraft, saveDraft, sendDraft, watchDraft } from "./drafts.js";
export {
  declarationFor,
  elementsDeclaring,
  layerFact,
  matchesWhen,
} from "./registry.js";
export {
  flashDuration,
  foldDuration,
  returnDuration,
  foldBlock,
  backgroundFlash,
  motion,
  scrollBehavior,
} from "./motion.js";
// A package's routes past presentation both declare the arrival, so a widget cannot
// defer without the page knowing: `afterPresentation` waits for presentation and then
// starts the work; `deferredArrival` counts work the widget has already started.
export {
  PAGE_INTERFACE,
  PRESENTATION,
  afterPresentation,
  deferredArrival,
  whileInterfaceConnected,
} from "./presentation.js";
export { copyBlock } from "./code-copy.js";
export { copyControl } from "./copy-control.js";
export { retainUserIntent } from "./user-intent.js";
// Whether a press is the plain one a control claims: the primary button, no modifier;
// and whether a click came from the keyboard rather than a pointer.
export { plainPress, pressIsKeyboardActivation } from "./pointer.js";
export { onUserInput } from "./focus.js";
export { keepView, openingView, viewMembers } from "./storage.js";
export { highlightBlocks, langForPath } from "./syntax.js";
export {
  saidAt,
  readHistory,
  reportSequence,
  reportsPresented,
  reportsReady,
} from "./reports.js";
// The one watcher of the page's readings (module-reading.md, "Page readings").
export {
  PRESSABLE,
  dragging,
  el,
  motionPreview,
  nameAction,
  namedAction,
  reachedForWords,
  relabel,
  searchField,
  worksInside,
} from "./widget-elements.js";
export { atLayoutPrecision, keeps, keepsHidden, keepsText, layoutPx } from "./keeps.js";

// The CodeMirror view class Leaf's own editors use, built over the CodeMirror module
// the caller imported, so CodeMirror stays off a page's opening; the runtime loads it once
// the page has presented.
export { leafEditorView } from "./editor-view.js";

// Render a declared template or a generated document as an isolated live Leaf page.
// The returned host owns readiness, Reset and disposal (live-samples.md).
/** @param {Parameters<typeof import("./sample.js").mountSample>[0]} frame
 * @param {Parameters<typeof import("./sample.js").mountSample>[1]} options
 * @returns {Promise<ReturnType<typeof import("./sample.js").mountSample>>} */
export async function mountSample(frame, options) {
  const owner = await import("./sample.js");
  return owner.mountSample(frame, options);
}
export { wear } from "./dress.js";
export { landInThread } from "./application.js";
export { threadInput } from "./thread/landing.js";
// What the page calls its agent, as On <agent> names it, for `lf-tally`'s words.
export { agentName } from "./semantic-state.js";
// A region's open obligations by whose turn each is, in the words `lf-tally` and
// `lf-deck` both show.
export { tally, tallyWords } from "./obligations/tally.js";
// The page node the user's current location stands for, through a margin entry or a
// thread card, as `lf-deck` asks whether the user is on its open card.
export { placeOf } from "./current-target.js";
