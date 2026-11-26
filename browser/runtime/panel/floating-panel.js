/* The floating panel: Leaf's chrome, as one box hovering over the foot of the page. It
 * presents what other owners hold, so it reads their readings and calls their commands:
 * the status (page-status.js), the page's controls (`pageControls`,
 * base/page-controls.js), the threads (`readThreads`), the queues (`readQueues`), the
 * versions (`versionPicker`), the drafts (records/drafts.js), the passing notices
 * (transport/notifications.js) and the errors (transport/errors.js). It decides only how they are shown.
 *
 * The box has three sizes, and which it stands at follows what the user does, so no
 * setting chooses it:
 * - **Folded**, the leaf alone in the window's corner, coloured by the agent's state,
 *   with its count of what waits on the user as a badge over its corner and a dot for
 *   threads with news, the row gathered into it where it stands at the row's end. The
 *   user folds it from the leaf's menu or with `.`, or by a pointer with the small round
 *   button that rides the box's top-left corner while the pointer is near it and no
 *   view's head line holds that corner. It folds itself where focus lands on a place
 *   the row alone would hide (`giveWay`). A
 *   press on the leaf unfolds it, and it stays as it was left across pages (`rest`).
 *   Once the page presents, its status tooltip keeps the explanation it opened for
 *   one pointer or focus exposure, so news and aging words cannot move text being
 *   read. The next exposure, including a return from a hidden tab, reads the current
 *   status. The leaf's tone, counts and accessible name stay live, and notices
 *   answering a gesture show immediately.
 * - **The row**: the comment field, and at its end the leaf, coloured by the agent's
 *   state, counting what waits on the user on a badge over its corner, with a dot
 *   while a thread holds a reply they have not read, as it does folded. A press on it
 *   opens the On view on the tab those marks point at (`leafOpens`), so the leaf is
 *   both the way to the menu and to what waits on the user. The user chose this over
 *   the leaf at the row's start and an On Me mark at its end, two marks opening one
 *   view's tabs, and over a leaf that always opens the menu, which put On Me two
 *   presses away; the leaf at the end stands on the side it folds to. While a search or a stance stands, the ✕ that ends it stands
 *   between the field and the leaf, so the stance always has a way out on screen, and
 *   the leaf keeps its place, since it says the agent's state and leads to the rest. A
 *   stance owns the
 *   row while it stands, on the page and in a thread alike: the field's mode chip names it
 *   beside its ✕ in a word ("Draw", "Go to"; its scope's `says`), as a search's chip
 *   names its scope beside its own ✕ (`stanceName`), and the field takes no words
 *   (field-readings.js, `still`), offering neither Reply nor the microphone, so the row
 *   reads whose turn it is or the status, Close and esc at the field's end while Escape
 *   would end the stance (`stanceClose`), the name and the ✕. The user chose this: the
 *   name beside its way out over the name first, at the row's far end from the ✕ it
 *   names; one word over "In Draw mode"; and a mode that
 *   stops the field's writing over a reply, its Send and the microphone standing
 *   beside the mode's ✕. On the page too the ✕ is the stance's way out for a pointer.
 *   A draft the field holds
 *   stays, unwritable, through the stance. The ✕ takes a symbol's width, the folded
 *   leaf's, beside the field; more room would stand it apart from the field, which the
 *   user questioned. An open view has its ✕ on a line of its own, its
 *   head line or its tabs (**Opened**), but for a stance's ✕, which keeps its place in
 *   the row there too. Rejected: the ✕
 *   waiting for the view to close, which left a stance entered from a thread, such as
 *   Go-to or Draw mode, unnamed and with no way out on screen.
 *   Threads is the On view's tab rather than a mark of its own, since On Me already
 *   lists a thread message that waits on the user, which the user chose over a Threads
 *   mark in the row. Rejected, by the user: a press on the row's end pressing Next On Me
 *   with `m` beside its count: a second place for a press and its key, where the
 *   field's end already offers the moment's. Nothing else stands in the row, so the
 *   field's width follows only the user's own moves, and what its end says never
 *   slides. The empty field says one thing at a time, the agent's status at rest, and
 *   its end the one press that matters most then (field-readings.js says which, for
 *   how long, and why). Before the panel stands, the row the document served from its
 *   first paint says the keys pressed while the page loads (`heldWords`;
 *   bootstrap.js). No transient message adds a row. A pointer resting on the field, or
 *   a finger holding it, reads its words whole where the field cuts them short, as it
 *   cuts a long status, which the user asked for (`pageEditor`). Words the field shows
 *   whole preview nothing, since the user rejected a tooltip repeating them over the
 *   page. The leaf's menu holds the full status, and the Errors list, where an error
 *   the field has passed or no box stands for waits, with a dot on the leaf and on Errors until the user opens the list
 *   (`errorsList`), each copying with its context. The user asked for Errors to show
 *   in red that it is what the leaf's dot marks, which a count in the accent's ink
 *   leaves unclear.
 *   The keys that send are Send's hover name, where Return sends with
 *   Shift+Return's new line beside it (annotations/composing/input.js).
 * - **Opened**: a view above the same row (On, whose tabs are the menu, On Me,
 *   On <agent>, Threads and the plan; a thread; or All pages), what the user reads or
 *   chooses there, under its head
 *   line: the way back to the list the view opened over, a ‹ alone before the name,
 *   which names that list as its tooltip; the view's name; a thread's own presses, its
 *   held news, Next unread, Show on page and Resolve; and last its Close, in the
 *   top-right corner. A list's name is the tab its foot shows, so its head line stands
 *   only for what Threads holds while it is read (`threadsListing`), and its Close ends
 *   its tabs, on the row, which its growing view never moves, so a
 *   tab, filter, search or Close the user presses stays under the pointer as the list
 *   fits what it shows; a line for ✕ alone read as a missing name (browser/AGENTS.md,
 *   "A control takes only its own room"). A thread has no foot, so its reply stands
 *   right under its messages. Where a view's presses don't fit beside its ‹, as on a
 *   phone beside Next unread and Show on page, they take a line of their own under its
 *   name, Close still last; a thread's news stands with its name, so its arrival never
 *   moves them. The user chose
 *   this over a row of controls between a thread and its reply, where Resolve and
 *   Close stand with the way back as ‹ Threads
 *   among them. Rejected: Threads › before the name, which takes room from the name; a
 *   ‹ hanging off the box beside the leaf, far from the name it leads away from; and no
 *   way back, which leaves a pointer two presses from Threads. The field below keeps
 *   its width while a view stands, at rest and widened alike, which the user chose over
 *   Close in the row, which takes room from the field at rest; only a search's or a
 *   stance's ✕ stands there then (**The row**). The
 *   panel stands on the window's foot, so a view grows and shrinks from its top edge,
 *   and its head line moves with it: news, such as an answer growing a thread, carries
 *   the thread's presses up with its name. A press on the head line holds the view's
 *   height as it acts, so the presses there stay under the pointer for the next press,
 *   as a press in the view holds it (`judgePress`); Resolve, which takes the thread
 *   away, opens the next one at its own height (`resolveLanding`). It lasts while it
 *   is used: Escape or a press on the page puts it
 *   away, Escape once the caret has
 *   left the field, since the caret is the innermost thing open, and travel to a
 *   place on the page it would stand over once landed puts it away, so an `m` walk
 *   from a thread's view shows the next stop (`clearFor`). One Escape puts away a
 *   thread opened over a list, such as Threads or On Me, as it does any other view;
 *   Back returns to that list, as the ‹ does. The user chose this over Escape stepping
 *   back to Threads at the thread's row, with a second Escape putting the list away. A
 *   thread's view
 *   also goes when a route, such as the `t` walk, opens a thread's card on the page,
 *   so one thread stands open (`reveal`; the user chose this, so a walk doesn't
 *   leave the panel's thread under the card it opens). A card's Open in panel
 *   moves the other way, closing the card for this view (`openThread`), which the
 *   user chose for a long thread read in a card's narrow room beside
 *   the column; rejected was opening it wider than other views. It also chooses this
 *   panel for the threads after it, until the view's Show on page chooses cards again
 *   (records/thread/threads-in-panel.js). The view stands right
 *   on the row, with no room between them that typing would show or hide.
 *   The user chose that over a blank line's room kept under every
 *   open view, which reads in Threads as a missing row. Rejected there: the line pushing
 *   the view up as it comes. The view's last words scroll clear of New reply
 *   (records/thread/thread-card.js), the one thing that stands over the row. It is as tall as
 *   what it holds, so a one-message thread opens one message tall, up to most of the
 *   window's height, the larger size a long thread or a long Threads list is read at;
 *   past that it scrolls. The user chose views that fit their content with a larger size for long
 *   reading; content alone reaches that size. Rejected: an Expand
 *   control at the view's head, which the growth it asks for would carry up from under
 *   the pointer, and a compact cap with the larger size behind a gesture, which leaves
 *   every long thread scrolling in a small box until the user finds that gesture.
 *   While it stands it covers the page under it, which reads as unseen (dom/geometry.js,
 *   `declareCover`).
 *
 * The leaf's menu is the On view's first tab, beside On Me, On <agent> and Threads,
 * and the leaf opens the view on it where its marks point at no list (`leafOpens`): the
 * full status over the rest of the page's
 * controls, each one line, with its key where it has one, and a chevron on a row that
 * opens a list of its own (Versions, and the groups Navigate and Annotations). Such a
 * list opens over the menu, its way back returning there. While the menu stands, the
 * field is its search (`menuFound`), narrowing the rows to the words typed, with the
 * threads and versions they name and a press that hands the words to the command
 * reference. The user chose this over the menu as a small list of its
 * own over the leaf, which reaches neither On Me nor Threads and, with
 * its lists, keeps a second surface with its own opening, holding and fade beside the
 * views. Rejected with it: the On view's tabs at that menu's foot, a menu of rows for
 * On Me and Threads, and a leaf that folds the panel or opens On <agent>. A row that
 * copies a text is one press in the menu wherever the page can copy (`canCopy`), and
 * says which session or Leaf the page runs only in About this page (base/page-controls.js,
 * the `about` group). A
 * keyboard's convenience for where the reader stands, such as Resume writing, stands
 * under Navigate only where no keyboard is there to reach it (base/page-controls.js, the
 * `keys` group). The row's end shows the keys of the presses standing there, each
 * only while it would make its press now: `c` at the field's end while it enters the
 * field, which says where `c` goes, beside Reply in an open thread, which the user
 * asked for as a margin card's reply box shows it, and beside Comment at rest, which
 * they chose to match the box that rests beside a target (annotations/composing/surface.js,
 * `restFab`); and a passing press's key, such as Next thread's `t` or Next On Me's `m`
 * (`pressReading`). The menu's rows carry every other key and `?` opens the full
 * reference, which the user chose over a hint or two in the line over the field, to
 * keep the panel quietest. The field the
 * user clicks in is the field they write in: a page
 * comment where no thread is open, a reply where one is: the reply box every view of a
 * thread draws (records/thread/replies.js), with its ↑ to the user's last message, which Leaf's
 * reader draws in the field's place. Each destination keeps its own native editor (its
 * draft, caret and send), and the panel stands the current one in the field's place, so
 * words never move between editors. Page and Threads search take this same field
 * with their own native inputs: a right-hand scope chip and a faint tint name the
 * mode after its placeholder is gone. Search never borrows an editor or its send,
 * attachments or dictation. Every mode keeps its field on the bottom row, with
 * mode-specific controls beside it. Content opens in a view; response choices
 * use a picker. Features contribute to those surfaces rather than adding strips.
 *
 * A list's tabs stand at its foot, the presses on a thread's head line hold its view's
 * height as they act, the leaf's menu holds what it showed while it stands, and a
 * control the user pressed in a thread stays where it was (browser/AGENTS.md, "The
 * page holds still under the user's aim"). Resolving a thread opened from Threads moves the user on to the next
 * one (`resolveLanding`), a view of its own as tall as what it holds, so its head line
 * stands where that height puts it: the press took the pressed Resolve away, and the
 * next thread is its result, which the user said is fine. A control
 * that arrives under the pointer takes the next press at once, as the user chose.
 * Rejected: holding such a control inert until the pointer moves; and opening the next
 * thread at the height the resolved one stood at, so Resolve stays under the pointer,
 * which the user rejected: a run of Resolves shows every
 * thread at the first one's height, cut off or with room under it, until their next
 * turn, and a key's Resolve, which aims at nothing, holds it too.
 *
 * Every change of the box's layout takes effect in one step, and what the user sees
 * then travels from where it was drawn to where it stands, by one model
 * (dom/box-motion.js): the surface behind the box, a separate layer, follows by a clip, the
 * way the Codex app's floating panel moves, and so does the field's ring; a part that
 * kept its size is carried by a transform; one that changed size grows from where it
 * stood, carrying its words by their start corner; one that is new is revealed by the
 * edges of what holds it. News is carried as the user's own change is, so an answer
 * growing a thread's view slides the turns above it up rather than jumping them, as the
 * user chose (dom/box-motion.js). Nothing's layout tweens, so the box's room on the page is
 * its new room at once. The user asked for this, so a line the field gains doesn't
 * leave its attachment vanishing and its ring outrunning the box, nor does more room
 * leave the field behind the box widening around it. Rejected: revealing everything a
 * change moves by the surface's clip, which hides each part that moved until the clip
 * reaches it. */
import {
  guard,
  html,
  noChange,
  keyed as keyedBy,
  live,
  nothing,
  ref,
  render,
  repeat,
} from "/vendor/lit.js";
import { signal } from "/vendor/signals-core.js";
import { reveal } from "../dom/widget-elements.js";
import { el } from "../lib/elements.js";
import { offeredAction } from "../lib/controls.js";
import { actionTemplate, iconTemplate } from "../lib/icons.js";
import { actionName } from "../lib/icon-paths.js";
import { canCopy, copyControl } from "../transport/copy-control.js";
import { atLayoutPrecision, keeps, keepsHidden } from "../lib/keeps.js";
import { keepFieldKeys } from "../base/field-keys.js";
import { statusReading } from "./page-status.js";
import { leavesRows } from "../host/live-leaves.js";
import { keys } from "../dom/keyboard/scopes.js";
import { pageCommand, pageDoor, pageRung } from "../dom/keyboard/register.js";
import {
  advertisesKeys,
  cycledRow,
  parsed,
  spell,
  titleOf as rowTitle,
} from "../dom/keyboard/bindings.js";
import {
  keySequenceModel,
  keySequenceTemplate,
  neutralSteps,
} from "../dom/keyboard/key-sequence.js";
import { pageControls } from "../base/page-controls.js";
import { findCommands } from "./page-keys/command-reference.js";
import { readPlace } from "../records/history.js";
import {
  NO_OPEN_THREADS,
  THREADS_OFFLINE,
  readThreads,
  threadNamed,
} from "../records/thread/state.js";
import {
  discussed,
  isNews,
  lastChange,
  newestFirst,
  threadCounts,
} from "../state/thread/model.js";
import { LeafElement } from "../lib/leaf-element.js";
import {
  RESOLVED,
  threadAttention,
  inHand,
  todoWord,
  workflowStep,
  workflowWord,
} from "../records/thread/workflow.js";
import {
  agentSays,
  leafSays,
  saidBy,
  voiceOf,
  voiced,
  wordsText,
  COMMENT_HINT,
  REOPEN_HINT,
  REPLY_HINT,
} from "../base/voice.js";
import {
  anchorLabel,
  draftPreview,
  draftWords,
  messageReading,
  messageText,
  PREVIEWED_LINE,
  threadHeading,
  threadName,
  threadPassage,
  threadPreview,
  titlePending,
} from "../records/thread/messages.js";
import { drawnThreadId, THREAD } from "../records/thread/selectors.js";
import { declareThreadParts } from "../records/thread/selectors.js";
import { openingPart } from "../records/thread/focus.js";
import { threadPlace } from "../records/thread/placement.js";
import { dismissReply, releaseReplies } from "../records/thread/replies.js";
import {
  BESIDE_PASSAGES,
  chooseThreadsInPanel,
  threadsInPanel,
  wouldChoose,
} from "../records/thread/threads-in-panel.js";
import { landSent } from "../records/thread/landing.js";
import {
  PAGE_DRAFT,
  draftAnchor,
  draftSends,
  draftsReading,
  isComposerDraft,
  loadDraft,
  mirrorDraft,
  saveDraft,
  sendMessage,
  tellDraft,
} from "../records/drafts.js";
import { textField } from "../annotations/composing/text-field.js";
import {
  draftOf,
  standsAtItsBox,
  syncInput,
  writesIn,
} from "../annotations/composing/input.js";
import { TEXT_FIELD } from "../dom/control-selectors.js";
import { retainUserIntent } from "../dom/user-intent.js";
import { focusByKey, focusKey } from "../records/carry.js";
import { focusPlace, holdPlaceOf, standsAt } from "../readings/user-place.js";
import { onUserCount, readPlan, readQueues } from "../state/queue-api.js";
import { queueTitle } from "./queue-title.js";
import { groupingLabel, namedIn, ON_ME_GROUPINGS, queueStop } from "./queue-walk.js";
import {
  carriesObligation,
  emptyOnList,
  itemEnding,
  itemNoun,
  itemOutcome,
  onList,
} from "../state/queues.js";
import { agePreview, ago, clockTime, shortAgo, timeOfDay } from "../state/presence.js";
import { userChoice } from "../state/storage.js";
import { obligationEnding } from "../records/obligations/answer.js";
import { answeredInWords } from "../records/obligations/model.js";
import { obligationPlace, readObligations } from "../records/obligations/place.js";
import { ON_CARD } from "../records/obligations/view-elements.js";
import { declareSide, holdPagePlace } from "../records/current-target.js";
import { versionPicker } from "../features/version-picker.js";
import {
  changesCounted,
  comparable,
  comparisonBase,
  comparisonChanges,
  countWhenShown,
  offeredVersion,
  versionsReading,
} from "../features/version.js";
import { UPGRADE } from "../readings/presentation.js";
import {
  announce,
  answeringStep,
  gestureReading,
  noticeReading,
  noticeWords,
} from "../transport/notifications.js";
import {
  dismissError,
  dismissErrors,
  errorsReading,
  passErrors,
  seeErrors,
} from "../transport/errors.js";
import { stanceWords, statusContextReading } from "./page-keys/status-context.js";
import { passingWords, readField } from "./field-readings.js";
import { motionPlays, playMotion } from "../dom/motion.js";
import { motionEasing, motionTime } from "../lib/motion-timing.js";
import { pagePresented } from "../base/page-paint.js";
import {
  claimReleaseClick,
  focusDestination,
  focusElement,
  focused,
  holdFocus,
  inputCount,
  letGo,
  onCurrentLocation,
  onPressAway,
  openLayer,
  pressHolds,
  pressLed,
  pressRecords,
  currentLocationIn,
} from "../dom/focus.js";
import { rove } from "../lib/roving.js";
import { rowWalk, walkWords } from "../records/walk-position.js";
import { capitalized, counted, excerptWords } from "../lib/words.js";
import { coarsePointer } from "../base/pointer.js";
import { afterScript, afterSettling, holdRendering } from "../base/rendering.js";
import { nextRender, sizeObserver } from "../lib/frame-pass.js";
import { boxMotion } from "../dom/box-motion.js";
import { landedBox, scrollIntoView } from "../readings/landing-scroll.js";
import { gesturedOn, newsCount, newsNotice } from "../records/thread/held-news.js";
import { keepFoot, moveScrollerBy, scrollToEnd } from "../dom/scrolling.js";
import {
  readingIn,
  showReading,
  showReturnTurn,
} from "../records/thread/reply-landing.js";
import {
  announceRoom,
  covered,
  declareCover,
  hiddenByCovers,
  placeBox,
  placeHolder,
  seenRect,
  stateFootBand,
} from "../dom/geometry.js";
import { overlaps } from "../dom/rect.js";
import { registerReadingRegion } from "../readings/reading-regions.js";
import { sectionsInView } from "../readings/reading-place.js";
import { agentName, documentChanged } from "../state/semantic-state.js";
import { runtime } from "../state/context.js";
import {
  byRenderedOrder,
  renderedUnder,
  under,
  closestAcross,
} from "../lib/shadow-tree.js";
import { nativeModalAdmits } from "../dom/keyboard/layer-stack.js";
import {
  commandBindingsNow,
  commandKeysNow,
  commandSteps,
} from "../dom/keyboard/control-keys.js";
import {
  escapeInvocation,
  innermostStance,
  pressCommand,
  standingStances,
} from "../dom/keyboard/dispatch.js";
import { rowArrows } from "../lib/keys.js";

const prefs = () => window.lfChrome;
// What the status says before the page has one (page-status.js, `statusReading`).
const CONNECTING = {
  tone: "",
  summary: "Connecting…",
  summaryParts: [leafSays("Connecting…")],
  explanation: "Connecting…",
  explanationParts: [leafSays("Connecting…")],
  adds: "",
  addsParts: [],
  asks: false,
  publication: null,
};
// What a press on the leaf opens (`leafOpens`), by the name its label and preview give it.
const LEAF_PRESSES = Object.freeze({
  menu: "Page menu",
  you: "On Me",
  threads: "Threads",
});
// The On view's tabs, each a view of its own, which the leaf opens and puts away.
const ON_VIEW = new Set(["menu", "queue", "threads"]);
// What the leaf's marks count, as its label and preview say them: what waits on the user,
// and the threads with news or, where none has news, the drafts put away.
/** @param {number} onUser @param {number} news @param {number} kept */
const leafMarks = (onUser, news, kept) =>
  [
    onUser ? `${onUser} waiting on me` : "",
    news
      ? `${counted(news, "thread")} with news`
      : kept
        ? `${counted(kept, "draft")} unsent`
        : "",
  ]
    .filter(Boolean)
    .join(", ");
// The page's field's name where no selection is offered, which the field the document
// serves wears too (`panelTemplate`, `initial`).
const PAGE_FIELD_NAME = "Comment on the page";
// The field's end at rest while On Me lists anything (`pageOffer`): the walk's route `m`
// takes (queue-walk.js). No notice carries it, so it has no `stands`; `pageOffer`
// decides when it stands.
/** @typedef {Omit<import("../transport/notifications.js").NoticePress, "stands">} FieldPress */
/** @type {FieldPress} */
const NEXT_ON_ME = { action: "next-on-me", command: "queue.next" };
// The keys that would make the press's command (control-keys.js, `commandKeysNow`).
// The field's end shows the press with them, and shows no press without them, as on
// a touchscreen or with the caret in a box.
/** @param {FieldPress} press */
const pressKeys = (press) =>
  press.command === null ? [] : commandKeysNow(press.command);
// A notice's press, or a page's own (`pagePress`), as the field's end offers it
// (annotations/composing/input.js, `BoxPress`): its action's word, its keys (`pressKeys`), read at
// each ask, so a box standing it rechecks its keys without reading the field's words
// again (annotations/composing/input.js, `pressing`), and what it does: its own `run`, else the
// command it names.
/** @param {FieldPress} press @returns {import("../records/composition-input.js").BoxPress} */
const pressReading = (press) => ({
  word: actionName(press.action),
  get keys() {
    return pressKeys(press);
  },
  run: press.run ?? (() => press.command !== null && pressCommand(press.command)),
});

// What the field's own search box asks for, in each list it searches, in Leaf's words
// as every search's prompt is (dom/control-labels.js, `searchField`).
const SEARCH_PROMPTS = Object.freeze({
  menu: "Find a row, thread or version…",
  threads: "Find a thread or message…",
});
// The menu's groups, each a list of the page's controls declaring it, in the menu's place.
const GROUPS = Object.freeze([
  { name: "navigate", label: "Navigate" },
  { name: "annotate", label: "Annotations" },
]);
// The On view's tabs, in their strip's order (`onTabs`), which ← and → turn (`turnTab`),
// and the Go-to door to each list (page-keys/go-to-sequence.js), which its tab names.
/** @type {readonly ("menu" | "you" | "agent" | "threads")[]} */
const ON_TABS = Object.freeze(["menu", "you", "agent", "threads"]);
const ON_DOORS = Object.freeze({
  you: "navigation.panel.queue",
  agent: "navigation.panel.agent",
  threads: "navigation.panel.threads",
});
// Rows held elsewhere, so the menu and its groups leave them out: by the menu's foot.
const FOLD = "panel.floating.fold";
// The leaf's press by key (`pressLeaf`), which the leaf itself is the finger's route to.
const LEAF = "panel.floating.leaf";
// A thread's row in Threads, which names the thread by its key.
const THREAD_ROW = ".lf-fp-thread[data-lf-key]";
const HELD_ELSEWHERE = Object.freeze(["keyboard", `command:${FOLD}`]);
// A row the menu or a group lists: neither held elsewhere nor a stance's way out, at the
// row's end.
/** @param {ReturnType<typeof pageControls>[number]} entry */
const listed = (entry) =>
  !entry.exit &&
  !HELD_ELSEWHERE.includes(entry.key) &&
  (!entry.copies || (!copyRefused && canCopy()));
// The menu offers a copy shortcut only where a copy can work (transport/copy-control.js,
// `canCopy`). A clipboard may still refuse a write, after which the menu drops its copy
// shortcuts (`copyItem`).
let copyRefused = false;
// Keyboard conveniences also stand under Navigate where a finger needs them.
/** @param {ReturnType<typeof pageControls>[number]} entry */
const groupOf = (entry) =>
  entry.group === "keys" && !advertisesKeys() ? "navigate" : entry.group;
// What passes in the panel's one seat for words that pass, as a surface of the panel
// hears it (`passingFacts`), on the page, as field-readings.js orders it
// (`passingWords`), or null. The user asked that whatever is not anchored to the page
// stand at the panel rather than against the window.
function passing() {
  return passingWords({ thread: false, ...passingFacts(NO_STANDING) });
}
/** @type {ReadonlySet<string>} */
const NO_STANDING = new Set();
// What may pass in the panel's one seat, as a surface hears it: a notice while one
// shows, the Go-to filter's word while its sequence waits for a key, and a walk's
// position for a notice's moment after each step (transport/notifications.js, `answerStep`), in
// the words the screen lacks (records/walk-position.js, `walkWords`). `says` is what the
// surface's own words say of where the user stands: the page field's say each fact
// `standing` does (`STANDING`), so a notice about one of them is left to those words,
// unless the field's end shows its press, which those words don't say. The end shows it
// only with a key that would make it now (control-keys.js, `commandKeysNow`), so never on
// a touchscreen. A walk over its list says its
// place alone; the folded leaf's peek and a thread's field say none.
/** @param {ReadonlySet<string>} says */
function passingFacts(says) {
  const notice = noticeReading();
  const { goTo, walk } = statusContextReading();
  const offers = notice.press !== null && pressKeys(notice.press).length > 0;
  const said = notice.about !== null && !offers && says.has(notice.about);
  return {
    notice: notice.visible && !said ? notice : null,
    goTo,
    step: walk && answeringStep() ? walkWords(walk, says) : null,
  };
}
// An age the panel shows, which previews the clock time behind it as every age does
// (state/presence.js, `agePreview`): short, in a room of its own (`.lf-fp-age`) at a line's
// end, or in Leaf's voice inside a sentence Leaf says (`spoken`), as a sentence words
// it where it says when (`long`: "3h ago").
/** @param {string} ts @param {{face?: string | null, spoken?: boolean, long?: boolean}} [options] */
const panelAge = (ts, { face = "lf-fp-age", spoken = false, long = false } = {}) => {
  const age = html`<time
    class=${spoken ? nothing : (face ?? nothing)}
    datetime=${ts}
    .lfPreview=${agePreview}
    >${long ? ago(ts) : shortAgo(ts)}</time
  >`;
  return spoken ? html`<span data-lf-voice="leaf">${age}</span>` : age;
};
// What a row whose face ends in a word and an age adds to its preview: the word and
// the clock time behind the age, as "Resolved Sat, Nov 21, 2026, 9:05 AM PT", since
// the face says only how long ago (browser/AGENTS.md, "A preview says what its target
// doesn't"). The keyboard reads it at the row, where it can't point at the age.
/** @param {import("../base/voice.js").Words} word @param {string} ts */
const ageLine = (word, ts) => html`${voiced(word)} ${clockTime(ts)}`;

/** @typedef {(typeof GROUPS)[number]} MenuGroup */
/** @typedef {({view: "thread", thread: string} | {view: "group", group: MenuGroup} |
 * {view: "errors", errors: readonly import("../transport/errors.js").RaisedError[]} |
 * {view: "menu"} | {view: "threads"} | {view: "queue"} | {view: "leaves"} |
 * {view: "versions"}) & {
 * thread?: string, group?: MenuGroup, errors?: readonly import("../transport/errors.js").RaisedError[]}} PanelRoute */
/** @template {PanelRoute["view"]} K @typedef {Extract<PanelRoute, {view: K}>} RouteFor */
/** @template {PanelRoute} R @typedef {{
 * title: (route: R) => string, draw: (route: R) => unknown,
 * key?: (route: R) => string, head?: (route: R) => unknown, quiet?: (route: R) => boolean,
 * controls?: (route: R) => {crumb?: unknown, aux?: unknown},
 * presses?: (route: R) => {facts?: unknown, presses?: unknown},
 * nominate?: (route: R, collection: import("../records/thread/primary-reader.js").PrimaryCollection, parts: import("../records/thread/primary-reader.js").NominationParts) => unknown,
 * over?: readonly ("threads" | "queue" | "menu")[], rows?: string, at?: string,
 * row?: PanelRoute,
 * keys?: readonly import("../dom/keyboard/bindings.js").Command[],
 * claims?: (binding: string) => boolean}} PanelView */
/** @typedef {{[K in PanelRoute["view"]]: PanelView<RouteFor<K>>}} PanelViews */
/** @typedef {{key: string, draw: (gone: boolean) => unknown}} MenuSeat */

/** @typedef {FloatingPanel} FloatingPanelElement For its generated tag. */
class FloatingPanel extends LeafElement {
  draw = () => {};
  render() {
    this.draw();
    return noChange;
  }
}
customElements.define("leaf-floating-panel", FloatingPanel);

/** @typedef {NonNullable<ReturnType<typeof import("../host/application.js").mountApplication>>} Application */
/** @typedef {ReturnType<typeof import("./queue-walk.js").createQueueWalk>} QueueWalk */
/** @typedef {Pick<Application, "threadActions" | "registerChromeThreadPresentation" | "queueActions" | "withdraw"> & {
 * wireInput: ReturnType<typeof import("../annotations/composing/input.js").createCompositionInputs>["wireInput"],
 * observeFeedback: ReturnType<typeof import("../records/thread/read.js").createReadTracking>["observeFeedback"],
 * obligations: Pick<ReturnType<typeof import("../records/obligations/view.js").createObligationView>, "choicesOf">,
 * arrivesAt: QueueWalk["arrivesAt"], onMe: QueueWalk["onMe"],
 * placedAt: ReturnType<typeof import("../annotations/anchor-placement.js").createAnchorPlacement>["placedAt"],
 * openThreadSubject: ReturnType<typeof import("../records/thread/destination.js").createThreadDestinations>["openThreadSubject"],
 * showsOnPage: ReturnType<typeof import("../records/thread/destination.js").createThreadDestinations>["showsOnPage"],
 * annotationsHidden: () => boolean,
 * resumeDraft: ReturnType<typeof import("../records/drafts.js").createWritingResume>["resumeDraft"]}} FloatingPanelOptions */
/** @param {FloatingPanelOptions} dependencies */
export function createFloatingPanel({
  wireInput,
  threadActions,
  registerChromeThreadPresentation,
  observeFeedback,
  obligations: obligationView,
  queueActions,
  arrivesAt,
  onMe,
  withdraw,
  placedAt,
  openThreadSubject,
  showsOnPage,
  annotationsHidden,
  resumeDraft,
}) {
  const host = new FloatingPanel();
  host.className = "lf-ui lf-floating-panel";
  // A public part a theme restyles (`layer.chrome_restyle`), as its ground is below.
  host.setAttribute("part", "panel");
  // The panel's durations and curves, which its stylesheet declares on it and says why
  // each is what it is (floating-panel.css, "The panel's motion"), read live as every
  // `--lf-motion-*` is.
  const ease = () => motionEasing("--lf-motion-box-ease", host);
  const foldEase = () => motionEasing("--lf-motion-panel-fold-ease", host);
  const resizeMs = () => motionTime("--lf-motion-box-resize", host);
  const foldMs = () => motionTime("--lf-motion-panel-fold", host);
  const viewResizeMs = () => motionTime("--lf-motion-disclosure", host);
  const fadeMs = () => motionTime("--lf-motion-view-in", host);
  const outMs = () => motionTime("--lf-motion-view-out", host);
  // The leaf answers the moments transport/notifications.js passes on (`gesture`) with a motion
  // each, once per moment, its length on the panel's sheet (`--lf-motion-leaf-nod` and
  // its siblings, named for each motion). A new one takes over from one still playing,
  // which stops where it is rather than carrying on once the new one ends. Each
  // turns, lifts or scales the mark about its centre and comes back to rest, every
  // stretch with its own easing, so it plays over the pose the tone holds
  // (floating-panel.css, `data-lf-tone="away"`). The nod answers the user's own key, so
  // a press shows it landed although the field's words, quiet and already standing on a
  // repeat, may not; the user picked it over the words brightening
  // and the panel tinting, and picked each other moment's motion too,
  // leaving the leaf still while the agent works. The leaf's personality is still
  // evolving (browser/AGENTS.md, "Motion is brief and keeps the user oriented"). Each
  // motion moves the whole mark, since the panel draws it as the layer's icon.svg
  // masking a filled square (chrome.css), which leaves it no parts to move. Parts, such
  // as a blade flexing on its stem, need icon.svg drawn as named shapes, where today it
  // is one path, and the panel drawing the mark from them, as the tab already reads
  // icon.svg's `lf-tone` element (page-status.js). A package's replacement mark without
  // those shapes would move whole.
  const MOTIONS = {
    nod: [
      { transform: "none", easing: "ease-out" },
      { transform: "rotate(-12deg) scale(1.15)", offset: 0.35, easing: "ease-out" },
      { transform: "rotate(6deg)", offset: 0.7, easing: "ease-out" },
      { transform: "none" },
    ],
    // The nod's "no".
    shake: [
      { transform: "none", easing: "ease-in-out" },
      {
        transform: "translateX(-3px) rotate(-5deg)",
        offset: 0.14,
        easing: "ease-in-out",
      },
      {
        transform: "translateX(3px) rotate(5deg)",
        offset: 0.36,
        easing: "ease-in-out",
      },
      {
        transform: "translateX(-2px) rotate(-3deg)",
        offset: 0.58,
        easing: "ease-in-out",
      },
      { transform: "translateX(1px) rotate(1deg)", offset: 0.8, easing: "ease-in-out" },
      { transform: "none" },
    ],
    perk: [
      { transform: "none", easing: "ease-out" },
      { transform: "translateY(-3px) scale(1.14)", offset: 0.4, easing: "ease-out" },
      { transform: "translateY(0.5px) scale(0.98)", offset: 0.75, easing: "ease-out" },
      { transform: "none" },
    ],
    // A leaf in a breeze: two swings, each smaller.
    sway: [
      { transform: "none", easing: "ease-in-out" },
      { transform: "rotate(10deg)", offset: 0.22, easing: "ease-in-out" },
      { transform: "rotate(-6deg)", offset: 0.55, easing: "ease-in-out" },
      { transform: "rotate(2.5deg)", offset: 0.82, easing: "ease-in-out" },
      { transform: "none" },
    ],
    twirl: [
      { transform: "rotate(0deg)", easing: "ease-in" },
      { transform: "rotate(180deg) scale(1.15)", offset: 0.5, easing: "ease-out" },
      { transform: "rotate(360deg)" },
    ],
    beckon: [
      { transform: "none", easing: "ease-in-out" },
      {
        transform: "rotate(14deg) translateX(1px)",
        offset: 0.2,
        easing: "ease-in-out",
      },
      { transform: "none", offset: 0.45, easing: "ease-in-out" },
      {
        transform: "rotate(14deg) translateX(1px)",
        offset: 0.7,
        easing: "ease-in-out",
      },
      { transform: "none" },
    ],
  };
  /** @type {Record<import("../transport/notifications.js").Moment, keyof typeof MOTIONS>} */
  const GESTURES = {
    notice: "nod",
    walk: "nod",
    error: "shake",
    pickup: "perk",
    version: "sway",
    reply: "sway",
    "new-on-me": "beckon",
    "on-me-empty": "twirl",
  };
  /** @type {Animation | null} */
  let gesturing = null;
  /** @param {import("../transport/notifications.js").Moment} moment */
  const gestureLeaf = (moment) => {
    const motion = GESTURES[moment];
    const leaf = host.querySelector(".lf-fp-leaf > svg");
    if (!leaf) return;
    gesturing?.cancel();
    gesturing = playMotion(leaf, MOTIONS[motion], {
      duration: motionTime(`--lf-motion-leaf-${motion}`, host),
      easing: "linear",
    });
  };
  host.setAttribute("role", "region");
  host.setAttribute("aria-label", "Leaf");
  let expanded = false;
  // While a row's press runs its command (`putAwayThen`), the row's posture keeps what
  // it shows, and the press draws it once it has finished. The posture is what stands
  // around the field's occupant and follows it, which no command reads or focuses:
  // `paintNow` writes it through `posture` and `panelTemplate` draws it through `marks`.
  // Which editor or search stands in the field stays live, since the command may open
  // and focus it. Of the posture, `data-lf-offers` decides whether the field or a
  // seated comment box stands in the row (floating-panel.css), so a command that put
  // the caret in the page's field before returning would find the field hidden there;
  // none does today.
  let rowPress = false;
  // One template owns the panel's shell, views and editor placement. Its detached first
  // drawing (`initial`) establishes the retained nodes that setup wires below, and is
  // also the row a served document stands from its first paint, before this module has
  // loaded (build/panel-row.mjs writes it to runtime/panel-row.html, and bootstrap.js
  // stands it): what the row shows before the panel has a reading or an editor. So it
  // draws the leaf without a count and, in the editor's seat, the field's words
  // in a box of their own (`.lf-fp-words`), which the bootstrap rewrites with the keys it
  // holds, under a textarea the user writes in until the editor stands
  // (`.lf-fp-served-field`); the panel's first paint puts the editor there, saying the
  // same words where they stood (floating-panel.css), and takes the textarea's words
  // (`write`, at `mount`). The peek must follow the leaf in the tree so it
  // can anchor to it.
  // The leaf's count keeps its room even when empty; a count arriving moves nothing
  // beside it. The corner mark presses the fold command's row, as the menu does, so
  // its press is announced and logged like the key's.
  function panelTemplate(initial = false) {
    // The row's posture, which a row's press holds (`rowPress`).
    /** @param {unknown} drawn */
    const marks = (drawn) => (rowPress ? noChange : drawn);
    const top = initial ? null : (trail.value.at(-1) ?? null);
    const search = initial ? null : activeSearch();
    const searchMode = initial ? "" : searchModeOf(search);
    const searchControls = search?.controls ?? [];
    const searchLabel = `Search ${searchMode}`;
    const prompt = searchMode === "menu" ? SEARCH_PROMPTS.menu : SEARCH_PROMPTS.threads;
    const thread = top ? (threadOf(top)?.id ?? null) : null;
    const input = initial ? null : fieldInput();
    const reading = initial ? null : fieldReading(top?.thread ?? null, input);
    const selection =
      !search && reading?.says === "selection" && Boolean(draftOf(input));
    // Held keys the field's words don't say, under an error or a draft, stand in the
    // mode chip, as selected words do.
    const held =
      reading && !search && (reading.says !== "held" || draftOf(input))
        ? heldWords.value
        : null;
    const folded = !initial && prefs().rest === "mark" && !top && !search;
    const statusModel = initial ? CONNECTING : status();
    const { onUser, news, kept } = initial
      ? { onUser: 0, news: 0, kept: 0 }
      : leafCounts(folded);
    const unseen = !initial && errorsWaiting(reading);
    const exit = initial ? null : fieldExit(search, top);
    // A view's Close ends the line its presses stand on: a list's tabs at its foot, or
    // the head line, where a thread's presses stand and every other view's name. A
    // search's own ✕ ends the row under a list's tabs while it holds the field, so the
    // list's Close waits, unseen, for the search to end, and one ✕ shows at the foot;
    // it keeps its room, so the search press beside it stays under the pointer.
    const closeAtFoot = Boolean(top && viewOf(top).controls);
    const peek = initial ? null : peekPresentation();
    // A stance's ✕ in the row has the stance's name beside it, as a search's has its
    // scope, read from the dispatcher as the ✕ is (`fieldExit`).
    const stanceName = exit && !search ? stanceWords(innermostStance()?.scope) : null;
    const mode = search
      ? html`<span class="lf-fp-mode-word">Search </span>${iconTemplate(
            "search",
            "lf-fp-mode-icon",
          )}<span>${searchMode}</span>`
      : held
        ? heldParts(held)
        : (stanceName ?? (selection ? "Selection" : nothing));
    const leafName = [
      folded ? "Unfold Leaf" : LEAF_PRESSES[initial ? "menu" : leafOpens(reading)],
      leafMarks(onUser, news, kept),
      statusModel.summary,
    ]
      .filter(Boolean)
      .join(" · ");
    const viewClose = html`<button
      type="button"
      ${offeredAction("symbol", "lf-fp-exit lf-fp-close", "Close", { action: "close" })}
      data-lf-carry="close"
      ?data-lf-unoffered=${Boolean(search) && !menuSearching() && closeAtFoot}
      @mousedown=${(/** @type {MouseEvent} */ event) => event.preventDefault()}
      @click=${() => close()}
    ></button>`;
    const roomLabel = expanded ? "Less room to write" : "More room to write";
    return html`
      <div class="lf-fp-card">
        <div class="lf-fp-inner">
          <div class="lf-fp-opened">
            <div
              class="lf-fp-head"
              data-lf-thread=${thread ?? nothing}
              ?data-lf-thread-view=${thread !== null}
            >
              ${
                top ? headTemplate(top, closeAtFoot ? nothing : viewClose) : nothing
              }${initial ? nothing : joinedTemplate()}
            </div>
            <div class="lf-fp-stage">
              ${
                initial
                  ? nothing
                  : repeat(
                      [...(leaving ? [leaving] : []), ...(top ? [top] : [])],
                      routeKey,
                      (route) =>
                        html`<div
                          class="lf-fp-view"
                          tabindex="-1"
                          data-lf-route=${route.view}
                          data-lf-thread=${threadOf(route)?.id ?? nothing}
                          ?data-lf-thread-view=${threadOf(route) !== null}
                          ?data-lf-rises=${Boolean(route.thread)}
                          ${ref(declareView)}
                          style=${
                            route === top && opening.room !== null
                              ? `height: ${opening.room}px`
                              : nothing
                          }
                          ?data-lf-leaving=${route === leaving}
                        >
                          ${viewOf(route).draw(route)}
                        </div>`,
                    )
              }
            </div>
            <div class="lf-fp-controls" ?hidden=${!closeAtFoot}>
              ${top && closeAtFoot ? controlsTemplate(top, viewClose) : nothing}
            </div>
          </div>
          <div class="lf-fp-row">
            <button
              type="button"
              ${offeredAction("symbol", "lf-fp-expand", roomLabel, {
                action: expanded ? "fit" : "expand",
              })}
              aria-pressed=${String(expanded)}
              @mousedown=${(/** @type {MouseEvent} */ event) => event.preventDefault()}
              @click=${() => {
                expanded = !expanded;
                paint();
              }}
            ></button>
            <div
              class="lf-fp-field"
              @mousedown=${(/** @type {MouseEvent} */ event) => {
                // Holding the caret, the slot runs to the panel's edges and wears the
                // ring there (floating-panel.css), so its padding reads as the field's:
                // a press on it keeps the focus the words hold.
                if (event.target === event.currentTarget) event.preventDefault();
              }}
            >
              <div class="lf-fp-editors" ?hidden=${Boolean(search)}>
                ${
                  initial
                    ? html`<div class="lf-compose-field">
                        <span class="lf-fp-words"
                          ><span class="lf-compose-placeholder"
                            ><span class="lf-compose-placeholder-words"
                              >${voiced(statusModel.summaryParts)}</span
                            ></span
                          ></span
                        ><textarea
                          class="lf-fp-served-field"
                          name="comment"
                          rows="1"
                          aria-label=${PAGE_FIELD_NAME}
                          autocapitalize="sentences"
                        ></textarea>
                      </div>`
                    : top?.thread
                      ? replyOutlet
                      : pageEditor().box
                }
              </div>
              <div
                class=${`lf-fp-search-surface${searchMode === "page" ? " lf-page-search" : ""}`}
                role="search"
                aria-label=${searchMode ? `Search ${searchMode}` : nothing}
                ?hidden=${!searchMode}
              >
                ${initial ? nothing : (pageSearch?.input ?? nothing)}<input
                  type="search"
                  class="lf-fp-search"
                  name="thread-search"
                  placeholder=${prompt}
                  data-lf-voice="leaf"
                  aria-label=${searchLabel}
                  .value=${live(initial ? "" : query)}
                  ?hidden=${searchMode !== "threads" && searchMode !== "menu"}
                  @input=${(
                    /** @type {InputEvent & {currentTarget: HTMLInputElement}} */ event,
                  ) => {
                    query = event.currentTarget.value;
                    refit();
                    paint();
                  }}
                />
              </div>
              <span
                class="lf-fp-mode"
                ?hidden=${mode === nothing}
                aria-label=${search ? searchLabel : nothing}
                .lfPreview=${() => {
                  const words = search
                    ? searchLabel
                    : held
                      ? heldText(held)
                      : selection && !stanceName
                        ? wordsText(reading.words)
                        : null;
                  return words ? { name: words } : null;
                }}
                >${mode}</span
              >
              <div class="lf-fp-actions" ?hidden=${!searchControls.length}>
                ${searchControls}
              </div>
            </div>
            <div class="lf-fp-response"></div>
            ${marks(
              exit
                ? html`<button
                    type="button"
                    ${offeredAction("symbol", "lf-fp-exit", exit.label, {
                      action: "close",
                    })}
                    ?disabled=${Boolean(exit.disabled)}
                    @mousedown=${(/** @type {MouseEvent} */ event) =>
                      event.preventDefault()}
                    @click=${() => exit.press()}
                  ></button>`
                : nothing,
            )}
            <button
              type="button"
              ${offeredAction("symbol", "lf-fp-leaf", leafName, { action: "menu" })}
              data-lf-tone=${statusModel.tone || nothing}
              aria-expanded=${folded ? nothing : String(!initial && onViewStands())}
              .lfPreview=${leafPreview}
              @click=${pressLeaf}
            >
              ${marks(
                html`<span class="lf-badges" aria-hidden="true"
                  ><span class="lf-fp-error-dot" ?data-lf-shown=${unseen}></span
                  ><span
                    class="lf-fp-news-dot lf-unread-dot"
                    ?data-lf-shown=${news > 0 || kept > 0}
                    ?data-lf-drafts=${!news}
                  ></span
                  ><span class="lf-fp-badge lf-badge-count" ?data-lf-shown=${onUser > 0}
                    >${onUser || ""}</span
                  ></span
                >`,
              )}
            </button>
          </div>
        </div>
      </div>
      <div class="lf-fp-peek" ?data-lf-shown=${Boolean(peek?.shown)}>
        ${peek?.content ?? nothing}
      </div>
      <button
        ${offeredAction("mark", "lf-fp-minimize", "Fold to the leaf", {
          action: "minimize",
        })}
        data-lf-corner
        tabindex="-1"
        @click=${() =>
          rows()
            .find((entry) => entry.key === `command:${FOLD}`)
            ?.press?.(null)}
      ></button>
    `;
  }
  render(panelTemplate(true), host);
  /** @param {string} name */
  const shell = (name) => {
    const node = host.querySelector(`.lf-fp-${name}`);
    if (!(node instanceof HTMLElement))
      throw new Error(`Floating panel template is missing ${name}`);
    return node;
  };
  const card = shell("card");
  const opened = shell("opened");
  const stage = shell("stage");
  const head = shell("head");
  const controls = shell("controls");
  // The fold mark rides the box's top-left corner, where macOS keeps a window's
  // minimize, at the far end from the leaf it folds to. The user chose it over the
  // top-right corner, where the leaf's count badge stands since the leaf took the
  // row's end, and over dropping the mark, which leaves a pointer two presses from a
  // fold, through the menu's row. That row and `.` provide its keyboard and touch
  // routes. It shows only while the pointer is near the corner it rides, so the panel
  // at rest, and under a pointer passing over the field or the leaf, carries no
  // control the user did not reach for. Near is the box's top-left corner, a mark's
  // width in and half a row down, or the button itself where it stands out past the
  // box, and never a draft's pictures, which the panel holds above the box: a pointer
  // on one shows the picture's own marks and leaves its press to the picture. The
  // corner moves when the box changes size under a still pointer, as a view opening
  // above a press on Send carries it up, so nearness is read again then (`follow`): a
  // button left showing where the pointer no longer is would ride the box's next
  // change, such as a refused send taking that view back, across the window without
  // input.
  const CORNER = { across: 64, down: 24 };
  const foldMark = shell("minimize");
  /** @type {{x: number, y: number, onMark: boolean} | null} */
  let pointer = null;
  const readCorner = () => {
    const box = card.getBoundingClientRect();
    const near =
      pointer !== null &&
      (pointer.onMark || (pointer.x >= box.left && pointer.y >= box.top)) &&
      pointer.x <= box.left + CORNER.across &&
      pointer.y <= box.top + CORNER.down;
    keeps(host, "data-lf-corner", near ? "" : null);
  };
  host.addEventListener("pointermove", (event) => {
    pointer = {
      x: event.clientX,
      y: event.clientY,
      onMark: event.target instanceof Node && foldMark.contains(event.target),
    };
    readCorner();
  });
  host.addEventListener("pointerleave", () => {
    pointer = null;
    readCorner();
    // A press offered while the pointer stood on the panel stands once it leaves
    // (`pagePress`).
    if (shownOffer !== pageOffer()) paint();
  });
  const leaf = shell("leaf");
  const field = shell("field");
  const editorSeat = shell("editors");
  // A long draft offers more room, by the user's press rather than on its own: past
  // three lines a quiet mark stands over the leaf, in the corner the draft leaves free
  // beside its first line, so it takes no room of its own (browser/AGENTS.md, "A
  // control takes only its own room"). Pressing it widens the
  // panel and gives the field more lines (floating-panel.css), so the words
  // re-wrap because the user asked. It folds back when the field empties, a send included, or on a second
  // press. The user chose this over the panel widening by itself at the
  // third line, which re-wraps every line under the caret; composers such as Open WebUI
  // and Zulip don't widen on their own either, and offer the same press once text is long.
  // Whether the draft in the field runs past three lines, read from the editor's own
  // height as the field's size changes.
  let long = false;
  const lengthWatch = sizeObserver(() => {
    const input = fieldInput();
    const lines = input
      ? (input.getBoundingClientRect().height - 10) /
        Number.parseFloat(getComputedStyle(input).lineHeight)
      : 0;
    if (lines > 3.5 === long) return;
    long = lines > 3.5;
    // In the frame the field grows, so the mark fades in as the line that brought it
    // arrives, carried with the corner it rides (floating-panel.css, `.lf-fp-expand`).
    markRoom();
  });
  // The mark stands while the draft runs long, and while the field is wide, where the
  // draft may fit three lines again; search's field takes no draft.
  const markRoom = () =>
    keeps(host, "data-lf-long", (long || expanded) && !activeSearch() ? "" : null);
  lengthWatch.observe(field);
  // The anchored comment box's home on a page that draws its own annotations
  // (`data-annotations="page"`), where the page gives the box no seat of its own
  // (annotations/composing/surface.js, `responseHome`). While its composer is open it stands in the
  // field's place, as each destination's own editor does there: its words go to a new
  // thread on the passage it quotes, which the box says. The field comes back when the
  // box closes, while a view is open above the row, whose field it is, and while the
  // field quotes words selected on the page, which a press there comments on. Which of
  // the two shows is the stylesheet's reading of the composer's own open state and the
  // row's `data-lf-offers` (floating-panel.css), so the box seated in the page, or put
  // away, moves nothing here. Rejected: a view of its own above the row, which stood a
  // second field over the panel's own.
  const responseSeat = shell("response");

  const status = () => statusReading() ?? CONNECTING;
  // Words drawn in their speakers' faces (base/voice.js), where the agent's sentence alone
  // carries response identity. Its renderer ref registers and retires that exact node
  // with the shared exposure owner, wherever status stands: the field's placeholder
  // slot, the menu, or the folded leaf's peek.
  /** @param {import("../state/activity-words.js").Words} words */
  const statusParts = (words) =>
    [words].flat().map((part) => {
      if (typeof part === "string" || !part.source) return voiced(part);
      const source = part.source;
      /** @type {(() => void) | null} */
      let stop = null;
      return html`<span
        class="lf-fp-status-feedback"
        data-lf-voice=${part.voice}
        ${ref((node) => {
          stop?.();
          stop = node
            ? observeFeedback(node, {
                input_id: source.item,
                reply_id: source.event_id,
                reply_kind: "work",
                presentation_kind: "status_words",
                surface: "panel",
              })
            : null;
        })}
        >${part.text}</span
      >`;
    });
  // The trail of views open above the row, innermost last; empty at rest. It is a
  // signal, since the panel's keys read it and follow the signals they read
  // (dom/keyboard/scopes.js): a press that opens Threads gives the panel its `/` with no
  // other call.
  /** @type {import("@preact/signals-core").Signal<PanelRoute[]>} */
  const trail = signal([]);
  /** @type {PanelRoute | null} */
  let leaving = null;
  let query = "";
  let searching = false;
  // The settled sections the user unfolded while the panel stands open
  // (`settledHeading`).
  const unfolded = new Set();
  /** @typedef {Parameters<import("../annotations/composing/target-picker.js").TargetPickerOptions["searchInPanel"]>[0]} PanelSearch */
  /** @type {PanelSearch | null} */
  let pageSearch = null;
  const threadSearchInput = (() => {
    const input = host.querySelector("input.lf-fp-search");
    if (!(input instanceof HTMLInputElement))
      throw new Error("Floating panel template is missing its search input");
    keepFieldKeys(input);
    return input;
  })();
  const threadSearch = { input: threadSearchInput, controls: [] };
  // While the menu stands the field is its search, so the leaf opens a list the user
  // narrows by typing (`menuFound`); Threads' search opens on `/` or its press. Both
  // take the same native input, each with its own words. The user chose the menu's
  // search, with the menu as the On view's first tab.
  const menuSearching = () => showing({ view: "menu" });
  const activeSearch = () =>
    pageSearch?.open
      ? pageSearch
      : (searching && showing({ view: "threads" })) || menuSearching()
        ? threadSearch
        : null;
  // What the field searches, by the name its mode chip says.
  /** @param {PanelSearch | typeof threadSearch | null} search */
  const searchModeOf = (search) =>
    !search ? "" : pageSearch?.open ? "page" : menuSearching() ? "menu" : "threads";
  /** @param {PanelSearch} search */
  function searchPage(search) {
    pageSearch = search;
    paint();
  }
  function closeThreadSearch() {
    searching = false;
    query = "";
    refit();
    paint();
    const view = shownView();
    if (!view) throw new Error("Closing thread search requires its mounted view");
    focusDestination(view, "return");
  }
  // While the user writes, from the moment they open the field, Dictate, then Send,
  // stand in its one corner, and the first key moves nothing. The user chose this
  // over the field changing at the first key, which moves its end and the action under
  // it as typing begins. At rest the corner stands empty, and the field's end press,
  // such as Reply and its key, stands where the corner's press would, as far from the
  // leaf on the page as in a thread: the two never stand together, since the composer
  // decides both from whether the user writes in the field (annotations/composing/input.js,
  // `writesIn`, `cornerAtRest`). While the field holds words, Send stays in the corner
  // with the caret elsewhere, so a draft the user steps away from keeps every line
  // where it was; the user chose this over the counts coming back as the caret left,
  // which rewrapped the draft each time the user stepped out and back. Rejected:
  // writing that lasts while focus stays anywhere in the panel. It stood Dictate beside
  // the end press, and the room the field kept for it outlived it, so the end press
  // stood a corner's width further from the leaf in some states.
  // Whether the field holds a draft, and whether the user wrote in it, as the row last
  // drew them. A draft is anything typed, a line break included.
  let drafted = false;
  let drawnWriting = false;
  // The beat of the moment the leaf last answered (`gestureLeaf`).
  let answered = gestureReading().beat;
  // The thread the reader lands in once its reading is drawn: on opening,
  // at the turn the user comes back for (`showReturnTurn`); after the user's turn,
  // past it, at its end (`end`); after a press on its held news, at the first message
  // the news showed, where it showed one (`shown`, the messages drawn before it); and
  // reopened where the user had read it to (`reading`, records/thread/reply-landing.js,
  // `restoreCurrentLocation`).
  /** @type {{key: string, end: boolean, shown?: Set<string>, reading?: import("../base/held-place.js").ThreadReading} | null} */
  let landing = null;

  // ---------- one native editor per destination ----------
  // The errors the field can say now, newest first (transport/errors.js): about nothing, not yet
  // edited past, while the editor standing in the field is empty. An error about the
  // editor covers it instead, as at any box (annotations/composing/input.js). A folded panel, or a
  // view with no editor in the field, can say none. The editor is the one this paint
  // stands in the field, whether or not it stands there yet: the paint that closes a
  // thread's view reads before it moves the page's editor in, and read from the DOM,
  // the error would go unsaid for that paint, and the leaf's dot would be set and
  // cleared in one task.
  function sayable() {
    const input = host.dataset.lfRest === "mark" ? null : fieldInput();
    if (!input || draftOf(input) !== "") return [];
    return errorsReading().filter((error) => !error.passed && error.subject === null);
  }
  // The words selected on the page that a press on the page's field comments on, as
  // the response surface offers them (annotations/composing/surface.js, `offerSelection`): their
  // `quote`, and the `comment` that opens the comment on them. Null while none stand.
  /** @typedef {{quote: string, comment: () => unknown}} SelectedWords */
  /** @type {SelectedWords | null} */
  let selectedWords = null;
  // What the keys the bootstrap holds while the page loads say, until the runtime takes
  // them (bootstrap.js, `holdEarlyKeys`), or null while none are shown. They are the
  // user's latest keys and say what became of them, so the field says them in place of
  // whatever else it would but an error, which says why the page may not get ready, and
  // offers no press at its end while they wait, where a key would only join them. The
  // mode chip says them where an error or a draft takes the field's words, and the
  // folded leaf's peek as it says a notice.
  // Before the panel stands, the row the document served shows them (`panelTemplate`,
  // `initial`), which goes as the panel offers its field (`mount`).
  /** @type {import("@preact/signals-core").Signal<HeldWords | null>} */
  const heldWords = signal(null);
  /** @param {HeldWords} words */
  const heldText = (words) =>
    words.map((part) => (typeof part === "string" ? part : part.key)).join("");
  /** @param {HeldWords} words */
  const heldParts = (words) =>
    words.map((part) =>
      typeof part === "string"
        ? voiced(leafSays(part))
        : html`<kbd class="lf-key-badge lf-held-key">${part.key}</kbd>`,
    );
  // What the empty field says and what its end offers, as field-readings.js orders the
  // readings, from the moment's facts for the field asked about: the page's
  // (`key` null) or an open thread's reply box. `drawn` is the thread as its view draws
  // it, which the reply box's words read (`replyOptionsFor`).
  /** @param {string | null} key @param {Element | null} input
   * @param {import("../records/thread/thread-card.js").DrawnThread | null} [drawn] */
  function fieldReading(key, input, drawn = null) {
    const thread = key ? threadByKey(key) : null;
    // A retained field can repaint between a thread leaving the reading and its
    // route being retired. Its native row survives that interval, not its turn.
    if (key && !thread) return ABSENT;
    const held = heldWords.value;
    const page = !key;
    const { notice, goTo, step } = passingFacts(page ? STANDING : NO_STANDING);
    const error = fieldError();
    return readField({
      thread: !page,
      keys: advertisesKeys(),
      writing: writesIn(input),
      error: error && {
        message: error.message,
        press: error.press?.stands() ? pressReading(error.press) : null,
      },
      held: held && heldText(held),
      selected: page && selectedWords ? excerptWords(selectedWords.quote, 60) : null,
      notice: notice && {
        message: notice.message,
        press: notice.press ? pressReading(notice.press) : null,
        news: notice.news,
      },
      goTo,
      step,
      still: stanceStands(),
      standing: () => (page ? standing() : []),
      destination: () => whereTo(drawn ?? thread),
      status: () => status().summaryParts,
      close: stanceClose,
      pagePress,
    });
  }
  // Whether a stance stands, so the row is its (`stanceName`) and the field takes no
  // words (field-readings.js, `still`), as the stance's words in the repaint frame say
  // it (status-context.js), so the field and the row's ✕ change in the same paint.
  const stanceStands = () => statusContextReading().stance !== null;
  // Whether the field takes no words now (`closed`), read from the dispatcher as the
  // repaint frame reads it, so a command in the task that ends a stance, as a Go-to
  // destination's after `g i`, finds the field open before that frame paints it.
  const stanceHolds = () => stanceWords(innermostStance()?.scope) !== null;
  /** @type {ReturnType<typeof readField>} */
  const ABSENT = Object.freeze({
    says: "absent",
    words: [],
    lead: [],
    end: "",
    offers: false,
  });
  // The newest error the field can say, which it says where nothing newer claims it
  // (field-readings.js, "error").
  const fieldError = () => sayable()[0] ?? null;
  // Whether an error waits unseen in the menu's Errors list: one the user hasn't opened
  // the list on, which neither the field says now (`reading`) nor stands at its own box.
  // The leaf and the Errors row wear the same dot for it, so the row a press on the
  // dotted leaf opens to is the one dotted there.
  /** @param {ReturnType<typeof fieldReading> | null} reading */
  function errorsWaiting(reading) {
    const said = reading?.says === "error" ? fieldError() : null;
    return errorsReading().some(
      (error) => !error.seen && error !== said && !standsAtItsBox(error),
    );
  }
  // Where the user stands on the page, which leads the page field's words for as long
  // as the user's own choice stands (field-readings.js, `lead`), each fact with its words
  // in the order they are said (`STANDING_PARTS`): the version the
  // page shows where it is older than the latest (features/version.js, `shownBehind`), how many
  // changes the page marks since the version it compares with (features/version.js), whose
  // bars say only that a block changed, and that the user hid the annotation layer (`g H`,
  // annotations/annotation-layer.js), which a reload keeps, or a page whose marks are hidden would
  // read as one with none. What passes on the page field leaves to these words the
  // facts they say (`STANDING`, `passingFacts`). They stand in the field's words, so
  // the field's width never follows them, and the status changing after them leaves
  // them where they stand. Each part carries its separator in its own speaker's face,
  // so words all Leaf's keep the native placeholder (`saying`). A stance is named in
  // the row's mode chip (`stanceName`).
  /** @type {readonly [string, () => ReturnType<typeof leafSays> | null][]} */
  const STANDING_PARTS = [
    [
      "version",
      () => {
        const { shown } = versionsReading().latest;
        return shown === null ? null : leafSays(shown);
      },
    ],
    [
      "comparison",
      () => {
        const base = comparisonBase();
        return base
          ? leafSays(
              `${counted(comparisonChanges().length, "change")} since ${base.name}`,
            )
          : null;
      },
    ],
    [
      "annotations",
      () => (annotationsHidden() ? leafSays("Annotations hidden") : null),
    ],
  ];
  const STANDING = new Set(STANDING_PARTS.map(([about]) => about));
  function standing() {
    return STANDING_PARTS.map(([, words]) => words())
      .filter((part) => part !== null)
      .map((part) => saidBy(part.voice, `${part.text} · `));
  }
  // The page's own press at the field's end: Open latest while the page shows an older
  // version (`OPEN_LATEST`), else Next On Me while On Me lists anything, or null, where
  // Comment and c stand (`pageOffer`). It comes and goes with the server's reading
  // rather than with the user's input, so while the pointer rests on the panel the
  // field's end keeps what it showed, and takes the change at the user's next input or
  // once the pointer leaves: a press arriving there would stand where the user was
  // about to press another (browser/AGENTS.md, "The page holds still under the user's
  // aim"). A notice's press needs no such hold: it comes and goes with its words, which
  // say why the end changed (transport/notifications.js, `showNotice`).
  /** @returns {FieldPress | null} */
  const pageOffer = () =>
    latestOffered() ? OPEN_LATEST : onUserCount() ? NEXT_ON_ME : null;
  /** @type {ReturnType<typeof pageOffer>} */
  let shownOffer = null;
  let offerShownAt = -1;
  function pagePress() {
    if (pointer === null || inputCount() !== offerShownAt) {
      shownOffer = pageOffer();
      offerShownAt = inputCount();
    }
    return shownOffer ? pressReading(shownOffer) : null;
  }
  // What stands before an open thread's reply while the field says it, beside the leaf
  // (annotations/composing/input.js, `hintLead`): the thread's word, as Threads says it, then a
  // walk's position. The thread walk standing on this thread says only its place,
  // "11 of 11", since the view names the thread; any other walk says what the screen
  // lacks with no words standing before it (records/walk-position.js, `walkWords`), so a
  // comparison's changes are named here, "Change 1 of 5 since v2". The agent's own
  // line, a to-do's title or a start's, stays in the thread, where the working message
  // says it. A notice or the Go-to word, which pass in a moment, take its place.
  // The thread's word is the one its view draws (`drawn`), held news included, as its
  // Resolve says it. The stance the user is in stands in the mode chip, beside its ✕
  // (`panelTemplate`).
  /** @param {string | null} key @param {Element | null} input
   * @param {import("../records/thread/thread-card.js").DrawnThread} drawn */
  function turnLead(key, input, drawn) {
    if (fieldReading(key, input).says !== "turn") return "";
    const thread = threadByKey(key);
    const { walk } = statusContextReading();
    const position = !walk
      ? ""
      : walk.kind === "thread" && walk.target === thread?.id
        ? walk.place
        : walkWords(walk, NO_STANDING);
    // A walk gone on to the page, leaving the thread's view open above the stop it
    // reached (`clearFor`), names that stop alone: the user is at it now, not at this
    // thread's turn.
    const away = Boolean(position) && !currentLocationIn(host);
    const settled = drawn.resolvedBy ? leafSays(drawn.resolvedBy) : RESOLVED;
    const word = away ? null : drawn.resolved ? settled : drawn.attention?.word;
    if (!word) return position && voiced(leafSays(position));
    return voiced([word, ...(position ? [leafSays(` · ${position}`)] : [])]);
  }
  // What the focused field says: the word it says at rest, as every comment box does
  // with the caret in, which the user chose over naming where the
  // words go, which a box beside its target or in its card repeats and cuts short. A
  // reply to a resolved thread still says that it reopens it (events.md), since the
  // Resolved that says so at rest goes with the caret.
  /** @param {{resolved: unknown} | null} thread */
  const whereTo = (thread) =>
    leafSays(!thread ? COMMENT_HINT : thread.resolved ? REOPEN_HINT : REPLY_HINT);
  // An editor's empty words, as its own paint draws them (annotations/composing/input.js, `hint`),
  // which marks the editor with whose reading they are, so the face the theme gives that
  // reading changes in the same paint as the words (floating-panel.css). Words all one
  // speaker says, such as an error or Leaf's own state, mark the editor with that voice,
  // which its placeholder's part wears whole (`voiceOf`).
  /** @param {string | null} key @param {Element | null} input
   * @param {import("../records/thread/thread-card.js").DrawnThread | null} [drawn] */
  function saying(key, input, drawn = null) {
    const { says, words, offers } = fieldReading(key, input, drawn);
    if (input) {
      keeps(input, "data-lf-says", says);
      keeps(input, "data-lf-voice", voiceOf(words));
      keeps(input, "data-lf-offers", offers ? "" : null);
    }
    return wordsText(words);
  }
  // The empty words drawn as parts in the editor's light tree, in their speakers'
  // faces, where the status's exposure registers the agent's sentence (`statusParts`)
  // and the field's preview reads which words the field cuts (`pageEditor`), neither of
  // which reaches the native placeholder inside the editor's closed tree. Null, for no
  // words, leaves the native placeholder.
  /** @param {string | null} key @param {Element | null} input
   * @param {import("../records/thread/thread-card.js").DrawnThread | null} [drawn] */
  function fieldHint(key, input, drawn = null) {
    const { says, words, lead } = fieldReading(key, input, drawn);
    const held = heldWords.value;
    if (says === "held" && held) return heldParts(held);
    const parts = [words].flat();
    // Where the user stands, before the status, is drawn apart from it, so the ink a
    // status that asks wears stays the status's (floating-panel.css).
    if (says === "status" && lead.length)
      return standingParts(lead, parts.slice(lead.length));
    return wordsText(words) ? standingParts([], parts) : null;
  }
  // One template with or without a stance's lead, so a stance coming or going
  // updates the status's nodes in place rather than rebuilding equal ones.
  /** @param {readonly (string | import("../base/voice.js").Said)[]} lead @param {import("../base/voice.js").Words} rest */
  const standingParts = (lead, rest) =>
    html`${lead.length ? html`<span class="lf-fp-standing">${statusParts(lead)}</span>` : nothing}${statusParts(rest)}`;
  // The page's own editor: the field where no thread is open.
  /** @type {{box: HTMLDivElement, input: ReturnType<typeof textField>, sync: () => void} | null} */
  let general = null;
  function pageEditor() {
    if (general) return general;
    const input = textField();
    input.name = "comment";
    // Pointing at the field reads its words whole where it cuts them short (the
    // header, "The row"); annotations/preview.js drops words the field shows whole (`beyondFace`).
    // A draft hides the words, so the field previews nothing while it holds one.
    input.lfPreview = () =>
      input.value ? null : { name: wordsText(fieldReading(null, input).words) };
    const box = el("div", "lf-fp-box");
    box.append(input);
    input.value = loadDraft(PAGE_DRAFT)?.text ?? "";
    // The first Lit render reads this editor through the panel's field selectors.
    general = { box, input, sync: () => sync() };
    const sync = wireInput(input, {
      hint: () => saying(null, input),
      hintParts: () => fieldHint(null, input),
      // The one press the moment offers at the field's end (field-readings.js, `end`).
      enters: () => fieldReading(null, input).end,
      // While a stance stands the field takes no words (field-readings.js, `still`).
      closed: stanceHolds,
      cornerAtRest: () => false,
      // Named for what a press there does, as the field's reading says it, once the
      // editor this builds is the one the reading reads.
      accessibleName: () =>
        general && fieldReading(null, input).says === "selection"
          ? "Comment on the selection"
          : PAGE_FIELD_NAME,
      sends: "send",
      sendClass: "lf-fp-send",
      save: (text) => {
        saveDraft(PAGE_DRAFT, text);
        tellDraft(PAGE_DRAFT, text);
        retype();
      },
      send: (_text, raw, owns) => {
        streamSend();
        // A page comment has no passage, so it records the sections on screen as the
        // user sends it (readings/reading-place.js, `sectionsInView`).
        const viewing = sectionsInView();
        /** @type {PanelRoute | null} */
        let route = null;
        const handle = sendMessage(
          PAGE_DRAFT,
          owns,
          (attempt) =>
            threadActions.create({
              attempt,
              text: raw,
              ...(viewing.length && { viewing }),
            })?.delivery,
          // A refusal takes back the thread the send drew, which the server never held,
          // and its view goes with it (`paintPanel`); the words go back to the page's
          // draft. Unless the user has opened another view since, the field stands for
          // the page again holding them, and the user who has done nothing since in it
          // (records/drafts.js, `sendMessage`).
          () => {
            if (trail.value.length && trail.value.at(-1) !== route) return;
            caretToField = true;
            paint();
          },
        );
        if (!handle) return;
        // The box empties as the send leaves; the row reads it again once it has.
        queueMicrotask(paint);
        // A page comment starts a thread, keyed by the attempt that sent it, which the
        // panel opens, its reply in the same field, and the send lands the user on its
        // view, as every send leaves its box for its thread (records/thread/landing.js,
        // `landSent`).
        route = { view: "thread", thread: handle.attempt };
        open(route, { replace: true, part: "thread", travel: false });
      },
    });
    sync();
    // Resume writing (`g i`) comes back to the page's words here, in the panel.
    mirrorDraft(input, sync, PAGE_DRAFT, {
      retained: true,
      resume: () => ({ where: input, input: () => input, open: writeOnPage }),
    });
    return general;
  }
  // A thread's reply is the reply box every thread view has (records/thread/replies.js), which
  // the thread draws into the field where the panel gives it a place
  // (`nominateThread`), so ↑ to the user's last message, the draft's editing session
  // and Send work as in a card.
  // The panel says what the empty box reads, and a send leaves the user on the view, as
  // in a card (records/thread/landing.js, `landSent`), landing the view at its end. A resolved
  // thread keeps its reply box, whose empty field says Resolved before Reply, and a
  // reply reopens the thread, as the user expects and as every thread card does.
  // Rejected: a field that takes no words there and says only Resolved, so writing in
  // a resolved thread takes Reopen first.
  const replyOutlet = el("div", "lf-fp-reply-outlet");
  const replyInput = () => replyOutlet.querySelector(TEXT_FIELD);
  /** @type {Map<string, import("../records/thread/thread-card.js").ThreadReplyOptions>} */
  const replyOptions = new Map();
  /** @param {string} key */
  const replyOptionsFor = (key) => {
    let options = replyOptions.get(key);
    if (!options)
      replyOptions.set(
        key,
        (options = {
          // The thread's view hands its words the thread as it draws it (`drawn`).
          hint: (drawn) => saying(key, replyInput(), drawn),
          hintParts: (drawn) => fieldHint(key, replyInput(), drawn),
          hintLead: (drawn) => turnLead(key, replyInput(), drawn),
          // A notice passing over the thread's field offers its press at the field's
          // end, as over the page's (field-readings.js, `end`).
          enters: () => fieldReading(key, replyInput()).end,
          closed: stanceHolds,
          cornerAtRest: () => false,
          accessibleName: () => `Reply to ${threadTitle(key)}`,
          sending: streamSend,
          // A turn the log refuses takes its room back from the view, and the words it
          // hands back grow the field as typing does, so the view's head and the controls
          // over the field move with them. The user chose this over holding
          // the head and the field's height through the refusal: the words the
          // user is about to send show whole first, the path is rare, and a hold for it
          // costs code.
          sent: () => {
            // The user's turn lets go of the height a press held (`pressAt`).
            opening.room = null;
            opening.rewriting = false;
            landing = { key, end: true };
            queueMicrotask(paint);
          },
        }),
      );
    return options;
  };
  // The editor standing in the field now, the page's or the open thread's reply; none
  // while search owns the field.
  const fieldInput = () => {
    if (activeSearch()) return null;
    const top = trail.value.at(-1);
    return top?.thread ? (threadOf(top) ? replyInput() : null) : pageEditor().input;
  };
  // The way out between the field and the leaf: a search's, or a stance's while one
  // stands, on the page and in a thread alike. An open view's Close stands on the view's own line
  // (`closeAtFoot`); the menu's search, which holds the field while the menu stands, has
  // no ✕ of its own. It asks the dispatcher whether a stance stands now
  // (`innermostStance`), since the stance's words and its exit row are read in the
  // repaint frame: for the paint a search's close makes, they still name the search,
  // and the row would draw its ✕ for that paint and take it away in the next.
  /** @param {PanelSearch | typeof threadSearch | null} search @param {PanelRoute | null | undefined} top */
  const fieldExit = (search, top) => {
    if (search === threadSearch && !menuSearching())
      return {
        label: "Close search",
        press: closeThreadSearch,
        disabled: false,
        action: null,
      };
    if (top && menuSearching()) return null;
    if (!search && !innermostStance()) return null;
    const exit = rows().find((entry) => entry.exit);
    return exit ? { ...exit, press: () => exit.press?.(null) } : null;
  };
  // A draft arriving in an empty field, or the last of it going, re-seats the row.
  function retype() {
    if (Boolean(draftOf(fieldInput())) !== drafted) paint();
  }
  field.addEventListener("input", retype);
  // A press on the page's editor while words stand selected on the page comments on
  // them, as its placeholder says, rather than writing on the page (`selectedWords`).
  // The words are the ones the field quotes as the press begins, so the press does what
  // the field says (an error the field says instead hides the words, and the press
  // writes on the page). The press's pointerdown is cancelled, so the editor never takes
  // focus, a phone raises no keyboard for it, and the page's selection stands until the
  // comment takes it. The comment opens as the press completes, since the press is
  // still one away from whatever comment box stands open on the page, which goes as it
  // completes (annotations/composing/surface.js, `standDown`). WebKit does not deliver a click
  // after this cancelled touch pointerdown, so the release owns the handoff, and claims
  // the click other engines deliver after it, which would land on the comment box the
  // release opened under the pointer, as on its Other responses. A Tab
  // through the row, or the runtime putting the caret there, writes on the page.
  // The words are kept against the press (dom/focus.js, `pressing`), so a press that never
  // completes, cancelled or let go elsewhere, leaves none behind for a later release.
  const pressedWords = pressRecords();
  const quotedWords = () =>
    general &&
    fieldInput() === general.input &&
    fieldReading(null, general.input).says === "selection"
      ? selectedWords
      : null;
  field.addEventListener(
    "pointerdown",
    (event) => {
      if (!event.isPrimary || !general || !event.composedPath().includes(general.input))
        return;
      const words = quotedWords();
      if (!words) return;
      pressedWords.keep(event, words);
      event.preventDefault();
    },
    true,
  );
  field.addEventListener("pointerup", (event) => {
    const words = pressHolds(event) && pressedWords.kept();
    if (!words || !general || !event.composedPath().includes(general.input)) return;
    claimReleaseClick();
    words.comment();
  });
  // The user's first edit in the field passes every error it could say to the menu's
  // list, read before the edit changes what it could say. The user chose this.
  field.addEventListener(
    "beforeinput",
    () => passErrors(sayable().map((error) => error.id)),
    { capture: true },
  );

  // ---------- readings ----------
  // The threads the page draws, this tab's sends among them while the saved ones are
  // still on their way, so a thread the user just started opens and lists at once. A
  // count is a reading of the saved inventory, so the leaf and tabs say one only once
  // it has arrived (`inventoried`).
  const threads = () => readThreads().threads;
  const inventoried = () => readThreads().phase === "ready";
  /** @param {string | null | undefined} key */
  const threadByKey = (key) => {
    const thread = key ? threadNamed(key) : null;
    return thread && discussed(thread) ? thread : null;
  };
  // The thread a route shows, where it shows one the reading holds.
  /** @param {PanelRoute | null | undefined} route */
  const threadOf = (route) => (route?.thread ? threadByKey(route.thread) : null);
  /** @param {string} key */
  const threadTitle = (key) => {
    const thread = threadByKey(key);
    return thread ? threadName(thread) : "this thread";
  };
  const newCount = () => (inventoried() ? threadCounts(threads()).unread : 0);
  // Where nothing has news, the leaf wears the unread dot grey for these, and opens
  // Threads on them (`leafOpens`). The user asked for it, so a draft put away stays in
  // sight without opening Threads.
  const keptDrafts = () => draftsReading().length;
  const openCount = () => (inventoried() ? threadCounts(threads()).open : null);
  // Ordinary open state is implicit, and news is the row's mark (`data-lf-unread`),
  // which says New to assistive tech alone. Only an open thread is news (`isNews`), as
  // the leaf's dot counts it: the user chose that a resolved
  // thread's unread reply says nothing new. Rows name attention, and a resolved thread
  // says so with how long ago, as a Done line says its outcome and age. A reply the user
  // is writing stands under Drafts (`draftsListing`).
  /** @param {ReturnType<typeof readThreads>["threads"][number]} thread */
  const threadStatus = (thread) => {
    const word = thread.resolved
      ? RESOLVED
      : threadAttention(thread, agentName())?.word;
    return html`${word ? voiced(word) : nothing}${thread.resolved?.ts ? html` ${panelAge(thread.resolved.ts)}` : nothing}`;
  };
  const rows = () => pageControls();

  // ---------- the views ----------
  // What each route the panel shows is, by its `view`, so the panel asks this table
  // rather than a route's name, and a new view is one entry here. A route names its
  // view and what that view shows. One that names a `thread` is that thread's view,
  // which Leaf's reader draws and whose height follows its messages, as the
  // header's "Opened" says (`answersAtOnce`, `holdThread`); every other view fits what
  // the user chose it to show and holds that (`refit`, `holdRoom`).
  // - `key`: what tells two routes of the view apart, where its name alone does not.
  // - `title`: its name, over it, on the way back to it and in the Escape that closes it;
  //   `head` in its heading where that says more, and `quiet` where something in view
  //   already says it, so the heading names it to assistive tech alone: On's tabs, or an
  //   untitled thread's opening message, whose words its name would repeat. While a
  //   title is on its way, the heading shows and says so, as every list of threads does;
  //   the user chose that over a heading of the opening words.
  // - `draw`: what it holds. `presses`: what stands on its head line after its name
  //   (`headTemplate`). `controls`: what stands at its foot (`controlsTemplate`):
  //   `crumb`, its tabs, and `aux`, the presses beside them.
  // - `nominate`: the outlets in it Leaf's reader draws threads or messages into.
  // - `row`: the menu leads to it by a row of the page's controls, which the panel then
  //   opens itself, those rows leading the menu in this order.
  // - `rows`: the rows of a list the arrows walk (`listRows`), and `at`, the one it opens
  //   at (`focusView`).
  // - `over`: the lists it opens over, which its way back returns to, the first where it
  //   was opened from anywhere else (`open`). A list the menu leads to, such as
  //   Versions, opens over the menu, so its way back returns there.
  // - `keys`: the page's keys it acts on itself while it stands, and `claims`, those it
  //   rests (the declaration on the view, below).
  // Versions' key for the live page, from an older version: what Open latest does, where
  // a version's digit opens that version pinned, so it stays as later versions land. It
  // puts Versions away as a digit does (`showVersion`); its row in the list is a
  // finger's route.
  /** @type {import("../dom/keyboard/bindings.js").Command} */
  const latestRow = {
    id: "panel.floating.versions.latest",
    keys: ["l"],
    title: "latest version",
    touch: false,
    when: () => {
      const { latest } = versionsReading();
      return latest.shown !== null && !latest.disabled;
    },
    run: () => putAwayThen(() => versionPicker.latest()),
  };
  // The version the user stands on in Versions: the row holding focus, else the one
  // Versions opened at (`versionsList`).
  const standingVersion = () => {
    const view = shownView();
    const on = view && currentLocationIn(view) ? focused() : null;
    return (
      on?.closest(".lf-fp-version") ??
      view?.querySelector(".lf-fp-version[data-lf-at]") ??
      null
    );
  };
  const standingCompare = () =>
    standingVersion()?.querySelector(":scope > .lf-fp-compare") ?? null;
  // Versions' key that compares the version the user stands on, by pressing its
  // Compare, so `g V v` marks what changed since the version Versions offers, and on a
  // lit Compare takes the marks off. The Compare beside each row is a finger's route.
  // While Versions stands, the row holding focus decides through `control`; before it
  // opens, the version it opens at does (features/version.js, `offeredVersion`), so the keys of
  // Show changes can say `g V v` (dom/keyboard/control-keys.js, `pressNow`).
  /** @type {import("../dom/keyboard/bindings.js").Command} */
  const compareRow = {
    id: "panel.floating.versions.compare",
    keys: ["v"],
    title: "compare",
    touch: false,
    control: standingCompare,
    when: () => {
      if (versionsShown()) return true;
      const offered = offeredVersion();
      return offered !== null && comparable(offered);
    },
  };
  /** @type {PanelViews} */
  const VIEWS = Object.freeze({
    menu: {
      title: () => "Menu",
      quiet: () => true,
      draw: () => menuView(),
      controls: () => ({ crumb: onTabs("menu") }),
      rows: ".lf-fp-item:not(:disabled)",
      keys: [
        {
          id: "panel.floating.menu.find",
          keys: ["/"],
          title: "search the menu",
          run: () => focusDestination(threadSearchInput, "move"),
        },
      ],
    },
    threads: {
      title: () => "Threads",
      quiet: () => true,
      draw: () => threadsView(),
      controls: () => threadsControls(),
      rows: ".lf-fp-draft, .lf-fp-thread, .lf-fp-settled",
      // It opens on its first thread, so Enter there opens a conversation whether or
      // not Drafts stands over it.
      at: ".lf-fp-thread",
      keys: [
        {
          id: "panel.floating.threads.find",
          keys: ["/"],
          title: "find a thread",
          run: () => findThreads(),
        },
      ],
    },
    thread: {
      key: (route) => `thread:${route.thread}`,
      title: (route) => threadTitle(route.thread),
      head: (route) => {
        const thread = threadOf(route);
        return thread ? threadHeading(thread) : threadTitle(route.thread);
      },
      quiet: (route) => {
        const thread = threadOf(route);
        return thread?.title == null && !(thread && titlePending(thread));
      },
      draw: (route) => threadView(route.thread),
      presses: (route) => threadPresses(route),
      nominate: (route, collection, parts) => nominateThread(route, collection, parts),
      over: ["threads", "queue", "menu"],
    },
    queue: {
      title: () => tabLabel(queueTab),
      quiet: () => true,
      draw: () => onView(),
      controls: () => queueControls(),
      nominate: (_route, collection, parts) => nominateAsked(collection, parts),
      // Done's band is a row, as Threads' Resolved is, so the arrows reach what it
      // folds (`groupedItems`).
      rows: ".lf-fp-on-item[data-lf-card], .lf-fp-on-line, .lf-fp-settled",
    },
    leaves: {
      title: () => "All pages",
      draw: () => pagesView(),
      rows: ".lf-fp-page[href]",
      row: { view: "leaves" },
    },
    versions: {
      title: () => "Versions",
      draw: () => versionsList(),
      rows: ".lf-fp-version > :is(.lf-fp-item, .lf-fp-compare)",
      at: ".lf-fp-version[data-lf-at] > .lf-fp-item",
      row: { view: "versions" },
      over: ["menu"],
      // Versions is a list for choosing, so while it stands the page's character keys
      // rest rather than move the page under it; two doors stay open: `?`, and Go-to,
      // whose `g V` puts Versions away as it opened it.
      keys: [
        {
          id: "panel.floating.versions.pick",
          keys: () => numbered().map(({ version }) => String(version)),
          label: () => {
            const top = numbered().at(-1)?.version;
            return top !== undefined && top > 1 ? `1–${top}` : "1";
          },
          title: "show version",
          when: () => numbered().length > 0,
          runKey: (binding) => {
            const chosen = numbered().find(
              ({ version }) => String(version) === binding,
            );
            if (!chosen)
              throw new Error(`Version ${binding} is unavailable in the panel`);
            showVersion(chosen.entry);
          },
        },
        latestRow,
        compareRow,
      ],
      claims: (binding) => {
        const { key, mods } = parsed(binding);
        return (
          key.length === 1 &&
          key !== " " &&
          mods.every((mod) => mod === "Shift") &&
          !pageDoor(binding)
        );
      },
    },
    errors: {
      title: () => "Errors",
      draw: (route) => errorsList(route),
      over: ["menu"],
    },
    group: {
      key: (route) => `group:${route.group.name}`,
      title: (route) => route.group.label,
      draw: (route) => groupList(route.group.name),
      rows: ".lf-fp-item:not(:disabled)",
      over: ["menu"],
    },
  });
  /** @template {PanelRoute["view"]} K @param {RouteFor<K>} route @returns {PanelView<RouteFor<K>>} */
  const viewOf = (route) => VIEWS[route.view];
  // A route's key is also the `data-lf-row` of the menu's row that opens it, which going
  // back stands on.
  /** @param {PanelRoute} route */
  const routeKey = (route) => viewOf(route).key?.(route) ?? route.view;
  /** @param {PanelRoute} route */
  const titleOf = (route) => viewOf(route).title(route);
  // The views the menu's rows open, in the order they lead it.
  const OWN_VIEWS = Object.values(VIEWS).flatMap((view) =>
    view.row ? [view.row] : [],
  );
  // Whether the route is the view standing over the row.
  /** @param {PanelRoute} route */
  const showing = (route) => {
    const at = trail.value.at(-1);
    return Boolean(at && routeKey(at) === routeKey(route));
  };
  // Whether the On view stands on any of its tabs, itself or under a view it leads to,
  // such as a thread opened from Threads or a list from the menu, so the leaf that opened
  // it closes it.
  const onViewStands = () => trail.value.some((level) => ON_VIEW.has(level.view));
  // What one opening of the view over the row keeps, from the change that opens it to
  // the one that puts it away, by its route's key (`transition`): a change of key,
  // closing included, starts a fresh opening, so nothing one view held reaches the
  // next, and a change that keeps the key keeps the opening. Within it, a field goes
  // back only where what it holds lapses while the view stands: the user's turn, a
  // tab, a list refitting. A view fading out draws beside the opening that replaced
  // its own. Each field is described where it is used.
  /**
   * @typedef {{
   *   drawn: boolean,
   *   room: number | null,
   *   rewriting: boolean,
   *   pressed: {
   *     node: Element, at: number, height: number, holds: number, keep: () => void,
   *   } | null,
   *   drawnRows: Map<string, {section: string, at: number}> | null,
   *   drawnDrafts: Set<string> | null,
   *   onPageSeat: boolean,
   *   openItem: string | null,
   *   seatHeights: Map<string, number>,
   *   menuSeats: { key: string, draw: (gone: boolean) => unknown }[] | null,
   *   menuLines: { summary: number, explain: number } | null,
   * }} Opening
   */
  /** @returns {Opening} */
  const freshOpening = () => ({
    drawn: false,
    room: null,
    rewriting: false,
    pressed: null,
    drawnRows: null,
    drawnDrafts: null,
    onPageSeat: false,
    openItem: null,
    seatHeights: new Map(),
    menuSeats: null,
    menuLines: null,
  });
  let opening = freshOpening();

  // ---------- navigation ----------
  // The trail a route opens at from anywhere but a list it opens over.
  /** @param {PanelRoute} route @returns {PanelRoute[]} */
  const pathTo = (route) => {
    const [over] = viewOf(route).over ?? [];
    return over ? [{ view: over }, route] : [route];
  };
  // The stances that stood as each view opened, so Escape takes whichever of a view
  // and a stance came last (the `floating panel` rung): a mode entered from an open
  // thread ends first, and a thread opened in a mode closes first. The user asked
  // for this, since the one entered last is the one they are in. Rejected: the
  // view always first, which left a mode entered from a thread on as Escape took the
  // thread away, and the mode always first, which ends the mode under a thread
  // opened in it. Every stance standing counts, so a view a Go-to key opens in Draw
  // mode, while both stand, still closes before Draw mode ends.
  /** @type {WeakMap<PanelRoute, ReadonlySet<import("../dom/keyboard/bindings.js").Scope>>} */
  const openedIn = new WeakMap();
  // A thread lands the user in its reply (`focusView`), or on the thread itself
  // (`part`), as the thread a send starts does. A thread opened where the user stands,
  // as a send's is, passes `travel: false` to a package's reader, so its route adds no
  // Back step (features/anchor-travel.js, `prepareNavigationStep`).
  /** @param {PanelRoute} route @param {{replace?: boolean, reopen?: boolean, focus?: boolean, part?: "reply" | "thread", travel?: boolean}} [options] */
  function open(
    route,
    {
      replace = false,
      reopen = false,
      focus = true,
      part = "reply",
      travel = true,
    } = {},
  ) {
    const before = trail.value.at(-1);
    if (before && routeKey(before) === routeKey(route) && !replace) {
      if (reopen) return;
      putAway();
      return;
    }
    if (route.thread && presentation && !presentation.primary) {
      openInPackage(route.thread, { focus, part, travel });
      return;
    }
    // A view opened from a list it opens over, as a thread from Threads or On, has that
    // list behind it, so its back link returns where the user came from.
    trail.value =
      replace && before
        ? [...trail.value.slice(0, -1), route]
        : before && viewOf(route).over?.some((view) => view === before.view)
          ? [before, route]
          : pathTo(route);
    if (replace && trail.value.length === 1) trail.value = pathTo(route);
    // Threads' search lasts while Threads stands in the trail, a thread opened from it
    // over it.
    if (!trail.value.some((level) => level.view === "threads")) searching = false;
    if (route.thread) arriveAt(route.thread);
    openedIn.set(route, new Set(standingStances().map(({ scope }) => scope)));
    openLayer(host);
    transition(before, { focus, part });
  }
  // Where the page's package draws its conversations, a thread opens in its reader, in
  // its reply as a row's opening does (`focusView`), or on the thread a send starts
  // (`part`), and the view it was chosen from goes, uncovering the page.
  /** @param {string} key @param {{focus?: boolean, message?: string | null, part?: "reply" | "thread", travel?: boolean}} [options] */
  function openInPackage(
    key,
    { focus = true, message = null, part = "reply", travel = true } = {},
  ) {
    if (trail.value.length) close();
    void threadActions.open(threadByKey(key)?.key ?? key, {
      part,
      focus,
      message,
      travel,
    });
  }
  // A row of a list here that names a thread, in Threads, On Me's Reply and Discuss or
  // the menu's search, opens it by the route every opening of a thread takes, so it
  // follows the user's choice of where threads open (records/thread/destination.js): in this
  // panel, over the list, which its way back returns to (`reveal`), or beside its
  // passage, where the list goes once the thread stands there, since the user has gone
  // on to the page. It lands in the reply, by a key as by a press, since what the user
  // types after picking a row is an answer (records/thread/focus.js, `openingPart`); a finger
  // lands on the thread, since the keyboard a reply takes would rise over what the user
  // opened to read.
  /** @param {string} key */
  function openRow(key) {
    const intent = retainUserIntent();
    const part = coarsePointer.matches ? "thread" : "reply";
    void threadActions.open(key, { part, intent }).then((landed) => {
      if (!landed || !intent() || renderedUnder(landed, host)) return;
      if (trail.value.length) close();
    });
  }
  // Opening a thread shows it at its first unread reply, as its card does, else at its
  // end, where the latest turn is. The user chose that over opening at
  // the end with Next unread, which leaves a long unread reply's head, with its New,
  // above the view.
  /** @param {string} key */
  function arriveAt(key) {
    landing = { key: threadByKey(key)?.key ?? key, end: false };
  }
  // Asking to write is asking for the field, so a folded panel unfolds, and the field
  // stands for the page again, with nothing open above it.
  // Whether the paint that next stands the page's field in the row puts the caret in it.
  let caretToField = false;
  function clearRow() {
    const before = trail.value.at(-1);
    if (prefs().rest === "mark") prefs().setRest("row");
    // Thread presentation may nominate this seat again after its own commit. An
    // already empty route must keep its signal identity or that commit reads the
    // new route as an input and starts the same presentation again.
    if (trail.value.length) trail.value = [];
    transition(before, { focus: false });
  }
  function writeOnPage() {
    caretToField = true;
    clearRow();
  }
  // Resolving a thread opened from Threads moves the user on: to the open thread after it
  // in the list's order, or before it at the end, standing on its view so `r`, `t` and
  // Escape go on from there; or, with none left, back to the list. A thread opened from
  // elsewhere goes back to where it came from. Taking the resolve back, or the log
  // refusing it, opens the thread again (folding.js, `settleThread`).
  const openThreads = () =>
    newestFirst(
      threads().filter((candidate) => !candidate.resolved),
      lastChange,
    );
  // The next thread is a fresh opening, as tall as what it holds (the header records
  // why its Resolve doesn't stay under the pointer). The thread resolved is found among
  // the open ones by its key: the record the thread draws from need not be the list's.
  /** @param {string} key */
  function resolveLanding(key) {
    const route = trail.value.at(-1);
    const fromThreads = trail.value.at(-2)?.view === "threads";
    const at = openThreads().findIndex((candidate) => candidate.key === key);
    const mayLand = retainUserIntent();
    return () => {
      if (!mayLand() || trail.value.at(-1) !== route) return false;
      const kept = openThreads();
      const next = fromThreads ? (kept[at] ?? kept[at - 1]) : null;
      // The next thread opens where every route to a thread opens it
      // (records/thread/destination.js): here, in place of the resolved one, or beside its
      // passage, where this view goes.
      if (next)
        return threadActions
          .open(next.key, { part: "thread", intent: mayLand })
          .then(Boolean);
      back();
      return true;
    };
  }
  function back() {
    const before = trail.value.at(-1);
    trail.value = trail.value.slice(0, -1);
    // Back in the menu, the user stands on the row that opened the list. The transition
    // leaves them to it rather than standing them on the menu's first row, which the
    // paint's walk would follow there and back, a write that changes nothing.
    const door =
      before && trail.value.at(-1)?.view === "menu" ? routeKey(before) : null;
    transition(before, { focus: door === null });
    if (door === null) return;
    const row = shownView()?.querySelector(`[data-lf-row="${CSS.escape(door)}"]`);
    if (row) focusDestination(row, "return");
    else focusView(trail.value.at(-1), null);
  }
  // A press that puts the view away, the leaf's or a door's, takes a user standing in
  // it back to the page, as Escape does (the `floating panel` rung), rather than
  // leaving focus on nothing as the view goes. One standing anywhere else stays there.
  function putAway() {
    const inside = currentLocationIn(opened);
    close();
    if (inside) letGo();
  }
  function close({ handedOn = false } = {}) {
    const before = trail.value.at(-1);
    trail.value = [];
    searching = false;
    unfolded.clear();
    transition(before, { handedOn });
  }
  // A row's press puts away the view it stands in, the menu or a list it leads to, and
  // the command owns any navigation it causes. Hand back to the leaf, the menu's door,
  // before its command runs, so the pressed row going takes no one's focus to the body:
  // a layer the command opens records the leaf as where its close returns (dom/focus.js,
  // `openLayer`), folding leaves the user on the leaf it folds to, and a command that
  // places the user elsewhere still does. The command runs on the panel the put-away
  // drew, and may then open a view or fold the panel, as ⌘Z showing a thread does. The
  // row's posture (`rowPress`) waits for the command to return, so it is written once,
  // from where the press found the panel to where the command leaves it, rather than for
  // the empty row in between as well; a view the command opens after an `await` changes
  // it again. Rejected: drawing the put-away only with the command's own change, which
  // ran the command with the view still drawn, and Align from the menu then left the
  // page where it was.
  /** @param {() => unknown} run */
  function putAwayThen(run) {
    const inside = currentLocationIn(host);
    rowPress = true;
    try {
      close();
      if (inside) focusDestination(leaf, "return");
      run();
    } finally {
      rowPress = false;
      paint();
    }
  }

  // ---------- motion: everything follows the box ----------
  // The box's layout changes in one step, whatever changed it: a view opening, a field
  // growing a line, more room, folding to the leaf. Everything the user sees then moves
  // from where it was drawn to where it stands, by one model (dom/box-motion.js): the
  // surface draws the box's outline, and the field's ring while it moves; a part that
  // kept its size is carried; one that changed size grows from where it stood; one that
  // is new is revealed by the edges of what holds it. The first reading, and any under
  // reduced motion, is taken as it is.
  //
  // Until when a change is a view arriving or leaving (`transition`), which takes the
  // shorter tween: the view's own change, and the one when the view it replaced is gone
  // after its fade.
  let viewMovingUntil = 0;
  // Leaf's reader draws into the open thread's view on its own schedule, and its
  // draw lands the view. That may change the box's size, and the browser
  // delivers no observer a box shallower than the view later in the frame it resized,
  // so the box is read again here, before that frame paints what moved.
  const fit = sizeObserver(() => {
    stood = openView()?.offsetHeight ?? null;
    followBox();
  });
  const follow = sizeObserver(() => {
    readCorner();
    followBox();
  });
  const following = boxMotion({
    root: host,
    box: card,
    // The surface the box stands on: a layer of its own over the whole window, with a
    // ring a pixel outside the box's outline, cast at the height of what opens over
    // the page, so its outline can move between two places without either box's
    // layout moving.
    surface: "lf-ui lf-fp-ground",
    lift: 2,
    outset: 1,
    observer: follow,
  });
  const { ground } = following;
  // The ground stands beside the panel rather than in it, so it carries the panel's
  // part too, and the tokens a theme sets there colour both.
  ground.setAttribute("part", "panel");
  // The box stands over the window's foot, the row and any view open above it: what it
  // covers reads as unseen (dom/geometry.js, `declareCover`), and a landing stands clear of
  // its reach (`followBox`). It covers where its surface is drawn
  // (dom/box-motion.js, `outline`): while the box moves, the card stands transparent at its
  // rest and the surface carries the panel from where it stood. The card's own box is
  // where that motion ends, which a landing about to show a place asks (`standsOver`).
  declareCover(
    host,
    () => following.outline(),
    () => card.getBoundingClientRect(),
  );
  // A send is the user's change joining the stream the box shows (dom/box-motion.js,
  // "send"): the box reads where that stream stands before the send draws, and each
  // reading until the send's rendering settles carries it on from where it last stood,
  // on the box's own tween.
  function streamSend() {
    following.stream();
  }
  let bandFrame = 0;
  function followBox() {
    stateBand();
    const compact = host.dataset.lfRest === "mark";
    const duration = compact
      ? foldMs()
      : performance.now() < viewMovingUntil && following.theirs() !== "send"
        ? viewResizeMs()
        : resizeMs();
    following.follow({ duration, easing: compact ? foldEase() : ease() }, compact);
  }
  function stateBand() {
    // How far the box reaches up from the window's foot, with the gap above the box and
    // at least the foot's room (`--lf-foot-band`, base.css): the band Leaf's landings
    // keep clear of (dom/geometry.js, `stateFootBand`, `landingBand`), so `m`, `t`, a Go-to or
    // an On Me row's Show lands what it reaches above an open view rather than under it.
    const box = card.getBoundingClientRect();
    const reach = box.height > 0 ? ground.getBoundingClientRect().bottom - box.top : 0;
    const root = document.documentElement;
    const [rest = 0, clear = 0] = getComputedStyle(root)
      .getPropertyValue("--lf-foot-band")
      .trim()
      .split(/\s+/)
      .map(Number.parseFloat);
    const band = atLayoutPrecision(Math.max(rest, reach + clear));
    if (stateFootBand(band)) {
      // This runs in the box's size delivery, which may write only what no one observes
      // (page-layout.js). The margin hears the news of the room, and its pass places an
      // open thread card in the same delivery, resizing a box shallower than any the
      // delivery can still reach: a ResizeObserver loop. So the news waits for the
      // frame; Leaf's own landings read the band stated above at once.
      bandFrame ||= nextRender(() => {
        bandFrame = 0;
        announceRoom();
      });
    }
  }

  // A view is as tall as what it holds, up to its cap (floating-panel.css,
  // `--lf-fp-view-height`); what does not fit scrolls inside it. A thread's view follows
  // its messages and every other fits what it shows (`VIEWS`); either way its top edge
  // moves, carrying its head line, while a list's tabs at its foot stay put. What a list
  // first holds is what it shows, and a message Leaf's reader has yet to draw into it is
  // not yet held. A thread's reader holds back any news that would move what is read
  // (records/thread/held-news.js) until the user asks for it. A reply the user sends grows the
  // view to show it, and news they open from the head line shows inside the view the
  // press holds (below).
  //
  // The agent's answer to the user's own last turn is the one news the reader hands the
  // view at once (`answersAtOnce`): the user is waiting for it. The view grows to hold
  // it, work under way and a reply streaming included, up to its cap: the field stays
  // put and the view's top edge rises, carrying its head line and the user's own turn
  // up with it. Past its cap the thread follows the answer into sight or says New reply
  // at the view's foot, the view being the box it names as its scroller
  // (records/thread/thread-card.js). The user
  // chose this growth, the one case where news may carry what a view shows
  // without a gesture (`browser/AGENTS.md`, "The page holds still under the user's aim"), over the view
  // holding its height while the user waits, which leaves a short thread's
  // answer behind New reply in a view one message tall. Rejected too: holding
  // the answer behind the reader's "1 new reply", which leaves the reply the user waits
  // for unseen. The growth carries Resolve and a message's pencil from under a pointer
  // resting on one, which the user called secondary and let move
  // (`browser/AGENTS.md`); a hold built for that pointer, which keeps the answer behind
  // the notice while it rests on a control, also holds replies that would move
  // nothing and misses a pointer on Copy. Other news in an open thread is still held.
  // A thread's view declares that it stands on its foot (`data-lf-rises`), which the
  // shift watch credits for exactly this growth (tests/shift_watch.js, `appendGrowth`).
  // Whether this opening of a thread has shown Show on page (`onPageSeat`), whose seat
  // then stands while the view does, so a revision detaching the thread moves nothing
  // beside it.
  // A thread's view stands on its foot, so what grows in it carries its name, and all
  // the view holds, up the window. That is the growth news and the user's own turns
  // make (`answersAtOnce`), but a press keeps what it pressed under the pointer. So where
  // what a press in the view grows would carry the pressed control away, as a quote's
  // label opening it, Show on a fold that opens below it, or a rewrite's pencil would,
  // the view holds the height it stood at as the press came (`judgePress`, before the
  // frame shows the growth) until the user's next turn, and what the press grew goes on
  // inside the view, revealed by scrolling. A press whose growth leaves it in place, as
  // Show on progress, which opens above it, holds nothing, so the view grows to show what
  // opened; nor does a press that grows nothing, so an answer the user waits for still
  // grows the view. A press on the head line, which every growth carries, holds the
  // view whatever it grows (below). The
  // caret in a rewrite, which a key can open from the field, holds the view while it
  // stays there, so typing carries none of the rewrite's own presses, the rewrite's
  // lower lines revealed by scrolling (records/thread/reply-landing.js, `revealEditor`). A card
  // grows down from the same press, so there the press stays put by itself. Rejected: a
  // hold for each control that grows the view, which missed each one added after it, as
  // the folds did; and every press in the view holding it, which kept an awaited answer
  // from growing it after a click on the words.
  //
  // The height the open view holds, a list's or a thread's, or null where it fits what
  // it holds (`room`), and whether the caret in a rewrite holds it (`rewriting`).
  // The open thread's view's height as last drawn, which the caret entering a rewrite
  // holds.
  /** @type {number | null} */
  let stood = null;
  /** @param {number | null} height */
  const holdThread = (height) => {
    if (!trail.value.at(-1)?.thread || opening.room !== null || height === null)
      return false;
    opening.room = height;
    return true;
  };
  // The view's head line stands on the edge its growth carries, so a press on any of
  // its controls holds the view's height as it comes, and what the press opens goes on
  // inside the view, brought into sight as the press takes the user there: Next unread
  // to a reply a summary held, and the held news's notice to the first message it
  // showed (`landing`); news that changed messages in place shows in place. The
  // presses beside it stay under the pointer.
  // A press on the name holds nothing, as words in the view don't. Rejected: the news
  // growing the view, which carried Resolve and Close up from beside the notice.
  head.addEventListener(
    "click",
    (event) => {
      const press =
        event.target instanceof Element ? event.target.closest("button") : null;
      const route = trail.value.at(-1);
      if (!press || !route?.thread) return;
      const view = openView();
      // Drawn once the script that made the press ends, still before the frame: a
      // press that leaves the thread, as Back does, takes the hold with the view, so
      // the hold never writes a height the leaving view would lose in the same script.
      if (holdThread(view?.getBoundingClientRect().height ?? null)) afterScript(paint);
      if (press.closest(".lf-fp-news-outlet") && view)
        landing = {
          key: threadByKey(route.thread)?.key ?? route.thread,
          end: false,
          shown: new Set(
            [...view.querySelectorAll(".lf-msg[data-lf-message]")].map(
              (message) => /** @type {HTMLElement} */ (message).dataset.lfMessage ?? "",
            ),
          ),
        };
    },
    { capture: true },
  );
  // A press that changes the view brings other controls under a pointer that hasn't
  // moved: the ‹ back to the menu, at the head of a shorter list, stands where the
  // menu's Undo comes. No control in the panel means anything by a second click, so a
  // click that goes on a run of clicks presses nothing and takes no focus where it lands
  // on another control than the run's last press did and the panel has drawn since that
  // press began: a double-click on ‹ goes back once. Clicks repeated on one control, as
  // Next match, each press it. So does a tap on Close just after a finger's hold read
  // Search beside it, which Chromium counts into the same run: the hold drew nothing in
  // the panel, so nothing it did put Close there. The run is the browser's, which counts
  // every press into it, a hold whose release its preview took included (annotations/preview.js), so
  // the panel hears each press as it begins rather than the clicks it receives.
  /** @param {Event} event */
  const pressed = (event) =>
    event.target instanceof Element ? event.target.closest("button") : null;
  // The control a press lands on and how many times the panel had drawn as it began
  // (`draws`): this press's, and the last one's it pressed. A press refused leaves the
  // run judged by the press before it, so a triple click's third presses nothing either.
  /** @typedef {{control: WeakRef<Element> | null, draws: number, refused: boolean}} RunPress */
  // How many times the panel has drawn (`paintPanel`).
  let draws = 0;
  /** @type {RunPress | null} */
  let pressNow = null;
  /** @type {RunPress | null} */
  let pressBefore = null;
  host.addEventListener(
    "pointerdown",
    (event) => {
      if (pressNow && !pressNow.refused) pressBefore = pressNow;
      const control = pressed(event);
      pressNow = { control: control && new WeakRef(control), draws, refused: false };
    },
    { capture: true },
  );
  /** @param {MouseEvent} event */
  const runOfClicks = (event) => {
    const control = pressed(event);
    if (
      event.detail > 1 &&
      control &&
      control !== pressBefore?.control?.deref() &&
      pressNow?.draws !== pressBefore?.draws
    ) {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (pressNow) pressNow.refused = true;
    }
  };
  host.addEventListener("mousedown", runOfClicks, { capture: true });
  host.addEventListener("click", runOfClicks, { capture: true });
  // The press being judged: the control pressed, where it stood in the view's content,
  // how tall the view and what it holds stood, and its hold on screen (readings/user-place.js,
  // `holdPlaceOf`). Once what the press changed has drawn, after the press's own
  // handlers, and before the frame shows it, the press is put back where it stood on
  // screen. A change below it would carry it as the view
  // grows or shrinks from its top edge, so the view holds the height it stood at. A
  // change above it, as progress opening over the answer whose head holds its
  // disclosure, leaves it in place as far as the view's height takes the change up, so
  // the view keeps growing or shrinking as it would, and scrolls by the rest. A press
  // that changes the view leaves its opening, so the next view judges nothing
  // (`pressed`).
  /** @param {Element} node @param {HTMLElement} view */
  const contentTop = (node, view) =>
    node.getBoundingClientRect().top -
    view.getBoundingClientRect().top +
    view.scrollTop;
  // How tall what the view holds stands, whatever height the view itself stands at.
  /** @param {HTMLElement} view */
  const holding = (view) =>
    Math.max(
      0,
      ...[...view.children].map(
        (child) => contentTop(child, view) + child.getBoundingClientRect().height,
      ),
    );
  /** @param {EventTarget | null} node */
  function pressAt(node) {
    const top = trail.value.at(-1);
    const view = openView();
    if (!top?.thread || !view || !(node instanceof Element)) return;
    if (!renderedUnder(node, view)) return;
    opening.pressed = {
      node,
      at: contentTop(node, view),
      height: view.offsetHeight,
      holds: holding(view),
      keep: holdPlaceOf(node),
    };
  }
  function judgePress() {
    const press = opening.pressed;
    opening.pressed = null;
    const view = openView();
    if (!press || !view || !press.node.isConnected) return;
    if (Math.abs(holding(view) - press.holds) < 0.5) return;
    const above = contentTop(press.node, view) - press.at;
    if (Math.abs(above) < 0.5) {
      if (holdThread(press.height)) paint();
      return;
    }
    press.keep();
  }
  stage.addEventListener("click", (event) => pressAt(event.target), { capture: true });
  stage.addEventListener("click", judgePress);
  /** @param {Node | null} node */
  const inRewrite = (node) =>
    Boolean(
      node && closestAcross(node, ".lf-msg:has(> .lf-msg-body > .lf-msg-editor)"),
    );
  // A modal over the panel, such as the image viewer opened from a rewrite's attachment,
  // is a layer the user steps into from the panel, which hands them back as it closes:
  // standing in it leaves them rewriting, so the view keeps the height it holds for the
  // rewrite behind the modal and on the way back.
  /** @param {Element | null} node */
  const overPanel = (node) =>
    Boolean(node && nativeModalAdmits(node) && !nativeModalAdmits(host));
  onCurrentLocation((node, cause) => {
    const top = trail.value.at(-1);
    if (!top?.thread || cause === "drop" || overPanel(node)) return;
    const view = openView();
    const writing = inRewrite(node) && Boolean(view) && renderedUnder(node, view);
    if (writing === opening.rewriting) return;
    if (writing) {
      opening.rewriting = holdThread(stood);
      if (!opening.rewriting) return;
    } else {
      opening.rewriting = false;
      opening.room = null;
    }
    paint();
  });
  // The menu grows upward from the row, so news that adds a row to it, or takes one
  // away, would carry every row above up or down the window under the reader: a row a
  // revision offers, such as the newer version, or a status re-wrapping the head. So
  // while one opening of it stands it holds what it showed with the first status it said
  // (Connecting… is not yet one). Its rows keep their seats (`menuSeats`): a row news
  // takes off offer stands disabled, and one news offers joins at the next opening.
  // Each part of its head keeps its lines (`menuLines`): a later status re-wraps inside
  // them, ending in an ellipsis where it runs past them. Turning back to the menu shows
  // everything as it is. Rejected: holding the head's height and scrolling what runs
  // past it, which still moves the words a re-wrap carries across its edge.
  function holdMenu() {
    if (opening.menuLines || !showing({ view: "menu" }) || !statusReading())
      return false;
    const state = shownView()?.querySelector(".lf-fp-state");
    if (!state) return false;
    /** @param {string} part */
    const lines = (part) => {
      const line = state.querySelector(`.lf-fp-${part}`);
      return line
        ? Math.round(
            line.getBoundingClientRect().height /
              Number.parseFloat(getComputedStyle(line).lineHeight),
          )
        : 0;
    };
    opening.menuLines = { summary: lines("summary"), explain: lines("explain") };
    return true;
  }
  // A list takes its room as soon as it stands at what it fits: in the paint that
  // first draws it (`paintPanel`), the frame after a refit settles (`refit`), or once
  // Leaf's reader has drawn the messages its cards ask (`present`). Taking it then
  // writes only the height the list already stands at, and before news can arrive:
  // Chromium suspends the view's scroll anchoring for a layout in which the view's
  // `height` changes, even to the height it stands at, so the room written in the paint
  // that adds a row above the rows in sight would move every row in sight by the row's
  // height.
  function holdRoom() {
    const top = trail.value.at(-1);
    if (!top || top.thread || opening.room !== null || refitting) return false;
    if (!opening.drawn) return false;
    const view = shownView();
    if (!view || view.querySelector(".lf-fp-asked:empty")) return false;
    opening.room = view.offsetHeight;
    return true;
  }
  // A tab, filter or search the user presses changes what the list shows, which it
  // then fits, moving as one opening does; each such press repaints. The list takes
  // its room again in the next frame, once it stands at what it now fits.
  let refitting = false;
  // Each row standing Threads draws, by its thread's key, with its section and the
  // change it is placed by (`drawnRows`), and each draft's row by its key
  // (`drawnDrafts`); null while no list stands, so the next paint draws every row where
  // it now belongs (`threadsListing`, `draftsListing`).
  // The keys of the rows a notice's press lands on, while its paint draws them
  // (`showJoined`).
  /** @type {Set<string> | null} */
  let landingKeys = null;
  // The outlet the view's fit watches (`paintNow`).
  /** @type {HTMLElement | null} */
  let fitted = null;
  function refit() {
    opening.room = null;
    opening.drawnRows = null;
    opening.drawnDrafts = null;
    viewMovingUntil = performance.now() + viewResizeMs();
    if (refitting) return;
    refitting = true;
    nextRender(() => {
      refitting = false;
      if (holdRoom()) paint();
    });
  }
  /** @param {PanelRoute | null | undefined} before @param {{focus?: boolean, handedOn?: boolean, part?: "reply" | "thread"}} [options] */
  function transition(before, { focus = true, handedOn = false, part = "reply" } = {}) {
    const after = trail.value.at(-1);
    // The thread the user is in as the change begins, on the page or in the panel,
    // read before the paint that may take its view away.
    const stoodIn = drawnThreadId(closestAcross(focused(), THREAD));
    const reading = [before, after].some((route) => route?.thread);
    if (after?.view !== "queue") seated = null;
    const changed =
      (before ? routeKey(before) : null) !== (after ? routeKey(after) : null);
    if (changed) opening = freshOpening();
    // Taking the panel away from a thread ends the editing session of its reply, as a
    // press elsewhere does (records/thread/replies.js), keeping the draft: the field no longer
    // draws that reply, and a session left standing would carry the user back to it.
    // A thread the page takes from the panel takes the session with it (`handedOn`).
    if (changed && before?.thread && !handedOn)
      dismissReply(threadByKey(before.thread)?.key ?? before.thread);
    // The view going away fades where it stood, closing included, so the box shrinking
    // under it never shows an empty ground.
    leaving = changed && before && after ? before : null;
    if (changed) viewMovingUntil = performance.now() + outMs() + viewResizeMs();
    paint();
    // The reader draws what the view arriving holds, and lets go of what the one
    // leaving held: a thread's messages, or the obligations On shows as messages.
    const drawn =
      reading || (before && viewOf(before).nominate)
        ? present({ release: reading })
        : null;
    if (!changed || !motionPlays()) {
      leaving = null;
      paint();
      if (focus) focusView(after, drawn, stoodIn, part);
      return;
    }
    // A view a send opens rises with the box as the stream does (`streamSend`).
    const arriving = stage.querySelector(".lf-fp-view:not([data-lf-leaving])");
    if (arriving && following.theirs() !== "send")
      playMotion(arriving, [{ opacity: 0 }, { opacity: 1 }], {
        duration: fadeMs(),
        delay: leaving ? outMs() : 0,
        easing: "linear",
      });
    const gone = stage.querySelector(".lf-fp-view[data-lf-leaving]");
    const fade =
      gone &&
      playMotion(gone, [{ opacity: 1 }, { opacity: 0 }], {
        duration: outMs(),
        easing: "linear",
      });
    // The view leaving goes once its fade ends, which is still the gesture's rendering,
    // so the box moving then moves as the user's change (`followBox`).
    if (fade) {
      const release = holdRendering();
      fade.finished.then(() => {
        leaving = null;
        paint();
        release();
      }, release);
    } else leaving = null;
    if (focus) focusView(after, drawn, stoodIn, part);
  }
  /** @param {PanelRoute | undefined} route @param {PromiseLike<unknown> | null} drawn
   * @param {string | null} [stoodIn] @param {"reply" | "thread"} [part] */
  function focusView(route, drawn, stoodIn = null, part = "reply") {
    if (!route) return;
    const view = shownView();
    // A thread opens with the caret in its reply, as the one field means, once Leaf's
    // reader has drawn the reply there, from a list's row by a key as by a press
    // (records/thread/focus.js, `openingPart`, says why a row differs from a card); one taking
    // no reply, as a resolved thread does, holds focus itself, so the user is in it. The
    // thread a send starts lands the user on its view, as a send does (`landSent`). A
    // list stands on the row of the thread the user was in, where it lists it, as `g T`
    // from a thread does; else, opened by a key, in the panel or on the page as `g T`
    // is, on its first row, or its first control where it has none, or itself where it
    // holds neither, as an empty Threads does, so the key's landing wears a ring; opened
    // by a pointer, it holds focus itself. The user chose this over leaving focus on
    // the list's view after `g T` from the page, where nothing shows it and
    // Enter goes nowhere seen. A list that declares a row it opens at, such as the
    // version Versions offers to compare with, brings that row into view by either
    // route, a key lands on it, and Tab enters the list there (`rove`).
    // A fold's heading (`settledHeading`) is a row the arrows reach and never a landing:
    // a list holding only what was put away holds focus itself, with no ring
    // (floating-panel.css, `.lf-fp-view:focus`), and ↓ enters the fold. The user asked
    // for that, since a ring on Resolved, where `r` on the last open thread returns them
    // to Threads, reads as Resolved chosen.
    if (route.thread) {
      // A finger opening a thread reads it first, standing in the view, whose box
      // raises no keyboard; the keyboard rises when they tap in.
      const intent = retainUserIntent();
      void Promise.resolve(drawn).then(() => {
        const at = shownView();
        if (!at || trail.value.at(-1) !== route || !intent()) return;
        if (part === "thread") landSent(at);
        else
          focusDestination(
            (!coarsePointer.matches && viewParts.reply(at)) || at,
            "move",
          );
      });
      return;
    }
    const rows = listRows();
    const stoodRow =
      stoodIn &&
      rows.find((row) => threadByKey(row.getAttribute("data-lf-key"))?.id === stoodIn);
    const declared = viewOf(route).at;
    const at = declared ? view?.querySelector(declared) : null;
    const first =
      rows.find((row) => !row.matches(".lf-fp-settled")) ??
      (rows.length ? null : view?.querySelector("button, input"));
    const target = stoodRow || (pressLed() ? view : (at ?? first ?? view));
    // The row of the thread the user was in takes them back where they came from.
    if (target) focusDestination(target, target === stoodRow ? "return" : "move");
    if (at) scrollIntoView(at, { block: "nearest", within: view });
  }

  // ---------- the leaf's menu ----------
  // A row that opens a list of its own ends in a chevron, past its value, so the user
  // knows before pressing that it leads further rather than acting.
  /** @param {unknown} label @param {unknown} end @param {(event: MouseEvent) => unknown} press
   * @param {{urgent?: boolean, disabled?: boolean, role?: string | null, row?: string | null,
   * key?: string | null, opens?: boolean, title?: string | null, current?: boolean}} [options] */
  const menuItem = (
    label,
    end,
    press,
    {
      urgent = false,
      disabled = false,
      row = null,
      key = null,
      opens = false,
      title = null,
      current = false,
    } = {},
  ) =>
    html`<button
      type="button"
      data-lf-row=${row ?? nothing}
      data-lf-key=${key ?? nothing}
      .lfPreview=${() => (title ? { detail: [title] } : null)}
      ${offeredAction("row", "lf-fp-item")}
      aria-current=${current ? "location" : nothing}
      ?disabled=${disabled}
      ?data-lf-urgent=${urgent}
      ?data-lf-opens=${opens}
      @click=${press}
    >
      <span class="lf-fp-label lf-row-main">${label}</span
      ><span class="lf-fp-end lf-row-end"
        >${end}${opens ? iconTemplate("next", "lf-fp-chevron") : nothing}</span
      >
    </button>`;
  // The row that opens the Errors list, which the menu and its search both offer. It
  // wears the leaf's error dot beside its name while an error waits unseen in the list
  // (`errorsWaiting`), so a press on the dotted leaf finds the dotted row.
  /** @param {readonly import("../transport/errors.js").RaisedError[]} errors @param {boolean} [gone] */
  const errorsRow = (errors, gone = false) =>
    menuItem(
      html`Errors<span
          class="lf-fp-error-dot"
          aria-hidden="true"
          ?data-lf-shown=${errorsWaiting(fieldReading(null, fieldInput()))}
        ></span>`,
      html`<span class="lf-fp-value">${errors.length}</span>`,
      () => {
        open({ view: "errors", errors });
        seeErrors();
      },
      { opens: true, disabled: gone, row: "errors" },
    );
  // A row's end says its value in words, then its shortcut where a keyboard is there to
  // press it, each press a key as the command reference draws it, so the two never read
  // as one run of text.
  /** @param {ReturnType<typeof pageControls>[number]} entry */
  const rowEnd = (entry) =>
    html`${
      entry.value ? html`<span class="lf-fp-value">${entry.value}</span>` : nothing
    }${
      entry.shortcut.length && advertisesKeys()
        ? keySequenceTemplate(keySequenceModel(neutralSteps(entry.shortcut)))
        : nothing
    }`;
  // Copy shortcuts close on success; a refusal opens About's selectable text.
  /** @type {Map<string, ReturnType<typeof copyControl>>} */
  const copyItems = new Map();
  /** @param {ReturnType<typeof pageControls>[number]} entry */
  function copyItem(entry) {
    let copy = copyItems.get(entry.key);
    if (!copy) {
      // The trigger is the row this renders into the control below.
      copy = copyControl("lf-fp-copy-item", {
        success: `${capitalized(entry.label)} copied`,
        error: `${capitalized(entry.label)} not copied · select it to copy`,
        trigger: true,
      });
      copy.addEventListener("wa-copy", () => putAwayThen(() => {}));
      copy.addEventListener("wa-error", () => {
        copyRefused = true;
        putAwayThen(() => {
          const inspection = rows().find((row) => row.key === "inspection");
          if (!inspection?.press)
            throw new Error("Copy recovery requires page inspection");
          inspection.press(null);
        });
      });
      copyItems.set(entry.key, copy);
    }
    copy.value = entry.copies;
    copy.disabled = entry.disabled;
    render(
      menuItem(
        `Copy ${entry.label}`,
        actionTemplate("copy", "lf-fp-copy-icon"),
        () => {},
        {
          disabled: entry.disabled,
          row: entry.key,
          title: entry.title || entry.value || null,
        },
      ),
      copy,
    );
    return copy;
  }
  // A row leading to a list of the panel's own opens that list over the menu, whose way
  // back returns there; any other row runs its command.
  /** @param {ReturnType<typeof pageControls>[number]} entry */
  function rowFor(entry) {
    if (entry.copies) return copyItem(entry);
    const route = OWN_VIEWS.find((route) => route.view === entry.key) ?? null;
    return menuItem(
      entry.label,
      rowEnd(entry),
      () => {
        if (route) open(route);
        else putAwayThen(() => entry.press?.(heldCurrentLocation));
      },
      {
        urgent: Boolean(entry.urgent),
        disabled: entry.disabled,
        row: entry.key,
        opens: Boolean(route && viewOf(route).over?.includes("menu")),
      },
    );
  }
  // The menu: the On view's first tab, the state over its rows, or what its search
  // finds while the field holds words.
  const menuView = () =>
    html`<div class="lf-fp-menu">${query.trim() ? menuFound() : rootTemplate()}</div>`;
  // The menu narrowed to the words its search holds: the lists whose names hold them,
  // then every row it reaches, the rows its lists hold included, then the threads and
  // versions whose names hold the words, and last the command reference opened on them,
  // which searches every command. The reference owns that catalog, so the menu lists
  // only what it already reaches.
  function menuFound() {
    const words = query.trim();
    /** @param {unknown} text */
    const holds = (text) =>
      String(text ?? "")
        .toLocaleLowerCase()
        .includes(words.toLocaleLowerCase());
    const reached = rows().filter(
      (entry) =>
        !entry.exit &&
        (listed(entry) || HELD_ELSEWHERE.includes(entry.key)) &&
        (groupOf(entry) === "page" ||
          GROUPS.some((group) => group.name === groupOf(entry))) &&
        holds(entry.copies ? `Copy ${entry.label}` : entry.label),
    );
    const lists = GROUPS.filter(
      (group) =>
        holds(group.label) &&
        rows().some((entry) => groupOf(entry) === group.name && listed(entry)),
    );
    const errors = holds("Errors") ? errorsReading() : [];
    const named = threads().filter((thread) => holds(threadName(thread)));
    const versions = versionsReading().rows.filter((entry) =>
      holds(`${entry.name} ${entry.note ?? ""}`),
    );
    /** @param {unknown} word */
    const kind = (word) => html`<span class="lf-fp-value">${word}</span>`;
    return html`${errors.length ? errorsRow(errors) : nothing}${lists.map((group) =>
        menuItem(group.label, nothing, () => open({ view: "group", group }), {
          opens: true,
          row: `group:${group.name}`,
        }),
      )}${reached.map(rowFor)}${named.map((thread) =>
        menuItem(threadName(thread), kind("Thread"), () => openRow(thread.key), {
          row: `thread:${thread.key}`,
        }),
      )}${versions.map((entry) =>
        menuItem(
          html`${entry.name}${
            entry.note ? html`<span class="lf-fp-note">${entry.note}</span>` : nothing
          }`,
          kind("Version"),
          () => showVersion(entry),
          { title: entry.note },
        ),
      )}${
        errors.length ||
        reached.length ||
        lists.length ||
        named.length ||
        versions.length
          ? nothing
          : html`<p class="lf-rows-empty">No row, thread or version matches.</p>`
      }
      <hr class="lf-fp-rule" />
      ${menuItem(`Search commands for “${words}”`, nothing, () =>
        putAwayThen(() => findCommands(words, leaf)),
      )}`;
  }
  function rootTemplate() {
    const all = rows();
    // The panel's own views lead, in the order the user reaches for them; the rest of
    // the page's rows follow in their rank's order.
    /** @type {readonly string[]} */
    const lead = OWN_VIEWS.map((route) => route.view);
    const page = all
      .filter((entry) => groupOf(entry) === "page" && listed(entry))
      .sort(
        (a, b) =>
          (lead.includes(a.key) ? lead.indexOf(a.key) : lead.length) -
          (lead.includes(b.key) ? lead.indexOf(b.key) : lead.length),
      );
    const keyboard = all.find((entry) => entry.key === "keyboard");
    const fold = all.find((entry) => entry.key === `command:${FOLD}`);
    const groups = GROUPS.filter((group) =>
      all.some((entry) => groupOf(entry) === group.name && listed(entry)),
    );
    // The state is said once: its one line, and under that only what the status adds to
    // the line (`statusModel`, `adds`), since the menu is reached by pointer, key and
    // finger alike. Each line names the state itself ("Codex away"), so no word for the
    // tone stands over it, and the line takes the ink the row's status does, its tone's
    // only where it asks the user to act (floating-panel.css, `.lf-fp-summary`).
    const { summaryParts, adds, addsParts, publication } = status();
    // A published page's introduction follows, with its links.
    const said = adds ? statusParts(addsParts) : "";
    const explains = publication
      ? html`${said}${adds ? " " : nothing}${voiced(leafSays(publication.copy))}${
            publication.examplesUrl
              ? html`<a href=${publication.examplesUrl}>${publication.examples}</a> `
              : nothing
          }<a href=${publication.installUrl} target="_blank" rel="noopener"
            >${publication.install}</a
          >`
      : said;
    const held = opening.menuLines;
    /** @param {"summary" | "explain"} name @param {unknown} text */
    const part = (name, text) =>
      (held ? held[name] : text)
        ? html`<span
            class="lf-fp-${name}"
            style=${held ? `--lines: ${held[name]}` : nothing}
            >${text}</span
          >`
        : nothing;
    /** @param {ReturnType<typeof pageControls>[number]} entry @returns {MenuSeat} */
    const seat = (entry) => ({
      key: entry.key,
      draw: (gone) => rowFor(gone ? { ...entry, disabled: true } : entry),
    });
    const errors = errorsReading();
    /** @type {MenuSeat[]} */
    const offered = [
      ...(errors.length
        ? [
            {
              key: "errors",
              draw: (/** @type {boolean} */ gone) => errorsRow(errors, gone),
            },
          ]
        : []),
      ...page.map(seat),
      ...groups.map((group) => ({
        key: `group:${group.name}`,
        draw: (/** @type {boolean} */ gone) =>
          menuItem(
            group.label,
            groupValue(group.name)
              ? html`<span class="lf-fp-value">${groupValue(group.name)}</span>`
              : nothing,
            () => open({ view: "group", group }),
            { opens: true, disabled: gone, row: `group:${group.name}` },
          ),
      })),
      { key: "", draw: () => html`<hr class="lf-fp-rule" />` },
      ...(keyboard ? [seat(keyboard)] : []),
      ...(fold ? [seat(fold)] : []),
    ];
    const now = new Map(offered.map((row) => [row.key, row]));
    // Only the menu standing holds its seats; a menu leaving draws what it showed.
    const seats = showing({ view: "menu" }) ? (opening.menuSeats ??= offered) : offered;
    // Keyed by row, so a row the menu gains or loses moves the others rather than
    // redrawing each in its neighbour's place, the copy shortcut's element included.
    return html`<div class="lf-fp-state" ?data-lf-held-lines=${held !== null}>
        ${part("summary", statusParts(summaryParts))}${part("explain", explains)}
      </div>
      ${repeat(
        seats,
        ({ key }) => key,
        ({ key, draw }) => now.get(key)?.draw(false) ?? draw(true),
      )}`;
  }
  /** @param {string} group */
  const groupValue = (group) =>
    group === "annotate"
      ? rows().find((entry) => entry.key === "command:annotations.toggle")?.label ===
        "Show annotations"
        ? "Hidden"
        : ""
      : "";

  /** @param {string} group */
  function groupList(group) {
    return rows()
      .filter((entry) => groupOf(entry) === group && listed(entry))
      .map(rowFor);
  }
  // Where the agent's latest save failed its check, first what the check found, which
  // its error points here to read (features/version.js, `holdFailedSave`); then the versions
  // the picker lists, each a press that travels there and says the note its stamp gave
  // it after its name, cut to the row and whole on hover, or whole under the name for a
  // pointer that can't hover (floating-panel.css). A column at the rows' end
  // holds Compare where the picker offers it and Showing for the version shown, so
  // the two words line up. Showing stands outside the press, as Compare does, over
  // the row's end; the press carries it as `aria-current`. Before its word, Compare
  // says how many changes a comparison with its version would mark, once Versions has
  // counted them, which it does for the presses that show in the window (features/version.js,
  // `changesCounted`, `countWhenShown`), so the counts stand one under another
  // and a press on a count shows those changes. The count's room is held from the
  // start, so a count coming in moves no words beside it. The press's name says the
  // count first, as the press shows it, then "Compare with" the version. Versions opens
  // at the version it offers to compare with (features/version.js, `selection.offered`), else
  // at the version shown, the row marked `data-lf-at`.
  /** @param {ReturnType<typeof versionsReading>["rows"][number]} entry */
  const showVersion = (entry) => putAwayThen(() => versionPicker.activate(entry));
  // The room a count holds: three digits, past which a count is cut.
  const CHANGES_ROOM = "100 changes";
  // Each row of Versions is named by the version it is (`rowKey`), so the row the
  // user stood on comes back as they left it (records/history.js), whichever versions the list
  // has gained since.
  /** @param {ReturnType<typeof versionsReading>["rows"][number]} entry */
  const versionKey = (entry) =>
    `${entry.version === null ? "draft" : "version"}:${entry.revision}`;
  /** @param {ReturnType<typeof versionsReading>["rows"][number]} entry
   * @param {ReturnType<typeof versionsReading>["selection"]} selection */
  function comparePress(entry, selection) {
    const n = changesCounted(entry.revision);
    const said = n === null ? "" : n ? counted(n, "change") : "No changes";
    return html`<button
      type="button"
      data-lf-key=${`compare:${versionKey(entry)}`}
      ${offeredAction("word", "lf-fp-compare")}
      ${countWhenShown(entry.revision)}
      aria-pressed=${String(selection.on && selection.base === entry.revision)}
      aria-label=${[said, `Compare with ${entry.name}`].filter(Boolean).join(", ")}
      @click=${() => putAwayThen(() => versionPicker.compare(entry.version))}
    >
      <span class="lf-fp-changes" data-lf-room=${CHANGES_ROOM}
        ><span>${said}</span></span
      >
      Compare
    </button>`;
  }
  function versionsList() {
    const { rows: versions, picker, selection, latest } = versionsReading();
    /** @param {(typeof versions)[number]} entry */
    const opensAt = (entry) =>
      selection.offered === null
        ? entry.current
        : entry.comparable && entry.revision === selection.offered;
    return html`
      ${
        latest.failed
          ? html`<div class="lf-fp-failed">
              <b>${latest.label}</b>
              <p class="lf-fp-failed-error" data-lf-scroll>${latest.error}</p>
            </div>`
          : nothing
      }
      <div class="lf-fp-versions lf-rows">
        ${repeat(
          versions,
          versionKey,
          (entry) =>
            html`<div
              class="lf-fp-version"
              ?data-lf-current=${entry.current}
              ?data-lf-at=${opensAt(entry)}
            >
              ${menuItem(
                html`${entry.name}${
                  entry.note
                    ? html` <span
                        class="lf-fp-note"
                        .lfPreview=${() => ({ name: entry.note })}
                        >${entry.note}</span
                      >`
                    : nothing
                }`,
                nothing,
                () => showVersion(entry),
                { current: entry.current, key: versionKey(entry) },
              )}${
                entry.current
                  ? html`<span class="lf-fp-showing" aria-hidden="true">Showing</span>`
                  : nothing
              }${entry.comparable ? comparePress(entry, selection) : nothing}
            </div>`,
        )}
      </div>
      ${
        versions.length
          ? nothing
          : html`<p class="lf-rows-empty">Showing ${picker.token}</p>`
      }
    `;
  }

  // What a copied error says, for whoever the user hands it to, a person or an agent:
  // the error, when, on which revision and from which stack it was raised (transport/errors.js),
  // then what About this page copies to say which page, Leaf and agent session the page
  // runs as it is pressed (page-about.js). The page's link stays out, since it grants
  // access to every page on this machine.
  /** @param {import("../transport/errors.js").RaisedError} error */
  const errorReport = (error) =>
    [
      [
        `Leaf error: ${error.message}`,
        `raised: ${new Date(error.at).toISOString()}`,
        ...(error.revision === null ? [] : [`revision: ${error.revision}`]),
        error.stack,
      ].join("\n"),
      ...pageControls()
        .filter((entry) => entry.group === "about" && entry.copies)
        .map((entry) => entry.copies),
    ].join("\n\n");
  // The errors the user has met, newest first, each saying what failed and when, with
  // a press that copies it with its context (`errorReport`), where the browser can copy,
  // and one that dismisses it, whose names carry both, since a list's keys reach only
  // its presses. The list keeps the reading it opened with: new errors wait behind the
  // leaf's dot until reopening. An error whose cause ends
  // clears its words but keeps its space, so the next control stays under the reader.
  // A dismissal removes that space by the user's gesture and leaves them on the next
  // error's press, or on the way back once none is left.
  /** @param {RouteFor<"errors">} route */
  function errorsList({ errors }) {
    const live = new Set(errorsReading().map((error) => error.id));
    if (!errors.length) return html`<p class="lf-rows-empty">No errors.</p>`;
    /** @param {number | null} dismissed */
    const movePast = (dismissed) => {
      const presses = [...stage.querySelectorAll(".lf-fp-error .lf-fp-dismiss")];
      const at = errors.findIndex((error) => error.id === dismissed);
      const after = errors.findIndex(
        (error, index) => index > at && live.has(error.id),
      );
      const before = errors.findLastIndex(
        (error, index) => index < at && live.has(error.id),
      );
      const next = dismissed === null ? null : presses[after >= 0 ? after : before];
      const target = next ?? controls.querySelector(".lf-fp-back");
      if (target) focusDestination(target, "move");
    };
    // An error clearing itself also hands focus off before its control disappears.
    const currentLocation = focused(document)?.closest(".lf-fp-error");
    const currentLocationId = Number(currentLocation?.getAttribute("data-lf-key"));
    if (currentLocation && !live.has(currentLocationId)) movePast(currentLocationId);
    // The user moves on before the list repaints, so its roving stop lands once.
    /** @param {number | null} dismissed */
    const dismiss = (dismissed) => {
      movePast(dismissed);
      trail.value = [
        ...trail.value.slice(0, -1),
        {
          view: "errors",
          errors:
            dismissed === null ? [] : errors.filter((error) => error.id !== dismissed),
        },
      ];
      if (dismissed === null) dismissErrors();
      else dismissError(dismissed);
    };
    return html`${repeat(
      errors,
      (error) => error.id,
      (error) =>
        html`<div
          class="lf-fp-error"
          data-lf-key=${error.id}
          style=${live.has(error.id) ? nothing : "visibility: hidden"}
        >
          <p class="lf-fp-error-words" aria-hidden="true">
            <b>${error.message}</b
            ><span class="lf-fp-note">${timeOfDay(error.at)}</span>
          </p>
          ${
            error.press
              ? html`<button
                  type="button"
                  ${offeredAction("word", "lf-fp-error-press")}
                  ?disabled=${!live.has(error.id) || !error.press.stands()}
                  aria-label=${`${actionName(error.press.action)}: ${error.message}, ${timeOfDay(error.at)}`}
                  @click=${() =>
                    putAwayThen(() => error.press && pressReading(error.press).run())}
                >
                  ${actionName(error.press.action)}
                </button>`
              : nothing
          }
          ${
            canCopy()
              ? guard([error.id], () => {
                  const copy = copyControl("lf-fp-error-copy", {
                    label: `Copy with page details: ${error.message}, ${timeOfDay(error.at)}`,
                    success: "Error copied",
                    error: "Error not copied",
                    role: "symbol",
                  });
                  copy.addEventListener(
                    "click",
                    () => {
                      copy.value = errorReport(error);
                    },
                    { capture: true },
                  );
                  return copy;
                })
              : nothing
          }
          <button
            type="button"
            ${offeredAction("word", "lf-fp-dismiss")}
            ?disabled=${!live.has(error.id)}
            aria-label=${`Dismiss: ${error.message}, ${timeOfDay(error.at)}`}
            @click=${() => dismiss(error.id)}
          >
            Dismiss
          </button>
        </div>`,
    )}${
      errors.length > 1
        ? html`<hr class="lf-fp-rule" />
            ${menuItem("Dismiss all", nothing, () => dismiss(null))}`
        : nothing
    }`;
  }

  // The open threads, then the resolved ones folded under Resolved (`settledHeading`),
  // as what left On Me stands under Done, each unread row marked. The user chose this,
  // with Threads as the On view's tab, over Open, Unread, Drafts and Resolved filters,
  // which a second row of tabs would have to hold. Each group reads newest first
  // (`threadsListing`). A search reads every thread's name, its messages and summaries
  // as they read, and the words it is about, as its head quotes them (`threadPassage`),
  // and lists matches as one list. The threads come in the log's order.
  function shownThreads() {
    const words = query.trim().toLowerCase();
    return words
      ? threads().filter((thread) =>
          [
            threadName(thread),
            anchorLabel(threadPassage(thread), thread.root.about),
            ...thread.msgs.map(messageText),
            ...thread.summaries.map(messageText),
          ]
            .join(" ")
            .toLowerCase()
            .includes(words),
        )
      : threads();
  }
  // A row joining Threads while the list stands, a thread the agent starts, or a row
  // changing section or place, one a reply reopens or moves up, or one resolved
  // elsewhere, would move the rows the user reads there (`browser/AGENTS.md`, "News
  // moves what the reader reads only in the thread they are in"). So the standing list
  // draws each row in the section and the place it drew it in, and a thread new to it
  // not at all, and says what joined or changed section in the notice a
  // thread's held news uses (records/thread/held-news.js, `newsNotice`) until the user
  // presses it, which lets the list settle and lands on the first row it names. The
  // notice stands over the list, in the view's head, which grows the panel upward by
  // its line so no row moves, as a feed says "2 new posts" over its top. The user chose
  // that over the notice in the controls after the tabs, which fill the
  // start where a thread's held news stands and leave it "1 …+1" at a phone's width,
  // and over the notice in the held row's own place, which a long list scrolls out of
  // sight. The browser reads
  // nothing ahead of the server: a held row draws the thread as the server now reads
  // it, in its old place. A row the user's own gesture moves, as their reply, their
  // resolve or its Undo, moves at once (`gesturedOn`), and a press that changes what
  // the list shows, a tab or a search, or the next opening, draws it whole (`refit`,
  // `transition`). A row news moves up within its section stays where it stood until
  // then, and the notice doesn't count it: no row joined or left a section.
  // Rejected: holding only rows that would
  // land among the rows in sight, by their geometry, which a list whose rows change
  // section rather than join would hold none of.
  // The rows the list draws, each in its section with the change it is placed by
  // (`at`), and the threads joining or changing section that it holds: `was` the
  // section a moving row still stands in, null for one the list didn't draw. The rows
  // read newest first, by each thread's last change (`lastChange`), so a resolved row's
  // place agrees with the age it says, as Done's do in On Me. The user chose that over
  // the page's order, the one the `t` walk steps through (records/thread/placement.js),
  // down which Resolved's ages read out of order.
  function threadsListing() {
    const searched = Boolean(query.trim());
    const drawn = opening.drawnRows;
    const rows = [];
    const joined = [];
    for (const thread of shownThreads()) {
      const now = searched ? "found" : thread.resolved ? "resolved" : "open";
      const held = drawn?.get(thread.key);
      const was = drawn ? (held?.section ?? null) : now;
      const acted = gesturedOn(thread);
      const at = held && !acted ? held.at : lastChange(thread);
      if (was === now || acted) rows.push({ thread, section: now, at });
      else {
        joined.push({ thread, was, now });
        if (held) rows.push({ thread, section: held.section, at });
      }
    }
    return { rows: newestFirst(rows, (row) => row.at), joined, searched };
  }
  // After a paint: what the standing list drew, which the next paint holds to.
  function noteDrawnRows() {
    const stands = showing({ view: "threads" }) && inventoried();
    opening.drawnRows = stands
      ? new Map(
          threadsListing().rows.map(({ thread, section, at }) => [
            thread.key,
            { section, at },
          ]),
        )
      : null;
    opening.drawnDrafts = stands
      ? new Set(draftsListing().rows.map(({ key }) => key))
      : null;
  }
  // What the notice says, a fact for each way a row joined.
  /** @param {ReturnType<typeof threadsListing>["joined"]} joined */
  function joinedFacts(joined) {
    /** @param {string} kind @param {string} one @param {string} many */
    const fact = (kind, one, many) => {
      const count = joined.filter(
        ({ was, now }) => (was === null && now !== "found" ? "new" : now) === kind,
      ).length;
      return count ? counted(count, one, many) : null;
    };
    return [
      fact("new", "new thread", "new threads"),
      fact("open", "thread reopened", "threads reopened"),
      fact("resolved", "thread resolved", "threads resolved"),
      fact("found", "new match", "new matches"),
    ].filter((said) => said !== null);
  }
  const joinedNotice = newsNotice();
  // The notice's press: the list settles, and the first row it named, in the list's
  // order, comes into sight with the walk standing on it, and focus too where the
  // notice, the view or a row of its list held it, since the arrows walk from focus
  // there (`inList`). A press from elsewhere, such as a pointer's while the caret is
  // in the field, leaves focus where it is.
  function showJoined() {
    const { joined } = threadsListing();
    const drafts = draftsListing().joined;
    const keys = new Set([
      ...drafts.map(({ key }) => key),
      ...joined.map(({ thread }) => thread.key),
    ]);
    const carried = focused() === joinedNotice.node || inList();
    // Where only resolved threads joined, the row it lands on stands under Resolved,
    // which unfolds to show it (`settledHeading`).
    if (
      !drafts.length &&
      joined.every(({ now }) => now === "resolved") &&
      !unfolded.has("resolved")
    ) {
      unfolded.add("resolved");
      refit();
    }
    opening.drawnRows = null;
    opening.drawnDrafts = null;
    // The paint stands the list's walk on the row it lands on: a rove after it would
    // take back the stop the paint first gave another row, a write that changes nothing.
    landingKeys = keys;
    paint();
    landingKeys = null;
    const row = threadRows().find((candidate) => {
      const key = candidate.getAttribute("data-lf-key");
      return key !== null && keys.has(key);
    });
    if (!row) return null;
    scrollIntoView(row, { block: "nearest" });
    if (carried) focusDestination(row, "move");
    return null;
  }
  // The notice while the list holds a row, else nothing.
  function joinedTemplate() {
    if (!showing({ view: "threads" })) return nothing;
    const { joined } = threadsListing();
    const drafts = draftsListing().joined.length;
    const facts = [
      ...(drafts ? [counted(drafts, "new draft")] : []),
      ...joinedFacts(joined),
    ];
    if (!facts.length) return nothing;
    joinedNotice.set({
      text: newsCount(joined.length + drafts),
      label: facts.join(" · "),
      open: showJoined,
    });
    return html`<span class="lf-fp-joined"
      ><span class="lf-fp-news-outlet">${joinedNotice.node}</span></span
    >`;
  }
  // What left a list stands folded under one heading, its name and count, which the
  // user unfolds, so a page whose conversations have all settled takes one row rather
  // than a row for each. The heading is a row of the list, which the arrows walk to and
  // Enter opens, and a section stays unfolded while the panel stays open (`unfolded`).
  // It is its group's band (controls.css, `.lf-rows-group`, `data-lf-band`), its
  // disclosure arrow hanging in the band's start padding, so its name starts where every
  // band's does. The user chose the fold over resolved threads only searched for, which
  // leaves them nothing to browse, and over the newest three resolved with the rest
  // behind a row.
  /** @param {string} key @param {string} title @param {number} count */
  function settledHeading(key, title, count) {
    const open = unfolded.has(key);
    return html`<h3 class="lf-rows-head">
      <button
        type="button"
        ${offeredAction("row", "lf-fp-settled lf-disclosure-marker")}
        data-lf-band
        aria-expanded=${open ? "true" : "false"}
        @click=${() => {
          if (open) unfolded.delete(key);
          else unfolded.add(key);
          refit();
          paint();
        }}
      >
        <span class="lf-row-main">${title}</span
        ><span class="lf-row-end">${count}</span>
      </button>
    </h3>`;
  }
  // Every message the user has started and not sent stands under Drafts, over the
  // threads, but the page's own, which the field under the list holds. A draft stays
  // with what it is about (records/drafts.js, `draftSubject`), so this is where the user finds
  // one whose box is out of sight, and a press resumes it in that box: its passage's
  // comment box, or its thread's reply or rewrite. A row reads the draft's words, then
  // what it is about, dim, as a menu row's note: the passage or element a comment is
  // on, or the thread a reply or rewrite is in. Its end says what Send makes of it, and
  // its preview reads both whole. The rows read in the page's order, each where the
  // thread it starts or joins stands, and a search reads their subjects and words.
  // The list reads the drafts list (records/drafts.js, `draftsReading`), which repaints it when
  // a draft starts or stops holding words, not per keystroke. While the list stands, a
  // draft that joins it, as one another tab writes or a refusal hands back, waits
  // behind the notice that holds new threads (`joinedTemplate`), and its press draws
  // it. The user asked for Drafts, in place of unsent words
  // following the next Comment to another target, and for its rows to hold still as
  // Threads' do; Drafts as a filter was rejected with the other filters,
  // which a second row of tabs would have to hold.
  function draftsListing() {
    const words = query.trim().toLowerCase();
    const rows = draftsReading().map((draft) => {
      const inThread = draft.part === "reply" || draft.part === "rewrite";
      const thread = inThread ? threadByKey(draft.name) : null;
      const composed =
        draft.part === "comment" && isComposerDraft(draft.payload)
          ? draft.payload
          : null;
      const anchor = draftAnchor(draft);
      return {
        context: draft.context,
        // A row's key among Threads' rows, which hold focus and land a notice's press
        // by it, apart from any thread's.
        key: `draft:${draft.context}`,
        // A reply or rewrite whose thread the log no longer holds, as an undo takes
        // one back, says so in Leaf's voice; a press moves its words to the page.
        gone: inThread && !thread,
        about: thread
          ? threadName(thread)
          : inThread
            ? "Thread gone"
            : anchorLabel(anchor, composed?.about) || "The page",
        kind: draftSends(draft),
        said: draftWords(draft),
        listed: draft,
        place: thread ?? { id: "", anchor },
      };
    });
    const listed = byRenderedOrder(
      words
        ? rows.filter((row) => `${row.about} ${row.said}`.toLowerCase().includes(words))
        : rows,
      (row) => threadPlace(row.place, placedAt),
    );
    const drawn = opening.drawnDrafts;
    return {
      rows: drawn ? listed.filter(({ key }) => drawn.has(key)) : listed,
      joined: drawn ? listed.filter(({ key }) => !drawn.has(key)) : [],
    };
  }
  /** @param {ReturnType<typeof draftsListing>["rows"][number]} draft */
  const draftRow = (draft) =>
    html`<button
      type="button"
      ${offeredAction("row", "lf-fp-draft")}
      data-lf-key=${draft.key}
      data-lf-draft=${draft.context}
      .lfPreview=${() =>
        draftPreview([draft.listed], excerptWords(draft.about, PREVIEWED_LINE))}
      @click=${() => putAwayThen(() => resumeDraft(draft.context))}
    >
      <span class="lf-row-lead"></span>
      <span class="lf-fp-label lf-row-main"
        >${draft.said}
        <span class="lf-fp-note"
          >${draft.gone ? voiced(leafSays(draft.about)) : draft.about}</span
        ></span
      >
      <span class="lf-row-end">${draft.kind}</span>
    </button>`;
  function threadsView() {
    const { rows, searched } = threadsListing();
    const drafts = draftsListing().rows;
    const listed = rows
      .filter(({ section }) => section !== "resolved")
      .map(({ thread }) => thread);
    const resolved = rows
      .filter(({ section }) => section === "resolved")
      .map(({ thread }) => thread);
    // A row previews its thread as the thread's margin entry and mark do
    // (`threadPreview`), leaving out to the keyboard the word its status already says,
    // and a resolved one says when it was resolved (`ageLine`).
    /** @param {ReturnType<typeof readThreads>["threads"][number]} thread */
    const row = (thread) => {
      const attention = threadAttention(thread, agentName());
      const resolved = thread.resolved?.ts;
      return html`<button
        type="button"
        ${offeredAction("row", "lf-fp-thread")}
        data-lf-key=${thread.key}
        ?data-lf-unread=${isNews(thread)}
        ?data-lf-resolved=${thread.resolved}
        data-lf-turn=${attention?.turn === "user" ? "user" : nothing}
        .lfPreview=${(
          /** @type {import("../base/preview-declaration.js").Route} */ route,
        ) => {
          const read = threadPreview(
            [thread],
            route === "focus" && attention ? wordsText(attention.word) : null,
          );
          return read && resolved
            ? { ...read, detail: [...(read.detail ?? []), ageLine(RESOLVED, resolved)] }
            : read;
        }}
        @click=${() => openRow(thread.key)}
      >
        <span class="lf-row-lead"
          ><span class="lf-fp-news-mark lf-unread-dot"
            >${isNews(thread) ? html`<span class="lf-quiet">New</span>` : nothing}</span
          ></span
        >
        <span class="lf-fp-label lf-row-main">${threadHeading(thread)}</span>
        <span class="lf-row-end">${threadStatus(thread)}</span>
      </button>`;
    };
    // Every thread stands in a group, as every item does in On's lists (`groupedItems`).
    // The open ones keep their group's box as a search narrows them to its matches, so
    // the rows stay under the box they stood in.
    // A band counts the threads the page holds in that state now, as the tab does, so
    // it says the same number while the list holds a row in its old section or a new
    // thread behind the notice; a search counts its matches.
    const groups = [
      {
        key: "open",
        title: searched ? "Matches" : "Open",
        items: listed,
        count: searched ? listed.length : threadCounts(threads()).open,
      },
      {
        key: "resolved",
        title: "Resolved",
        items: resolved,
        count: threads().filter((thread) => thread.resolved).length,
        folds: true,
      },
    ].filter((group) => group.items.length);
    return html`<div class="lf-fp-list lf-rows">
      ${bandedGroups(
        drafts.length ? [{ key: "drafts", title: "Drafts", items: drafts }] : [],
        (draft) => draft.context,
        draftRow,
      )}
      ${
        listed.length || (searched && drafts.length) || !inventoried()
          ? nothing
          : html`<p class="lf-rows-empty">
              ${searched ? "Nothing matches." : `${NO_OPEN_THREADS}. Comment below to start one.`}
            </p>`
      }
      ${bandedGroups(groups, (thread) => thread.key, row)}
      ${
        // This tab's sends are listed, but the saved threads are still to come, which
        // the list says after the rows it has, so their arrival moves none of them.
        inventoried()
          ? nothing
          : html`<p class="lf-rows-empty">
              ${
                readThreads().phase === "offline"
                  ? `${THREADS_OFFLINE}.`
                  : "Loading current threads…"
              }
            </p>`
      }
    </div>`;
  }

  // A thread inside the panel is drawn by Leaf's own conversation reader: the panel
  // registers as the page's primary thread presentation (host/application.js,
  // `registerChromeThreadPresentation`), yielding to one the page's package registers, in
  // whose reader its threads then open, and gives the open thread an outlet here. Leaf
  // draws the thread there as a card on the page draws it (records/thread/thread-card.js,
  // `ThreadView`): the words it is about, its to-dos, and its messages, work under way
  // as the dim working message and an ended step nowhere, New in each unread reply's
  // head, with their reactions, rewrites and agent-authored widgets. The user chose
  // that over every message at full size, which stands each progress step as a reply
  // and marks nothing unread. The thread stands its
  // notice of the news it holds back and its Resolve on the view's head line, and its
  // reply box in the field below, where the panel gives them places (`nominateThread`),
  // so the view and a card share one of each. A thread anchored to a passage stays the
  // page's where the page draws it: its card opens beside the words it is about, and the
  // panel shows it only where nothing on the page does (`reveal`), or for a message of
  // it the view shows.
  /** @type {ReturnType<FloatingPanelOptions["registerChromeThreadPresentation"]> | null} */
  let presentation = null;
  // The thread's held news is a fact about the thread, so it reads whole on the view's
  // head line, after the thread's name and before its presses, and pressing it shows
  // what was held. The name gives it the room it takes, so news arriving moves no press
  // and nothing in the messages (floating-panel.css, `.lf-fp-facts`). The user chose a
  // notice among the thread's presses over the notice at the end of the
  // first message's head, cut to 5rem there ("2 new rep…"), and over the news joining
  // New reply at the view's foot. Its Resolve ends the thread's presses, before Close.
  // While the thread holds news, its Resolve and the field's words say the thread as
  // its view draws it, held news included, as a card's do, so the three change together
  // when the user shows the news. Rejected: Resolve and the field saying the thread
  // as it stands, which shows Reopen and "Reply to reopen" beside a notice still
  // holding the agent's Resolve.
  // Each thread's head line draws places of its own for them (`threadPresses`), so the
  // notice of the thread the user leaves goes with them rather than standing in the
  // next one's until the reader draws that.
  const headOutlets = () => {
    /** @type {HTMLElement | null} */
    const news = head.querySelector(".lf-fp-facts > .lf-fp-news-outlet");
    /** @type {HTMLElement | null} */
    const controls = head.querySelector(".lf-fp-aux > .lf-fp-thread-controls");
    /** @type {HTMLElement | null} */
    const unread = head.querySelector(".lf-fp-aux > .lf-fp-unread-outlet");
    return news && controls && unread ? { news, controls, unread } : null;
  };
  // The view standing open, rather than one still leaving.
  /** @returns {HTMLElement | null} */
  const shownView = () => stage.querySelector(".lf-fp-view:not([data-lf-leaving])");
  // The rows of the open view's list, which the arrows walk and Tab stands at one of. A
  // version's Compare is a stop of the walk after its version, so the list stays one
  // stop for Tab; an On card's own controls stay Tab's, inside the card the walk stands on.
  /** @returns {HTMLElement[]} */
  const listRows = () => {
    const top = trail.value.at(-1);
    const rows = top && viewOf(top).rows;
    const view = shownView();
    /** @type {NodeListOf<HTMLElement> | null} */
    const found = rows && view ? view.querySelectorAll(rows) : null;
    return found ? [...found] : [];
  };
  const threadRows = () => (showing({ view: "threads" }) ? listRows() : []);
  // What names a list's row: its item's key, or the route a menu row opens.
  /** @param {HTMLElement} row */
  const rowKey = (row) => row.dataset.lfKey ?? row.dataset.lfRow ?? null;
  /** @returns {HTMLElement | null} */
  const openView = () =>
    stage.querySelector(".lf-fp-view[data-lf-thread-view]:not([data-lf-leaving])");
  const viewContents = () => {
    const view = openView();
    if (!view) return null;
    /** @type {HTMLElement | null} */
    const outlet = view.querySelector(".lf-fp-outlet");
    return outlet ? { view, outlet } : null;
  };
  /** @param {import("../records/thread/primary-reader.js").PrimaryCollection} collection @param {import("../records/thread/primary-reader.js").NominationParts} parts */
  function nominate(collection, parts) {
    const top = trail.value.at(-1);
    if (top) viewOf(top).nominate?.(top, collection, parts);
  }
  // On draws each message its cards ask in, in the card's outlet, aside from the
  // conversation: a thread the page shows keeps the message's widgets (messages.js,
  // `HOLDS`).
  /** @param {import("../records/thread/primary-reader.js").PrimaryCollection} collection @param {import("../records/thread/primary-reader.js").NominationParts} parts */
  function nominateAsked(collection, parts) {
    /** @type {NodeListOf<HTMLElement>} */
    const outlets = stage.querySelectorAll(
      ".lf-fp-view:not([data-lf-leaving]) .lf-fp-asked",
    );
    for (const outlet of outlets) {
      const { lfThread: key, lfMessage: message } = outlet.dataset;
      const thread = collection.threads.find((candidate) => candidate.key === key);
      const asked = thread?.msgs.find((candidate) => candidate.key === message);
      if (thread && asked) parts.message(thread.key, asked.key, outlet);
    }
  }
  /** @param {RouteFor<"thread">} route @param {import("../records/thread/primary-reader.js").PrimaryCollection} collection @param {import("../records/thread/primary-reader.js").NominationParts} parts */
  function nominateThread(route, collection, parts) {
    const contents = viewContents();
    const thread = collection.threads.find(
      (candidate) => candidate.key === route.thread || candidate.id === route.thread,
    );
    if (!contents || !thread) return;
    const { view, outlet } = contents;
    const heads = headOutlets();
    parts.thread(thread.key, outlet, {
      ...(heads ? { head: heads } : {}),
      reply: { outlet: replyOutlet, options: replyOptionsFor(thread.key) },
      // The view stands over the row, away from the words the thread is about, so it
      // quotes them over its messages.
      quote: true,
      scroller: () => view,
      // Resolving moves on to the next thread, and the way back reopens the thread
      // here (records/thread/folding.js); reopening lands in the reply in the field, as the
      // thread's own landing does.
      landing: (resolved) => {
        // Enter on Resolve runs the thread's command before any click, so the press
        // holds the view here as a pointer's does on the head line (`head`).
        if (holdThread(openView()?.getBoundingClientRect().height ?? null)) paint();
        return resolved ? null : resolveLanding(thread.key);
      },
      drawn: threadDrawn(thread, view, outlet),
    });
  }
  // A deliberate view change shows the reader the whole current thread.
  function present({ release = false } = {}) {
    if (!presentation) return Promise.resolve();
    return presentation
      .update({ release })
      .then(() => {
        if (holdRoom()) paint();
      })
      .catch(() => {});
  }

  // A thread's reply and Resolve stand outside its view, in the field and on the view's
  // head line, where the thread draws them (`nominateThread`), so the view declares them
  // as its thread's own (records/thread/selectors.js,
  // `threadPart`): while it is the thread open, the reply box in the field where the
  // thread takes a reply, and Resolve; and the view itself as the thread whole. The
  // head line is the thread's own, as a card's head is, and the field's outlet holds its
  // reply, so both are drawings of the thread too, declaring the same parts: `r` on
  // Resolve there settles the thread as on a card's, `e` there finds the messages in the
  // view above it, and Escape from the reply returns to the view, as a card's reply
  // returns to the card.
  /** @param {Element} view */
  const openIn = (view) => {
    const top = trail.value.at(-1);
    const thread = threadOf(top);
    return thread &&
      !view.hasAttribute("data-lf-leaving") &&
      drawnThreadId(view) === thread.id
      ? thread
      : null;
  };
  /** @type {import("../records/thread/selectors.js").ThreadParts} */
  const viewParts = Object.freeze({
    reply: (view) => {
      return openIn(view) ? replyInput() : null;
    },
    settlement: (view) =>
      openIn(view)
        ? head.querySelector(".lf-fp-thread-controls :is(.lf-resolve, .lf-reopen)")
        : null,
    move: (view) => (openIn(view) ? head.querySelector(".lf-thread-move") : null),
    whole: (view) => (openIn(view) ? openView() : null),
    controls: (view) => (openIn(view) ? head : null),
  });
  /** @param {Element | undefined} view */
  const declareView = (view) => view && declareThreadParts(view, viewParts);
  // Each view scrolls what it holds, so each is a reading region while it stands, and a
  // landing in it, as a rewrite opening on a message above its top, scrolls the view
  // rather than the page its fixed box stands still over (readings/reading-regions.js).
  //
  // A thread's view stands on its foot, beside the field, and keeps what stands there
  // as the room the box gives it changes, read back or not (dom/scrolling.js, `keepFoot`).
  // Where the box reaches the window's top, a line the field gains takes its room from
  // the view rather than carrying the view up, so the view gives way at its top and its
  // words move up with the field, as they do while the box has room. The user asked for
  // this over the view keeping its scroll and giving way at its foot, which lets a long
  // reply cover the agent's last line.
  /** @type {Map<Element, () => void>} */
  const viewRegions = new Map();
  let regionCount = 0;
  function regionViews() {
    for (const [view, stop] of viewRegions)
      if (!view.isConnected) {
        stop();
        viewRegions.delete(view);
      }
    for (const view of /** @type {NodeListOf<HTMLElement>} */ (
      stage.querySelectorAll(".lf-fp-view")
    ))
      if (!viewRegions.has(view)) {
        const stopRegion = registerReadingRegion({
          id: `floating-panel-view-${++regionCount}`,
          host: view,
          body: view,
        });
        const stopFoot = view.hasAttribute("data-lf-thread-view")
          ? keepFoot(view)
          : null;
        viewRegions.set(view, () => {
          stopRegion();
          stopFoot?.();
        });
      }
  }
  declareView(head);
  declareView(replyOutlet);

  /** @param {string} key */
  function threadView(key) {
    // A thread the reading let go of takes its view away before the view draws.
    const thread = threadByKey(key);
    if (!thread) return nothing;
    return html`<div
      class="lf-fp-messages lf-fp-outlet"
      data-lf-reflow="append"
    ></div>`;
  }

  // ---------- On: obligations answered where they are read ----------
  // The lists are the publisher's (`readQueues`): what waits on the user and on the
  // agent, a tab each. The view has no name of its own: its title is the open tab's.
  //
  // On Me holds a card per item standing open, its answers on it, under the groups the
  // `m` walk steps through in the same order (queue-walk.js, `onMeGroups`), with what
  // left the list under Done. A card says what the item is and where it stands, then
  // its question and its answers, Discuss, Undo, and Show, which travels where `m`
  // would. An item answered here keeps its seat, saying its answer, until the view
  // closes. The user chose open cards, so answering what they already
  // know about takes one press each, over one line per item that a press opens, which
  // fits more items and hides every answer behind a press.
  //
  // On <agent> is the agent's work list: in hand, queued and done, a line each with its
  // stage and age. The user chose this over saying how much in the status alone and
  // over a trace of the turn, which needs facts the served state lacks. While the
  // agent has a plan, its goals and steps head the list, and the list under them holds
  // only what no step names, so each item stands once. The plan stands there without
  // a press: behind one, as a disclosure at the view's foot, a returning user saw only
  // its count. A chooser shows the work as this List or as a Summary in sentences: the
  // user chose a menu of layouts for now, to live with several before settling one,
  // against their rule that a layout is not picked from a menu.
  //
  // The opening keeps the item standing open, by its key (`openItem`), and the height
  // each card first stood at, which it keeps while open, so an answer that shortens it
  // moves nothing below (`seatHeights`). The items On Me seats, and what each card
  // carries, stay out of it: a view opened over On clears them, and On Me fading out
  // under that view seats again what still waits on the user, so going back to On
  // keeps those in their seats, one answered in that view included.
  /** @type {"you" | "agent"} */
  let queueTab = "you";
  /** @type {PanelQueueItem[] | null} */
  let seated = null; // On Me's item keys present in the open view
  /** @type {Map<string, readonly string[]>} */
  const carrying = new Map(); // what each card in the open On Me view carries (`also`)
  const QUEUE_TABS = Object.freeze({ you: "user", agent: "agent" });
  const AGENT_LAYOUTS = Object.freeze(["list", "summary"]);
  const agentLayout = userChoice("lf-on-agent-layout", AGENT_LAYOUTS);
  const layoutOf = () => agentLayout.read() ?? "list";
  // Turning to another list seats its items afresh, in a view that fits it.
  /** @param {"you" | "agent"} tab */
  const chooseQueueTab = (tab) => {
    if (tab === queueTab) return false;
    queueTab = tab;
    seated = null;
    opening.openItem = null;
    opening.seatHeights.clear();
    refit();
    fromTop = true;
    return true;
  };
  // A press that changes what the list shows, a tab, a grouping or a layout, shows it
  // from its top, where the plan and the first group stand, rather than where the view
  // stood scrolled in what it showed before, which scroll anchoring would otherwise
  // keep in view.
  let fromTop = false;
  function showFromTop() {
    if (!fromTop) return;
    fromTop = false;
    const view = shownView();
    if (view && trail.value.at(-1)?.view === "queue")
      moveScrollerBy(view, -view.scrollTop);
  }
  // A list's door, as `g M` presses On Me's and `g A` On <agent>'s: the view on that
  // list, turned to it where the view shows the other, else opened or closed. Turning
  // lands the user on the list as opening it does (`focusView`), since the row they
  // stood on went with the other list.
  /** @param {"you" | "agent"} tab */
  function openOnList(tab) {
    const turned = chooseQueueTab(tab);
    if (!turned || !showing({ view: "queue" })) {
      open({ view: "queue" });
      return;
    }
    paint();
    focusView(trail.value.at(-1), null);
  }
  // An On list's empty text (state/queues.js, `emptyOnList`), a sentence but for the
  // ellipsis of one still loading.
  /** @param {string} name */
  const emptyListText = (name) => {
    const words = emptyOnList(readQueues().phase, name);
    return words.endsWith("…") ? words : `${words}.`;
  };
  // Each list as served: On Me's grouped where it is drawn (`onMe.groups`), On
  // <agent>'s strongest workflow first, and Done newest first.
  const queueLists = () => {
    // Page placement determines the list's order, including after a revision
    // removes the element where an obligation stood.
    documentChanged();
    const reading = readQueues();
    if (reading.phase !== "ready") return { you: [], agent: [], done: [] };
    return {
      you: reading.on_user,
      agent: reading.on_agent,
      done: reading.done.filter((item) => item.owner === QUEUE_TABS[queueTab]),
    };
  };

  // The undo list's entry for the gesture that answered an obligation, where it can still be
  // taken back (records/undo.js).
  /** @param {import("../state/semantic-application.js").ObligationRecord} item */
  const answerGesture = (item) => {
    const id = item.answer?.event?.id ?? item.answer?.event;
    if (!id) return null;
    const entry = runtime.undo.find(
      ({ event }) => event.id === id || event.attempt === id,
    );
    return entry?.event ?? null;
  };
  /** @param {string} tab */
  const tabLabel = (tab) => onList(tab === "agent" ? agentName() : "me");
  // The stop the `m` walk stands on while the field says its position
  // (page-keys/status-context.js): its row in On Me wears the ring a focused row
  // wears, and the list brings it into view as the walk reaches it (`landWalked`), so
  // the list follows the walk rather than standing where it was.
  const walkedStop = () => {
    const { walk } = statusContextReading();
    return walk?.kind === "queue" ? walk.target : null;
  };
  /** @type {unknown} */
  let walkedLanded = null;
  function landWalked() {
    const key = showing({ view: "queue" }) ? walkedStop() : null;
    if (key === walkedLanded) return;
    walkedLanded = key;
    const view = shownView();
    const card = key ? view?.querySelector(".lf-fp-on-item[data-lf-walked]") : null;
    if (card) scrollIntoView(card, { block: "nearest", within: view });
  }
  // The stop the walk reached stands at its ringed card while the panel hides it: On Me
  // stays open over the stop it lists (`clearFor`), and a stop at the page's foot can't
  // be scrolled clear of it, so the card is where the user sees where they are, and a
  // key pressed there acts at the stop rather than letting it go (readings/user-place.js,
  // `focusPlace`). A stop in sight is its own place, which a reading keeps still
  // (readings/user-place.js, `holdUserPlace`).
  standsAt("*", (node) =>
    node === focused() &&
    showing({ view: "queue" }) &&
    walkedStop() &&
    !seenRect(node, new Map())
      ? (shownView()?.querySelector(".lf-fp-on-item[data-lf-walked]") ?? null)
      : null,
  );

  // ---------- choosing an arrangement ----------
  // A view's choice among its arrangements, at its foot: a symbol, as Leaf's controls
  // are (browser/AGENTS.md, "Controls are few and quiet"), over the platform's own select, which
  // a key, a pointer and a finger each open on its list of words, the chosen one
  // checked. The select stands unseen over the symbol, so it is what each of them
  // presses; its name and choice are the tooltip. The choice is kept for every page,
  // and the view fits what it then shows. The user chose the symbol over
  // the select showing its chosen word, bordered or not.
  /** @template {string} T @param {{label: string, values: readonly T[], name: (value: T) => string,
   * current: T, choose: (value: T) => unknown}} options */
  const chooser = ({ label, values, name, current, choose }) =>
    html`<span
      class="lf-fp-chooser"
      .lfPreview=${() => ({ name: `${label}: ${name(current)}` })}
      >${actionTemplate("arrange", "lf-action-icon")}<select
        aria-label=${label}
        .value=${live(current)}
        @change=${(/** @type {Event & {currentTarget: HTMLSelectElement}} */ event) => {
          const option = values.find((value) => value === event.currentTarget.value);
          if (option === undefined)
            throw new Error("Panel arrangement selection has no declared option");
          choose(option);
          refit();
          fromTop = true;
          paint();
        }}
      >
        ${values.map(
          (value) =>
            html`<option value=${value} ?selected=${value === current}>
              ${name(value)}
            </option>`,
        )}
      </select></span
    >`;

  // ---------- the plan ----------
  // What each state reads as to assistive tech, which hears no mark.
  // A step's face: where it stands, and for a done one how it ended.
  /** @param {import("../../types/contract.js").ServedPlanStep} step */
  const planFace = (step) =>
    step.state === "done" ? (step.outcome ?? "done") : step.state;
  const PLAN_STATES = Object.freeze({
    waiting: "Not started",
    running: "Under way",
    done: "Done",
    failed: "Failed",
    dropped: "Dropped",
  });
  // A blocked step says why in the word its item says on every other surface.
  /** @param {import("../../types/contract.js").ServedPlanStep} step */
  const planWord = (step) =>
    step.state === "blocked"
      ? todoWord(step).text
      : PLAN_STATES[step.state === "done" ? (step.outcome ?? "done") : step.state];
  const PLAN_MARKS = Object.freeze({
    waiting: null,
    done: "check",
    running: "activity",
    blocked: null,
    failed: "cross",
    dropped: "subtract",
  });
  // How far the plan has come: its goals' steps done, of all of them, counted as each
  // goal counts its own (`plans.py`).
  const planProgress = () => {
    const goals = readPlan()?.steps ?? [];
    return goals.length
      ? {
          done: goals.reduce((sum, goal) => sum + goal.done, 0),
          total: goals.reduce((sum, goal) => sum + goal.total, 0),
        }
      : null;
  };
  /** @param {import("../../types/contract.js").ServedPlanStep} step @returns {ReturnType<typeof html>} */
  function planStep(step) {
    const face = planFace(step);
    const mark = PLAN_MARKS[face];
    return html`<li class="lf-fp-plan-step" data-lf-state=${face}>
      <span class="lf-fp-plan-mark" role="img" aria-label=${planWord(step)}
        >${mark ? iconTemplate(mark, "lf-action-icon") : nothing}</span
      ><span class="lf-fp-plan-title">${step.title ?? ""}</span>${
        step.next_actor === "user"
          ? html`<button
              type="button"
              ${offeredAction("inline", "lf-fp-plan-tag")}
              @click=${() => {
                chooseQueueTab("you");
                paint();
                // The pressed step leaves with the plan, so focus moves to the list
                // it turned to rather than falling to the page.
                const tab = controls.querySelector(
                  '.lf-fp-filters [aria-pressed="true"]',
                );
                if (!tab) throw new Error("On Me has no active tab after selecting it");
                focusDestination(tab, "move");
              }}
            >
              On Me
            </button>`
          : step.state === "running" && step.since
            ? panelAge(step.since, { face: "lf-fp-plan-time" })
            : nothing
      }${
        step.running
          ? html`<span class="lf-fp-running"
              >${voiced(agentSays(step.running.text))}</span
            >`
          : step.detail
            ? html`<span class="lf-fp-plan-detail"
                >${voiced(agentSays(step.detail))}</span
              >`
            : nothing
      }${
        step.steps.length
          ? html`<ol class="lf-fp-plan-steps">
              ${step.steps.map(planStep)}
            </ol>`
          : nothing
      }
    </li>`;
  }
  // Each goal of the plan: a heading over its steps, with how many are done, or a
  // to-do or obligation at the top, drawn as a step is, its own steps under it.
  /** @param {readonly import("../../types/contract.js").ServedPlanStep[]} goals */
  const planCards = (goals) =>
    goals.map((goal) =>
      goal.item
        ? html`<section class="lf-fp-plan">
            <ol class="lf-fp-plan-steps">
              ${planStep(goal)}
            </ol>
          </section>`
        : html`<section class="lf-fp-plan">
            <h3 class="lf-fp-plan-goal">
              <span>${goal.title ?? ""}</span
              ><span class="lf-fp-plan-count">${goal.done} of ${goal.total}</span>
            </h3>
            <ol class="lf-fp-plan-steps">
              ${goal.steps.map(planStep)}
            </ol>
          </section>`,
    );
  // ---------- an item's line, and its card ----------
  // What the agent's list calls an item: a to-do, or the reply or answer it owes.
  /** @typedef {ReturnType<typeof readQueues>["on_user"][number] | ReturnType<typeof readQueues>["done"][number]} PanelQueueItem */
  /** @typedef {keyof ReturnType<typeof queueLists>} PanelQueueList */
  /** @param {PanelQueueItem} item */
  const agentNoun = (item) =>
    item.kind === "todo" ? "To-do" : capitalized(itemNoun(item));
  // What the agent is doing about an item on its list: the word for the stage it
  // stands at, the line its running step wrote while one runs, each said by whoever
  // says it, and since when.
  /** @param {PanelQueueItem} item */
  const workOn = (item) =>
    item.obligation.source.kind === "todo"
      ? {
          word: todoWord(item.obligation),
          line: item.obligation.line ? agentSays(item.obligation.line.text) : null,
          since: item.obligation.line?.ts ?? item.obligation.ts ?? null,
        }
      : {
          word: workflowWord(item.workflow, agentName()),
          line: workflowStep(item.workflow),
          since: item.workflow?.ts ?? null,
        };
  // A press on a line opens its card, or folds it; the view keeps its height where the
  // list allows (`fitOpened`).
  let fitting = false;
  /** @param {string} key */
  function toggleItem(key) {
    if (opening.openItem) opening.seatHeights.delete(opening.openItem);
    opening.openItem = opening.openItem === key ? null : key;
    fitting = true;
    paint();
  }
  // The open item goes when it leaves what the view lists, so nothing stands open that
  // is not drawn.
  /** @param {readonly PanelQueueItem[]} items */
  function forgetOpened(items) {
    if (opening.openItem && !items.some((item) => item.id === opening.openItem))
      opening.openItem = null;
  }
  // Escape folds the open card back to its line, where it leaves the user.
  /** @param {string} key */
  function foldItem(key) {
    toggleItem(key);
    const line = shownView()?.querySelector(
      `.lf-fp-on-item[data-lf-key="${CSS.escape(key)}"] .lf-fp-on-line`,
    );
    if (line) focusDestination(line, "return");
  }
  // A card opening or folding changes the view's height only by what the list makes
  // it: opened, by what the card lacks below the view's foot, and folded, by the room
  // the list then leaves empty. So the pressed line holds still unless the view must
  // grow to show its card, and then rises only by the room the card needs.
  // A card opened as the list refits, as one a promise opens from its thread does
  // (`showTodo`), is fitted once the list holds its room again.
  function fitOpened() {
    if (!fitting) return;
    const view = shownView();
    const listed = trail.value.at(-1)?.view === "queue";
    if (view && listed && opening.room === null) return;
    fitting = false;
    if (!view || !listed || opening.room === null) return;
    const foot =
      view.getBoundingClientRect().bottom -
      Number.parseFloat(getComputedStyle(view).paddingBottom);
    const card = view.querySelector(".lf-fp-on-item[data-lf-open]");
    const end = (card ?? view.lastElementChild)?.getBoundingClientRect().bottom;
    const change =
      end === undefined ? 0 : card ? Math.max(0, end - foot) : Math.min(0, end - foot);
    if (change) {
      opening.room = Math.max(0, opening.room + change);
      viewMovingUntil = performance.now() + viewResizeMs();
      paint();
    }
    if (card) scrollIntoView(card, { block: "nearest", within: view });
  }

  // A card's first part, the line its Show ends (`onItemCard`), then the rest.
  /** @param {readonly unknown[]} parts @param {unknown} show */
  function cardHead(parts, show) {
    const [first, ...rest] = parts.filter((part) => part !== null);
    return html`<div class="lf-fp-on-head">${first}${show}</div>
      ${rest}`;
  }
  // One item: On Me's card standing open (`card`), else a line opened into its card
  // while it is the open item. `says` names what the group's heading already says of
  // it, which the card leaves out where that is its `place`; `leads` whether it is the
  // first item of the walk's stop it stands at, which alone wears the walk's ring.
  // `drawing` collects the ids of the messages this paint's cards have drawn so far,
  // so a later card doesn't draw one again (`nominateAsked`).
  /** @param {PanelQueueItem} item @param {PanelQueueList} list
   * @param {{card?: boolean, says?: "place" | "kind" | null, leads?: boolean,
   * also?: readonly string[] | undefined, drawing?: Set<string>}} [options] */
  function onItemCard(
    item,
    list,
    {
      card = false,
      says = null,
      leads = true,
      also = item.also,
      drawing = new Set(),
    } = {},
  ) {
    const record = carriesObligation(item) ? item.obligation : null;
    const thread = item.thread ? threadByKey(item.thread) : null;
    // A question asked in words is a message in its thread, and reads as that message,
    // drawn whole by Leaf's reader as the thread draws it (`nominate`), images and all:
    // its words cut to text would end at whatever they introduce. The thread names it
    // above, where it has a name of its own rather than the message's opening words.
    // Where the page's package draws its conversations instead, Leaf's reader draws
    // none here, and the message's words stand for it under the thread's name.
    const inWords = record !== null && answeredInWords(record);
    const asking =
      inWords && thread
        ? thread.msgs.find((candidate) => candidate.id === record.message)
        : null;
    // A widget in an agent's message, such as a choice asked in a thread, is in the
    // document only while a drawing of that message holds it (records/thread/messages.js,
    // `HOLDS`). So its card draws the message too, aside from the conversation. Where
    // nothing else shows the message, the widget stands in the card: focused, the card
    // shows the options' digits, and a pick is the same action a pick in the thread
    // records. Where the page shows the message, as a thread open beside its passage
    // does, the widget stays there, and the card answers it with its choices
    // (`choicesOf`), as a page choice's card does. Which drawing holds the widget can
    // change while the card stands, as a margin card opens or closes, so the card draws
    // its choices wherever the widget stands, and they give way to the widget while the
    // card's own drawing of the message holds it (floating-panel.css, `data-lf-holds`).
    // A view draws a message once, so where it holds several such
    // widgets the first card draws it and the others answer through their choices. A
    // line opened into its card keeps the name it has folded.
    const holding =
      record?.source.kind === "widget" && thread
        ? (thread.msgs.find((candidate) => candidate.id === record.message) ?? null)
        : null;
    const key = item.id;
    const opened = opening.openItem === key;
    const reader = presentation?.primary !== false;
    const message =
      asking && thread && reader
        ? { thread, reading: asking }
        : holding && thread && reader && (card || opened) && !drawing.has(holding.id)
          ? { thread, reading: holding }
          : null;
    if (message && (card || opened)) drawing.add(message.reading.id);
    const title =
      message && (asking || card)
        ? (message.thread.title ??
          (message.thread.root.id === message.reading.id
            ? ""
            : threadName(message.thread)))
        : asking && thread
          ? threadName(thread)
          : queueTitle(item);
    const said = message
      ? ""
      : asking
        ? messageReading(asking, { workflows: [] }).body.plainText
        : record?.prompt?.text;
    const prompt = said && said.trim() !== title.trim() ? said : "";
    // The other questions the user answers at this card's place (`also`): further
    // messages its thread's reply answers, and on an obligation's card those asked in a
    // thread about it, so an answer about a decision rides on the decision. Each reads
    // as its message, as a question asked in words does above.
    const carried = (also ?? []).flatMap((id) => {
      const other = readObligations().byId.get(id);
      if (!other) return [];
      const where = other.thread ? threadByKey(other.thread) : null;
      if (!where) return [];
      const asked = where.msgs.find((candidate) => candidate.id === other.message);
      return asked ? [{ record: other, thread: where, message: asked }] : [];
    });
    const conversation = thread ?? carried[0]?.thread ?? null;
    // A carried question still waiting once the card's own is answered.
    const waiting = carried.find(({ record: other }) => other.next_actor === "user");
    // Where the thread's name stands for the item, it reads as Threads names the thread
    // (`threadHeading`).
    const heading =
      thread && title === threadName(thread) ? threadHeading(thread) : title;
    const answered = record && record.state === "done";
    const choices =
      record && !answered && record.source.kind === "widget"
        ? obligationView.choicesOf(record)
        : null;
    const gesture = answered ? answerGesture(record) : null;
    const discuss = conversation
      ? html`<button
          type="button"
          ${offeredAction("word", "lf-fp-discuss")}
          @click=${() => openRow(conversation.key)}
        >
          Discuss
        </button>`
      : nothing;
    // Show takes the user to the item where `m` would, by the walk's own arrival
    // (queue-walk.js, `arriveAtItem`), wherever that leads anywhere but this card. On a
    // card it stands at the end of the card's first line, as a thread's Show on page
    // stands on its head line, beside what it shows and where an answer moves it
    // nowhere; on a line opened into its card, at the end of its answers. The user chose
    // this over the end of a card's answers, where under a long message it
    // stands far from the question it shows. The arrival may open a thread in this
    // panel; keep its current route until the destination decides, then close only for
    // page travel.
    const show = arrivesAt(item)
      ? html`<button
          type="button"
          ${offeredAction("symbol", "lf-fp-show", undefined, { action: "show" })}
          @click=${() => {
            const route = trail.value.at(-1);
            void queueActions.open(item.id).then((arrived) => {
              if (arrived && trail.value.at(-1) === route) close();
            });
          }}
        ></button>`
      : nothing;
    let answers;
    let discussHere = true;
    // A finished item says how it ended and when: on its card, where its answers
    // stood, and on a line at the line's end, so the line's card holds Discuss.
    const ending =
      !record && item.obligation.state === "done" ? itemEnding(item) : null;
    if (ending)
      answers = card
        ? html`<span class="lf-fp-said"
            >${voiced(itemOutcome(item))}${
              ending.ended ? html` ${panelAge(ending.ended, { face: null })}` : nothing
            }</span
          >`
        : nothing;
    // What the agent is doing about it stands on its line, so its card answers nothing
    // more.
    else if (list !== "you" && !answered) answers = nothing;
    else if (answered) {
      discussHere = false;
      answers = html`<span class="lf-fp-said">${voiced(obligationEnding(record))}</span
        >${
          gesture
            ? html`<button
                type="button"
                ${offeredAction("symbol", "", undefined, { action: "undo" })}
                @click=${() => withdraw(gesture)}
              ></button>`
            : nothing
        }${
          waiting
            ? html`<button
                type="button"
                ${offeredAction("word", "lf-fp-reply")}
                @click=${() => openRow(waiting.thread.key)}
              >
                Reply
              </button>`
            : nothing
        }`;
    } else if (choices?.length)
      // A choice that says more than its name, what choosing it gives and whether the
      // page advises it, stands on a line of its own with those words under its name,
      // two lines at most, so the user can answer here without Show, and whole on
      // hover, as a version's note is, and for a finger on the option's own card, where
      // Show goes. The words carry the tooltip rather than the
      // press, whose name already holds them: a title there is read again as its
      // description. Rejected: the option's whole card, whose tags and picture let one
      // choice fill a phone's screen, and its name alone, which left the user picking
      // blind on a phone.
      // The press that commits what the user composed, such as a group's Done, wears
      // the commit face its widget gives it, so it never reads as one more choice, and
      // what it does is its tooltip, as in the command reference.
      answers = html`${choices.map((choice) => {
        const press = () => {
          choice.press();
          paint();
        };
        if (choice.commits)
          return html`<button
            ${offeredAction("commit", "lf-fp-commit")}
            .lfPreview=${() =>
              choice.description ? { detail: [choice.description] } : null}
            aria-pressed=${String(choice.chosen)}
            @click=${press}
          >
            ${capitalized(choice.label)}
          </button>`;
        const told = Boolean(choice.description || choice.recommended);
        return html`<button
          type="button"
          ${offeredAction("answer", "lf-fp-answer")}
          ?data-lf-told=${told}
          aria-pressed=${String(choice.chosen)}
          @click=${press}
        >
          ${
            told
              ? html`<span class="lf-fp-choice-name">${capitalized(choice.label)}</span
                  >${
                    choice.recommended
                      ? html` <span class="lf-fp-choice-tag">recommended</span>`
                      : nothing
                  }${
                    choice.description
                      ? html`<span
                          class="lf-fp-choice-says"
                          .lfPreview=${() => ({ name: choice.description })}
                          >${choice.description}</span
                        >`
                      : nothing
                  }`
              : capitalized(choice.label)
          }
        </button>`;
      })}`;
    else if (inWords && thread) {
      discussHere = false;
      answers = html`<button
        type="button"
        ${offeredAction("word", "lf-fp-reply")}
        @click=${() => openRow(thread.key)}
      >
        Reply
      </button>`;
    } else answers = nothing;
    const stop = queueStop(item);
    // A line of the agent's says what its item is, the reply, answer or to-do it owes.
    // The user's stand as cards, but under Done, where how one ended, such as the answer
    // it took, says what it was.
    const kind = item.owner === "user" ? "" : agentNoun(item);
    const where = says === "place" ? "" : onMe.place(item);
    const walked = leads && queueTab === "you" && walkedStop() === stop.key;
    // On Me's card says only where its item stands over its question, where its band
    // doesn't say it, and keeps that once it is answered, so the answer moves nothing.
    // It names no kind: its question and answers say what it is. The user chose that
    // over a kind word before every card's place, which repeats
    // what the card's answers already say.
    if (card)
      return html`<section
        class="lf-fp-on-item"
        data-lf-card
        data-lf-list=${list}
        data-lf-key=${key}
        data-lf-obligation-id=${record?.id ?? nothing}
        ?data-lf-walked=${walked}
        style=${
          opening.seatHeights.has(key)
            ? `min-height: ${opening.seatHeights.get(key)}px`
            : ""
        }
      >
        ${cardHead(
          [
            where ? html`<p class="lf-fp-on-place lf-rows-head">${where}</p>` : null,
            ...(message
              ? [
                  title ? html`<h3 class="lf-fp-on-title">${heading}</h3>` : null,
                  html`<div
                    class="lf-fp-asked lf-fp-outlet"
                    data-lf-thread=${message.thread.key}
                    data-lf-message=${message.reading.key}
                  ></div>`,
                ]
              : prompt
                ? [
                    html`<h3 class="lf-fp-on-title">${heading}</h3>`,
                    html`<p class="lf-fp-prompt">${prompt}</p>`,
                  ]
                : [html`<p class="lf-fp-prompt">${heading}</p>`]),
          ],
          show,
        )}${carried.map(({ thread: where, message: asked }) =>
          presentation?.primary !== false
            ? html`<div
                class="lf-fp-asked lf-fp-outlet"
                data-lf-carried
                data-lf-thread=${where.key}
                data-lf-message=${asked.key}
              ></div>`
            : html`<p class="lf-fp-prompt">
                ${messageReading(asked, { workflows: [] }).body.plainText}
              </p>`,
        )}
        <div class="lf-fp-answers">${answers}${discussHere ? discuss : nothing}</div>
      </section>`;
    // A line ends with the one thing the list most needs of it: the agent's stage and
    // how long it has stood there, how a finished item ended and when, an answer while
    // its card is folded, else the part of the page it stands in. Under its name, a line
    // of the agent's says what its running step wrote, as the item's thread says it
    // under the message that owes it and the page's status says the newest: one line
    // folded, whole in its card. The user chose this over the name and stage alone,
    // which showed the work only once its card was opened, and with two items running
    // only the newest in the status.
    /** @type {unknown} */
    let end = nothing;
    // The clock time behind the age the line's end shows, which its preview says.
    /** @type {import("../base/preview-declaration.js").Line} */
    let ageSaid = null;
    const work = list === "agent" ? workOn(item) : null;
    if (work) {
      end = html`<span class="lf-fp-value"
        >${voiced(work.word ?? "")}${work.since ? html` ${panelAge(work.since)}` : nothing}</span
      >`;
      if (work.since) ageSaid = ageLine(work.word ?? "", work.since);
    } else if (ending) {
      end = html`<span class="lf-fp-value"
        >${voiced(itemOutcome(item))}${ending.ended ? html` ${panelAge(ending.ended)}` : nothing}</span
      >`;
      if (ending.ended) ageSaid = ageLine(itemOutcome(item), ending.ended);
    } else if (answered && !opened)
      end = html`<span class="lf-fp-value">${voiced(obligationEnding(record))}</span>`;
    else if (where) end = html`<span class="lf-fp-value">${where}</span>`;
    const name = heading || (thread ? threadHeading(thread) : queueTitle(item));
    // An opened line draws a card under it only where the card holds something, such
    // as Discuss. A to-do on the whole page has nothing there, so opening it only shows
    // its running line whole.
    const held = discussHere ? discuss : nothing;
    const carded =
      opened &&
      Boolean(
        message ||
        prompt ||
        answers !== nothing ||
        held !== nothing ||
        show !== nothing,
      );
    return html`<section
      class="lf-fp-on-item"
      data-lf-list=${list}
      data-lf-key=${key}
      data-lf-obligation-id=${record?.id ?? nothing}
      ?data-lf-open=${opened}
      ?data-lf-walked=${walked}
      style=${
        opened && opening.seatHeights.has(key)
          ? `min-height: ${opening.seatHeights.get(key)}px`
          : ""
      }
    >
      <button
        type="button"
        ${offeredAction("row", "lf-fp-item lf-fp-on-line")}
        aria-expanded=${String(opened)}
        ?data-lf-resolved=${!opened && (list === "done" || Boolean(answered))}
        .lfPreview=${() => (ageSaid ? { name, detail: [ageSaid] } : null)}
        @click=${() => toggleItem(key)}
      >
        <span class="lf-fp-value lf-fp-on-noun lf-row-lead">${kind}</span
        ><span class="lf-fp-on-says lf-row-main"
          ><span class="lf-fp-label">${name}</span>${end}</span
        >${
          work?.line
            ? html`<span class="lf-fp-running">${voiced(work.line)}</span>`
            : nothing
        }
      </button>
      ${
        carded
          ? html`<div class="lf-fp-on-body">
              ${
                message
                  ? html`<div
                      class="lf-fp-asked lf-fp-outlet"
                      data-lf-thread=${message.thread.key}
                      data-lf-message=${message.reading.key}
                    ></div>`
                  : prompt
                    ? html`<p class="lf-fp-prompt">${prompt}</p>`
                    : nothing
              }
              <div class="lf-fp-answers">${answers}${held}${show}</div>
            </div>`
          : nothing
      }
    </section>`;
  }
  // Groups of rows, each a box of its own opened by its band: the group's name and how
  // many it counts (`count`, else all of its rows), which sticks while its group passes
  // (controls.css, `.lf-rows-group`, which keeps the record of the design). A group that
  // `folds` stands folded under its band (`settledHeading`). `keyOf` keys a row and
  // `line` draws it, given the group it stands in. Each group is keyed by its own key,
  // its rows keyed inside it. A row that moves to another group, as an item the agent
  // starts or finishes does, is drawn afresh there, and the paint's hold puts focus back
  // on the row carrying its key (`paintNow`, dom/focus.js `holdFocus`).
  /** @template T
   * @template {{key: string | Element, title: string, items: readonly T[], count?: number, folds?: boolean}} G
   * @param {readonly G[]} groups @param {(item: T) => unknown} keyOf @param {(item: T, group: G) => unknown} line */
  function bandedGroups(groups, keyOf, line) {
    return repeat(
      groups,
      (group) => group.key,
      (group) => {
        const count = group.count ?? group.items.length;
        const folded = group.folds && !unfolded.has(String(group.key));
        return html`<section class="lf-rows-group">
          ${
            group.folds
              ? settledHeading(String(group.key), group.title, count)
              : html`<h3 class="lf-rows-head">
                  <span class="lf-row-main">${group.title}</span
                  ><span class="lf-row-end">${count}</span>
                </h3>`
          }${folded ? nothing : repeat(group.items, keyOf, (item) => line(item, group))}
        </section>`;
      },
    );
  }
  /** @template {{key: string | Element, title: string, items: readonly PanelQueueItem[], count?: number, folds?: boolean}} G
   * @param {readonly G[]} groups @param {(item: PanelQueueItem, group: G) => unknown} line */
  function groupedItems(groups, line) {
    return html`<div class="lf-fp-on-list lf-rows">
      ${bandedGroups(groups, (item) => item.id, line)}
    </div>`;
  }

  // A thread's view, its head and its reply stand at what the thread is about, and an On
  // card at the obligation it shows (records/current-target.js, `declareSide`), as the side
  // panel's thread cards and On rows did. So an ask a thread or card in the panel is
  // about wears its ring and takes its digits there, whether the thread is open or
  // resolved. In a thread's view the thread's own keys stay its own, so only `m`, where
  // the thread is not a stop of its own, steps from the ask; from an On card `m`, `t`,
  // `c` and `e` all start at its obligation. An ask in a reply stands for itself. The
  // panel shows them beside the page, so the user in it has not arrived at the ask
  // (`beside`).
  declareSide(
    (node) => {
      const part = [openView(), head, replyOutlet].find((at) => at && under(node, at));
      const thread = part && openIn(part);
      if (thread) return placedAt(thread.id)?.place ?? null;
      const id = under(node, stage)
        ? closestAcross(node, ON_CARD)?.getAttribute("data-lf-obligation-id")
        : null;
      const record = id ? readObligations().byId.get(id) : null;
      return record ? obligationPlace(record).node : null;
    },
    { beside: true },
  );

  function onView() {
    const lists = queueLists();
    return queueTab === "agent" ? workView(lists) : onMeView(lists);
  }
  /** @param {ReturnType<typeof queueLists>} lists */
  function onMeView(lists) {
    const all = [...lists.you, ...lists.agent, ...lists.done];
    const byKey = new Map(all.map((item) => [item.id, item]));
    // The items this opening of the view holds: those it showed, still in the reading
    // wherever they now stand, so an answered one stays, and any that joined the list
    // since. They stand in the walk's groups and order, one joining included, so `m`
    // reaches them down the list; one joining above the card being read moves nothing
    // on screen, since the view's scroll anchoring holds that card where it was.
    // A card carries the records it carried when the view opened or since (`also`)
    // until the view closes, so where answering a decision leaves a thread's answer
    // about it on a row of its own, the answer stays on the card the user pressed,
    // which offers its reply, rather than moving to a card of its own.
    // A record stays on the card that first carried it, though a later reading moves it
    // to another, as a thread about two decisions moves to the second once the first is
    // answered.
    if (seated === null) carrying.clear();
    for (const item of lists.you) {
      const key = item.id;
      const elsewhere = new Set(
        [...carrying].flatMap(([other, ids]) => (other === key ? [] : ids)),
      );
      carrying.set(key, [
        ...new Set([
          ...(carrying.get(key) ?? []),
          ...(item.also ?? []).filter((id) => !elsewhere.has(id)),
        ]),
      ]);
    }
    const carried = new Set(
      (seated ?? []).flatMap((item) => carrying.get(item.id) ?? []),
    );
    const retained = (seated ?? []).flatMap((previous) => {
      const current = byKey.get(previous.id);
      return current ? [current] : [];
    });
    const retainedKeys = new Set(retained.map((item) => item.id));
    const items = [
      ...retained,
      ...lists.you.filter(
        (item) => !retainedKeys.has(item.id) && !carried.has(item.id),
      ),
    ];
    seated = items;
    const seatedKeys = new Set(items.map((item) => item.id));
    /** @type {Set<string>} */
    const drawing = new Set();
    /** @param {PanelQueueItem} item @returns {PanelQueueList} */
    const listOf = (item) =>
      lists.you.some((current) => current === item)
        ? "you"
        : lists.agent.some((current) => current === item)
          ? "agent"
          : "done";
    const grouping = onMe.grouping();
    const says = grouping === "plan" ? null : grouping;
    // A record a card carries is drawn on that card, ended or not, and not in Done too.
    const held = new Set(items.flatMap((item) => carrying.get(item.id) ?? []));
    const finished = lists.done.filter(
      (item) => !seatedKeys.has(item.id) && !held.has(item.id),
    );
    // A group counts what still waits in it; the cards answered here keep their seats,
    // so a group keeps its band while the view stands. Every group has its band, one
    // card alone in it included, so the list has one shape whatever its groups hold: the
    // user chose that with the bands (`groupedItems`), over a heading only for a group
    // of two or more, a card alone saying its group's name over its place. What left
    // the list stands folded under Done, a line each once unfolded, as Threads'
    // Resolved does.
    /** @param {PanelQueueItem} item */
    const waits = (item) => lists.you.some((current) => current === item);
    // Only Done's items stand as lines, which open, and only while it is unfolded.
    forgetOpened(unfolded.has("done:you") ? finished : []);
    const groups = onMe.groups(items, grouping, held).map((group) => ({
      ...group,
      count: group.items.filter(waits).length,
    }));
    // Another grouping draws the list afresh: every card moves, and moving each keyed
    // node in turn would stand some back where they were.
    return html`${
      items.length ? nothing : html`<p class="lf-rows-empty">${emptyListText("me")}</p>`
    }${keyedBy(
      grouping,
      groupedItems(
        [
          ...groups,
          ...(finished.length
            ? [{ key: "done:you", title: "Done", items: finished, folds: true }]
            : []),
        ],
        (item, group) =>
          !("leads" in group)
            ? onItemCard(item, "done", { drawing })
            : onItemCard(item, listOf(item), {
                card: true,
                says,
                leads: group.leads.has(item),
                also: carrying.get(item.id),
                drawing,
              }),
      ),
    )}`;
  }
  // On <agent>: the work as the user chose to see it, a list or a summary. The list's
  // groups are states, not places: what the agent has in hand, what is up next, and
  // what it finished, folded under Done. While the agent has a plan, its goals head
  // the list, which then holds only the items no step names.
  /** @param {ReturnType<typeof queueLists>} lists */
  function workView(lists) {
    /** @param {ReturnType<typeof queueLists>["agent"]} items */
    const held = (items) => items.filter((item) => inHand(item.obligation));
    /** @param {ReturnType<typeof queueLists>["agent"]} items */
    const queued = (items) => items.filter((item) => !inHand(item.obligation));
    if (layoutOf() === "summary") {
      forgetOpened([]);
      return workSummary(held(lists.agent), queued(lists.agent), lists.done);
    }
    const goals = readPlan()?.steps ?? [];
    const named = new Set(goals.flatMap(namedIn));
    const agent = lists.agent.filter((item) => !named.has(item.id));
    const done = lists.done.filter((item) => !named.has(item.id));
    const groups = [
      { key: "in-hand", title: "In hand", items: held(agent) },
      { key: "queued", title: "Up next", items: queued(agent) },
      { key: "done:agent", title: "Done", items: done, folds: true },
    ].filter((group) => group.items.length);
    forgetOpened([...agent, ...(unfolded.has("done:agent") ? done : [])]);
    return html`${planCards(goals)}${
      goals.length || agent.length
        ? nothing
        : html`<p class="lf-rows-empty">${emptyListText(agentName())}</p>`
    }${groupedItems(groups, (item, group) =>
      onItemCard(item, group.folds ? "done" : "agent"),
    )}`;
  }
  // The work said in a few sentences: how much the agent has in hand and for how long,
  // what is queued, what its newest step says, how far the plan has come, and what it
  // finished last. Leaf says them, around the agent's own line and an item's name.
  /** @param {ReturnType<typeof queueLists>["agent"]} inHand @param {ReturnType<typeof queueLists>["agent"]} queued @param {ReturnType<typeof queueLists>["done"]} done */
  function workSummary(inHand, queued, done) {
    const work = inHand.map(workOn);
    const since = work
      .map((each) => each.since)
      .filter(Boolean)
      .toSorted()[0];
    const longest = since && shortAgo(since) !== "now" ? since : null;
    const waiting = queued.length ? `${queued.length} up next` : "";
    const first = inHand.length
      ? html`${voiced(
          leafSays(`Working on ${inHand.length}${longest ? ", the longest for " : ""}`),
        )}${longest ? panelAge(longest, { spoken: true }) : nothing}${voiced(
          leafSays(waiting ? `; ${waiting}.` : "."),
        )}`
      : voiced(
          leafSays(waiting ? `${capitalized(waiting)}.` : "Nothing to do right now."),
        );
    const now = work.find(
      (each) => each.line && each.line.text !== each.word?.text,
    )?.line;
    const progress = planProgress();
    const [last] = done;
    return html`<div class="lf-fp-work-summary">
      <p>${first}${now ? voiced([leafSays(" Now: "), now, leafSays(".")]) : nothing}</p>
      ${
        progress
          ? html`<p>
              ${voiced(leafSays(`Plan: ${progress.done} of ${progress.total} steps.`))}
            </p>`
          : nothing
      }${
        last
          ? html`<p>
              ${voiced([
                leafSays("Last done: "),
                agentSays(excerptWords(queueTitle(last), 60)),
              ])}${
                itemEnding(last).ended
                  ? html`${voiced(leafSays(", "))}${panelAge(/** @type {string} */ (itemEnding(last).ended), { spoken: true, long: true })}`
                  : nothing
              }${voiced(leafSays("."))}
            </p>`
          : nothing
      }
    </div>`;
  }

  // ---------- All pages: the pages live on this machine ----------
  // Each page served on this machine now, this one first (host/live-leaves.js, `leavesRows`):
  // its leaf in its agent's tone, its title, and what its agent is doing, its whole
  // account on hover, or at rest for a pointer that can't hover (floating-panel.css).
  // A row is a link that opens its page in a tab of its own; this
  // page's row says it is this page and goes nowhere, so the walk passes it by.
  function pagesView() {
    const rows = leavesRows(runtime.state);
    if (!rows.length) return html`<p class="lf-rows-empty">No pages are live.</p>`;
    return html`<div class="lf-fp-list">
      ${repeat(
        rows,
        (row) => row.key,
        (row) => {
          const face = html`<span
              class="lf-dot"
              data-lf-tone=${row.tone || nothing}
              aria-hidden="true"
            ></span
            ><span class="lf-fp-label">${row.title}</span
            ><span class="lf-fp-value"
              >${row.self ? "This page" : voiced(row.parts)}</span
            >${
              row.rest
                ? html`<span class="lf-fp-page-rest">${row.rest}</span>`
                : nothing
            }`;
          return row.self
            ? html`<div
                class="lf-fp-page"
                .lfPreview=${() => (row.account ? { name: row.account } : null)}
              >
                ${face}
              </div>`
            : html`<a
                ${offeredAction("row", "lf-fp-page")}
                data-lf-key=${row.key}
                href=${row.href}
                target="_blank"
                rel="noopener"
                .lfPreview=${() => (row.account ? { detail: [row.account] } : null)}
                >${face}</a
              >`;
        },
      )}
    </div>`;
  }

  // ---------- the head and the controls: the view's name, and its presses ----------
  // A tab with a count (`count(name)` a number rather than null) says it even at zero,
  // in a quieter ink, in a room kept for two digits, so news changing the count moves
  // no tab beside it and no tab stands with a blank where its count would go.
  // Rejected: a blank at zero, which reads as a gap after the word, and the word
  // centred in a room wider on both sides, which stood it off centre once it had a
  // count, as On Me nearly always does. An empty gap stands between two tabs, for the
  // strip's gutter track (floating-panel.css, `.lf-fp-filters`). A tab the view doesn't
  // show previews the keys of the Go-to door that opens it (`door`), such as `g A` on
  // On <agent>'s, where they would press it from where the user is, so the user meets
  // the key where they reach for the list. A tab is named for its list alone and
  // described by its count, so a screen reader hears "Threads", then "2", and its
  // preview's keys follow "Threads", not "Threads 2".
  /** @template {string} T @param {readonly T[]} names @param {T} current
   * @param {(name: T) => string} label @param {(name: T) => unknown} choose
   * @param {(name: T) => number | null} count @param {(name: T) => string | null} door */
  const tabs = (names, current, label, choose, count, door) =>
    html`<div class="lf-fp-filters" data-lf-scroll role="group" aria-label="Show">
      ${names.map((name, at) => {
        const counted = count(name);
        const gap = at ? html`<span class="lf-fp-tab-gap"></span>` : nothing;
        const opens = door(name);
        return html`${gap}<button
            type="button"
            ${offeredAction("word", "lf-fp-tab")}
            aria-pressed=${String(current === name)}
            aria-label=${label(name)}
            aria-description=${counted === null ? nothing : String(counted)}
            .lfPreview=${() => {
              const steps = opens && current !== name ? commandBindingsNow(opens) : [];
              return steps.length ? { keys: [steps] } : null;
            }}
            @click=${() => {
              refit();
              choose(name);
            }}
          >
            <span class="lf-fp-tab-words"
              >${label(name)}${
                counted === null
                  ? nothing
                  : html` <span class="lf-fp-count" ?data-lf-zero=${!counted}
                      >${counted}</span
                    >`
              }</span
            >
          </button>`;
      })}
    </div>`;
  // Threads' own search, which its search button and `/` in Threads open: a fresh
  // search the first time, and the one standing, words kept, after that.
  function findThreads() {
    if (!searching) {
      searching = true;
      query = "";
      refit();
      paint();
    }
    focusDestination(threadSearchInput, "move");
  }
  // The view's head line, in two parts. First its name: the way back to the list it
  // opened over, a ‹ alone that names that list as its tooltip; the view's name
  // (`VIEWS`, `title`, `head` and `quiet`), a thread's saying when its title is still on
  // its way (`threadHeading`); and the facts the view states after it. Then the view's
  // presses, ended by its Close where the view has no tabs (`closeAtFoot`). A view's
  // `presses` gives both its facts and its presses.
  /** @param {PanelRoute} top @param {unknown} close */
  const headTemplate = (top, close) => {
    const view = viewOf(top);
    const parent = trail.value.at(-2);
    const { facts = nothing, presses = nothing } = view.presses?.(top) ?? {};
    return html`<div class="lf-fp-name">
        ${
          parent
            ? html`<button
                type="button"
                ${offeredAction("symbol", "lf-fp-back", `Back to ${titleOf(parent)}`, {
                  action: "back",
                })}
                @click=${back}
              ></button>`
            : nothing
        }
        <h2 class=${view.quiet?.(top) ? "lf-fp-title lf-quiet" : "lf-fp-title"}>
          ${(view.head ?? view.title)(top)}
        </h2>
        ${facts}
      </div>
      ${
        presses === nothing && close === nothing
          ? nothing
          : html`<div class="lf-fp-aux">${presses}${close}</div>`
      }`;
  };
  // A view's foot, as its head line is in two parts: its tabs (`VIEWS`, `controls`),
  // then what stands beside them, ended by its Close; a view with none has no foot.
  /** @param {PanelRoute} top @param {unknown} close */
  function controlsTemplate(top, close) {
    const { crumb = nothing, aux = nothing } = viewOf(top).controls?.(top) ?? {};
    return html`<div class="lf-fp-crumb">${crumb}</div>
      <div class="lf-fp-aux">${aux}${close}</div>`;
  }
  // The On view's tabs: the menu, the two lists and Threads, at the controls' start,
  // where every other view's way back stands, since they name the view. The menu and
  // Threads are views of their own, so turning to or from either stands the other view
  // in its place (`onTab`). The user chose the menu as the first tab,
  // over a menu of its own standing over the leaf, which reaches neither list nor
  // Threads; the leaf opens the view on it, or on the list its marks point at.
  const TAB_LABELS = Object.freeze({ menu: "Menu", threads: "Threads" });
  /** @param {"menu" | "you" | "agent" | "threads"} current */
  function onTabs(current) {
    const lists = queueLists();
    // A list is counted once the server's reading is in, as Threads is (`openCount`),
    // so no tab says 0 of a list the page can't read yet or offline.
    const counted = readQueues().phase === "ready";
    return tabs(
      ON_TABS,
      current,
      (tab) => (tab === "menu" || tab === "threads" ? TAB_LABELS[tab] : tabLabel(tab)),
      onTab,
      (tab) =>
        tab === "menu"
          ? null
          : tab === "threads"
            ? openCount()
            : counted
              ? lists[tab].length
              : null,
      (tab) => (tab === "menu" ? null : ON_DOORS[tab]),
    );
  }
  // A tab keeps the user on it, as turning between the lists always has, so the press
  // that stands Threads in the list's place leaves focus on the Threads tab.
  /** @param {"menu" | "you" | "agent" | "threads"} tab */
  function onTab(tab) {
    if (tab === "menu" || tab === "threads") {
      query = "";
      open({ view: tab }, { replace: true, focus: false });
      return;
    }
    const turned = chooseQueueTab(tab);
    if (!showing({ view: "queue" }))
      open({ view: "queue" }, { replace: true, focus: false });
    else if (turned) paint();
  }
  // Threads' tabs and its search.
  function threadsControls() {
    return {
      crumb: onTabs("threads"),
      aux: html`<button
        type="button"
        ${offeredAction("symbol", "", "Find a thread or message", { action: "find" })}
        aria-pressed=${String(searching)}
        @click=${() => {
          if (!searching) {
            findThreads();
            return;
          }
          closeThreadSearch();
        }}
      ></button>`,
    };
  }
  function queueControls() {
    // The view's chooser follows its tabs.
    return {
      crumb: onTabs(queueTab),
      aux:
        queueTab === "you"
          ? chooser({
              label: "Group On Me",
              values: ON_ME_GROUPINGS,
              name: groupingLabel,
              current: onMe.grouping(),
              choose: onMe.choose,
            })
          : chooser({
              label: `Show On ${agentName()} as`,
              values: AGENT_LAYOUTS,
              name: capitalized,
              current: layoutOf(),
              choose: agentLayout.write,
            }),
    };
  }
  // A thread's parts of its head line: the place of its held news after its name, and
  // its presses, between the places of Next unread and its Resolve, which the thread
  // draws in all of them.
  /** @param {RouteFor<"thread">} route */
  function threadPresses(route) {
    const thread = threadOf(route);
    if (!thread) return {};
    // Resolve, and Reopen in its place, is the thread's own, which it draws in the place
    // last on the line, before Close (`nominateThread`), as a card's head draws it.
    // A thread about an element an agent sent in a message stands in that message
    // (annotations/anchor-placement.js), so its way there is Show in message, which opens the
    // message's thread here on that element (records/thread/destination.js,
    // `openThreadSubject`).
    const inMessage = Boolean(placedAt(thread.id)?.message);
    // A thread the destinations handed the panel as their last resort, whose place the
    // page draws nowhere, has no page to show (records/thread/destination.js, `showsOnPage`).
    // One the page shows only the place of, as a window with no room for the rail does,
    // goes there.
    opening.onPageSeat ||=
      Boolean(thread.anchor) && (inMessage || showsOnPage(thread.key));
    // Next unread stands first, in a place of its own the thread draws it in.
    const presses = html`${keyedBy(
      thread.key,
      html`<span class="lf-fp-unread-outlet"></span>`,
    )}${
      opening.onPageSeat
        ? html`<button
            type="button"
            ${
              inMessage
                ? offeredAction("symbol", "lf-fp-on-page", "Show in message", {
                    action: "show",
                  })
                : // The press that moves the thread to Leaf's other place for it
                  // (`lf-thread-move`, records/thread/selectors.js), which `p` presses.
                  offeredAction("symbol", "lf-fp-on-page lf-thread-move", undefined, {
                    action: "show-on-page",
                  })
            }
            .lfPreview=${() =>
              !inMessage && wouldChoose(false)
                ? { detail: [`${BESIDE_PASSAGES} from now on`] }
                : null}
            data-lf-carry="show"
            ?disabled=${!thread.anchor}
            ?data-lf-unoffered=${!thread.anchor}
            @click=${() => {
              if (inMessage)
                void openThreadSubject(thread.id, { intent: retainUserIntent() });
              else showOnPage(thread.key);
            }}
          ></button>`
        : nothing
    }${keyedBy(thread.key, html`<span class="lf-fp-thread-controls"></span>`)}`;
    return {
      facts: html`<span class="lf-fp-facts"
        >${keyedBy(thread.key, html`<span class="lf-fp-news-outlet"></span>`)}</span
      >`,
      presses,
    };
  }

  // ---------- paint ----------
  /** @param {Parameters<ReturnType<typeof prefs>["setRest"]>[0]} rest */
  function setRest(rest) {
    const before = trail.value.at(-1);
    // Folding takes away whatever the user was on in the panel but the leaf, so it
    // keeps them on the leaf it folds to; from the page they stay where they are.
    const inside = currentLocationIn(host);
    prefs().setRest(rest);
    trail.value = [];
    transition(before, { focus: false });
    if (inside) focusDestination(leaf, "return");
  }

  // A paint can blur what it removes, and the blur asks for a paint; that one runs
  // once this has finished rather than inside it. Every paint runs through the panel's
  // Lit host, so the readings it draws repaint it whichever input
  // asked for the paint.
  let painting = false;
  let again = false;
  function paint() {
    if (painting) again = true;
    else {
      host.requestUpdate();
      host.performUpdate();
    }
  }
  function paintPanel() {
    draws += 1;
    painting = true;
    try {
      // A thread's view draws a thread of the reading. One the reading no longer holds,
      // as a refused send's or an undone comment's, leaves it nothing to draw, so it goes
      // with its thread, as a card does (margin-projection.js), whoever opened it.
      const top = trail.value.at(-1);
      if (top?.thread && !threadOf(top)) close();
      paintNow();
      if (holdRoom()) paintNow();
      if (holdMenu()) paintNow();
    } finally {
      painting = false;
    }
    if (again) {
      again = false;
      paintPanel();
      return;
    }
    seatOnItems();
    fitOpened();
    showFromTop();
    landWalked();
  }
  // A card's seat is the height it first stands at once its message is drawn; a card
  // whose message Leaf's reader has not drawn yet asks it to (`nominate`), once, and
  // releases what the reader holds back, since a thread it holds as news would leave the
  // card standing without its question (records/thread/held-news.js).
  const asked = new WeakSet();
  function seatOnItems() {
    if (!showing({ view: "queue" })) return;
    let draw = false;
    /** @type {NodeListOf<HTMLElement>} */
    const cards = stage.querySelectorAll(
      ".lf-fp-view:not([data-lf-leaving]) .lf-fp-on-item:is([data-lf-card], [data-lf-open])",
    );
    for (const card of cards) {
      const outlet = card.querySelector(".lf-fp-asked:empty");
      if (outlet) {
        draw ||= !asked.has(outlet);
        asked.add(outlet);
      } else {
        const key = card.getAttribute("data-lf-key");
        if (key === null) throw new Error("On Me card has no item key");
        if (!opening.seatHeights.has(key))
          opening.seatHeights.set(key, card.getBoundingClientRect().height);
      }
    }
    // The drawing grows the card after it was fitted, so it is fitted again once the
    // drawing lands (`fitOpened`).
    if (draw)
      void present({ release: true }).then(() => {
        fitting = true;
        paint();
      });
  }
  // Drawing a thread completes only the navigation intent it began with, in the opening
  // and outlet it drew. The thread reads its own news and its own answer.
  /** @param {ReturnType<typeof readThreads>["threads"][number]} thread @param {HTMLElement} view @param {HTMLElement} outlet
   * @returns {() => void} */
  function threadDrawn(thread, view, outlet) {
    const intent = landing;
    const drawing = opening;
    return () => {
      if (opening !== drawing || outlet !== viewContents()?.outlet) return;
      if (intent && landing === intent && thread.key === intent.key) {
        landing = null;
        if (intent.end) scrollToEnd(view);
        else if (intent.reading) showReading(view, intent.reading);
        else if (intent.shown) {
          const before = intent.shown;
          const shown = [...outlet.querySelectorAll(".lf-msg[data-lf-message]")].find(
            (message) =>
              !before.has(/** @type {HTMLElement} */ (message).dataset.lfMessage ?? ""),
          );
          if (shown) scrollIntoView(shown, { block: "nearest", within: view });
        } else {
          const transcript = outlet.querySelector(".lf-thread-transcript");
          if (!transcript)
            throw new Error("Thread draw completed without its transcript");
          showReturnTurn(transcript, thread);
        }
      }
    };
  }
  function paintNow() {
    const top = trail.value.at(-1) ?? null;
    const drawing = opening;
    const search = activeSearch();
    const folded = prefs().rest === "mark" && !top && !search;
    keeps(host, "data-lf-search", searchModeOf(search) || null);
    keeps(host, "data-lf-rest", folded ? "mark" : "row");
    keeps(host, "data-lf-open", top ? top.view : null);
    // Capture native focus before Lit commits the next view and editor.
    const heldView = shownView();
    const focusHold = heldView
      ? { view: heldView, restore: holdFocus(heldView, { key: "data-lf-key" }) }
      : null;
    const replying = Boolean(top?.thread);
    const leavesReply = !replying && editorSeat.contains(replyOutlet);
    const hadEditorFocus = currentLocationIn(editorSeat);
    const heading = threadOf(top)?.id ?? null;
    keeps(replyOutlet, "data-lf-thread", heading);
    keeps(replyOutlet, "data-lf-thread-view", heading === null ? null : "");
    if (pageSearch) keepsHidden(pageSearch.input, !pageSearch.open);
    const input = fieldInput();
    if (input) syncInput(input);
    // The row's posture, which a row's press holds (`rowPress`).
    /** @param {string} name @param {string | null} value */
    const posture = (name, value) => {
      if (!rowPress) keeps(host, name, value);
    };
    const caretLands = caretToField && !replying && !search;
    const words = Boolean(draftOf(input));
    drafted = words;
    drawnWriting = writesIn(input);
    if (!words) expanded = false;
    markRoom();
    keeps(host, "data-lf-expanded", expanded ? "" : null);
    const reading = fieldReading(top?.thread ?? null, input);
    // Only the page field competes with the seated annotation composer. An open
    // view already keeps that seat out, regardless of what its reply field says.
    posture("data-lf-offers", !top && !search && reading.offers ? "" : null);
    keeps(host, "data-lf-tone", status().tone || null);
    keeps(host, "data-lf-asks", status().asks ? "" : null);
    // Each moment the leaf answers has a beat of its own (transport/notifications.js), so it plays
    // once per moment, a press repeating the words standing included, however often the
    // field leaves those words and returns; of several in one task, the latest.
    const { moment, beat } = gestureReading();
    const gestures = beat !== answered ? moment : null;
    answered = beat;

    render(panelTemplate(), host);
    noteDrawnRows();
    if (gestures) gestureLeaf(gestures);

    // Geometry, native focus and reading regions consume the committed tree.
    for (const copy of copyItems.values()) if (!copy.isConnected) copy.remove();
    if (focusHold && focusHold.view === shownView())
      focusHold.restore?.(focusHold.view);
    drawing.drawn = true;
    regionViews();
    const contents = viewContents();
    const outlet = contents?.outlet ?? null;
    if (outlet !== fitted) {
      fit.disconnect();
      if (contents)
        for (const box of [contents.outlet, contents.view]) fit.observe(box);
      fitted = outlet;
    }
    const listed = listRows();
    const declaredAt = top ? viewOf(top).at : undefined;
    // A notice's landing outranks the focused row, so its paint stands the walk on the
    // landing in one write; `showJoined` then moves focus there where it stood in the
    // list or on the notice.
    rove(
      listed,
      listed.find((row) => {
        const key = row.dataset.lfKey;
        return key !== undefined && landingKeys?.has(key);
      }) ??
        listed.find((row) => row === focused()) ??
        listed.find((row) => row.getAttribute("tabindex") === "0") ??
        (declaredAt ? listed.find((row) => row.matches(declaredAt)) : undefined) ??
        listed[0],
    );
    if (leavesReply && hadEditorFocus && !search) focusDestination(leaf, "return");
    if (caretLands) {
      caretToField = false;
      focusDestination(pageEditor().input, "move");
    }
  }

  // ---------- the field's presses ----------
  // A notice's press, or the page's own (`pagePress`), stands at the field's end as
  // `pressReading` reads it. The user chose that the right side of
  // the box is for shortcuts, so a notice's press stands there with its key, in the
  // face Comment and c wear, over the notice's own line with an inked Undo over the
  // field's start, the one press in the row in a face of its own.
  // The way out of the stance the user is in, as the field's end offers it while the
  // stance stands, on the page and in a thread (field-readings.js, `still`): Close, a
  // press that ends the stance at once, as the ✕ beside its name does
  // (page-keys/touch-controls.js), with `esc`, the key that leaves it. It stands only
  // while Escape takes the stance off now, as the dispatcher reads it
  // (`escapeInvocation`): its step is the stance's exit, or one titled as that exit, the
  // ladder's step for the stance. Where something stands over the stance, such as a
  // thread opened inside it or a widget's comment box in Design mode, Escape closes that
  // first, so Close leaves the end. A finger, shown no keys, has the ✕ as its way out,
  // so Close stands only where the page shows keys. It asks the dispatcher whether a
  // stance stands now (`innermostStance`), as `fieldExit` does.
  /** @returns {import("../records/composition-input.js").BoxPress | null} */
  function stanceClose() {
    const held = innermostStance();
    const exit = held ? rows().find((entry) => entry.exit) : null;
    if (!held || !exit || !advertisesKeys()) return null;
    return {
      word: actionName("close"),
      // Read at each ask, as a notice's press's key is (`pressReading`).
      get keys() {
        const escape = escapeInvocation();
        const ends =
          escape !== null &&
          (escape.row === held.exit || rowTitle(escape.row) === rowTitle(held.exit));
        return ends ? [spell("Escape")] : [];
      },
      run: () => exit.press?.(null),
    };
  }
  // Open latest, which the field's end offers while the page shows an older version
  // than the latest, as its words say first (`standing`), when no other press is
  // offered there (`pagePress`). Its verb and its keys say it acts, as every other
  // press at the field's end says its key: "Latest" alone, in the dim face every word
  // at the field's end wears, read as a status. It names Versions' own `l`
  // (`latestRow`), which opens the live page as the press does, where a version's digit
  // there opens that version pinned. The menu's row that opens the latest offers it too.
  /** @type {FieldPress} */
  const OPEN_LATEST = {
    action: "open-latest",
    command: latestRow.id,
    // The press puts nothing away: a revision installed under an open thread hands
    // back the reply being written there (features/version.js, `restoreEditingContinuity`).
    run: () => versionPicker.latest(),
  };
  const latestOffered = () => latestRow.when?.() ?? false;

  // ---------- gestures ----------
  // The leaf unfolds a folded panel, and otherwise opens the On view on the tab its
  // marks point at (`leafOpens`), or puts the view away where it stands, a view it leads
  // to included. `o` presses it (`LEAF`), so on a folded panel `o` unfolds it as a
  // click or Enter on the leaf does; Go-to's doors open their view over the fold. A key
  // lands on the tab's first row, as every
  // key that opens a list does (`focusView`), so ← and → go on to the other tabs from
  // there, and ↑ or `/` reaches the menu's search. A mouse's press on the menu puts
  // the caret in its search, so the words the user types narrow it; a finger reads the
  // menu first, as it reads a thread before the keyboard rises (`focusView`).
  function pressLeaf() {
    if (host.dataset.lfRest === "mark") {
      prefs().setRest("row");
      paint();
      return;
    }
    if (onViewStands()) {
      putAway();
      return;
    }
    const opens = leafOpens(
      fieldReading(trail.value.at(-1)?.thread ?? null, fieldInput()),
    );
    query = "";
    if (opens === "you") openOnList("you");
    else if (opens === "threads") {
      refit();
      open({ view: "threads" });
    } else {
      open({ view: "menu" });
      if (pressLed() && !coarsePointer.matches)
        focusDestination(threadSearchInput, "move");
    }
  }
  // What the leaf's marks count: what waits on the user, the threads with news, and the
  // drafts put away. Drafts are marked only where nothing has news, so the dot stays
  // news's mark, and only while the user isn't writing in the field, or the panel is
  // folded, so writing never reads them.
  /** @param {boolean} folded */
  function leafCounts(folded) {
    const news = newCount();
    return {
      onUser: onUserCount(),
      news,
      kept: news || (!folded && (writesIn(fieldInput()) || drafted)) ? 0 : keptDrafts(),
    };
  }
  // The tab a press on the leaf opens the On view on, read from what its marks say: the
  // menu while an error waits unseen in its Errors list, so the dotted leaf opens to the
  // dotted row; else On Me while anything waits on the user; else Threads while a thread
  // holds a reply they have not read or a draft they put away; else the menu.
  /** @param {ReturnType<typeof fieldReading> | null} reading @returns {keyof typeof LEAF_PRESSES} */
  function leafOpens(reading) {
    if (errorsWaiting(reading)) return "menu";
    if (onUserCount()) return "you";
    return newCount() || keptDrafts() ? "threads" : "menu";
  }
  // Folded, the leaf's peek carries passing notices, since there is no field to show
  // them. The leaf's preview names what pressing it does (annotations/preview.js), and folded, says
  // the page's status under that, which the row and the menu already show unfolded; the
  // words keep still while they show, even as the live status ages.
  function peekPresentation() {
    const held = heldWords.value;
    const notice = passing();
    const telling = (held || notice) && host.dataset.lfRest === "mark";
    return {
      content: !telling
        ? nothing
        : held
          ? heldParts(held)
          : voiced(noticeWords(notice ?? "")),
      shown: Boolean(telling),
    };
  }
  // The leaf's label carries the status's summary for a screen reader, which its
  // preview says in full, so the preview names the leaf in fewer words. A passing
  // notice standing in the folded leaf's peek is all it says.
  function leafPreview() {
    const top = trail.value.at(-1) ?? null;
    const { onUser, news, kept } = leafCounts(host.dataset.lfRest === "mark");
    const counts = leafMarks(onUser, news, kept);
    if (host.dataset.lfRest !== "mark")
      return {
        name: LEAF_PRESSES[leafOpens(fieldReading(top?.thread ?? null, fieldInput()))],
        detail: counts ? [counts] : [],
      };
    if (passing()) return false;
    const fold = commandSteps(FOLD);
    return {
      name: "Unfold Leaf",
      keys: fold.length ? [fold] : [],
      detail: [counts, pagePresented() && statusParts(status().explanationParts)],
    };
  }
  // What stands open above the row, the menu as any view, is a step of the page's Escape,
  // taken wherever focus has fallen once the field has been left
  // (`panel.floating.leave`); with nothing open, the page's own foot of the ladder takes
  // the user from the panel back onto the page.
  pageRung("floating panel", () => {
    // The field's search, the menu's or Threads', clears its words first; then, empty,
    // the menu's closes the menu and Threads' returns to Threads, as a find box returns
    // to its panel (dom/keyboard/AGENTS.md, "Escape").
    if (focused()?.matches(".lf-fp-search"))
      return query
        ? {
            root: host,
            title: "clear search",
            out: () => {
              query = "";
              refit();
              paint();
            },
          }
        : menuSearching()
          ? {
              root: host,
              title: "close menu",
              out: () => {
                close();
                focusDestination(leaf, "return");
              },
            }
          : {
              root: host,
              title: "close search",
              out: closeThreadSearch,
            };
    const top = trail.value.at(-1);
    if (!top) return null;
    // A stance entered over this view came after it, so its own step comes first
    // (`openedIn`).
    const stance = innermostStance();
    if (stance && !openedIn.get(top)?.has(stance.scope)) return null;
    if (trail.value.at(-2)?.view === "menu")
      return { root: host, title: "back to menu", out: back };
    if (top.view === "menu")
      return {
        root: host,
        title: "close menu",
        out: () => {
          close();
          focusDestination(leaf, "return");
        },
      };
    // An On item standing open folds back to its line before the view goes, where the
    // user is in the panel; from the page, where `m` took them, Escape puts the view
    // away as it always has.
    const openItem = opening.openItem;
    if (trail.value.at(-1)?.view === "queue" && currentLocationIn(host) && openItem)
      return { root: host, title: "fold item", out: () => foldItem(openItem) };
    return {
      root: host,
      title: `close ${titleOf(top).toLowerCase()}`,
      // Putting a view away returns the user to the page, where the view's thread or
      // list took them from.
      out: () => {
        close();
        letGo();
      },
    };
  });
  // A view's list, the menu, Threads, On, Versions or a group, is one list the arrows,
  // Home and End walk, from the view itself too, which a pointer opening it stands on: ↓
  // there enters its first row. Only from a row or the view, so the arrows on an On
  // card's own controls, or in a thread's messages, keep their meaning there. With
  // nothing open the panel declares no Escape of its own: the page's foot of the ladder
  // takes the user from the chrome back onto the page (page-keys/page.js), and a step
  // declared over the whole panel would claim Escape on its every control, where the
  // Go-to sequence refuses to arm.
  const inList = () => {
    const at = focused();
    const rows = listRows();
    return rows.length > 0 && (at === shownView() || rows.some((row) => row === at));
  };
  // The On view's tab it shows, or null where the view standing is no tab of it, as a
  // thread or Versions is.
  const shownTab = () => {
    const top = trail.value.at(-1)?.view;
    return top === "queue"
      ? queueTab
      : top === "menu" || top === "threads"
        ? top
        : null;
  };
  /** @returns {HTMLElement | null} */
  const tabOn = () => focused()?.closest(".lf-fp-tab") ?? null;
  // Whether the user stands where ← and → turn the On view's tabs: on a tab, or where
  // ↑ and ↓ walk its rows, a list that holds none included.
  const atTabs = () =>
    shownTab() !== null &&
    (Boolean(tabOn()) || inList() || (focused() !== null && focused() === shownView()));
  // ← and → turn the On view to the tab beside the one it shows, round from either
  // end as a tab strip's walk comes round (`cycledRow`), while ↑ and ↓ walk its rows,
  // so its lists stand on a grid the arrows cross. From the list the user lands on the
  // new tab's list as a key opening it lands (`focusView`); from the tab strip, on the
  // new tab, as a press on a tab keeps them (`onTab`), stepping from the tab they stand
  // on, which Tab may have moved off the one shown. The arrows on a card's own controls
  // keep their meaning there, as with the rows' walk.
  /** @param {string} binding */
  function turnTab(binding) {
    const strip = tabOn();
    const stripTabs = [...controls.querySelectorAll(".lf-fp-tab")];
    const from = strip ? ON_TABS[stripTabs.indexOf(strip)] : shownTab();
    if (!from) return;
    const back = binding === rowArrows(strip ?? host)[0];
    const to = cycledRow(ON_TABS, from, back ? -1 : 1);
    if (to === undefined) return;
    if (to === "menu" || to === "threads") query = "";
    onTab(to);
    if (!strip) {
      focusView(trail.value.at(-1), null);
      return;
    }
    const pressed = controls.querySelector('.lf-fp-tab[aria-pressed="true"]');
    if (pressed) focusDestination(pressed, "move");
  }
  keys(host, "In the floating panel", [
    ...rowWalk({
      id: "panel.floating.rows",
      noun: "Row",
      plural: "rows of the open view",
      rows: listRows,
      // A list names its rows' places to a screen reader itself; the walk shows no
      // position over it.
      position: () => null,
      landed: (row) => rove(listRows(), row),
    }).map((row) => ({ ...row, when: inList })),
    {
      id: "panel.floating.tabs",
      keys: ["ArrowLeft", "ArrowRight"],
      title: "move through the tabs",
      description: () => `Menu, On Me, On ${agentName()} and Threads`,
      travels: true,
      when: atTabs,
      runKey: turnTab,
    },
  ]);
  keys(
    stage,
    "In the menu",
    [
      {
        id: "panel.floating.menu.search",
        keys: ["ArrowUp"],
        title: "back to the search",
        touch: false,
        travels: true,
        run: () => focusDestination(threadSearchInput, "move"),
      },
    ],
    () => menuSearching() && focused() === listRows()[0],
  );
  // The menu's search box, as the page's find box does, takes Enter to press what it
  // found first and ↓ to the rows, on the exact input, ahead of the text field's own
  // claim on those keys (dom/keyboard/dispatch.js).
  keys(
    threadSearchInput,
    "In the menu's search",
    [
      {
        id: "panel.floating.menu.first",
        keys: ["Enter"],
        title: "press the first row found",
        touch: false,
        when: () => query.trim() !== "" && listRows().length > 0,
        run: () => listRows()[0]?.click(),
      },
      {
        id: "panel.floating.menu.rows",
        keys: ["ArrowDown"],
        title: "to the rows",
        touch: false,
        travels: true,
        when: () => listRows().length > 0,
        run: () => {
          const first = listRows()[0];
          if (first) focusDestination(first, "move");
        },
      },
    ],
    () => menuSearching(),
  );
  // A key the page has acts on the view standing open where the view has that act of
  // its own (`VIEWS`, `keys` and `claims`), as d and u already page the view the user is
  // in (navigation.js): `/` in the menu or Threads searches it rather than the page's
  // words, and a number in Versions shows that version. Rooted at the view and its
  // controls together, so the filters find too; the search box's own `/` is a
  // character. An element holds one declaration (dom/keyboard/scopes.js), so every view's
  // keys are this one, each standing while its view does.
  const versionsShown = () => showing({ view: "versions" });
  const shownViewDef = () => {
    const top = trail.value.at(-1);
    return top ? viewOf(top) : null;
  };
  const numbered = () =>
    versionsReading()
      .rows.flatMap((entry) =>
        entry.version !== null && entry.version <= 9
          ? [{ entry, version: entry.version }]
          : [],
      )
      .toSorted((a, b) => a.version - b.version);
  keys(
    opened,
    "In the floating panel",
    Object.values(VIEWS).flatMap((view) =>
      (view.keys ?? []).map((row) => ({
        ...row,
        when: () => shownViewDef() === view && (row.when?.() ?? true),
      })),
    ),
    {
      when: () => Boolean(shownViewDef()?.keys),
      claims: (binding) => shownViewDef()?.claims?.(binding) ?? false,
    },
  );
  // The caret in the field is the innermost thing open, so while a view is open
  // Escape leaves the field first and leaves the rest standing, the draft included
  // (dom/keyboard/AGENTS.md, "Escape"), and the next Escape puts the view away. A reply
  // returns to its thread, the view, by the reply box's own way back (records/thread/landing.js,
  // `text.leave`); the page's field returns to the leaf beside it. The step is the
  // field's alone, so the leaf and the chips keep Escape for the page's ladder.
  keys(editorSeat, "In the comment field", [
    {
      id: "panel.floating.leave",
      keys: ["Escape"],
      description: "The view above stays open",
      title: "leave field",
      when: () => trail.value.length > 0,
      run: () => focusDestination(leaf, "return"),
    },
  ]);
  // Folding to the leaf is the page's command, so it has a key and a row in the menu. A
  // listener hears the panel go, or come back, which nothing else says to them.
  const foldPanel = () => {
    const folding = prefs().rest !== "mark";
    setRest(folding ? "mark" : "row");
    announce(folding ? "Folded to the leaf" : "Unfolded");
  };
  pageCommand({
    id: FOLD,
    keys: ["."],
    title: () => (prefs().rest === "mark" ? "unfold" : "fold"),
    touch: () => (prefs().rest === "mark" ? "Unfold the panel" : "Fold to the leaf"),
    menu: "page",
    run: foldPanel,
  });
  // The leaf's press by key, `o` for On. The leaf is its control, so the key presses
  // the leaf (`pressLeaf`), the leaf's preview names the key, and the leaf is the
  // finger's route. The user asked for keys that reach On Me and On <agent> and move
  // through them: this one opens the On view where the leaf points, ← and → turn its
  // tabs (`turnTab`), and Go-to's `g M` and `g A` open each list by name.
  pageCommand({
    id: LEAF,
    keys: ["o"],
    title: () =>
      onViewStands()
        ? "close"
        : LEAF_PRESSES[
            leafOpens(fieldReading(trail.value.at(-1)?.thread ?? null, fieldInput()))
          ],
    description: "Press the leaf: the list its marks point at, or the menu",
    control: leaf,
    touch: false,
  });
  // Where the reader stood before stepping into the panel, which a row's command that
  // acts on that place gets back (records/history.js, `readPlace`).
  /** @type {ReturnType<typeof readPlace> | null} */
  let heldCurrentLocation = null;
  // It is still where they are on the page while they stand in the panel.
  holdPagePlace(() => (currentLocationIn(host) ? heldCurrentLocation : null));
  // A press reads it before the press moves focus, which may put away what held it, and
  // the focus that press moves, a finger's included, which lands only after its release,
  // keeps it (dom/focus.js, `pressing`).
  const fromThePage = pressRecords();
  host.addEventListener(
    "pointerdown",
    (event) => {
      if (currentLocationIn(host)) return;
      heldCurrentLocation = readPlace();
      fromThePage.keep(event, true);
    },
    true,
  );
  // What the field says turns on whether the user writes in it (`writesIn`), so the row
  // draws again as that changes, and as the user moves within the panel.
  onCurrentLocation((node, _cause, left) => {
    const inside = Boolean(node) && renderedUnder(node, host);
    // Stepping in from the page holds where the user was, and from nowhere holds no
    // place. A row the panel just took away, as a pressed menu row hands the user to the
    // leaf, is no longer under the panel but came from it, and holds nothing.
    if (inside && !left && !fromThePage.kept()) heldCurrentLocation = null;
    else if (inside && left?.isConnected && !renderedUnder(left, host))
      heldCurrentLocation = readPlace(left);
    if (!inside && writesIn(fieldInput()) === drawnWriting) return;
    paint();
  });
  // A press away from the panel puts away what stands open above the row (dom/focus.js,
  // `onPressAway`). A press in a modal over the panel is not on the page (`overPanel`).
  onPressAway(
    (path) => trail.value.length > 0 && !path.includes(host) && nativeModalAdmits(host),
    () => close(),
  );
  // Travel to a place on the page (features/anchor-travel.js, `arrive`) shows it, so the view
  // open above the row gives way where it would stand over any of that place once
  // landed (`landed`, readings/landing-scroll.js `landedBox`), as it gives way to a press on the
  // page: a long thread's view covers most of the window, and a place at the page's
  // foot can't be scrolled above even a short one. Back reopens a thread whose view the
  // landing put away, which the entry it returns to names (records/thread/address.js), and
  // Forward, to the entry naming none, puts it away again. On Me stays where it lists the item travel lands on (`onMe.lists`), since its
  // card shows that item, ringed where the `m` walk reached it (`walkedStop`); a thread
  // On Me doesn't list, as `t` reaches, has no card there. A Tab onto a page stop the
  // view would stand over clears it the same way, since the ring the user follows would
  // stand under it. Whether the panel stands over the place at all is its cover's
  // answer, by the rule every reading of what the user sees takes (dom/geometry.js,
  // `covered`), so a place in the top layer or the panel's own is never under it; the
  // view gives way only where it is the part that does, and the row stays either way.
  // A route that opens a thread here and takes the page to its passage leaves the user
  // in the view (records/thread/destination.js, `taken`), so travel that moves no one to the
  // passage of the thread the view shows leaves the view standing (`ownPassage`).
  /** @param {Element | Range} where @param {DOMRect | null} landed */
  const standsOver = (where, landed) => {
    const holder = placeHolder(where);
    const box = landed ?? placeBox(where);
    return Boolean(
      trail.value.length &&
      holder &&
      covered(box, holder) &&
      overlaps(box, opened.getBoundingClientRect()),
    );
  };
  // Whether `where` stands in the place of the thread the view shows.
  /** @param {Element | Range} where */
  const ownPassage = (where) => {
    const thread = threadOf(trail.value.at(-1));
    const place = thread ? placedAt(thread.id)?.place : null;
    const holder = placeHolder(where);
    return Boolean(place && holder && (holder === place || under(holder, place)));
  };
  /** @param {Element | null} node */
  const onMeHolds = (node) => doors.queue.shows() && onMe.lists(node);
  /** @param {Pick<import("../dom/arrival-plan.js").Arrival, "where" | "focus">} destination
   * @param {DOMRect | null} landed */
  function clearFor({ where, focus }, landed) {
    if (!focus && ownPassage(where)) return;
    if (focus !== false && onMeHolds(focus ? focusElement(focus) : placeHolder(where)))
      return;
    if (standsOver(where, landed)) close();
  }
  // Focus that lands where the panel alone would hide it, once its landing has taken it
  // as far as its regions scroll, leaves the user unable to see where they are, and the
  // next key would let go of it (page-keys/controller.js, `letsGo`): a Tab onto an
  // action at the foot of a workspace that fills the window, an arrow onto a tab low in
  // a stuck side list, or a press on a label whose control stands there. The page keeps
  // no band at the window's foot for the row, as the user chose, so the panel gives way
  // there: the view closes where it stands over the place (above), and where the row
  // would still hide all of it, the panel folds to the leaf as `.` folds it. It stays
  // folded until the user unfolds it or asks to write (`clearRow`). "All of it" is cut
  // by the rule every reading of what the user sees takes (dom/geometry.js, `uncovered`),
  // which gives the row every column of a place it reaches into, so a control mostly
  // beside the row folds it too, as the let-go would otherwise read it out of sight.
  // On Me stays open over an item it lists, as travel leaves it, since its card rings
  // the stop the walk reached (`standsAt`), and a place the user is held at elsewhere
  // folds nothing. The panel asks once the script that moved focus has run, of the node
  // focus then holds, so a script that passes focus through a place on its way
  // elsewhere folds nothing. Rejected: a fold that comes back once focus leaves the
  // place, which would need a second way of resting beside the one `.` keeps, and would
  // carry the row back over the page between two Tabs.
  /** @type {Element | null} */
  let reached = null;
  function giveWay() {
    const node = reached;
    reached = null;
    if (!node || node !== focused() || prefs().rest === "mark") return;
    if (onMeHolds(node) || focusPlace()) return;
    if (!hiddenByCovers(node, landedBox(node))) return;
    setRest("mark");
    announce("Folded to the leaf");
  }
  onCurrentLocation((node, cause) => {
    if (!node || cause === "drop" || renderedUnder(node, host)) return;
    if (cause === "return") clearFor({ where: node, focus: node }, landedBox(node));
    else if (cause === "step" && standsOver(node, landedBox(node))) close();
    reached = node;
    afterScript(giveWay);
  });

  // The doors to the panel's views and to Versions, as Go-to's named destinations
  // (page-keys/go-to-sequence.js) and version travel (`g V`, features/version.js) press them:
  // each opens what it names, or puts it away where it already stands, so the press
  // that opened it closes it. The On Me and On <agent> doors turn the On view to their
  // list where it shows another tab (`openOnList`), and the Threads door to Threads.
  // `shows` says whether the press would put its view away, and `name` what a door
  // with no fixed name opens. `scope` is what the press enters, for the command that
  // presses it to name (`opens`, dom/keyboard/bindings.js): the view's own keys, standing
  // while `shows` says so.
  function putVersionsAway() {
    const inside = currentLocationIn(host);
    close();
    if (inside) focusDestination(leaf, "return");
  }
  /** @param {{keys?: readonly import("../dom/keyboard/bindings.js").Command[]}} view @param {() => boolean} shows */
  const doorScope = (view, shows) =>
    Object.freeze({ rows: view.keys ?? [], at: shows });
  const threadsShown = () => showing({ view: "threads" });
  const onMeShown = () => showing({ view: "queue" }) && queueTab === "you";
  const agentShown = () => showing({ view: "queue" }) && queueTab === "agent";
  const leavesShown = () => showing({ view: "leaves" });
  const doors = Object.freeze({
    threads: {
      shows: threadsShown,
      press: () => {
        query = "";
        refit();
        open({ view: "threads" });
      },
      scope: doorScope(VIEWS.threads, threadsShown),
    },
    queue: {
      shows: onMeShown,
      press: () => openOnList("you"),
      scope: doorScope(VIEWS.queue, onMeShown),
    },
    agent: {
      name: () => tabLabel("agent"),
      shows: agentShown,
      press: () => openOnList("agent"),
      scope: doorScope(VIEWS.queue, agentShown),
    },
    leaves: {
      shows: leavesShown,
      press: () => open({ view: "leaves" }),
      scope: doorScope(VIEWS.leaves, leavesShown),
    },
    versions: {
      shows: versionsShown,
      press: () => (versionsShown() ? putVersionsAway() : open({ view: "versions" })),
      scope: doorScope(VIEWS.versions, versionsShown),
    },
  });

  // A live sample's host showing its child's threads in the panel (host/sample.js, the
  // `thread` command): the thread it names, else Threads. A host's view never takes the
  // child's focus, nor the field from the child's user: a view that would stand another
  // editor in the field (a thread's reply for the page's comment, or back) is declined
  // while the caret stands in the field or its editor holds words, since the caret never
  // passes between editors and the words would leave the screen under no key or press
  // of the user's.
  /** @param {{thread?: string | null}} options */
  function showForSample({ thread }) {
    const wanted = thread ? threadByKey(thread) : null;
    if (thread && !wanted) return Promise.resolve(false);
    const top = trail.value.at(-1);
    const shown = threadOf(top)?.key;
    if (
      (wanted?.key ?? null) !== (shown ?? null) &&
      (currentLocationIn(field) || draftOf(fieldInput()).trim())
    )
      return Promise.resolve(false);
    if (wanted) {
      open({ view: "thread", thread: wanted.key }, { reopen: true, focus: false });
    } else {
      query = "";
      refit();
      open({ view: "threads" }, { reopen: true, focus: false });
      paint();
    }
    return present({ release: true }).then(() => true);
  }

  // A margin card's Open in panel hands its thread here, where a long thread reads
  // wider than in the card's room beside the column (thread-preview.js). It chooses
  // this panel for the threads after it, offering this thread's Show on page back, and
  // opens the thread by the route every opening takes (records/thread/destination.js), which
  // the choice now puts here.
  /** @param {string} id */
  function openThread(id) {
    const thread = threadByKey(id);
    if (!thread) return;
    const { key } = thread;
    chooseThreadsInPanel(true, () => showOnPage(key));
    void threadActions.open(key, {
      part: openingPart({ moved: key }),
      travel: false,
      intent: retainUserIntent(),
    });
  }
  // A thread's Show on page. On a window wide enough for cards it chooses them for the
  // threads after this one too, which its preview says, offering this thread's Open in
  // panel back, and the route then opens this one in its card; on a narrower one it
  // leaves the choice as it stood.
  /** @param {string} key */
  function showOnPage(key) {
    const thread = threadByKey(key);
    if (!thread) return;
    chooseThreadsInPanel(false, () => openThread(key));
    // The words come into view in the press's own task, so a widget hiding them, as a
    // diff's file filter does, gives them up to this press rather than after the
    // route's awaits (dom/widget-elements.js, `reveal`).
    const intent = retainUserIntent();
    const place = placedAt(thread.id)?.place;
    if (place) reveal(place, intent);
    // The route reads where the user is before anything moves, so Back returns to this
    // view, then draws the thread on the page and has this view put away, handing the
    // reply box the field drew to the page's drawing. Where the page draws no view of
    // the thread, as a window with no room for the rail does, it lands on the thread's
    // place (records/thread/destination.js, `reader: "page"`) and the view goes once it has,
    // keeping its reply's words as a close does. A route that lands nowhere leaves the
    // view where the user was.
    void threadActions
      .open(key, { part: openingPart({ moved: key }), intent, reader: "page" })
      .then((landed) => {
        if (!landed || !intent()) return;
        if (threadOf(trail.value.at(-1))?.key === key) close();
      });
  }

  // A promise's word in a message's head hands its to-do here (records/thread/messages.js):
  // On <agent> opens at the to-do's row with its card open, which says what the agent
  // is doing about it and where it stands among the rest. The keys land on the row's
  // line, as `g M` lands on a list's first row; a pointer leaves focus on the view
  // (`focusView`), and the card stands in view either way (`fitOpened`). Only the List
  // layout draws rows, so the press turns a Summary to it, as its chooser would, and
  // the chooser turns it back.
  /** @param {string} todo */
  function showTodo(todo) {
    chooseQueueTab("agent");
    if (layoutOf() !== "list") {
      agentLayout.write("list");
      refit();
    }
    if (!showing({ view: "queue" })) open({ view: "queue" }, { focus: false });
    opening.openItem = todo;
    fitting = true;
    paint();
    const view = shownView();
    const line = view?.querySelector(
      `.lf-fp-on-item[data-lf-key="${CSS.escape(todo)}"] .lf-fp-on-line`,
    );
    if (view) focusDestination(pressLed() || !line ? view : line, "move");
  }

  // A live revision carries the thread open here, and where its view was read to,
  // across it (features/version.js, `captureRetainedCurrentLocation`): the reader is still at
  // it, so the view comes back as they left it, with the user in it where they were,
  // and with the reply's own editing continuity handing back the field. A revision
  // installed in place keeps the view, which still shows the thread, so its restore
  // changes nothing. A view opened by the user's next visit does not come back
  // (state/restore-state.js); this is not that.
  function captureCurrentLocation() {
    const at = focused();
    const top = trail.value.at(-1);
    const view = openView();
    if (!top?.thread || !view) return null;
    const inView = [view, head].some(
      (part) => at && at !== document.body && renderedUnder(at, part),
    );
    // Where the user is in the thread, on its view, a message or its head line, whose
    // Resolve and Show on page stand for the view, as history names it (records/carry.js,
    // `focusKey`); the field's reply is its editing continuity's.
    const focus = inView ? focusKey(at) : null;
    return {
      thread: threadByKey(top.thread)?.key ?? top.thread,
      reading: readingIn(view),
      focus: focus?.on === "reply" ? null : focus,
    };
  }
  // The view opens again through the thread's route, which keeps one thread open
  // (records/thread/destination.js), so a card a walk opened since closes. The route has this
  // panel open the view in the task that asks (`reveal`), so the landing set after it
  // is the one the view's drawing lands at, and the user goes back to what they were on
  // in it once it is drawn.
  /** @param {ReturnType<typeof captureCurrentLocation>} currentLocation */
  async function restoreCurrentLocation(currentLocation) {
    const thread = currentLocation && threadByKey(currentLocation.thread);
    if (!thread) return false;
    const { reading, focus } = currentLocation;
    const intent = retainUserIntent();
    const returnFocus = () => {
      const view = openView();
      if (focus && view)
        focusByKey(
          focus,
          () => view,
          (target) => intent() && !currentLocationIn(target),
        );
    };
    if (trail.value.at(-1)?.thread === thread.key && openView()) {
      returnFocus();
      return true;
    }
    const opened = threadActions.open(thread.key, {
      reader: "primary",
      part: "thread",
      focus: false,
      travel: false,
      scroll: false,
    });
    landing = { key: thread.key, end: false, ...(reading && { reading }) };
    const shown = Boolean(await opened);
    if (shown) returnFocus();
    return shown;
  }

  // The page's comment box in this chrome, as `c` and Resume writing find it
  // (annotations/composing/surface.js, `commentDestination`), and the selected words a press on it
  // comments on (`offer`, `selectedWords`).
  const pageComment = Object.freeze({
    get box() {
      return pageEditor().input;
    },
    open: writeOnPage,
    close: () => {},
    sync: () => pageEditor().sync(),
    /** @param {SelectedWords | null} passage */
    offer(passage) {
      const moved = passage?.quote !== selectedWords?.quote;
      selectedWords = passage;
      if (moved) paint();
    },
  });

  /** @param {Element} parent */
  function mount(parent) {
    host.draw = paintPanel;
    parent.append(ground, host);
    follow.observe(card);
    // The window changed size, which the box's motion takes as it stands
    // (dom/box-motion.js). An export mounts no panel, so its root states no band.
    addEventListener("resize", followBox);
    presentation = registerChromeThreadPresentation(host, {
      render: nominate,
      // The view makes room for the agent's answer to the user's last turn itself
      // (the growth under **Opened**), so the reader hands it over at once.
      answersAtOnce: true,
      // The view's only message parts are On Me's cards, which stand aside from
      // the conversation (messages.js, `HOLDS`).
      messagesAside: true,
      // A reader the page's package registers later takes the thread open here, and
      // the user's place in it where they were in the panel, read before the panel's
      // reader, and the message they were on, goes. The thread moves where the user
      // stands, which is no step of theirs (records/history.js).
      yielded: () => {
        const top = trail.value.at(-1);
        if (!top?.thread) return null;
        const focus = currentLocationIn(host);
        const message = focus
          ? (closestAcross(focused(), ".lf-msg")?.getAttribute("data-lf-message") ??
            null)
          : null;
        const key = top.thread;
        return () => openInPackage(key, { focus, message, travel: false });
      },
      // A thread about the whole page opens here, and so does one about a passage once
      // the user has chosen the panel for threads (records/thread/threads-in-panel.js; the rule
      // is records/thread/destination.js's), even where a widget's seat draws it on the page
      // too. Under the cards choice one about a passage opens beside it, where the page draws it, widgets in its messages included, and here
      // only where nothing on the page shows it, as on a page drawing no margin or a
      // window with no room for the rail, the destination's last resort
      // (`request.last`), or for one of its messages
      // while the view already shows it, so a walk to an ask in it leaves the user
      // where they read. A route to the page alone, as Show on page is, has the view go
      // under either choice once the page shows the thread (`request.page`). Where the user lands in it is the route's (`request.part`),
      // which Leaf's destinations take them to once it is drawn: the reply, a message,
      // or the thread itself, the view, where the `t` walk goes on from.
      /** @type {import("../records/thread/destination.js").OpenPrimary} */
      reveal: (key, { part, last, page }) => {
        const thread = threadByKey(key);
        if (!thread) return false;
        const top = trail.value.at(-1);
        const shown = threadOf(top)?.key === thread.key;
        const declines = page || !threadsInPanel();
        if (thread.anchor && declines && !(part === "message" && shown)) {
          if (!last) {
            // The page draws it, so a thread's view here goes, its own or another's, as
            // Show on page puts it away: the thread shows once, and the one the user
            // arrived at is the one thread open, which the field's reply and a walk's
            // position then name. The panel closes rather than going back to a list
            // the view stood over, since the user has gone on to the page. Where the
            // page takes the thread this view shows, the reply being written in it goes
            // along, the row itself, to the page's view of the thread, or to wait for
            // it to open (records/thread/replies.js, `releaseReplies`), so the user goes on
            // writing there.
            if (shown) releaseReplies(replyOutlet);
            if (top?.thread) close({ handedOn: shown });
            return false;
          }
        }
        open({ view: "thread", thread: thread.key }, { reopen: true, focus: false });
        // The band the view takes is stated once it is drawn, before the box's size
        // delivery, so the route's landing of the thread's passage, which may follow in
        // the same task, stands clear of the view (records/thread/destination.js, `taken`).
        return present({ release: true }).then((shown) => {
          stateBand();
          return shown;
        });
      },
    });
    // Upgrade turns the status to its loading words without a publication.
    document.addEventListener(UPGRADE, () => paint(), { once: true });
    document.addEventListener("lf-chrome-preference", () => paint());
    paint();
    // The panel takes over the row the document served, and the field the held keys'
    // words, in the frame the panel first draws (`heldWords`; bootstrap.js).
    document.dispatchEvent(
      new CustomEvent("lf-held-keys-seat", {
        detail: {
          /** @param {HeldWords | null} words */
          show(words) {
            heldWords.value = words;
            if (words) announce(heldText(words));
          },
          // The served row's field, which the user may have written in before the
          // panel stood (`initial`): its words go on in the page's field, a space
          // after a draft the field holds, which the row didn't show, and the caret,
          // if the user is in the textarea, with the selection where it stood. The
          // caret moves while the textarea still stands, so a phone's keyboard has a
          // field to stay up for.
          /** @param {HTMLTextAreaElement} box */
          write(box) {
            const inBox = focused() === box;
            if (!box.value && !inBox) return;
            const input = pageEditor().input;
            const draft =
              box.value && /\S$/.test(input.value) ? `${input.value} ` : input.value;
            if (box.value) input.edit(draft + box.value);
            if (!inBox) return;
            input.setSelectionRange(
              draft.length + box.selectionStart,
              draft.length + box.selectionEnd,
              box.selectionDirection,
            );
            writeOnPage();
            paint();
          },
        },
      }),
    );
  }

  return {
    // The panel's element, which holds its first drawing until it mounts: the row a
    // served document stands from its first paint (build/panel-row.mjs).
    host,
    mount,
    clearFor,
    pageComment,
    searchPage,
    doors,
    showForSample,
    openThread,
    showTodo,
    captureCurrentLocation,
    restoreCurrentLocation,
    // The thread whose view stands open above the row, read through the trail, and
    // putting that view away: what the entry's thread address follows and asks for
    // (records/thread/address.js). Where an entry's record names a list, the list shows as the
    // user left it: the view gives way to it where it stood over it, by its way back
    // (`back`); else the list opens, or stays, as after a reload, which forgets the views
    // the panel stood, On on the tab it stood at. It stands on the row the record names,
    // the one the user left by, else on the row of `from`, the thread the user was in,
    // wherever it showed, and where it was read to once what it holds has drawn, unless
    // the user has moved since (`intent`). `listShown` names the list that stands open,
    // the On tab, the row focus is on in it and how far it was read, which the record
    // keeps (records/history.js). The lists it names are those whose route is the view's name
    // alone, as Threads, On, Versions and All pages are; one a route qualifies, as a
    // menu group or Errors, stays shut.
    shownThread: () => threadOf(trail.value.at(-1))?.id ?? null,
    /** @param {import("../records/history.js").RecordList | null} list @param {string | null} from
     * @param {import("../dom/user-intent.js").UserIntent} intent */
    putThreadAway: (list, from, intent) => {
      const top = trail.value.at(-1);
      const route = list && /** @type {PanelRoute} */ ({ view: list.view });
      const turned = list?.tab ? chooseQueueTab(list.tab) : false;
      if (threadOf(top) && route && trail.value.at(-2)?.view === route.view) back();
      else {
        if (threadOf(top)) close();
        if (route && !showing(route)) open(route);
      }
      if (!list) return;
      if (turned) paint();
      const view = shownView();
      const key = list.row ?? (from && threadByKey(from)?.key);
      const row = key && listRows().find((node) => rowKey(node) === key);
      if (row) focusDestination(row, "return");
      if (!view) return;
      void present().then(() =>
        afterSettling(() => {
          if (intent() && shownView() === view)
            moveScrollerBy(view, list.scroll - view.scrollTop);
        }),
      );
    },
    listShown: () => {
      const top = trail.value.at(-1);
      const view = shownView();
      if (!top || !view || Object.keys(top).some((part) => part !== "view"))
        return null;
      const at = focused();
      const row = at ? listRows().find((node) => renderedUnder(at, node)) : null;
      return {
        view: top.view,
        tab: top.view === "queue" ? queueTab : null,
        row: row ? rowKey(row) : null,
        scroll: view.scrollTop,
      };
    },
    // The anchored comment box opening in its home (`responseSeat`) clears the row for
    // it, where the composer then takes the caret (annotations/composing/surface.js,
    // `finishPlacement`).
    responseHome: responseSeat,
    revealResponse: clearRow,
    // The thread whose row in Threads holds `under`, the element under the pointer, and
    // the row Threads draws for a thread, through which hover links a row and its
    // passage both ways (annotations/anchor-paint.js, `markRow`). Each asks the rows' own markup, so
    // a pointer move costs the same however many threads Threads lists.
    /** @param {Element | null} under */
    hoveredThread: (under) => {
      const row = showing({ view: "threads" })
        ? closestAcross(under, THREAD_ROW)
        : null;
      return row instanceof HTMLElement
        ? (threadByKey(row.dataset.lfKey)?.id ?? null)
        : null;
    },
    /** @param {string} id */
    threadRow: (id) => {
      const key = threadByKey(id)?.key;
      return key && showing({ view: "threads" })
        ? (shownView()?.querySelector(
            `${THREAD_ROW}[data-lf-key="${CSS.escape(key)}"]`,
          ) ?? null)
        : null;
    },
  };
}
