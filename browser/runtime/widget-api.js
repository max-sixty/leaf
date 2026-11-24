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
   widget keeps importing from here.

   Shared web code that reaches none of Leaf's is no part of this surface: it is the
   library's (lib/; browser/AGENTS.md, "The library of shared web code"). */
import "./element-integration.js";
import { deferredArrival } from "./presentation.js";
export * from "./portable-api.js";
export { signal } from "/runtime/framework.js";
export { widgetController } from "./widget-controller.js";
export { quoted } from "./widget-descriptors.js";
// The rank a position record carries for a unit dropped at an index in a container.
export { rankAt } from "./projection/model.js";

// `fragmentTarget(hash)` is the page element a URL fragment names, read as Leaf's own
// arrivals and links read it.
export { fragmentTarget } from "./anchor-resolution.js";
export { addressableLabel, addressableWord } from "./addressable-names.js";
// `authoredTitle()`: the page's own `<title>`, without the count the tab's title
// shows in front of it.
export { authoredTitle } from "./tab-title.js";
// `titledElement(heading)`: the element a heading titles, its hgroup and the section or
// article that opens with it, which a count per heading counts under that heading.
export { titledElement } from "./addressable-names.js";
// What a place on the page previews: its name, first parts, state and conversations.
export { placePreview } from "./place-preview.js";
// The name Threads, the margin, and reactions give a comment's anchor.
export { anchorLabel } from "./thread/messages.js";
// The part of the page a node stands in, by the one rule On Me groups its items by and
// a link's preview names a place by.
export { partOver } from "./thread/placement.js";
// The authored page body, or the body of the message whose markup a node stands in.
export { authoredScope, elementById } from "./passages.js";
export { navigateToDatum } from "./application.js";
// `growthIsSeen(element)`: whether the element changing size now would move what the
// user sees, as scroll anchoring and the chrome leave it; `whenNone` hears when such a
// reading stops holding.
export { growthIsSeen, landingInsets, shownWindow, whenNone } from "./geometry.js";
export { registerRootHeader } from "./root-headers.js";
// What stands at the reading line, and holding a place across one change the
// browser's scroll anchoring can't keep still, such as one hiding what it anchors.
export { holdPlace, readingAt } from "./user-place.js";
// Putting the user on an element, saying what moved them there; holding their place,
// caret included, across a move or re-render of the node they stand on, by key in a
// list; hearing each move of their current location with its cause; running something
// once they move off an element, or once a press lands away from it (`onPressAway`); and
// a group's roving Tab stop. TEXT_FIELD is the tag of the box a widget offers for the
// user to write Markdown in.
export { onCurrentLocation, onPress, onPressAway, rove } from "./focus.js";
export { TEXT_FIELD } from "./control-selectors.js";
export { answeredInWords, readObligations } from "./obligations/model.js";
// The obligations a region of the page holds, by the rule every count and walk of them
// reads, and which regions hold a widget that asks the user something, including one
// whose obligation the inventory hasn't listed yet or lists as withdrawn.
export {
  obligationsByRegion,
  obligationsIn,
  regionsAwaiting,
} from "./obligations/place.js";
export { comparisonChanges } from "./version.js";
export { answerWords } from "./obligations/answer.js";
export { readWork, workAncestor } from "./work.js";
export { obligationActions } from "./application.js";
export { readQueues, queueItemKey } from "./queue-api.js";
export { queueTitle } from "./queue-title.js";
export { queueActions } from "./application.js";
export {
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
export { under } from "./shadow-tree.js";
// `rowArrows(node)` is the `[back, ahead]` arrow pair along a row, in its text direction.
export { PRESS, labelOf, rowArrows } from "./keyboard/bindings.js";
export { commandScope, commandsOn } from "./keyboard/scopes.js";
export { saying } from "./keyboard/control-keys.js";
// The claim of a scope standing over the page: every key but the command reference's.
export { allButCommandReference } from "./keyboard/register.js";
export { rowWalk } from "./walk-position.js";
export { excerptWords } from "./words.js";
export { contributionItemKey } from "./contribution-model.js";
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
export { scopedMediaUrl } from "./media.js";
export { fitsWhole } from "./landing-scroll.js";
// The user's place as a landmark, and the history entries a widget adds.
export { capturePlace, restorePlace } from "./reading-place.js";
export { claimTraversals, pushEntry, replaceEntry } from "./history.js";
export {
  compoundReadingRegionId,
  preserveReadingRegions,
  registerReadingRegion,
  scrollerFor,
  showReadingSubject,
} from "./reading-regions.js";
export { raiseError } from "./errors.js";
export { MAX_EDIT_LENGTH } from "./text-alignment.js";
export { named, phrasing, says } from "./passages.js";
export { ago, agePreview, clockValue } from "./presence.js";
export { boundFile } from "./file-api.js";
export { RequestError } from "./layer-client.js";
export { generate } from "./llm-api.js";
export { connection } from "./http-api.js";
export { clearDraft, loadDraft, saveDraft, sendDraft, watchDraft } from "./drafts.js";
export { declarationFor, layerFact, matchesWhen } from "./registry.js";
export { foldDuration, returnDuration, backgroundFlash, motion } from "./motion.js";
// A package's routes past presentation all declare the arrival, so a widget cannot
// defer without the page knowing: `afterPresentation` waits for presentation and
// `whenNear` for the reader to near a node, then each starts the work;
// `deferredArrival` counts work the widget has already started.
export {
  PAGE_INTERFACE,
  PRESENTATION,
  afterPresentation,
  deferredArrival,
  whenNear,
  whileInterfaceConnected,
} from "./presentation.js";
export { copyControl } from "./copy-control.js";
export { keepView, openingView, viewDocument, viewMembers } from "./storage.js";
export { dressCode } from "./code-dressing.js";
export { readHistory, reportSequence, reportsReady } from "./reports.js";
// The one watcher of the page's readings (module-reading.md, "Page readings").
export {
  dragging,
  el,
  motionPreview,
  reachedForWords,
  worksInside,
} from "./widget-elements.js";

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
  // The page counts the sample's arrival from here; the host counts it once it starts.
  const owner = await deferredArrival(import("./sample.js"));
  return owner.mountSample(frame, options);
}
export { wear } from "./dress.js";
export { landInThread } from "./application.js";
export { threadInput } from "./thread/landing.js";
// What the page calls its agent, as On <agent> names it, for `lf-tally`'s words.
export { agentName } from "./semantic-state.js";
// The page node the user's current location stands for, through a margin entry or a
// thread card, as `lf-deck` asks whether the user is on its open card.
export { placeOf } from "./current-target.js";
