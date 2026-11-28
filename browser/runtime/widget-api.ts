/* The functions page scripts and widgets import from Leaf. Capabilities come from their
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
   library's (lib/; browser/AGENTS.md, "The library of shared web code").

   Each export is a name every package author learns, so one joins this file only
   after the questions in packages/AGENTS.md, "A widget's need of Leaf". */
import "./host/element-integration.js";
import { deferredArrival } from "./readings/presentation.js";
import { growthIsSeen } from "./dom/geometry.js";
import { PendingTaskEvent } from "./lib/pending-task.js";
export * from "./portable-api.js";

// `elementById(address, from)`: the element an id, a widget's `id:key` or a fragment
// names, in the message `from` was written in first, then on the page.
export { elementNamed as elementById } from "./readings/anchor-resolution.js";
// `nameOf(thing)`: the name Leaf gives an element, the page, a thread or an On list
// row, in words.
export { nameOf } from "./panel/names.js";
// `titledElement(heading)`: the element a heading titles, its hgroup and the section or
// article that opens with it, which a count per heading counts under that heading.
export { titledElement } from "./readings/addressable-names.js";
// What a place on the page previews: its name, first parts, state and conversations.
export { placePreview } from "./annotations/place-preview.js";
// The name Threads, the margin, and reactions give a comment's anchor.
export { anchorLabel } from "./records/thread/messages.js";
export { navigateToDatum } from "./host/application.js";
// `growthIsSeen(element)`: whether the element changing size now would move what the
// user sees, as scroll anchoring and the chrome leave it.
export { growthIsSeen, landingInsets, shownWindow } from "./dom/geometry.js";
export { alreadyShown } from "./readings/landing-scroll.js";
// Holding what the reader reads across one change the browser's scroll anchoring
// can't keep still, such as one hiding what it anchors.
export { holdPlace } from "./readings/user-place.js";
// Hearing each move of the user's current location with its cause
// (`onCurrentLocation`), following the primary pointer's press (`onPress`), and hearing
// a press that lands away from a surface (`onPressAway`).
export { onCurrentLocation, onPress, onPressAway } from "./dom/focus.js";
// The page's obligations, or those a region of it holds by the rule every count and walk
// of them reads, with whether the region's markup asks the user something.
export { readObligations } from "./records/obligations/place.js";
export { comparisonChanges } from "./features/version.js";
export { answerWords } from "./records/obligations/answer.js";
export { readWork } from "./host/work.js";
export { obligationActions } from "./host/application.js";
export { readQueues } from "./state/queue-api.js";
export {
  placePageThreads,
  registerThreadPresentation,
  threadActions,
} from "./host/application.js";
export { readThreads } from "./records/thread/state.js";
// Holding a region's rows the log or the clock decides while their growth would be seen
// (browser/AGENTS.md, "The page holds still under the user's aim").
export { HeldReading } from "./records/thread/held-news.js";
export { wireInput } from "./host/application.js";
export { rowWalk } from "./records/walk-position.js";
export { presentContributionEntry } from "./features/contribution-controls.js";
export { registerContribution } from "./features/contributions.js";
export { pageLinks } from "./records/page-markdown.js";
export { scopedMediaUrl } from "./records/media.js";
export {
  preserveReadingRegions,
  scrollerFor,
  showReadingSubject,
} from "./readings/reading-regions.js";
export { named, phrasing, says } from "./readings/passages.js";
export { clockValue } from "./state/presence.js";
export { boundFile } from "./host/file-api.js";
export { generate } from "./host/llm-api.js";
export { connection } from "./host/http-api.js";
export { draft } from "./records/drafts.js";
export { backgroundFlash, motion } from "./dom/motion.js";
// A package's routes past presentation all declare the arrival, so a widget cannot
// defer without the page knowing: `afterPresentation` waits for presentation and
// `whenNear` for the reader to near a node, then each runs its callback.
// `afterPresentation`'s callback may return work the widget has already started, which
// it counts from its call.
export {
  afterPresentation,
  whenNear,
  whileInterfaceConnected,
} from "./readings/presentation.js";
export { copyControl } from "./transport/copy-control.js";
// The members a widget shows one at a time: Leaf remembers the one shown, names it in
// the address where the widget's views are the page's, and keeps the user's place in
// each view of the page's flow (records/views.js).
export { keepView, openingView, viewMembers } from "./records/views.js";
export { dressCode } from "./readings/code-dressing.js";
export { readHistory, readReports } from "./host/reports.js";
export { aimedAt } from "./dom/widget-elements.js";

// The CodeMirror view class Leaf's own editors use, built over the CodeMirror module
// the caller imported, so CodeMirror stays off a page's opening; the runtime loads it once
// the page has presented.
export { leafEditorView } from "./annotations/editor-view.js";

// Render a declared template or a generated document as an isolated live Leaf page.
// The returned host owns readiness, the frame's height, Reset and disposal
// (live-samples.md). A block's frame the reader sees as it mounts is drawing under way
// (lib/pending-task.js), read here in the caller's stack: the page's presentation
// waits for it, or the gesture whose rendering showed the frame owns its fit. The host
// says when that drawing is in (host/sample.js, `landed`).
export async function mountSample(
  frame: Parameters<typeof import("./host/sample.js").mountSample>[0],
  options: Parameters<typeof import("./host/sample.js").mountSample>[1],
): Promise<ReturnType<typeof import("./host/sample.js").mountSample>> {
  const landing: PromiseWithResolvers<void> | null =
    !options.window && growthIsSeen(frame) ? Promise.withResolvers() : null;
  if (landing) frame.dispatchEvent(new PendingTaskEvent(landing.promise));
  try {
    // The page counts the sample's arrival from here; the host counts it once it starts.
    const owner = await deferredArrival(import("./host/sample.js"));
    return owner.mountSample(frame, options, landing && landing.resolve);
  } catch (error) {
    landing?.resolve();
    throw error;
  }
}
export { wear } from "./dom/dress.js";
export { landInThread } from "./host/application.js";
export { threadInput } from "./records/thread/landing.js";
// What the page calls its agent, as On <agent> names it, for `lf-tally`'s words.
export { agentName } from "./state/semantic-state.js";
// The page node the user's current location stands for, through a margin entry or a
// thread card, as `lf-deck` asks whether the user is on its open card.
export { placeOf } from "./records/current-target.js";
