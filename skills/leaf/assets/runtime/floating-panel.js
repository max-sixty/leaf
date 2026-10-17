/* The floating panel: Leaf's chrome, as one box hovering over the foot of the page. It
 * presents what other owners hold, so it reads their readings and calls their commands:
 * the status and approval (page-status.js), the page's controls (`pageControls`,
 * page-controls.js), the threads (`readThreads`), the queues (`readQueues`), the
 * versions (`versionPicker`), the drafts (drafts.js) and the passing notices
 * (notifications.js). It decides only how they are shown.
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
 *   not miss, such as a failed save or reading an older version, tinted by its tone and
 *   with at most one press (`ROW_NOTICES`); the field gives it room, so the marks keep
 *   their seats. The empty
 *   field says what the agent is doing or wants, in the status's words
 *   (`statusReading`), or what a passing notice says, where a placeholder would say
 *   "Comment"; in a thread it says whose turn it is. A status that reports reads dimmer
 *   than anything written, and while the agent works it carries the one sheen that marks
 *   work under way; one that asks the user to act reads in its tone's ink, and pointing
 *   at the field says any status in full. Clicking in gives the placeholder to where
 *   the words go, a passing notice included, which then moves to one quiet line above
 *   the field, where it also stands over words that hide the placeholder. Once words
 *   hide it, that line says where they go as well, and keeps saying it while they
 *   stand. It never names who reads them: the page has one agent. The keys that send
 *   are Send's hover name, where Return sends with Shift+Return's new line beside it
 *   (composing/input.js). The line shows only with no view open, standing above the
 *   row, where nothing above it moves. Over an open view it would mostly repeat what is
 *   already on screen: where the words go, which the placeholder said before words hid
 *   it and a thread's head names, or news arriving, such as the reply the open thread
 *   already shows. A notice answering what the user did, such as a refused send's
 *   reason, the leaf's peek says there instead, as it does on a folded panel
 *   (`paintPeek`); news arriving goes unsaid but for the live region. The user chose
 *   this (2026-10-14), reversing the line lying over the view's foot in 12px of room
 *   every open view kept for it whether or not it showed (#2902). Rejected: that
 *   overlay, whose room stood under every view's last words for a line that repeated
 *   the head or the placeholder. A walk's position and Go-to's word go unsaid there
 *   too: they last while the user stands where they were said, which, for a walk that
 *   reached the block being read, is as long as the user writes, so the peek, made for
 *   a passing answer, lay on the view's last words that whole time. The empty field
 *   says them until the caret enters it.
 * - **Opened**: a view above the same row (On, Threads, a thread or All pages), what
 *   the user reads there, with where they are at its top edge. It lasts while it is
 *   used: Escape or a press on the page puts it away, Escape once the caret has
 *   left the field, since the caret is the innermost thing open. The view stands right
 *   on the row, with no line between them, so typing moves nothing at the view's head.
 *   The user chose that (2026-10-14), reversing a blank line's room kept under every
 *   open view, which read in Threads as a missing row. Rejected there: the line pushing
 *   the view up as it comes. The view's last words scroll clear of New reply
 *   (`fitAnswer`), the one thing that stands at its foot. It is as tall as what it
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
 * points to, under a head naming it that goes back, as → and ← do (`menuAt`): those
 * lists are for choosing, as the menu is, while what the user reads, Threads, On and
 * All pages, whose rows say what each page's agent is doing, opens as a view. The user
 * chose this on 15 October, reversing each list opening as a view rising from the
 * field with no way back to the menu. Rejected: that view keeping
 * its place with a "‹ Menu /" crumb at its head, which still moves the user's eye from
 * the menu to the panel's top. A
 * keyboard's convenience for where the reader stands, such as Resume writing, stands
 * under Navigate only where no keyboard is there to reach it (page-controls.js, the
 * `keys` group). The field the user clicks in is the field they write in: a page
 * comment where no thread is open, a reply where one is: the reply box every view of a
 * thread draws (thread/replies.js), with its ↑ to the user's last message, which Leaf's
 * reader draws in the field's place. Each destination keeps its own native editor (its
 * draft, caret and send), and the panel stands the current one in the field's place, so
 * words never move between editors.
 *
 * Nothing moves under the pointer: a filtered inventory keeps its height, the leaf's
 * menu holds what it showed while it stands, and a control the user pressed stays where
 * it was. Every change of the box's size takes effect in
 * one step, and the surface behind it, a separate layer, follows by a clip from where it
 * stood to where it stands, the way the Codex app's floating panel moves
 * (`notes/floating-panel/GOAL.md`): nothing's layout tweens, so nothing a user aims at
 * travels after the gesture that moved it. */
import {
  html,
  keyed as keyedBy,
  nothing,
  ref,
  render,
  repeat,
} from "/vendor/browser-runtime.js";
import { el, reveal } from "./widget-elements.js";
import { iconElement, iconTemplate } from "./icons.js";
import { copyControl } from "./copy-control.js";
import { keeps, keepsHidden, keepsText } from "./keeps.js";
import {
  approvalReading,
  approve,
  registerApprovalPresentation,
  statusReading,
} from "./page-status.js";
import { leavesRows } from "./live-leaves.js";
import { keys } from "./keyboard/scopes.js";
import { pageCommand, pageRung } from "./keyboard/register.js";
import { advertisesKeys, rowArrows } from "./keyboard/bindings.js";
import { keySequenceModel, keySequenceTemplate } from "./keyboard/key-sequence.js";
import { pageControls, watchPageControls } from "./page-controls.js";
import { readPlace } from "./history.js";
import { readThreads } from "./thread/state.js";
import { watchProjection } from "./projection-watch.js";
import { threadAttention, workflowLabel } from "./thread/workflow.js";
import { messageReading, threadName } from "./thread/messages.js";
import { drawnThreadId, THREAD } from "./thread/selectors.js";
import { declareThreadParts } from "./thread/focus.js";
import { quoteReading } from "./thread/thread-card.js";
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
import { draftOf, syncInput } from "./composing/input.js";
import { TEXT_FIELD } from "./control-selectors.js";
import { retainUserIntent } from "./user-intent.js";
import { settleThread } from "./thread/folding.js";
import { queueItemKey, readQueues } from "./queue-api.js";
import { queueTitle } from "./queue-title.js";
import { itemOutcome } from "./queues.js";
import { shortAgo } from "./presence.js";
import { askEnding } from "./asks/answer.js";
import { versionPicker } from "./version-picker.js";
import { versionsReading } from "./version.js";
import { UPGRADE } from "./presentation.js";
import { noticeReading, registerNoticePresentation } from "./notifications.js";
import { move } from "./dom-move.js";
import {
  registerStatusContextPresentation,
  statusContextReading,
} from "./keyboard/status-context.js";
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
import { nextRender, sizeObserver } from "./rendering.js";
import { scrollIntoView } from "./landing-scroll.js";
import { moveScrollerBy, SCROLL_SLACK, scrollLimit, scrollToEnd } from "./scrolling.js";
import { declareOccluder, declareWindowChrome } from "./geometry.js";
import { agentName } from "./semantic-state.js";
import { runtime } from "./context.js";
import { renderedUnder } from "./shadow.js";
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
// or pressing `s` already starts it.
const FOLD = "panel.floating.fold";
const HELD_ELSEWHERE = Object.freeze([
  "keyboard",
  `command:${FOLD}`,
  "command:target.picker.open",
]);
// A row the menu or a group lists: neither held elsewhere nor the next step of a
// gesture, which stands in the counts' place instead.
const listed = (entry) => !entry.gesture && !HELD_ELSEWHERE.includes(entry.key);
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
// position ("1 of 3 waiting on me · Ask"). The user asked on 16 October that whatever
// is not anchored to the page stand at the panel rather than against the window.
// `answers` marks a notice answering what the user did, the one kind the leaf's peek
// says over an open view (`paintPeek`).
function passing() {
  const notice = noticeReading();
  if (notice.visible)
    return { message: notice.message, visible: true, answers: !notice.news };
  const { goTo, walk } = statusContextReading();
  const message = goTo ?? (walk?.shown ? walk.text : "");
  return { message, visible: Boolean(message), answers: false };
}
// What the leaf's colour says, in a word, at the head of its menu.
const TONE_WORDS = Object.freeze({
  working: "Working",
  listening: "Waiting on me",
  away: "Away",
  offline: "Not connected",
});

export function createFloatingPanel({
  wireInput,
  threadActions,
  registerChromeThreadPresentation,
  observeFeedback,
  asks: askView,
  queueActions,
  withdraw,
  settlement,
  placedAt,
}) {
  const host = el("section", "lf-ui lf-floating-panel");
  host.setAttribute("aria-label", "Leaf");
  // The surface the box stands on: a layer of its own over the whole window, cut to the
  // box's outline, with a ring a pixel outside it, so its outline can move between two
  // places without either box's layout moving.
  const ground = el("div", "lf-ui lf-fp-ground");
  ground.setAttribute("aria-hidden", "true");
  const ring = el("div", "lf-fp-ring");
  const fill = el("div", "lf-fp-fill");
  ground.append(ring, fill);
  const card = el("div", "lf-fp-card");
  const inner = el("div", "lf-fp-inner");
  // What stands above the row while a view is open: where the user is, and the view.
  const opened = el("div", "lf-fp-opened");
  const head = el("div", "lf-fp-head");
  const stage = el("div", "lf-fp-stage");
  opened.append(head, stage);
  const context = el("div", "lf-fp-context");
  const contextWords = el("span", "lf-fp-context-words");
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
  let peekAsked = false; // the pointer or focus asking the folded leaf's peek to show
  let peekReading = null;
  // A notice answering the user that the line over the field would say, were a view not
  // open (`paintPeek`).
  let overView = false;
  context.append(contextWords);
  inner.append(opened, context, row);
  card.append(inner);
  // The menu and the peek stand over the leaf by anchoring to it, which they can only
  // do from after it in the tree.
  host.append(card, menu, badge, newsDot, peek);
  // The pointer's way to fold, which the user asked for as a minimize shown on hover: a
  // round button on the box's top-right corner, chosen over one at the row's end on 15
  // October. It presses the fold command's own row, as the menu's row does; that row and
  // `.` are the keyboard's and a finger's ways, so it takes no Tab stop of its own.
  const minimize = el("button", "lf-fp-minimize");
  minimize.type = "button";
  minimize.tabIndex = -1;
  minimize.title = "Fold to the leaf";
  minimize.setAttribute("aria-label", "Fold to the leaf");
  minimize.append(iconElement("subtract", "lf-fp-minimize-icon"));
  minimize.addEventListener("click", () =>
    rows()
      .find((entry) => entry.key === `command:${FOLD}`)
      .press(null),
  );
  host.append(minimize);
  // It shows only while the pointer is near the corner it rides, so the panel at rest,
  // and under a pointer passing over the field or the marks, carries no control the user
  // did not reach for (15 October). Near is the box's top-right corner, a mark's width in
  // and half a row down, or the button itself.
  const CORNER = { across: 64, down: 24 };
  host.addEventListener("pointermove", (event) => {
    const box = card.getBoundingClientRect();
    const near =
      event.target === minimize ||
      minimize.contains(event.target) ||
      (event.clientX >= box.right - CORNER.across &&
        event.clientY <= box.top + CORNER.down);
    keeps(host, "data-corner", near ? "" : null);
  });
  host.addEventListener("pointerleave", () => keeps(host, "data-corner", null));
  // The row stands over the window's foot, so what the page reveals stands clear of it.
  // A view opened above it is itself read, and stands over the page only while it is
  // used, so it leaves the page's room alone; but what it stands over is hidden while it
  // does (`declareOccluder`).
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
  leaf.append(mark);
  const field = el("div", "lf-fp-field");
  // A long draft offers more room, by the user's press rather than on its own: past
  // three lines a quiet mark stands at the end of a line already over the field, the
  // line saying where the words go, or an open view's head, so it takes no room of
  // its own (assets/AGENTS.md, "A control takes only its own room"). Pressing it widens the
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
    // The mark's strip resizes the field this watches, so it paints in the next frame
    // rather than inside the observer's delivery.
    nextRender(paint);
  });
  lengthWatch.observe(field);
  const rowNoticeSeat = el("div", "lf-fp-row-notice");
  const quick = el("div", "lf-fp-quick");
  // The anchored comment box's home on a page that draws its own annotations
  // (`data-annotations="page"`), where the page gives the box no seat of its own
  // (composing/surface.js, `responseHome`). While its composer is open it stands in the
  // field's place, as each destination's own editor does there: its words go to a new
  // thread on the passage it quotes, which the box says. The field comes back when the
  // box closes, and while a view is open above the row, whose field it is. Which of the
  // two shows is the stylesheet's reading of the composer's own open state
  // (floating-panel.css), so the box seated in the page, or put away, moves nothing
  // here. Rejected: a view of its own above the row, which stood a second field over
  // the panel's own.
  const responseSeat = el("div", "lf-fp-response");
  row.append(leaf, field, responseSeat, rowNoticeSeat, quick);

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
  const statusParts = (parts) =>
    parts.map((part) => {
      if (!part.source) return part.text;
      let stop = null;
      return html`<span
        class="lf-fp-status-feedback"
        ${ref((node) => {
          stop?.();
          stop = node
            ? observeFeedback(node, {
                input_id: part.source.item,
                reply_id: part.source.event_id,
                reply_kind: "work",
                presentation_kind: "status_words",
                surface: "panel",
              })
            : null;
        })}
        >${part.text}</span
      >`;
    });
  // The trail of views open above the row, innermost last; empty at rest.
  let trail = [];
  let leaving = null;
  let menuOpen = false;
  // The list standing in the menu's place, a group or Versions, or null for the menu,
  // and the height it first stood at, which it keeps while it stands, as a view keeps
  // its room (`holdRoom`), so news changing the list moves none of the menu's rows.
  let menuAt = null;
  let menuRoom = null;
  let filter = "open";
  let query = "";
  let searching = false;
  let writing = false;
  // Whether the user is typing, as the row last showed it: Send in the field's corner,
  // the counts stepped aside.
  let typing = false;
  // The thread the reader lands at the end of, once Leaf has drawn more than `after`
  // of its messages: the whole of it on opening, or past the turn the user just sent.
  let landAtEnd = null;

  // ---------- one native editor per destination ----------
  // What the empty field says, and whose reading it is (`says`): once the caret is in
  // a field that takes words, where they go; a passing notice while one stands; a
  // resolved thread's way back; else on the page what the agent is doing or wants, in
  // the status's words, and in a thread whose turn it is.
  function fieldReading(key, input) {
    const thread = key ? threadByKey(key) : null;
    if (input === focused() && !thread?.resolved)
      return { says: "destination", words: whereTo(key) };
    const notice = passing();
    if (notice.visible) return { says: "notice", words: notice.message };
    if (thread?.resolved) return { says: "turn", words: "Resolved · reopen to reply" };
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
          ? statusParts(parts)
          : null;
      },
      accessibleName: "Comment on the page",
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
        // and hands the words back to the page's draft (drafts.js, `standGesture`). Its
        // view goes with it, where it still stands, so the field stands for the page
        // again holding them, with the caret in them where the user still stands in the
        // panel or has done nothing since the send.
        const untouched = retainUserIntent();
        void Promise.resolve(flight).then((sent) => {
          if (sent || trail.at(-1) !== route) return;
          caretToField = standingIn(host) || untouched();
          trail = [];
          transition(route, { focus: false });
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
  // and the field says how to reopen it instead.
  const replyOutlet = el("div", "lf-fp-reply");
  const resolvedLine = el("p", "lf-fp-resolved");
  resolvedLine.textContent = "Resolved · reopen to reply";
  const replyInput = () => replyOutlet.querySelector(`.lf-thread-reply ${TEXT_FIELD}`);
  const replyOptions = new Map();
  const replyOptionsFor = (key) => {
    if (!replyOptions.has(key))
      replyOptions.set(key, {
        hint: () => saying(key, replyInput()),
        accessibleName: () => `Reply to ${threadTitle(key)}`,
        sent: () => {
          landAtEnd = { key, after: outletOf()?.childElementCount ?? 0 };
          // The user's turn grows the view to show it and takes New reply away.
          waiting = null;
          queueMicrotask(paint);
        },
      });
    return replyOptions.get(key);
  };
  // The editor standing in the field now, the page's or the open thread's reply.
  const fieldInput = () =>
    field.firstElementChild === replyOutlet ? replyInput() : pageEditor().input;
  // Words arriving in an empty field, or the last of them going, re-seat the row.
  function retype() {
    if (Boolean(draftOf(fieldInput()).trim()) !== typing) paint();
  }
  field.addEventListener("input", retype);

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
  const unread = (thread) => thread.unread.length > 0;
  const newCount = () => (inventoried() ? threads().filter(unread).length : 0);
  const openCount = () =>
    inventoried() ? threads().filter((thread) => !thread.resolved).length : null;
  const onUserCount = () => {
    const queues = readQueues();
    return queues.phase === "ready" ? queues.on_user.length : 0;
  };
  // A thread row's state in words, less the one the filter the list is shown by already
  // says: under Open no row says "Open", under Unread none "New".
  const threadStatus = (thread, shownBy) => {
    const state = thread.resolved
      ? "Resolved"
      : (threadAttention(thread)?.label ?? "Open");
    const said = {
      unread: "New",
      open: "Open",
      resolved: "Resolved",
      drafts: "Draft",
    }[shownBy];
    return [
      unread(thread) && "New",
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
      thread: route.thread ? threadTitle(route.thread) : "",
      group: GROUPS[route.group],
    })[route.view];
  // The menu's list as its row's `data-row` names it, which going back stands on.
  const levelRow = (level) => (level.view === "group" ? routeKey(level) : level.view);
  const pathTo = (route) =>
    route.view === "thread" ? [{ view: "threads" }, route] : [route];
  function open(route, { replace = false, reopen = false, focus = true } = {}) {
    const before = trail.at(-1);
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
    trail =
      replace && before
        ? [...trail.slice(0, -1), route]
        : route.view === "thread" && LISTS.includes(before?.view)
          ? [before, route]
          : pathTo(route);
    if (replace && route.view === "thread" && trail.length === 1) trail = pathTo(route);
    if (route.view === "thread") arriveAt(route.thread);
    transition(before, { focus });
  }
  // Where the page's package draws its conversations, a thread opens in its reader,
  // and the view it was chosen from goes, uncovering the page.
  function openInPackage(key, { focus = true, message = null } = {}) {
    if (trail.length) close();
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
    const before = trail.at(-1);
    if (prefs().rest === "mark") prefs().setRest("row");
    trail = [];
    setMenu(false);
    transition(before, { focus: false });
  }
  function writeOnPage() {
    caretToField = true;
    clearRow();
  }
  // Resolving a thread opened from Threads moves the user on: to the open thread after it, or
  // before it at the end, standing on its view so `r`, `t` and Escape go on from there;
  // or, with none left, back to the list. A thread opened from elsewhere goes back to
  // where it came from. Taking the resolve back, or the log refusing it, stands the
  // user on its row in Threads, while they have not acted since (folding.js,
  // `settleThread`).
  function resolveLanding(thread) {
    const route = trail.at(-1);
    const fromThreads = trail.at(-2)?.view === "threads";
    const at = threads()
      .filter((candidate) => !candidate.resolved)
      .indexOf(thread);
    const mayLand = retainUserIntent();
    let mayRestore = () => false;
    return {
      optimistic: () => {
        if (!mayLand() || trail.at(-1) !== route) return false;
        const kept = threads().filter((candidate) => !candidate.resolved);
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
        if (!may() || trail.at(-1)?.view !== "threads") return;
        const row = shownView()?.querySelector(
          `.lf-fp-thread[data-key="${CSS.escape(thread.key)}"]`,
        );
        if (row) focusDestination(row, "move");
      },
    };
  }
  function back() {
    const before = trail.at(-1);
    trail = trail.slice(0, -1);
    transition(before);
  }
  function close() {
    const before = trail.at(-1);
    trail = [];
    searching = false;
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
    if (menuOpen === on) return;
    menuOpen = on;
    menuAt = null;
    menuRoom = null;
    held = null;
    paint();
  }
  // A list the menu leads to takes the menu's place, and going back puts the menu back,
  // either sliding in from the side it lies on. The menu stays open across the change, so
  // a user standing on the row it removes stands on the leaf, its door, meanwhile; one who
  // came by key, or from outside the panel, as `g V` does, stands on the first row the
  // list offers, and going back, on the row that opened it.
  function showMenuAt(level) {
    const before = menuOpen ? menuAt : undefined;
    if (before && level && routeKey(before) === routeKey(level)) return;
    const outside = !standingIn(host);
    if (renderedUnder(focused(), menu)) focusDestination(leaf, "return");
    menuOpen = true;
    menuAt = level;
    menuRoom = null;
    held = null;
    paint();
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
    if (!keyed && !outside) return;
    const target = level
      ? page?.querySelector(".lf-fp-item:not(.lf-fp-menu-back, :disabled)")
      : before && menu.querySelector(`[data-row="${levelRow(before)}"]`);
    if (target) focusDestination(target, "move");
  }

  // ---------- motion: the surface follows the box ----------
  // The box's layout changes in one step, whatever changed it: a view opening, the line
  // naming where the words go, a field growing a line, folding to the leaf. The surface
  // then follows from the outline it stood at to the box's new one by a clip, which
  // moves nothing's layout; while the box grows, its own contents are clipped to the
  // same outline, so they appear as the surface reaches them. The first outline, and
  // any under reduced motion, is taken as it is.
  let outline = null;
  // Until when a change of outline is a view arriving or leaving (`transition`), which
  // takes the shorter tween: the view's own change, and the one when the view it
  // replaced is gone after its fade.
  let viewMovingUntil = 0;
  const SHADOW_REACH = 32;
  const outlineClip = (box, grow = 0) =>
    `inset(${box.top - grow}px ${box.right - grow}px ${box.bottom - grow}px ${
      box.left - grow
    }px round ${box.radius + grow}px)`;
  function followBox() {
    const room = ground.getBoundingClientRect();
    const rect = card.getBoundingClientRect();
    const radius = Number.parseFloat(getComputedStyle(card).borderTopLeftRadius) || 0;
    const next = {
      top: rect.top - room.top,
      right: room.right - rect.right,
      bottom: room.bottom - rect.bottom,
      left: rect.left - room.left,
      width: rect.width,
      height: rect.height,
      radius,
    };
    const was = outline;
    if (
      was &&
      ["top", "right", "bottom", "left", "radius"].every(
        (side) => Math.abs(was[side] - next[side]) < 0.5,
      )
    )
      return;
    outline = next;
    const duration = performance.now() < viewMovingUntil ? VIEW_RESIZE_MS : RESIZE_MS;
    // The ground is cut too, to the outline grown by its shadow's reach (`--raise-2`, a
    // 24px blur dropped 8px), so it stands over nothing else in the window: a layer over
    // the whole window that paints nothing left every word under it unmeasured by a
    // contrast checker. Its cut moves with the ring's, so it holds the ring every frame.
    for (const [layer, grow] of [
      [ground, SHADOW_REACH],
      [ring, 1],
      [fill, 0],
    ]) {
      const from = was ? getComputedStyle(layer).clipPath : null;
      for (const running of layer.getAnimations()) running.cancel();
      keeps(layer, "style", `clip-path: ${outlineClip(next, grow)}`);
      if (!was || reducedMotion() || !pagePresented()) continue;
      layer.animate([{ clipPath: from }, { clipPath: outlineClip(next, grow) }], {
        duration,
        easing: EASE,
      });
    }
    for (const running of card.getAnimations()) running.cancel();
    if (!was || reducedMotion() || !pagePresented()) return;
    if (next.width <= was.width + 0.5 && next.height <= was.height + 0.5) return;
    // Within its own box, the outline the surface still stands at.
    const within = {
      top: Math.max(0, was.top - next.top),
      right: Math.max(0, was.right - next.right),
      bottom: Math.max(0, was.bottom - next.bottom),
      left: Math.max(0, was.left - next.left),
      radius: was.radius,
    };
    card.animate(
      [{ clipPath: outlineClip(within) }, { clipPath: `inset(0 round ${radius}px)` }],
      { duration, easing: EASE },
    );
  }
  const fit = sizeObserver(() => fitAnswer());
  const follow = sizeObserver(() => followBox());
  addEventListener("resize", () => {
    outline = null;
    followBox();
  });

  // A view is as tall as what it first holds, up to its cap (floating-panel.css,
  // `--lf-fp-view-height`). A list's room is then fixed for as long as it stays open, so
  // news arriving in it, or a filter or tab changing what it shows, moves no control at
  // its head; what does not fit scrolls inside it. A thread's view instead follows its
  // messages, since its reader already holds back any news that would move what is read
  // (thread/held-news.js) until the user asks for it, and what the user asks for, a
  // reply they send or news they open, grows the view to show it. What the view first
  // holds is what it shows, not what a filter hides, and a message Leaf's reader has
  // yet to draw into it is not yet held.
  //
  // The agent's answer to the user's own last turn is the one news the reader hands the
  // view at once (`answersAtOnce`): the user is waiting for it. The view grows to hold
  // it, work under way and a reply streaming included, up to its cap: the field stays
  // put and the head rises, carrying the user's own turn up with it. Where the user
  // stood at the view's end and their turn and the answer together fit in the view, the
  // end follows the answer into sight, as a card's transcript follows a turn joining its
  // end. Otherwise the answer goes on below the fold, and New reply stands at the view's
  // foot until a press on it, or the user scrolling there, shows it; the user's turn
  // stays wholly in sight above the press, its head included (`fitAnswer`). The user
  // chose this growth (2026-10-14), the one case where news may carry a view's head
  // without a gesture (`skills/leaf/assets/AGENTS.md`, "Stability"), reversing the view
  // holding its height while the user waited (#2892), which left a short thread's
  // answer behind New reply in a view one message tall. Rejected then and now: holding
  // the answer behind the reader's "1 new reply", which left the reply the user waited
  // for unseen. Other news in an open thread is still held. A thread's view declares
  // that it stands on its foot (`data-lf-rises`), which the shift watch credits for
  // exactly this growth (tests/shift_watch.js, `appendGrowth`).
  const rooms = new Map();
  // Whether this opening of a thread has shown On the page, whose seat then stands
  // while the view does, so a revision detaching the thread moves nothing beside it.
  let onPageSeat = false;
  // The threads about a passage the page last drew nowhere, which Leaf's destinations
  // then handed the panel as their last resort (`reveal`): On the page has nowhere to
  // take the user from those.
  const unplaced = new Set();
  function holdRoom() {
    const top = trail.at(-1);
    if (!top || top.view === "thread" || rooms.has(routeKey(top))) return false;
    const view = stage.querySelector(".lf-fp-view:not([data-leaving])");
    if (!view || view.querySelector(".lf-fp-asked:empty")) return false;
    rooms.set(routeKey(top), view.offsetHeight);
    return true;
  }
  // The open thread's messages as last drawn in its view, and how far its content then
  // reached; and the answer waiting below the fold behind New reply, by its first
  // message.
  let drawnThread = null;
  let waiting = null;
  let fitted = null;
  // Where the panel itself last scrolled the open thread's view, which is not the user
  // going anywhere (`sawAnswer`).
  let placed = null;
  // Read where the reader's drawing lands, after layout and before the frame is shown.
  function fitAnswer() {
    const top = trail.at(-1);
    const view = openView();
    const outlet = outletOf();
    if (top?.view !== "thread" || !view || !outlet) {
      drawnThread = null;
      return;
    }
    const keys = [...outlet.querySelectorAll(".lf-msg[data-message]")].map(
      (node) => node.dataset.message,
    );
    const before = drawnThread?.key === top.thread ? drawnThread : null;
    const msgs = threadByKey(top.thread)?.msgs ?? [];
    const message = (key) => msgs.find((each) => each.key === key);
    // Which messages were still coming as drawn, work under way or a reply streaming,
    // judged then: an answer completing its stream is no longer one.
    drawnThread = {
      key: top.thread,
      keys,
      coming: keys.filter(
        (key) => message(key)?.ephemeral || message(key)?.provisional,
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
      !answer.keys.every((key) => message(key)?.author === "agent")
    )
      return;
    // An answer folding the work before it into less room moves nothing either.
    if (view.scrollHeight <= before.extent + 0.5) return;
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
    const reply = answer.keys.find((key) => !message(key).ephemeral);
    const next = reply
      ? { key: top.thread, message: reply, label: "New reply" }
      : { key: top.thread, message: answer.keys[0], label: "New update" };
    if (waiting?.message === next.message) return;
    const arriving = !waiting;
    waiting = next;
    paint();
    if (!arriving || !atEnd) return;
    // The user's turn stands wholly in sight, between the view's head and New reply's
    // ground, its head first where it is taller than that.
    const foot = view.querySelector(".lf-fp-foot")?.getBoundingClientRect();
    const below = foot ? turn.getBoundingClientRect().bottom - foot.top : 0;
    const by = Math.min(Math.max(below, 0), from());
    if (Math.abs(by) < 0.5) return;
    moveScrollerBy(view, by);
    placed = view.scrollTop;
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
    const node = outletOf()?.querySelector(
      `.lf-msg[data-message="${CSS.escape(answer.message)}"]`,
    );
    if (node) scrollIntoView(node, { block: "start" });
  }
  // Scrolling the answer's start into sight above New reply takes New reply away, the
  // view keeping its height.
  function sawAnswer(event) {
    const view = event.currentTarget;
    if (!waiting || view.scrollTop === placed) return;
    const node = view.querySelector(
      `.lf-msg[data-message="${CSS.escape(waiting.message)}"]`,
    );
    const press = view.querySelector(".lf-fp-new-reply");
    if (!node || !press) return;
    if (node.getBoundingClientRect().top >= press.getBoundingClientRect().top) return;
    waiting = null;
    paint();
  }
  // The leaf's menu stands on the leaf and grows upward, so anything news adds to it, or
  // takes from it, carries everything above up or down the window: a row a revision
  // offers, such as the newer version, or a status re-wrapping the head. So while the
  // menu stands it holds what it showed with the first status it said (Connecting… is
  // not yet one). Its rows keep their seats: a row news takes off offer stands
  // disabled, and one news offers joins at the next opening. Each part of its head under
  // the word keeps its lines: a later status re-wraps inside them, ending in an ellipsis
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
    if (!menuOpen || held !== null || !statusReading()) return false;
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
    const after = trail.at(-1);
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
      rooms.clear();
      quoteExpanded = false;
      waiting = null;
      placed = null;
      drawnThread = null;
      onPageSeat = false;
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
    // The reader draws what the view arriving holds, and lets go of what the one
    // leaving held: a thread's messages, or the asks On shows as messages.
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
    const settle = () => {
      leaving = null;
      paint();
    };
    if (fade) fade.finished.then(settle, () => {});
    else leaving = null;
    if (focus) focusView(after, drawn, stoodIn);
  }
  function focusView(route, drawn, stoodIn = null) {
    if (!route) return;
    const view = shownView();
    // A thread opens with the caret in its reply, as the one field means, once Leaf's
    // reader has drawn the reply there. A list stands on the row of the thread the user
    // stood in, where it lists it, as `g T` from a thread does; else, opened by a key in
    // the panel, on its first row, or its first control where it has none, or itself
    // where it holds neither, as an empty Threads does; opened from anywhere else, as
    // `g T` from the page or a pointer, it holds focus itself.
    if (route.view === "thread") {
      // A finger opening a thread reads it first; the keyboard rises when they tap in.
      if (coarse()) return;
      const intent = retainUserIntent();
      void Promise.resolve(drawn).then(() => {
        const input = replyInput();
        if (input && trail.at(-1) === route && intent())
          focusDestination(input, "move");
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

  // Whether the gesture now under way is a key in the panel: a key arriving in a view
  // stands on its first control, a pointer in the view itself, with no ring drawn. A
  // gesture outside the panel, `g T` from the page among them, is neither, whatever the
  // panel last heard, so the view it opens holds focus itself.
  let keyed = false;
  onUserInput((event) => {
    if (["keydown", "pointerdown"].includes(event.type))
      keyed = event.type === "keydown" && event.composedPath().includes(host);
  });

  // ---------- the leaf's menu ----------
  // A row that opens a list of its own ends in a chevron, past its value, so the user
  // knows before pressing that it leads further rather than acting.
  const menuItem = (
    label,
    end,
    press,
    {
      urgent = false,
      disabled = false,
      role = "menuitem",
      row = null,
      opens = false,
      title = null,
    } = {},
  ) =>
    html`<button
      type="button"
      role=${role ?? nothing}
      data-row=${row ?? nothing}
      title=${title ?? nothing}
      class="lf-fp-item"
      ?disabled=${disabled}
      ?data-lf-urgent=${urgent}
      ?data-opens=${opens}
      @click=${press}
    >
      <span class="lf-fp-label">${label}</span
      ><span class="lf-fp-end"
        >${end}${opens ? iconTemplate("next", "lf-fp-chevron") : nothing}</span
      >
    </button>`;
  // A row's end says its value in words, then its shortcut where a keyboard is there to
  // press it, each press a key as the command reference draws it, so the two never read
  // as one run of text.
  const rowEnd = (entry) =>
    html`${
      entry.value ? html`<span class="lf-fp-value">${entry.value}</span>` : nothing
    }${
      entry.shortcut.length && advertisesKeys()
        ? keySequenceTemplate(keySequenceModel(entry.shortcut))
        : nothing
    }`;
  // A row of the menu whose press copies a text, such as the page's link, is Leaf's copy
  // control worn by the row (copy-control.js): one press copies, the menu goes, and the
  // field says whether the copy took, as it says any passing notice. What the text is,
  // which a field to select it would say beneath it, is the row's hover name. Where no
  // clipboard is offered, the row stands in About instead, its text there to select
  // (`groupOf`); where the clipboard refuses the copy, the row moves there for good and
  // About opens on the text, so the user can still take it.
  const copyItems = new Map();
  function copyItem(entry) {
    let copy = copyItems.get(entry.key);
    if (!copy) {
      copy = copyControl("lf-fp-copy-item", {
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
    copy.value = entry.copies;
    copy.disabled = entry.disabled;
    render(
      menuItem(
        `Copy ${entry.label}`,
        html`<wa-icon library="system" name="copy" variant="regular"></wa-icon>`,
        () => {},
        {
          disabled: entry.disabled,
          role: menuOpen ? "menuitem" : null,
          row: entry.key,
          title: entry.value || null,
        },
      ),
      copy,
    );
    return copy;
  }
  function rowFor(entry) {
    if (entry.copies) return copyItem(entry);
    const view = OWN_VIEWS.includes(entry.key) ? entry.key : null;
    return menuItem(
      entry.label,
      rowEnd(entry),
      () => {
        if (view === "versions") showMenuAt({ view });
        else if (view) open({ view });
        else putAwayThen(() => entry.press(heldStanding));
      },
      {
        urgent: Boolean(entry.urgent),
        disabled: entry.disabled,
        role: menuOpen ? "menuitem" : null,
        row: entry.key,
        opens: view === "versions",
      },
    );
  }
  // The menu, or the list standing in its place under a head that goes back to it.
  function menuTemplate() {
    if (!menuAt)
      return html`<div class="lf-fp-menu-page" role="none">${rootTemplate()}</div>`;
    return html`<div class="lf-fp-menu-page" role="none">
      <button
        type="button"
        role="menuitem"
        class="lf-fp-item lf-fp-menu-back"
        aria-label=${`Back to the page menu from ${titleOf(menuAt)}`}
        @click=${() => showMenuAt(null)}
      >
        <span class="lf-fp-label"
          >${iconTemplate("next", "lf-fp-chevron")}<b>${titleOf(menuAt)}</b></span
        >
      </button>
      ${menuAt.view === "versions" ? versionsList() : groupList(menuAt.group)}
    </div>`;
  }
  function rootTemplate() {
    const all = rows();
    // The panel's own views lead, in the order the user reaches for them; the rest of
    // the page's rows follow in their rank's order.
    const lead = OWN_VIEWS;
    const page = all
      .filter((entry) => groupOf(entry) === "page" && listed(entry))
      .sort(
        (a, b) =>
          (lead.includes(a.key) ? lead.indexOf(a.key) : lead.length) -
          (lead.includes(b.key) ? lead.indexOf(b.key) : lead.length),
      );
    const keyboard = all.find((entry) => entry.key === "keyboard");
    const fold = all.find((entry) => entry.key === `command:${FOLD}`);
    const groups = Object.keys(GROUPS).filter((group) =>
      all.some((entry) => groupOf(entry) === group && listed(entry)),
    );
    // The state is said once: in a word, over its one line, and under that only what
    // the status adds to the line (`statusModel`, `adds`), since the menu is reached by
    // pointer, key and finger alike.
    const { tone, summary, summaryParts, adds, addsParts, publication } = status();
    // A published page's introduction keeps its links.
    const explains = publication
      ? html`${publication.copy}${
            publication.examplesUrl
              ? html`<a href=${publication.examplesUrl}>${publication.examples}</a> `
              : nothing
          }<a href=${publication.installUrl} target="_blank" rel="noopener"
            >${publication.install}</a
          >`
      : adds && addsParts
        ? statusParts(addsParts)
        : adds;
    const word = TONE_WORDS[tone];
    const part = (name, text) =>
      (held ? held[name] : text)
        ? html`<span
            class="lf-fp-${name}"
            style=${held ? `--lines: ${held[name]}` : nothing}
            >${text}</span
          >`
        : nothing;
    const seat = (entry) => ({
      key: entry.key,
      draw: (gone) => rowFor(gone ? { ...entry, disabled: true } : entry),
    });
    const offered = [
      ...page.map(seat),
      ...groups.map((group) => ({
        key: `group:${group}`,
        draw: (gone) =>
          menuItem(
            GROUPS[group],
            groupValue(group)
              ? html`<span class="lf-fp-value">${groupValue(group)}</span>`
              : nothing,
            () => showMenuAt({ view: "group", group }),
            { opens: true, disabled: gone, row: `group:${group}` },
          ),
      })),
      { key: "", draw: () => html`<hr />` },
      ...[keyboard, fold].filter(Boolean).map(seat),
    ];
    const now = new Map(offered.map((row) => [row.key, row]));
    seats = held?.seats ?? offered;
    return html`<div
        class="lf-fp-state"
        role="none"
        data-tone=${tone || nothing}
        ?data-held=${held !== null}
      >
        <b>${word ?? (summaryParts ? statusParts(summaryParts) : summary)}</b>${part(
          "summary",
          word ? (summaryParts ? statusParts(summaryParts) : summary) : "",
        )}${part("explain", explains)}
      </div>
      ${seats.map(({ key, draw }) => now.get(key)?.draw(false) ?? draw(true))}`;
  }
  const groupValue = (group) =>
    group === "annotate"
      ? rows().find((entry) => entry.key === "command:annotations.toggle")?.label ===
        "Show annotations"
        ? "Hidden"
        : ""
      : "";

  function groupList(group) {
    return rows()
      .filter((entry) => groupOf(entry) === group && listed(entry))
      .map((entry) => (entry.copies ? copyRow(entry) : rowFor(entry)));
  }
  // A row of a group whose press copies a text, which stands in About only where the
  // clipboard is missing or refused (`groupOf`), shows that text for the user to select
  // as well, with Leaf's copy control beside it (copy-control.js), which shows on its own
  // face whether the copy took. Where no clipboard is offered (`canCopy`) the control
  // stands down and the text is there to select; the view stays open across a press, so the
  // text is still there if the copy failed. Its value, which a one-line row would end
  // with, says beneath it what the text is. A text of several lines, such as a preview's
  // diagnostics, shows its first few, and selecting it takes the whole.
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
    copy.value = entry.copies;
    copy.disabled = entry.disabled;
    keepsHidden(copy, !canCopy());
    return copy;
  }
  function copyRow(entry) {
    const field = `lf-fp-copy-${entry.key}`;
    return html`<div class="lf-fp-copy" role="none">
      <label class="lf-fp-copy-label" for=${field}>${capital(entry.label)}</label>
      <textarea
        id=${field}
        class="lf-fp-copy-text"
        readonly
        wrap="off"
        spellcheck="false"
        rows=${Math.min(entry.copies.split("\n").length, 3)}
        .value=${entry.copies}
        @focus=${(event) => event.target.select()}
      ></textarea
      >${copyFor(entry)}
      ${entry.value ? html`<p class="lf-fp-copy-note">${entry.value}</p>` : nothing}
    </div>`;
  }

  // Where the agent's latest save failed its check, first what the check found, which
  // the row's notice opens this view to say (`failedSave`); then the versions the picker
  // lists, the one shown marked, each a press that travels
  // there and says the note its stamp gave it after its name, cut to the row and whole
  // on hover; with Compare where the picker offers it;
  // then the version's approval, where
  // the page asks for one, with why a press would not approve yet.
  function versionsList() {
    const { rows: versions, picker, selection, latest } = versionsReading();
    const approval = approvalReading();
    const approved = approval?.approved;
    return html`
      ${
        latest.failed
          ? html`<div class="lf-fp-failed" role="none">
              <b>${latest.label}</b>
              <p class="lf-fp-failed-error">${latest.error}</p>
            </div>`
          : nothing
      }
      ${repeat(
        versions,
        (entry) => `${entry.version === null ? "draft" : "version"}:${entry.revision}`,
        (entry) =>
          html`<div class="lf-fp-version" role="none" ?data-current=${entry.current}>
            ${menuItem(
              html`${entry.name}${
                entry.note
                  ? html`<span class="lf-fp-note">${entry.note}</span>`
                  : nothing
              }`,
              entry.current ? html`<span class="lf-fp-value">Showing</span>` : nothing,
              () => putAwayThen(() => versionPicker.activate(entry)),
              { title: entry.note },
            )}${
              entry.comparable
                ? html`<button
                    type="button"
                    role="menuitem"
                    class="lf-fp-quiet lf-fp-compare"
                    aria-pressed=${String(
                      selection.on && selection.base === entry.version,
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
      ${
        versions.length
          ? nothing
          : html`<p class="lf-fp-empty" role="none">Showing ${picker.token}</p>`
      }
      ${
        approval
          ? html`<hr />
              <div
                class="lf-fp-approval"
                role="none"
                title=${approval.reason ?? nothing}
              >
                ${menuItem(
                  approval.text,
                  approval.reason
                    ? html`<span class="lf-fp-value">${approval.reason}</span>`
                    : nothing,
                  () => approve(),
                  { disabled: Boolean(approval.reason) && !approved },
                )}
              </div>`
          : nothing
      }
    `;
  }

  function shownThreads() {
    const words = query.trim().toLowerCase();
    return threads().filter((thread) => {
      if (words) {
        const text = [threadName(thread), ...thread.msgs.map((m) => m.text ?? "")]
          .join(" ")
          .toLowerCase();
        return text.includes(words);
      }
      if (filter === "unread") return unread(thread);
      if (filter === "drafts") return draftHasContent(replyContext(thread.key));
      if (filter === "resolved") return thread.resolved;
      return !thread.resolved;
    });
  }
  function threadsView() {
    const shown = shownThreads();
    const empty = query.trim()
      ? "Nothing matches."
      : {
          open: "No open threads. Comment below to start one.",
          unread: "All caught up.",
          drafts: "No drafts.",
          resolved: "No resolved threads.",
        }[filter];
    return html`<div class="lf-fp-list">
      ${
        shown.length
          ? repeat(
              shown,
              (thread) => thread.key,
              (thread) =>
                html`<button
                  type="button"
                  class="lf-fp-thread"
                  data-key=${thread.key}
                  ?data-unread=${unread(thread)}
                  ?data-resolved=${thread.resolved}
                  ?data-yours=${threadAttention(thread)?.kind === "needs_user"}
                  @click=${() => open({ view: "thread", thread: thread.key })}
                >
                  <span class="lf-fp-news-mark" aria-hidden="true"></span>
                  <span class="lf-fp-label">${threadName(thread)}</span>
                  <span class="lf-fp-value"
                    >${threadStatus(thread, query.trim() ? null : filter)}</span
                  >
                </button>`,
            )
          : inventoried()
            ? html`<p class="lf-fp-empty">${empty}</p>`
            : nothing
      }
      ${
        // This tab's sends are listed, but the saved threads are still to come, which
        // the list says after the rows it has, so their arrival moves none of them.
        inventoried()
          ? nothing
          : html`<p class="lf-fp-empty">
              ${
                readThreads().phase === "offline"
                  ? "Current threads are unavailable while the server is offline."
                  : "Loading current threads…"
              }
            </p>`
      }
    </div>`;
  }

  // A thread inside the panel is drawn by Leaf's own conversation reader: the panel
  // registers as the page's primary thread presentation (application.js,
  // `registerChromeThreadPresentation`), yielding to one the page's package registers, in
  // whose reader its threads then open, and gives the open thread's messages an outlet
  // here. Leaf draws each message there, with its reactions, rewrites, read marks and
  // agent-authored widgets, and holds news that would move what the reader is reading
  // behind its notice, which the panel stands in the view's head (`newsOutlet`). The
  // reply is the thread's reply box, which the reader draws in the field below rather
  // than in the outlet. A thread anchored to a passage stays the page's where the page
  // draws it: its card opens beside the words it is about, and the panel shows it only
  // where nothing on the page does (`reveal`).
  let presentation = null;
  // The thread's held news is a fact about the thread, so it reads in the head with the
  // others, its title and where it stands among the open ones, before the latter, whole,
  // and pressing it shows what was held. The title gives it the room it takes, so news
  // arriving moves nothing else in the head or the messages below (floating-panel.css,
  // `.lf-fp-facts`). The user chose this on 16 October over the notice at the end of the
  // first message's head, cut to 5rem there ("2 new rep…"), and over the news joining
  // New reply at the view's foot. Each thread's head draws an outlet of its own, so the
  // notice of the thread the user leaves goes with its head rather than standing in the
  // next one's until the reader draws that.
  const newsOutlet = () => head.querySelector(".lf-fp-news-outlet");
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
    const rows = LIST_ROWS[trail.at(-1)?.view];
    const view = shownView();
    return rows && view ? [...view.querySelectorAll(rows)] : [];
  };
  const openView = () =>
    stage.querySelector('.lf-fp-view[data-view="thread"]:not([data-leaving])');
  const outletOf = () => openView()?.querySelector(".lf-fp-outlet") ?? null;
  function nominate(collection, parts) {
    const top = trail.at(-1);
    // On draws each prose ask as its message, in its card's outlet.
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
    for (const message of thread.msgs) parts.message(thread.key, message.key, outlet);
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

  // A thread's reply and Resolve stand outside its view, in the field and the view's
  // head, so the view declares them as its thread's own (thread/focus.js, `threadPart`):
  // while it is the thread open, the reply box in the field where the thread takes a
  // reply, and Resolve; and the view itself as the thread whole. The head is the
  // thread's heading, as a card's title is, and the field's outlet holds its reply, so
  // both are drawings of the thread too, declaring the same parts: `r` on the head's
  // Resolve settles the thread as on a card's, `e` there finds the messages in the view
  // below it, and Escape from the reply returns to the view, as a card's reply returns
  // to the card.
  const openIn = (view) => {
    const top = trail.at(-1);
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
    settlement: (view) => (openIn(view) ? head.querySelector(".lf-fp-settle") : null),
    whole: (view) => (openIn(view) ? openView() : null),
  });
  const declareView = (view) => view && declareThreadParts(view, viewParts);
  declareView(head);
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
  const watchQuote = (node) => {
    quoteWatch.disconnect();
    if (node) quoteWatch.observe(node);
  };
  function quoteHead(thread) {
    const quote = quoteReading(thread, { placedAt });
    if (!quote) return nothing;
    const expanded = quote.localReading && quoteExpanded;
    return html`<header class="lf-fp-quote-head">
      ${
        quote.localReading
          ? html`<button
              type="button"
              class="lf-thread-disclosure lf-quote-expand"
              aria-label="Full quote"
              hidden
              aria-expanded=${String(quoteExpanded)}
              aria-controls="lf-fp-quote"
              @click=${() => {
                quoteExpanded = !quoteExpanded;
                paint();
              }}
            >
              Full quote
            </button>`
          : nothing
      }
      <blockquote
        ${ref(watchQuote)}
        id="lf-fp-quote"
        class=${`lf-quote lf-fp-quote${quote.anchored && !quote.found ? " detached" : ""}`}
        data-expanded=${String(expanded)}
        title=${(quote.anchored && !quote.found && quote.title) || nothing}
      >
        <span class="lf-quote-label">${quote.label}</span>${
          quote.outdated
            ? html`<span class="lf-anchor-status">Earlier data</span>`
            : quote.changed
              ? html`<span class="lf-anchor-status">Changed</span>`
              : nothing
        }
      </blockquote>
    </header>`;
  }

  function threadView(key) {
    const thread = threadByKey(key);
    if (!thread)
      return html`<p class="lf-fp-empty">This thread is not on the page.</p>`;
    return html`${quoteHead(thread)}
      <div class="lf-fp-messages lf-fp-outlet" data-lf-reflow="append"></div>
      ${
        waiting?.key === key
          ? html`<div class="lf-fp-foot">
              <button type="button" class="lf-fp-new-reply" @click=${showAnswer}>
                ${iconTemplate("down", "lf-action-icon")}${waiting.label}
              </button>
            </div>`
          : nothing
      }`;
  }

  // ---------- On: asks answered where they are read ----------
  // The lists are the publisher's (`readQueues`): what waits on the user and on the
  // agent, a tab each, and under each what left it, its Done (`owner`). The view has no
  // name of its own: its title is the open tab's. An item the user answers here stays
  // where it stood, saying its answer and offering Undo, until the view closes, so
  // answering one ask never carries the next under the pointer. Done stands open under
  // the list rather than folded, since a fold opening would grow the view up from under
  // the pointer that opened it.
  let queueTab = "you";
  let seated = null; // queue item keys present in the open On view
  // The height each seated card first stood at, which it keeps while seated, so an
  // answer that shortens it moves nothing below.
  const seatHeights = new Map();
  const QUEUE_TABS = Object.freeze({ you: "user", agent: "agent" });
  // Turning to another list seats its items afresh.
  const chooseQueueTab = (tab) => {
    if (tab === queueTab) return false;
    queueTab = tab;
    seated = null;
    seatHeights.clear();
    return true;
  };
  // The On me door, as the mark and `g M` press it: the view on the
  // user's list, turned to it where the view shows the agent's, else opened or closed.
  function openOnMe() {
    const turned = chooseQueueTab("you");
    if (turned && trail.at(-1)?.view === "queue") paint();
    else open({ view: "queue" });
  }
  const queueLists = () => {
    const reading = readQueues();
    if (reading.phase !== "ready") return { you: [], agent: [], done: [] };
    return {
      you: reading.on_user,
      agent: reading.on_agent,
      done: reading.done.filter((item) => item.owner === QUEUE_TABS[queueTab]),
    };
  };

  // The undo list's entry for the gesture that answered an ask, where it can still be
  // taken back (undo.js).
  const answerGesture = (ask) => {
    const id = ask?.answer?.event?.id ?? ask?.answer?.event;
    if (!id) return null;
    const entry = runtime.undo.find(
      ({ event }) => event.id === id || event.attempt === id,
    );
    return entry?.event ?? null;
  };
  const tabLabel = (tab) => (tab === "agent" ? `On ${agentName()}` : "On me");

  function onItemCard(item, list) {
    const ask = item.kind === "ask" ? item.ask : null;
    const thread = item.thread ? threadByKey(item.thread) : null;
    // A prose ask is a message in its thread, and reads as that message, drawn whole by
    // Leaf's reader as the thread draws it (`nominate`), images and all: its words cut
    // to text would end at whatever they introduce. The thread names it above, where it
    // has a name of its own rather than the message's opening words. Where the page's
    // package draws its conversations instead, Leaf's reader draws none here, and the
    // message's words stand for it under the thread's name.
    const asking =
      ask?.source.kind === "reply" && thread
        ? thread.msgs.find((candidate) => candidate.id === ask.message)
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
        : ask?.prompt?.text;
    const prompt = said && said.trim() !== title.trim() ? said : "";
    const answered = ask && ask.status !== "open";
    const choices =
      ask && !answered && ask.source.kind === "widget" ? askView.choicesOf(ask) : null;
    const gesture = answered ? answerGesture(ask) : null;
    const discuss = thread
      ? html`<button
          type="button"
          class="lf-fp-quiet"
          @click=${() => open({ view: "thread", thread: thread.key })}
        >
          Discuss
        </button>`
      : nothing;
    const arrive = html`<button
      type="button"
      class="lf-fp-quiet"
      @click=${() => {
        close();
        void (ask ? askView.open(ask.id) : queueActions.open(queueItemKey(item)));
      }}
    >
      Show
    </button>`;
    let answers;
    if (list === "done" && !ask)
      answers = html`<span class="lf-fp-said"
          >${[itemOutcome(item), shortAgo(item.ended)].filter(Boolean).join(" ")}</span
        >${thread ? discuss : nothing}`;
    else if (list !== "you" && !answered)
      answers = html`<span class="lf-fp-said"
          >${item.running?.text ?? workflowLabel(item.workflow) ?? ""}</span
        >${thread ? discuss : nothing}`;
    else if (answered)
      answers = html`<span class="lf-fp-said">${askEnding(ask)}</span>${
          gesture
            ? html`<button
                type="button"
                class="lf-fp-quiet"
                @click=${() => withdraw(gesture)}
              >
                Undo
              </button>`
            : nothing
        }`;
    else if (ask?.source.kind === "approval") {
      const approval = approvalReading();
      answers = html`<button
        type="button"
        class="lf-fp-answer"
        aria-disabled=${approval?.reason ? "true" : nothing}
        title=${approval?.reason ?? nothing}
        @click=${() => approve()}
      >
        ${approval?.text ?? "Approve version"}
      </button>`;
    } else if (choices?.length)
      answers = html`${choices.map(
        (choice) =>
          html`<button
            type="button"
            class="lf-fp-answer"
            aria-pressed=${String(choice.chosen)}
            @click=${() => {
              choice.press();
              paint();
            }}
          >
            ${capital(choice.label)}
          </button>`,
      )}${discuss}`;
    else if (item.offers?.done)
      answers = html`<button
          type="button"
          class="lf-fp-answer"
          @click=${() => queueActions.done(queueItemKey(item))}
        >
          Done</button
        >${discuss}${arrive}`;
    else if (ask?.source.kind === "reply" && thread)
      answers = html`<button
        type="button"
        class="lf-fp-answer"
        @click=${() => open({ view: "thread", thread: thread.key })}
      >
        Reply
      </button>`;
    else answers = html`${arrive}${discuss}`;
    const key = queueItemKey(item);
    const approval = ask?.source.kind === "approval";
    return html`<section
      class="lf-fp-on-item"
      data-list=${list}
      data-key=${key}
      ?data-approval=${approval}
      style=${seatHeights.has(key) ? `min-height: ${seatHeights.get(key)}px` : ""}
    >
      ${
        message
          ? html`${title ? html`<h3 class="lf-fp-on-title">${title}</h3>` : nothing}
              <div
                class="lf-fp-asked lf-fp-outlet"
                data-thread=${thread.key}
                data-message=${message.key}
              ></div>`
          : prompt
            ? html`<h3 class="lf-fp-on-title">${title}</h3>
                <p class="lf-fp-prompt">${prompt}</p>`
            : html`<p class="lf-fp-prompt">${title}</p>`
      }
      <div class="lf-fp-answers">${answers}</div>
    </section>`;
  }

  // The version's approval is answered here: arriving at it, as `m` and an On me row
  // do, opens this view on its card and stands on its
  // Approve, or once it is answered on its Undo, or the card itself.
  const approvalControl = () => {
    const card = stage.querySelector(".lf-fp-view:not([data-leaving]) [data-approval]");
    return card?.querySelector("button") ?? card;
  };
  // An approval is an ask, always On me's, open or done.
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
    const lists = queueLists();
    const all = [...lists.you, ...lists.agent, ...lists.done];
    const byKey = new Map(all.map((item) => [queueItemKey(item), item]));
    const current = lists[queueTab].map(queueItemKey);
    // The seats this opening of the view holds: those it showed, still in the reading
    // wherever they now stand, then any that joined this list since.
    seated = [
      ...(seated ?? []).filter((key) => byKey.has(key)),
      ...current.filter((key) => !(seated ?? []).includes(key)),
    ];
    const listOf = (item) =>
      lists.you.includes(item) ? "you" : lists.agent.includes(item) ? "agent" : "done";
    const items = seated.map((key) => byKey.get(key));
    const finished = lists.done.filter((item) => !seated.includes(queueItemKey(item)));
    return html`${
      items.length
        ? repeat(items, queueItemKey, (item) => onItemCard(item, listOf(item)))
        : html`<p class="lf-fp-empty">
            Nothing waiting on ${queueTab === "you" ? "me" : agentName()}.
          </p>`
    }${
      finished.length
        ? html`<h3 class="lf-fp-on-done">Done</h3>
            ${repeat(finished, queueItemKey, (item) => onItemCard(item, "done"))}`
        : nothing
    }`;
  }

  // ---------- All pages: the pages live on this machine ----------
  // Each page served on this machine now, this one first (live-leaves.js, `leavesRows`):
  // its leaf in its agent's tone, its title, and what its agent is doing, its whole
  // account on hover. A row is a link that opens its page in a tab of its own; this
  // page's row says it is this page and goes nowhere, so the walk passes it by.
  function pagesView() {
    const rows = leavesRows(runtime.state);
    if (!rows.length) return html`<p class="lf-fp-empty">No pages are live.</p>`;
    return html`<div class="lf-fp-list">
      ${repeat(
        rows,
        (row) => row.key,
        (row) => {
          const face = html`<span
              class=${`lf-dot${row.tone ? ` ${row.tone}` : ""}`}
              aria-hidden="true"
            ></span
            ><span class="lf-fp-label">${row.title}</span
            ><span class="lf-fp-value">${row.self ? "This page" : row.line}</span>`;
          return row.self
            ? html`<div class="lf-fp-page" title=${row.account}>${face}</div>`
            : html`<a
                class="lf-fp-page"
                data-key=${row.key}
                href=${row.href}
                target="_blank"
                rel="noopener"
                title=${row.account}
                >${face}</a
              >`;
        },
      )}
    </div>`;
  }

  function viewTemplate(route) {
    switch (route.view) {
      case "threads":
        return threadsView();
      case "thread":
        return threadView(route.thread);
      case "queue":
        return onView();
      case "leaves":
        return pagesView();
    }
    return nothing;
  }

  // ---------- the head: where the user is, at the view's top edge ----------
  // A tab with a count (`count(name)` a number rather than null) says it even at zero,
  // in a quieter ink, in a room kept for two digits, so news changing the count moves
  // no tab beside it and no tab stands with a blank where its count would go.
  // Rejected: a blank at zero, which reads as a gap after the word, and the word
  // centred in a room wider on both sides, which stood it off centre once it had a
  // count, as On me nearly always does.
  const tabs = (names, current, label, choose, count) =>
    html`<div class="lf-fp-filters" role="group" aria-label="Show">
      ${names.map((name) => {
        const counted = count(name);
        return html`<button
          type="button"
          aria-pressed=${String(current === name)}
          @click=${() => choose(name)}
        >
          ${label(name)}${
            counted === null
              ? nothing
              : html` <span class="lf-fp-count" ?data-zero=${!counted}
                  >${counted}</span
                >`
          }
        </button>`;
      })}
    </div>`;
  function headTemplate(top) {
    const parent = trail.at(-2);
    const thread = top.view === "thread" ? threadByKey(top.thread) : null;
    /** @type {unknown} */
    let aux = nothing;
    if (top.view === "threads") {
      const news = newCount();
      aux = html`${tabs(
          FILTERS,
          filter,
          capital,
          (name) => {
            filter = name;
            query = "";
            paint();
          },
          // Open counts what the thread mark counts, so the mark's number is found here.
          (name) => (name === "unread" ? news : name === "open" ? openCount() : null),
        )}<button
          type="button"
          class="lf-fp-icon-btn"
          aria-label="Find a thread or message"
          aria-pressed=${String(searching)}
          @click=${() => {
            searching = !searching;
            query = "";
            paint();
            if (searching)
              focusDestination(head.querySelector(".lf-fp-search"), "move");
          }}
        >
          ${iconTemplate("search", "lf-action-icon")}
        </button>`;
    } else if (top.view === "queue") {
      const lists = queueLists();
      aux = tabs(
        Object.keys(QUEUE_TABS),
        queueTab,
        tabLabel,
        (tab) => {
          if (chooseQueueTab(tab)) paint();
        },
        (tab) => lists[tab].length,
      );
    } else if (thread) {
      // Resolve and Reopen share one seat as wide as the wider of them, both drawn and
      // one shown, so the agent settling the thread moves nothing beside it.
      // Resolve says it is unavailable while a settling is pending rather than leaving
      // the tab order, so the user who pressed it, or `r` on it, stays standing on it;
      // the action itself refuses a press meanwhile (thread/actions.js, `settle`).
      // Resolving leaves the reply's editing place, as a card's Resolve does, keeping
      // its draft (thread/replies.js), so the thread shows its way back instead.
      onPageSeat ||= Boolean(thread.anchor) && !unplaced.has(thread.key);
      aux = html`${
          onPageSeat
            ? html`<button
                type="button"
                class="lf-fp-quiet"
                ?disabled=${!thread.anchor}
                ?data-unoffered=${!thread.anchor}
                @click=${() => {
                  // The words come into view in the press's own task, so a widget
                  // hiding them, as a diff's file filter does, gives them up to this
                  // press rather than after the route's awaits (widget-elements.js,
                  // `reveal`).
                  const intent = retainUserIntent();
                  const place = placedAt(thread.id)?.place;
                  if (place) reveal(place, intent);
                  close();
                  // The reply box the field drew goes back to the thread's drawing on
                  // the page once the reader has drawn the view gone, and the route
                  // lands in it there.
                  void present({ release: true }).then(() =>
                    threadActions.open(thread.key, { part: null, intent }),
                  );
                }}
              >
                On the page
              </button>`
            : nothing
        }<button
          type="button"
          class="lf-fp-settle ${thread.resolved ? "lf-reopen" : "lf-resolve"}"
          aria-disabled=${String(
            !(thread.resolved ? thread.offers.reopen : thread.offers.resolve),
          )}
          @click=${() => {
            if (!thread.resolved) dismissReply(thread.key);
            void settleThread({
              parent: () => thread.id,
              key: thread.key,
              resolved: Boolean(thread.resolved),
              prepareLanding: thread.resolved ? null : () => resolveLanding(thread),
              ...settlement,
            }).catch(() => {});
          }}
        >
          <span class="lf-fp-face" ?data-shown=${!thread.resolved}
            >${iconTemplate("check", "lf-action-icon")}Resolve</span
          ><span class="lf-fp-face" ?data-shown=${thread.resolved}>Reopen</span>
        </button>`;
    }
    const openThreads = threads().filter((candidate) => !candidate.resolved);
    const at = thread ? openThreads.indexOf(thread) : -1;
    // On's name is its selected tab's, which the tabs beside it already show, so the
    // heading names the view to assistive tech alone.
    const titleClass = top.view === "queue" ? "lf-fp-title lf-quiet" : "lf-fp-title";
    const crumb =
      top.view === "threads" && searching
        ? html`<input
            class="lf-fp-search"
            type="search"
            placeholder="Find a thread or message"
            aria-label="Find a thread or message"
            .value=${query}
            @input=${(event) => {
              query = event.target.value;
              paint();
            }}
          />`
        : html`${
              parent
                ? html`<button
                      type="button"
                      class="lf-fp-back"
                      aria-label=${`Back to ${titleOf(parent)}`}
                      @click=${back}
                    >
                      ${titleOf(parent)}</button
                    ><span class="lf-fp-sep" aria-hidden="true">/</span>`
                : nothing
            }
            <h2 class=${titleClass}>${titleOf(top)}</h2>
            ${
              thread
                ? html`<span class="lf-fp-facts"
                    >${keyedBy(
                      thread.key,
                      html`<span class="lf-fp-news-outlet"></span>`,
                    )}${
                      at >= 0
                        ? html`<span class="lf-fp-where"
                            >${at + 1} of ${openThreads.length}</span
                          >`
                        : nothing
                    }</span
                  >`
                : nothing
            }`;
    return html`<div class="lf-fp-crumb">${crumb}</div>
      <div class="lf-fp-aux">${aux}</div>
      ${expand}
      <button
        type="button"
        class="lf-fp-icon-btn lf-fp-close"
        aria-label="Close"
        @click=${close}
      >
        ${iconTemplate("down", "lf-action-icon")}
      </button>`;
  }

  // ---------- paint ----------
  function setRest(rest) {
    const before = trail.at(-1);
    // Folding takes away whatever the user stood on in the panel but the leaf, so it
    // keeps them on the leaf it folds to; from the page they stay where they are.
    const inside = standingIn(host);
    prefs().setRest(rest);
    trail = [];
    menuOpen = false;
    menuAt = null;
    menuRoom = null;
    held = null;
    transition(before, { focus: false });
    if (inside) focusDestination(leaf, "return");
  }

  // A paint can blur what it removes, and the blur asks for a paint; that one runs
  // once this has finished rather than inside it. Every paint runs through the panel's
  // watcher (`watchProjection`), so the readings it draws repaint it whichever input
  // asked for the paint.
  let painting = false;
  let again = false;
  let watching = null;
  function paint() {
    if (painting) again = true;
    else if (watching) watching.refresh();
    else paintPanel();
  }
  function paintPanel() {
    painting = true;
    try {
      paintNow();
      if ([holdRoom(), holdMenu()].some(Boolean)) paintNow();
    } finally {
      painting = false;
    }
    if (again) {
      again = false;
      paintPanel();
      return;
    }
    landReader();
    seatOnItems();
  }
  // A card's seat is the height it first stands at once its message is drawn; a card
  // whose message Leaf's reader has not drawn yet asks it to (`nominate`), once, and
  // releases what the reader holds back, since a thread it holds as news would leave the
  // card standing without its question (thread/held-news.js).
  const asked = new WeakSet();
  function seatOnItems() {
    if (trail.at(-1)?.view !== "queue") return;
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
  // A thread the reader opens, or answers, or asks to see the news of, stands at its end.
  function landReader() {
    const top = trail.at(-1);
    if (!landAtEnd || top?.view !== "thread" || top.thread !== landAtEnd.key) return;
    const view = stage.querySelector(
      '.lf-fp-view[data-view="thread"]:not([data-leaving])',
    );
    if (!view || (outletOf()?.childElementCount ?? 0) <= landAtEnd.after) return;
    landAtEnd = null;
    scrollToEnd(view);
  }
  function paintNow() {
    const top = trail.at(-1) ?? null;
    const folded = prefs().rest === "mark" && !top && !menuOpen;
    keeps(host, "data-rest", folded ? "mark" : "row");
    keeps(host, "data-open", top ? top.view : null);
    keeps(host, "data-menu", menuOpen ? "" : null);
    keeps(mark, "class", `lf-dot${status().tone ? ` ${status().tone}` : ""}`);
    keeps(
      leaf,
      "aria-label",
      folded ? `Unfold Leaf · ${status().summary}` : `Page menu · ${status().summary}`,
    );
    keeps(leaf, "aria-expanded", folded ? null : String(menuOpen));

    // What waits on the user, which the folded leaf carries as a badge and a dot.
    const onUser = onUserCount();
    const news = newCount();
    keepsText(badge, onUser ? String(onUser) : "");
    keeps(badge, "data-shown", onUser ? "" : null);
    keeps(newsDot, "data-shown", news ? "" : null);

    render(menuOpen ? menuTemplate() : nothing, menu);
    // A copy control the menu keeps for its next showing leaves the list the render just
    // took down, which it would otherwise hold whole, rows and all, as its parent.
    for (const copy of [...copyItems.values(), ...copies.values()])
      if (!copy.isConnected) copy.remove();
    keeps(menu, "data-level", menuOpen && menuAt ? menuAt.view : null);
    keeps(menu, "style", menuOpen && menuRoom ? `height: ${menuRoom}px` : null);
    // A text to select, which About holds where no clipboard copies it, is no menu's row.
    keeps(menu, "role", menu.querySelector("textarea") ? "dialog" : "menu");
    if (menuOpen) {
      const rows = menuRows();
      rove(rows, rows.includes(focused()) ? focused() : rows[0]);
    }

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
    render(
      repeat(
        views,
        routeKey,
        (route) =>
          html`<div
            class="lf-fp-view"
            tabindex="-1"
            data-view=${route.view}
            data-thread=${shows(route) ?? nothing}
            ?data-lf-thread-view=${shows(route) !== null}
            ?data-lf-rises=${route.view === "thread"}
            ${ref(declareView)}
            style=${
              rooms.has(routeKey(route))
                ? `height: ${rooms.get(routeKey(route))}px`
                : nothing
            }
            ?data-leaving=${route === leaving}
            @scroll=${sawAnswer}
          >
            ${viewTemplate(route)}
          </div>`,
      ),
      stage,
    );
    if (restoreFocus && heldView === shownView()) restoreFocus(heldView);
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
    render(top ? headTemplate(top) : nothing, head);
    // The more-room mark stands in the view's head while one is open, else at the end
    // of the line over the field.
    if (!top) move(context, expand, null);
    const heading = top ? shows(top) : null;
    for (const drawing of [head, replyOutlet]) {
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
    const shown = replying ? [replyOutlet, resolvedLine] : [pageEditor().box];
    if (field.firstElementChild !== shown[0]) {
      const had = standingIn(field);
      field.replaceChildren(...shown);
      if (had && !replying) focusDestination(leaf, "return");
    }
    // A move to the page's field waits for the paint that stands it there, and lands
    // before the paint reads where the caret is, so the field is drawn once for it
    // (`writeOnPage`).
    if (caretToField && !replying) {
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
    // While the user types, Send stands in the field's corner and the counts step
    // aside for the field.
    typing = writing && Boolean(draftOf(input).trim());
    keeps(host, "data-typing", typing ? "" : null);
    if (!draftOf(input).trim()) expanded = false;
    // The mark stays while the field is wide, where the draft may fit three lines again.
    keeps(host, "data-long", (long || expanded) && !resting ? "" : null);
    keeps(host, "data-expanded", expanded ? "" : null);
    keeps(expand, "aria-pressed", String(expanded));
    keeps(expand, "aria-label", expanded ? "Less room to write" : "More room to write");
    keeps(expand, "title", expanded ? "Less room to write" : "More room to write");
    render(iconTemplate(expanded ? "fit" : "expand", "lf-action-icon"), expand);
    // Whose reading the empty field says, which its face follows (`saying`): a status
    // dims, and carries the sheen while the agent works, unless it asks the user to act,
    // such as to nudge the agent in its terminal, which it says in its tone's ink
    // (`pageStatus`, `asks`). The field's room cuts a long status short, so pointing at
    // the field says it in full, as the folded leaf's peek does.
    const reading = fieldReading(replying ? top.thread : null, input);
    keeps(host, "data-tone", status().tone || null);
    keeps(host, "data-asks", status().asks ? "" : null);
    keeps(
      field,
      "title",
      reading.says === "status" ? status().explanation || status().summary : null,
    );
    // The line over the field says what the field cannot: a passing notice is said
    // where the field's placeholder would be, and once the caret is in, where the
    // placeholder says where the words go, or words hide it, the notice stands on this
    // line instead, as a refused send's reason does over the words it returned. Where the
    // words go is said once: by the empty focused field's placeholder, and once words hide
    // that, here in the same words, the way a field's label rises above what is written
    // in it. Who reads them goes unsaid: every word written here goes to the page's one
    // agent. With nothing to say the line is gone, and while a view is open it is gone
    // too: the leaf's peek says a notice answering the user there (`paintPeek`), and
    // news arriving, a walk's position and Go-to's word go unsaid (`passing`).
    const empty = draftOf(input) === "";
    const notice = passing();
    const covered = notice.visible && (!empty || reading.says === "destination");
    overView = Boolean(top) && covered && notice.answers;
    keeps(context, "data-notice", covered ? "" : null);
    keepsText(
      contextWords,
      top ? "" : covered ? notice.message : empty ? "" : whereTo(null),
    );
    keepsHidden(context, !contextWords.textContent);
    paintPeek();

    const standing = rowNotice();
    keepsHidden(rowNoticeSeat, !standing);
    render(standing ? rowNoticeTemplate(standing) : nothing, rowNoticeSeat);

    // The next step of what the user is doing now, such as leaving Draw mode or
    // commenting on the words a finger selected, stands in the counts' place while that
    // gesture holds it (page-controls.js, `gesture`).
    const steps = rows().filter((entry) => entry.gesture);
    keeps(quick, "data-steps", steps.length ? "" : null);
    if (steps.length) {
      render(
        html`${repeat(
          steps,
          (entry) => entry.key,
          (entry) =>
            html`<button
              type="button"
              class="lf-fp-chip lf-fp-step"
              ?disabled=${entry.disabled}
              @mousedown=${(event) => event.preventDefault()}
              @click=${() => entry.press()}
            >
              ${entry.label}
            </button>`,
        )}`,
        quick,
      );
      return;
    }
    // Each mark keeps its room whether or not it has a number, so a count arriving or
    // leaving moves nothing beside it.
    // A mark's name is its tooltip too, as an icon control's title is elsewhere in Leaf.
    const threadsOpen = top?.view === "threads" || top?.view === "thread";
    const onUserName = onUser ? `On me: ${onUser}` : "On me";
    const threadsName = inventoried()
      ? `Threads, ${openCount()} open${news ? `, ${news} with news` : ""}`
      : "Threads";
    render(
      html`<button
          type="button"
          class="lf-fp-chip lf-fp-on-user"
          aria-pressed=${String(top?.view === "queue")}
          ?data-due=${onUser > 0}
          aria-label=${onUserName}
          title=${onUserName}
          @click=${openOnMe}
        >
          ${iconTemplate("inbox", "lf-action-icon")}<span class="lf-fp-num"
            >${onUser || ""}</span
          ></button
        ><button
          type="button"
          class="lf-fp-chip lf-fp-threads"
          aria-pressed=${String(threadsOpen)}
          aria-label=${threadsName}
          title=${threadsName}
          @click=${() => {
            filter = news && !threadsOpen ? "unread" : "open";
            query = "";
            open({ view: "threads" });
          }}
        >
          ${iconTemplate("comment", "lf-action-icon")}<span class="lf-fp-num"
            >${openCount() || ""}</span
          ><span class="lf-fp-news" ?hidden=${!news}></span>
        </button>`,
      quick,
    );
  }

  // ---------- the row's notice ----------
  // One small notice beside the marks, for a state the user should not miss while they
  // read: a few words (`says`), a `tone` that tints it, and at most one `press`, a
  // button or a link. Leaf's own readings raise each, and a notice ends when the state
  // it reads does. The slot shows the first that holds, most urgent first, so the
  // field's room never goes to a stack of them. Each case is a reading below; a new
  // one joins `ROW_NOTICES` in its place.
  // The agent's latest save failed its check, so the page shows the last one that
  // passed; Why opens Versions, which says what the check found.
  function failedSave() {
    const { latest } = versionsReading();
    if (!latest.failed) return null;
    return {
      says: "Latest edit not shown",
      tone: "danger",
      press: {
        label: "Why",
        title: latest.error,
        run: () => showMenuAt({ view: "versions" }),
      },
    };
  }
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
  // A copy of a page on Leaf's website: the field says who revises it, and the notice
  // where Leaf comes from; the menu's head holds the introduction and its links.
  function website() {
    const { publication } = status();
    if (!publication) return null;
    return {
      says: publication.examples ? "Example" : "Leaf page",
      tone: "accent",
      press: { label: publication.install, href: publication.installUrl },
    };
  }
  // The version shown is approved, until a new version asks again.
  function approvedVersion() {
    if (!approvalReading()?.approved) return null;
    return { says: `✓ ${versionsReading().picker.token} approved`, tone: "ok" };
  }
  const ROW_NOTICES = [failedSave, olderVersion, website, approvedVersion];
  const rowNotice = () => {
    for (const read of ROW_NOTICES) {
      const notice = read();
      if (notice) return notice;
    }
    return null;
  };
  function rowNoticeTemplate({ says, tone, press = null }) {
    const face = html`<span class="lf-fp-row-notice-face" data-tone=${tone}
      >${says}${
        press
          ? html`<span class="lf-fp-row-notice-sep" aria-hidden="true">·</span
              ><span class="lf-fp-row-notice-act">${press.label}</span>`
          : nothing
      }</span
    >`;
    if (!press) return face;
    return press.href
      ? html`<a
          class="lf-fp-chip lf-fp-row-notice-press"
          href=${press.href}
          target="_blank"
          rel="noopener"
          >${face}</a
        >`
      : html`<button
          type="button"
          class="lf-fp-chip lf-fp-row-notice-press"
          title=${press.title ?? nothing}
          ?disabled=${press.disabled}
          @click=${press.run}
        >
          ${face}
        </button>`;
  }

  // ---------- gestures ----------
  // The leaf unfolds a folded panel, and otherwise opens or closes its menu.
  leaf.addEventListener("click", () => {
    if (host.dataset.rest === "mark") {
      prefs().setRest("row");
      paint();
      return;
    }
    setMenu(!menuOpen);
    if (menuOpen && keyed) {
      const first = menu.querySelector("button");
      if (first) focusDestination(first, "move");
    }
  });
  // The folded leaf's peek says the status in full while the pointer or focus asks for
  // it, and a passing notice by itself, since a folded panel has no field to say it in.
  // Over an open view it says a notice answering the user that the field cannot, which
  // the line over the field would say with no view open (`overView`), unless the leaf's
  // menu stands where it would show.
  function paintPeek() {
    const folded = host.dataset.rest === "mark";
    const notice = passing();
    const telling = notice.visible && (folded || (overView && !menuOpen));
    const reading = status();
    const parts = reading.explanationParts ?? [
      { text: reading.explanation || reading.summary },
    ];
    if (!folded || !peekAsked || !readingIsContinuous()) peekReading = null;
    if (folded && peekAsked && !telling && pagePresented()) peekReading ??= parts;
    render(telling ? notice.message : statusParts(peekReading ?? parts), peek);
    keeps(peek, "data-shown", telling || (folded && peekAsked) ? "" : null);
  }
  const showPeek = (on) => {
    peekAsked = on;
    paintPeek();
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
    if (query && focused()?.matches?.(".lf-fp-search"))
      return {
        root: host,
        title: "clear search",
        description: "Clear the search",
        out: () => {
          query = "";
          paint();
        },
      };
    if (menuOpen && menuAt)
      return {
        root: host,
        title: "back to menu",
        description: "Go back from the list to the page menu",
        out: () => showMenuAt(null),
      };
    if (menuOpen)
      return {
        root: host,
        title: "close menu",
        description: "Close the page menu",
        out: () => {
          setMenu(false);
          focusDestination(leaf, "return");
        },
      };
    if (!trail.length) return null;
    return {
      root: host,
      title: `close ${titleOf(trail.at(-1)).toLowerCase()}`,
      description: `Close ${titleOf(trail.at(-1))}`,
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
  keys(
    host,
    "In the floating panel",
    /** @type {object[]} */ (
      rowWalk({
        id: "panel.floating.menu",
        noun: "Row",
        plural: "rows of the page menu",
        rows: menuRows,
        // A menu names its rows' places to a screen reader itself, so the walk shows none.
        position: () => null,
        landed: (row) => rove(menuRows(), row),
      }).map((row) => ({ ...row, when: () => menuOpen }))
    ).concat(
      rowWalk({
        id: "panel.floating.list",
        noun: "Row",
        plural: "rows of the open view",
        rows: listRows,
        position: () => null,
        landed: (row) => rove(listRows(), row),
      }).map((row) => ({ ...row, when: () => !menuOpen && inList() })),
      // → goes into the list a row opens, as its chevron points, and ← back to the menu.
      {
        id: "panel.floating.menu.level",
        keys: ["ArrowLeft", "ArrowRight"],
        routes: [
          { id: "panel.floating.menu.level-left", binding: "ArrowLeft", title: "left" },
          {
            id: "panel.floating.menu.level-right",
            binding: "ArrowRight",
            title: "right",
          },
        ],
        description:
          "Open the list a row of the page menu leads to, or go back to the menu",
        title: "open or leave a list",
        when: () => menuOpen && renderedUnder(focused(), menu),
        run: (binding) => {
          const [backward] = rowArrows(menu);
          if (binding === backward) {
            if (menuAt) showMenuAt(null);
          } else if (focused()?.hasAttribute("data-opens")) focused().click();
        },
      },
      // Tab leaves the menu as it leaves a menu button's menu: the menu goes, and the
      // browser moves the user on from the leaf that opened it, either way.
      ["Tab", "Shift+Tab"].map((key) => ({
        id: `panel.floating.menu.leave-${key === "Tab" ? "forward" : "backward"}`,
        keys: [key],
        description: `Leave the page menu ${key === "Tab" ? "forward" : "backward"}`,
        title: key === "Tab" ? "leave forward" : "leave backward",
        native: true,
        when: () => menuOpen && renderedUnder(focused(), menu),
        run: () => {
          focusDestination(leaf, "move");
          setMenu(false);
        },
      })),
    ),
  );
  // The caret in the field is the innermost thing open, so while a view is open
  // Escape leaves the field first and leaves the rest standing, the draft included
  // (keyboard/AGENTS.md, "Escape"), and the next Escape puts the view away. A reply
  // returns to its thread, the view, by the reply box's own way back (thread/landing.js,
  // `text.leave`); the page's field returns to the leaf beside it. The step is the
  // field's alone, so the leaf and the chips keep Escape for the page's ladder.
  keys(field, "In the comment field", [
    {
      id: "panel.floating.leave",
      keys: ["Escape"],
      description: "Leave the comment field, keeping the view open above it",
      title: "leave field",
      when: () => !menuOpen && trail.length > 0,
      run: () => focusDestination(leaf, "return"),
    },
  ]);
  // Folding to the leaf is the page's command, so it has a key and a row in the menu.
  pageCommand({
    id: FOLD,
    keys: ["."],
    description: "Fold the Leaf panel to the leaf in the window's corner, or unfold it",
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
    if (menuOpen && node && node !== leaf && !renderedUnder(node, menu)) setMenu(false);
    const inside = Boolean(node) && renderedUnder(node, host);
    if (inside && left && !renderedUnder(left, host)) heldStanding = readPlace(left);
    const next = inside ? writing || node.localName === "leaf-text" : false;
    if (next === writing && !inside) return;
    writing = next;
    paint();
  });
  // A press on the page puts away what stands open above the row. A press in a modal
  // over the panel, such as the image viewer opened from a draft, is not on the page.
  document.addEventListener(
    "pointerdown",
    (event) => {
      if (event.composedPath().includes(host) || !nativeModalAdmits(host)) return;
      if (menuOpen) setMenu(false);
      if (trail.length) close();
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
      shows: () => trail.at(-1)?.view === "threads",
      press: () => {
        filter = "open";
        query = "";
        open({ view: "threads" });
      },
    },
    queue: {
      shows: () => trail.at(-1)?.view === "queue" && queueTab === "you",
      press: openOnMe,
    },
    leaves: {
      shows: () => trail.at(-1)?.view === "leaves",
      press: () => open({ view: "leaves" }),
    },
    versions: {
      shows: () => menuOpen && menuAt?.view === "versions",
      press: () =>
        menuOpen && menuAt?.view === "versions"
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
    const top = trail.at(-1);
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
      open({ view: "threads" }, { reopen: true, focus: false });
      paint();
    }
    return present({ release: true }).then(() => true);
  }

  // A live revision that loads a fresh document carries the thread open here, and where
  // its view was read to, across it (version.js, the revision handoff): the reader is
  // still at it, so the view comes back as they left it, without taking focus, which
  // the reply's own editing continuity hands back. A view opened by the user's next
  // visit does not come back (restore-state.js); this is not that.
  function captureStanding() {
    const top = trail.at(-1);
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
    open({ view: "thread", thread: thread.key }, { reopen: true, focus: false });
    landAtEnd = null;
    void present({ release: true }).then(() => {
      const view = openView();
      if (view && trail.at(-1)?.thread === thread.key)
        moveScrollerBy(view, standing.scroll - view.scrollTop);
    });
    return true;
  }

  // The page's comment box in this chrome, as `c` and Resume writing find it
  // (composing/surface.js, `commentDestination`).
  const pageComment = Object.freeze({
    get box() {
      return pageEditor().input;
    },
    open: writeOnPage,
    close: () => {},
    sync: () => pageEditor().sync(),
  });

  // Where Leaf's controls begin in this chrome, as the page's Skip to Leaf controls finds
  // them: the field, where words go, or the leaf, while the panel is folded to it.
  // A resolved thread's field takes no words, so there the leaf is where they begin.
  function enter() {
    const top = trail.at(-1);
    const thread = top?.view === "thread" ? threadByKey(top.thread) : null;
    const takesWords = !thread || replyAvailable(thread);
    const input = prefs().rest !== "mark" && takesWords ? fieldInput() : null;
    focusDestination(input ?? leaf, "move");
  }

  function mount(parent) {
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
        const top = trail.at(-1);
        if (top?.view !== "thread") return null;
        const focus = standingIn(host);
        const message = focus
          ? (closestAcross(focused(), ".lf-msg")?.dataset.message ?? null)
          : null;
        return () => openInPackage(top.thread, { focus, message });
      },
      // A thread about the whole page opens here; one about a passage opens beside it,
      // where the page draws it, and here only for one of its messages, which Leaf's
      // reader alone draws whole, or where nothing on the page shows it, as on a page
      // drawing no margin, the destination's last resort (`request.last`,
      // thread/destination.js). Where the user lands in it is the route's
      // (`request.part`), which Leaf's destinations take them to once it is drawn: the
      // reply, a message, or the thread itself, the view, where the `t` walk goes on from.
      reveal: (key, { part, last }) => {
        const thread = threadByKey(key);
        if (!thread) return false;
        if (thread.anchor && part !== "message") {
          if (!last) {
            unplaced.delete(thread.key);
            // The page draws it, so a view of it here goes, as On the page puts it
            // away, and the thread shows once.
            const top = trail.at(-1);
            if (top?.view === "thread" && threadByKey(top.thread)?.key === thread.key)
              close();
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
    registerNoticePresentation(() => paint());
    registerStatusContextPresentation(() => paint());
    watchPageControls(() => paint());
    // A comparison started or stopped changes the versions without a publication.
    versionPicker.watch(() => paint());
    document.addEventListener("lf-chrome-preference", () => paint());
    onReadingInterrupted(() => {
      peekReading = null;
      paintPeek();
    });
    watching = watchProjection(host, paintPanel);
    paint();
  }

  return {
    host,
    mount,
    open,
    close,
    enter,
    pageComment,
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
  };
}
