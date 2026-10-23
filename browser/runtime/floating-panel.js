/* The floating panel: Leaf's chrome, as one box hovering over the foot of the page. It
 * presents what other owners hold, so it reads their readings and calls their commands:
 * the status and approval (page-status.js), the page's controls (`pageControls`,
 * page-controls.js), the threads (`readThreads`), the queues (`readQueues`), the
 * versions (`versionPicker`), the drafts (drafts.js), the passing notices
 * (notifications.js) and the errors (errors.js). It decides only how they are shown.
 *
 * The box has three sizes, and which it stands at follows what the user does, so no
 * setting chooses it:
 * - **Folded**, the leaf alone in the window's corner, coloured by the agent's state,
 *   with a badge counting what waits on the user and a dot for threads with news. The
 *   user folds it from the leaf's menu or with `.`, or by a pointer with the small round
 *   button that rides the box's top-right corner while the pointer is near it; a
 *   press on the leaf unfolds it, and it stays as it was left across pages (`rest`).
 *   Once the page presents, its status tooltip keeps the explanation it opened for
 *   one pointer or focus exposure, so news and aging words cannot move text being
 *   read. The next exposure, including a return from a hidden tab, reads the current
 *   status. The leaf's tone, counts and accessible name stay live, and notices
 *   answering a gesture show immediately.
 * - **The row**: the leaf, the comment field, and marks with counts for On me and
 *   Threads, with at most one small notice beside the marks for a state the user should
 *   not miss, such as reading an older version, tinted by its tone and with at most one
 *   press (`ROW_NOTICES`); the field gives it room, so the marks keep their seats, but
 *   only while it holds no words, which a narrower field would rewrap under the reader;
 *   the notice waits while words stand there. The empty field says what the agent is
 *   doing or wants, in the status's words
 *   (`statusReading`), or what a passing notice says, where a placeholder would say
 *   "Comment"; in a stance, such as Draw mode, it names the stance, whose way out is a ✕
 *   at the row's end; in a thread it says whose turn it is. While words stand selected
 *   on the page, the page's field quotes them, inside a stance too, and a press there
 *   comments on them (`selectedWords`), the one route a finger has to them; the user
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
 * - **Opened**: a view above the same row (On, Threads, a thread or All pages), what
 *   the user reads there, with its name over it and its controls at its foot, on the
 *   row: the way back, its tabs or a thread's own presses. Close occupies the
 *   bottom row's shared exit slot; a view with no actions needs no footer. The panel stands
 *   on the window's foot, so a view grows and shrinks from its top edge, and only its
 *   name and what it holds move as it does, while every control at its foot stays
 *   where the user aims at it. So a list fits what each tab, filter or search the user
 *   presses shows. The user chose this on 20 October, comparing it with the whole head
 *   at the foot and with the head at the top edge, where it stood from 12 October.
 *   There a list kept the height it opened at across tabs, so a tab moved no control,
 *   and hid what a longer tab showed past that height; and a press in a thread's head
 *   and a refused turn each held the thread's height. Rejected with the whole head at
 *   the foot: a tall view opening on what it holds with nothing naming it. It lasts
 *   while it is
 *   used: Escape or a press on the page puts it away, Escape once the caret has
 *   left the field, since the caret is the innermost thing open. The view stands right
 *   on the row, with no line between them that typing would show or hide.
 *   The user chose that (2026-10-14), reversing a blank line's room kept under every
 *   open view, which read in Threads as a missing row. Rejected there: the line pushing
 *   the view up as it comes. The view's last words scroll clear of New reply
 *   (`fitAnswer`), the one thing that stands over its controls. It is as tall as what it
 *   holds, so a one-message thread opens one message tall, up to most of the window's
 *   height, the larger size a long thread or a long Threads list is read at; past that
 *   it scrolls. The user chose views that fit their content with a larger size for long
 *   reading (2026-10-13); content alone reaches that size. Rejected: an Expand
 *   control at the view's head, which the growth it asks for would carry up from under
 *   the pointer, and a compact cap with the larger size behind a gesture, which leaves
 *   every long thread scrolling in a small box until the user finds that gesture.
 *   While it stands it covers the page under it, which reads as unseen (geometry.js,
 *   `declareOccluder`).
 *
 * The leaf's menu is a small list above the leaf holding the rest of the page's
 * controls, each one line, with its key where it has one, and a chevron on a row that
 * opens a list of its own (Versions, and the groups: Navigate, Annotations, and About,
 * which holds the rows that copy a text only where no clipboard is there to copy with;
 * elsewhere each such row, the page's link and the Leaf version among them, is one press
 * in the menu, as the user chose on 15 October over an About view of one line). That
 * list takes the menu's place in the same box, sliding in from the side the chevron
 * points to, under its name and over a way back to the menu, as → and ← go, which
 * stands at the list's foot over the leaf as a view's controls do (`menuAt`): those
 * lists are for choosing, as the menu is, while what the user reads, Threads, On and
 * All pages, whose rows say what each page's agent is doing, opens as a view. The user
 * chose this on 15 October, reversing each list opening as a view rising from the
 * field with no way back to the menu. Rejected: that view keeping
 * its place with a "‹ Menu /" crumb at its head, which still moves the user's eye from
 * the menu to the panel's top. A
 * keyboard's convenience for where the reader stands, such as Resume writing, stands
 * under Navigate only where no keyboard is there to reach it (page-controls.js, the
 * `keys` group). The panel shows no key hints of its own: the menu's rows carry their
 * keys and `?` opens the full reference, which the user chose on 13 October over a
 * hint or two in the line over the field, to keep the panel quietest. The field the
 * user clicks in is the field they write in: a page
 * comment where no thread is open, a reply where one is: the reply box every view of a
 * thread draws (thread/replies.js), with its ↑ to the user's last message, which Leaf's
 * reader draws in the field's place. Each destination keeps its own native editor (its
 * draft, caret and send), and the panel stands the current one in the field's place, so
 * words never move between editors. Page and Threads search take this same field
 * with their own native inputs: a right-hand scope chip and a faint tint name the
 * mode after its placeholder is gone. Search never borrows an editor or its send,
 * attachments or dictation. Every mode keeps its field on the bottom row, with
 * mode-specific controls beside it. Content opens in a view; response choices
 * use a picker. Features contribute to those surfaces rather than adding strips.
 *
 * Nothing moves under the pointer: a view's controls stand at its foot, the leaf's
 * menu holds what it showed while it stands, and a control the user pressed in a
 * thread stays where it was. Every change of the box's layout takes effect in one step,
 * and what the user sees then travels from where it was drawn to where it stands, by
 * one model (box-motion.js): the surface behind the box, a separate layer, follows by a
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
  afterRender,
  renderCommit,
  html as nativeHtml,
  createView,
  createEffect,
  For,
  Show,
  onCleanup,
  untrack,
  subscribe,
  createSignal,
  flush,
} from "/vendor/browser-runtime.js";
import { el, reveal } from "./widget-elements.js";
import { iconElement } from "./icons.js";
import { copyControl } from "./copy-control.js";
import { keeps, keepsHidden, keepsText, layoutPx } from "./keeps.js";
import { setRuntimeRootStyle } from "./root-state.js";
import {
  approvalReading,
  approve,
  registerApprovalPresentation,
  statusReading,
} from "./page-status.js";
import { leavesRows } from "./live-leaves.js";
import { keys } from "./keyboard/scopes.js";
import { pageCommand, pageDoor, pageRung } from "./keyboard/register.js";
import { advertisesKeys, parsed, rowArrows } from "./keyboard/bindings.js";
import { keySequenceModel, keySequenceTemplate } from "./keyboard/key-sequence.js";
import { pageControls } from "./page-controls.js";
import { readPlace } from "./history.js";
import { readThreads } from "./thread/state.js";
import { hasUnread, threadCounts } from "./thread/model.js";
import { LeafElement } from "./leaf-element.js";
import { afterScript } from "./rendering.js";
import { threadAttention, workflowStep } from "./thread/workflow.js";
import {
  messageReading,
  threadName,
  threadHeadingModel,
  threadHeadingView,
} from "./thread/messages.js";
import { drawnThreadId, THREAD } from "./thread/selectors.js";
import { declareThreadParts } from "./thread/focus.js";
import { quoteReading } from "./thread/thread-card.js";
import { inPageOrder } from "./thread/placement.js";
import { dismissReply, replyAvailable } from "./thread/replies.js";
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
import { settleThread } from "./thread/folding.js";
import { queueItemKey, readPlan, readQueues } from "./queue-api.js";
import { queueTitle } from "./queue-title.js";
import { queueStop } from "./queue-walk.js";
import { carriesObligation, itemOutcome } from "./queues.js";
import { shortAgo } from "./presence.js";
import { obligationEnding } from "./obligations/answer.js";
import { answeredInWords, readObligations } from "./obligations/model.js";
import { obligationPlace } from "./obligations/place.js";
import { declareSide } from "./standing-target.js";
import { versionPicker } from "./version-picker.js";
import { versionsReading } from "./version.js";
import { UPGRADE } from "./presentation.js";
import { noticeReading } from "./notifications.js";
import {
  dismissError,
  dismissErrors,
  errorsReading,
  passErrors,
  seeErrors,
} from "./errors.js";
import { move } from "./dom-move.js";
import { statusContextReading } from "./keyboard/status-context.js";
import { reducedMotion } from "./motion.js";
import { pagePresented } from "./page-paint.js";
import { onReadingInterrupted, readingIsContinuous } from "./reading-continuity.js";
import {
  focusDestination,
  focused,
  holdFocus,
  letGo,
  onStanding,
  onUserInput,
  rove,
  standingIn,
} from "./focus.js";
import { rowWalk } from "./walk-position.js";
import { excerptWords } from "./words.js";
import { afterSettling, holdRendering, nextRender, sizeObserver } from "./rendering.js";
import { boxMotion } from "./box-motion.js";
import { scrollIntoView } from "./landing-scroll.js";
import { moveScrollerBy, SCROLL_SLACK, scrollLimit, scrollToEnd } from "./scrolling.js";
import { declareOccluder, declareWindowChrome } from "./geometry.js";
import { registerReadingRegion } from "./reading-regions.js";
import { agentName } from "./semantic-state.js";
import { runtime } from "./context.js";
import { renderedUnder, under } from "./shadow.js";
import { nativeModalAdmits } from "./keyboard/layer-stack.js";
import { closestAcross } from "./passages.js";

const prefs = () => document.documentElement.lfChrome;
// The Codex panel's tween: one strong ease-out for every change of size and fade.
const EASE = "cubic-bezier(.23, 1, .32, 1)";
// The box growing as the words do, a line at a time, takes the tween's full length, which
// the user singled out as the panel's best motion (15 October).
const RESIZE_MS = 300;
// A view the user opened, or put away, is what they asked to see, so it arrives almost at
// once, as the menu does: its outline in a third of the tween, its words faded in at
// once after the leaving view's. The user found the full tween slow here (15 October).
const VIEW_RESIZE_MS = 120;
const FADE_MS = 90;
// The view leaving is gone before the one arriving shows, so the two never read
// through each other.
const OUT_MS = 60;

// The menu's groups, each a list of the page's controls declaring it, in the menu's place.
const GROUPS = Object.freeze({
  navigate: "Navigate",
  annotate: "Annotations",
  about: "About this page",
});
// Rows the panel opens itself: All pages as a view, Versions as a list in the menu's
// place.
const OWN_VIEWS = Object.freeze(["leaves", "versions"]);
// Rows held elsewhere, so the menu and its groups leave them out: by the menu's foot,
// or, for picking an element to comment on, by the page itself, where selecting words
// or pressing `s` already starts it. A finger has no `s`, and selecting words picks no
// widget or picture, so where no keyboard is there to press it, Annotations lists it
// (keyboard/AGENTS.md, "Touch routes").
const FOLD = "panel.floating.fold";
const HELD_ELSEWHERE = Object.freeze(["keyboard", `command:${FOLD}`]);
const PICK = "command:target.picker.open";
// A row the menu or a group lists: neither held elsewhere nor a stance's way out, at the
// row's end.
const listed = (entry) =>
  !entry.exit &&
  !HELD_ELSEWHERE.includes(entry.key) &&
  !(entry.key === PICK && advertisesKeys());
// A browser offers the clipboard only to a secure context (https or localhost), so a
// page read over plain http from another machine has none to copy with; and one that
// offers it may still refuse a write, after which the page copies nothing more by a
// press (`copyItem`).
let copyRefused = false;
const canCopy = () => !copyRefused && Boolean(navigator.clipboard?.writeText);
// Where a row stands in the menu: in its group; a keyboard's convenience (`keys`) under
// Navigate only where no keyboard is there to reach it, so a finger still can; and a row
// that copies a text, such as the page's link, under About where no clipboard is there to
// copy it with, since About shows its text to select.
const groupOf = (entry) =>
  entry.group === "keys" && !advertisesKeys()
    ? "navigate"
    : entry.copies && !canCopy()
      ? "about"
      : entry.group;
const FILTERS = Object.freeze(["open", "unread", "drafts", "resolved"]);
// The views a thread is opened from.
const LISTS = Object.freeze(["threads", "queue"]);
const capital = (word) => word[0].toUpperCase() + word.slice(1);
const coarse = () => matchMedia("(pointer: coarse)").matches;
// What passes in the panel's one seat for words that pass: a notice while one shows,
// else what the status line says between notices, the Go-to filter's word or a walk's
// position ("1 of 3 waiting on me · Options"). The user asked on 16 October that
// whatever is not anchored to the page stand at the panel rather than against the
// window.
function passing() {
  const notice = noticeReading();
  if (notice.visible) return { message: notice.message, visible: true };
  const { goTo, walk } = statusContextReading();
  const message = goTo ?? (walk?.shown ? walk.text : "");
  return { message, visible: Boolean(message) };
}
// A progress run's face in a thread's view (transcript.js), the working message among
// them, standing for the work under way where the view reads the answer to the user's
// turn (`fitAnswer`); and the key each is drawn under there, by the run it faces.
const WORKING = ".lf-thread-working";
const FACE = "face:";
const isFace = (key) => key.startsWith(FACE);
const clock = (at) =>
  new Date(at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

/** @typedef {FloatingPanel} FloatingPanelElement For its generated tag. */
class FloatingPanel extends LeafElement {
  draw = () => {};
  render() {
    this.draw();
  }
}
customElements.define("leaf-floating-panel", FloatingPanel);

export function createFloatingPanel({
  wireInput,
  threadActions,
  registerChromeThreadPresentation,
  observeFeedback,
  firstUnread,
  afterReadingPass,
  obligations: obligationView,
  queueActions,
  arrivesAt,
  inWalkOrder,
  withdraw,
  settlement,
  placedAt,
  openThreadSubject,
}) {
  const host = new FloatingPanel();
  host.className = "lf-ui lf-floating-panel";
  host.setAttribute("role", "region");
  host.setAttribute("aria-label", "Leaf");
  // The surface the box stands on: a layer of its own over the whole window, cut to the
  // box's outline, with a ring a pixel outside it, so its outline can move between two
  // places without either box's layout moving.
  const ground = el("div", "lf-ui lf-fp-ground");
  ground.setAttribute("aria-hidden", "true");
  const ring = el("div", "lf-fp-ring");
  const fill = el("div", "lf-fp-fill");
  // The field's focus ring, drawn here only while the box moves (box-motion.js), since
  // no transform draws a ring changing size.
  const fieldRing = el("div", "lf-fp-field-ring");
  const fieldFill = el("div", "lf-fp-fill");
  ground.append(ring, fill, fieldRing, fieldFill);
  const card = el("div", "lf-fp-card");
  const inner = el("div", "lf-fp-inner");
  // What stands above the row while a view is open: its name, with nothing to press, the
  // view, and its controls at its foot.
  const opened = el("div", "lf-fp-opened");
  const head = el("div", "lf-fp-head");
  const stage = el("div", "lf-fp-stage");
  const controls = el("div", "lf-fp-controls");
  opened.append(head, stage, controls);
  const row = el("div", "lf-fp-row");
  const menu = el("div", "lf-fp-menu");
  menu.id = "lf-fp-menu";
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", "Page");
  const badge = el("span", "lf-fp-badge");
  const newsDot = el("span", "lf-fp-news-dot");
  for (const mark of [badge, newsDot]) mark.setAttribute("aria-hidden", "true");
  const peek = el("div", "lf-fp-peek");
  peek.id = "lf-fp-peek";
  peek.setAttribute("role", "tooltip");
  let peekAsked = false; // pointer or focus on the folded leaf
  let peekReading = null;
  inner.append(opened, row);
  card.append(inner);
  // The menu and the peek stand over the leaf by anchoring to it, which they can only
  // do from after it in the tree.
  host.append(card, menu, badge, newsDot, peek);
  // The pointer's way to fold, which the user asked for as a minimize shown on hover: a
  // corner mark on the box's top-right corner, chosen over one at the row's end on 15
  // October. It presses the fold command's own row, as the menu's row does; that row and
  // `.` are the keyboard's and a finger's ways, so it takes no Tab stop of its own.
  const minimize = el("button", "lf-corner-mark lf-fp-minimize");
  minimize.type = "button";
  minimize.tabIndex = -1;
  minimize.title = "Fold to the leaf";
  minimize.setAttribute("aria-label", "Fold to the leaf");
  minimize.append(iconElement("subtract", "lf-corner-mark-icon"));
  minimize.addEventListener("click", () =>
    rows()
      .find((entry) => entry.key === `command:${FOLD}`)
      .press(null),
  );
  host.append(minimize);
  // It shows only while the pointer is near the corner it rides, so the panel at rest,
  // and under a pointer passing over the field or the marks, carries no control the user
  // did not reach for (15 October). Near is the box's top-right corner, a mark's width in
  // and half a row down, which holds the button itself. The corner moves when the box changes
  // size under a still pointer, as a view opening above a press on Send carries it up,
  // so nearness is read again then (`follow`): a button left showing where the
  // pointer no longer is would ride the box's next change, such as a refused send
  // taking that view back, across the window without input.
  const CORNER = { across: 64, down: 24 };
  let pointer = null;
  const readCorner = () => {
    const box = card.getBoundingClientRect();
    const near =
      pointer !== null &&
      pointer.x >= box.right - CORNER.across &&
      pointer.y <= box.top + CORNER.down;
    keeps(host, "data-corner", near ? "" : null);
  };
  host.addEventListener("pointermove", (event) => {
    pointer = { x: event.clientX, y: event.clientY };
    readCorner();
  });
  host.addEventListener("pointerleave", () => {
    pointer = null;
    readCorner();
  });
  // The row stands over the window's foot, so what the page reveals stands clear of it.
  // A view opened above it is itself read, and stands over the page only while it is
  // used, so it leaves the page's room alone; but what it stands over is hidden while it
  // does (`declareOccluder`), and a landing stands clear of it (`--lf-panel-reach`,
  // `followBox`).
  declareWindowChrome(() => {
    const box = row.getBoundingClientRect();
    return box.width > 0 && box.height > 0 ? [box] : [];
  }, [row]);
  declareOccluder(opened);

  const leaf = el("button", "lf-fp-leaf");
  leaf.type = "button";
  leaf.setAttribute("aria-haspopup", "menu");
  leaf.setAttribute("aria-controls", menu.id);
  leaf.setAttribute("aria-describedby", peek.id);
  const mark = el("span", "lf-dot");
  // An error the user has not seen yet, waiting in the leaf's menu (`errorsList`).
  const errorDot = el("span", "lf-fp-error-dot");
  errorDot.setAttribute("aria-hidden", "true");
  leaf.append(mark, errorDot);
  const field = el("div", "lf-fp-field");
  const editorSeat = el("div", "lf-fp-editors");
  // A long draft offers more room, by the user's press rather than on its own: past
  // three lines a quiet mark stands over the leaf, in the corner the draft leaves free
  // beside its first line, or among an open view's controls, so it takes no room of its own
  // (assets/AGENTS.md, "A control takes only its own room"). It stood at the end of the
  // line over the field until, on 17 October, that line stopped saying where the words
  // go and so stopped standing over them. Pressing it widens the
  // panel and lets the field take most of the window, so the words re-wrap because the
  // user asked. It folds back when the field empties, a send included, or on a second
  // press. The user chose this on 15 October over the panel widening by itself at the
  // third line, which re-wraps every line under the caret; no composer they compared
  // widens on its own (Open WebUI and Zulip offer the same press once text is long).
  const expand = el("button", "lf-fp-expand");
  expand.type = "button";
  let expanded = false;
  // A pointer's press leaves the caret in the words, as the microphone's does.
  expand.addEventListener("mousedown", (event) => event.preventDefault());
  expand.addEventListener("click", () => {
    expanded = !expanded;
    paint();
  });
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
    // In the frame the field grows, ahead of the box's reading (`followBox`), so the
    // box's motion reveals the mark with the line that brought it.
    markRoom();
  });
  // The mark stands while the draft runs long, and while the field is wide, where the
  // draft may fit three lines again; a resolved thread's field takes no words.
  let fieldRests = false;
  const markRoom = () =>
    keeps(host, "data-long", (long || expanded) && !fieldRests ? "" : null);
  lengthWatch.observe(field);
  const searchSurface = el("div", "lf-fp-search-surface");
  searchSurface.setAttribute("role", "search");
  const fieldMode = el("span", "lf-fp-mode");
  const fieldActions = el("div", "lf-fp-actions");
  field.append(editorSeat, searchSurface, fieldMode, fieldActions);
  const rowNoticeSeat = el("div", "lf-fp-row-notice");
  const quick = el("div", "lf-fp-quick");
  // The way out of the stance the user stands in, at the row's end beside the counts,
  // and there while the user types (touch-controls.js, `stance`).
  const exitSeat = el("div", "lf-fp-exit-seat");
  // The anchored comment box's home on a page that draws its own annotations
  // (`data-annotations="page"`), where the page gives the box no seat of its own
  // (composing/surface.js, `responseHome`). While its composer is open it stands in the
  // field's place, as each destination's own editor does there: its words go to a new
  // thread on the passage it quotes, which the box says. The field comes back when the
  // box closes, while a view is open above the row, whose field it is, and while the
  // field quotes words selected on the page, which a press there comments on. Which of
  // the two shows is the stylesheet's reading of the composer's own open state and the
  // row's `data-offers` (floating-panel.css), so the box seated in the page, or put
  // away, moves nothing here. Rejected: a view of its own above the row, which stood a
  // second field over the panel's own.
  const responseSeat = el("div", "lf-fp-response");
  row.append(leaf, field, responseSeat, rowNoticeSeat, quick, exitSeat);

  const CONNECTING = {
    tone: "",
    summary: "Connecting…",
    summaryParts: [{ text: "Connecting…", source: null }],
    explanation: "Connecting…",
    explanationParts: [{ text: "Connecting…", source: null }],
    adds: "",
    addsParts: [],
    asks: false,
    publication: null,
  };
  const status = () => statusReading() ?? CONNECTING;
  // Only the authored runs carry response identity. Their renderer refs register
  // and retire those exact nodes with the shared exposure owner, wherever status
  // stands: the field's native placeholder slot, the menu, or the folded leaf's peek.
  // Snapshot props keep domain reads in the controller; each generated seat owns
  // one Solid root, retained across the same view's revisions.
  const nativeDrawings = new WeakMap();
  function paintView(container, component, props) {
    let drawing = nativeDrawings.get(container);
    if (drawing) drawing.update(props);
    else
      nativeDrawings.set(
        container,
        (drawing = createView(container, component, props)),
      );
  }
  const statusWords = (parts) => [
    For({
      get each() {
        return parts();
      },
      keyed: false,
      children: (part) =>
        nativeHtml`<span class="lf-fp-status-feedback" ref=${(node) =>
          createEffect(
            () =>
              part().source
                ? JSON.stringify([part().source.item, part().source.event_id])
                : null,
            (source) => {
              if (!source) return;
              const [item, event] = JSON.parse(source);
              return observeFeedback(node, {
                input_id: item,
                reply_id: event,
                reply_kind: "work",
                presentation_kind: "status_words",
                surface: "panel",
              });
            },
          )}>${() => part().text}</span>`,
    }),
  ];
  // The trail of views open above the row, innermost last; empty at rest. It, whether
  // the menu is open and the list standing in it are signals, since the panel's keys
  // read them and follow the signals they read (keyboard/scopes.js): a press that opens
  // Threads gives the panel its `/` with no other call.
  const [trail, setTrail] = createSignal([], { ownedWrite: true });
  let leaving = null;
  const [menuOpen, setMenuOpen] = createSignal(false, { ownedWrite: true });
  // The list standing in the menu's place, a group or Versions, or null for the menu,
  // and the height it first stood at, which it keeps while it stands, so news changing
  // the list moves none of the menu's rows.
  const [menuAt, setMenuAt] = createSignal(null, { ownedWrite: true });
  let menuRoom = null;
  let filter = "open";
  let query = "";
  let searching = false;
  let pageSearch = null;
  let searchFocus = null;
  const threadSearchInput = el("input", "lf-fp-search");
  searchSurface.prepend(threadSearchInput);
  threadSearchInput.type = "search";
  threadSearchInput.name = "thread-search";
  threadSearchInput.placeholder = "Find a thread or message";
  threadSearchInput.setAttribute("aria-label", "Find a thread or message");
  threadSearchInput.addEventListener("input", () => {
    query = threadSearchInput.value;
    refit();
    paint();
  });
  const threadSearch = { input: threadSearchInput, controls: [] };
  const activeSearch = () =>
    pageSearch?.open
      ? pageSearch
      : searching && trail().at(-1)?.view === "threads"
        ? threadSearch
        : null;
  function searchPage(search) {
    if (pageSearch?.input !== search.input) searchSurface.prepend(search.input);
    if (search.open && !pageSearch?.open)
      searchFocus = { input: search.input, current: retainUserIntent() };
    if (!search.open) searchFocus = null;
    pageSearch = search;
    paint();
  }
  function closeThreadSearch() {
    searching = false;
    searchFocus = null;
    query = "";
    refit();
    paint();
    focusDestination(shownView(), "return");
  }
  let writing = false;
  // Whether the field holds a draft, as the row last showed it: Send in the field's
  // corner, the counts stepped aside. The row takes that posture, or gives it up, only
  // at the user's own move: typing, or a view changing, which stands another editor in
  // the field. The caret coming into or leaving the field moves nothing, so a draft the
  // user steps away from keeps every line where it was. The user chose this on 20
  // October over the counts coming back as the caret left, which rewrapped the draft
  // each time the user stepped out and again as they came back. Words a refused send
  // hands back move nothing, so its action stays in the seat the empty field gave it,
  // Dictate's, until the user types again; emptying the field always ends it. A draft is
  // anything typed, a line break included: a new line grows the field as words do, so
  // the field takes its room from the first key (20 October).
  let drafted = false;
  let postureMoved = true;
  // The thread the reader lands at the end of, once Leaf has drawn more than `after`
  // of its messages: the whole of it on opening, or past the turn the user just sent.
  let landAtEnd = null;
  const drawnTurns = () => outletOf()?.querySelectorAll(".lf-msg").length ?? 0;

  // ---------- one native editor per destination ----------
  // The errors the field can say now, newest first (errors.js): about nothing, not yet
  // edited past, while the editor standing in the field is empty. An error about the
  // editor covers it instead, as at any box (composing/input.js). A folded panel, or a
  // view with no editor in the field, can say none.
  function sayable() {
    const input = host.dataset.rest === "mark" ? null : fieldInput();
    if (!input?.isConnected || draftOf(input) !== "") return [];
    return errorsReading().filter((error) => !error.passed && error.subject === null);
  }
  // The words selected on the page that a press on the page's field comments on, as
  // the response surface offers them (composing/surface.js, `offerSelection`): their
  // `quote`, and the `comment` that opens the comment on them. Null while none stand.
  let selectedWords = null;
  // What the empty field says, and whose reading it is (`says`): the newest error it
  // can say; once the caret is in a field that takes words, where they go; on the page,
  // the selected words a press there comments on; a passing notice while one stands; a
  // resolved thread's way back; else on the page what the agent is doing or wants, in
  // the status's words, and in a thread whose turn it is. On the page, the stance the
  // user stands in, such as Draw mode, heads a passing notice and takes the status's
  // place (keyboard/status-context.js); the leaf keeps the status's colour.
  function fieldReading(key, input) {
    const [error] = sayable();
    if (error) return { says: "error", words: error.message };
    const thread = key ? threadByKey(key) : null;
    if (input === focused() && !thread?.resolved)
      return { says: "destination", words: whereTo(key) };
    // The words alone, in quotation marks: a 320px phone's row leaves the field room
    // for about a dozen characters, so "Comment on" before them would leave none, and
    // the field's own name says what a press does (`pageEditor`). The field's ellipsis
    // cuts them to its room, which the excerpt's cap only bounds.
    if (!key && selectedWords)
      return { says: "selection", words: `“${excerptWords(selectedWords.quote, 60)}”` };
    const stance = key ? null : statusContextReading().stance;
    const notice = passing();
    if (notice.visible)
      return {
        says: "notice",
        words: stance ? `${stance} · ${notice.message}` : notice.message,
      };
    if (thread?.resolved) return { says: "turn", words: "Resolved · reopen to reply" };
    if (stance) return { says: "stance", words: stance };
    if (!key) return { says: "status", words: status().summary };
    if (!thread) return { says: "turn", words: "Reply…" };
    const agent = agentName();
    const attention = threadAttention(thread);
    const words =
      attention?.kind === "needs_user"
        ? `${attention.label} · reply to ${agent}`
        : attention
          ? [attention.label, attention.secondary].filter(Boolean).join(" · ")
          : `Reply to ${agent}`;
    return { says: "turn", words };
  }
  // Where the words go, as the focused field's placeholder says it; the thread's own
  // name already heads its view.
  const whereTo = (key) => (key ? "Reply in this thread" : "Comment on the page");
  // An editor's empty words, as its own paint draws them (composing/input.js, `hint`),
  // which marks the editor with whose reading they are, so the face the theme gives that
  // reading changes in the same paint as the words (floating-panel.css).
  function saying(key, input) {
    const reading = fieldReading(key, input);
    if (input) keeps(input, "data-says", reading.says);
    return reading.words;
  }
  // The page's own editor: the field where no thread is open.
  let general = null;
  function pageEditor() {
    if (general) return general;
    const input = textField();
    input.name = "comment";
    const send = el("button", "lf-fp-send");
    send.type = "button";
    const box = el("div", "lf-fp-box");
    box.append(input, send);
    input.value = loadDraft(PAGE_DRAFT) ?? "";
    const sync = wireInput(input, {
      hint: () => saying(null, input),
      hintParts: () => {
        const parts = status().summaryParts;
        return fieldReading(null, input).says === "status" &&
          parts?.some((part) => part.source)
          ? parts
          : null;
      },
      hintView: (read) => statusWords(() => read().parts ?? [{ text: read().word }]),
      // Named for what a press there does, as the field's reading says it, once the
      // editor this builds is the one the reading reads.
      accessibleName: () =>
        general && fieldReading(null, input).says === "selection"
          ? "Comment on the selection"
          : "Comment on the page",
      sends: "send",
      sendBtn: send,
      save: (text) => {
        saveDraft(PAGE_DRAFT, text);
        tellDraft(PAGE_DRAFT, text);
        retype();
      },
      send: (_text, raw, owns) => {
        let flight = null;
        const handle = sendMessage(
          PAGE_DRAFT,
          owns,
          (attempt) =>
            (flight = threadActions.create({ attempt, text: raw })?.delivery),
        );
        if (!handle) return;
        // The box empties as the send leaves; the row reads it again once it has.
        queueMicrotask(paint);
        // A page comment starts a thread, keyed by the attempt that sent it, which the
        // panel opens so its reply follows in the same field.
        const route = { view: "thread", thread: handle.attempt };
        open(route, { replace: true });
        // A refusal takes back the thread the send drew, which the server never held,
        // and its view goes with it (`paintPanel`); the words go back to the page's
        // draft (drafts.js, `standGesture`). Unless the user has opened another view
        // since, the field stands for the page again holding them. The caret follows
        // only while no later input has changed where the user is reading.
        const untouched = retainUserIntent({ source: host });
        void Promise.resolve(flight).then((sent) => {
          if (sent || (trail().length && trail().at(-1) !== route)) return;
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
    general = { box, input, sync };
    return general;
  }
  // A thread's reply is the reply box every thread view has (thread/replies.js), which
  // Leaf's reader draws into the field where the panel nominates it (`nominate`), so ↑
  // to the user's last message, the draft's editing session and Send work as in a card.
  // The panel says what the empty box reads, and a send keeps the user in the field for
  // the next turn, landing the view at its end. A resolved thread shows no reply box,
  // and the field's line says how to reopen it instead, or a passing notice, such as
  // the one `z` leaves when it shows the resolve it takes back next (undo.js).
  const replyOutlet = el("div", "lf-fp-reply");
  const resolvedLine = el("p", "lf-fp-resolved");
  const replyInput = () => replyOutlet.querySelector(`.lf-thread-reply ${TEXT_FIELD}`);
  const replyOptions = new Map();
  const replyOptionsFor = (key) => {
    if (!replyOptions.has(key))
      replyOptions.set(key, {
        hint: () => saying(key, replyInput()),
        accessibleName: () => `Reply to ${threadTitle(key)}`,
        sent: () => {
          // The user's turn lets go of the height a press held (`pressAt`).
          room = null;
          rewriting = false;
          landAtEnd = { key, after: drawnTurns() };
          // The user's turn grows the view to show it and takes New reply away.
          waiting = null;
          queueMicrotask(paint);
        },
      });
    return replyOptions.get(key);
  };
  // The editor standing in the field now, the page's or the open thread's reply; none
  // while search owns the field or a resolved thread says how to reopen it instead.
  const fieldInput = () =>
    activeSearch()
      ? null
      : editorSeat.firstElementChild !== replyOutlet
        ? pageEditor().input
        : replyOutlet.hidden
          ? null
          : replyInput();
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
  // writes on the page). The press's mousedown is cancelled, so the editor never takes
  // focus, a phone raises no keyboard for it, and the page's selection stands until the
  // comment takes it. The comment opens as the press completes, since that mousedown
  // still reaches the page, which puts away whatever comment box it finds open
  // (composing/surface.js, `standDown`). A Tab through the row, or the runtime putting
  // the caret there, writes on the page.
  let pressedWords = null;
  const quotedWords = () =>
    general &&
    fieldInput() === general.input &&
    fieldReading(null, general.input).says === "selection"
      ? selectedWords
      : null;
  field.addEventListener(
    "pointerdown",
    (event) => {
      pressedWords =
        event.isPrimary && event.composedPath().includes(general?.input)
          ? quotedWords()
          : null;
    },
    true,
  );
  field.addEventListener(
    "mousedown",
    (event) => {
      if (pressedWords) event.preventDefault();
    },
    true,
  );
  field.addEventListener("click", (event) => {
    const words = pressedWords;
    pressedWords = null;
    if (words && event.composedPath().includes(general?.input)) words.comment();
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
  // count is a reading of the saved inventory, so the marks and tabs say one only once
  // it has arrived (`inventoried`).
  const threads = () => readThreads().threads;
  const inventoried = () => readThreads().phase === "ready";
  const threadByKey = (key) =>
    threads().find((thread) => thread.key === key || thread.id === key) ?? null;
  const threadTitle = (key) => {
    const thread = threadByKey(key);
    return thread ? threadName(thread) : "this thread";
  };
  const newCount = () => (inventoried() ? threadCounts(threads()).unread : 0);
  const openCount = () => (inventoried() ? threadCounts(threads()).open : null);
  const onUserCount = () => {
    const queues = readQueues();
    return queues.phase === "ready" ? queues.on_user.length : 0;
  };
  // Ordinary open state is implicit. Rows name attention, resolution, news and drafts,
  // less the state the selected filter already says, such as "New" under Unread.
  const threadStatus = (thread, shownBy) => {
    const state = thread.resolved ? "Resolved" : threadAttention(thread)?.label;
    const said = {
      unread: "New",
      resolved: "Resolved",
      drafts: "Draft",
    }[shownBy];
    return [
      hasUnread(thread) && "New",
      state,
      draftHasContent(replyContext(thread.key)) && "Draft",
    ]
      .filter((word) => word && word !== said)
      .join(" · ");
  };
  const rows = () => pageControls();

  // ---------- navigation ----------
  const routeKey = (route) =>
    route.view === "thread"
      ? `thread:${route.thread}`
      : route.view === "group"
        ? `group:${route.group}`
        : route.view;
  const titleOf = (route) =>
    ({
      threads: "Threads",
      queue: tabLabel(queueTab),
      leaves: "All pages",
      versions: "Versions",
      errors: "Errors",
      thread: route.thread ? threadTitle(route.thread) : "",
      group: GROUPS[route.group],
    })[route.view];
  // The menu's list as its row's `data-row` names it, which going back stands on.
  const levelRow = (level) => (level.view === "group" ? routeKey(level) : level.view);
  const pathTo = (route) =>
    route.view === "thread" ? [{ view: "threads" }, route] : [route];
  function open(route, { replace = false, reopen = false, focus = true } = {}) {
    const before = trail().at(-1);
    setMenu(false);
    if (before && routeKey(before) === routeKey(route) && !replace) {
      if (reopen) return;
      close();
      return;
    }
    if (route.view === "thread" && presentation && !presentation.primary) {
      openInPackage(route.thread, { focus });
      return;
    }
    if (route.view !== "threads" && route.view !== "thread") searching = false;
    // A thread opened from a list, Threads or On, has that list behind it, so its
    // back link returns where the user came from.
    flush(() =>
      setTrail(() =>
        replace && before
          ? [...trail().slice(0, -1), route]
          : route.view === "thread" && LISTS.includes(before?.view)
            ? [before, route]
            : pathTo(route),
      ),
    );
    if (replace && route.view === "thread" && trail().length === 1)
      flush(() => setTrail(() => pathTo(route)));
    if (route.view === "thread") arriveAt(route.thread);
    transition(before, { focus });
  }
  // Where the page's package draws its conversations, a thread opens in its reader,
  // and the view it was chosen from goes, uncovering the page.
  function openInPackage(key, { focus = true, message = null } = {}) {
    if (trail().length) close();
    void threadActions.open(threadByKey(key)?.key ?? key, {
      part: null,
      focus,
      message,
    });
  }
  // Opening a thread shows it whole, at its end, where the latest turn is.
  function arriveAt(key) {
    landAtEnd = { key: threadByKey(key)?.key ?? key, after: 0 };
  }
  // Asking to write is asking for the field, so a folded panel unfolds, and the field
  // stands for the page again, with nothing open above it.
  // Whether the paint that next stands the page's field in the row puts the caret in it.
  let caretToField = false;
  function clearRow() {
    const before = trail().at(-1);
    if (prefs().rest === "mark") prefs().setRest("row");
    if (trail().length) flush(() => setTrail(() => []));
    setMenu(false);
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
  // refusing it, stands the user on its row in Threads, while they have not acted since
  // (folding.js, `settleThread`).
  const openThreads = () =>
    inPageOrder(
      threads().filter((candidate) => !candidate.resolved),
      placedAt,
    );
  function resolveLanding(thread) {
    const route = trail().at(-1);
    const fromThreads = trail().at(-2)?.view === "threads";
    const at = openThreads().indexOf(thread);
    const mayLand = retainUserIntent();
    let mayRestore = () => false;
    return {
      optimistic: () => {
        if (!mayLand() || trail().at(-1) !== route) return false;
        const kept = openThreads();
        const next = fromThreads ? (kept[at] ?? kept[at - 1]) : null;
        if (next) {
          open({ view: "thread", thread: next.key }, { replace: true, focus: false });
          const view = shownView();
          if (view) focusDestination(view, "move");
        } else back();
        mayRestore = retainUserIntent();
        return true;
      },
      // Taking the resolve back stands the user on the thread's row, where they are
      // back at Threads. Where they moved on to the next thread, they stay on it, and
      // the reopened thread waits in Threads: the reopening arrives with the server's
      // reading, and a view opening or closing then would move the panel under no
      // press. The undo door passes the intent of the press that asked for it.
      reverse: (may = mayRestore) => {
        if (!may() || trail().at(-1)?.view !== "threads") return;
        const row = shownView()?.querySelector(
          `.lf-fp-thread[data-key="${CSS.escape(thread.key)}"]`,
        );
        if (row) focusDestination(row, "move");
      },
    };
  }
  // Reopening a thread puts the caret in its reply, which the reopening draws in the
  // field, so what the user types next is their reply. Taking the reopen back, or the
  // log refusing it, stands the user on the thread's view again, while they have not
  // acted since, so the reply they did not write in goes with the reopening
  // (folding.js, `settleThread`).
  function reopenLanding() {
    const route = trail().at(-1);
    const mayLand = retainUserIntent();
    let mayRestore = () => false;
    return {
      optimistic: () => {
        const input = fieldInput();
        if (!mayLand() || trail().at(-1) !== route || !input) return false;
        focusDestination(input, "move");
        mayRestore = retainUserIntent();
        return true;
      },
      reverse: (may = mayRestore) => {
        const view = shownView();
        if (!may() || trail().at(-1) !== route || !view) return;
        focusDestination(view, "return");
      },
    };
  }
  function back() {
    const before = trail().at(-1);
    flush(() => setTrail(() => trail().slice(0, -1)));
    transition(before);
  }
  function close() {
    const before = trail().at(-1);
    searching = false;
    flush(() => setTrail(() => []));
    transition(before);
  }
  // A press that puts away the menu or view it stands in hands the user back to the leaf,
  // the door to both, before its command runs, so the pressed row going takes no one's
  // focus to the body: a layer the command opens records the leaf as where its close
  // returns (focus.js, `openLayer`), folding leaves the user on the leaf it folds to, and
  // a command that places the user elsewhere still does.
  function putAwayThen(run) {
    const inside = standingIn(host);
    close();
    setMenu(false);
    if (inside) focusDestination(leaf, "return");
    run();
  }
  function setMenu(on) {
    if (menuOpen() === on) return;
    menuRoom = null;
    held = null;
    flush(() => {
      setMenuAt(() => null);
      setMenuOpen(() => on);
    });
    paint();
  }
  // A list the menu leads to takes the menu's place, and going back puts the menu back,
  // either sliding in from the side it lies on. The menu stays open across the change, so
  // a user standing on the row it removes stands on the leaf, its door, meanwhile; one who
  // came by key, or from outside the panel, as `g V` does, stands on the first row the
  // list offers, and going back, on the row that opened it.
  function showMenuAt(level) {
    return renderCommit(() => {
      const before = menuOpen() ? menuAt() : undefined;
      if (before && level && routeKey(before) === routeKey(level)) return;
      if (renderedUnder(focused(), menu)) focusDestination(leaf, "return");
      menuRoom = null;
      held = null;
      flush(() => {
        setMenuAt(() => level);
        setMenuOpen(() => true);
      });
      paint();
      afterRender(() => {
        if (level) {
          menuRoom = menu.offsetHeight;
          paint();
        }
        const page = menu.firstElementChild;
        if (before !== undefined && page && !reducedMotion()) {
          const side =
            (level ? 1 : -1) * (getComputedStyle(menu).direction === "rtl" ? -1 : 1);
          page.animate(
            [
              { translate: `${side * 16}px 0`, opacity: 0 },
              { translate: "0 0", opacity: 1 },
            ],
            { duration: VIEW_RESIZE_MS, easing: EASE },
          );
        }
        // A press on a menu row leaves focus on that row. A command-reference press
        // originates outside the panel even when closing the reference hands focus back
        // to the leaf before this door runs, so enter the menu in that case.
        if (pointedInPanel) return;
        const target = level
          ? page?.querySelector(".lf-fp-item:not(.lf-fp-menu-back, :disabled)")
          : before && menu.querySelector(`[data-row="${levelRow(before)}"]`);
        if (target) focusDestination(target, "move");
      });
    }).ready;
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
  // Leaf's reader draws into the open thread's view on its own schedule, a sent turn
  // among them, so the view lands where that drawing shows, not at the panel's next paint.
  // The view's landing may change the box's size, and the browser delivers no observer a
  // box shallower than the view later in the frame it resized, so the box is read
  // again here, before that frame paints what moved.
  const fit = sizeObserver(() => {
    landReader();
    fitAnswer();
    stood = openView()?.offsetHeight ?? null;
    followBox();
  });
  const follow = sizeObserver(() => {
    readCorner();
    followBox();
  });
  const motion = boxMotion({
    root: host,
    box: card,
    room: ground,
    // The ground is cut too, to the outline grown by its shadow's reach (`--raise-2`'s
    // blur dropped by its drop, theme.css), so it stands over nothing else in the
    // window: a layer over the whole window that paints nothing left every word under
    // it unmeasured by a contrast checker. Its cut moves with the ring's, so it holds
    // the ring every frame.
    surface: () => {
      const lift = getComputedStyle(ground);
      const shadowReach = ["--raise-2-drop", "--raise-2-blur"]
        .map((token) => Number.parseFloat(lift.getPropertyValue(token)))
        .reduce((reach, part) => reach + part);
      return [
        [ground, shadowReach],
        [ring, 1],
        [fill, 0],
      ];
    },
    ring: [fieldRing, fieldFill],
    observer: follow,
    theirs: () => gesture,
  });
  // The user's key, press or typing owns what it sets going until that rendering
  // settles (rendering.js, `afterSettling`): changes to the box meanwhile are theirs,
  // and what changes it after, such as an answer arriving, is news. News landing before
  // the gesture's rendering settles, a reading back within a frame or two, is taken as
  // theirs. Typing is told apart, since the field it types in must not move under it.
  let gesture = null;
  let gestures = 0;
  // Activation is a new gesture too: a held press can settle before its click.
  const beginGesture = (event) => {
    if (
      !["keydown", "pointerdown", "input", "touchstart", "click"].includes(event.type)
    )
      return;
    gesture = event.type === "input" ? "typing" : "press";
    const own = ++gestures;
    afterSettling(() => {
      if (gestures === own) gesture = null;
    });
  };
  onUserInput(beginGesture);
  window.addEventListener("click", beginGesture, { capture: true, passive: true });
  function followBox() {
    // How far the box reaches up from the window's foot, which the root's
    // `scroll-padding-bottom` keeps every landing clear of (theme.css), so `m`, `t`, a
    // Go-to or an On me row's Show lands what it reaches above an open view rather than
    // under it. The browser's own reveals read the same padding. CSS can't size the
    // root's padding from a fixed box in the chrome's shadow tree, so the box states it.
    const box = card.getBoundingClientRect();
    setRuntimeRootStyle(
      document.documentElement,
      "--lf-panel-reach",
      layoutPx(box.height > 0 ? ground.getBoundingClientRect().bottom - box.top : 0),
    );
    const moving = !reducedMotion() && pagePresented();
    const duration = performance.now() < viewMovingUntil ? VIEW_RESIZE_MS : RESIZE_MS;
    motion.follow(moving ? { duration, easing: EASE } : null);
  }
  addEventListener("resize", () => {
    motion.forget();
    followBox();
  });

  // A view is as tall as what it holds, up to its cap (floating-panel.css,
  // `--lf-fp-view-height`); what does not fit scrolls inside it. A list fits what the
  // user chose it to show, as it opens and as a tab, filter or search they press changes
  // it (`refit`), which moves only its top edge and its name, since its controls stand
  // at its foot; between those presses it holds that height (`room`), so news arriving
  // in it or leaving it moves none of the rows it shows. What a list first holds is what
  // it shows, and a message Leaf's reader has yet to draw into it is not yet held. A
  // thread's view follows its messages, whose reader holds back any news that would move
  // what is read (thread/held-news.js) until the user asks for it, and what the user
  // asks for, a reply they send or news they open, grows the view to show it.
  //
  // The agent's answer to the user's own last turn is the one news the reader hands the
  // view at once (`answersAtOnce`): the user is waiting for it. The view grows to hold
  // it, work under way and a reply streaming included, up to its cap: the field and the
  // view's controls stay put and its top edge rises, carrying the user's own turn up
  // with it. Where the user
  // stood at the view's end and their turn and the answer together fit in the view, the
  // end follows the answer into sight, as a card's transcript follows a turn joining its
  // end. Otherwise the answer goes on below the fold, and New reply stands at the view's
  // foot until a press on it, or the user scrolling there, shows it; the user's turn
  // stays wholly in sight above the press, its head included (`fitAnswer`). The user
  // chose this growth (2026-10-14), the one case where news may carry what a view shows
  // without a gesture (`browser/AGENTS.md`, "Stability"), reversing the view
  // holding its height while the user waited (#2892), which left a short thread's
  // answer behind New reply in a view one message tall. Rejected then and now: holding
  // the answer behind the reader's "1 new reply", which left the reply the user waited
  // for unseen. Other news in an open thread is still held. A thread's view declares
  // that it stands on its foot (`data-lf-rises`), which the shift watch credits for
  // exactly this growth (tests/shift_watch.js, `appendGrowth`).
  // Whether this opening of a thread has shown On the page, whose seat then stands
  // while the view does, so a revision detaching the thread moves nothing beside it.
  let onPageSeat = false;
  // Whether this opening of a thread offers Next unread, decided once the opening has
  // landed and a pass of read tracking has read what it shows whole (thread/read.js,
  // `afterPass`): it does where a reply still stands unread, out of sight or behind a
  // fold, and the seat then stands while the view does, the press unoffered once none is
  // left, so reading moves nothing beside it. Until then, and where every reply showed
  // whole, nothing stands there. Replies arriving later need none: New reply leads to one
  // the user waits for, and the thread's notice to news it holds. Rejected: deciding as
  // the view first drew, which offered Next unread for the moment before the opening
  // read a short reply.
  let unreadSeat = null;
  function decideUnreadSeat() {
    const route = trail().at(-1);
    if (route?.view !== "thread" || unreadSeat !== null) return;
    const key = routeKey(route);
    afterReadingPass(() => {
      const top = trail().at(-1);
      if (!top || routeKey(top) !== key || unreadSeat !== null) return;
      unreadSeat = (threadByKey(route.thread)?.unread.length ?? 0) > 0;
      if (unreadSeat) paint();
    });
  }
  // The threads about a passage the page last drew nowhere, which Leaf's destinations
  // then handed the panel as their last resort (`reveal`): On the page has nowhere to
  // take the user from those.
  const unplaced = new Set();
  // A thread's view stands on its foot, so what grows in it carries its name, and all
  // the view holds, up the window. That is the growth news and the user's own turns
  // make (`fitAnswer`), but a press keeps what it pressed under the pointer. So where
  // what a press in the view grows would carry the pressed control away, as Full quote,
  // Show on a fold that opens below it, or a rewrite's pencil would, the view holds the
  // height it stood at as the press came (`judgePress`, before the frame shows the
  // growth) until the user's next turn, and what the press grew goes on inside the
  // view, revealed by scrolling. A press whose growth leaves it in place, as Show on
  // progress, which opens above it, holds nothing, so the view grows to show what
  // opened; nor does a press that grows nothing, so an answer the user waits for still
  // grows the view, nor one among its controls, which its growth leaves in place. The
  // caret in a rewrite, which a key can open from the field, holds the view while it
  // stays there, so typing carries none of the rewrite's own presses, the rewrite's
  // lower lines revealed by scrolling (thread/reply-landing.js, `revealEditor`). A card
  // grows down from the same press, so there the press stays put by itself. Rejected: a
  // hold for each control that grows the view, which missed each one added after it, as
  // the folds did; and every press in the view holding it, which kept an awaited answer
  // from growing it after a click on the words.
  //
  // The height the open view holds, a list's or a thread's, or null where it fits what
  // it holds.
  let room = null;
  // The view last drawn open, by its route's key.
  let drawnTop = null;
  // The open thread's view's height as last drawn, which the caret entering a rewrite
  // holds.
  let stood = null;
  let rewriting = false;
  const holdThread = (height) => {
    if (trail().at(-1)?.view !== "thread" || room !== null || height === null)
      return false;
    room = height;
    return true;
  };
  // The press being judged: the control pressed, where it stood in the view's content,
  // and how tall the view, what it holds and its scroll stood. Once what the press
  // changed has drawn, after the press's own handlers, and before the frame shows it,
  // the press is put back where it stood. A change below it would carry it as the view
  // grows or shrinks from its top edge, so the view holds the height it stood at. A
  // change above it, as progress opening over the answer whose head holds its
  // disclosure, leaves it in place as far as the view's height takes the change up, so
  // the view keeps growing or shrinking as it would, and scrolls by the rest.
  let pressed = null;
  const contentTop = (node, view) =>
    node.getBoundingClientRect().top -
    view.getBoundingClientRect().top +
    view.scrollTop;
  // How tall what the view holds stands, whatever height the view itself stands at.
  const holding = (view) =>
    Math.max(
      0,
      ...[...view.children].map(
        (child) => contentTop(child, view) + child.getBoundingClientRect().height,
      ),
    );
  function pressAt(node) {
    const top = trail().at(-1);
    const view = openView();
    if (top?.view !== "thread" || !view || !(node instanceof Element)) return;
    if (!renderedUnder(node, view)) return;
    pressed = {
      node,
      at: contentTop(node, view),
      height: view.offsetHeight,
      holds: holding(view),
      scroll: view.scrollTop,
    };
  }
  function judgePress() {
    const press = pressed;
    pressed = null;
    const view = openView();
    if (!press || !view || !press.node.isConnected) return;
    if (Math.abs(holding(view) - press.holds) < 0.5) return;
    const above = contentTop(press.node, view) - press.at;
    if (Math.abs(above) < 0.5) {
      if (holdThread(press.height)) paint();
      return;
    }
    const grown = view.offsetHeight - press.height;
    moveScrollerBy(view, press.scroll + above - grown - view.scrollTop);
  }
  stage.addEventListener("click", (event) => pressAt(event.target), { capture: true });
  stage.addEventListener("click", judgePress);
  const inRewrite = (node) => Boolean(node && closestAcross(node, ".lf-msg-editor"));
  // A modal over the panel, such as the image viewer opened from a rewrite's attachment,
  // is a layer the user steps into from the panel, which hands them back as it closes:
  // standing in it leaves them rewriting, so the view keeps the height it holds for the
  // rewrite behind the modal and on the way back.
  const overPanel = (node) =>
    Boolean(node) && nativeModalAdmits(node) && !nativeModalAdmits(host);
  onStanding((node, cause) => {
    const top = trail().at(-1);
    if (top?.view !== "thread" || cause === "drop" || overPanel(node)) return;
    const view = openView();
    const writing = inRewrite(node) && Boolean(view) && renderedUnder(node, view);
    if (writing === rewriting) return;
    if (writing) {
      rewriting = holdThread(stood);
      if (!rewriting) return;
    } else {
      rewriting = false;
      room = null;
    }
    paint();
  });
  // A list takes its room as it stands before the paint that would change it, once
  // drawn: what it holds then is what it fits, so taking it writes only the height the
  // list already stands at.
  function holdRoom() {
    const top = trail().at(-1);
    if (!top || top.view === "thread" || room !== null || refitting) return false;
    if (drawnTop !== routeKey(top)) return false;
    const view = shownView();
    if (!view || view.querySelector(".lf-fp-asked:empty")) return false;
    room = view.offsetHeight;
    return true;
  }
  // A tab, filter or search the user presses changes what the list shows, which it
  // then fits, moving as one opening does; each such press repaints. The list takes
  // its room again from the next frame, once it stands at what it now fits.
  let refitting = false;
  function refit() {
    room = null;
    viewMovingUntil = performance.now() + VIEW_RESIZE_MS;
    if (refitting) return;
    refitting = true;
    nextRender(() => {
      refitting = false;
    });
  }
  // The open thread's messages as last drawn in its view, those its folds leave in
  // sight and the faces of its progress runs (`FACE`), and how far its content then
  // reached; and the answer waiting below the fold behind New reply, by its first
  // message.
  let drawnThread = null;
  let waiting = null;
  const drawnNode = (within, key) =>
    within?.querySelector(
      isFace(key)
        ? `${WORKING}[data-face="${CSS.escape(key.slice(FACE.length))}"]`
        : `.lf-msg[data-message="${CSS.escape(key)}"]`,
    ) ?? null;
  let fitted = null;
  // Where the panel itself last scrolled the open thread's view, which is not the user
  // going anywhere (`sawAnswer`).
  let placed = null;
  // Read where the reader's drawing lands, after layout and before the frame is shown.
  function fitAnswer() {
    const top = trail().at(-1);
    const view = openView();
    const outlet = outletOf();
    if (top?.view !== "thread" || !view || !outlet) {
      drawnThread = null;
      return;
    }
    const keys = [...outlet.querySelectorAll(`.lf-msg[data-message], ${WORKING}`)]
      .filter((node) => node.checkVisibility())
      .map((node) => node.dataset.message ?? FACE + node.dataset.face);
    const before = drawnThread?.key === top.thread ? drawnThread : null;
    const msgs = threadByKey(top.thread)?.msgs ?? [];
    const message = (key) => msgs.find((each) => each.key === key);
    // Which messages were still coming as drawn, work under way or a reply streaming,
    // judged then: an answer completing its stream is no longer one.
    drawnThread = {
      key: top.thread,
      keys,
      coming: keys.filter(
        (key) => isFace(key) || message(key)?.ephemeral || message(key)?.provisional,
      ),
      extent: view.scrollHeight,
      limit: scrollLimit(view),
    };
    // What follows the user's last turn in what is drawn: the answer, as far as it has
    // come. Before, it held only work under way or a reply still streaming.
    const answerIn = (drawn) => {
      const turn = drawn.findLastIndex((key) => {
        const each = message(key);
        return each?.author === "user" && !each.ephemeral;
      });
      return turn < 0 ? null : { turn: drawn[turn], keys: drawn.slice(turn + 1) };
    };
    const answer = answerIn(keys);
    const asked = before && answerIn(before.keys);
    if (
      !answer?.keys.length ||
      asked?.turn !== answer.turn ||
      !asked.keys.every((key) => before.coming.includes(key)) ||
      !answer.keys.every((key) => isFace(key) || message(key)?.author === "agent")
    )
      return;
    // An answer folding the work before it into less room moves nothing either, though
    // it takes over a New update the work left waiting.
    if (!waiting && view.scrollHeight <= before.extent + 0.5) return;
    // The answer arriving, or growing as it streams, in a view that has grown to hold
    // it as far as its cap lets it. Where the user stood at the view's end and their
    // turn and the answer fit in the view, the end follows the answer into sight;
    // otherwise New reply says what waits below the fold, and leads to the reply itself
    // once one follows the work under way, as it takes over the press.
    const atEnd = before.limit - view.scrollTop <= SCROLL_SLACK;
    const turn = outlet.querySelector(
      `.lf-msg[data-message="${CSS.escape(answer.turn)}"]`,
    );
    const pad = Number.parseFloat(getComputedStyle(view).paddingTop);
    const from = () =>
      turn.getBoundingClientRect().top - view.getBoundingClientRect().top - pad;
    if (
      !waiting &&
      atEnd &&
      view.scrollHeight - view.scrollTop - from() <= view.clientHeight
    ) {
      scrollToEnd(view);
      return;
    }
    const reply = answer.keys.find((key) => !isFace(key) && !message(key).ephemeral);
    const next = reply
      ? { key: top.thread, message: reply, label: "New reply" }
      : { key: top.thread, message: answer.keys[0], label: "New message" };
    if (waiting?.message === next.message) return;
    const arriving = !waiting;
    waiting = next;
    // New reply's foot joins the view, whose children other observers watch, so it is
    // drawn in the next frame rather than inside this observer's delivery.
    nextRender(() => {
      if (waiting !== next || openView() !== view) return;
      paint();
      if (!arriving || !atEnd || !turn.isConnected) return;
      // The user's turn stands wholly in sight, between the view's top edge and New
      // reply's ground, its head first where it is taller than that.
      const foot = view.querySelector(".lf-fp-foot")?.getBoundingClientRect();
      const below = foot ? turn.getBoundingClientRect().bottom - foot.top : 0;
      const by = Math.min(Math.max(below, 0), from());
      if (Math.abs(by) < 0.5) return;
      moveScrollerBy(view, by);
      placed = view.scrollTop;
    });
  }
  // Shows the answer waiting below the fold: its start comes into sight. The press that
  // took New reply away leaves the user standing on the thread, the view, as showing a
  // thread's held news does.
  function showAnswer() {
    const answer = waiting;
    waiting = null;
    paint();
    const view = openView();
    if (view) focusDestination(view, "move");
    const node = drawnNode(outletOf(), answer.message);
    if (node) scrollIntoView(node, { block: "start" });
  }
  // Scrolling the answer's start into sight above New reply takes New reply away, the
  // view keeping its height.
  function sawAnswer(event) {
    const view = event.currentTarget;
    if (!waiting || view.scrollTop === placed) return;
    const node = drawnNode(view, waiting.message);
    const press = view.querySelector(".lf-fp-new-reply");
    if (!node || !press) return;
    // Focusing New reply can scroll this view to reveal the button. That scroll
    // must not remove the focused button before its Enter press can activate it.
    if (press === focused()) return;
    if (node.getBoundingClientRect().top >= press.getBoundingClientRect().top) return;
    waiting = null;
    paint();
  }
  // The leaf's menu stands on the leaf and grows upward, so anything news adds to it, or
  // takes from it, carries everything above up or down the window: a row a revision
  // offers, such as the newer version, or a status re-wrapping the head. So while the
  // menu stands it holds what it showed with the first status it said (Connecting… is
  // not yet one). Its rows keep their seats: a row news takes off offer stands
  // disabled, and one news offers joins at the next opening. Each part of its head
  // keeps its lines: a later status re-wraps inside them, ending in an ellipsis
  // where it runs past them; a part the first status lacked stays out, and one a later
  // status lacks stands blank. Reopening the menu shows everything as it is. Rejected:
  // holding the head's height and scrolling what runs past it, which still moves the
  // words a re-wrap carries across its edge, and the same lines for every status, which
  // leaves most heads blank.
  let held = null;
  // The menu's seats as last drawn, each a row's key and how to draw it, `gone` once
  // news has taken it off offer.
  let seats = [];
  function holdMenu() {
    if (!menuOpen() || held !== null || !statusReading()) return false;
    const state = menu.querySelector(".lf-fp-state");
    if (!state) return false;
    const lines = (part) => {
      const line = state.querySelector(`.lf-fp-${part}`);
      return line
        ? Math.round(
            line.getBoundingClientRect().height /
              Number.parseFloat(getComputedStyle(line).lineHeight),
          )
        : 0;
    };
    held = { summary: lines("summary"), explain: lines("explain"), seats };
    return true;
  }
  function transition(before, { focus = true } = {}) {
    return renderCommit(() => {
      const after = trail().at(-1);
      postureMoved = true;
      // The thread the user stands in as the change begins, on the page or in the panel,
      // read before the paint that may take its view away.
      const stoodIn = drawnThreadId(closestAcross(focused(), THREAD));
      const reading = [before, after].some((route) => route?.view === "thread");
      if (after?.view !== "queue") {
        seated = null;
        seatHeights.clear();
      }
      const changed =
        (before ? routeKey(before) : null) !== (after ? routeKey(after) : null);
      if (changed) {
        room = null;
        rewriting = false;
        pressed = null;
        quoteExpanded = false;
        waiting = null;
        placed = null;
        drawnThread = null;
        onPageSeat = false;
        unreadSeat = null;
      }
      // Taking the panel away from a thread ends the editing session of its reply, as a
      // press elsewhere does (thread/replies.js), keeping the draft: the field no longer
      // draws that reply, and a session left standing would carry the user back to it.
      if (changed && before?.view === "thread")
        dismissReply(threadByKey(before.thread)?.key ?? before.thread);
      // The view going away fades where it stood, closing included, so the box shrinking
      // under it never shows an empty ground.
      leaving = changed && before && after ? before : null;
      if (changed) viewMovingUntil = performance.now() + OUT_MS + VIEW_RESIZE_MS;
      paint();
      afterRender(() => {
        // The reader draws what the view arriving holds, and lets go of what the one
        // leaving held: a thread's messages, or the obligations On shows as messages.
        const drawn =
          reading || before?.view === "queue" ? present({ release: reading }) : null;
        if (!changed || reducedMotion() || !pagePresented()) {
          leaving = null;
          paint();
          if (focus) focusView(after, drawn, stoodIn);
          return;
        }
        const arriving = stage.querySelector(".lf-fp-view:not([data-leaving])");
        arriving?.animate([{ opacity: 0 }, { opacity: 1 }], {
          duration: FADE_MS,
          delay: leaving ? OUT_MS : 0,
          easing: "linear",
          fill: "backwards",
        });
        const gone = stage.querySelector(".lf-fp-view[data-leaving]");
        const fade = gone?.animate([{ opacity: 1 }, { opacity: 0 }], {
          duration: OUT_MS,
          easing: "linear",
          fill: "forwards",
        });
        // The view leaving goes once its fade ends, which is still the gesture's rendering,
        // so the box moving then moves as the user's change (`followBox`).
        const release = fade ? holdRendering() : null;
        const settle = () => {
          leaving = null;
          paint();
          release();
        };
        if (fade)
          fade.finished.then(settle, () => {
            release();
          });
        else leaving = null;
        if (focus) focusView(after, drawn, stoodIn);
      });
    }).ready;
  }
  function focusView(route, drawn, stoodIn = null) {
    if (!route) return;
    const view = shownView();
    // A thread opens with the caret in its reply, as the one field means, once Leaf's
    // reader has drawn the reply there; one taking no reply, as a resolved thread does,
    // holds focus itself, so the user stands in it. A list stands on the row of the
    // thread the user stood in, where it lists it, as `g T` from a thread does; else,
    // opened by a key in the panel, on its first row, or its first control where it has
    // none, or itself where it holds neither, as an empty Threads does; opened from
    // anywhere else, as `g T` from the page or a pointer, it holds focus itself.
    if (route.view === "thread") {
      // A finger opening a thread reads it first, standing in the view, whose box
      // raises no keyboard; the keyboard rises when they tap in.
      const intent = retainUserIntent();
      void Promise.resolve(drawn).then(() => {
        const at = shownView();
        const target = at && ((!coarse() && viewParts.reply(at)) || at);
        if (target && trail().at(-1) === route && intent())
          focusDestination(target, "move");
      });
      return;
    }
    const rows = listRows();
    const stoodRow =
      stoodIn && rows.find((row) => threadByKey(row.dataset.key)?.id === stoodIn);
    const target =
      stoodRow ||
      (keyed ? (rows[0] ?? view?.querySelector("button, input") ?? view) : view);
    if (target) focusDestination(target, "move");
  }

  // Where the gesture now under way began: a key in a view stands on its first
  // control, while a pointer in the panel leaves focus on the pressed control. A
  // gesture outside the panel, `g T` from the page among them, is neither, whatever
  // the panel last heard, so the view it opens holds focus itself.
  let keyed = false;
  let pointedInPanel = false;
  onUserInput((event) => {
    if (["keydown", "pointerdown"].includes(event.type)) {
      const inPanel = event.composedPath().includes(host);
      keyed = event.type === "keydown" && inPanel;
      pointedInPanel = event.type === "pointerdown" && inPanel;
    }
  });

  // ---------- the leaf's menu ----------
  const copyItems = new Map();
  function copyItem(entry) {
    let copy = copyItems.get(entry.key);
    if (!copy) {
      copy = copyControl("lf-fp-copy-item", {
        label: `Copy ${entry.label}`,
        success: `${capital(entry.label)} copied`,
        error: `${capital(entry.label)} not copied · select it to copy`,
      });
      copy.addEventListener("wa-copy", () => putAwayThen(() => {}));
      copy.addEventListener("wa-error", () => {
        copyRefused = true;
        showMenuAt({ view: "group", group: "about" });
      });
      copyItems.set(entry.key, copy);
    }
    if (copy.value !== entry.copies) copy.value = entry.copies;
    if (copy.disabled !== Boolean(entry.disabled))
      copy.disabled = Boolean(entry.disabled);
    paintView(
      copy,
      (read) => nativeHtml`<button type="button" class="lf-fp-item"
        role=${() => (menuOpen() ? "menuitem" : undefined)}
        data-row=${() => read().entry.key}
        title=${() => read().entry.value || undefined}
        disabled=${() => read().entry.disabled}>
        <span class="lf-fp-label">Copy ${() => read().entry.label}</span>
        <span class="lf-fp-end">${iconElement("copy", "lf-action-icon")}</span>
      </button>`,
      { entry },
    );
    return copy;
  }
  const copies = new Map();
  function copyFor(entry) {
    if (!copies.has(entry.key))
      copies.set(
        entry.key,
        copyControl("lf-fp-copy-press", {
          label: `Copy ${entry.label}`,
          success: `${capital(entry.label)} copied`,
          error: `${capital(entry.label)} not copied · select it to copy`,
        }),
      );
    const copy = copies.get(entry.key);
    if (copy.value !== entry.copies) copy.value = entry.copies;
    if (copy.disabled !== Boolean(entry.disabled))
      copy.disabled = Boolean(entry.disabled);
    keepsHidden(copy, !canCopy());
    return copy;
  }
  const groupValue = (group) =>
    group === "annotate" &&
    rows().find((entry) => entry.key === "command:annotations.toggle")?.label ===
      "Show annotations"
      ? "Hidden"
      : "";
  const menuEntry = (entry, group = false) => {
    const view = OWN_VIEWS.includes(entry.key) ? entry.key : null;
    return {
      ...entry,
      kind: entry.copies ? (group ? "copy-text" : "copy") : "row",
      copy: entry.copies ? (group ? copyFor(entry) : copyItem(entry)) : null,
      shortcut:
        advertisesKeys() && entry.shortcut?.length
          ? keySequenceModel(entry.shortcut)
          : null,
      opens: view === "versions",
      role: menuOpen() ? "menuitem" : undefined,
      press: () => {
        if (view === "versions") showMenuAt({ view });
        else if (view) open({ view });
        else putAwayThen(() => entry.press(heldStanding));
      },
    };
  };
  function menuReading() {
    if (!menuOpen()) return { open: false };
    const at = menuAt();
    if (at?.view === "versions")
      return {
        open: true,
        key: "versions",
        title: titleOf(at),
        kind: "versions",
        ...versionsReading(),
        approval: approvalReading(),
      };
    if (at?.view === "errors")
      return {
        open: true,
        key: "errors",
        title: titleOf(at),
        kind: "errors",
        errors: errorsReading().map((error) => ({ ...error, clock: clock(error.at) })),
      };
    if (at)
      return {
        open: true,
        key: `group:${at.group}`,
        title: titleOf(at),
        kind: "group",
        entries: rows()
          .filter((entry) => groupOf(entry) === at.group && listed(entry))
          .map((entry) => menuEntry(entry, true)),
      };
    const all = rows();
    const page = all
      .filter((entry) => groupOf(entry) === "page" && listed(entry))
      .sort(
        (a, b) =>
          (OWN_VIEWS.includes(a.key) ? OWN_VIEWS.indexOf(a.key) : OWN_VIEWS.length) -
          (OWN_VIEWS.includes(b.key) ? OWN_VIEWS.indexOf(b.key) : OWN_VIEWS.length),
      );
    const groups = Object.keys(GROUPS).filter((group) =>
      all.some((entry) => groupOf(entry) === group && listed(entry)),
    );
    const errors = errorsReading();
    const offered = [
      ...(errors.length
        ? [
            {
              key: "errors",
              label: "Errors",
              value: String(errors.length),
              kind: "row",
              role: "menuitem",
              opens: true,
              urgent: errors.some((error) => !error.seen),
              press: () => {
                showMenuAt({ view: "errors" });
                seeErrors();
              },
            },
          ]
        : []),
      ...page.map((entry) => menuEntry(entry)),
      ...groups.map((group) => ({
        key: `group:${group}`,
        label: GROUPS[group],
        value: groupValue(group),
        kind: "row",
        role: "menuitem",
        opens: true,
        press: () => showMenuAt({ view: "group", group }),
      })),
      { key: "", kind: "rule" },
      ...[
        all.find((entry) => entry.key === "keyboard"),
        all.find((entry) => entry.key === `command:${FOLD}`),
      ]
        .filter(Boolean)
        .map((entry) => menuEntry(entry)),
    ];
    const now = new Map(offered.map((entry) => [entry.key, entry]));
    seats = held?.seats ?? offered;
    const reading = status();
    return {
      open: true,
      key: "root",
      kind: "root",
      held,
      tone: reading.tone,
      summary: reading.summaryParts ?? [{ text: reading.summary }],
      adds: reading.addsParts ?? [{ text: reading.adds }],
      publication: reading.publication,
      showSummary: held ? !!held.summary : !!reading.summary,
      showExplain: held ? !!held.explain : !!(reading.adds || reading.publication),
      entries: seats.map((entry) => now.get(entry.key) ?? { ...entry, disabled: true }),
    };
  }
  const menuRow = (read) => nativeHtml`<button type="button" role=${() => read().role}
    data-row=${() => read().key} title=${() => read().title}
    class="lf-fp-item" disabled=${() => read().disabled}
    data-lf-urgent=${() => (read().urgent ? "" : undefined)} data-opens=${() => (read().opens ? "" : undefined)}
    onClick=${() => read().press()}>
    <span class="lf-fp-label">${() => read().label}${Show({
      get when() {
        return read().note;
      },
      children: (_visible) => nativeHtml`
      <span class="lf-fp-note">${() => read().note}</span>`,
    })}</span>
    <span class="lf-fp-end">${Show({
      get when() {
        return read().value;
      },
      children: (_visible) => nativeHtml`
      <span class="lf-fp-value">${() => read().value}</span>`,
    })}
      ${Show({
        get when() {
          return read().shortcut;
        },
        children: (_visible) => keySequenceTemplate(() => read().shortcut),
      })}
      ${Show({
        get when() {
          return read().opens;
        },
        children: (_visible) => iconElement("next", "lf-fp-chevron"),
      })}
    </span>
  </button>`;
  const copyRow = (read) => nativeHtml`<div class="lf-fp-copy" role="none">
    <label class="lf-fp-copy-label" for=${() => `lf-fp-copy-${read().key}`}>${() => capital(read().label)}</label>
    <textarea id=${() => `lf-fp-copy-${read().key}`} class="lf-fp-copy-text" readonly wrap="off" spellcheck="false"
      rows=${() => Math.min(read().copies.split("\n").length, 3)} value=${() => read().copies}
      onFocus=${(event) => event.target.select()}></textarea>${() => read().copy}
    ${Show({
      get when() {
        return read().value;
      },
      children: (_visible) =>
        nativeHtml`<p class="lf-fp-copy-note">${() => read().value}</p>`,
    })}
  </div>`;
  const menuEntries = (read) =>
    For({
      get each() {
        return read().entries;
      },
      keyed: (entry) => `${entry.kind}:${entry.key}`,
      children: (entry) =>
        entry().kind === "rule"
          ? nativeHtml`<hr />`
          : entry().kind === "copy"
            ? [() => entry().copy]
            : entry().kind === "copy-text"
              ? copyRow(entry)
              : menuRow(entry),
    });
  function dismissMenuError(id) {
    const errors = errorsReading();
    const presses = [...menu.querySelectorAll(".lf-fp-error button")];
    const at = errors.findIndex((error) => error.id === id);
    const next = id === null ? null : (presses[at + 1] ?? presses[at - 1]);
    focusDestination(next ?? menu.querySelector(".lf-fp-menu-back"), "move");
    if (id === null) dismissErrors();
    else dismissError(id);
  }
  const showVersion = (entry) => putAwayThen(() => versionPicker.activate(entry));
  const versionsList = (read) => [
    Show({
      get when() {
        return read().latest.failed;
      },
      children: (_visible) => nativeHtml`<div class="lf-fp-failed" role="none">
      <b>${() => read().latest.label}</b><p class="lf-fp-failed-error">${() => read().latest.error}</p></div>`,
    }),
    For({
      get each() {
        return read().rows;
      },
      keyed: (entry) =>
        `${entry.version === null ? "draft" : "version"}:${entry.revision}`,
      children: (
        entry,
      ) => nativeHtml`<div class="lf-fp-version" role="none" data-current=${() => (entry().current ? "" : undefined)}>
        ${menuRow(() => ({ ...entry(), label: entry().name, value: entry().current ? "Showing" : "", role: "menuitem", title: entry().note, press: () => showVersion(entry()) }))}
        ${Show({
          get when() {
            return entry().comparable;
          },
          children: (_visible) => nativeHtml`
          <button type="button" role="menuitem" class="lf-fp-quiet lf-fp-compare"
            aria-pressed=${() => String(read().selection.on && read().selection.base === entry().version)}
            aria-label=${() => `Compare with ${entry().name}`} onClick=${() => putAwayThen(() => versionPicker.compare(entry().version))}>Compare</button>`,
        })}
      </div>`,
    }),
    Show({
      get when() {
        return !read().rows.length;
      },
      children: (_visible) =>
        nativeHtml`<p class="lf-fp-empty" role="none">Showing ${() => read().picker.token}</p>`,
    }),
    Show({
      get when() {
        return read().approval;
      },
      children: (
        approval,
      ) => nativeHtml`<hr /><div class="lf-fp-approval" role="none" title=${() => approval().reason}>
      ${menuRow(() => ({ label: approval().text, value: approval().reason, role: "menuitem", disabled: !!approval().reason && !approval().approved, press: approve }))}
    </div>`,
    }),
  ];
  const errorsList = (read) => [
    For({
      get each() {
        return read().errors;
      },
      keyed: (error) => error.id,
      children: (
        error,
      ) => nativeHtml`<div class="lf-fp-error" role="none"><p class="lf-fp-error-words" aria-hidden="true">
      <b>${() => error().message}</b><span class="lf-fp-note">${() => error().clock}</span></p>
      <button type="button" role="menuitem" class="lf-fp-quiet" aria-label=${() => `Dismiss: ${error().message}, ${error().clock}`}
        onClick=${() => dismissMenuError(error().id)}>Dismiss</button></div>`,
    }),
    Show({
      get when() {
        return !read().errors.length;
      },
      children: (_visible) =>
        nativeHtml`<p class="lf-fp-empty" role="none">No errors</p>`,
    }),
    Show({
      get when() {
        return read().errors.length > 1;
      },
      children: (_visible) => nativeHtml`<hr />
      ${menuRow(() => ({ label: "Dismiss all", role: "menuitem", press: () => dismissMenuError(null) }))}`,
    }),
  ];
  const menuTemplate = (read) => [
    Show({
      get when() {
        return read().open;
      },
      children: (_visible) => nativeHtml`
    <div class="lf-fp-menu-page" role="none">${Show({
      get when() {
        return read().key;
      },
      keyed: true,
      children: (key) => {
        if (key === "root")
          return nativeHtml`<div class="lf-fp-state" role="none" data-tone=${() => read().tone || undefined} data-held=${() => (read().held ? "" : undefined)}>
        ${Show({
          get when() {
            return read().showSummary;
          },
          children: (_visible) => nativeHtml`<span class="lf-fp-summary"
          style=${() => ({ "--lines": read().held ? String(read().held.summary) : undefined })}>${statusWords(() => read().summary)}</span>`,
        })}
        ${Show({
          get when() {
            return read().showExplain;
          },
          children: (_visible) => nativeHtml`<span class="lf-fp-explain"
          style=${() => ({ "--lines": read().held ? String(read().held.explain) : undefined })}>${statusWords(() => read().adds)}
          ${Show({
            get when() {
              return read().publication;
            },
            children: (publication) => nativeHtml`
            ${() => (read().adds.some((part) => part.text) ? " " : "")}${() => publication().copy}
            ${Show({
              get when() {
                return publication().examplesUrl;
              },
              children: (_visible) =>
                nativeHtml`<a href=${() => publication().examplesUrl}>${() => publication().examples}</a> `,
            })}
            <a href=${() => publication().installUrl} target="_blank" rel="noopener">${() => publication().install}</a>`,
          })}
        </span>`,
        })}</div>${menuEntries(read)}`;
        return nativeHtml`<div class="lf-fp-menu-name" role="none">${() => read().title}</div>
        ${key === "versions" ? versionsList(read) : key === "errors" ? errorsList(read) : menuEntries(read)}
        <div class="lf-fp-menu-rule" role="none"></div>
        <button type="button" role="menuitem" class="lf-fp-item lf-fp-menu-back"
          aria-label=${() => `Back to the page menu from ${read().title}`} onClick=${() => showMenuAt(null)}>
          <span class="lf-fp-label">${iconElement("next", "lf-fp-chevron")}Menu</span></button>`;
      },
    })}</div>`,
    }),
  ];

  // The rows read in the page's order, the one the `t` walk steps through
  // (thread/placement.js), so each thread stands among its passage's neighbours. A
  // search reads a thread's name, its messages and the words it is about, as its head
  // quotes them (`quoteReading`).
  function shownThreads() {
    const words = query.trim().toLowerCase();
    const shown = threads().filter((thread) => {
      if (words) {
        const text = [
          threadName(thread),
          quoteReading(thread, { placedAt })?.label ?? "",
          ...thread.msgs.map((m) => m.text ?? ""),
        ]
          .join(" ")
          .toLowerCase();
        return text.includes(words);
      }
      if (filter === "unread") return hasUnread(thread);
      if (filter === "drafts") return draftHasContent(replyContext(thread.key));
      if (filter === "resolved") return thread.resolved;
      return !thread.resolved;
    });
    return inPageOrder(shown, placedAt);
  }
  function threadsView() {
    return {
      kind: "threads",
      rows: shownThreads().map((thread) => ({
        key: thread.key,
        unread: hasUnread(thread),
        resolved: thread.resolved,
        yours: threadAttention(thread)?.kind === "needs_user",
        heading: threadHeadingModel(thread),
        status: threadStatus(thread, query.trim() ? null : filter),
      })),
      inventoried: inventoried(),
      empty: query.trim()
        ? "Nothing matches."
        : {
            open: "No open threads. Comment below to start one.",
            unread: "All caught up.",
            drafts: "No drafts.",
            resolved: "No resolved threads.",
          }[filter],
      loading:
        readThreads().phase === "offline"
          ? "Current threads are unavailable while the server is offline."
          : "Loading current threads…",
    };
  }

  // A thread inside the panel is drawn by Leaf's own conversation reader: the panel
  // registers as the page's primary thread presentation (application.js,
  // `registerChromeThreadPresentation`), yielding to one the page's package registers, in
  // whose reader its threads then open, and gives the open thread's transcript an outlet
  // here. Leaf draws the messages there as a card on the page draws them
  // (thread/transcript.js): progress folded behind the answer that completed it, work
  // under way as the dim working message, a rail on each unread reply, with their
  // reactions, rewrites and agent-authored widgets. The user chose that (2026-10-19)
  // over every message at full size, which stood each progress step as a reply and
  // marked nothing unread. The reader holds news that would move what the user is
  // reading behind its notice, which the panel stands among the view's controls
  // (`newsOutlet`),
  // with Next unread beside it while a reply of the thread waits unread. The
  // reply is the thread's reply box, which the reader draws in the field below rather
  // than in the outlet. A thread anchored to a passage stays the page's where the page
  // draws it: its card opens beside the words it is about, and the panel shows it only
  // where nothing on the page does (`reveal`), or for a message of it the view shows.
  let presentation = null;
  // The thread's held news is a fact about the thread, so it reads whole after the way
  // back, at the start of the view's controls, and pressing it shows what was held. The
  // room the way back leaves gives it the room it takes, so news arriving moves nothing
  // else among the controls or in the messages above (floating-panel.css,
  // `.lf-fp-facts`). The user chose this on 16 October over the notice at the end of the
  // first message's head, cut to 5rem there ("2 new rep…"), and over the news joining
  // New reply at the view's foot. Each thread's controls draw an outlet of their own, so
  // the notice of the thread the user leaves goes with them rather than standing in the
  // next one's until the reader draws that.
  const newsOutlet = () => controls.querySelector(".lf-fp-news-outlet");
  // The view standing open, rather than one still leaving.
  const shownView = () => stage.querySelector(".lf-fp-view:not([data-leaving])");
  // The rows of the open view's list, which the arrows walk and Tab stands at one of. A
  // version's Compare is a stop of the walk after its version, so the list stays one
  // stop for Tab; an On card's own controls stay Tab's, inside the card the walk stands on.
  const LIST_ROWS = Object.freeze({
    threads: ".lf-fp-thread",
    queue: ".lf-fp-on-item",
    leaves: ".lf-fp-page[href]",
  });
  const listRows = () => {
    const rows = LIST_ROWS[trail().at(-1)?.view];
    const view = shownView();
    return rows && view ? [...view.querySelectorAll(rows)] : [];
  };
  const threadRows = () => (trail().at(-1)?.view === "threads" ? listRows() : []);
  const openView = () =>
    stage.querySelector('.lf-fp-view[data-view="thread"]:not([data-leaving])');
  const outletOf = () => openView()?.querySelector(".lf-fp-outlet") ?? null;
  function nominate(collection, parts) {
    const top = trail().at(-1);
    // On draws each question asked in words as its message, in its card's outlet.
    if (top?.view === "queue") {
      for (const outlet of stage.querySelectorAll(
        ".lf-fp-view:not([data-leaving]) .lf-fp-asked",
      )) {
        const { thread: key, message } = outlet.dataset;
        const thread = collection.threads.find((candidate) => candidate.key === key);
        if (thread?.msgs.some((candidate) => candidate.key === message))
          parts.message(key, message, outlet);
      }
      return;
    }
    if (top?.view !== "thread") return;
    const outlet = outletOf();
    const thread = collection.threads.find(
      (candidate) => candidate.key === top.thread || candidate.id === top.thread,
    );
    if (!outlet || !thread) return;
    parts.transcript(thread.key, outlet);
    const news = newsOutlet();
    if (news) parts.news(thread.key, news);
    if (replyOutlet.isConnected)
      parts.reply(thread.key, replyOutlet, replyOptionsFor(thread.key));
  }
  // A deliberate view change shows the reader the whole current thread.
  function present({ release = false } = {}) {
    if (!presentation) return Promise.resolve();
    return presentation
      .update({ release })
      .then(() => {
        if (holdRoom()) paint();
        landReader();
      })
      .catch(() => {});
  }

  // A thread's reply and Resolve stand outside its view, in the field and among the
  // view's controls, so the view declares them as its thread's own (thread/focus.js,
  // `threadPart`): while it is the thread open, the reply box in the field where the
  // thread takes a reply, and Resolve; and the view itself as the thread whole. The
  // controls are the thread's own, as a card's head is, and the field's outlet holds its
  // reply, so both are drawings of the thread too, declaring the same parts: `r` on
  // Resolve there settles the thread as on a card's, `e` there finds the messages in the
  // view above it, and Escape from the reply returns to the view, as a card's reply
  // returns to the card.
  const openIn = (view) => {
    const top = trail().at(-1);
    const thread = top?.view === "thread" ? threadByKey(top.thread) : null;
    return thread &&
      !view.hasAttribute("data-leaving") &&
      drawnThreadId(view) === thread.id
      ? thread
      : null;
  };
  const viewParts = Object.freeze({
    reply: (view) => {
      const thread = openIn(view);
      return thread && replyAvailable(thread) ? replyInput() : null;
    },
    settlement: (view) =>
      openIn(view) ? controls.querySelector(".lf-fp-settle") : null,
    whole: (view) => (openIn(view) ? openView() : null),
  });
  const declareView = (view) => view && declareThreadParts(view, viewParts);
  // Each view scrolls what it holds, so each is a reading region while it stands, and a
  // landing in it, as a rewrite opening on a message above its top, scrolls the view
  // rather than the page its fixed box stands still over (reading-regions.js).
  const viewRegions = new Map();
  let regionCount = 0;
  function regionViews() {
    for (const [view, stop] of viewRegions)
      if (!view.isConnected) {
        stop();
        viewRegions.delete(view);
      }
    for (const view of stage.querySelectorAll(".lf-fp-view"))
      if (!viewRegions.has(view))
        viewRegions.set(
          view,
          registerReadingRegion({
            id: `floating-panel-view-${++regionCount}`,
            host: view,
            body: view,
          }),
        );
  }
  declareView(controls);
  declareView(replyOutlet);

  // The words a thread is about, as its card's head quotes them (thread-card.js,
  // `quoteReading`), above its messages, in three lines: where they still stand on the
  // page, On the page goes there; where they no longer do, as for a thread a revision
  // detached from its passage, the quotation the thread kept is all that is left of
  // them, so Full quote shows the whole of it here, its press standing above the words
  // it grows so the press never moves itself. It shows only where three lines cut them.
  let quoteExpanded = false;
  function measureQuote() {
    const quote = stage.querySelector(".lf-fp-view:not([data-leaving]) .lf-fp-quote");
    const press = quote?.previousElementSibling;
    if (press?.classList.contains("lf-quote-expand"))
      keeps(
        press,
        "hidden",
        !quoteExpanded && quote.scrollHeight <= quote.clientHeight ? "" : null,
      );
  }
  // The press resizes the view the panel's other observers watch, so it shows in the
  // next frame rather than inside this observer's delivery.
  const quoteWatch = sizeObserver(() => nextRender(measureQuote));
  function threadView(key) {
    const thread = threadByKey(key);
    const quote = thread && quoteReading(thread, { placedAt });
    return {
      kind: "thread",
      exists: !!thread,
      quote: quote
        ? {
            ...quote,
            expanded: !!(quote.localReading && quoteExpanded),
            disclosureExpanded: quoteExpanded,
          }
        : null,
      waiting: waiting?.key === key ? waiting : null,
    };
  }
  const quoteHead = (read) => [
    Show({
      get when() {
        return read().quote;
      },
      children: (quote) => nativeHtml`
    <header class="lf-fp-quote-head">
      ${Show({
        get when() {
          return quote().localReading;
        },
        children: (_visible) => nativeHtml`
        <button type="button" class="lf-thread-disclosure lf-quote-expand" aria-label="Full quote" hidden
          aria-expanded=${() => String(quote().disclosureExpanded)} aria-controls="lf-fp-quote"
          onClick=${() => {
            quoteExpanded = !quoteExpanded;
            paint();
          }}>Full quote</button>`,
      })}
      <blockquote ref=${(node) => {
        quoteWatch.observe(node);
        onCleanup(() => quoteWatch.unobserve(node));
      }}
        id="lf-fp-quote" class=${() => `lf-quote lf-fp-quote${quote().anchored && !quote().found ? " detached" : ""}`}
        data-expanded=${() => String(quote().expanded)} title=${() => (quote().anchored && !quote().found ? quote().title : undefined)}>
        <span class="lf-quote-label">${() => quote().label}</span>
        ${Show({
          get when() {
            return quote().outdated || quote().changed;
          },
          children: (_visible) => nativeHtml`
          <span class="lf-anchor-status">${() => (quote().outdated ? "Earlier data" : "Changed")}</span>`,
        })}
      </blockquote>
    </header>`,
    }),
  ];

  // ---------- On: obligations answered where they are read ----------
  // The lists are the publisher's (`readQueues`): what waits on the user and on the
  // agent, a tab each, and under each what left it, its Done (`owner`). The view has no
  // name of its own: its title is the open tab's. An item the user answers here stays
  // where it stood, saying its answer and offering Undo, until the view closes, so
  // answering one obligation never carries the next under the pointer. Done stands open under
  // the list rather than folded, since a fold opening would grow the view up from under
  // the pointer that opened it.
  let queueTab = "you";
  let seated = null; // queue item keys present in the open On view
  // The height each seated card first stood at, which it keeps while seated, so an
  // answer that shortens it moves nothing below.
  const seatHeights = new Map();
  const QUEUE_TABS = Object.freeze({ you: "user", agent: "agent" });
  // The agent's plan has a tab of its own beside the two lists, while there is a plan,
  // or while the view stands on it. The lists stay as they are, a planned to-do
  // included, since the plan arranges items without owning them. The user chose this
  // on 2026-10-19 over the plan heading On <agent>, with the to-dos it leaves out
  // following as rows.
  const queueTabs = () =>
    readPlan()?.steps.length || queueTab === "plan"
      ? [...Object.keys(QUEUE_TABS), "plan"]
      : Object.keys(QUEUE_TABS);
  // Turning to another list seats its items afresh, in a view that fits it.
  const chooseQueueTab = (tab) => {
    if (tab === queueTab) return false;
    queueTab = tab;
    seated = null;
    seatHeights.clear();
    refit();
    return true;
  };
  // The On me door, as the mark and `g M` press it: the view on the
  // user's list, turned to it where the view shows the agent's, else opened or closed.
  function openOnMe() {
    const turned = chooseQueueTab("you");
    if (turned && trail().at(-1)?.view === "queue") paint();
    else open({ view: "queue" });
  }
  // Each list in the `m` walk's order (queue-walk.js, `inWalkOrder`), so the cards the
  // walk outlines (`walkedStop`) follow one another down the list.
  const queueLists = () => {
    const reading = readQueues();
    if (reading.phase !== "ready") return { you: [], agent: [], done: [] };
    return {
      you: inWalkOrder(reading.on_user),
      agent: inWalkOrder(reading.on_agent),
      done: inWalkOrder(
        reading.done.filter((item) => item.owner === QUEUE_TABS[queueTab]),
      ),
    };
  };

  // The undo list's entry for the gesture that answered an obligation, where it can still be
  // taken back (undo.js).
  const answerGesture = (item) => {
    const id = item?.answer?.event?.id ?? item?.answer?.event;
    if (!id) return null;
    const entry = runtime.undo.find(
      ({ event }) => event.id === id || event.attempt === id,
    );
    return entry?.event ?? null;
  };
  const tabLabel = (tab) =>
    tab === "plan" ? "Plan" : tab === "agent" ? `On ${agentName()}` : "On me";
  // The stop the `m` walk stands on while the field says its position
  // (keyboard/status-context.js): its card in On me wears the ring a focused card
  // wears, and the list brings it into view as the walk reaches it (`landWalked`), so
  // the list follows the walk rather than standing where it was.
  const walkedStop = () => {
    const { walk } = statusContextReading();
    return walk?.shown && walk.kind === "queue" ? walk.target : null;
  };
  let walkedLanded = null;
  function landWalked() {
    const key = trail().at(-1)?.view === "queue" ? walkedStop() : null;
    if (key === walkedLanded) return;
    walkedLanded = key;
    const view = shownView();
    const card = key && view?.querySelector(".lf-fp-on-item[data-walked]");
    if (card) scrollIntoView(card, { block: "nearest", within: view });
  }

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
    done: "check",
    working: "activity",
    failed: "cross",
    dropped: "subtract",
  });
  const planItemIds = (steps) =>
    steps.flatMap((step) => [
      ...(step.item ? [step.item.id] : []),
      ...planItemIds(step.steps),
    ]);
  // Where an item stands in the plan: its goal, and its place among that goal's steps,
  // counted as the goal's own count is, without the dropped ones (`plans.py`).
  function planPlace(id) {
    for (const goal of readPlan()?.steps ?? []) {
      const counted = goal.steps.filter((step) => step.state !== "dropped");
      const index = counted.findIndex(
        (step) => step.item?.id === id || planItemIds(step.steps).includes(id),
      );
      if (index < 0) continue;
      const place = `step ${index + 1} of ${counted.length}`;
      return goal.title ? `${goal.title} · ${place}` : capital(place);
    }
    return null;
  }
  const planStep = (step) => ({
    ...step,
    time: step.since ? shortAgo(step.since) : "",
    steps: step.steps.map(planStep),
  });
  const planCards = () => (readPlan()?.steps ?? []).map(planStep);
  function onItemCard(item, list) {
    const record = carriesObligation(item) ? item.obligation : null;
    const thread = item.thread ? threadByKey(item.thread) : null;
    const inWords = record !== null && answeredInWords(record);
    const asking =
      inWords && thread
        ? thread.msgs.find((candidate) => candidate.id === record.message)
        : null;
    const message = asking && presentation?.primary !== false ? asking : null;
    const title = message
      ? (thread.title ?? (thread.root.id === message.id ? "" : threadName(thread)))
      : asking
        ? threadName(thread)
        : queueTitle(item);
    const said = message
      ? ""
      : asking
        ? messageReading(asking, { reactions: [], workflows: [] }).body.plainText
        : record?.prompt?.text;
    const prompt = said && said.trim() !== title.trim() ? said : "";
    const heading =
      thread && title === threadName(thread)
        ? threadHeadingModel(thread)
        : { pending: false, name: title };
    const answered = record && record.status !== "open";
    const choices =
      record && !answered && record.source.kind === "widget" && !inWords
        ? obligationView.choicesOf(record)
        : null;
    const gesture = answered ? answerGesture(record) : null;
    const discuss = thread
      ? [
          {
            key: "discuss",
            label: "Discuss",
            quiet: true,
            run: () => open({ view: "thread", thread: thread.key }),
          },
        ]
      : [];
    let saidAnswer = "";
    let answers = [];
    if (list === "done" && !record) {
      saidAnswer = [itemOutcome(item), shortAgo(item.ended)].filter(Boolean).join(" ");
      answers = discuss;
    } else if (list !== "you" && !answered) {
      saidAnswer = item.todo?.running?.text ?? workflowStep(item.workflow);
      answers = discuss;
    } else if (answered) {
      saidAnswer = obligationEnding(record);
      answers = gesture
        ? [{ key: "undo", label: "Undo", quiet: true, run: () => withdraw(gesture) }]
        : [];
    } else if (record?.source.kind === "approval") {
      const approval = approvalReading();
      answers = [
        {
          key: "approve",
          label: approval?.text ?? "Approve version",
          disabled: !!approval?.reason,
          title: approval?.reason,
          run: approve,
        },
      ];
    } else if (choices?.length)
      answers = [
        ...choices.map((choice, index) => ({
          key: `choice:${index}`,
          label: capital(choice.label),
          pressed: String(choice.chosen),
          run: () => {
            choice.press();
            paint();
          },
        })),
        ...discuss,
      ];
    else if (item.offers?.done)
      answers = [
        {
          key: "done",
          label: "Done",
          run: () => queueActions.done(queueItemKey(item)),
        },
        ...discuss,
      ];
    else if (inWords && thread)
      answers = [
        {
          key: "reply",
          label: "Reply",
          run: () => open({ view: "thread", thread: thread.key }),
        },
      ];
    else answers = discuss;
    if (arrivesAt(item))
      answers.push({
        key: "show",
        label: "Show",
        quiet: true,
        show: true,
        run: () => {
          close();
          void queueActions.open(queueItemKey(item));
        },
      });
    const key = queueItemKey(item);
    const stop = queueStop(item);
    return {
      key,
      list,
      obligation: record?.id,
      approval: record?.source.kind === "approval",
      walked: queueTab === "you" && walkedStop() === stop.key,
      minHeight: seatHeights.has(key) ? `${seatHeights.get(key)}px` : undefined,
      about:
        queueTab === "you"
          ? [stop.noun, planPlace(item.id)].filter(Boolean).join(" · ")
          : "",
      title,
      heading,
      message: message ? { key: message.key, thread: thread.key } : null,
      prompt,
      saidAnswer,
      answers,
    };
  }
  const planStepView = (
    read,
  ) => nativeHtml`<li class="lf-fp-plan-step" data-state=${() => read().state}>
    <span class="lf-fp-plan-mark" role="img" aria-label=${() => PLAN_STATES[read().state]}>
      ${Show({
        get when() {
          return PLAN_MARKS[read().state];
        },
        keyed: true,
        children: (mark) => iconElement(mark, "lf-action-icon"),
      })}
    </span><span class="lf-fp-plan-title">${() => read().title ?? ""}</span>
    ${Show({
      get when() {
        return read().owner === "user" && read().state === "open";
      },
      get fallback() {
        return untrack(() => [
          Show({
            get when() {
              return read().state === "working" && read().time;
            },
            children: (_visible) => nativeHtml`
        <span class="lf-fp-plan-time">${() => read().time}</span>`,
          }),
        ]);
      },
      children: (_visible) =>
        nativeHtml`<button type="button" class="lf-fp-plan-tag" onClick=${() => {
          chooseQueueTab("you");
          paint();
          focusDestination(
            controls.querySelector('.lf-fp-filters [aria-pressed="true"]'),
            "move",
          );
        }}>On me</button>`,
    })}
    ${Show({
      get when() {
        return read().running;
      },
      children: (_visible) =>
        nativeHtml`<span class="lf-fp-plan-line">${() => read().running?.text}</span>`,
    })}
    ${Show({
      get when() {
        return read().steps.length;
      },
      children: (_visible) => nativeHtml`<ol class="lf-fp-plan-steps">
      ${For({
        get each() {
          return read().steps;
        },
        keyed: false,
        children: (step) => planStepView(step),
      })}</ol>`,
    })}
  </li>`;
  const onItemView = (
    read,
  ) => nativeHtml`<section class="lf-fp-on-item" data-list=${() => read().list} data-key=${() => read().key}
    data-obligation=${() => read().obligation} data-approval=${() => (read().approval ? "" : undefined)}
    data-walked=${() => (read().walked ? "" : undefined)} style=${() => ({ "min-height": read().minHeight })}>
    ${Show({
      get when() {
        return read().about;
      },
      children: (_visible) =>
        nativeHtml`<p class="lf-fp-on-kind">${() => read().about}</p>`,
    })}
    ${Show({
      get when() {
        return !!read().message;
      },
      get fallback() {
        return untrack(() => [
          Show({
            get when() {
              return read().prompt;
            },
            get fallback() {
              return untrack(
                () =>
                  nativeHtml`<p class="lf-fp-prompt">${threadHeadingView(() => read().heading)}</p>`,
              );
            },
            children: (_visible) =>
              nativeHtml`<h3 class="lf-fp-on-title">${threadHeadingView(() => read().heading)}</h3><p class="lf-fp-prompt">${() => read().prompt}</p>`,
          }),
        ]);
      },
      children: (_visible) => nativeHtml`
        ${Show({
          get when() {
            return read().title;
          },
          children: (_visible) =>
            nativeHtml`<h3 class="lf-fp-on-title">${threadHeadingView(() => read().heading)}</h3>`,
        })}
        <div class="lf-fp-asked lf-fp-outlet" data-thread=${() => read().message?.thread} data-message=${() => read().message?.key}></div>`,
    })}
    <div class="lf-fp-answers">
      ${Show({
        get when() {
          return read().saidAnswer;
        },
        children: (_visible) =>
          nativeHtml`<span class="lf-fp-said">${() => read().saidAnswer}</span>`,
      })}
      ${For({
        get each() {
          return read().answers;
        },
        keyed: (answer) => answer.key,
        children: (answer) => nativeHtml`
        <button type="button" class=${() => `${answer().quiet ? "lf-fp-quiet" : "lf-fp-answer"}${answer().show ? " lf-fp-show" : ""}`}
          aria-pressed=${() => answer().pressed} aria-disabled=${() => (answer().disabled ? "true" : undefined)}
          title=${() => answer().title} onClick=${() => answer().run()}>${() => answer().label}</button>`,
      })}
    </div>
  </section>`;

  // A thread's view, its head and its reply stand at what the thread is about, and an On
  // card at the obligation it shows (standing-target.js, `declareSide`), as the side
  // panel's thread cards and On rows did. So an ask a thread or card in the panel is
  // about wears its ring and takes its digits there, whether the thread is open or
  // resolved. In a thread's view the thread's own keys stay its own, so only `m`, where
  // the thread is not a stop of its own, steps from the ask; from an On card `m`, `t`,
  // `c` and `e` all start at its obligation. An ask in a reply stands for itself. The
  // panel shows them beside the page, so the user in it has not arrived at the ask
  // (`beside`).
  declareSide(
    (node) => {
      const part = [openView(), controls, replyOutlet].find(
        (at) => at && under(node, at),
      );
      const thread = part && openIn(part);
      if (thread) return placedAt(thread.id)?.place ?? null;
      const id = under(node, stage)
        ? closestAcross(node, ".lf-fp-on-item[data-obligation]")?.dataset.obligation
        : null;
      const record = id && readObligations().all.find((item) => item.id === id);
      return record ? obligationPlace(record).node : null;
    },
    { beside: true },
  );

  // The version's approval is answered here: arriving at it, as `m` and an On me row
  // do, opens this view on its card and stands on its
  // Approve, or once it is answered on its Undo, or the card itself.
  const approvalControl = () => {
    const card = stage.querySelector(".lf-fp-view:not([data-leaving]) [data-approval]");
    return card?.querySelector("button") ?? card;
  };
  // An approval is an obligation, always On me's, open or done.
  function arriveAtApproval() {
    chooseQueueTab("you");
    open({ view: "queue" }, { reopen: true, focus: false });
    paint();
    const target = approvalControl();
    if (!target) return Promise.resolve(false);
    scrollIntoView(target, { block: "nearest" });
    focusDestination(target, "move");
    return Promise.resolve(true);
  }

  function onView() {
    if (queueTab === "plan") return { kind: "plan", goals: planCards() };
    const lists = queueLists();
    const all = [...lists.you, ...lists.agent, ...lists.done];
    const byKey = new Map(all.map((item) => [queueItemKey(item), item]));
    const current = lists[queueTab].map(queueItemKey);
    seated = [
      ...(seated ?? []).filter((key) => byKey.has(key)),
      ...current.filter((key) => !(seated ?? []).includes(key)),
    ];
    const listOf = (item) =>
      lists.you.includes(item) ? "you" : lists.agent.includes(item) ? "agent" : "done";
    return {
      kind: "queue",
      items: inWalkOrder(seated.map((key) => byKey.get(key))).map((item) =>
        onItemCard(item, listOf(item)),
      ),
      finished: lists.done
        .filter((item) => !seated.includes(queueItemKey(item)))
        .map((item) => onItemCard(item, "done")),
      empty: `Nothing waiting on ${queueTab === "you" ? "me" : agentName()}.`,
    };
  }
  function viewReading(route) {
    const body =
      route.view === "threads"
        ? threadsView()
        : route.view === "thread"
          ? threadView(route.thread)
          : route.view === "queue"
            ? onView()
            : { kind: "leaves", rows: leavesRows(runtime.state) };
    return {
      rows: [],
      items: [],
      goals: [],
      finished: [],
      quote: null,
      waiting: null,
      exists: false,
      inventoried: false,
      empty: "",
      loading: "",
      ...body,
    };
  }
  const pageFace = (
    read,
  ) => nativeHtml`<span class=${() => `lf-dot${read().tone ? ` ${read().tone}` : ""}`} aria-hidden="true"></span>
    <span class="lf-fp-label">${() => read().title}</span><span class="lf-fp-value">${() => (read().self ? "This page" : read().line)}</span>`;
  const viewTemplate = (read) => [
    Show({
      get when() {
        return read().kind;
      },
      keyed: true,
      children: (kind) => {
        if (kind === "threads")
          return nativeHtml`<div class="lf-fp-list">
      ${For({
        get each() {
          return read().rows;
        },
        keyed: (thread) => thread.key,
        children: (thread) => nativeHtml`
        <button type="button" class="lf-fp-thread" data-key=${() => thread().key} data-unread=${() => (thread().unread ? "" : undefined)}
          data-resolved=${() => (thread().resolved ? "" : undefined)} data-yours=${() => (thread().yours ? "" : undefined)}
          onClick=${() => open({ view: "thread", thread: thread().key })}>
          <span class="lf-fp-news-mark" aria-hidden="true"></span><span class="lf-fp-label">${threadHeadingView(() => thread().heading)}</span>
          <span class="lf-fp-value">${() => thread().status}</span></button>`,
      })}
      ${Show({
        get when() {
          return !read().rows.length && read().inventoried;
        },
        children: (_visible) =>
          nativeHtml`<p class="lf-fp-empty">${() => read().empty}</p>`,
      })}
      ${Show({
        get when() {
          return !read().inventoried;
        },
        children: (_visible) =>
          nativeHtml`<p class="lf-fp-empty">${() => read().loading}</p>`,
      })}
    </div>`;
        if (kind === "thread")
          return [
            Show({
              get when() {
                return read().exists;
              },
              children: (_visible) => nativeHtml`
      ${quoteHead(read)}<div class="lf-fp-messages lf-fp-outlet" data-lf-reflow="append"></div>
      ${Show({
        get when() {
          return read().waiting;
        },
        children: (_visible) => nativeHtml`<div class="lf-fp-foot">
        <button type="button" class="lf-fp-new-reply" onClick=${showAnswer}>${iconElement("down", "lf-action-icon")}${() => read().waiting?.label}</button></div>`,
      })}`,
            }),
          ];
        if (kind === "plan")
          return [
            For({
              get each() {
                return read().goals;
              },
              keyed: false,
              children: (goal) => nativeHtml`
      <section class="lf-fp-plan"><h3 class="lf-fp-plan-goal"><span>${() => goal().title ?? ""}</span><span class="lf-fp-plan-count">${() => goal().done} of ${() => goal().total}</span></h3>
      <ol class="lf-fp-plan-steps">${For({
        get each() {
          return goal().steps;
        },
        keyed: false,
        children: (step) => planStepView(step),
      })}</ol></section>`,
            }),
            Show({
              get when() {
                return !read().goals.length;
              },
              children: (_visible) => nativeHtml`<p class="lf-fp-empty">No plan.</p>`,
            }),
          ];
        if (kind === "queue")
          return [
            For({
              get each() {
                return read().items;
              },
              keyed: (item) => item.key,
              children: (item) => onItemView(item),
            }),
            Show({
              get when() {
                return !read().items.length;
              },
              children: (_visible) =>
                nativeHtml`<p class="lf-fp-empty">${() => read().empty}</p>`,
            }),
            Show({
              get when() {
                return read().finished.length;
              },
              children: (_visible) => nativeHtml`<h3 class="lf-fp-on-done">Done</h3>
        ${For({
          get each() {
            return read().finished;
          },
          keyed: (item) => item.key,
          children: (item) => onItemView(item),
        })}`,
            }),
          ];
        if (kind === "leaves")
          return nativeHtml`<div class="lf-fp-list">
      ${For({
        get each() {
          return read().rows;
        },
        keyed: (row) => row.key,
        children: (row) =>
          row().self
            ? nativeHtml`<div class="lf-fp-page" title=${() => row().account}>${pageFace(row)}</div>`
            : nativeHtml`<a class="lf-fp-page" data-key=${() => row().key} href=${() => row().href} target="_blank" rel="noopener" title=${() => row().account}>${pageFace(row)}</a>`,
      })}
      ${Show({
        get when() {
          return !read().rows.length;
        },
        children: (_visible) =>
          nativeHtml`<p class="lf-fp-empty">No pages are live.</p>`,
      })}</div>`;
      },
    }),
  ];

  // ---------- the head and the controls: the view's name, and its presses ----------
  // A tab with a count (`count(name)` a number rather than null) says it even at zero,
  // in a quieter ink, in a room kept for two digits, so news changing the count moves
  // no tab beside it and no tab stands with a blank where its count would go.
  // Rejected: a blank at zero, which reads as a gap after the word, and the word
  // centred in a room wider on both sides, which stood it off centre once it had a
  // count, as On me nearly always does.
  const tabs = (
    read,
    choose,
  ) => nativeHtml`<div class="lf-fp-filters" role="group" aria-label="Show">
    ${For({
      get each() {
        return read().tabs;
      },
      keyed: (tab) => tab.name,
      children: (tab) => nativeHtml`
      <button type="button" aria-pressed=${() => String(read().current === tab().name)} onClick=${() => {
        refit();
        choose(tab().name);
      }}>
        ${() => tab().label}${Show({
          get when() {
            return tab().count !== null;
          },
          children: (_visible) => [
            " ",
            nativeHtml`<span class="lf-fp-count"
          data-zero=${() => (!tab().count ? "" : undefined)}>${() => tab().count}</span>`,
          ],
        })}
      </button>`,
    })}</div>`;
  // Threads' own search, which its search button and `/` in Threads open: a fresh
  // search the first time, and the one standing, words kept, after that.
  function findThreads() {
    if (!searching) {
      searching = true;
      query = "";
      refit();
    }
    searchFocus = { input: threadSearchInput, current: retainUserIntent() };
    paint();
  }
  // The view's name, over it. On's is its selected tab's, which the tabs at its foot
  // already show, so the heading names the view to assistive tech alone. A thread's
  // says when its title is still on its way (`threadHeading`).
  const headReading = (top) => {
    const thread = top?.view === "thread" ? threadByKey(top.thread) : null;
    return {
      top,
      heading: thread
        ? threadHeadingModel(thread)
        : { pending: false, name: top ? titleOf(top) : "" },
    };
  };
  const headTemplate = (read) => [
    Show({
      get when() {
        return read().top;
      },
      children: (_visible) => nativeHtml`
    <h2 class=${() => (read().top?.view === "queue" ? "lf-fp-title lf-quiet" : "lf-fp-title")}>${threadHeadingView(() => read().heading)}</h2>`,
    }),
  ];
  function controlsReading(top) {
    if (!top)
      return {
        top: null,
        kind: null,
        parent: null,
        tabs: { current: null, tabs: [] },
        searching: false,
        query: "",
        thread: null,
      };
    const parent = trail().at(-2);
    const thread = top.view === "thread" ? threadByKey(top.thread) : null;
    const kind = thread ? "thread" : top.view;
    const news = newCount();
    const lists = top.view === "queue" ? queueLists() : null;
    const tabNames =
      top.view === "threads" ? FILTERS : top.view === "queue" ? queueTabs() : [];
    const current = top.view === "threads" ? filter : queueTab;
    const tabReading = {
      current,
      tabs: tabNames.map((name) => ({
        name,
        label: top.view === "threads" ? capital(name) : tabLabel(name),
        count:
          top.view === "threads"
            ? name === "unread"
              ? news
              : name === "open"
                ? openCount()
                : null
            : name === "plan"
              ? null
              : lists[name].length,
      })),
    };
    const inMessage = Boolean(thread && placedAt(thread.id)?.message);
    if (thread)
      onPageSeat ||= Boolean(thread.anchor) && (inMessage || !unplaced.has(thread.key));
    return {
      top,
      kind,
      parent: parent ? titleOf(parent) : null,
      tabs: tabReading,
      searching: top.view === "threads" && searching,
      query,
      thread: thread
        ? {
            key: thread.key,
            resolved: thread.resolved,
            unread: thread.unread.length,
            unreadSeat,
            onPageSeat,
            anchor: !!thread.anchor,
            placeLabel: inMessage ? "In its message" : "On the page",
            disabled: !(thread.resolved ? thread.offers.reopen : thread.offers.resolve),
            onPage: () => {
              if (inMessage) {
                void openThreadSubject(thread.id, { intent: retainUserIntent() });
                return;
              }
              const intent = retainUserIntent();
              const place = placedAt(thread.id)?.place;
              if (place) reveal(place, intent);
              close();
              void present({ release: true }).then(() =>
                threadActions.open(thread.key, { part: null, intent }),
              );
            },
            settle: () => {
              if (!thread.resolved) dismissReply(thread.key);
              void settleThread({
                parent: () => thread.id,
                key: thread.key,
                resolved: !!thread.resolved,
                prepareLanding: () =>
                  thread.resolved ? reopenLanding() : resolveLanding(thread),
                ...settlement,
              }).catch(() => {});
            },
          }
        : null,
    };
  }
  const chooseThreadTab = (name) => {
    filter = name;
    query = "";
    paint();
  };
  const chooseOnTab = (tab) => {
    chooseQueueTab(tab);
    paint();
  };
  function toggleSearch() {
    if (!searching) findThreads();
    else closeThreadSearch();
  }
  const controlsTemplate = (read) => [
    Show({
      get when() {
        return read().top;
      },
      children: (_visible) => nativeHtml`
    <div class="lf-fp-crumb">
      ${Show({
        get when() {
          return read().kind === "queue";
        },
        children: (_value) => tabs(() => read().tabs, chooseOnTab),
      })}
      ${Show({
        get when() {
          return read().kind !== "queue" && read().parent;
        },
        children: (_value) =>
          nativeHtml`<button type="button" class="lf-fp-back" aria-label=${() => `Back to ${read().parent}`} onClick=${back}>${iconElement("next", "lf-fp-chevron")}${() => read().parent}</button>`,
      })}
      ${Show({
        get when() {
          return read().thread?.key;
        },
        keyed: true,
        children: (_value) =>
          nativeHtml`<span class="lf-fp-facts"><span class="lf-fp-news-outlet"></span></span>`,
      })}
    </div>
    <div class="lf-fp-aux">
      ${Show({
        get when() {
          return read().kind === "threads";
        },
        children: (_visible) => nativeHtml`
        ${tabs(() => read().tabs, chooseThreadTab)}<button type="button" class="lf-fp-icon-btn" aria-label="Find a thread or message"
          aria-pressed=${() => String(read().searching)} onClick=${toggleSearch}>${iconElement("search", "lf-action-icon")}</button>`,
      })}
      ${Show({
        get when() {
          return read().thread;
        },
        children: (thread) => nativeHtml`
        ${Show({
          get when() {
            return thread().unreadSeat;
          },
          children: (
            _visible,
          ) => nativeHtml`<button type="button" class="lf-fp-next-unread"
          disabled=${() => !thread().unread} data-unoffered=${() => (!thread().unread ? "" : undefined)} onClick=${() => void firstUnread(thread().key)}>
          ${iconElement("down", "lf-action-icon")}Next unread</button>`,
        })}
        ${Show({
          get when() {
            return thread().onPageSeat;
          },
          children: (_visible) => nativeHtml`<button type="button" class="lf-fp-quiet"
          disabled=${() => !thread().anchor} data-unoffered=${() => (!thread().anchor ? "" : undefined)} onClick=${() => thread().onPage()}>${() => thread().placeLabel}</button>`,
        })}
        <button type="button" class=${() => `lf-fp-icon-btn lf-fp-settle ${thread().resolved ? "lf-reopen" : "lf-resolve"}`}
          aria-label=${() => (thread().resolved ? "Reopen" : "Resolve thread")}
          title=${() => (thread().resolved ? "Reopen" : "Resolve thread")}
          aria-disabled=${() => String(thread().disabled)} onClick=${() => thread().settle()}>
          ${iconElement("check", "lf-action-icon")}
        </button>`,
      })}
    </div>
  `,
    }),
  ];

  // ---------- paint ----------
  function setRest(rest) {
    const before = trail().at(-1);
    // Folding takes away whatever the user stood on in the panel but the leaf, so it
    // keeps them on the leaf it folds to; from the page they stay where they are.
    const inside = standingIn(host);
    prefs().setRest(rest);
    flush(() => setTrail(() => []));
    flush(() => setMenuOpen(() => false));
    flush(() => setMenuAt(() => null));
    menuRoom = null;
    held = null;
    transition(before, { focus: false });
    if (inside) focusDestination(leaf, "return");
  }

  // A paint can blur what it removes, and the blur asks for a paint; that one runs
  // once this has finished rather than inside it. Every paint runs through the panel's
  // LeafElement host, so the readings it draws repaint it whichever input
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
    painting = true;
    const commit = renderCommit(() => {
      const top = trail().at(-1);
      if (top?.view === "thread" && !threadByKey(top.thread)) close();
      holdRoom();
      paintNow();
      afterRender(() => {
        if (holdMenu()) paintNow();
        afterRender(() => {
          landReader();
          seatOnItems();
          landWalked();
        });
      });
    });
    return commit.ready.finally(() => {
      painting = false;
      if (again) {
        again = false;
        paint();
      }
    });
  }
  // A card's seat is the height it first stands at once its message is drawn; a card
  // whose message Leaf's reader has not drawn yet asks it to (`nominate`), once, and
  // releases what the reader holds back, since a thread it holds as news would leave the
  // card standing without its question (thread/held-news.js).
  const asked = new WeakSet();
  function seatOnItems() {
    if (trail().at(-1)?.view !== "queue") return;
    let draw = false;
    for (const card of stage.querySelectorAll(
      ".lf-fp-view:not([data-leaving]) .lf-fp-on-item[data-key]",
    )) {
      const outlet = card.querySelector(".lf-fp-asked:empty");
      if (outlet) {
        draw ||= !asked.has(outlet);
        asked.add(outlet);
      } else if (!seatHeights.has(card.dataset.key))
        seatHeights.set(card.dataset.key, card.getBoundingClientRect().height);
    }
    if (draw) void present({ release: true });
  }
  // A thread the reader opens, or answers, or asks to see the news of, stands at its end,
  // once the drawing it waits for lands: on the panel's paint, the reader's presentation,
  // or the outlet's resize (`fit`).
  function landReader() {
    const top = trail().at(-1);
    if (!landAtEnd || top?.view !== "thread" || top.thread !== landAtEnd.key) return;
    const view = stage.querySelector(
      '.lf-fp-view[data-view="thread"]:not([data-leaving])',
    );
    if (!view || drawnTurns() <= landAtEnd.after) return;
    landAtEnd = null;
    scrollToEnd(view);
    decideUnreadSeat();
  }
  function paintNow() {
    const top = trail().at(-1) ?? null;
    const search = activeSearch();
    const folded = prefs().rest === "mark" && !top && !menuOpen() && !search;
    keeps(host, "data-search", search ? (pageSearch?.open ? "page" : "threads") : null);
    keeps(host, "data-rest", folded ? "mark" : "row");
    keeps(host, "data-open", top ? top.view : null);
    keeps(host, "data-menu", menuOpen() ? "" : null);
    keeps(mark, "class", `lf-dot${status().tone ? ` ${status().tone}` : ""}`);
    keeps(
      leaf,
      "aria-label",
      folded ? `Unfold Leaf · ${status().summary}` : `Page menu · ${status().summary}`,
    );
    keeps(leaf, "aria-expanded", folded ? null : String(menuOpen()));

    // What waits on the user, which the folded leaf carries as a badge and a dot.
    const onUser = onUserCount();
    const news = newCount();
    keepsText(badge, onUser ? String(onUser) : "");
    keeps(badge, "data-shown", onUser ? "" : null);
    keeps(newsDot, "data-shown", news ? "" : null);
    // An error the user has not seen marks the leaf while nothing says it: passed, about
    // a box not on screen, about nothing while the field holds words, or held while
    // folded. One a box on screen stands over says itself there (`standsAtItsBox`).
    const sayingNow = new Set(sayable().map((error) => error.id));
    const unseen = errorsReading().some(
      (error) => !error.seen && !sayingNow.has(error.id) && !standsAtItsBox(error),
    );
    keeps(errorDot, "data-shown", unseen ? "" : null);

    paintView(menu, menuTemplate, menuReading());
    afterRender(() => {
      // A copy control the menu keeps for its next showing leaves the list the render just
      // took down, which it would otherwise hold whole, rows and all, as its parent.
      for (const copy of [...copyItems.values(), ...copies.values()])
        if (!copy.isConnected) copy.remove();
      keeps(menu, "data-level", menuOpen() && menuAt() ? menuAt().view : null);
      keeps(menu, "style", menuOpen() && menuRoom ? `height: ${menuRoom}px` : null);
      // A text to select, which About holds where no clipboard copies it, is no menu's row.
      keeps(menu, "role", menu.querySelector("textarea") ? "dialog" : "menu");
      if (menuOpen()) {
        const rows = menuRows();
        rove(rows, rows.includes(focused()) ? focused() : rows[0]);
      }
    });
    const views = [leaving, top].filter(Boolean);
    // A row leaving the list the user stands on, as a page that goes idle leaves All
    // pages, hands them to the row after it, else before it, else the view that stays
    // open, rather than to the body (focus.js, `holdFocus`). Each list's rows carry
    // their key as `data-key`.
    const heldView = shownView();
    const restoreFocus = heldView && holdFocus(heldView, { key: "data-key" });
    // A thread's view stands for that thread (thread/selectors.js, `THREAD`), so the
    // user standing anywhere in it is in the thread, as in a card in Threads, and the
    // thread's keys find its reply and Resolve where the view declares them.
    const shows = (route) =>
      route.view === "thread" ? (threadByKey(route.thread)?.id ?? null) : null;
    paintView(
      stage,
      (read) => [
        For({
          get each() {
            return read().views;
          },
          keyed: (view) => view.key,
          children: (
            view,
          ) => nativeHtml`<div class="lf-fp-view" tabindex="0" data-focus="primary"
        data-view=${() => view().route.view} data-thread=${() => view().thread ?? undefined}
        data-lf-thread-view=${() => (view().thread !== null ? "" : undefined)}
        data-lf-rises=${() => (view().route.view === "thread" ? "" : undefined)} ref=${declareView}
        style=${() => ({ height: view().room !== null ? `${view().room}px` : undefined })}
        data-leaving=${() => (view().leaving ? "" : undefined)} onScroll=${sawAnswer}>${viewTemplate(() => view().body)}</div>`,
        }),
      ],
      {
        views: views.map((route) => ({
          key: routeKey(route),
          route,
          thread: shows(route),
          room: route === top ? room : null,
          leaving: route === leaving,
          body: viewReading(route),
        })),
      },
    );
    afterRender(() => {
      if (restoreFocus && heldView === shownView()) restoreFocus(heldView);
      drawnTop = top ? routeKey(top) : null;
      regionViews();
      // The open thread's messages are read where they land, and its view's height
      // whatever changes it (`fitAnswer`).
      const outlet = outletOf();
      if (outlet !== fitted) {
        fit.disconnect();
        if (outlet) for (const box of [outlet, openView()]) fit.observe(box);
        fitted = outlet;
      }
      const listed = listRows();
      rove(
        listed,
        listed.includes(focused())
          ? focused()
          : (listed.find((row) => row.getAttribute("tabindex") === "0") ?? listed[0]),
      );
      paintView(head, headTemplate, headReading(top));
      paintView(controls, controlsTemplate, controlsReading(top));
      // The more-room mark stands among the view's controls while one is open, else over
      // the leaf.
      move(row, expand, leaf);
      const heading = top ? shows(top) : null;
      for (const drawing of [controls, replyOutlet]) {
        keeps(drawing, "data-thread", heading);
        keeps(drawing, "data-lf-thread-view", heading === null ? null : "");
      }

      // The field: the destination's own editor stands in its place, the page's or, in a
      // thread, the outlet Leaf's reader draws the thread's reply box in (`nominate`). The
      // caret never passes from one editor to the next, since words typed after the
      // change would go somewhere the user did not choose. A thread opening while the
      // caret is in the field is the user's own send opening the thread it started, whose
      // reply takes the caret once it is drawn, as the thread's opening does
      // (`focusView`); an editor leaving with the caret otherwise leaves it on the leaf.
      const thread = top?.view === "thread" ? threadByKey(top.thread) : null;
      const replying = top?.view === "thread";
      if (threadSearchInput.value !== query) threadSearchInput.value = query;
      keepsHidden(threadSearchInput, search !== threadSearch);
      if (pageSearch) keepsHidden(pageSearch.input, !pageSearch.open);
      if (search) {
        const label = pageSearch?.open ? "Search page" : "Search threads";
        keeps(searchSurface, "aria-label", label);
        keeps(
          searchSurface,
          "class",
          `lf-fp-search-surface${pageSearch?.open ? " lf-page-search" : ""}`,
        );
      }
      paintView(fieldActions, (read) => () => read().controls, {
        controls: search?.controls ?? [],
      });
      keepsHidden(fieldActions, !search?.controls.length);
      // The editor stays connected while search stands in its place: a thread's reader
      // keeps that outlet, and the native editor keeps its caret and undo history.
      if (searchSurface.hidden !== !search) postureMoved = true;
      keepsHidden(editorSeat, Boolean(search));
      keepsHidden(searchSurface, !search);
      const shown = replying ? [replyOutlet, resolvedLine] : [pageEditor().box];
      if (editorSeat.firstElementChild !== shown[0]) {
        const had = standingIn(editorSeat);
        editorSeat.replaceChildren(...shown);
        if (had && !replying && !search) focusDestination(leaf, "return");
      }
      // A move to the page's field waits for the paint that stands it there, and lands
      // before the paint reads where the caret is, so the field is drawn once for it
      // (`writeOnPage`).
      if (caretToField && !replying && !search) {
        caretToField = false;
        focusDestination(pageEditor().input, "move");
      }
      // A resolved thread takes no reply: the field says how to reopen it instead.
      const resting = Boolean(thread) && !replyAvailable(thread);
      keepsHidden(resolvedLine, !resting);
      keepsHidden(replyOutlet, resting);
      const input = fieldInput();
      if (input) syncInput(input);
      keeps(host, "data-writing", writing ? "" : null);
      // While the field holds a draft, Send stands in its corner and the counts step
      // aside for it (`drafted`).
      const words = Boolean(draftOf(input));
      if (postureMoved || !words) drafted = words;
      postureMoved = false;
      keeps(host, "data-drafted", drafted ? "" : null);
      keeps(host, "data-words", words ? "" : null);
      if (!words) expanded = false;
      fieldRests = resting || Boolean(search);
      markRoom();
      keeps(host, "data-expanded", expanded ? "" : null);
      keeps(expand, "aria-pressed", String(expanded));
      keeps(
        expand,
        "aria-label",
        expanded ? "Less room to write" : "More room to write",
      );
      keeps(expand, "title", expanded ? "Less room to write" : "More room to write");
      paintView(
        expand,
        (read) => [
          Show({
            get when() {
              return read().icon;
            },
            keyed: true,
            children: (icon) => iconElement(icon, "lf-action-icon"),
          }),
        ],
        { icon: expanded ? "fit" : "expand" },
      );
      // Whose reading the empty field says, which its face follows (`saying`): a status
      // dims, and carries the sheen while the agent works, unless it asks the user to act,
      // such as to nudge the agent in its terminal, which it says in its tone's ink
      // (`pageStatus`, `asks`). The menu holds the full status and the Errors list.
      const reading = fieldReading(replying ? top.thread : null, input);
      // The field quoting selected words stands in an open comment box's place
      // (floating-panel.css, `data-offers`).
      keeps(host, "data-offers", !search && reading.says === "selection" ? "" : null);
      keeps(host, "data-tone", status().tone || null);
      keeps(host, "data-asks", status().asks ? "" : null);
      keepsText(
        resolvedLine,
        reading.says === "notice" ? reading.words : "Resolved · reopen to reply",
      );
      const selection = !search && reading.says === "selection" && words;
      const searchLabel = pageSearch?.open ? "Search page" : "Search threads";
      paintView(
        fieldMode,
        (read) =>
          Show({
            get when() {
              return read().search;
            },
            get fallback() {
              return nativeHtml`${() => (read().selection ? "Selection" : "")}`;
            },
            children: (_value) =>
              nativeHtml`<span class="lf-fp-mode-word">Search </span>${iconElement("search", "lf-fp-mode-icon")}<span>${() => (read().page ? "page" : "threads")}</span>`,
          }),
        { search: Boolean(search), selection, page: Boolean(pageSearch?.open) },
      );
      keeps(fieldMode, "aria-label", search ? searchLabel : null);
      keeps(
        fieldMode,
        "title",
        search ? searchLabel : selection ? reading.words : null,
      );
      keepsHidden(fieldMode, !search && !selection);
      paintPeek();

      const standing = search ? null : rowNotice();
      keepsHidden(rowNoticeSeat, !standing);
      paintView(
        rowNoticeSeat,
        (read) => [
          Show({
            get when() {
              return read().standing;
            },
            children: (notice) => rowNoticeView(notice),
          }),
        ],
        { standing },
      );

      // The way out of the stance the user stands in, beside the counts.
      const exit =
        search === threadSearch
          ? { label: "Close search", press: closeThreadSearch, disabled: false }
          : (rows().find((entry) => entry.exit) ??
            (top ? { label: "Close", press: close, disabled: false } : null));
      paintView(
        exitSeat,
        (read) => [
          Show({
            get when() {
              return read().exit;
            },
            children: (exit) => nativeHtml`
      <button type="button" class=${() => `lf-fp-chip lf-fp-exit${exit().press === close ? " lf-fp-close" : ""}`} aria-label=${() => exit().label} title=${() => exit().label}
        disabled=${() => exit().disabled} onMouseDown=${(event) => event.preventDefault()} onClick=${() => exit().press()}>
        ${iconElement("cross", "lf-action-icon")}
      </button>`,
          }),
        ],
        { exit },
      );
      keepsHidden(exitSeat, !exit);
      const landing = searchFocus;
      // A coalesced older paint must leave a newer field's focus request for
      // the paint that actually seats it. The native input is its stable identity.
      if (landing && search?.input === landing.input)
        afterRender(() => {
          if (searchFocus !== landing) return;
          searchFocus = null;
          if (activeSearch()?.input === landing.input && landing.current())
            focusDestination(landing.input, "move");
        });
      // Each mark keeps its room whether or not it has a number, so a count arriving or
      // leaving moves nothing beside it.
      // A mark's name is its tooltip too, as an icon control's title is elsewhere in Leaf.
      const threadsOpen = top?.view === "threads" || top?.view === "thread";
      const onUserName = onUser ? `On me: ${onUser}` : "On me";
      const threadsName = inventoried()
        ? `Threads, ${openCount()} open${news ? `, ${news} with news` : ""}`
        : "Threads";
      paintView(
        quick,
        (read) => nativeHtml`<button type="button" class="lf-fp-chip lf-fp-on-user"
      aria-pressed=${() => String(read().queue)} data-due=${() => (read().onUser > 0 ? "" : undefined)}
      aria-label=${() => read().onUserName} title=${() => read().onUserName} onClick=${openOnMe}>
      ${iconElement("inbox", "lf-action-icon")}<span class="lf-fp-num">${() => read().onUser || ""}</span>
    </button><button type="button" class="lf-fp-chip lf-fp-threads" aria-pressed=${() => String(read().threadsOpen)}
      aria-label=${() => read().threadsName} title=${() => read().threadsName} onClick=${() => {
        filter = read().news && !read().threadsOpen ? "unread" : "open";
        query = "";
        refit();
        open({ view: "threads" });
      }}>${iconElement("comment", "lf-action-icon")}<span class="lf-fp-num">${() => read().openCount || ""}</span>
      <span class="lf-fp-news" hidden=${() => !read().news}></span>
    </button>`,
        {
          queue: top?.view === "queue",
          threadsOpen,
          onUser,
          news,
          onUserName,
          threadsName,
          openCount: openCount(),
        },
      );
    });
  }

  // ---------- the row's notice ----------
  // One small notice beside the marks, for a state the user should not miss while they
  // read: a few words (`says`), a `tone` that tints it, and at most one `press`.
  // Leaf's own readings raise each, and a notice ends when the state
  // it reads does. The slot shows the first that holds, most urgent first, so the
  // field's room never goes to a stack of them. Each case is a reading below; a new
  // one joins `ROW_NOTICES` in its place.
  // The page shows an older version than the latest: the menu's row that opens the
  // latest says so too, but only once the menu is open, while the counts beside it
  // follow the version shown with no word of why.
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
  // The version shown is approved, until a new version asks again.
  function approvedVersion() {
    if (!approvalReading()?.approved) return null;
    return { says: `✓ ${versionsReading().picker.token} approved`, tone: "ok" };
  }
  const ROW_NOTICES = [olderVersion, approvedVersion];
  const rowNotice = () => {
    for (const read of ROW_NOTICES) {
      const notice = read();
      if (notice) return notice;
    }
    return null;
  };
  function rowNoticeView(read) {
    const face =
      () => nativeHtml`<span class="lf-fp-row-notice-face" data-tone=${() => read().tone}>
      ${() => read().says}${Show({
        get when() {
          return read().press;
        },
        children: (press) => nativeHtml`
        <span class="lf-fp-row-notice-sep" aria-hidden="true">·</span><span class="lf-fp-row-notice-act">${() => press().label}</span>`,
      })}</span>`;
    return [
      Show({
        get when() {
          return !!read().press;
        },
        get fallback() {
          return face();
        },
        children: (
          _visible,
        ) => nativeHtml`<button type="button" class="lf-fp-chip lf-fp-row-notice-press"
        title=${() => read().press?.title} disabled=${() => read().press?.disabled} onClick=${() => read().press?.run()}>${face()}</button>`,
      }),
    ];
  }

  // ---------- gestures ----------
  // The leaf unfolds a folded panel, and otherwise opens or closes its menu.
  leaf.addEventListener("click", () => {
    if (host.dataset.rest === "mark") {
      prefs().setRest("row");
      paint();
      return;
    }
    setMenu(!menuOpen());
    if (menuOpen() && keyed) {
      const first = menu.querySelector("button");
      if (first) focusDestination(first, "move");
    }
  });
  // Only the folded leaf needs a status peek; the row and menu already show status.
  // Folded, it also carries passing notices because there is no field to show them.
  const peekAsks = () => host.dataset.rest === "mark" && peekAsked;
  function paintPeek() {
    const folded = host.dataset.rest === "mark";
    const notice = passing();
    const telling = notice.visible && folded;
    const reading = status();
    const parts = reading.explanationParts ?? [
      { text: reading.explanation || reading.summary },
    ];
    const asked = peekAsks();
    // Keep words still through one exposure, even as the live status ages.
    if (!asked || !readingIsContinuous()) peekReading = null;
    if (asked && !telling && pagePresented()) peekReading ??= parts;
    paintView(peek, (read) => statusWords(() => read().parts), {
      parts: telling ? [{ text: notice.message }] : (peekReading ?? parts),
    });
    keeps(peek, "data-shown", telling || asked ? "" : null);
  }
  // Hovering the expanded row must not register a new exposure of status words.
  const showPeek = (on) => {
    const before = peekAsks();
    peekAsked = on;
    if (peekAsks() !== before) paintPeek();
  };
  leaf.addEventListener("pointerenter", () => showPeek(true));
  leaf.addEventListener("pointerleave", () => showPeek(false));
  leaf.addEventListener("focus", () => showPeek(leaf.matches(":focus-visible")));
  leaf.addEventListener("blur", () => showPeek(false));
  // What stands open, the menu first and then a view, is a step of the page's Escape,
  // taken wherever focus has fallen once the field has been left
  // (`panel.floating.leave`); with nothing open, the page's own foot of the ladder takes
  // the user from the panel back onto the page.
  pageRung("floating panel", () => {
    // Threads' search box clears its words first, then, empty, returns to Threads,
    // as a find box returns to its panel (keyboard/AGENTS.md, "Escape").
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
        : {
            root: host,
            title: "close search",
            out: closeThreadSearch,
          };
    if (menuOpen() && menuAt())
      return {
        root: host,
        title: "back to menu",
        out: () => showMenuAt(null),
      };
    if (menuOpen())
      return {
        root: host,
        title: "close menu",
        out: () => {
          setMenu(false);
          focusDestination(leaf, "return");
        },
      };
    if (!trail().length) return null;
    return {
      root: host,
      title: `close ${titleOf(trail().at(-1)).toLowerCase()}`,
      // Putting a view away returns the user to the page, where the view's thread or
      // list took them from.
      out: () => {
        close();
        letGo();
      },
    };
  });
  // The menu's rows are one list the arrows, Home and End walk, from the leaf too, and
  // one stop for Tab, which stands on the row last walked to. With nothing open the
  // panel declares no Escape of its own: the page's foot of the ladder takes the user
  // from the chrome back onto the page (keyboard/page.js), and a step declared over the
  // whole panel would claim Escape on its every control, where the Go-to sequence
  // refuses to arm.
  const menuRows = () => [...menu.querySelectorAll("button:not(:disabled)")];
  // A view's list, Threads, On, Versions or a group, is walked as the menu is, from the
  // view itself too, which a pointer opening it stands on: ↓ there enters its first row.
  // Only from a row or the view, so the arrows on an On card's own controls, or in a
  // thread's messages, keep their meaning there.
  const inList = () => {
    const at = focused();
    const rows = listRows();
    return rows.length > 0 && (at === shownView() || rows.includes(at));
  };
  // One walk over whichever list is open, the menu while it stands and the view's list
  // otherwise, so each key has one meaning and one row in the command reference.
  const walkedRows = () => (menuOpen() ? menuRows() : listRows());
  keys(
    host,
    "In the floating panel",
    /** @type {object[]} */ (
      rowWalk({
        id: "panel.floating.rows",
        noun: "Row",
        plural: "rows of the page menu or the open view",
        rows: walkedRows,
        // A menu names its rows' places to a screen reader itself; the walk shows no
        // position over either list.
        position: () => null,
        landed: (row) => rove(walkedRows(), row),
      }).map((row) => ({ ...row, when: () => menuOpen() || inList() }))
    ).concat(
      // → goes into the list a row opens, as its chevron points, and ← back to the menu.
      {
        id: "panel.floating.menu.level",
        keys: ["ArrowLeft", "ArrowRight"],
        title: "open or leave a list",
        when: () => menuOpen() && renderedUnder(focused(), menu),
        run: (binding) => {
          const [backward] = rowArrows(menu);
          if (binding === backward) {
            if (menuAt()) showMenuAt(null);
          } else if (focused()?.hasAttribute("data-opens")) focused().click();
        },
      },
      // Tab leaves the menu as it leaves a menu button's menu: the menu goes, and the
      // browser moves the user on from the leaf that opened it, either way.
      ["Tab", "Shift+Tab"].map((key) => ({
        id: `panel.floating.menu.leave-${key === "Tab" ? "forward" : "backward"}`,
        keys: [key],
        title: key === "Tab" ? "leave forward" : "leave backward",
        native: true,
        when: () => menuOpen() && renderedUnder(focused(), menu),
        run: () => {
          focusDestination(leaf, "move");
          setMenu(false);
        },
      })),
    ),
  );
  // A key the page has acts on the view standing open where the view has that act of
  // its own, as d and u already page the view the user is in (navigation.js): `/` in
  // Threads finds a thread rather than the page's words. Rooted at the view and its
  // controls together, so the filters find too; the search box's own `/` is a character.
  keys(
    opened,
    "In the floating panel",
    [
      {
        id: "panel.floating.threads.find",
        keys: ["/"],
        title: "find a thread",
        run: findThreads,
      },
    ],
    () => trail().at(-1)?.view === "threads",
  );
  // Versions is a list for choosing, as the menu is, so while it holds focus the
  // page's character keys rest rather than move the page under it, and a version's
  // number shows it. Two doors stay open: `?`, and Go-to, whose `g V` puts Versions
  // away as it opened it.
  const versionsShown = () => menuOpen() && menuAt()?.view === "versions";
  const numbered = () =>
    versionsReading()
      .rows.filter(({ version }) => version !== null && version <= 9)
      .toSorted((a, b) => a.version - b.version);
  keys(
    menu,
    "In the floating panel",
    [
      {
        id: "panel.floating.versions.pick",
        keys: () => numbered().map(({ version }) => String(version)),
        label: () => {
          const top = numbered().at(-1)?.version;
          return top > 1 ? `1–${top}` : "1";
        },
        title: "show version",
        when: () => numbered().length > 0,
        run: (binding) =>
          showVersion(numbered().find(({ version }) => String(version) === binding)),
      },
    ],
    {
      when: versionsShown,
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
      when: () => !menuOpen() && trail().length > 0,
      run: () => focusDestination(leaf, "return"),
    },
  ]);
  // Folding to the leaf is the page's command, so it has a key and a row in the menu.
  pageCommand({
    id: FOLD,
    keys: ["."],
    title: () => (prefs().rest === "mark" ? "unfold" : "fold"),
    touch: () => (prefs().rest === "mark" ? "Unfold the panel" : "Fold to the leaf"),
    menu: "page",
    run: () => setRest(prefs().rest === "mark" ? "row" : "mark"),
  });
  // Where the reader stood before stepping into the panel, which a row's command that
  // acts on that place gets back (history.js, `readPlace`).
  let heldStanding = null;
  host.addEventListener(
    "pointerdown",
    () => {
      if (!standingIn(host)) heldStanding = readPlace();
    },
    true,
  );
  // Writing begins in the field and lasts while the user stays in the panel, so the
  // line naming where the words go stays put while they press Resolve or a filter.
  onStanding((node, _cause, left) => {
    // The menu lasts while the user stands in it or on the leaf that opened it, so Tab
    // past its row, or a press in the field, puts it away.
    if (menuOpen() && node && node !== leaf && !renderedUnder(node, menu))
      setMenu(false);
    const inside = Boolean(node) && renderedUnder(node, host);
    // Stepping in from the page holds where the user stood. A row the panel just took
    // away, as a pressed menu row hands the user to the leaf, is no longer under the
    // panel but came from it, and holds nothing.
    if (inside && left?.isConnected && !renderedUnder(left, host))
      heldStanding = readPlace(left);
    const next = inside ? writing || node.localName === "leaf-text" : false;
    if (next === writing && !inside) return;
    writing = next;
    paint();
  });
  // A press on the page puts away what stands open above the row. A press in a modal
  // over the panel is not on the page (`overPanel`).
  document.addEventListener(
    "pointerdown",
    (event) => {
      if (event.composedPath().includes(host) || !nativeModalAdmits(host)) return;
      if (menuOpen()) setMenu(false);
      if (trail().length) close();
    },
    true,
  );

  // The doors to the panel's views and to Versions, as Go-to's named destinations
  // (keyboard/go-to-sequence.js) and version travel (`g V`, version.js) press them:
  // each opens what it names, or puts it away where it already stands, so the press
  // that opened it closes it. The On me door turns the On view to the user's list where
  // it shows the agent's, as the mark does; the Threads door opens on Open threads.
  // `shows` says whether the press would put its view away.
  function putVersionsAway() {
    const inside = renderedUnder(focused(), menu);
    setMenu(false);
    if (inside) focusDestination(leaf, "return");
  }
  const doors = Object.freeze({
    threads: {
      shows: () => trail().at(-1)?.view === "threads",
      press: () => {
        filter = "open";
        query = "";
        refit();
        open({ view: "threads" });
      },
    },
    queue: {
      shows: () => trail().at(-1)?.view === "queue" && queueTab === "you",
      press: openOnMe,
    },
    leaves: {
      shows: () => trail().at(-1)?.view === "leaves",
      press: () => open({ view: "leaves" }),
    },
    versions: {
      shows: () => menuOpen() && menuAt()?.view === "versions",
      press: () =>
        menuOpen() && menuAt()?.view === "versions"
          ? putVersionsAway()
          : showMenuAt({ view: "versions" }),
    },
  });

  // A live sample's host showing its child's threads in the panel (sample.js, the
  // `thread` command): the thread it names, else Threads, on Resolved where it asks for
  // `resolved`. A host's view never takes the child's focus, nor the field from the
  // child's user: a view that would stand another editor in the field (a thread's reply
  // for the page's comment, or back) is declined while the caret stands in the field or
  // its editor holds words, since the caret never passes between editors and the words
  // would leave the screen under no key or press of the user's.
  function showForSample({ thread, status }) {
    const wanted = thread ? threadByKey(thread) : null;
    if (thread && !wanted) return Promise.resolve(false);
    const top = trail().at(-1);
    const shown = top?.view === "thread" ? threadByKey(top.thread)?.key : null;
    if (
      (wanted?.key ?? null) !== (shown ?? null) &&
      (standingIn(field) || draftOf(fieldInput()).trim())
    )
      return Promise.resolve(false);
    if (wanted) {
      open({ view: "thread", thread: wanted.key }, { reopen: true, focus: false });
    } else {
      filter = status === "resolved" ? "resolved" : "open";
      query = "";
      refit();
      open({ view: "threads" }, { reopen: true, focus: false });
      paint();
    }
    return present({ release: true }).then(() => true);
  }

  // A live revision carries the thread open here, and where its view was read to,
  // across it (version.js, `captureRetainedStanding`): the reader is still at it, so
  // the view comes back as they left it, without taking focus, which the reply's own
  // editing continuity hands back. A revision installed in place keeps the view, which
  // still shows the thread, so its restore changes nothing. A view opened by the
  // user's next visit does not come back (restore-state.js); this is not that.
  function captureStanding() {
    const top = trail().at(-1);
    const view = openView();
    if (top?.view !== "thread" || !view) return null;
    return {
      thread: threadByKey(top.thread)?.key ?? top.thread,
      scroll: view.scrollTop,
    };
  }
  function restoreStanding(standing) {
    const thread = standing && threadByKey(standing.thread);
    if (!thread) return false;
    if (trail().at(-1)?.thread === thread.key && openView()) return true;
    open({ view: "thread", thread: thread.key }, { reopen: true, focus: false });
    landAtEnd = null;
    void present({ release: true }).then(() => {
      const view = openView();
      if (view && trail().at(-1)?.thread === thread.key)
        moveScrollerBy(view, standing.scroll - view.scrollTop);
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
    offer(passage) {
      const moved = passage?.quote !== selectedWords?.quote;
      selectedWords = passage;
      if (moved) paint();
    },
  });

  function mount(parent) {
    host.draw = paintPanel;
    parent.append(ground, host);
    follow.observe(card);
    presentation = registerChromeThreadPresentation(host, {
      render: nominate,
      // The view makes room for the agent's answer to the user's last turn itself
      // (`fitAnswer`), so the reader hands it over at once.
      answersAtOnce: true,
      // A reader the page's package registers later takes the thread open here, and
      // the user's place in it where they stood in the panel, read before the panel's
      // reader, and the message they stood on, goes.
      yielded: () => {
        const top = trail().at(-1);
        if (top?.view !== "thread") return null;
        const focus = standingIn(host);
        const message = focus
          ? (closestAcross(focused(), ".lf-msg")?.dataset.message ?? null)
          : null;
        return () => openInPackage(top.thread, { focus, message });
      },
      // A thread about the whole page opens here; one about a passage opens beside it,
      // where the page draws it, widgets in its messages included, and here only where
      // nothing on the page shows it, as on a page drawing no margin, the destination's
      // last resort (`request.last`, thread/destination.js), or for one of its messages
      // while the view already shows it, so a walk to an ask in it leaves the user
      // where they read. Where the user lands in it is the route's (`request.part`),
      // which Leaf's destinations take them to once it is drawn: the reply, a message,
      // or the thread itself, the view, where the `t` walk goes on from.
      reveal: (key, { part, last }) => {
        const thread = threadByKey(key);
        if (!thread) return false;
        const top = trail().at(-1);
        const shown =
          top?.view === "thread" && threadByKey(top.thread)?.key === thread.key;
        if (thread.anchor && !(part === "message" && shown)) {
          if (!last) {
            unplaced.delete(thread.key);
            // The page draws it, so a view of it here goes, as On the page puts it
            // away, and the thread shows once.
            if (shown) close();
            return false;
          }
          unplaced.add(thread.key);
        }
        open({ view: "thread", thread: thread.key }, { reopen: true, focus: false });
        return present({ release: true });
      },
    });
    // Upgrade turns the status to its loading words without a publication.
    document.addEventListener(UPGRADE, () => paint(), { once: true });
    registerApprovalPresentation({
      target: approvalControl,
      arrive: arriveAtApproval,
      repaint: () => paint(),
    });
    // A passing notice is said in the empty field, the one seat this chrome gives it.
    subscribe(noticeReading, ({ visible }) => (visible ? paint() : afterScript(paint)));
    subscribe(errorsReading, paint);
    subscribe(statusContextReading, paint);
    document.addEventListener("lf-chrome-preference", () => paint());
    onReadingInterrupted(() => {
      peekReading = null;
      paintPeek();
    });
    paint();
  }

  return {
    host,
    mount,
    open,
    close,
    pageComment,
    searchPage,
    doors,
    showForSample,
    captureStanding,
    restoreStanding,
    // The anchored comment box opening in its home (`responseSeat`) clears the row for
    // it, where the composer then takes the caret (composing/surface.js,
    // `finishPlacement`).
    responseHome: responseSeat,
    revealResponse: clearRow,
    // Where the reader stood before stepping into the panel, while they are in it
    // (navigation.js, `currentItem`).
    heldPlace: () => (standingIn(host) ? heldStanding : null),
    // The thread whose row in Threads the pointer is on, and the row Threads draws for
    // a thread, through which hover links a row and its passage both ways
    // (anchor-paint.js, `markRow`).
    hoveredThread: () => {
      const row = threadRows().find((candidate) => candidate.matches(":hover"));
      return row ? (threadByKey(row.dataset.key)?.id ?? null) : null;
    },
    threadRow: (id) => {
      const key = threadByKey(id)?.key;
      return threadRows().find((row) => row.dataset.key === key) ?? null;
    },
  };
}
