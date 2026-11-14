/* The floating panel: Leaf's chrome, as one box hovering over the foot of the page. It
 * presents what other owners hold, so it reads their readings and calls their commands:
 * the status (page-status.js), the page's controls (`pageControls`,
 * page-controls.js), the threads (`readThreads`), the queues (`readQueues`), the
 * versions (`versionPicker`), the drafts (drafts.js), the passing notices
 * (notifications.js) and the errors (errors.js). It decides only how they are shown.
 *
 * The box has three sizes, and which it stands at follows what the user does, so no
 * setting chooses it:
 * - **Folded**, the leaf alone in the window's corner, coloured by the agent's state,
 *   with a badge counting what waits on the user and a dot for threads with news. The
 *   user folds it from the leaf's menu or with `.`, or by a pointer with the small round
 *   button that rides the box's top-right corner while the pointer is near it and no
 *   view's Close holds that corner; a
 *   press on the leaf unfolds it, and it stays as it was left across pages (`rest`).
 *   Once the page presents, its status tooltip keeps the explanation it opened for
 *   one pointer or focus exposure, so news and aging words cannot move text being
 *   read. The next exposure, including a return from a hidden tab, reads the current
 *   status. The leaf's tone, counts and accessible name stay live, and notices
 *   answering a gesture show immediately.
 * - **The row**: the leaf, the comment field, and at its end one seat: the On Me mark,
 *   counting what waits on the user, with a dot while a thread holds a reply they have
 *   not read; or, while a search stands, the ✕ that ends it, and while a stance stands,
 *   the ✕ that ends it wherever the field doesn't say Close at its end, as it does with
 *   its words at rest, so the seat never stands empty and the stance has one way out
 *   on screen. The ✕ takes the leaf's width, beside the field;
 *   filling the room On Me keeps for its count stood it 29px clear of the field, which
 *   the user questioned on 31 October. The ✕ keeps the seat while the user writes in
 *   the stance. Once the stance ends, a draft's Send takes the corner as it does at
 *   rest, so a draft standing through a stance rewraps as the stance comes and as it
 *   goes, which a path this rare may do (browser/AGENTS.md, "The page holds still
 *   under the user's aim"). Rejected: holding the seat for the draft until the next posture
 *   change. That kept On Me beside the draft and the field narrower, and saved no
 *   rewrap, since the stance's arrival had already rewrapped the draft. An open view
 *   has its ✕ on a line of its own, its head line or its tabs, and the field takes the
 *   seat's room while the view stands, a stance's ✕ waiting with it (**Opened**).
 *   The user chose the one seat on 25 October over a Threads mark beside On Me and a seat kept
 *   empty for the ✕, which left a gap at the row's end; Threads became the On view's
 *   tab, since On Me already lists a thread message that waits on the user. Rejected:
 *   the ✕ standing before both marks, which kept them still but stood it between the
 *   field and the marks. Beside the seat stands at most one small notice for a state
 *   the user should not miss, such as reading an older version, tinted by its tone and
 *   with at most one press (`olderVersion`); the field gives it room, so the seat keeps
 *   its place, but only while it holds no words, which a narrower field would rewrap
 *   under the reader; the notice waits while words stand there, or a press at the
 *   field's end, which a notice coming or going on news would move. The empty field says
 *   what the agent is doing or wants, in the status's words
 *   (`statusReading`), or what a passing notice says, where a placeholder would say
 *   "Comment", and the field's end says the one press that matters most at that
 *   moment: Comment and c at rest; while it passes, the press a notice of the user's
 *   own gesture offers, as a Resolve's Next thread and t (`noticePress`,
 *   thread/folding.js); once the server reads a gesture as answering something On Me
 *   lists, a pick, a settling reaction or a reply sent from a card, while more stands
 *   there, Next On Me and m (application.js, `offerNextOnMe`), which a reply or comment
 *   sent from this field never shows, since the caret stays in it; and in a stance,
 *   such as Draw mode, whose name the field says, Close (`stanceClose`), in place of
 *   the seat's ✕. A press acts as a touch control does, wherever the caret stands, and
 *   says its key only while that key would make it now: `m` typed in a card's reply is
 *   a letter, and Escape closes a comment box standing in Design mode before the mode.
 *   The user chose a notice's press on 31 October, so a Resolve that moves the panel
 *   on says which thread it resolved and offers its next step there, and the rest on 6
 *   November 2026, from what three weeks of their keys pressed next, over Undo and z
 *   after a Resolve, Comment and c after an answer, and the ✕ with Escape unsaid in a
 *   stance. In a thread it says the thread's word beside the leaf, in its
 *   speaker's face (voice.js), with a walk's position after it, and Reply with the key
 *   that enters the field at the field's end (`turnLead`). The user chose this on 27
 *   October so the next action reads apart from the agent's words, over three others:
 *   the key beside Reply with the turn at the field's end in one face, Reply alone with
 *   the turn left to the thread's messages, and the agent's words in a lane of their
 *   own before the seat, at rest too. Reply was in ink until 5 November 2026, when the
 *   user chose one dim face for every comment box's word. While words stand selected
 *   on the page, the page's field quotes them, inside a stance too, and ends in Comment
 *   and c as at rest (the user's choice on 6 November 2026, over c alone after the
 *   quote), and a press there comments on them (`selectedWords`), the one route a
 *   finger has to them; the user
 *   chose that on 19 October over a worded step standing in the marks' place, which
 *   took a stance's steps away while it stood, accepting that a press on the field
 *   addresses selected words whenever they stand. A status that reports reads dimmer
 *   than anything written, and while the agent works it carries the one sheen that marks
 *   work under way; one that asks the user to act reads in its tone's ink. The row
 *   shows no status tooltip: the user rejected the repeated words over the page on
 *   20 October. The leaf's menu holds the full status and the Errors list. Clicking in
 *   gives the placeholder to where the words go, and from then on nothing that passes
 *   is said while the caret is in the field: news, an acknowledgement, a walk's position and Go-to's word go unsaid
 *   there but for the live region, and the empty field says what still stands once the
 *   caret leaves. An error (errors.js) is no passing word: one about the field's
 *   editor covers its words, as at any box (composing/input.js), and the empty field
 *   says the newest one about nothing in its status's place and the danger's ink,
 *   until the user's first edit. An error the field has passed or no box stands for
 *   waits in the leaf's menu, under Errors, with a dot on the leaf until the user
 *   opens the list (`errorsList`). The user chose this on 17
 *   October over errors riding the passing notice, which faded after four seconds and
 *   went unsaid while the user wrote. A draft takes precedence over passing notices,
 *   which still reach the live region. A selected passage is named by the field's
 *   mode chip when a draft hides its placeholder. No transient message adds a row.
 *   The keys that send are Send's hover name, where Return sends with
 *   Shift+Return's new line beside it (composing/input.js).
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
 *   this on 31 October, taking away the row of controls between a thread and its reply,
 *   where Resolve and Close stood from 20 October with the way back as ‹ Threads
 *   among them. Rejected: Threads › before the name, which cost the name about 70px; a
 *   ‹ hanging off the box beside the leaf, far from the name it leads away from; and no
 *   way back, which left a pointer two presses from Threads. The field below runs to
 *   the panel's edge while a view stands, at rest and widened alike, which the user
 *   chose on 28 October over Close in the row's seat, 52px of the field at rest. The
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
 *   from a thread's view shows the next stop (`clearFor`). A thread's view
 *   also goes when a route, such as the `t` walk, opens a thread's card on the page,
 *   so one thread stands open (`reveal`; the user chose this on 23 October, after a
 *   walk left the panel's thread under the card it opened). A card's Open in panel
 *   moves the other way, closing the card for this view (`openThread`), which the
 *   user chose on 25 October for a long thread read in a card's narrow room beside
 *   the column; rejected was opening it wider than other views. The view stands right
 *   on the row, with no room between them that typing would show or hide.
 *   The user chose that (2026-10-14), reversing a blank line's room kept under every
 *   open view, which read in Threads as a missing row. Rejected there: the line pushing
 *   the view up as it comes. The view's last words scroll clear of New reply
 *   (thread/thread-card.js), the one thing that stands over the row. It is as tall as
 *   what it holds, so a one-message thread opens one message tall, up to most of the
 *   window's height, the larger size a long thread or a long Threads list is read at;
 *   past that it scrolls. The user chose views that fit their content with a larger size for long
 *   reading (2026-10-13); content alone reaches that size. Rejected: an Expand
 *   control at the view's head, which the growth it asks for would carry up from under
 *   the pointer, and a compact cap with the larger size behind a gesture, which leaves
 *   every long thread scrolling in a small box until the user finds that gesture.
 *   While it stands it covers the page under it, which reads as unseen (geometry.js,
 *   `declareCover`).
 *
 * The leaf's menu is the On view's first tab, beside On Me, On <agent> and Threads,
 * and the leaf opens the view on it: the full status over the rest of the page's
 * controls, each one line, with its key where it has one, and a chevron on a row that
 * opens a list of its own (Versions, and the groups Navigate and Annotations). Such a
 * list opens over the menu, its way back returning there. While the menu stands, the
 * field is its search (`menuFound`), narrowing the rows to the words typed, with the
 * threads and versions they name and a press that hands the words to the command
 * reference. The user chose this on 30 October, over the menu as a small list of its
 * own over the leaf (15 October), which reached neither On Me nor Threads and, with
 * its lists, kept a second surface with its own opening, holding and fade beside the
 * views. Rejected with it: the On view's tabs at that menu's foot, a menu of rows for
 * On Me and Threads, and a leaf that folds the panel or opens On <agent>. A row that
 * copies a text is one press in the menu wherever the page can copy (`canCopy`), and
 * says which session or Leaf the page runs only in About this page (page-controls.js,
 * the `about` group). A
 * keyboard's convenience for where the reader stands, such as Resume writing, stands
 * under Navigate only where no keyboard is there to reach it (page-controls.js, the
 * `keys` group). The panel shows one key hint of its own, `c` at the field's end while
 * it enters the field, which says where `c` goes: beside Reply in an open thread, which
 * the user asked for on 22 October as a margin card's reply box shows it, and beside
 * Comment at rest, which they chose on 5 November 2026 after the box that rests beside
 * a target (composing/surface.js, `restFab`). The menu's rows carry every other key and `?` opens
 * the full reference, which the user chose on 13 October over a hint or two in the line
 * over the field, to keep the panel quietest. The field the
 * user clicks in is the field they write in: a page
 * comment where no thread is open, a reply where one is: the reply box every view of a
 * thread draws (thread/replies.js), with its ↑ to the user's last message, which Leaf's
 * reader draws in the field's place. Each destination keeps its own native editor (its
 * draft, caret and send), and the panel stands the current one in the field's place, so
 * words never move between editors. Page and Threads search take this same field
 * with their own native inputs: a right-hand scope chip and a faint tint name the
 * mode after its placeholder is gone. Search never borrows an editor or its send or
 * attachments. Every mode keeps its field on the bottom row, with
 * mode-specific controls beside it. Content opens in a view; response choices
 * use a picker. Features contribute to those surfaces rather than adding strips.
 *
 * A list's tabs stand at its foot, the presses on a thread's head line hold its view's
 * height as they act, the leaf's menu holds what it showed while it stands, and a
 * control the user pressed in a thread stays where it was (browser/AGENTS.md, "The
 * page holds still under the user's aim"). Resolving a thread opened from Threads moves the user on to the next
 * one (`resolveLanding`), a view of its own as tall as what it holds, so its head line
 * stands where that height puts it: the press took the pressed Resolve away, and the
 * next thread is its result, which the user said on 31 October is fine. A control
 * that arrives under the pointer takes the next press at once, as the user chose then.
 * Rejected: holding such a control inert until the pointer moves; and opening the next
 * thread at the height the resolved one stood at, so Resolve stayed under the pointer
 * (#4878), which the user rejected on 3 November: a run of Resolves showed every
 * thread at the first one's height, cut off or with room under it, until their next
 * turn, and a key's Resolve, which aims at nothing, held it too.
 *
 * Every change of the box's layout takes effect in one step, and what the user sees
 * then travels from where it was drawn to where it stands, by one model
 * (box-motion.js): the surface behind the box, a separate layer, follows by a
 * clip, the way the Codex app's floating panel moves, and so does the field's ring; a
 * part that kept its size is carried by a transform; one that changed size grows from
 * where it stood, carrying its words by their start corner; one that is new is revealed
 * by the edges of what holds it. That carrying is for the user's own change, a key,
 * press or typing: news, such as an answer growing a thread's view, shows what it moved
 * where it now stands, revealed by the surface's clip, so news moves nothing the reader
 * reads. Nothing's layout tweens, so the box's room on the page is its new room at
 * once. The user asked for this on 20 October, after a line the field gained left its
 * attachment vanishing and its ring outrunning the box, and more room left the field
 * behind the box widening around it; it replaced revealing everything a change moved
 * by the surface's clip, which hid each part that moved until the clip reached it. */
import {
  html,
  noChange,
  keyed as keyedBy,
  live,
  nothing,
  ref,
  render,
  repeat,
  signal,
} from "/runtime/framework.js";
import { el, offeredAction, reveal } from "./widget-elements.js";
import { actionTemplate, iconTemplate } from "./icons.js";
import { actionName } from "./icon-paths.js";
import { canCopy, copyControl } from "./copy-control.js";
import { atLayoutPrecision, keeps, keepsHidden } from "./keeps.js";
import { keepFieldKeys } from "./field-keys.js";
import { setRuntimeRootStyle } from "./root-state.js";
import { statusReading } from "./page-status.js";
import { leavesRows } from "./live-leaves.js";
import { keys } from "./keyboard/scopes.js";
import { pageCommand, pageDoor, pageRung } from "./keyboard/register.js";
import {
  advertisesKeys,
  parsed,
  spell,
  titleOf as rowTitle,
} from "./keyboard/bindings.js";
import {
  keySequenceModel,
  keySequenceTemplate,
  neutralSteps,
} from "./keyboard/key-sequence.js";
import { pageControls } from "./page-controls.js";
import { findCommands } from "./keyboard/command-reference.js";
import { readPlace } from "./history.js";
import {
  NO_OPEN_THREADS,
  THREADS_OFFLINE,
  readThreads,
  threadNamed,
} from "./thread/state.js";
import { discussed, isNews, threadCounts } from "./thread/model.js";
import { LeafElement } from "./leaf-element.js";
import {
  RESOLVED,
  threadAttention,
  todoWord,
  workflowStep,
  workflowWord,
} from "./thread/workflow.js";
import { agentSays, leafSays, voiceOf, voiced, wordsText } from "./voice.js";
import {
  anchorLabel,
  messageReading,
  messageText,
  threadHeading,
  threadName,
  threadPassage,
  threadPreview,
  titlePending,
} from "./thread/messages.js";
import { drawnThreadId, THREAD } from "./thread/selectors.js";
import { declareThreadParts } from "./thread/selectors.js";
import { inPageOrder } from "./thread/placement.js";
import { dismissReply, releaseReplies } from "./thread/replies.js";
import {
  PAGE_DRAFT,
  draftHasContent,
  loadDraft,
  mirrorDraft,
  saveDraft,
  replyContext,
  sendMessage,
  tellDraft,
} from "./drafts.js";
import { textField } from "./composing/text-field.js";
import { draftOf, standsAtItsBox, syncInput } from "./composing/input.js";
import { TEXT_FIELD } from "./control-selectors.js";
import { retainUserIntent } from "./user-intent.js";
import { holdPlace, standsAt } from "./user-place.js";
import { onUserCount, queueItemKey, readPlan, readQueues } from "./queue-api.js";
import { queueTitle } from "./queue-title.js";
import { groupingLabel, ON_ME_GROUPINGS, queueStop } from "./queue-walk.js";
import {
  carriesObligation,
  emptyOnList,
  itemNoun,
  itemOutcome,
  onList,
} from "./queues.js";
import { agePreview, ago, shortAgo } from "./presence.js";
import { userChoice } from "./storage.js";
import { obligationEnding } from "./obligations/answer.js";
import { answeredInWords, readObligations } from "./obligations/model.js";
import { obligationPlace } from "./obligations/place.js";
import { ON_CARD } from "./obligations/view-elements.js";
import { declareSide, holdPagePlace } from "./current-target.js";
import { versionPicker } from "./version-picker.js";
import { versionsReading } from "./version.js";
import { UPGRADE } from "./presentation.js";
import {
  gestureReading,
  noticeReading,
  noticeWords,
  offeredPress,
} from "./notifications.js";
import {
  dismissError,
  dismissErrors,
  errorsReading,
  passErrors,
  seeErrors,
} from "./errors.js";
import { statusContextReading } from "./keyboard/status-context.js";
import { motionEasing, motionPlays, motionTime, playMotion } from "./motion.js";
import { pagePresented } from "./page-paint.js";
import {
  claimReleaseClick,
  focusDestination,
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
  rove,
  currentLocationIn,
} from "./focus.js";
import { rowWalk } from "./walk-position.js";
import {
  capitalized,
  COMMENT_HINT,
  counted,
  excerptWords,
  REOPEN_HINT,
  REPLY_HINT,
} from "./words.js";
import { coarsePointer } from "./pointer.js";
import { afterScript, holdRendering, nextRender, sizeObserver } from "./rendering.js";
import { boxMotion } from "./box-motion.js";
import { landedBox, scrollIntoView } from "./landing-scroll.js";
import { gesturedOn, newsCount, newsNotice } from "./thread/held-news.js";
import { keepFoot, moveScrollerBy, scrollToEnd } from "./scrolling.js";
import { showReturnTurn } from "./thread/reply-landing.js";
import {
  announceRoom,
  covered,
  declareCover,
  placeBox,
  placeHolder,
  seenRect,
  stateFootBand,
} from "./geometry.js";
import { overlaps } from "./rect.js";
import { registerReadingRegion } from "./reading-regions.js";
import { sectionsInView } from "./reading-place.js";
import { agentName, documentChanged } from "./semantic-state.js";
import { runtime } from "./context.js";
import { renderedUnder, under } from "./shadow.js";
import { nativeModalAdmits } from "./keyboard/layer-stack.js";
import { commandSteps } from "./keyboard/control-keys.js";
import {
  activeCommandLabel,
  escapeInvocation,
  innermostStance,
} from "./keyboard/dispatch.js";
import { closestAcross } from "./passages.js";

const prefs = () => window.lfChrome;

// What the field's own search box asks for, in each list it searches, in Leaf's words
// as every search's prompt is (control-labels.js, `searchField`).
const SEARCH_PROMPTS = Object.freeze({
  menu: "Find a row, thread or version…",
  threads: "Find a thread or message…",
});
// The menu's groups, each a list of the page's controls declaring it, in the menu's place.
const GROUPS = Object.freeze([
  { name: "navigate", label: "Navigate" },
  { name: "annotate", label: "Annotations" },
]);
// Rows held elsewhere, so the menu and its groups leave them out: by the menu's foot.
const FOLD = "panel.floating.fold";
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
// The menu offers a copy shortcut only where a copy can work (copy-control.js,
// `canCopy`). A clipboard may still refuse a write, after which the menu drops its copy
// shortcuts (`copyItem`).
let copyRefused = false;
// Keyboard conveniences also stand under Navigate where a finger needs them.
/** @param {ReturnType<typeof pageControls>[number]} entry */
const groupOf = (entry) =>
  entry.group === "keys" && !advertisesKeys() ? "navigate" : entry.group;
// What passes in the panel's one seat for words that pass: a notice while one shows,
// else what the status line says between notices, the Go-to filter's word or a walk's
// position ("1 of 3 waiting on me · Options"). The user asked on 16 October that
// whatever is not anchored to the page stand at the panel rather than against the
// window.
function passing() {
  const notice = noticeReading();
  if (notice.visible)
    return { message: notice.message, visible: true, press: notice.press };
  const message = navigationWords();
  return { message, visible: Boolean(message), press: null };
}
function navigationWords() {
  const { goTo, walk } = statusContextReading();
  return goTo ?? walk?.text ?? "";
}
/** @param {number} at */
const clock = (at) =>
  new Date(at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
// An age the panel shows, which previews the clock time behind it as every age does
// (presence.js, `agePreview`): short, in a room of its own (`.lf-fp-age`) at a line's
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

/** @typedef {(typeof GROUPS)[number]} MenuGroup */
/** @typedef {({view: "thread", thread: string} | {view: "group", group: MenuGroup} |
 * {view: "errors", errors: readonly import("./errors.js").RaisedError[]} |
 * {view: "menu"} | {view: "threads"} | {view: "queue"} | {view: "leaves"} |
 * {view: "versions"}) & {
 * thread?: string, group?: MenuGroup, errors?: readonly import("./errors.js").RaisedError[]}} PanelRoute */
/** @template {PanelRoute["view"]} K @typedef {Extract<PanelRoute, {view: K}>} RouteFor */
/** @template {PanelRoute} R @typedef {{
 * title: (route: R) => string, draw: (route: R) => unknown,
 * key?: (route: R) => string, head?: (route: R) => unknown, quiet?: (route: R) => boolean,
 * controls?: (route: R) => {crumb?: unknown, aux?: unknown},
 * presses?: (route: R) => {facts?: unknown, presses?: unknown},
 * nominate?: (route: R, collection: import("./thread/primary-reader.js").PrimaryCollection, parts: import("./thread/primary-reader.js").NominationParts) => unknown,
 * over?: readonly ("threads" | "queue" | "menu")[], rows?: string, at?: string,
 * row?: PanelRoute,
 * keys?: readonly import("./keyboard/bindings.js").Command[],
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

/** @typedef {NonNullable<ReturnType<typeof import("./application.js").mountApplication>>} Application */
/** @typedef {ReturnType<typeof import("./queue-walk.js").createQueueWalk>} QueueWalk */
/** @typedef {Pick<Application, "threadActions" | "registerChromeThreadPresentation" | "queueActions" | "withdraw"> & {
 * wireInput: ReturnType<typeof import("./composing/input.js").createCompositionInputs>["wireInput"],
 * observeFeedback: ReturnType<typeof import("./thread/read.js").createReadTracking>["observeFeedback"],
 * obligations: Pick<ReturnType<typeof import("./obligations/view.js").createObligationView>, "choicesOf">,
 * arrivesAt: QueueWalk["arrivesAt"], onMe: QueueWalk["onMe"],
 * placedAt: ReturnType<typeof import("./anchor-placement.js").createAnchorPlacement>["placedAt"],
 * openThreadSubject: ReturnType<typeof import("./thread/destination.js").createThreadDestinations>["openThreadSubject"],
 * showsOnPage: ReturnType<typeof import("./thread/destination.js").createThreadDestinations>["showsOnPage"],
 * annotationsHidden: () => boolean}} FloatingPanelOptions */
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
  // The leaf answers the moments notifications.js passes on (`gesture`) with a motion
  // each, once per moment, its length on the panel's sheet (`--lf-motion-leaf-nod` and
  // its siblings, named for each motion). A new one takes over from one still playing,
  // which stops where it is rather than carrying on once the new one ends. Each
  // turns, lifts or scales the mark about its centre and comes back to rest, every
  // stretch with its own easing, so it plays over the pose the tone holds
  // (floating-panel.css, `data-lf-tone="away"`). The nod answers the user's own key, so
  // a press shows it landed although the field's words, quiet and already standing on a
  // repeat, may not; the user picked it on 9 November 2026 over the words brightening
  // and the panel tinting, and then each other moment's motion from a playground of
  // them, leaving the leaf still while the agent works. The leaf's personality is still
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
  /** @type {Record<import("./notifications.js").Moment, keyof typeof MOTIONS>} */
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
  /** @param {import("./notifications.js").Moment} moment */
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
  // One template owns the panel's shell, views and editor placement. Its detached first
  // drawing establishes the retained nodes that setup wires below. The peek must follow
  // the leaf in the tree so it can anchor to it.
  // The quick seat is one button, changing between the mark and a search's or a
  // stance's way out. Its count keeps its room even when empty; a count arriving moves
  // nothing beside it. The corner mark presses the fold command's row, as the menu
  // does, so its press is announced and logged like the key's.
  function panelTemplate(initial = false) {
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
    const folded = !initial && prefs().rest === "mark" && !top && !search;
    const statusModel = initial ? { summary: "Connecting…", tone: "" } : status();
    const onUser = initial ? 0 : onUserCount();
    const news = initial ? 0 : newCount();
    const sayingNow =
      initial || noticePressing(input)
        ? new Set()
        : new Set(sayable().map((error) => error.id));
    const unseen =
      !initial &&
      errorsReading().some(
        (error) => !error.seen && !sayingNow.has(error.id) && !standsAtItsBox(error),
      );
    const exit = initial ? null : fieldExit(search, top, input, reading);
    // A view's Close ends the line its presses stand on: a list's tabs at its foot, or
    // the head line, where a thread's presses stand and every other view's name. A
    // search's own ✕ ends the row under a list's tabs while it holds the field, so the
    // list's Close waits, unseen, for the search to end, and one ✕ shows at the foot;
    // it keeps its room, so the search press beside it stays under the pointer.
    const closeAtFoot = Boolean(top && viewOf(top).controls);
    // Page search's way out is its stance's, which the repaint frame reads after the
    // paint that opens it (touch-controls.js). Until then the seat keeps what it shows
    // rather than stepping aside, which, opened from the menu, would hide it again in
    // the task that put the menu away and showed it.
    const quickHidden =
      initial || (Boolean(top) && !exit) || (!exit && (writing || drafted));
    const notice = initial || search ? null : olderVersion();
    const peek = initial ? null : peekPresentation();
    const mode = search
      ? html`<span class="lf-fp-mode-word">Search </span>${iconTemplate(
            "search",
            "lf-fp-mode-icon",
          )}<span>${searchMode}</span>`
      : selection
        ? "Selection"
        : nothing;
    const newsName = news ? `${counted(news, "thread")} with news` : "";
    const onUserName = [onUser ? `On Me: ${onUser}` : "On Me", newsName]
      .filter(Boolean)
      .join(", ");
    const quick = html`<button
      type="button"
      ${offeredAction(
        "symbol",
        exit ? "lf-fp-exit" : "lf-fp-on-user",
        exit ? exit.label : onUserName,
        { action: exit ? "close" : "on-me" },
      )}
      ?data-lf-due=${!exit && onUser > 0}
      ?disabled=${Boolean(exit?.disabled)}
      @mousedown=${
        exit ? (/** @type {MouseEvent} */ event) => event.preventDefault() : nothing
      }
      @click=${exit ? () => exit.press() : pressMark}
    >
      ${
        exit
          ? nothing
          : html`<span class="lf-fp-num">${onUser || ""}</span
              ><span class="lf-fp-news lf-unread-dot" ?hidden=${!news}></span>`
      }
    </button>`;
    const viewClose = html`<button
      type="button"
      ${offeredAction("symbol", "lf-fp-exit lf-fp-close", "Close", { action: "close" })}
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
            <button
              type="button"
              ${offeredAction(
                "symbol",
                "lf-fp-leaf",
                `${folded ? "Unfold Leaf" : "Page menu"} · ${statusModel.summary}`,
                { action: "menu" },
              )}
              data-lf-tone=${statusModel.tone || nothing}
              aria-expanded=${folded ? nothing : String(!initial && menuStands())}
              .lfPreview=${leafPreview}
              @click=${pressLeaf}
            >
              <span
                class="lf-fp-error-dot"
                aria-hidden="true"
                ?data-lf-shown=${unseen}
              ></span>
              <span class="lf-fp-badge" aria-hidden="true" ?data-lf-shown=${onUser > 0}
                >${onUser || ""}</span
              >
              <span
                class="lf-fp-news-dot lf-unread-dot"
                aria-hidden="true"
                ?data-lf-shown=${news > 0}
              ></span>
            </button>
            <div class="lf-fp-field">
              <div class="lf-fp-editors" ?hidden=${Boolean(search)}>
                ${initial ? nothing : top?.thread ? replyOutlet : pageEditor().box}
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
                  const words = search ? searchLabel : selection ? reading.words : null;
                  return words ? { name: words } : null;
                }}
                >${mode}</span
              >
              <div class="lf-fp-actions" ?hidden=${!searchControls.length}>
                ${searchControls}
              </div>
            </div>
            <div class="lf-fp-response"></div>
            <div class="lf-fp-row-notice" ?hidden=${!notice}>
              ${notice ? rowNoticeTemplate(notice) : nothing}
            </div>
            <div class="lf-fp-quick" ?hidden=${quickHidden}>${quick}</div>
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
  // The fold mark rides the box's top-right corner, chosen over the row's end on
  // 15 October. The menu's fold row and `.` provide its keyboard and touch routes.
  // It shows only while the pointer is near the corner it rides, so the panel at rest,
  // and under a pointer passing over the field or the marks, carries no control the user
  // did not reach for (15 October). Near is the box's top-right corner, a mark's width in
  // and half a row down, which holds the button itself. The corner moves when the box changes
  // size under a still pointer, as a view opening above a press on Send carries it up,
  // so nearness is read again then (`follow`): a button left showing where the
  // pointer no longer is would ride the box's next change, such as a refused send
  // taking that view back, across the window without input.
  const CORNER = { across: 64, down: 24 };
  /** @type {{x: number, y: number} | null} */
  let pointer = null;
  const readCorner = () => {
    const box = card.getBoundingClientRect();
    const near =
      pointer !== null &&
      pointer.x >= box.right - CORNER.across &&
      pointer.y <= box.top + CORNER.down;
    keeps(host, "data-lf-corner", near ? "" : null);
  };
  host.addEventListener("pointermove", (event) => {
    pointer = { x: event.clientX, y: event.clientY };
    readCorner();
  });
  host.addEventListener("pointerleave", () => {
    pointer = null;
    readCorner();
    // A press offered while the pointer stood on the panel stands once it leaves
    // (`pagePress`).
    if (shownOffer !== offeredPress()) paint();
  });
  const leaf = shell("leaf");
  const field = shell("field");
  const editorSeat = shell("editors");
  // A long draft offers more room, by the user's press rather than on its own: past
  // three lines a quiet mark stands over the leaf, in the corner the draft leaves free
  // beside its first line, so it takes no room of its own (browser/AGENTS.md, "A
  // control takes only its own room"). It stood at the end of the
  // line over the field until, on 17 October, that line stopped saying where the words
  // go and so stopped standing over them. Pressing it widens the
  // panel and gives the field more lines (floating-panel.css), so the words
  // re-wrap because the user asked. It folds back when the field empties, a send included, or on a second
  // press. The user chose this on 15 October over the panel widening by itself at the
  // third line, which re-wraps every line under the caret; no composer they compared
  // widens on its own (Open WebUI and Zulip offer the same press once text is long).
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
  const searchSurface = shell("search-surface");
  // The row's end: the On Me mark, or the way out of the search the user is in, or of
  // their stance where no view is open, there while the user types too
  // (touch-controls.js, `stance`), each at its own width (floating-panel.css,
  // `.lf-fp-quick`).
  // The anchored comment box's home on a page that draws its own annotations
  // (`data-annotations="page"`), where the page gives the box no seat of its own
  // (composing/surface.js, `responseHome`). While its composer is open it stands in the
  // field's place, as each destination's own editor does there: its words go to a new
  // thread on the passage it quotes, which the box says. The field comes back when the
  // box closes, while a view is open above the row, whose field it is, and while the
  // field quotes words selected on the page, which a press there comments on. Which of
  // the two shows is the stylesheet's reading of the composer's own open state and the
  // row's `data-lf-offers` (floating-panel.css), so the box seated in the page, or put
  // away, moves nothing here. Rejected: a view of its own above the row, which stood a
  // second field over the panel's own.
  const responseSeat = shell("response");

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
  const status = () => statusReading() ?? CONNECTING;
  // Words drawn in their speakers' faces (voice.js), where the agent's sentence alone
  // carries response identity. Its renderer ref registers and retires that exact node
  // with the shared exposure owner, wherever status stands: the field's placeholder
  // slot, the menu, or the folded leaf's peek.
  /** @param {import("./activity-words.js").Words} words */
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
  // (keyboard/scopes.js): a press that opens Threads gives the panel its `/` with no
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
  /** @typedef {Parameters<import("./composing/target-picker.js").TargetPickerOptions["searchInPanel"]>[0]} PanelSearch */
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
  // search on 30 October, with the menu as the On view's first tab.
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
  // While the user writes, the field runs to the row's end, the mark and the row's
  // notice stepped aside, from the moment they open it: Send stands in
  // the corner, and the first key moves nothing. The user chose this on 29
  // October over the field widening at the first key, which moved its end and the
  // action under it by the mark's width as typing began.
  let writing = false;
  // Whether the field holds a draft, as the row last showed it: Send in the field's
  // corner, the mark stepped aside. The row takes that posture, or gives it up, only
  // at the user's own move: typing, or a view changing, which stands another editor in
  // the field. The caret coming into or leaving the field moves nothing, so a draft the
  // user steps away from keeps every line where it was. The user chose this on 20
  // October over the counts coming back as the caret left, which rewrapped the draft
  // each time the user stepped out and again as they came back. Words a refused send
  // hands back move nothing, so its action stays in the seat the empty field gave it,
  // until the user types again; emptying the field always ends it. A draft is
  // anything typed, a line break included.
  let drafted = false;
  let postureMoved = true;
  // The beat of the moment the leaf last answered (`gestureLeaf`).
  let answered = gestureReading().beat;
  // The thread the reader lands in once its reading is drawn: on opening,
  // at the turn the user comes back for (`showReturnTurn`); after the user's turn,
  // past it, at its end (`end`); after a press on its held news, at the first message
  // the news showed, where it showed one (`shown`, the messages drawn before it).
  /** @type {{key: string, end: boolean, shown?: Set<string>} | null} */
  let landing = null;

  // ---------- one native editor per destination ----------
  // The errors the field can say now, newest first (errors.js): about nothing, not yet
  // edited past, while the editor standing in the field is empty. An error about the
  // editor covers it instead, as at any box (composing/input.js). A folded panel, or a
  // view with no editor in the field, can say none. The editor is the one this paint
  // stands in the field, whether or not it stands there yet: the paint that closes a
  // thread's view reads before it moves the page's editor in, and read from the DOM,
  // the error went unsaid for that paint, and the leaf's dot was set and cleared in
  // one task.
  function sayable() {
    const input = host.dataset.lfRest === "mark" ? null : fieldInput();
    if (!input || draftOf(input) !== "") return [];
    return errorsReading().filter((error) => !error.passed && error.subject === null);
  }
  // The words selected on the page that a press on the page's field comments on, as
  // the response surface offers them (composing/surface.js, `offerSelection`): their
  // `quote`, and the `comment` that opens the comment on them. Null while none stand.
  /** @typedef {{quote: string, comment: () => unknown}} SelectedWords */
  /** @type {SelectedWords | null} */
  let selectedWords = null;
  // What the empty field says, and whose reading it is (`says`): the newest error it
  // can say; once the caret is in a field that takes words, where they go; on the page,
  // the selected words a press there comments on; a passing notice while one stands;
  // else on the page what the agent is doing or wants, in
  // the status's words, and in a thread whose turn it is. On the page, the stance the
  // user is in, such as Draw mode, heads a passing notice and takes the status's
  // place (keyboard/status-context.js); the leaf keeps the status's colour. While the
  // user has hidden the annotation layer (`o`, annotation-layer.js), which a reload
  // keeps, the status or stance says so, or a page whose marks are hidden would read
  // as one with none.
  //
  // In an open thread the field is the reply box, so it says the reply, with the key
  // that enters it, but for a notice or the Go-to word for their moment; whose turn it
  // is and a walk's position, which stand as long as the user does, stand before it
  // (`turnLead`). The user asked for this on 22 October, when a walk's "Thread 11 of
  // 11" in the field's place left nothing saying how to reply to the thread they were
  // reading.
  //
  // A reading that offers a press (`offers`), the reply or the selected words, stands
  // with the key that makes it; the page field's other readings end in the press the
  // moment offers (`offer`), else in Comment and the key that enters the field. Every
  // reading, and the words standing before the reply, are said by the agent or by
  // Leaf, each in its face (voice.js), and read dim (floating-panel.css). A stance's
  // name and the words quoted are nobody's.
  const HIDDEN = "Annotations hidden";
  // A notice offering a press after the user's own gesture is newer than any error the
  // field says, so while it passes it says its words over that error,
  // which waits in the menu's Errors meanwhile, as one the field has passed does, and
  // the field says it again once the notice has gone. The caret in the field says
  // nothing that passes.
  /** @param {Element | null} input */
  function noticePressing(input) {
    return Boolean(passing().press) && input !== focused();
  }
  // The page field's readings whose words say something other than a press there, so
  // its end says the press: the status, a passing notice, and the words selected on the
  // page, which the user chose on 6 November 2026 to end in Comment… and c, as the field
  // does at rest, over c alone right after the quote.
  const SAYS_ELSE = new Set(["status", "notice", "selection"]);
  const hiddenLead = () => (annotationsHidden() ? [leafSays(`${HIDDEN} · `)] : []);
  // `drawn` is the thread as its view draws it, which the reply box's words read
  // (`replyOptionsFor`).
  /** @param {string | null} key @param {Element | null} input
   * @param {import("./thread/thread-card.js").DrawnThread | null} [drawn] */
  function fieldReading(key, input, drawn = null) {
    const notice = passing();
    const [error] = sayable();
    if (error && !noticePressing(input))
      return { says: "error", words: leafSays(error.message) };
    const thread = key ? threadByKey(key) : null;
    // A retained field can repaint between a thread leaving the reading and its
    // route being retired. Its native row survives that interval, not its turn.
    if (key && !thread) return { says: "absent", words: "" };
    if (input === focused())
      return { says: "destination", words: whereTo(drawn ?? thread) };
    if (thread && !noticeReading().visible && !statusContextReading().goTo)
      return { says: "turn", words: leafSays(REPLY_HINT), offers: true };
    const stance = key ? null : statusContextReading().stance;
    // Keep the current navigation context alongside the selection's comment offer.
    // The field's own name says what a press does (`pageEditor`); on a narrow phone
    // its ellipsis shortens the quote after the mode and position, not instead of them.
    if (!key && selectedWords)
      return {
        says: "selection",
        offers: true,
        words: [stance, navigationWords(), `“${excerptWords(selectedWords.quote, 60)}”`]
          .filter(Boolean)
          .join(" · "),
      };
    // A notice says its words in the empty field's, and the press it offers, such as
    // a Resolve's Next thread, is the one the field's end offers while it passes, said
    // as Comment and its key are (`noticePress`, composing/input.js `enters`); one
    // offering none leaves the page's own there (`pagePress`), as the walk a Next On
    // Me makes says its place beside the press that takes it on.
    if (notice.visible) {
      const own = notice.press ? noticePress(notice.press) : null;
      const close = own || !stance ? null : stanceClose();
      return {
        says: "notice",
        words: [
          ...(stance ? [`${stance} · `] : []),
          ...[noticeWords(notice.message)].flat(),
        ],
        offer: own ?? close ?? (key ? null : pagePress()),
        exits: Boolean(close),
      };
    }
    if (stance) {
      const close = stanceClose();
      return {
        says: "stance",
        words: annotationsHidden() ? [`${stance} · `, leafSays(HIDDEN)] : stance,
        offer: close,
        exits: Boolean(close),
      };
    }
    if (!key)
      return {
        says: "status",
        words: [...hiddenLead(), ...status().summaryParts],
        offer: pagePress(),
      };
    return { says: "turn", words: leafSays(REPLY_HINT), offers: true };
  }
  // The press offered alone on the page, as Next On Me after an answer
  // (notifications.js, `offerPress`), or null. It comes and goes with the server's
  // reading rather than with the user's input, so while the pointer rests on the panel
  // the field's end keeps what it showed, and takes the change at the user's next input
  // or once the pointer leaves: a press arriving there would stand where the user was
  // about to press Comment (browser/AGENTS.md, "The page holds still under the user's
  // aim").
  /** @type {import("./notifications.js").NoticePress | null} */
  let shownOffer = null;
  let offerShownAt = -1;
  function pagePress() {
    if (pointer === null || inputCount() !== offerShownAt) {
      shownOffer = offeredPress();
      offerShownAt = inputCount();
    }
    return shownOffer ? noticePress(shownOffer) : null;
  }
  // What stands before an open thread's reply while the field says it, beside the leaf
  // (composing/input.js, `hintLead`): the thread's word, as Threads says it, then a
  // walk's position. The thread walk standing on this thread says only its place,
  // "11 of 11", since the view names the thread. The agent's own line, a to-do's title
  // or a start's, stays in the thread, where the working message says it. A notice or
  // the Go-to word, which pass in a moment, take the reply's place. The thread's word
  // is the one its view draws (`drawn`), held news included, as its Resolve says it.
  /** @param {string | null} key @param {Element | null} input
   * @param {import("./thread/thread-card.js").DrawnThread} drawn */
  function turnLead(key, input, drawn) {
    if (fieldReading(key, input).says !== "turn") return "";
    const thread = threadByKey(key);
    const { walk } = statusContextReading();
    const position = !walk
      ? ""
      : walk.kind === "thread" && walk.target === thread?.id
        ? `${walk.position} of ${walk.total}`
        : walk.text;
    // A walk gone on to the page, leaving the thread's view open above the stop it
    // reached (`clearFor`), names that stop alone: the user is at it now, not at this
    // thread's turn.
    const away = Boolean(position) && !currentLocationIn(host);
    const settled = drawn.resolvedBy ? leafSays(drawn.resolvedBy) : RESOLVED;
    const word = away ? null : drawn.resolved ? settled : drawn.attention?.word;
    if (!word) return position;
    return voiced([word, ...(position ? [` · ${position}`] : [])]);
  }
  // What the focused field says: the word it says at rest, as every comment box does
  // with the caret in, which the user chose on 5 November 2026 over naming where the
  // words go, which a box beside its target or in its card repeats and cuts short. A
  // reply to a resolved thread still says that it reopens it (events.md), since the
  // Resolved that says so at rest goes with the caret.
  /** @param {{resolved: unknown} | null} thread */
  const whereTo = (thread) =>
    leafSays(!thread ? COMMENT_HINT : thread.resolved ? REOPEN_HINT : REPLY_HINT);
  // An editor's empty words, as its own paint draws them (composing/input.js, `hint`),
  // which marks the editor with whose reading they are, so the face the theme gives that
  // reading changes in the same paint as the words (floating-panel.css). Words all one
  // speaker says, such as an error or Leaf's own state, mark the editor with that voice,
  // which its native placeholder wears whole (`voiceOf`).
  /** @param {string | null} key @param {Element | null} input
   * @param {import("./thread/thread-card.js").DrawnThread | null} [drawn] */
  function saying(key, input, drawn = null) {
    const { says, words, offers } = fieldReading(key, input, drawn);
    if (input) {
      keeps(input, "data-lf-says", says);
      keeps(input, "data-lf-voice", voiceOf(words));
      keeps(input, "data-lf-offers", offers ? "" : null);
    }
    return wordsText(words);
  }
  // The empty words drawn as parts, where the native placeholder's one face can't say
  // them: words whose speakers differ, and the agent's sentence, whose node the
  // status's exposure registers (`statusParts`). Null leaves the native placeholder.
  /** @param {string | null} key @param {Element | null} input
   * @param {import("./thread/thread-card.js").DrawnThread | null} [drawn] */
  function fieldHint(key, input, drawn = null) {
    const { words } = fieldReading(key, input, drawn);
    const parts = [words].flat();
    return wordsText(words) &&
      (!voiceOf(words) ||
        parts.some(
          (part) => typeof part !== "string" && "source" in part && part.source,
        ))
      ? statusParts(words)
      : null;
  }
  // The page's own editor: the field where no thread is open.
  /** @type {{box: HTMLDivElement, input: ReturnType<typeof textField>, sync: () => void} | null} */
  let general = null;
  function pageEditor() {
    if (general) return general;
    const input = textField();
    input.name = "comment";
    const box = el("div", "lf-fp-box");
    box.append(input);
    input.value = loadDraft(PAGE_DRAFT)?.text ?? "";
    // The first Lit render reads this editor through the panel's field selectors.
    general = { box, input, sync: () => sync() };
    const sync = wireInput(input, {
      hint: () => saying(null, input),
      hintParts: () => fieldHint(null, input),
      // The agent's or Leaf's words at rest say nothing about the press, so the key
      // that enters the field stands with its word (composing/input.js, `enters`),
      // unless the moment offers a press of its own there: a passing notice's, the
      // next On Me item after an answer, or a stance's Close (`fieldReading`).
      enters: () => {
        const { says, words, offer } = fieldReading(null, input);
        return offer ?? (SAYS_ELSE.has(says) && wordsText(words) ? COMMENT_HINT : "");
      },
      // Named for what a press there does, as the field's reading says it, once the
      // editor this builds is the one the reading reads.
      accessibleName: () =>
        general && fieldReading(null, input).says === "selection"
          ? "Comment on the selection"
          : "Comment on the page",
      sends: "send",
      sendClass: "lf-fp-send",
      save: (text) => {
        saveDraft(PAGE_DRAFT, text);
        tellDraft(PAGE_DRAFT, text);
        retype();
      },
      send: (_text, raw, owns) => {
        let flight = null;
        streamSend();
        // A page comment has no passage, so it records the sections on screen as the
        // user sends it (reading-place.js, `sectionsInView`).
        const viewing = sectionsInView();
        const handle = sendMessage(
          PAGE_DRAFT,
          owns,
          (attempt) =>
            (flight = threadActions.create({
              attempt,
              text: raw,
              ...(viewing.length && { viewing }),
            })?.delivery),
        );
        if (!handle) return;
        // The box empties as the send leaves; the row reads it again once it has.
        queueMicrotask(paint);
        // A page comment starts a thread, keyed by the attempt that sent it, which the
        // panel opens so its reply follows in the same field.
        /** @type {PanelRoute} */
        const route = { view: "thread", thread: handle.attempt };
        open(route, { replace: true });
        // A refusal takes back the thread the send drew, which the server never held,
        // and its view goes with it (`paintPanel`); the words go back to the page's
        // draft (drafts.js, `standGesture`). Unless the user has opened another view
        // since, the field stands for the page again holding them. The caret follows
        // only while no later input has changed where the user is reading.
        const untouched = retainUserIntent({ source: host });
        void Promise.resolve(flight).then((sent) => {
          if (sent || (trail.value.length && trail.value.at(-1) !== route)) return;
          caretToField = untouched();
          paint();
        });
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
  // A thread's reply is the reply box every thread view has (thread/replies.js), which
  // the thread draws into the field where the panel gives it a place
  // (`nominateThread`), so ↑ to the user's last message, the draft's editing session
  // and Send work as in a card.
  // The panel says what the empty box reads, and a send keeps the user in the field for
  // the next turn, landing the view at its end. A resolved thread keeps its reply box,
  // whose empty field says Resolved before Reply, and a reply reopens the thread, as
  // the user expected on 27 October and as every thread card does since 28 October.
  // The field once took no words there and said only Resolved, so writing in a
  // resolved thread took Reopen first.
  const replyOutlet = el("div", "lf-fp-reply-outlet");
  const replyInput = () => replyOutlet.querySelector(TEXT_FIELD);
  /** @type {Map<string, import("./thread/thread-card.js").ThreadReplyOptions>} */
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
          // end, as over the page's (`fieldReading`, `offer`).
          enters: () => fieldReading(key, replyInput()).offer ?? "",
          accessibleName: () => `Reply to ${threadTitle(key)}`,
          sending: streamSend,
          // A turn the log refuses takes its room back from the view, and the words it
          // hands back grow the field as typing does, so the view's head and the controls
          // over the field move with them. The user chose this on 25 October over holding
          // the head and the field's height through the refusal (#3939): the words the
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
  // The way out at the row's end: a search's, or, where no view stands, a stance's
  // while one stands and the page field doesn't say it at its end, which it does while
  // it says its words at rest (`stanceClose`). An open view's Close stands on the view's
  // own line (`closeAtFoot`).
  /** @param {PanelSearch | typeof threadSearch | null} search @param {PanelRoute | null | undefined} top
   * @param {Element | null} input @param {ReturnType<typeof fieldReading> | null} reading */
  const fieldExit = (search, top, input, reading) => {
    if (search === threadSearch && !menuSearching())
      return {
        label: "Close search",
        press: closeThreadSearch,
        disabled: false,
        action: null,
      };
    if (top && (!search || menuSearching())) return null;
    if (
      !search &&
      (!innermostStance() || (reading?.exits && input !== focused() && !draftOf(input)))
    )
      return null;
    const exit = rows().find((entry) => entry.exit);
    return exit ? { ...exit, press: () => exit.press?.(null) } : null;
  };
  // A draft arriving in an empty field, or the last of it going, re-seats the row.
  function retype() {
    postureMoved = true;
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
  // completes (composing/surface.js, `standDown`). WebKit does not deliver a click
  // after this cancelled touch pointerdown, so the release owns the handoff, and claims
  // the click other engines deliver after it, which would land on the comment box the
  // release opened under the pointer, as on its Other responses. A Tab
  // through the row, or the runtime putting the caret there, writes on the page.
  // The words are kept against the press (focus.js, `pressing`), so a press that never
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
  // list, read before the edit changes what it could say. The user chose this on 17
  // October.
  field.addEventListener(
    "beforeinput",
    () => passErrors(sayable().map((error) => error.id)),
    { capture: true },
  );

  // ---------- readings ----------
  // The threads the page draws, this tab's sends among them while the saved ones are
  // still on their way, so a thread the user just started opens and lists at once. A
  // count is a reading of the saved inventory, so the mark and tabs say one only once
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
  const openCount = () => (inventoried() ? threadCounts(threads()).open : null);
  // Ordinary open state is implicit, and news is the row's mark (`data-lf-unread`),
  // which says New to assistive tech alone. Only an open thread is news (`isNews`), as
  // the On Me mark's dot counts it: the user chose (2026-10-25) that a resolved
  // thread's unread reply says nothing new. Rows name attention and drafts, and a
  // resolved thread says so with how long ago, as a Done line says its outcome and age.
  /** @param {ReturnType<typeof readThreads>["threads"][number]} thread */
  const threadStatus = (thread) => {
    const word = thread.resolved
      ? RESOLVED
      : threadAttention(thread, agentName())?.word;
    const draft = draftHasContent(replyContext(thread.key)) && "Draft";
    return html`${word ? voiced(word) : nothing}${thread.resolved?.ts ? html` ${panelAge(thread.resolved.ts)}` : nothing}${word && draft ? " · " : ""}${draft || nothing}`;
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
  //   the user chose that on 26 October over a heading of the opening words.
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
      rows: ".lf-fp-thread, .lf-fp-settled",
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
      at: ".lf-fp-version[data-lf-current] > .lf-fp-item",
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
  // Whether the menu stands, itself or under a list it leads to, so the leaf that opened
  // it closes it.
  const menuStands = () => trail.value.some((level) => level.view === "menu");
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
   *   drawnSections: Map<string, string> | null,
   *   onPageSeat: boolean,
   *   openItem: string | null,
   *   seatHeights: Map<string, number>,
   *   planShown: boolean,
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
    drawnSections: null,
    onPageSeat: false,
    openItem: null,
    seatHeights: new Map(),
    planShown: false,
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
  /** @param {PanelRoute} route @param {{replace?: boolean, reopen?: boolean, focus?: boolean}} [options] */
  function open(route, { replace = false, reopen = false, focus = true } = {}) {
    const before = trail.value.at(-1);
    if (before && routeKey(before) === routeKey(route) && !replace) {
      if (reopen) return;
      close();
      return;
    }
    if (route.thread && presentation && !presentation.primary) {
      openInPackage(route.thread, { focus });
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
    openLayer(host);
    transition(before, { focus });
  }
  // Where the page's package draws its conversations, a thread opens in its reader, in
  // its reply as a row's opening does (`focusView`), and the view it was chosen from
  // goes, uncovering the page.
  /** @param {string} key @param {{focus?: boolean, message?: string | null}} [options] */
  function openInPackage(key, { focus = true, message = null } = {}) {
    if (trail.value.length) close();
    void threadActions.open(threadByKey(key)?.key ?? key, {
      part: "reply",
      focus,
      message,
    });
  }
  // Opening a thread shows it at its first unread reply, as its card does, else at its
  // end, where the latest turn is. The user chose that on 23 October over opening at
  // the end with Next unread, which left a long unread reply's head, with its New,
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
  // in the page's order, or before it at the end, standing on its view so `r`, `t` and
  // Escape go on from there; or, with none left, back to the list. A thread opened from
  // elsewhere goes back to where it came from. Taking the resolve back, or the log
  // refusing it, opens the thread again (folding.js, `settleThread`).
  const openThreads = () =>
    inPageOrder(
      threads().filter((candidate) => !candidate.resolved),
      placedAt,
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
      if (next) {
        open({ view: "thread", thread: next.key }, { replace: true, focus: false });
        const view = shownView();
        if (view) focusDestination(view, "move");
      } else back();
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
  function close({ handedOn = false } = {}) {
    // Closing the view ends the writing posture too. A saved page draft keeps
    // its own posture; entering the field starts writing again.
    writing = false;
    const before = trail.value.at(-1);
    trail.value = [];
    searching = false;
    unfolded.clear();
    transition(before, { handedOn });
  }
  // A row's press puts away the view it stands in, the menu or a list it leads to, and
  // the command owns any navigation it causes. Hand back to the leaf, the menu's door,
  // before its command runs, so the pressed row going takes no one's focus to the body:
  // a layer the command opens records the leaf as where its close returns (focus.js,
  // `openLayer`), folding leaves the user on the leaf it folds to, and a command that
  // places the user elsewhere still does.
  /** @param {() => unknown} run */
  function putAwayThen(run) {
    const inside = currentLocationIn(host);
    close();
    if (inside) focusDestination(leaf, "return");
    run();
  }

  // ---------- motion: everything follows the box ----------
  // The box's layout changes in one step, whatever changed it: a view opening, a field
  // growing a line, more room, folding to the leaf. Everything the user sees then moves
  // from where it was drawn to where it stands, by one model (box-motion.js): the
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
  // covers reads as unseen (geometry.js, `declareCover`), and a landing stands clear of
  // its reach (`followBox`). It covers where its surface is drawn
  // (box-motion.js, `outline`): while the box moves, the card stands transparent at its
  // rest and the surface carries the panel from where it stood. The card's own box is
  // where that motion ends, which a landing about to show a place asks (`standsOver`).
  declareCover(
    host,
    () => following.outline(),
    () => card.getBoundingClientRect(),
  );
  // A send is the user's change joining the stream the box shows (box-motion.js,
  // "send"): the box reads where that stream stands before the send draws, and the
  // readings until the send's rendering settles carry it from there on the box's own
  // tween.
  function streamSend() {
    following.stream();
  }
  let writtenBand = 0;
  let bandFrame = 0;
  function followBox() {
    // How far the box reaches up from the window's foot, which the root's
    // `scroll-padding-bottom` keeps every landing clear of, with the gap above the box
    // and at least the foot's room (`--lf-foot-band`, base.css), so `m`, `t`, a Go-to
    // or an On Me row's Show lands what it reaches above an open view rather than
    // under it. The browser's own reveals read the same padding, and Leaf's landings
    // the band stated beside it (geometry.js, `stateFootBand`). CSS can't size the
    // root's padding from a fixed box in the chrome's shadow tree, so the box states
    // it, in pixels and never as a custom property (root-state.js).
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
      // (page-layout.js). The root's style is a page attribute the margin hears, and its
      // pass places an open thread card in the same delivery, resizing a box shallower
      // than any the delivery can still reach: a ResizeObserver loop. So the padding and
      // the news of the room wait for the frame; Leaf's own landings read the band
      // stated above at once.
      writtenBand = band;
      bandFrame ||= nextRender(() => {
        bandFrame = 0;
        setRuntimeRootStyle(root, "scroll-padding-bottom", `${writtenBand}px`);
        announceRoom();
      });
    }
    const compact = host.dataset.lfRest === "mark";
    const duration = compact
      ? foldMs()
      : performance.now() < viewMovingUntil && following.theirs() !== "send"
        ? viewResizeMs()
        : resizeMs();
    following.follow({ duration, easing: compact ? foldEase() : ease() }, compact);
  }

  // A view is as tall as what it holds, up to its cap (floating-panel.css,
  // `--lf-fp-view-height`); what does not fit scrolls inside it. A thread's view follows
  // its messages and every other fits what it shows (`VIEWS`); either way its top edge
  // moves, carrying its head line, while a list's tabs at its foot stay put. What a list
  // first holds is what it shows, and a message Leaf's reader has yet to draw into it is
  // not yet held. A thread's reader holds back any news that would move what is read
  // (thread/held-news.js) until the user asks for it. A reply the user sends grows the
  // view to show it, and news they open from the head line shows inside the view the
  // press holds (below).
  //
  // The agent's answer to the user's own last turn is the one news the reader hands the
  // view at once (`answersAtOnce`): the user is waiting for it. The view grows to hold
  // it, work under way and a reply streaming included, up to its cap: the field stays
  // put and the view's top edge rises, carrying its head line and the user's own turn
  // up with it. Past its cap the thread follows the answer into sight or says New reply
  // at the view's foot, the view being the box it names as its scroller
  // (thread/thread-card.js). The user
  // chose this growth (2026-10-14), the one case where news may carry what a view shows
  // without a gesture (`browser/AGENTS.md`, "The page holds still under the user's aim"), reversing the view
  // holding its height while the user waited (#2892), which left a short thread's
  // answer behind New reply in a view one message tall. Rejected then and now: holding
  // the answer behind the reader's "1 new reply", which left the reply the user waited
  // for unseen. Other news in an open thread is still held. A thread's view declares
  // that it stands on its foot (`data-lf-rises`), which the shift watch credits for
  // exactly this growth (tests/shift_watch.js, `appendGrowth`).
  // Whether this opening of a thread has shown Show on page (`onPageSeat`), whose seat
  // then stands while the view does, so a revision detaching the thread moves nothing
  // beside it.
  // A thread's view stands on its foot, so what grows in it carries its name, and all
  // the view holds, up the window. That is the growth news and the user's own turns
  // make (`answersAtOnce`), but a press keeps what it pressed under the pointer. So where
  // what a press in the view grows would carry the pressed control away, as Full quote,
  // Show on a fold that opens below it, or a rewrite's pencil would, the view holds the
  // height it stood at as the press came (`judgePress`, before the frame shows the
  // growth) until the user's next turn, and what the press grew goes on inside the
  // view, revealed by scrolling. A press whose growth leaves it in place, as Show on
  // progress, which opens above it, holds nothing, so the view grows to show what
  // opened; nor does a press that grows nothing, so an answer the user waits for still
  // grows the view. A press on the head line, which every growth carries, holds the
  // view whatever it grows (below). The
  // caret in a rewrite, which a key can open from the field, holds the view while it
  // stays there, so typing carries none of the rewrite's own presses, the rewrite's
  // lower lines revealed by scrolling (thread/reply-landing.js, `revealEditor`). A card
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
  // every press into it, a hold whose release its preview took included (preview.js), so
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
  // how tall the view and what it holds stood, and its hold on screen (user-place.js,
  // `holdPlace`). Once what the press changed has drawn, after the press's own
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
      keep: holdPlace(node),
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
  // Each row standing Threads draws, by its thread's key, with its section
  // (`drawnSections`); null while no list stands, so the next paint draws every row
  // where it now belongs (`threadsListing`).
  // The keys of the rows a notice's press lands on, while its paint draws them
  // (`showJoined`).
  /** @type {Set<string> | null} */
  let landingKeys = null;
  // The outlet the view's fit watches (`paintNow`).
  /** @type {HTMLElement | null} */
  let fitted = null;
  function refit() {
    opening.room = null;
    opening.drawnSections = null;
    viewMovingUntil = performance.now() + viewResizeMs();
    if (refitting) return;
    refitting = true;
    nextRender(() => {
      refitting = false;
      if (holdRoom()) paint();
    });
  }
  /** @param {PanelRoute | null | undefined} before @param {{focus?: boolean, handedOn?: boolean}} [options] */
  function transition(before, { focus = true, handedOn = false } = {}) {
    const after = trail.value.at(-1);
    postureMoved = true;
    // The thread the user is in as the change begins, on the page or in the panel,
    // read before the paint that may take its view away.
    const stoodIn = drawnThreadId(closestAcross(focused(), THREAD));
    const reading = [before, after].some((route) => route?.thread);
    if (after?.view !== "queue") seated = null;
    const changed =
      (before ? routeKey(before) : null) !== (after ? routeKey(after) : null);
    if (changed) opening = freshOpening();
    // Taking the panel away from a thread ends the editing session of its reply, as a
    // press elsewhere does (thread/replies.js), keeping the draft: the field no longer
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
      if (focus) focusView(after, drawn, stoodIn);
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
    if (focus) focusView(after, drawn, stoodIn);
  }
  /** @param {PanelRoute | undefined} route @param {PromiseLike<unknown> | null} drawn @param {string | null} [stoodIn] */
  function focusView(route, drawn, stoodIn = null) {
    if (!route) return;
    const view = shownView();
    // A thread opens with the caret in its reply, as the one field means, once Leaf's
    // reader has drawn the reply there, from a list's row by a key as by a press
    // (thread/focus.js, `openingPart`, says why a row differs from a card); one taking
    // no reply, as a resolved thread does, holds focus itself, so the user is in it. A
    // list stands on the row of the thread the user was in, where it lists it, as `g T`
    // from a thread does; else, opened by a key, in the panel or on the page as `g T`
    // is, on its first row, or its first control where it has none, or itself where it
    // holds neither, as an empty Threads does, so the key's landing wears a ring; opened
    // by a pointer, it holds focus itself. The user chose this on 31 October, after
    // `g T` from the page left focus on the list's view, where nothing showed it and
    // Enter went nowhere seen. A list that declares a row it opens at, such as the
    // version the page shows in Versions, brings that row into view by either route, and
    // a key lands on it, as the user reopening the list from there expects to see it.
    if (route.thread) {
      // A finger opening a thread reads it first, standing in the view, whose box
      // raises no keyboard; the keyboard rises when they tap in.
      const intent = retainUserIntent();
      void Promise.resolve(drawn).then(() => {
        const at = shownView();
        const target = at && ((!coarsePointer.matches && viewParts.reply(at)) || at);
        if (target && trail.value.at(-1) === route && intent())
          focusDestination(target, "move");
      });
      return;
    }
    const rows = listRows();
    const stoodRow =
      stoodIn &&
      rows.find((row) => threadByKey(row.getAttribute("data-lf-key"))?.id === stoodIn);
    const declared = viewOf(route).at;
    const at = declared ? view?.querySelector(declared) : null;
    const target =
      stoodRow ||
      (pressLed()
        ? view
        : (at ?? rows[0] ?? view?.querySelector("button, input") ?? view));
    // The row of the thread the user was in takes them back where they came from.
    if (target) focusDestination(target, target === stoodRow ? "return" : "move");
    if (at) scrollIntoView(at, { block: "nearest", within: view });
  }

  // ---------- the leaf's menu ----------
  // A row that opens a list of its own ends in a chevron, past its value, so the user
  // knows before pressing that it leads further rather than acting.
  /** @param {unknown} label @param {unknown} end @param {(event: MouseEvent) => unknown} press
   * @param {{urgent?: boolean, disabled?: boolean, role?: string | null, row?: string | null,
   * opens?: boolean, title?: string | null, current?: boolean}} [options] */
  const menuItem = (
    label,
    end,
    press,
    {
      urgent = false,
      disabled = false,
      row = null,
      opens = false,
      title = null,
      current = false,
    } = {},
  ) =>
    html`<button
      type="button"
      data-lf-row=${row ?? nothing}
      .lfPreview=${() => (title ? { detail: [title] } : null)}
      ${offeredAction("row", "lf-fp-item")}
      aria-current=${current ? "true" : nothing}
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
  // back returns there. Folding takes the menu away with the rest of the panel, as its
  // key does (`setRest`), so the panel is drawn once, folded, rather than first open
  // and then folded. Any other row runs its command.
  /** @param {ReturnType<typeof pageControls>[number]} entry */
  function rowFor(entry) {
    if (entry.copies) return copyItem(entry);
    const route = OWN_VIEWS.find((route) => route.view === entry.key) ?? null;
    return menuItem(
      entry.label,
      rowEnd(entry),
      () => {
        if (route) open(route);
        else if (entry.key === `command:${FOLD}`) entry.press?.(null);
        else putAwayThen(() => entry.press?.(heldCurrentLocation));
      },
      {
        urgent: Boolean(entry.urgent),
        disabled: entry.disabled,
        row: entry.key,
        opens: Boolean(route && viewOf(route).over?.includes("menu")),
        title: entry.title || null,
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
    return html`${
        errors.length
          ? menuItem(
              "Errors",
              kind(errors.length),
              () => {
                open({ view: "errors", errors });
                seeErrors();
              },
              { opens: true, row: "errors" },
            )
          : nothing
      }${lists.map((group) =>
        menuItem(group.label, nothing, () => open({ view: "group", group }), {
          opens: true,
          row: `group:${group.name}`,
        }),
      )}${reached.map(rowFor)}${named.map((thread) =>
        menuItem(
          threadName(thread),
          kind("Thread"),
          () => open({ view: "thread", thread: thread.key }),
          { row: `thread:${thread.key}` },
        ),
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
              draw: (/** @type {boolean} */ gone) =>
                menuItem(
                  "Errors",
                  html`<span class="lf-fp-value">${errors.length}</span>`,
                  () => {
                    open({ view: "errors", errors });
                    seeErrors();
                  },
                  {
                    opens: true,
                    urgent: errors.some((error) => !error.seen),
                    disabled: gone,
                    row: "errors",
                  },
                ),
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
    return html`<div class="lf-fp-state" ?data-lf-held-lines=${held !== null}>
        ${part("summary", statusParts(summaryParts))}${part("explain", explains)}
      </div>
      ${seats.map(({ key, draw }) => now.get(key)?.draw(false) ?? draw(true))}`;
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
  // its error points here to read (version.js, `holdFailedSave`); then the versions
  // the picker lists, each a press that travels there and says the note its stamp gave
  // it after its name, cut to the row and whole on hover, or whole under the name for a
  // pointer that can't hover (floating-panel.css). A column at the rows' end
  // holds Compare where the picker offers it and Showing for the version shown, so
  // the two words line up. Showing stands outside the press, as Compare does, over
  // the row's end; the press carries it as `aria-current`.
  /** @param {ReturnType<typeof versionsReading>["rows"][number]} entry */
  const showVersion = (entry) => putAwayThen(() => versionPicker.activate(entry));
  function versionsList() {
    const { rows: versions, picker, selection, latest } = versionsReading();
    return html`
      ${
        latest.failed
          ? html`<div class="lf-fp-failed" role="none">
              <b>${latest.label}</b>
              <p class="lf-fp-failed-error" data-lf-scroll>${latest.error}</p>
            </div>`
          : nothing
      }
      <div class="lf-fp-versions lf-rows" role="none">
        ${repeat(
          versions,
          (entry) =>
            `${entry.version === null ? "draft" : "version"}:${entry.revision}`,
          (entry) =>
            html`<div
              class="lf-fp-version"
              role="none"
              ?data-lf-current=${entry.current}
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
                { current: entry.current },
              )}${
                entry.current
                  ? html`<span class="lf-fp-showing" aria-hidden="true">Showing</span>`
                  : nothing
              }${
                entry.comparable
                  ? html`<button
                      type="button"
                      ${offeredAction("word", "lf-fp-compare")}
                      aria-pressed=${String(
                        selection.on && selection.base === entry.revision,
                      )}
                      aria-label=${`Compare with ${entry.name}`}
                      @click=${() =>
                        putAwayThen(() => versionPicker.compare(entry.version))}
                    >
                      Compare
                    </button>`
                  : nothing
              }
            </div>`,
        )}
      </div>
      ${
        versions.length
          ? nothing
          : html`<p class="lf-rows-empty" role="none">Showing ${picker.token}</p>`
      }
    `;
  }

  // The errors the user has met, newest first, each saying what failed and when, with
  // a press that dismisses it, whose name carries both, since a list's keys reach only
  // its presses. The list keeps the reading it opened with: new errors wait behind the
  // leaf's dot until reopening. An error whose cause ends
  // clears its words but keeps its space, so the next control stays under the reader.
  // A dismissal removes that space by the user's gesture and leaves them on the next
  // error's press, or on the way back once none is left.
  /** @param {RouteFor<"errors">} route */
  function errorsList({ errors }) {
    const live = new Set(errorsReading().map((error) => error.id));
    if (!errors.length)
      return html`<p class="lf-rows-empty" role="none">No errors.</p>`;
    /** @param {number | null} dismissed */
    const movePast = (dismissed) => {
      const presses = [...stage.querySelectorAll(".lf-fp-error button")];
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
    const currentLocation = focused()?.closest(".lf-fp-error");
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
          role="none"
          style=${live.has(error.id) ? nothing : "visibility: hidden"}
        >
          <p class="lf-fp-error-words" aria-hidden="true">
            <b>${error.message}</b><span class="lf-fp-note">${clock(error.at)}</span>
          </p>
          <button
            type="button"
            ${offeredAction("word", "lf-fp-dismiss")}
            ?disabled=${!live.has(error.id)}
            aria-label=${`Dismiss: ${error.message}, ${clock(error.at)}`}
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

  // The rows read in the page's order, the one the `t` walk steps through
  // (thread/placement.js), so each thread stands among its passage's neighbours: the
  // open threads, then the resolved ones folded under Resolved (`settledHeading`), as
  // what left On Me stands under Done, each unread row marked and a drafted one saying
  // Draft. The user chose this on 25
  // October, with Threads becoming the On view's tab, over Open, Unread, Drafts and
  // Resolved filters, which a second row of tabs would have had to hold. A search reads
  // every thread's name, its messages and summaries as they read, and the words it is
  // about, as its head quotes them (`threadPassage`), and lists matches as one list.
  function shownThreads() {
    const words = query.trim().toLowerCase();
    const shown = words
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
    return inPageOrder(shown, placedAt);
  }
  // A row joining Threads while the list stands, a thread the agent starts, or a row
  // changing section, one a reply reopens or one resolved elsewhere, would move the
  // rows the user reads there (`browser/AGENTS.md`, "News moves what the reader reads
  // only in the thread they are in"). So the standing list draws each row in the
  // section it drew it in, and a thread new to it not at all, and says what joined or moved in the notice a
  // thread's held news uses (thread/held-news.js, `newsNotice`) until the user
  // presses it, which lets the list settle and lands on the first row it names. The
  // notice stands over the list, in the view's head, which grows the panel upward by
  // its line so no row moves, as a feed says "2 new posts" over its top. The user chose
  // that on 27 October over the notice in the controls after the tabs, which fill the
  // start where a thread's held news stands and left it "1 …+1" at a phone's width,
  // and over the notice in the held row's own place, which a long list scrolls out of
  // sight. The browser reads
  // nothing ahead of the server: a held row draws the thread as the server now reads
  // it, in its old place. A row the user's own gesture moves, as their resolve or its
  // Undo, moves at once (`gesturedOn`), and a press that changes what the list shows,
  // a tab or a search, or the next opening, draws it whole (`refit`, `transition`).
  // Rejected (2026-10-25, #3883 before the single list): holding only rows that would
  // land among the rows in sight, by their geometry, which a list whose rows change
  // section rather than join would have held none of.
  // The rows the list draws, each in its section, and the threads joining or moving
  // that it holds: `was` the section a moving row still stands in, null for one new.
  function threadsListing() {
    const searched = Boolean(query.trim());
    const rows = [];
    const joined = [];
    for (const thread of shownThreads()) {
      const now = searched ? "found" : thread.resolved ? "resolved" : "open";
      const was = opening.drawnSections
        ? (opening.drawnSections.get(thread.key) ?? null)
        : now;
      if (was === now || gesturedOn(thread)) rows.push({ thread, section: now });
      else {
        joined.push({ thread, was, now });
        if (was) rows.push({ thread, section: was });
      }
    }
    return { rows, joined, searched };
  }
  // After a paint: what the standing list drew, which the next paint holds to.
  function noteDrawnSections() {
    opening.drawnSections =
      showing({ view: "threads" }) && inventoried()
        ? new Map(
            threadsListing().rows.map(({ thread, section }) => [thread.key, section]),
          )
        : null;
  }
  // What the notice says, a fact for each way a row joined.
  /** @param {ReturnType<typeof threadsListing>["joined"]} joined */
  function joinedFacts(joined) {
    /** @param {string} kind @param {string} one @param {string} many */
    const fact = (kind, one, many) => {
      const count = joined.filter(
        ({ was, now }) => (was === null ? "new" : now) === kind,
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
    const keys = new Set(joined.map(({ thread }) => thread.key));
    const carried = focused() === joinedNotice.node || inList();
    // Where only resolved threads joined, the row it lands on stands under Resolved,
    // which unfolds to show it (`settledHeading`).
    if (joined.every(({ now }) => now === "resolved") && !unfolded.has("resolved")) {
      unfolded.add("resolved");
      refit();
    }
    opening.drawnSections = null;
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
    const facts = joinedFacts(joined);
    if (!facts.length) return nothing;
    joinedNotice.set({
      text: newsCount(joined.length),
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
  // band's does. The user chose the fold on 27 October over the newest three resolved
  // with the rest behind a row, which put a second order in a list read in the page's,
  // and over resolved threads only searched for, which left them nothing to browse.
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
  function threadsView() {
    const { rows, searched } = threadsListing();
    const listed = rows
      .filter(({ section }) => section !== "resolved")
      .map(({ thread }) => thread);
    const resolved = rows
      .filter(({ section }) => section === "resolved")
      .map(({ thread }) => thread);
    // A row previews its thread as the thread's margin entry and mark do
    // (`threadPreview`), leaving out to the keyboard the word its status already says.
    /** @param {ReturnType<typeof readThreads>["threads"][number]} thread */
    const row = (thread) => {
      const attention = threadAttention(thread, agentName());
      return html`<button
        type="button"
        ${offeredAction("row", "lf-fp-thread")}
        data-lf-key=${thread.key}
        ?data-lf-unread=${isNews(thread)}
        ?data-lf-resolved=${thread.resolved}
        data-lf-turn=${attention?.kind === "needs_user" ? "user" : nothing}
        .lfPreview=${(/** @type {import("./preview.js").Route} */ route) =>
          threadPreview(
            [thread],
            route === "focus" && attention ? wordsText(attention.word) : null,
          )}
        @click=${() => open({ view: "thread", thread: thread.key })}
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
      ${
        listed.length || !inventoried()
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
  // registers as the page's primary thread presentation (application.js,
  // `registerChromeThreadPresentation`), yielding to one the page's package registers, in
  // whose reader its threads then open, and gives the open thread an outlet here. Leaf
  // draws the thread there as a card on the page draws it (thread/thread-card.js,
  // `ThreadView`): the words it is about, its to-dos, and its messages, progress folded
  // behind the answer that completed it, work under way as the dim working message, New
  // in each unread reply's head, with their reactions, rewrites and agent-authored
  // widgets. The user chose that (2026-10-19) over every message at full size, which
  // stood each progress step as a reply and marked nothing unread. The thread stands its
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
  // notice among the thread's presses on 16 October over the notice at the end of the
  // first message's head, cut to 5rem there ("2 new rep…"), and over the news joining
  // New reply at the view's foot. Its Resolve ends the thread's presses, before Close.
  // While the thread holds news, its Resolve and the field's words say the thread as
  // its view draws it, held news included, as a card's do, so the three change together
  // when the user shows the news. The panel took the card's rule on 4 November; until
  // then Resolve and the field said the thread as it stood, Reopen and "Reply to
  // reopen" beside a notice still holding the agent's Resolve.
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
  /** @param {import("./thread/primary-reader.js").PrimaryCollection} collection @param {import("./thread/primary-reader.js").NominationParts} parts */
  function nominate(collection, parts) {
    const top = trail.value.at(-1);
    if (top) viewOf(top).nominate?.(top, collection, parts);
  }
  // On draws each question asked in words as its message, in its card's outlet.
  /** @param {import("./thread/primary-reader.js").PrimaryCollection} collection @param {import("./thread/primary-reader.js").NominationParts} parts */
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
  /** @param {RouteFor<"thread">} route @param {import("./thread/primary-reader.js").PrimaryCollection} collection @param {import("./thread/primary-reader.js").NominationParts} parts */
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
      // here (thread/folding.js); reopening lands in the reply in the field, as the
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
  // as its thread's own (thread/selectors.js,
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
  /** @type {import("./thread/selectors.js").ThreadParts} */
  const viewParts = Object.freeze({
    reply: (view) => {
      return openIn(view) ? replyInput() : null;
    },
    settlement: (view) =>
      openIn(view)
        ? head.querySelector(".lf-fp-thread-controls :is(.lf-resolve, .lf-reopen)")
        : null,
    whole: (view) => (openIn(view) ? openView() : null),
  });
  /** @param {Element | undefined} view */
  const declareView = (view) => view && declareThreadParts(view, viewParts);
  // Each view scrolls what it holds, so each is a reading region while it stands, and a
  // landing in it, as a rewrite opening on a message above its top, scrolls the view
  // rather than the page its fixed box stands still over (reading-regions.js).
  //
  // A thread's view stands on its foot, beside the field, and keeps what stands there
  // as the room the box gives it changes, read back or not (scrolling.js, `keepFoot`).
  // Where the box reaches the window's top, a line the field gains takes its room from
  // the view rather than carrying the view up, so the view gives way at its top and its
  // words move up with the field, as they do while the box has room. The user asked for
  // this on 31 October, when a long reply covered the agent's last line, the view having
  // kept its scroll and given way at its foot.
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
  // closes. The user chose open cards (2026-10-25), so answering what they already
  // know about takes one press each, over one line per item that a press opened, which
  // fitted more items and hid every answer behind a press.
  //
  // On <agent> is the agent's work list: in hand, queued and done, a line each with its
  // stage and age, the plan's progress at the view's foot disclosing its steps. The
  // user chose this (2026-10-21) over saying how much in the status alone and over a
  // trace of the turn, which needs facts the served state lacks; it replaced the Plan
  // tab. A chooser shows it as this List or as a Summary in sentences: the user chose a
  // menu of layouts for now, to live with several before settling one, against their
  // rule that a layout is not picked from a menu.
  //
  // The opening keeps the item standing open, by its key (`openItem`), and the height
  // each card first stood at, which it keeps while open, so an answer that shortens it
  // moves nothing below (`seatHeights`); and whether the plan's steps stand over On
  // <agent>'s list (`planShown`). The items On Me seats, and what each card carries,
  // stay out of it: a view opened over On clears them, and On Me fading out under that
  // view seats again what still waits on the user, so going back to On keeps those in
  // their seats, one answered in that view included.
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
  // A press that changes what the list shows, a tab, a grouping, a layout or the plan
  // disclosed over it, shows it from its top, where the plan and the first group
  // stand, rather than where the view stood scrolled in what it showed before, which
  // scroll anchoring would otherwise keep in view.
  let fromTop = false;
  function showFromTop() {
    if (!fromTop) return;
    fromTop = false;
    const view = shownView();
    if (view && trail.value.at(-1)?.view === "queue")
      moveScrollerBy(view, -view.scrollTop);
  }
  // The On Me door, as `g M` presses it: the view on the user's list, turned to it where
  // the view shows another tab, else opened or closed.
  function openOnMe() {
    const turned = chooseQueueTab("you");
    if (turned && showing({ view: "queue" })) paint();
    else open({ view: "queue" });
  }
  // The mark opens On Me, or Threads where nothing waits on the user but a reply they
  // have not read, as the Threads mark it replaced opened on its Unread filter. It
  // stands only while no view does, so it never closes one; the seat's ✕ does that.
  function pressMark() {
    if (!onUserCount() && newCount()) {
      query = "";
      refit();
      open({ view: "threads" });
    } else openOnMe();
  }
  // An On list's empty text (queues.js, `emptyOnList`), a sentence but for the
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
  // taken back (undo.js).
  /** @param {import("./framework/application.js").ObligationRecord} item */
  const answerGesture = (item) => {
    const id = item?.answer?.event?.id ?? item?.answer?.event;
    if (!id) return null;
    const entry = runtime.undo.find(
      ({ event }) => event.id === id || event.attempt === id,
    );
    return entry?.event ?? null;
  };
  /** @param {string} tab */
  const tabLabel = (tab) => onList(tab === "agent" ? agentName() : "me");
  // The stop the `m` walk stands on while the field says its position
  // (keyboard/status-context.js): its row in On Me wears the ring a focused row
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
  // The stop the walk reached stands at its ringed card while the panel hides it: On me
  // stays open over the stop it lists (`clearFor`), and a stop at the page's foot can't
  // be scrolled clear of it, so the card is where the user sees where they are, and a
  // key pressed there acts at the stop rather than letting it go (user-place.js,
  // `focusPlace`). A stop in sight is its own place, which a reading keeps still
  // (user-place.js, `holdUserPlace`).
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
  // and the view fits what it then shows. The user chose the symbol (2026-10-25) over
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
  const PLAN_STATES = Object.freeze({
    open: "Not started",
    working: "Under way",
    done: "Done",
    failed: "Failed",
    dropped: "Dropped",
  });
  const PLAN_MARKS = Object.freeze({
    open: null,
    done: "check",
    working: "activity",
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
  /** @param {import("../types/contract.js").ServedPlanStep} step @returns {ReturnType<typeof html>} */
  function planStep(step) {
    const mark = PLAN_MARKS[step.state];
    return html`<li class="lf-fp-plan-step" data-lf-state=${step.state}>
      <span class="lf-fp-plan-mark" role="img" aria-label=${PLAN_STATES[step.state]}
        >${mark ? iconTemplate(mark, "lf-action-icon") : nothing}</span
      ><span class="lf-fp-plan-title">${step.title ?? ""}</span>${
        step.owner === "user" && step.state === "open"
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
          : step.state === "working" && step.since
            ? panelAge(step.since, { face: "lf-fp-plan-time" })
            : nothing
      }${
        step.running
          ? html`<span class="lf-fp-plan-line">${step.running.text}</span>`
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
  const planCards = () =>
    (readPlan()?.steps ?? []).map(
      (goal) =>
        html`<section class="lf-fp-plan">
          <h3 class="lf-fp-plan-goal">
            <span>${goal.title ?? ""}</span
            ><span class="lf-fp-plan-count">${goal.done} of ${goal.total}</span>
          </h3>
          <ol class="lf-fp-plan-steps">
            ${goal.steps.map(planStep)}
          </ol>
        </section>`,
    );
  // The plan's head at On <agent>'s foot: how far it has come, which discloses its
  // steps over the list. It stands among the controls, which hold still as the view
  // grows from its top edge, so the press moves nothing under the pointer.
  /** @param {{done: number, total: number}} progress */
  const planHead = ({ done, total }) =>
    html`<button
      type="button"
      ${offeredAction("word", "lf-fp-plan-head")}
      aria-expanded=${String(opening.planShown)}
      @click=${() => {
        opening.planShown = !opening.planShown;
        refit();
        fromTop = opening.planShown;
        paint();
      }}
    >
      Plan ${done} of ${total}<span
        class="lf-fp-plan-bar"
        style=${`--lf-fp-plan-done: ${total ? (100 * done) / total : 0}%`}
      ></span>
    </button>`;

  // ---------- an item's line, and its card ----------
  // What the agent's list calls an item: a to-do, or the reply or answer it owes.
  /** @typedef {ReturnType<typeof readQueues>["on_user"][number] | ReturnType<typeof readQueues>["done"][number]} PanelQueueItem */
  /** @typedef {keyof ReturnType<typeof queueLists>} PanelQueueList */
  /** @param {PanelQueueItem} item */
  const agentNoun = (item) =>
    item.kind === "todo" ? "To-do" : capitalized(itemNoun(item));
  // What the agent is doing about an item on its list: the word for the stage it
  // stands at, the line its last step wrote, each said by whoever says it, and since
  // when.
  /** @param {PanelQueueItem} item */
  const workOn = (item) =>
    item.kind === "todo"
      ? {
          word: todoWord(item.todo.running),
          line: item.todo.running ? agentSays(item.todo.running.text) : null,
          since: item.todo.running?.ts ?? item.todo.ts,
        }
      : {
          word: workflowWord(item.workflow, agentName()),
          line: workflowStep(item.workflow, agentName()),
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
    if (
      opening.openItem &&
      !items.some((item) => queueItemKey(item) === opening.openItem)
    )
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
  function fitOpened() {
    if (!fitting) return;
    fitting = false;
    const view = shownView();
    if (!view || opening.room === null || trail.value.at(-1)?.view !== "queue") return;
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
  /** @param {PanelQueueItem} item @param {PanelQueueList} list
   * @param {{card?: boolean, says?: "place" | "kind" | null, leads?: boolean,
   * also?: readonly string[] | undefined}} [options] */
  function onItemCard(
    item,
    list,
    { card = false, says = null, leads = true, also = item.also } = {},
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
    const message =
      asking && thread && presentation?.primary !== false
        ? { thread, reading: asking }
        : null;
    const title = message
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
    const waiting = carried.find(
      ({ record: other }) => other.status === "open" && other.next_actor === "user",
    );
    // Where the thread's name stands for the item, it reads as Threads names the thread
    // (`threadHeading`).
    const heading =
      thread && title === threadName(thread) ? threadHeading(thread) : title;
    const answered = record && record.status !== "open";
    const choices =
      record && !answered && record.source.kind === "widget" && !inWords
        ? obligationView.choicesOf(record)
        : null;
    const gesture = answered ? answerGesture(record) : null;
    const discuss = conversation
      ? html`<button
          type="button"
          ${offeredAction("word", "lf-fp-discuss")}
          @click=${() => open({ view: "thread", thread: conversation.key })}
        >
          Discuss
        </button>`
      : nothing;
    // Show takes the user to the item where `m` would, by the walk's own arrival
    // (queue-walk.js, `arriveAtItem`), wherever that leads anywhere but this card. On a
    // card it stands at the end of the card's first line, as a thread's Show on page
    // stands on its head line, beside what it shows and where an answer moves it
    // nowhere; on a line opened into its card, at the end of its answers. The user chose
    // this on 4 November over the end of a card's answers, where under a long message it
    // stood far from the question it shows. The arrival may open a thread in this
    // panel; keep its current route until the destination decides, then close only for
    // page travel.
    // A card drawing the message it asks (`message`) holds that message's drawing ahead
    // of the page's (thread/messages.js, `authoredRank`), so an arrival with On Me
    // standing landed in this card, and the user fell to the page as it closed. Where
    // the thread stands on the page, On Me goes first and the arrival lands in its card.
    const show = arrivesAt(item)
      ? html`<button
          type="button"
          ${offeredAction("symbol", "lf-fp-show", undefined, { action: "show" })}
          @click=${() => {
            const route = trail.value.at(-1);
            if (message && placedAt(message.thread.id)?.place) close();
            void queueActions.open(queueItemKey(item)).then((arrived) => {
              if (arrived && trail.value.at(-1) === route) close();
            });
          }}
        ></button>`
      : nothing;
    let answers;
    let discussHere = true;
    // A finished item says how it ended and when: on its card, where its answers
    // stood, and on a line at the line's end, so the line's card holds Discuss.
    if ("state" in item && !record)
      answers = card
        ? html`<span class="lf-fp-said"
            >${voiced(itemOutcome(item))}${
              item.ended ? html` ${panelAge(item.ended, { face: null })}` : nothing
            }</span
          >`
        : nothing;
    // What the agent is doing about it: the line its last step wrote, as the status
    // says it of the whole page, else the stage it stands at.
    else if (list !== "you" && !answered)
      answers = html`<span class="lf-fp-said"
        >${voiced(workOn(item).line ?? "")}</span
      >`;
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
                @click=${() => open({ view: "thread", thread: waiting.thread.key })}
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
        @click=${() => open({ view: "thread", thread: thread.key })}
      >
        Reply
      </button>`;
    } else answers = nothing;
    const key = queueItemKey(item);
    const opened = opening.openItem === key;
    const stop = queueStop(item);
    const mine = item.owner === "user";
    // A line says what its item is: what waits on the user in the walk's word for it,
    // so a suggestion says Insertion, Deletion or Rewrite as the field does after `m`,
    // and the agent's as the reply, answer or to-do it owes. A line of the user's under
    // Done names none, since how it ended, such as the answer it took, says what it
    // was.
    const kind = mine ? (list === "done" ? "" : stop.noun) : agentNoun(item);
    const where = says === "place" ? "" : onMe.place(item);
    const walked = leads && queueTab === "you" && walkedStop() === stop.key;
    // On Me's card says only where its item stands over its question, where its band
    // doesn't say it, and keeps that once it is answered, so the answer moves nothing.
    // It names no kind: its question and answers say what it is. The user chose that
    // on 26 October 2026 over a kind word before every card's place, which repeated
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
    // its card is folded, else the part of the page it stands in.
    /** @type {unknown} */
    let end = nothing;
    if (list === "agent") {
      const work = workOn(item);
      end = html`<span class="lf-fp-value"
        >${voiced(work.word ?? "")}${work.since ? html` ${panelAge(work.since)}` : nothing}</span
      >`;
    } else if ("state" in item && !record)
      end = html`<span class="lf-fp-value"
        >${voiced(itemOutcome(item))}${item.ended ? html` ${panelAge(item.ended)}` : nothing}</span
      >`;
    else if (answered && !opened)
      end = html`<span class="lf-fp-value">${voiced(obligationEnding(record))}</span>`;
    else if (where) end = html`<span class="lf-fp-value">${where}</span>`;
    const name = heading || (thread ? threadHeading(thread) : queueTitle(item));
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
        @click=${() => toggleItem(key)}
      >
        <span class="lf-fp-value lf-fp-on-noun lf-row-lead">${kind}</span
        ><span class="lf-fp-on-says lf-row-main"
          ><span class="lf-fp-label">${name}</span>${end}</span
        >
      </button>
      ${
        opened
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
              <div class="lf-fp-answers">
                ${answers}${discussHere ? discuss : nothing}${show}
              </div>
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
  // on the row carrying its key (`paintNow`, focus.js `holdFocus`).
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
      ${bandedGroups(groups, queueItemKey, line)}
    </div>`;
  }

  // A thread's view, its head and its reply stand at what the thread is about, and an On
  // card at the obligation it shows (current-target.js, `declareSide`), as the side
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
    const byKey = new Map(all.map((item) => [queueItemKey(item), item]));
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
      const key = queueItemKey(item);
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
      (seated ?? []).flatMap((item) => carrying.get(queueItemKey(item)) ?? []),
    );
    const retained = (seated ?? []).flatMap((previous) => {
      const current = byKey.get(queueItemKey(previous));
      return current ? [current] : [];
    });
    const retainedKeys = new Set(retained.map(queueItemKey));
    const items = [
      ...retained,
      ...lists.you.filter(
        (item) => !retainedKeys.has(queueItemKey(item)) && !carried.has(item.id),
      ),
    ];
    seated = items;
    const seatedKeys = new Set(items.map(queueItemKey));
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
    const held = new Set(
      items.flatMap((item) => carrying.get(queueItemKey(item)) ?? []),
    );
    const finished = lists.done.filter(
      (item) => !seatedKeys.has(queueItemKey(item)) && !held.has(item.id),
    );
    // A group counts what still waits in it; the cards answered here keep their seats,
    // so a group keeps its band while the view stands. Every group has its band, one
    // card alone in it included, so the list has one shape whatever its groups hold: the
    // user chose that on 3 November 2026 with the bands (`groupedItems`), reversing their
    // choice of 22 October that only a group of two or more had a heading, a card alone
    // saying its group's name over its place, which they made when a heading was a line
    // of muted words that spent a card's room and grouped nothing. What left the list
    // stands folded under Done, a line each once unfolded, as Threads' Resolved does.
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
            ? onItemCard(item, "done")
            : onItemCard(item, listOf(item), {
                card: true,
                says,
                leads: group.leads.has(item),
                also: carrying.get(queueItemKey(item)),
              }),
      ),
    )}`;
  }
  // On <agent>: the plan's steps while its head discloses them, then the work as the
  // user chose to see it, a list or a summary. Its groups are states, not places: what
  // the agent has in hand, what is up next, and what it finished, folded under Done.
  /** @param {ReturnType<typeof queueLists>} lists */
  function workView(lists) {
    const inHand = lists.agent.filter((item) => item.live);
    const queued = lists.agent.filter((item) => !item.live);
    const groups = [
      { key: "in-hand", title: "In hand", items: inHand },
      { key: "queued", title: "Up next", items: queued },
      { key: "done:agent", title: "Done", items: lists.done, folds: true },
    ].filter((group) => group.items.length);
    forgetOpened(
      layoutOf() === "summary"
        ? []
        : [...lists.agent, ...(unfolded.has("done:agent") ? lists.done : [])],
    );
    return html`${opening.planShown ? planCards() : nothing}${
      layoutOf() === "summary"
        ? workSummary(inHand, queued, lists.done)
        : html`${
            inHand.length || queued.length
              ? nothing
              : html`<p class="lf-rows-empty">${emptyListText(agentName())}</p>`
          }${groupedItems(groups, (item, group) =>
            onItemCard(item, group.folds ? "done" : "agent"),
          )}`
    }`;
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
                last.ended
                  ? html`${voiced(leafSays(", "))}${panelAge(last.ended, { spoken: true, long: true })}`
                  : nothing
              }${voiced(leafSays("."))}
            </p>`
          : nothing
      }
    </div>`;
  }

  // ---------- All pages: the pages live on this machine ----------
  // Each page served on this machine now, this one first (live-leaves.js, `leavesRows`):
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
  // count, as On Me nearly always does.
  /** @template {string} T @param {readonly T[]} names @param {T} current
   * @param {(name: T) => string} label @param {(name: T) => unknown} choose
   * @param {(name: T) => number | null} count */
  const tabs = (names, current, label, choose, count) =>
    html`<div class="lf-fp-filters" data-lf-scroll role="group" aria-label="Show">
      ${names.map((name) => {
        const counted = count(name);
        return html`<button
          type="button"
          ${offeredAction("word", "lf-fp-tab")}
          aria-pressed=${String(current === name)}
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
  // in its place (`onTab`). The user chose the menu as the first tab on 30 October,
  // over a menu of its own standing over the leaf, which reached neither list nor
  // Threads; the leaf opens the view on it.
  const TAB_LABELS = Object.freeze({ menu: "Menu", threads: "Threads" });
  /** @param {"menu" | "you" | "agent" | "threads"} current */
  function onTabs(current) {
    const lists = queueLists();
    // A list is counted once the server's reading is in, as Threads is (`openCount`),
    // so no tab says 0 of a list the page can't read yet or offline.
    const counted = readQueues().phase === "ready";
    return tabs(
      ["menu", "you", "agent", "threads"],
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
    const progress = queueTab === "agent" ? planProgress() : null;
    // The view's chooser follows its tabs, with the plan's head before it on On <agent>.
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
          : html`${progress ? planHead(progress) : nothing}${chooser({
              label: `Show On ${agentName()} as`,
              values: AGENT_LAYOUTS,
              name: capitalized,
              current: layoutOf(),
              choose: agentLayout.write,
            })}`,
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
    // (anchor-placement.js), so its way there is Show in message, which opens the
    // message's thread here on that element (thread/destination.js,
    // `openThreadSubject`).
    const inMessage = Boolean(placedAt(thread.id)?.message);
    // A thread the destinations handed the panel as their last resort, whose place the
    // page draws nowhere, has no page to show (thread/destination.js, `showsOnPage`).
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
            ${offeredAction(
              "symbol",
              "lf-fp-on-page",
              inMessage ? "Show in message" : "Show on page",
              { action: "show" },
            )}
            ?disabled=${!thread.anchor}
            ?data-lf-unoffered=${!thread.anchor}
            @click=${() => {
              if (inMessage) {
                void openThreadSubject(thread.id, { intent: retainUserIntent() });
                return;
              }
              // The words come into view in the press's own task, so a widget
              // hiding them, as a diff's file filter does, gives them up to this
              // press rather than after the route's awaits (widget-elements.js,
              // `reveal`).
              const intent = retainUserIntent();
              const place = placedAt(thread.id)?.place;
              if (place) reveal(place, intent);
              close();
              // The reply box the field drew goes back to the thread's drawing on
              // the page once the reader has drawn the view gone, and the route lands
              // there where an opening does (thread/focus.js, `openingPart`); where the
              // page draws no view of the thread, as a window with no room for the rail
              // does, on its place (thread/destination.js, `reader: "page"`).
              void present({ release: true }).then(() =>
                threadActions.open(thread.key, {
                  part: null,
                  intent,
                  reader: "page",
                }),
              );
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
  // card standing without its question (thread/held-news.js).
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
    if (searchSurface.hidden !== !search) postureMoved = true;
    const input = fieldInput();
    if (input) syncInput(input);
    // The caret this paint puts in the page's field starts the writing posture in the
    // same paint, so the row draws it once rather than stepping out of it and back
    // when the field takes focus (`onCurrentLocation`).
    const caretLands = caretToField && !replying && !search;
    if (caretLands) writing = true;
    keeps(host, "data-lf-writing", writing ? "" : null);
    // A draft's Send takes the corner and the quick mark steps aside, unless a way
    // out holds that seat (`quickHidden`).
    const words = Boolean(draftOf(input));
    if (postureMoved || !words) drafted = words;
    postureMoved = false;
    keeps(host, "data-lf-drafted", drafted ? "" : null);
    if (!words) expanded = false;
    markRoom();
    keeps(host, "data-lf-expanded", expanded ? "" : null);
    const reading = fieldReading(top?.thread ?? null, input);
    // Only the page field competes with the seated annotation composer. An open
    // view already keeps that seat out, regardless of what its reply field says.
    keeps(host, "data-lf-offers", !top && !search && reading.offers ? "" : null);
    // A press standing at the field's end at rest keeps the row's notice aside, as the
    // user's words do, so a notice coming or going on news never moves it from under
    // the user's aim (floating-panel.css).
    const presses = !search && Boolean(reading.offer) && input !== focused() && !words;
    keeps(host, "data-lf-presses", presses ? "" : null);
    keeps(host, "data-lf-tone", status().tone || null);
    keeps(host, "data-lf-asks", status().asks ? "" : null);
    // Each moment the leaf answers has a beat of its own (notifications.js), so it plays
    // once per moment, a press repeating the words standing included, however often the
    // field leaves those words and returns; of several in one task, the latest.
    const { moment, beat } = gestureReading();
    const gestures = beat !== answered ? moment : null;
    answered = beat;

    render(panelTemplate(), host);
    noteDrawnSections();
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
        listed[0],
    );
    if (leavesReply && hadEditorFocus && !search) focusDestination(leaf, "return");
    if (caretLands) {
      caretToField = false;
      focusDestination(pageEditor().input, "move");
    }
  }

  // ---------- the row's notice ----------
  // One small notice beside the seat, for a state the user should not miss while they
  // read: a few words (`says`), a `tone` that tints it, and at most one `press`: the
  // older version's, whose Latest has no key. A passing notice of the user's own
  // gesture says its words and its press in the field instead (`fieldReading`).
  /** @typedef {{says: string, tone: string | null, press: {label: string,
   * run: () => unknown, title?: string | null, disabled?: boolean} | null}} RowNotice */
  // A notice's press, or one offered alone (notifications.js, `offerPress`), as the
  // field's end offers it (composing/input.js, `BoxPress`): its word, the keys of the
  // page command that makes it, as the command reference spells them, and what it does.
  // The user chose on 5 November 2026 that the right side of the box is for shortcuts,
  // so a notice's press stands there with its key, in the face Comment and c wear, over
  // the notice's own line with an inked Undo over the field's start, which since 31
  // October had been the one press in the row in a face of its own.
  // Its key stands beside it only while that key would make the same press now, as the
  // dispatcher reads it (`activeCommandLabel`): with the caret in a box, `m` is a letter
  // typed, and the press alone still acts.
  /** @param {import("./notifications.js").NoticePress} press
   * @returns {import("./composing/input.js").BoxPress} */
  function noticePress(press) {
    return {
      word: actionName(press.action),
      // Read at each ask, so a box standing this press rechecks its key without
      // reading the field's words again (composing/input.js, `pressing`).
      get keys() {
        const key = activeCommandLabel([press.command]);
        return key ? [key] : [];
      },
      run: press.run,
    };
  }
  // The way out of the stance the user is in, as the page field's end offers it while
  // the field says its words at rest: Close, a press that ends the stance at once, as
  // its ✕ does (keyboard/touch-controls.js), with `esc` beside it only while Escape takes
  // the stance off now, as the dispatcher reads it (`escapeInvocation`): its step is the
  // stance's exit, or one titled as that exit, the ladder's step for the stance. Where
  // something stands over the stance, such as a widget's comment box in Design mode,
  // Escape closes that first, and Close stands alone. The reading that offers it
  // `exits`, which tells `fieldExit` the field says it, so the seat holds the On Me mark
  // meanwhile. Both ask the dispatcher whether a stance stands now (`innermostStance`):
  // the stance's words and its exit row are read in the repaint frame, so for the paint
  // a search's close makes, they still name the search, and the seat would take its ✕
  // for that paint and give it up in the next.
  /** @returns {import("./composing/input.js").BoxPress | null} */
  function stanceClose() {
    const held = innermostStance();
    const exit = held ? rows().find((entry) => entry.exit) : null;
    if (!held || !exit) return null;
    return {
      word: actionName("close"),
      // Read at each ask, as a notice's press's key is (`noticePress`).
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
  // The page shows an older version than the latest: the menu's row that opens the
  // latest says so too, but only once the menu is open, while the count beside it
  // follows the version shown with no word of why.
  function olderVersion() {
    const { latest } = versionsReading();
    if (latest.shown === null) return null;
    return {
      says: latest.shown,
      tone: "warn",
      press: {
        label: "Latest",
        title: latest.keyTitle,
        disabled: latest.disabled,
        // The notice stands in the row, beside whatever view is open, so its press
        // puts nothing away: a revision installed under an open thread hands back
        // the reply being written there (version.js, `restoreEditingContinuity`).
        run: () => versionPicker.latest(),
      },
    };
  }
  /** @param {RowNotice} notice */
  function rowNoticeTemplate({ says, tone, press = null }) {
    return html`<span class="lf-fp-row-notice-face" data-lf-tone=${tone ?? nothing}
      ><span class="lf-fp-row-notice-says">${says}</span>${
        press
          ? html` <span class="lf-fp-row-notice-sep" aria-hidden="true">·</span>
              <button
                type="button"
                ${offeredAction("inline", "lf-fp-row-notice-press")}
                .lfPreview=${() => (press.title ? { detail: [press.title] } : null)}
                ?disabled=${press.disabled}
                @click=${press.run}
              >
                ${press.label}
              </button>`
          : nothing
      }</span
    >`;
  }

  // ---------- gestures ----------
  // The leaf unfolds a folded panel, and otherwise opens the menu, the On view's first
  // tab, or puts it away where it stands, a list it leads to included.
  function pressLeaf() {
    if (host.dataset.lfRest === "mark") {
      prefs().setRest("row");
      paint();
      return;
    }
    if (menuStands()) {
      close();
      return;
    }
    query = "";
    open({ view: "menu" });
    if (!coarsePointer.matches) focusDestination(threadSearchInput, "move");
  }
  // Folded, the leaf's peek carries passing notices, since there is no field to show
  // them. The leaf's preview names what pressing it does (preview.js), and folded, says
  // the page's status under that, which the row and the menu already show unfolded; the
  // words keep still while they show, even as the live status ages.
  function peekPresentation() {
    const notice = passing();
    const telling = notice.visible && host.dataset.lfRest === "mark";
    return {
      content: telling ? voiced(noticeWords(notice.message)) : nothing,
      shown: telling,
    };
  }
  // The leaf's label carries the status's summary for a screen reader, which its
  // preview says in full, so the preview names the leaf in fewer words. A passing
  // notice standing in the folded leaf's peek is all it says.
  function leafPreview() {
    if (host.dataset.lfRest !== "mark") return { name: "Page menu" };
    if (passing().visible) return false;
    const fold = commandSteps(FOLD);
    return {
      name: "Unfold Leaf",
      keys: fold.length ? [fold] : [],
      detail: [pagePresented() && statusParts(status().explanationParts)],
    };
  }
  // What stands open above the row, the menu as any view, is a step of the page's Escape,
  // taken wherever focus has fallen once the field has been left
  // (`panel.floating.leave`); with nothing open, the page's own foot of the ladder takes
  // the user from the panel back onto the page.
  pageRung("floating panel", () => {
    // The field's search, the menu's or Threads', clears its words first; then, empty,
    // the menu's closes the menu and Threads' returns to Threads, as a find box returns
    // to its panel (keyboard/AGENTS.md, "Escape").
    if (focused()?.matches?.(".lf-fp-search"))
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
  // takes the user from the chrome back onto the page (keyboard/page.js), and a step
  // declared over the whole panel would claim Escape on its every control, where the
  // Go-to sequence refuses to arm.
  const inList = () => {
    const at = focused();
    const rows = listRows();
    return rows.length > 0 && (at === shownView() || rows.some((row) => row === at));
  };
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
  // claim on those keys (keyboard/dispatch.js).
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
  // character. An element holds one declaration (keyboard/scopes.js), so every view's
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
  // (keyboard/AGENTS.md, "Escape"), and the next Escape puts the view away. A reply
  // returns to its thread, the view, by the reply box's own way back (thread/landing.js,
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
  // Folding to the leaf is the page's command, so it has a key and a row in the menu.
  const foldPanel = () => setRest(prefs().rest === "mark" ? "row" : "mark");
  pageCommand({
    id: FOLD,
    keys: ["."],
    title: () => (prefs().rest === "mark" ? "unfold" : "fold"),
    touch: () => (prefs().rest === "mark" ? "Unfold the panel" : "Fold to the leaf"),
    menu: "page",
    run: foldPanel,
  });
  // Where the reader stood before stepping into the panel, which a row's command that
  // acts on that place gets back (history.js, `readPlace`).
  /** @type {ReturnType<typeof readPlace> | null} */
  let heldCurrentLocation = null;
  // It is still where they are on the page while they stand in the panel.
  holdPagePlace(() => (currentLocationIn(host) ? heldCurrentLocation : null));
  // A press reads it before the press moves focus, which may put away what held it, and
  // the focus that press moves, a finger's included, which lands only after its release,
  // keeps it (focus.js, `pressing`).
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
  // Writing begins in the field and lasts while the user stays in the panel, so the
  // line naming where the words go stays put while they press Resolve or a filter.
  onCurrentLocation((node, _cause, left) => {
    const inside = Boolean(node) && renderedUnder(node, host);
    // Stepping in from the page holds where the user was, and from nowhere holds no
    // place. A row the panel just took away, as a pressed menu row hands the user to the
    // leaf, is no longer under the panel but came from it, and holds nothing.
    if (inside && !left && !fromThePage.kept()) heldCurrentLocation = null;
    else if (inside && left?.isConnected && !renderedUnder(left, host))
      heldCurrentLocation = readPlace(left);
    const next = inside ? writing || node?.localName === "leaf-text" : false;
    if (next === writing && !inside) return;
    writing = next;
    paint();
  });
  // A press away from the panel puts away what stands open above the row (focus.js,
  // `onPressAway`). A press in a modal over the panel is not on the page (`overPanel`).
  onPressAway(
    (path) => trail.value.length > 0 && !path.includes(host) && nativeModalAdmits(host),
    () => close(),
  );
  // Travel to a place on the page (anchor-travel.js, `arrive`) shows it, so the view
  // open above the row gives way where it would stand over any of that place once
  // landed (`landed`, landing-scroll.js `landedBox`), as it gives way to a press on the
  // page: a long thread's view covers most of the window, and a place at the page's
  // foot can't be scrolled above even a short one. A view the landing clears stays, so
  // a link followed from a thread's view leaves the thread open for Back to return to.
  // On Me stays too where it lists the item travel lands on (`onMe.lists`), since its
  // card shows that item, ringed where the `m` walk reached it (`walkedStop`); a thread
  // On Me doesn't list, as `t` reaches, has no card there. A Tab onto a page stop the
  // view would stand over clears it the same way, since the ring the user follows would
  // stand under it. Whether the panel stands over the place at all is its cover's
  // answer, by the rule every reading of what the user sees takes (geometry.js,
  // `covered`), so a place in the top layer or the panel's own is never under it; the
  // view gives way only where it is the part that does, and the row stays either way.
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
  /** @type {import("./anchor-travel.js").TravelOptions["clearFor"]} */
  function clearFor({ where, focus }, landed) {
    if (
      doors.queue.shows() &&
      focus !== false &&
      onMe.lists(focus ?? placeHolder(where))
    )
      return;
    if (standsOver(where, landed)) close();
  }
  onCurrentLocation((node, cause) => {
    if (cause === "step" && node && standsOver(node, landedBox(node))) close();
  });

  // The doors to the panel's views and to Versions, as Go-to's named destinations
  // (keyboard/go-to-sequence.js) and version travel (`g V`, version.js) press them:
  // each opens what it names, or puts it away where it already stands, so the press
  // that opened it closes it. The On Me door turns the On view to the user's list where
  // it shows another tab, and the Threads door to Threads.
  // `shows` says whether the press would put its view away.
  function putVersionsAway() {
    const inside = currentLocationIn(host);
    close();
    if (inside) focusDestination(leaf, "return");
  }
  const doors = Object.freeze({
    threads: {
      shows: () => showing({ view: "threads" }),
      press: () => {
        query = "";
        refit();
        open({ view: "threads" });
      },
    },
    queue: {
      shows: () => showing({ view: "queue" }) && queueTab === "you",
      press: openOnMe,
    },
    leaves: {
      shows: () => showing({ view: "leaves" }),
      press: () => open({ view: "leaves" }),
    },
    versions: {
      shows: versionsShown,
      press: () => (versionsShown() ? putVersionsAway() : open({ view: "versions" })),
    },
  });

  // A live sample's host showing its child's threads in the panel (sample.js, the
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
  // wider than in the card's room beside the column (thread-preview.js), as its row in
  // Threads opens it.
  /** @param {string} id */
  function openThread(id) {
    const thread = threadByKey(id);
    if (!thread) return;
    open({ view: "thread", thread: thread.key }, { reopen: true });
  }

  // A live revision carries the thread open here, and where its view was read to,
  // across it (version.js, `captureRetainedCurrentLocation`): the reader is still at it, so
  // the view comes back as they left it, without taking focus, which the reply's own
  // editing continuity hands back. A revision installed in place keeps the view, which
  // still shows the thread, so its restore changes nothing. A view opened by the
  // user's next visit does not come back (restore-state.js); this is not that.
  function captureCurrentLocation() {
    const top = trail.value.at(-1);
    const view = openView();
    if (!top?.thread || !view) return null;
    return {
      thread: threadByKey(top.thread)?.key ?? top.thread,
      scroll: view.scrollTop,
    };
  }
  /** @param {ReturnType<typeof captureCurrentLocation>} currentLocation */
  function restoreCurrentLocation(currentLocation) {
    const thread = currentLocation && threadByKey(currentLocation.thread);
    if (!thread || !currentLocation) return false;
    if (trail.value.at(-1)?.thread === thread.key && openView()) return true;
    open({ view: "thread", thread: thread.key }, { reopen: true, focus: false });
    landing = null;
    void present({ release: true }).then(() => {
      const view = openView();
      if (view && trail.value.at(-1)?.thread === thread.key)
        moveScrollerBy(view, currentLocation.scroll - view.scrollTop);
    });
    return true;
  }

  // The page's comment box in this chrome, as `c` and Resume writing find it
  // (composing/surface.js, `commentDestination`), and the selected words a press on it
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
    // (box-motion.js). An export mounts no panel, so its root states no band.
    addEventListener("resize", followBox);
    presentation = registerChromeThreadPresentation(host, {
      render: nominate,
      // The view makes room for the agent's answer to the user's last turn itself
      // (the growth under **Opened**), so the reader hands it over at once.
      answersAtOnce: true,
      // A reader the page's package registers later takes the thread open here, and
      // the user's place in it where they were in the panel, read before the panel's
      // reader, and the message they were on, goes.
      yielded: () => {
        const top = trail.value.at(-1);
        if (!top?.thread) return null;
        const focus = currentLocationIn(host);
        const message = focus
          ? (closestAcross(focused(), ".lf-msg")?.getAttribute("data-lf-message") ??
            null)
          : null;
        const key = top.thread;
        return () => openInPackage(key, { focus, message });
      },
      // A thread about the whole page opens here; one about a passage opens beside it,
      // where the page draws it, widgets in its messages included, and here only where
      // nothing on the page shows it, as on a page drawing no margin or a window with no
      // room for the rail, the destination's last resort (`request.last`,
      // thread/destination.js), or for one of its messages
      // while the view already shows it, so a walk to an ask in it leaves the user
      // where they read. Where the user lands in it is the route's (`request.part`),
      // which Leaf's destinations take them to once it is drawn: the reply, a message,
      // or the thread itself, the view, where the `t` walk goes on from.
      /** @type {import("./thread/destination.js").OpenPrimary} */
      reveal: (key, { part, last }) => {
        const thread = threadByKey(key);
        if (!thread) return false;
        const top = trail.value.at(-1);
        const shown = threadOf(top)?.key === thread.key;
        if (thread.anchor && !(part === "message" && shown)) {
          if (!last) {
            // The page draws it, so a thread's view here goes, its own or another's, as
            // Show on page puts it away: the thread shows once, and the one the user
            // arrived at is the one thread open, which the field's reply and a walk's
            // position then name. The panel closes rather than going back to a list
            // the view stood over, since the user has gone on to the page. Where the
            // page takes the thread this view shows, the reply being written in it goes
            // along, the row itself, to the page's view of the thread, or to wait for
            // it to open (thread/replies.js, `releaseReplies`), so the user goes on
            // writing there.
            if (shown) releaseReplies(replyOutlet);
            if (top?.thread) close({ handedOn: shown });
            return false;
          }
        }
        open({ view: "thread", thread: thread.key }, { reopen: true, focus: false });
        return present({ release: true });
      },
    });
    // Upgrade turns the status to its loading words without a publication.
    document.addEventListener(UPGRADE, () => paint(), { once: true });
    document.addEventListener("lf-chrome-preference", () => paint());
    paint();
  }

  return {
    mount,
    clearFor,
    pageComment,
    searchPage,
    doors,
    showForSample,
    openThread,
    captureCurrentLocation,
    restoreCurrentLocation,
    // The anchored comment box opening in its home (`responseSeat`) clears the row for
    // it, where the composer then takes the caret (composing/surface.js,
    // `finishPlacement`).
    responseHome: responseSeat,
    revealResponse: clearRow,
    // The thread whose row in Threads holds `under`, the element under the pointer, and
    // the row Threads draws for a thread, through which hover links a row and its
    // passage both ways (anchor-paint.js, `markRow`). Each asks the rows' own markup, so
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
