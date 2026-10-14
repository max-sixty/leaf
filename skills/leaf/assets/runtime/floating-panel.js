/* The floating panel: Leaf's chrome as one box hovering over the foot of the page, in
 * place of the banner and the bottom bar, which a reader has only by asking for them
 * (prepaint.js, `lfChrome`). It is another presentation of what the banner, the bottom
 * bar, Threads and the On panel already own, so it reads their readings and calls their
 * commands: the status (`statusReading`), the toolbar's rows (`bannerRows`), the threads
 * (`readThreads`), the queues (`readQueues`), the versions (`versionPicker`), the
 * drafts (drafts.js) and the passing notices (notifications.js). It decides only how
 * they are shown.
 *
 * The box has three sizes, and which it stands at follows what the user does, so no
 * setting chooses it:
 * - **Folded**, the leaf alone in the window's corner, coloured by the agent's state,
 *   with a badge counting what waits on the user and a dot for threads with news. The
 *   user folds it from the leaf's menu; a press on the leaf unfolds it, and it stays as
 *   it was left across pages (`rest`).
 * - **The row**: the leaf, the comment field, and marks with counts for On me and
 *   Threads. The empty field says what the agent is doing or wants, in the banner's own
 *   words (`statusReading`), or what a passing notice says, where a placeholder would say
 *   "Comment"; in a thread it says whose turn it is. A status reads dimmer than anything
 *   written, and while the agent works it carries the one sheen that marks work under
 *   way. Clicking in gives the placeholder to where the words go, and opens one quiet
 *   line above it naming who they go to; once words hide the placeholder, the line names
 *   where as well.
 * - **Opened**: a view above the same row (On, Threads, a thread, Versions, or a
 *   group of the page's controls) with where the user is at its top edge. It lasts while
 *   it is used: Escape or a press on the page puts it away, Escape once the caret has
 *   left the field, since the caret is the innermost thing open. The room of the line
 *   naming where the words go stands while a view is open, so clicking in moves nothing
 *   at the view's head. It is as tall as what it
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
 * opens a list of its own (Versions, and the groups: Navigate, Annotations, About). A
 * keyboard's convenience for where the reader stands, such as Resume writing, stands
 * under Navigate only where no keyboard is there to reach it (banner-toolbar.js, the
 * `keys` group). The field the user clicks in is the field they write in: a page
 * comment where no thread is open, a reply where one is: the reply box every view of a
 * thread draws (thread/replies.js), with its ↑ to the user's last message, which Leaf's
 * reader draws in the field's place. Each destination keeps its own native editor (its
 * draft, caret and send), and the panel stands the current one in the field's place, so
 * words never move between editors.
 *
 * Nothing moves under the pointer: a filtered inventory keeps its height, and a control
 * the user pressed stays where it was. Every change of the box's size takes effect in
 * one step, and the surface behind it, a separate layer, follows by a clip from where it
 * stood to where it stands, the way the Codex app's floating panel moves
 * (`notes/floating-panel/GOAL.md`): nothing's layout tweens, so nothing a user aims at
 * travels after the gesture that moved it. */
import { html, nothing, ref, render, repeat } from "../vendor/browser-runtime.js";
import { el } from "./widget-elements.js";
import { iconTemplate } from "./icons.js";
import { keeps, keepsHidden, keepsText } from "./keeps.js";
import {
  approvalReading,
  approve,
  registerApprovalPresentation,
  toggleBtn,
  statusReading,
} from "./banner.js";
import { queueBtn } from "./drawers.js";
import { keys } from "./keyboard/scopes.js";
import { pageCommand, pageRung } from "./keyboard/register.js";
import { advertisesKeys, submitLabel } from "./keyboard/bindings.js";
import { bannerRows, watchBannerRows } from "./banner-toolbar.js";
import { readPlace } from "./history.js";
import { readThreads } from "./thread/state.js";
import { watchProjection } from "./projection-watch.js";
import { threadAttention, workflowLabel } from "./thread/workflow.js";
import { threadSummary } from "./thread/model.js";
import { messageReading } from "./thread/messages.js";
import { declareThreadParts } from "./thread/focus.js";
import { dismissReply, replyAvailable } from "./thread/replies.js";
import {
  draftHasContent,
  loadDraft,
  mirrorDraft,
  saveDraft,
  sendMessage,
  tellDraft,
} from "./drafts.js";
import { textField } from "./composing/text-field.js";
import { draftOf, syncInput } from "./composing/input.js";
import { TEXT_FIELD } from "./control-selectors.js";
import { retainUserIntent } from "./user-intent.js";
import { queueItemKey, readQueues } from "./queue-api.js";
import { queueTitle } from "./queue-title.js";
import { askEnding } from "./asks/answer.js";
import { versionMenu, versionPicker } from "./version-picker.js";
import { versionsReading } from "./version.js";
import { UPGRADE } from "./presentation.js";
import { noticeReading, registerNoticePresentation } from "./notifications.js";
import { reducedMotion } from "./motion.js";
import { pagePresented } from "./page-paint.js";
import {
  focusDestination,
  focused,
  onStanding,
  onUserInput,
  rove,
  standingIn,
} from "./focus.js";
import { rowWalk } from "./walk-position.js";
import { sizeObserver } from "./rendering.js";
import { scrollIntoView } from "./landing-scroll.js";
import { declareOccluder, declareWindowChrome } from "./geometry.js";
import { agentName } from "./semantic-state.js";
import { runtime } from "./context.js";
import { renderedUnder } from "./shadow.js";
import { closestAcross } from "./passages.js";

const prefs = () => document.documentElement.lfChrome;
// The Codex panel's tween: one strong ease-out for every change of size and fade.
const EASE = "cubic-bezier(.23, 1, .32, 1)";
const RESIZE_MS = 300;
const FADE_MS = 180;
// The view leaving is gone before the one arriving shows, so the two never read
// through each other.
const OUT_MS = 80;

// The menu's groups, each opened as a view of the toolbar rows declaring it.
const GROUPS = Object.freeze({
  navigate: "Navigate",
  annotate: "Annotations",
  about: "About this page",
});
// Rows the panel draws as views of its own rather than pressing the native control.
const OWN_VIEWS = Object.freeze({
  threads: "threads",
  queue: "on",
  versions: "versions",
});
// Rows held elsewhere, so the menu and its groups leave them out: by the panel's row or
// its views, or, for picking an element to comment on, by the page itself, where
// selecting words or pressing `s` already starts it.
const FOLD = "panel.floating.fold";
const HELD_ELSEWHERE = Object.freeze([
  "threads",
  "queue",
  "page-comment",
  "approval",
  "keyboard",
  `command:${FOLD}`,
  "command:target.picker.open",
]);
// A row the menu or a group lists: neither held elsewhere nor the next step of a
// gesture, which stands in the counts' place instead.
const listed = (entry) => !entry.gesture && !HELD_ELSEWHERE.includes(entry.key);
// Where a row stands in the menu: in its group, and a keyboard's convenience (`keys`)
// under Navigate only where no keyboard is there to reach it, so a finger still can.
const groupOf = (entry) =>
  entry.group === "keys" && !advertisesKeys() ? "navigate" : entry.group;
const FILTERS = Object.freeze(["open", "unread", "drafts", "resolved"]);
// The views a thread is opened from.
const LISTS = Object.freeze(["threads", "on"]);
const capital = (word) => word[0].toUpperCase() + word.slice(1);
const coarse = () => matchMedia("(pointer: coarse)").matches;
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
  asks: askView,
  queueActions,
  withdraw,
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
  const contextDest = el("span", "lf-fp-dest");
  const contextKeys = el("span", "lf-fp-keys");
  context.append(contextDest, contextKeys);
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
  inner.append(opened, context, row);
  card.append(inner);
  // The menu and the peek stand over the leaf by anchoring to it, which they can only
  // do from after it in the tree.
  host.append(card, menu, badge, newsDot, peek);
  // The row stands over the window's foot as the bottom bar did, so what the page
  // reveals stands clear of it. A view opened above it is itself read, and stands over
  // the page only while it is used, so it leaves the page's room alone; but what it
  // stands over is hidden while it does, as under a side panel (`declareOccluder`).
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
  const quick = el("div", "lf-fp-quick");
  row.append(leaf, field, quick);

  const CONNECTING = { tone: "", summary: "Connecting…", explanation: "Connecting…" };
  const status = () => statusReading() ?? CONNECTING;
  // The trail of views open above the row, innermost last; empty at rest.
  let trail = [];
  let leaving = null;
  let menuOpen = false;
  let filter = "open";
  let query = "";
  let searching = false;
  let writing = false;
  // Whether the user is typing, as the row last showed it: Send in the counts' place.
  let typing = false;
  // The thread the reader lands at the end of, once Leaf has drawn more than `after`
  // of its messages: the whole of it on opening, or past the turn the user just sent.
  let landAtEnd = null;

  // ---------- one native editor per destination ----------
  // The draft the field writes: the open thread's reply, or the page's comment.
  const destination = () => {
    const top = trail.at(-1);
    return top?.view === "thread"
      ? `reply:${threadByKey(top.thread)?.key ?? top.thread}`
      : "general";
  };
  // What the empty field says, and whose reading it is (`says`): a passing notice while
  // one stands; a resolved thread's way back; once the caret is in the field, where
  // the words go; else on the page what the agent is doing or wants, in the banner's
  // words, and in a thread whose turn it is.
  function fieldReading(key, input) {
    const notice = noticeReading();
    if (notice.visible) return { says: "notice", words: notice.message };
    const thread = key ? threadByKey(key) : null;
    if (thread?.resolved) return { says: "turn", words: "Resolved · reopen to reply" };
    if (input === focused()) return { says: "destination", words: whereTo(key) };
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
    input.value = loadDraft("general") ?? "";
    const sync = wireInput(input, {
      hint: () => fieldReading(null, input).words,
      accessibleName: "Comment on the page",
      sends: "send",
      sendBtn: send,
      save: (text) => {
        saveDraft("general", text);
        tellDraft("general", text);
        retype();
      },
      send: (_text, raw, owns) => {
        const handle = sendMessage(
          "general",
          owns,
          (attempt) => threadActions.create({ attempt, text: raw })?.delivery,
        );
        if (!handle) return;
        // The box empties as the send leaves; the row reads it again once it has.
        queueMicrotask(paint);
        // A page comment starts a thread, keyed by the attempt that sent it, which the
        // panel opens so its reply follows in the same field.
        open({ view: "thread", thread: handle.attempt }, { replace: true });
      },
    });
    sync();
    // Resume writing (`g i`) comes back to the page's words here, in the panel.
    mirrorDraft(input, sync, "general", {
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
        hint: () => fieldReading(key, replyInput()).words,
        accessibleName: () => `Reply to ${threadTitle(key)}`,
        sent: () => {
          landAtEnd = { key, after: outletOf()?.childElementCount ?? 0 };
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
  const threads = () => {
    const reading = readThreads();
    return reading.phase === "ready" ? reading.threads : [];
  };
  const threadByKey = (key) =>
    threads().find((thread) => thread.key === key || thread.id === key) ?? null;
  const threadTitle = (key) => {
    const thread = threadByKey(key);
    return thread ? threadSummary(thread).topic : "this thread";
  };
  const unread = (thread) => thread.unread.length > 0;
  const newCount = () => threads().filter(unread).length;
  const openCount = () => threads().filter((thread) => !thread.resolved).length;
  const onUserCount = () => {
    const queues = readQueues();
    return queues.phase === "ready" ? queues.on_user.length : 0;
  };
  const threadStatus = (thread) => {
    const words = [
      thread.resolved ? "Resolved" : (threadAttention(thread)?.label ?? "Open"),
    ];
    if (draftHasContent(`reply:${thread.key}`)) words.push("Draft");
    return words.join(" · ");
  };
  const rows = () => bannerRows();

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
      on: "On",
      versions: "Versions",
      thread: route.thread ? threadTitle(route.thread) : "",
      group: GROUPS[route.group],
    })[route.view];
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
      openInPackage(route.thread);
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
  function writeOnPage() {
    const before = trail.at(-1);
    if (prefs().rest === "mark") prefs().set("rest", "row");
    trail = [];
    setMenu(false);
    transition(before);
    focusDestination(pageEditor().input, "move");
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
    paint();
  }

  // ---------- motion: the surface follows the box ----------
  // The box's layout changes in one step, whatever changed it: a view opening, the line
  // naming where the words go, a field growing a line, folding to the leaf. The surface
  // then follows from the outline it stood at to the box's new one by a clip, which
  // moves nothing's layout; while the box grows, its own contents are clipped to the
  // same outline, so they appear as the surface reaches them. The first outline, and
  // any under reduced motion, is taken as it is.
  let outline = null;
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
    for (const [layer, grow] of [
      [ring, 1],
      [fill, 0],
    ]) {
      const from = was ? getComputedStyle(layer).clipPath : null;
      for (const running of layer.getAnimations()) running.cancel();
      keeps(layer, "style", `clip-path: ${outlineClip(next, grow)}`);
      if (!was || reducedMotion() || !pagePresented()) continue;
      layer.animate([{ clipPath: from }, { clipPath: outlineClip(next, grow) }], {
        duration: RESIZE_MS,
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
      { duration: RESIZE_MS, easing: EASE },
    );
  }
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
  const rooms = new Map();
  function holdRoom() {
    const top = trail.at(-1);
    if (!top || top.view === "thread" || rooms.has(routeKey(top))) return false;
    const view = stage.querySelector(".lf-fp-view:not([data-leaving])");
    if (!view || view.querySelector(".lf-fp-asked:empty")) return false;
    rooms.set(routeKey(top), view.offsetHeight);
    return true;
  }
  function transition(before, { focus = true } = {}) {
    const after = trail.at(-1);
    const reading = [before, after].some((route) => route?.view === "thread");
    if (after?.view !== "on") {
      seated = null;
      seatHeights.clear();
    }
    const changed =
      (before ? routeKey(before) : null) !== (after ? routeKey(after) : null);
    if (changed) rooms.clear();
    // Taking the panel away from a thread ends the editing session of its reply, as a
    // press elsewhere does (thread/replies.js), keeping the draft: the field no longer
    // draws that reply, and a session left standing would carry the user back to it.
    if (changed && before?.view === "thread")
      dismissReply(threadByKey(before.thread)?.key ?? before.thread);
    // The view going away fades where it stood, closing included, so the box shrinking
    // under it never shows an empty ground.
    leaving = changed && before && after ? before : null;
    paint();
    // The reader draws what the view arriving holds, and lets go of what the one
    // leaving held: a thread's messages, or the asks On shows as messages.
    const drawn =
      reading || before?.view === "on" ? present({ release: reading }) : null;
    if (!changed || reducedMotion() || !pagePresented()) {
      leaving = null;
      paint();
      if (focus) focusView(after, drawn);
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
    if (focus) focusView(after, drawn);
  }
  function focusView(route, drawn) {
    if (!route) return;
    const view = stage.querySelector(".lf-fp-view:not([data-leaving])");
    // A thread opens with the caret in its reply, as the one field means, once Leaf's
    // reader has drawn the reply there; a list a key opened stands on its first
    // control; one a pointer opened holds focus itself.
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
    const target = keyed ? view?.querySelector("button, input") : view;
    if (target) focusDestination(target, "move");
  }

  // Whether the gesture now under way came from the keyboard: a key arriving in a view
  // stands on its first control, a pointer in the view itself, with no ring drawn.
  let keyed = false;
  onUserInput((event) => {
    if (
      ["keydown", "pointerdown"].includes(event.type) &&
      event.composedPath().includes(host)
    )
      keyed = event.type === "keydown";
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
    } = {},
  ) =>
    html`<button
      type="button"
      role=${role ?? nothing}
      data-row=${row ?? nothing}
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
  // A row's end says its value, then its shortcut where a keyboard is there to press it.
  const rowEnd = (entry) =>
    html`${entry.value ? html`<span class="lf-fp-value">${entry.value}</span>` : nothing}${
      entry.shortcut && advertisesKeys()
        ? html`<kbd class="lf-fp-key">${entry.shortcut}</kbd>`
        : nothing
    }`;
  function rowFor(entry) {
    const view = OWN_VIEWS[entry.key];
    return menuItem(
      entry.label,
      rowEnd(entry),
      () => {
        if (view) {
          open({ view });
          return;
        }
        putAwayThen(() => entry.press(heldStanding));
      },
      {
        urgent: Boolean(entry.urgent),
        disabled: entry.disabled,
        role: menuOpen ? "menuitem" : null,
        row: entry.key,
        opens: Boolean(view),
      },
    );
  }
  function menuTemplate() {
    const all = rows();
    // The panel's own views lead, in the order the user reaches for them; the rest of
    // the page's rows follow in the toolbar's order.
    const lead = Object.keys(OWN_VIEWS);
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
    // The state in a word over its one line, and the whole of it under that, which the
    // banner's disclosure gave: the menu is reached by pointer, key and finger alike.
    const word = TONE_WORDS[status().tone];
    const explanation =
      status().explanation && status().explanation !== status().summary
        ? status().explanation
        : null;
    return html`<div
        class="lf-fp-state"
        role="none"
        data-tone=${status().tone || nothing}
      >
        <b>${word ?? status().summary}</b>${
          word ? html`<span>${status().summary}</span>` : nothing
        }${explanation ? html`<span class="lf-fp-explain">${explanation}</span>` : nothing}
      </div>
      ${page.map(rowFor)}
      ${groups.map((group) =>
        menuItem(
          GROUPS[group],
          groupValue(group)
            ? html`<span class="lf-fp-value">${groupValue(group)}</span>`
            : nothing,
          () => open({ view: "group", group }),
          { opens: true },
        ),
      )}
      <hr />
      ${keyboard ? rowFor(keyboard) : nothing} ${fold ? rowFor(fold) : nothing}`;
  }
  const groupValue = (group) =>
    group === "annotate"
      ? rows().find((entry) => entry.key === "command:annotations.toggle")?.label ===
        "Show annotations"
        ? "Hidden"
        : ""
      : "";

  // ---------- views ----------
  function groupView(group) {
    return html`<div class="lf-fp-list">
      ${rows()
        .filter((entry) => groupOf(entry) === group && listed(entry))
        .map((entry) => (entry.copies ? copyRow(entry) : rowFor(entry)))}
    </div>`;
  }
  // A row whose press copies a text, such as the share link, shows that text for the
  // user to select as well, with its press beside it, since a browser offers the
  // clipboard only to a secure context (https or localhost) and may refuse a write; the
  // view stays open across the press, so the text is still there if the copy failed.
  // Its value, which a one-line row would end with, says beneath it what the text is.
  // A text of several lines, such as a preview's diagnostics, shows its first few, and
  // selecting it takes the whole.
  function copyRow(entry) {
    const field = `lf-fp-copy-${entry.key}`;
    return html`<div class="lf-fp-copy">
      <label class="lf-fp-copy-label" for=${field}>${entry.label}</label>
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
      ><button
        type="button"
        class="lf-fp-quiet"
        ?disabled=${entry.disabled}
        @click=${() => entry.press(heldStanding)}
      >
        Copy
      </button>
      ${entry.value ? html`<p class="lf-fp-copy-note">${entry.value}</p>` : nothing}
    </div>`;
  }

  // The versions the picker lists, the one shown marked, each a press that travels
  // there, with Compare where the picker offers it; then the version's approval, where
  // the page asks for one, with why a press would not approve yet.
  function versionsView() {
    const { rows: versions, picker, selection } = versionsReading();
    const approval = approvalReading();
    const approved = approval?.text.startsWith("✓");
    return html`<div class="lf-fp-list">
      ${repeat(
        versions,
        (entry) => `${entry.version === null ? "draft" : "version"}:${entry.revision}`,
        (entry) =>
          html`<div class="lf-fp-version" ?data-current=${entry.current}>
            ${menuItem(
              entry.name,
              entry.current ? html`<span class="lf-fp-value">Showing</span>` : nothing,
              () => putAwayThen(() => versionPicker.activate(entry)),
              { role: null },
            )}${
              entry.comparable
                ? html`<button
                    type="button"
                    class="lf-fp-quiet lf-fp-compare"
                    aria-pressed=${String(selection.on && selection.base === entry.version)}
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
      ${versions.length ? nothing : html`<p class="lf-fp-empty">${picker.token}</p>`}
      ${
        approval
          ? html`<hr />
              <div class="lf-fp-approval" title=${approval.reason ?? nothing}>
                ${menuItem(
                  approval.text,
                  approval.reason
                    ? html`<span class="lf-fp-value">${approval.reason}</span>`
                    : nothing,
                  () => approve(),
                  { disabled: Boolean(approval.reason) && !approved, role: null },
                )}
              </div>`
          : nothing
      }
    </div>`;
  }

  function shownThreads() {
    const words = query.trim().toLowerCase();
    return threads().filter((thread) => {
      if (words) {
        const text = [
          threadSummary(thread).topic,
          ...thread.msgs.map((m) => m.text ?? ""),
        ]
          .join(" ")
          .toLowerCase();
        return text.includes(words);
      }
      if (filter === "unread") return unread(thread);
      if (filter === "drafts") return draftHasContent(`reply:${thread.key}`);
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
                  ?data-unread=${unread(thread)}
                  ?data-resolved=${thread.resolved}
                  ?data-yours=${threadAttention(thread)?.kind === "needs_user"}
                  @click=${() => open({ view: "thread", thread: thread.key })}
                >
                  <span class="lf-fp-news-mark" aria-hidden="true"></span>
                  <span class="lf-fp-label">${threadSummary(thread).topic}</span>
                  <span class="lf-fp-value"
                    >${unread(thread) ? "New · " : ""}${threadStatus(thread)}</span
                  >
                </button>`,
            )
          : html`<p class="lf-fp-empty">${empty}</p>`
      }
    </div>`;
  }

  // A thread inside the panel is drawn by Leaf's own conversation reader: the panel
  // registers as the page's primary thread presentation (application.js,
  // `registerChromeThreadPresentation`), yielding to one the page's package registers, in
  // whose reader its threads then open, and gives the open thread's messages an outlet
  // here. Leaf draws each message there, with its reactions, rewrites, read marks and
  // agent-authored widgets, and holds news that would move what the reader is reading
  // behind its own notice. The reply is the thread's reply box, which the reader draws
  // in the field below rather than in the outlet. A thread anchored to a passage stays
  // the page's: its card opens beside the words it is about.
  let presentation = null;
  const openView = () =>
    stage.querySelector('.lf-fp-view[data-view="thread"]:not([data-leaving])');
  const outletOf = () => openView()?.querySelector(".lf-fp-outlet") ?? null;
  function nominate(collection, parts) {
    const top = trail.at(-1);
    // On draws each prose ask as its message, in its card's outlet.
    if (top?.view === "on") {
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
      view.dataset.thread === thread.id
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

  function threadView(key) {
    const thread = threadByKey(key);
    if (!thread)
      return html`<p class="lf-fp-empty">This thread is not on the page.</p>`;
    return html`<div class="lf-fp-messages lf-fp-outlet"></div>`;
  }

  // ---------- On: asks answered where they are read ----------
  // The three lists are the publisher's (`readQueues`): what waits on the user, on the
  // agent, and what is done. An item the user answers here stays where it stood, saying
  // its answer and offering Undo, until the view closes, so answering one ask never
  // carries the next under the pointer.
  let queueTab = "you";
  let seated = null; // queue item keys present in the open On view
  // The height each seated card first stood at, which it keeps while seated, so an
  // answer that shortens it moves nothing below.
  const seatHeights = new Map();
  const QUEUE_TABS = Object.freeze({
    you: "On me",
    agent: "On the agent",
    done: "Done",
  });
  const queueLists = () => {
    const reading = readQueues();
    return reading.phase === "ready"
      ? { you: reading.on_user, agent: reading.on_agent, done: reading.done }
      : { you: [], agent: [], done: [] };
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
  const tabLabel = (tab) => (tab === "agent" ? `On ${agentName()}` : QUEUE_TABS[tab]);

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
      ? (thread.title ??
        (thread.root.id === message.id ? "" : threadSummary(thread).topic))
      : asking
        ? threadSummary(thread).topic
        : queueTitle(item);
    const said = message
      ? ""
      : asking
        ? messageReading(asking, { panel: false, reactions: [], workflows: [] }).body
            .plainText
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
    if (list !== "you" && !answered)
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
      tabindex=${approval ? "-1" : nothing}
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

  // The version's approval is answered here, in the banner control's place: arriving at
  // it, as `m` and an On panel row do, opens this view on its card and stands on its
  // Approve, or once it is answered on its Undo, or the card itself.
  const approvalControl = () => {
    const card = stage.querySelector(".lf-fp-view:not([data-leaving]) [data-approval]");
    return card?.querySelector("button") ?? card;
  };
  function arriveAtApproval() {
    const lists = queueLists();
    const holding = (list) =>
      list.some((item) => item.kind === "ask" && item.ask.source.kind === "approval");
    const tab = Object.keys(QUEUE_TABS).find((key) => holding(lists[key])) ?? "you";
    if (tab !== queueTab) {
      queueTab = tab;
      seated = null;
      seatHeights.clear();
    }
    open({ view: "on" }, { reopen: true, focus: false });
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
    const items = seated.map((key) => byKey.get(key));
    return items.length
      ? repeat(items, queueItemKey, (item) =>
          onItemCard(
            item,
            lists.you.includes(item)
              ? "you"
              : lists.agent.includes(item)
                ? "agent"
                : "done",
          ),
        )
      : html`<p class="lf-fp-empty">
          ${
            {
              you: "Nothing waiting on me.",
              agent: `Nothing waiting on ${agentName()}.`,
              done: "Nothing is done yet.",
            }[queueTab]
          }
        </p>`;
  }

  function viewTemplate(route) {
    switch (route.view) {
      case "threads":
        return threadsView();
      case "thread":
        return threadView(route.thread);
      case "on":
        return onView();
      case "versions":
        return versionsView();
      case "group":
        return groupView(route.group);
    }
    return nothing;
  }

  // ---------- the head: where the user is, at the view's top edge ----------
  const tabs = (names, current, label, choose) =>
    html`<div class="lf-fp-filters" role="group" aria-label="Show">
      ${names.map(
        (name) =>
          html`<button
            type="button"
            aria-pressed=${String(current === name)}
            @click=${() => choose(name)}
          >
            ${label(name)}
          </button>`,
      )}
    </div>`;
  // A tab's count keeps its room whether or not it has a number, so news changing it
  // moves no tab beside it.
  const tabCount = (count) => html` <span class="lf-fp-count">${count || ""}</span>`;
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
          (name) =>
            html`${capital(name)}${name === "unread" ? tabCount(news) : nothing}`,
          (name) => {
            filter = name;
            query = "";
            paint();
          },
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
    } else if (top.view === "on") {
      const lists = queueLists();
      aux = tabs(
        Object.keys(QUEUE_TABS),
        queueTab,
        (tab) =>
          html`${tabLabel(tab)}${tab === "done" ? nothing : tabCount(lists[tab].length)}`,
        (tab) => {
          queueTab = tab;
          seated = null;
          seatHeights.clear();
          paint();
        },
      );
    } else if (thread) {
      // Resolve says it is unavailable while a settling is pending rather than leaving
      // the tab order, so the user who pressed it, or `r` on it, stays standing on it;
      // the action itself refuses a press meanwhile (thread/actions.js, `settle`).
      // Resolving leaves the reply's editing place, as a card's Resolve does, keeping
      // its draft (thread/replies.js), so the thread shows its way back instead.
      aux = html`${
          thread.anchor
            ? html`<button
                type="button"
                class="lf-fp-quiet"
                @click=${() => {
                  close();
                  void threadActions.open(thread.key, { part: null });
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
            if (thread.resolved) return threadActions.reopen(thread.key);
            dismissReply(thread.key);
            return threadActions.resolve(thread.key);
          }}
        >
          ${thread.resolved ? "Reopen" : html`${iconTemplate("check", "lf-action-icon")}Resolve`}
        </button>`;
    }
    const openThreads = threads().filter((candidate) => !candidate.resolved);
    const at = thread ? openThreads.indexOf(thread) : -1;
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
            <h2 class="lf-fp-title">${titleOf(top)}</h2>
            ${
              at >= 0
                ? html`<span class="lf-fp-where"
                    >${at + 1} of ${openThreads.length}</span
                  >`
                : nothing
            }`;
    return html`<div class="lf-fp-crumb">${crumb}</div>
      <div class="lf-fp-aux">${aux}</div>
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
    prefs().set("rest", rest);
    trail = [];
    menuOpen = false;
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
      if (holdRoom()) paintNow();
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
    if (trail.at(-1)?.view !== "on") return;
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
    view.scrollTop = view.scrollHeight;
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
    paintPeek();

    // What waits on the user, which the folded leaf carries as a badge and a dot.
    const onUser = onUserCount();
    const news = newCount();
    keepsText(badge, onUser ? String(onUser) : "");
    keeps(badge, "data-shown", onUser ? "" : null);
    keeps(newsDot, "data-shown", news ? "" : null);

    render(menuOpen ? menuTemplate() : nothing, menu);
    if (menuOpen) {
      const rows = menuRows();
      rove(rows, rows.includes(focused()) ? focused() : rows[0]);
    }

    const views = [leaving, top].filter(Boolean);
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
            ${ref(declareView)}
            style=${
              rooms.has(routeKey(route))
                ? `height: ${rooms.get(routeKey(route))}px`
                : nothing
            }
            ?data-leaving=${route === leaving}
          >
            ${viewTemplate(route)}
          </div>`,
      ),
      stage,
    );
    render(top ? headTemplate(top) : nothing, head);
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
    // A resolved thread takes no reply: the field says how to reopen it instead.
    const resting = Boolean(thread) && !replyAvailable(thread);
    keepsHidden(resolvedLine, !resting);
    keepsHidden(replyOutlet, resting);
    const input = fieldInput();
    if (input) syncInput(input);
    const holds = Boolean(loadDraft(destination())?.trim());
    // Clicking in opens one quiet line above the field naming who the words go to; it
    // stays while the field holds words, and while a thread is open, whose field is
    // always its reply, so nothing moves when the caret leaves.
    const engaged = Boolean(thread) || writing || holds;
    keeps(host, "data-engaged", engaged ? "" : null);
    keeps(host, "data-writing", writing ? "" : null);
    // While the user types, Send stands in the counts' place.
    typing = writing && Boolean(draftOf(input).trim());
    keeps(host, "data-typing", typing ? "" : null);
    // Whose reading the empty field says, which its face follows: a status dims, and
    // carries the sheen while the agent works.
    const reading = fieldReading(replying ? top.thread : null, input);
    keeps(host, "data-says", reading.says);
    keeps(host, "data-tone", status().tone || null);
    // A passing notice is said where the field's placeholder would be; once the field
    // holds words, which hide that, it stands on this line instead, as a refused send's
    // reason does over the words it returned. Where the words go is said once: by the
    // empty focused field's placeholder, and once words hide that, here, the way a
    // field's label rises above what is written in it.
    const empty = draftOf(input) === "";
    const covered = reading.says === "notice" && !empty;
    const recipient = agentName();
    const where = thread ? `Reply in ${threadSummary(thread).topic}` : whereTo(null);
    keeps(contextDest, "data-notice", covered ? "" : null);
    keepsText(
      contextDest,
      covered
        ? reading.words
        : reading.says === "destination" && empty
          ? `To ${recipient}`
          : `${where} · to ${recipient}`,
    );
    keepsText(
      contextKeys,
      advertisesKeys()
        ? `${submitLabel()} to send${submitLabel() === "⏎" ? " · ⇧⏎ new line" : ""}`
        : "",
    );
    keepsHidden(context, !engaged);

    // The next step of what the user is doing now, such as leaving Draw mode or
    // commenting on the words a finger selected, stands in the counts' place while that
    // gesture holds it, as it stands on the banner's row (banner-toolbar.js, `gesture`).
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
    const threadsOpen = top?.view === "threads" || top?.view === "thread";
    render(
      html`<button
          type="button"
          class="lf-fp-chip lf-fp-on-user"
          aria-pressed=${String(top?.view === "on")}
          ?data-due=${onUser > 0}
          aria-label=${onUser ? `On me: ${onUser}` : "On me"}
          @click=${() => open({ view: "on" })}
        >
          ${iconTemplate("question", "lf-action-icon")}<span class="lf-fp-num"
            >${onUser || ""}</span
          ></button
        ><button
          type="button"
          class="lf-fp-chip lf-fp-threads"
          aria-pressed=${String(threadsOpen)}
          aria-label=${`Threads, ${openCount()} open${news ? `, ${news} with news` : ""}`}
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

  // ---------- gestures ----------
  // The leaf unfolds a folded panel, and otherwise opens or closes its menu.
  leaf.addEventListener("click", () => {
    if (host.dataset.rest === "mark") {
      prefs().set("rest", "row");
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
  function paintPeek() {
    const folded = host.dataset.rest === "mark";
    const notice = noticeReading();
    const telling = folded && notice.visible;
    keepsText(peek, telling ? notice.message : status().explanation || status().summary);
    keeps(peek, "data-shown", folded && (peekAsked || telling) ? "" : null);
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
      out: () => {
        close();
        focusDestination(leaf, "return");
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
  // A press on the page puts away what stands open above the row.
  document.addEventListener(
    "pointerdown",
    (event) => {
      if (event.composedPath().includes(host)) return;
      if (menuOpen) setMenu(false);
      if (trail.length) close();
    },
    true,
  );

  // The Threads and On me doors are the banner's controls, which every route to
  // those surfaces presses, Go-to's included. In this chrome the panel stands for
  // them, so their press opens its view instead.
  for (const [door, view] of [
    [toggleBtn, "threads"],
    [queueBtn, "on"],
  ])
    door.addEventListener(
      "click",
      (event) => {
        event.stopImmediatePropagation();
        event.preventDefault();
        if (view === "threads") {
          filter = "open";
          query = "";
        }
        open({ view });
      },
      { capture: true },
    );

  // Version travel (`g V`, the picker's own press) opens the versions menu, whichever
  // route asks; in this chrome that opening is the panel's Versions view.
  versionMenu.addEventListener("beforetoggle", (event) => {
    if (event.newState !== "open") return;
    event.preventDefault();
    open({ view: "versions" }, { reopen: true });
  });

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

  function mount(parent) {
    parent.append(ground, host);
    follow.observe(card);
    presentation = registerChromeThreadPresentation(host, {
      render: nominate,
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
      // A thread about the whole page opens here; one about a passage opens beside it.
      // Where the user lands in it is the route's (`request.part`), which Leaf's
      // destinations take them to once it is drawn: the reply, a message, or the
      // thread itself, the view, where the `t` walk goes on from.
      reveal: (key) => {
        const thread = threadByKey(key);
        if (!thread || thread.anchor) return false;
        open({ view: "thread", thread: thread.key }, { reopen: true, focus: false });
        return present({ release: true });
      },
    });
    // Upgrade turns the status to its loading words without a publication.
    document.addEventListener(UPGRADE, () => paint(), { once: true });
    registerApprovalPresentation({ target: approvalControl, arrive: arriveAtApproval });
    // A passing notice is said in the empty field, the one seat this chrome gives it.
    registerNoticePresentation(() => paint());
    watchBannerRows(() => paint());
    // A comparison started or stopped changes the versions without a publication.
    versionPicker.watch(() => paint());
    document.addEventListener("lf-chrome-preference", () => paint());
    watching = watchProjection(host, paintPanel);
    paint();
  }

  return { host, mount, open, close, pageComment };
}
