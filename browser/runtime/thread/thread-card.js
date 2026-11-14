/* One synchronous Lit owner for complete page, outlet and margin threads, and for the
   floating panel's view of a thread: every surface that draws a thread draws it here.

   Every surface uses the same metadata, transcript, message and reply vocabulary.
   Containers own navigation and placement, including whether their transcript scrolls;
   shadow.css owns the conversation's appearance through widget shadow boundaries.
   Conversation flow stays inside a content region, separate from the outer body's
   retained reply space, except where a container's head line shares the transcript's
   tracks (`CardOutlets`, `line`). Thread controls stay outside message and
   summary folds. MessageView owns each complete message, so no container extracts or
   reparents its header.
   Where the container gives no head line, independent controls stand on the first
   header line, in the room the line keeps at its end, and a held-news notice stands on
   the same line after the header's words, each a box of its own anchored to the
   header, so no box stands over the words. That line reserves a notice's minimum hit
   area from its first paint; the metadata edge measured before news arrives is
   retained while it waits, including when its workflow receipt goes.
   Each message header text item keeps its allocated width while news waits, so a later
   receipt grows only inside its own clipped box. The first notice may use spare
   room for its new receipt without moving the author or time already shown.

   Each container says where the parts of the thread it holds stand, and how a send and
   a settlement land there (`ViewOutlets`): the floating panel gives the notice and the
   settlement places on its view's head line, which stands outside the view that
   scrolls, and the reply box the row's field, and asks for the words the thread is
   about over its messages, since nothing beside it shows them; a margin card stands the
   notice and the settlement on its row of presses, which stands in the thread over its
   first message's head. The thread draws each of them there, so the panel's view and a
   card share one notice, one settlement and one reply box. The card tried a head line
   above its messages and dropped it: the line made the card 36px taller for little more
   than its presses, which cost the card too much density. A title could fill the line,
   but the passage the card points at already says what the thread is about, so the card
   draws no quote either.

   Immutable descriptors contain generated presentation only. Retained native editors,
   a container's places and presses, and frozen message widgets keep their mechanical
   lifetime outside those values. The card draws its messages as every reader of a
   whole thread does, folds and working message included (transcript.js), around them
   its head's controls and its reply box. The owner alone renders its native card root,
   the boxes it draws apart, and all generated descendants; a failed candidate is
   restored by presenting its committed descriptor again. It owns title gesture policy,
   outgoing fold paint and local draft repaint. Surfaces receive whole-thread geometry
   readings rather than descendant nodes. It decides nothing by the reading's surface,
   which read tracking reports (transcript.js) and which ranks where a message's
   authored widgets stand (`threadReading`).

   A container whose head line holds a place for it offers Next unread there, which
   goes to the thread's first reply not yet read, a fold or the scroller's edge perhaps
   hiding it, as `g u` goes to the page's (read.js). Whether this opening of the thread
   offers it is decided once the container has landed the opening and a pass of read
   tracking has read what it shows whole (`settled`): it does where a reply still stands
   unread. Once none is left the press is unoffered and its seat stands, so reading
   moves nothing beside it; a margin card draws nothing instead, since nothing on its
   line moves for the press (annotation-chrome.css). Until then, and where every reply
   showed whole, nothing stands there. Replies arriving later need none: New reply leads to one
   the user waits for, and the thread's notice to news it holds. Rejected: deciding as
   the view first drew, which offered Next unread for the moment before the opening read
   a short reply.

   A container whose box scrolls the thread's messages names that box (`ThreadOutlets`,
   `scroller`): the floating panel's view, a margin card's capped transcript. It owns
   the box and the edge it holds still, and says when the box stands at its size
   (`settled`). The agent's answer to the user's own last turn, work under way and a
   reply streaming included, may then have arrived past the box's foot. Where the user
   stood at the box's end and their turn and the answer together fit in the box, its end
   follows the answer into sight. Otherwise New reply stands at the box's foot until a
   press on it, or the user scrolling there, shows the answer, or they send another turn,
   and a user who stood at the end keeps their turn wholly in sight above the press, its
   head included. A user whose wheel or key has the box scrolling as the answer arrives
   stands wherever that scroll takes them, though the browser has yet to move the box
   (arrivals.js, `readerScrolls`). Until then the answer is this thread's to place
   (`answering`), and a box that follows its end, as a card's transcript does
   (thread-preview.js), leaves it be. An answer the end followed into sight that grows afterwards, as a picture in it
   loads, is placed again by the same rule (`placesEnd`). The user chose New reply for
   the panel on 14 October 2026, and the rest of the floating panel's growth with it
   (floating-panel.js, which records it); the margin card gained it on 4 November, so
   one mechanism serves both, and that mechanism's rule at its end, under the user's
   request for one thread view (thread-preview.js). */
import { REOPEN_HINT, REPLY_HINT } from "../words.js";
import { nextRender, sizeObserver } from "../rendering.js";
import {
  holdFocus,
  focusDestination,
  focused,
  currentLocationTouches,
  currentLocationIn,
} from "../focus.js";
import {
  effect,
  html,
  nothing,
  ref,
  render,
  share,
  signal,
  untracked,
} from "/runtime/framework.js";
import { randomId } from "../ids.js";
import { turns, threadKey } from "./model.js";
import {
  anchorPlace,
  messageReading,
  threadPassage,
  threadSummary,
} from "./messages.js";
import { generatedElement, offeredAction } from "../widget-elements.js";
import { contentsBox, measure } from "../shown-box.js";
import { keeps, keepsHidden, layoutPx, roomPx } from "../keeps.js";
import { commandsOn } from "../keyboard/scopes.js";
import { PRESS } from "../keyboard/bindings.js";
import {
  createReplyView,
  replyIsEditing,
  dismissReply,
  threadHoldsDraft,
} from "./replies.js";
import {
  moveScrollerBy,
  SCROLL_SLACK,
  scrollLimit,
  scrollToEnd,
} from "../scrolling.js";
import { browserScrolls, readerScrolls } from "../arrivals.js";
import { scrollIntoView } from "../landing-scroll.js";
import { renderedOrder } from "../shadow.js";
import { iconTemplate } from "../icons.js";
import { threadNamed } from "./state.js";
import { settleThread } from "./folding.js";
import { answeredInWords } from "../obligations/model.js";
import { SAY_BOX, wholeThread } from "./selectors.js";
import {
  threadAttention,
  inHand,
  todoWord,
  workflowWord,
  hasWorkflowLine,
} from "./workflow.js";
import { leafSays, voiced } from "../voice.js";
import { agentName, documentChanged } from "../semantic-state.js";
import { growthIsSeen, shownRect } from "../geometry.js";
import { ago, shortAgo } from "../presence.js";
import { retainUserIntent } from "../user-intent.js";
import { scrollThreadIntoView, pinnedReply } from "./reply-landing.js";
import { threadRewrites } from "./message-edit.js";
import { authoredTitle } from "../tab-title.js";
import { NEWS_ROOM, newsNotice, threadChange } from "./held-news.js";
import { ReplyContinuity } from "./reply-continuity.js";
import { Transcript } from "./transcript.js";
import { partTrail } from "./placement.js";
import { addressableLabel } from "../addressable-names.js";

/** @typedef {import("../framework/snapshot.js").Immutable<ReturnType<typeof import("./model.js").readThreadRecords>[number]>} ThreadRecord */
/** @typedef {ReturnType<typeof messageReading>} MessageReading */
/** @typedef {{who: string, position: number, timestamp: string | null,
 * age: string | null, words: string, feedback: {
 * input_id?: string, reply_id: string | null, attempt?: string | null,
 * reply_kind: "work" | "progress"} | null,
 * live: boolean, condition: import("../voice.js").Said | null}} WorkingMessage */
/** @typedef {{key: string, summary: ReturnType<typeof threadSummary>,
 * recency: {short: string, long: string} | null,
 * id: string, attempt: string | null, surface: string, resolved: boolean,
 * attention: ReturnType<typeof threadAttention>, resolvedBy: string,
 * settlement: {kind: "resolve" | "unresolve", word: string, label: string},
 * summaries: ThreadRecord["summaries"],
 * messages: readonly MessageReading[], working: WorkingMessage | null,
 * source: ThreadRecord, reread: (held: ThreadRecord) => ThreadReading}} ThreadReading */

// What a thread says of the words it is about: where they stand, the words, whether they
// still stand on the page, and a status word, in Leaf's voice, where the page no longer
// reads as the quote does: a revision took the words out of the latest version, which
// may not be the version shown, where they can still stand; they can't be found on the
// page; they come from earlier data; or they have changed. A thread draws it where its
// container asks (`ThreadOutlets`, `quote`), as the floating panel's view does. The
// status is a word over the quote because a finger never reads a title. Where the words
// still stand, `trail` names the headings over them (`partTrail`), else the page's
// title, where no heading stands over them: a label of quoted words with no place of
// their own, and the head's title for any other.
/** @param {ThreadRecord} thread
 * @param {Pick<ReturnType<typeof import("../anchor-placement.js").createAnchorPlacement>, "placedAt">} anchors */
function quoteReading(thread, anchors) {
  const placement = anchors.placedAt(thread.id);
  const quoted = threadPassage(thread);
  const place = anchorPlace(quoted, thread.root.about);
  const words = quoted?.quote ?? "";
  if (!place && !words) return null;
  const anchored = Boolean(thread.anchor) || Boolean(thread.detached_from);
  const detached = anchored && (Boolean(thread.detached_from) || placement == null);
  // A version that rewrote the quoted words left the thread on their section
  // (`rewritten_from`, events.md); the head still names those words, marked as changed.
  const changed =
    Boolean(thread.rewritten_from) ||
    Boolean(words && placement?.datumElement && !placement.exact);
  return Object.freeze({
    place,
    words,
    detached,
    status: detached
      ? leafSays(thread.detached_from ? "Not in the latest version" : "Not found")
      : anchored && placement?.status === "outdated"
        ? leafSays("Earlier data")
        : changed
          ? leafSays("Changed")
          : null,
    // A surviving element can still be a destination after its quoted words
    // have gone (rewritten text, replaced data or a virtual datum). Only a
    // resolved passage can supply the original quote's complete reading.
    localReading: Boolean(words) && placement?.kind !== "passage",
    trail:
      !detached && placement?.place
        ? partTrail(placement.place)
            .map(addressableLabel)
            .filter(Boolean)
            .join(" › ") || authoredTitle()
        : "",
  });
}

// The thread's working message: what the agent is doing about the work it has in hand
// here, while no answer has come. Its words are the line the agent last gave for that
// work, which is the request's state (a start, `todos.py`), so they agree with the
// page's status and the agent's On count. The work is read from the thread's workflows
// and to-dos, not from whose turn the thread is, since the agent can be working on one
// message while an obligation in the same thread waits on the user. A message's work speaks before a to-do's, and
// a proactive progress message, which takes no request in hand, gives its own words.
// `live` while the work runs; work whose turn ended or went stale without an answer
// says so beside its last line. The progress messages behind it are gathered by
// `withPendingProgress`. It stands where those words were said, after `after`, the
// original log position (`workingPlace`): as the face of the progress run
// it follows, or as a face of its own (transcript.js). An answer already
// streaming at the thread's end replaces the working message and pending progress.
const STOPPED = new Set(["stopped", "quiet", "interrupted"]);
// A progress run's face (transcript.js), the working message among them, standing for
// the work under way where a thread reads the answer to the user's turn (`#fitAnswer`);
// and the key each is drawn under there, by the run it faces.
const WORKING = ".lf-thread-working";
const FACE = "face:";
// A first header's words, which a held-news notice stands after: everything it holds
// but the message's own controls at its end.
/** @param {HTMLElement} header @returns {HTMLElement[]} */
const words = (header) => {
  /** @type {NodeListOf<HTMLElement>} */
  const children = header.querySelectorAll(":scope > :not(.lf-msg-control-room)");
  return [...children];
};
/** @param {ThreadRecord} thread @param {readonly MessageReading[]} messages @returns {WorkingMessage | null} */
function workingMessage(thread, messages) {
  if (thread.resolved || messages.at(-1)?.provisional) return null;
  const covered = new Set(thread.summaries.flatMap(({ covers }) => covers));
  const pending = messages.filter(
    (message) => message.progress && !covered.has(message.id),
  );
  const lastProgress = pending.at(-1);
  const workflows = thread.workflows;
  const running = workflows.find(inHand);
  const runningLine = running && hasWorkflowLine(running) ? running : null;
  const stopped = workflows.find(
    /** @returns {workflow is Extract<import("../framework/application.js").Workflow, {detail: string}>} */
    (workflow) =>
      workflow.state === "blocked" &&
      workflow.reason !== null &&
      STOPPED.has(workflow.reason) &&
      Boolean(workflow.detail),
  );
  // The line of the start on a to-do of the agent's on the thread: one running, else
  // one that stopped or went quiet, which keeps the line it last said.
  const todos = thread.obligations.filter((item) => item.source.kind === "todo");
  const todo = todos.find(inHand)?.line ?? null;
  const stoppedTodo =
    todos.find((item) => item.state === "blocked" && item.line) ?? null;
  /** @typedef {{words: string, position: number, live: boolean,
   * condition: import("../voice.js").Said | null, agent: string | null | undefined}} Step */
  /** @type {Step | null} */
  const progressStep = lastProgress
    ? {
        words: lastProgress.body.plainText,
        position: lastProgress.sequence,
        live: Boolean(running),
        condition: null,
        agent: running?.agent,
      }
    : null;
  /** @type {Step | null} */
  const step = runningLine?.detail
    ? {
        words: runningLine.detail,
        position: runningLine.detail_seq,
        live: true,
        condition: null,
        agent: runningLine.agent,
      }
    : running
      ? progressStep
      : todo
        ? {
            words: todo.text,
            position: todo.seq,
            live: true,
            condition: null,
            agent: null,
          }
        : stopped
          ? {
              words: stopped.detail,
              position: stopped.detail_seq,
              live: false,
              condition: workflowWord(stopped, agentName()),
              agent: stopped.agent,
            }
          : stoppedTodo?.line
            ? {
                words: stoppedTodo.line.text,
                position: stoppedTodo.line.seq,
                live: false,
                condition: todoWord(stoppedTodo),
                agent: null,
              }
            : progressStep;
  if (!step || !step.words || (!pending.length && !step.live && !step.condition))
    return null;
  const { words, position, live, condition, agent } = step;
  const agentMessage = messages.findLast((message) => message.author === "agent");
  // A workflow's detail is explicit agent work text linked to its exact input. A
  // to-do's line can be user-authored, so it supplies no reply visibility evidence.
  const work = runningLine?.detail ? runningLine : !running && !todo ? stopped : null;
  const progress =
    !work && (running || (!todo && !stopped && !stoppedTodo)) ? pending.at(-1) : null;
  // Date the words being shown, rather than another message or the workflow's
  // liveness condition. A to-do line has no dated source in the thread reading.
  const timestamp = work?.ts ?? progress?.timestamp ?? null;
  /** @type {WorkingMessage["feedback"]} */
  const feedback = work?.input
    ? {
        input_id: work.input,
        reply_id: null,
        reply_kind: "work",
      }
    : progress
      ? {
          reply_id: progress.id,
          attempt: progress.attempt,
          reply_kind: "progress",
        }
      : null;
  return Object.freeze({
    who: work?.agent || progress?.by || agent || agentMessage?.by || "Agent",
    position,
    timestamp,
    age: timestamp ? ago(timestamp) : null,
    words: words.trim().replace(/\.$/, ""),
    feedback,
    live,
    condition,
  });
}

/** @param {ThreadRecord} thread @param {string} surface
 * @param {{authoredRank?: number}} commands @returns {ThreadReading} */
export function threadReading(thread, surface, commands) {
  const resolved = Boolean(thread.resolved);
  // A settlement in flight has already flipped `resolved`, because what the page can
  // draw of a gesture stands in the turn that sends it. The control the user is left
  // looking at is therefore the opposite one, live at once: a press sends the opposite
  // settlement after the first, as the ledger orders them. A delivery status is not the
  // result, so there is no "Resolving…" state to name.
  const kind = resolved ? "unresolve" : "resolve";
  const word = resolved ? "Reopen" : "Resolve";
  const label = resolved ? word : "Resolve thread";
  const attention = threadAttention(thread, agentName());
  // An answer says what it leaves (an lf-ask, `--todo`); its head says so while that
  // stands: a question the user still owes words to, a to-do still open on the
  // thread.
  const asking = new Set(
    thread.obligations
      .filter((item) => item.next_actor === "user" && answeredInWords(item))
      .map((item) => item.message),
  );
  const openTodos = new Set(
    thread.obligations
      .filter((item) => item.source.kind === "todo" && item.state !== "done")
      .map(({ id }) => id),
  );
  /** @param {ThreadRecord["msgs"][number]} message */
  const leaves = (message) =>
    asking.has(message.id)
      ? leafSays("Waiting on me")
      : message.todo && openTodos.has(message.id)
        ? todoWord({ state: "waiting", reason: null })
        : null;
  // Completion comes from the server, including the provisional answer. A held
  // reading keeps progress until its completing reply is among the messages shown.
  const presented = new Set(thread.msgs.map(({ id }) => id));
  const messages = turns(thread)
    .filter(
      (message) =>
        message.completed_by === undefined || !presented.has(message.completed_by),
    )
    .map((message) =>
      messageReading(message, {
        // Where a message's widgets stand when several drawings show it (messages.js,
        // `authoredHolders`): the primary reader's, then a margin card, then a seat.
        authoredRank: commands.authoredRank ?? (surface === "margin" ? 2 : 1),
        workflows: message.workflows,
        leaves: leaves(message),
      }),
    );
  const summary = threadSummary(thread);
  return Object.freeze({
    key: threadKey(thread),
    summary,
    // How long ago the thread last moved, read here with the rest of the reading, so a
    // card whose reading did not change shows the same age and need not draw again.
    recency: summary.latest
      ? Object.freeze({ short: shortAgo(summary.latest), long: ago(summary.latest) })
      : null,
    id: thread.id,
    attempt: thread.root.attempt ?? null,
    surface,
    resolved,
    attention,
    // Where a resolved thread stands already says it is resolved: in a seat's Resolved
    // disclosure (inline.js). Who resolved it is said only where it was the agent, in
    // Reopen's name and the words the panel's field says for the thread, which a finger
    // reads where it never reads that name.
    resolvedBy:
      thread.resolved?.author === "agent" ? `Resolved by ${thread.resolved.agent}` : "",
    settlement: Object.freeze({
      kind,
      word,
      label,
    }),
    summaries: Object.freeze(thread.summaries),
    messages: Object.freeze(messages),
    working: workingMessage(thread, messages),
    // The thread this reads, and the same reading of another state of it: the one a
    // seat holding news draws, the thread as it drew it (held-news.js).
    source: thread,
    reread: (held) => threadReading(held, surface, commands),
  });
}

// The width `node`'s words take, at the fraction of a pixel they are laid out at,
// whether or not its box cuts them: a cut name's scrollWidth counts its ellipsis, and a
// whole one's rounds.
/** @param {Element | null | undefined} node */
function wordsWidth(node) {
  return node ? contentsBox(node).width : 0;
}

/** @typedef {Omit<ThreadReading, "settlement"> & {
 * settlement: ThreadReading["settlement"] | null,
 * news?: import("./held-news.js").NewsNotice | null}} ThreadViewModel */

// The user's last turn in a thread, by its key, as threadChange reads it (held-news.js).
/** @param {ThreadViewModel} model */
const lastTurn = (model) =>
  model.messages.findLast((message) => message.author === "user" && !message.progress)
    ?.key;

/** @typedef {Omit<import("./messages.js").MessageCommands, "reply" | "reaction" | "edit"> & {
 * authoredRank?: number,
 * reply: import("./replies.js").ReplyCommands & import("./messages.js").MessageCommands["reply"],
 * read: Pick<ReturnType<typeof import("./read.js").createReadTracking>, "observeMessage" | "observeFeedback" | "firstUnread" | "afterPass">,
 * reaction: Omit<import("./messages.js").MessageCommands["reaction"], "pressed">,
 * settlement: Omit<Parameters<typeof settleThread>[0], "parent" | "key" | "resolved" | "prepareLanding" | "reader">,
 * placedAt: Parameters<typeof quoteReading>[1]["placedAt"],
 * landInThread: import("./replies.js").ReplyCommands["landInThread"]}} ThreadCommands */

/* Where a container stands the thread's parts, and what it asks the thread to draw and
   do (the header), each optional. Any container gives these, a package's included
   (module-annotations.md, "Owning the primary conversation presentation"):
   - `head`, the places on the container's own head line, outside the thread, for the
     held-news notice and the settlement, which otherwise stand beside the first
     message's head, and for Next unread, which it draws only where a place is named.
   - `reply`, the place for the reply box (`outlet`), which otherwise closes the thread,
     and what its empty box reads and how a send lands (`options`, replies.js,
     `createReplyView`).
   - `quote`, whether the thread draws the words it is about over its messages.
   - `scroller`, given the thread's transcript, the box that scrolls its messages, at
     whose foot it says New reply (the header); without one it says none.
   - `landing(resolved)`, given whether the thread stood resolved as the press came, the
     step that takes the user where Resolve or Reopen leaves them, or null for the
     thread's own: Reopen in its reply box, Resolve where the user stands (folding.js,
     `settleThread`).
   Only Leaf's own containers say the rest (`ViewOutlets`):
   - `reader`, the reader a way back reopens the thread in once a settlement is taken
     back (folding.js): the page, for a margin card, which stands for the thread there;
     the primary reader, for a whole thread it draws whose nomination lands the user
     elsewhere, as the floating panel's view does. A seat, and a primary reader's thread
     that keeps the user where they pressed, name none and leave the route to choose.
   - The margin card's own (`CardOutlets`): `line`, its head line, which it arranges
     around the boxes the thread draws its notice and settlement in, and which the thread
     stands after its messages, where it shares their heads' track
     (annotation-chrome.css) and the notice takes only the room the heads leave
     (`#fitLineNews`); `endNewsMoves()`, whether news at the thread's end, which
     grows the floating card at the edge it does not hold, would move what the user is
     on (thread-preview.js, `heldEdge`), and since the card stands itself, a landing in
     it scrolls nothing into view; and `standsAtEnd()`, whether the reader stands at the
     end the card's transcript follows, as its keeper says (scrolling.js, `followEnd`).
   The thread draws each part apart in a box of its own (`apart`), which the container
   places in the place it names before the thread draws it, as it places the thread's
   box in its outlet. The reply's options are read as the box is made, once for the
   view. What the box's empty words say reads the thread as the thread draws it
   (`DrawnThread`), held news included, so they agree with its settlement and notice, as
   a card's own words do (`#createReply`). */
/** The thread as a thread draws it, held news included, which its reply box's words
 * read: whether it is resolved and by which agent, and whose turn it is (workflow.js,
 * `threadAttention`).
 * @typedef {Pick<ThreadReading, "resolved" | "resolvedBy" | "attention">} DrawnThread */
/** @typedef {Omit<import("./replies.js").ReplyOptions, "hint" | "hintParts" | "hintLead"> & {
 * hint?: (drawn: DrawnThread) => string,
 * hintParts?: (drawn: DrawnThread) => unknown,
 * hintLead?: (drawn: DrawnThread) => unknown}} ThreadReplyOptions */
/** @typedef {{
 * head?: {news: HTMLElement, controls: HTMLElement, unread?: HTMLElement},
 * reply?: {outlet?: HTMLElement, options?: ThreadReplyOptions},
 * quote?: boolean,
 * scroller?: (transcript: HTMLElement) => HTMLElement | null,
 * landing?: (resolved: boolean) => import("./folding.js").Landing | null,
 * }} ThreadOutlets */
/** @typedef {{
 * line?: (apart: ThreadView["apart"]) => HTMLElement,
 * endNewsMoves?: () => boolean,
 * standsAtEnd?: () => boolean,
 * }} CardOutlets */
/** @typedef {ThreadOutlets & CardOutlets & {reader?: "page" | "primary"}} ViewOutlets */

// A box a thread draws a part in where its container stands the part apart: it lays
// out as what it holds (surfaces.css) and, as the thread's own box is, is Leaf's.
const apartBox = () => {
  const box = document.createElement("div");
  box.className = "lf-thread-apart lf-ui";
  box.dataset.lfRuntime = ""; // passages.js, leafSurface
  generatedElement(box, { says: false });
  return box;
};

export class ThreadView {
  #commands;
  #messageCommands;
  #rewrites;
  // The model this card shows. Commands follow it explicitly; mechanical reads of
  // this paint's output must not subscribe the presenter that writes it.
  /** @type {import("/vendor/signals-core.js").Signal<ThreadViewModel>} */
  #shown;
  get #model() {
    return this.#shown.peek();
  }
  set #model(model) {
    this.#shown.value = model;
  }
  #transcript;
  /** @type {ReturnType<typeof createReplyView> | null} */
  #reply = null;
  // What a thread in the page's flow holds back says so in its control row (held-news.js).
  #news = newsNotice();
  #continuity;
  /** @type {ThreadViewModel | null} */
  #received = null;
  /** @type {{header: HTMLElement, items: {node: HTMLElement, width: number}[], boxWidth: number, held: boolean} | null} */
  #headerSlot = null;
  /** @type {Element | null} */
  #observedHeader = null;
  #sizes = sizeObserver(() => this.#retainHeaderSlot());
  #lineNews = sizeObserver(() => nextRender(() => this.#fitLineNews()));
  /** @type {ViewOutlets} */
  #outlets = {};
  // The boxes of the parts it draws where its container stands them (`ThreadOutlets`).
  #apart = Object.freeze({
    news: apartBox(),
    controls: apartBox(),
    reply: apartBox(),
    unread: apartBox(),
  });
  get apart() {
    return this.#apart;
  }
  // The words the thread is about, where its container asks for them (`#drawQuote`).
  #quoteHead = Object.assign(document.createElement("header"), {
    className: "lf-thread-quote-head",
  });
  #quoteId = `lf-thread-quote-${randomId()}`;
  #quoteExpanded = signal(false);
  /** @type {(() => void) | null} */
  #quoteEffect = null;
  // The answer to the user's last turn drawn since the container last stood the thread
  // at its size, and how the box that scrolls it stood before (`#fitAnswer`).
  /** @type {{answer: NonNullable<import("./held-news.js").ThreadChange["answers"]>, before: {extent: number, limit: number}} | null} */
  #unfitted = null;
  // The answer the box's end last followed into sight, while it answers the user's last
  // turn (`placesEnd`).
  /** @type {NonNullable<import("./held-news.js").ThreadChange["answers"]> | null} */
  #followed = null;
  // The answer waiting past that box's foot behind New reply, by its first message or
  // the face of its progress run.
  /** @type {{message: string, label: string, scroller: HTMLElement} | null} */
  #waiting = null;
  // Whether this opening offers Next unread, and whether that has been asked (header).
  #unreadSeat = false;
  #unreadAsked = false;
  // Full quote shows only where three lines cut the words. Once the quote stands, a
  // change of its size resizes the view its container's observers watch, so the press
  // follows in the next frame rather than inside this observer's delivery.
  #quoteSize = sizeObserver(() => nextRender(() => this.#fitQuote()));

  /** @param {ThreadCommands} commands @param {ThreadViewModel} model */
  constructor(commands, model) {
    this.#shown = signal(model);
    this.#commands = commands;
    // A rewrite of one of the user's messages (`message-edit.js`). Opening or closing
    // it paints at once, so its editor takes or gives back the focus in the same press.
    this.#rewrites = threadRewrites({
      views: () => this.#transcript.views,
      paint: () => this.repaint(),
      // Its reply box where it stands, in the thread or where its container stands it.
      box: () => this.#reply?.input ?? null,
      home: () => this.node,
      // Opening a rewrite shows what the thread holds (held-news.js), and unfolds a
      // summary holding the message, since it opens to be seen.
      opening: (id) => {
        this.#showNews();
        this.#transcript.expandAround(id);
      },
      landInThread: commands.reply.landInThread,
      landSent: commands.reply.landSent,
    });
    // A press on a reply's reactions is the user acting in this thread, so what the
    // thread holds shows with it (held-news.js).
    this.#messageCommands = {
      ...commands,
      reaction: { ...commands.reaction, pressed: () => this.#showNews() },
      edit: this.#rewrites.edit,
    };
    this.node = document.createElement("div");
    this.#transcript = new Transcript({
      commands,
      messageCommands: this.#messageCommands,
      repaint: () => this.repaint(),
      home: () => this.node,
    });
    this.#continuity = new ReplyContinuity(this.node);
    this.node.tabIndex = -1;
    this.node.classList.add("lf-page-thread", "lf-ring-overlay", "lf-ui");
    this.node.dataset.lfRuntime = ""; // passages.js, leafSurface
    generatedElement(this.node, { says: false });
    this.node.dataset.lfOffer = "";
  }

  // What the container asks of the thread and where it stands its parts
  // (`ViewOutlets`), given before each presentation.
  /** @param {ViewOutlets} outlets */
  setOutlets(outlets) {
    this.#outlets = outlets;
  }

  get model() {
    return this.#model;
  }

  // Local disclosure and draft changes repaint the complete received descriptor,
  // never feed a held presentation back into the news owner's input.
  repaint() {
    if (this.#received) this.#paint(this.#received);
  }

  // The seat owns placement, including while the card's outgoing pixels still fold
  // outside its Resolved disclosure. Landing and held news read that same placement.
  /** @type {HTMLDetailsElement | null} */
  #foldedInto = null;
  /** @type {Promise<unknown> | null} */
  #retirement = null;
  /** @param {HTMLDetailsElement | null} group @param {Promise<unknown> | null} retirement */
  setFoldedInto(group, retirement = null) {
    this.#foldedInto = group;
    this.#retirement = retirement;
  }
  get transcript() {
    return this.#transcript.node;
  }

  get #fold() {
    return this.#foldedInto && !this.#foldedInto.open ? this.#foldedInto : null;
  }

  // The last of the thread a reader can see, after which its news grows: the last
  // node its transcript shows (transcript.js, `foot`), and none while the thread is
  // folded. A card folded in its seat's Resolved disclosure draws nothing at all.
  get #foot() {
    return this.#fold ? null : this.#transcript.foot;
  }

  // What the thread draws after its messages that its settlement swaps: the reply box
  // while it stands open; none while the thread is folded, where it does not show. A
  // resolved card's Reopen stands where Resolve did, so settling grows nothing else.
  get #settlementRow() {
    if (this.#fold) return null;
    return this.node.querySelector(":scope > .lf-thread-reply");
  }

  // The node a message the thread draws stands in, after which a change to it grows;
  // none while the thread is folded, where no message shows.
  /** @param {string} key */
  #messageNode(key) {
    return this.#fold ? null : this.#transcript.messageNode(key);
  }

  /** @param {string} id */
  ownsMessage(id) {
    return (
      this.#model?.id === id ||
      this.#model?.messages.some((message) => message.id === id)
    );
  }

  // HeldNews compares readings; this owner decides whether their changed regions
  // would move visible words. Existing-message changes retain the hold. A pinned reply
  // can absorb growth at the thread's end, but cannot absorb changes above it or
  // settlement replacing the reply itself.
  /** @param {import("./held-news.js").ThreadChange} change */
  newsMoves({ news, changed, folds, appendedAtEnd, footFold }) {
    // Folded in its seat's closed Resolved disclosure, the card moves nothing as it
    // changes, and draws at once whatever its settlement does to the seat.
    if (this.#fold) return false;
    const pinned = pinnedReply(this.#reply?.node);
    // An answer's own fold of the progress run at the thread's end changes only the
    // thread's foot, as the answer's arrival does, unless the user is on a message
    // the fold would put away, by focus or by a selection reaching into it.
    const foot =
      footFold &&
      !folds.messages.some((key) => currentLocationTouches(this.#messageNode(key)));
    // A floating card grows at one of its own edges: the one it does not hold
    // (`CardOutlets`, `endNewsMoves`; thread-preview.js, `heldEdge`). That edge is the
    // card's alone, since it stands itself rather than in a flow its growth moves, so
    // no place its parts stand in says it.
    // News shows at once only where it changes the thread's end and the card says growth
    // there moves nothing the user is on (`endNewsMoves`). A change to the last message
    // is such news where it is a reply still streaming, or where the transcript, at its
    // cap, follows it there, as its keeper does for a reader it says stands at the end
    // (`CardOutlets`, `standsAtEnd`). The transcript's offset doesn't say that: a turn
    // that grew in this task, as its picture loaded, has carried the end past the
    // reader before the keeper's next reading takes them there. Anything else
    // would move the messages being read, so it waits. A settlement keeps the editor it
    // interrupts, as every thread keeps its reply box.
    const { endNewsMoves, standsAtEnd } = this.#outlets;
    if (endNewsMoves) {
      if (news.settled) return false;
      const last = this.#model?.messages.at(-1);
      const list = this.#transcript.node;
      const follows =
        list.scrollHeight > list.clientHeight + 0.5 && Boolean(standsAtEnd?.());
      const atEnd =
        (!news.appended || appendedAtEnd) &&
        !news.summaries &&
        [...changed].every(
          (key) => key === last?.key && (last.provisional || follows),
        ) &&
        (foot || (!folds.messages.length && !folds.summaries.length));
      return growthIsSeen(this.node) && (!atEnd || endNewsMoves());
    }
    const followed = pinned && !news.settled ? this.#foot : null;
    return (
      this.#transcript.newsMoves({ news, changed, folds }, { followed }) ||
      Boolean(news.settled && this.#settlementRow && growthIsSeen(this.#settlementRow))
    );
  }

  // What a card draws from beyond its reading: whether a reply to it is being written
  // and whether it holds a draft.
  /** @param {ThreadViewModel} model */
  #outside(model) {
    return [
      replyIsEditing(model.key),
      threadHoldsDraft(
        model.key,
        model.messages.map(({ id }) => id),
      ),
    ];
  }

  // Whether `model` is the reading this card last drew, outside inputs included, so a
  // pass that hands it over again need not draw it. The reading is rebuilt on every
  // pass, so it is compared by content; its `reread` is a fresh closure over the same
  // reading each time.
  /** @param {ThreadViewModel} model */
  shows(model) {
    const prior = this.#received;
    const drawnWith = this.#drawnWith;
    if (!prior || !drawnWith) return false;
    // A card holding news draws on every pass: what it shows then moves with time and
    // the reader, not with its reading.
    if (this.#model?.news) return false;
    const { reread: _priorReread, ...was } = prior;
    const { reread: _reread, ...now } = model;
    const outside = this.#outside(model);
    return (
      share(was, now) === was &&
      outside.every((part, index) => part === drawnWith[index])
    );
  }

  /** @type {(boolean | null)[] | null} */
  #drawnWith = null;

  /** @param {ThreadViewModel} model */
  present(model, options = {}) {
    return this.#paint(model, options, true);
  }

  // The caller knows whether this is a publication or a local repaint. Only a
  // publication allocates passive space; disclosures and editors stay intrinsic.
  /** @param {ThreadViewModel} model */
  #paint(model, _options = {}, published = false) {
    const prior = this.#received ? this.#model : null;
    this.#received = model;
    this.#drawnWith = this.#outside(model);
    // Where the container stands the thread's parts (`ViewOutlets`).
    const { head, line, reply, quote, scroller } = this.#outlets;
    // A margin card's head line, arranged around the boxes the notice and the
    // settlement stand in before they are drawn (`CardOutlets`, `line`).
    const inLine = line?.(this.#apart) ?? null;
    // Whether the container gives the thread a head line, outside it or in it.
    const lined = Boolean(head || inLine);
    const replyApart = Boolean(reply?.outlet);
    // Capture the current words only when news starts waiting, before its update
    // removes a receipt. This allocation lives with the held view, not its reading.
    if (!lined && model.news && !prior?.news)
      this.#retainHeaderSlot({ observe: false });
    // The rewrites the user has open, and the messages leaving, change their own room.
    const bodyPlace = published
      ? this.#continuity?.before([
          ...this.#transcript.views
            .filter((view) => view.editing)
            .map(({ node }) => node),
          ...this.#transcript.leaving(model),
        ])
      : null;
    const restoreFocus = holdFocus(this.node);
    this.#model = model;
    const change = prior && scroller ? threadChange(prior, model) : null;
    const box = scroller?.(this.#transcript.node) ?? null;
    if (this.#followed && lastTurn(model) !== this.#followed.turn)
      this.#followed = null;
    if (change?.answers && box)
      this.#unfitted = {
        answer: change.answers,
        before: this.#unfitted?.before ?? {
          extent: box.scrollHeight,
          limit: scrollLimit(box),
        },
      };
    // Whether the box holds New reply at its foot, which a fade there leaves whole.
    if (box) keeps(box, "data-lf-awaits", this.#waiting ? "" : null);
    // Where the notice and the settlement stand:
    // - where the container gives the thread a head line, in their boxes on it: after
    //   the floating panel's view's name, and before a margin card's Previous and Next,
    //   with the thread's facts, rather than over the end of the message head beside it
    //   (the user's choices, 16 October).
    // - elsewhere, the head's controls row, which reserves the room of one icon control
    //   (shadow.css, `--lf-thread-action-room`) beside the first message's own
    //   controls, and the notice beside the first message's head. A foot row of its own
    //   drew resolved threads unlike open ones.
    const notice = this.#news;
    if (model.news) notice.set(model.news);
    const news = model.news ? notice.node : nothing;
    // Its id names the surface too (`drawnThreadId`).
    keeps(this.node, "data-lf-thread", model.id);
    keeps(this.node, "data-lf-resolved", model.resolved);
    keeps(this.node, "data-lf-attempt", model.attempt || null);
    // A card is itself where a send or a walk stands the user, so it carries the
    // thread's name.
    keeps(this.node, "role", "group");
    keeps(this.node, "aria-label", `Thread, ${model.summary.topic}`);
    // A thread whose reply stands elsewhere ends with its messages, so it grows only at
    // its foot, the growing tail of the region holding it, as the panel's view is
    // (tests/shift_watch.js).
    keeps(this.node, "data-lf-append-tail", replyApart ? "" : null);
    const settlement = model.settlement
      ? this.#settlement(model, model.settlement)
      : nothing;
    const handedOn = this.#transcript.present(model, {
      arrived: Boolean(prior),
      awaited: this.#newReply(),
    });
    this.#reply ??= this.#createReply(model);
    // Beside the first header the notice is a box of its own on that header's line,
    // anchored to the header beside the controls' box at its end (surfaces.css,
    // `.lf-thread-content > .lf-thread-news`); its words change in place.
    keeps(notice.node, "data-lf-reflow", lined ? null : "text");
    const body = html`
      ${quote ? this.#drawQuote() : nothing}${this.#transcript.node}
      ${
        lined
          ? (inLine ?? nothing)
          : model.settlement || model.news
            ? html`${news}
                <div class="lf-thread-controls" data-lf-reflow="text">
                  <span class="lf-thread-meta-actions">${settlement}</span>
                </div>`
            : nothing
      }
    `;
    // A head line standing in the thread shares the transcript's grid, whose tracks the
    // line's width sets (annotation-chrome.css), so the two stand as the thread's own
    // children rather than in a content region.
    render(
      html`
        ${inLine ? body : html`<div class="lf-thread-content">${body}</div>`}
        ${this.#continuity?.gap ?? nothing} ${replyApart ? nothing : this.#reply.node}
      `,
      this.node,
    );
    render(lined ? news : nothing, this.#apart.news);
    render(lined ? settlement : nothing, this.#apart.controls);
    render(lined ? this.#nextUnread() : nothing, this.#apart.unread);
    render(replyApart ? this.#reply.node : nothing, this.#apart.reply);
    // Full quote stands from the quote's first paint, so its arrival moves nothing below
    // it; later changes of the quote's size follow by its observer (`#quoteSize`).
    if (quote) measure(this.#quoteHead, () => this.#fitQuote());
    if (!lined && model.news) measure(this.node, () => this.#retainHeaderSlot());
    else this.#releaseHeaderSlot();
    if (inLine && model.news) measure(this.node, () => this.#watchLineNews());
    else this.#releaseLineNews();
    this.#continuity?.after(bodyPlace);
    // A page thread whose render took the user's place puts them in its reply, or on
    // the thread itself.
    // Handing it on is the card's own act, which the list holding the card defers to.
    // A progress disclosure the user was on that this render replaced hands them to
    // its successor (transcript.js). A thread whose container stands its reply apart
    // lands no one there: as one rewrite gives way to the next, a landing in the
    // panel's field would let go of the height its view holds for a rewrite and take it
    // again in the same press (floating-panel.js, `holdThread`).
    restoreFocus?.(
      ...(handedOn
        ? [() => (focusDestination(handedOn, "return"), true)]
        : replyApart
          ? []
          : [
              () =>
                this.#commands.landInThread(
                  this.node.querySelector(SAY_BOX) ?? this.node,
                ),
            ]),
    );
    return this.node;
  }

  // Whether an answer to the user's turn is the thread's to place: one not yet fitted,
  // or one New reply stands for (the header).
  get answering() {
    return Boolean(this.#unfitted || this.#waiting);
  }

  // A box following its end asks this as the end moves, with how the box stood before
  // the move: whether the thread places that end itself. It does while an answer to the
  // user's turn is its to place (`answering`), and again once an answer the end followed
  // into sight grows, as when a picture in it loads, since the same rule decides whether
  // the end follows that growth or New reply stands for it (`#fitAnswer`). A move that
  // only changes the box's room, as a reply being typed does, is the box's.
  /** @param {{extent: number, limit: number}} before */
  placesEnd(before) {
    if (this.answering) return true;
    const answer = this.#followed;
    const scroller = this.#outlets.scroller?.(this.#transcript.node);
    if (!answer || !scroller || scroller.scrollHeight <= before.extent + 0.5)
      return false;
    this.#followed = null;
    this.#unfitted = { answer, before };
    this.#fitAnswer();
    return true;
  }

  // The container has stood the thread where it draws it: its scroller at its size, and
  // a new opening landed where it shows first. What the thread reads of them waits for
  // this (the header).
  settled() {
    this.#fitAnswer();
    const { head, line } = this.#outlets;
    if (this.#unreadAsked || (!head?.unread && !line)) return;
    this.#unreadAsked = true;
    this.#commands.read.afterPass(() => {
      if (!this.#received) return;
      this.#unreadSeat = (threadNamed(this.#model.key)?.unread.length ?? 0) > 0;
      if (this.#unreadSeat) this.repaint();
    });
  }

  #nextUnread() {
    if (!this.#unreadSeat) return nothing;
    const { key } = this.#model;
    const left = (threadNamed(key)?.unread.length ?? 0) > 0;
    return html`<button
      type="button"
      ${offeredAction("inline", "lf-next-unread")}
      ?disabled=${!left}
      ?data-lf-unoffered=${!left}
      @click=${() => void this.#commands.read.firstUnread(key)}
    >
      ${iconTemplate("down", "lf-action-icon")}Next unread
    </button>`;
  }

  // New reply, at the transcript's end, which sticks at the foot of the box scrolling it.
  #newReply() {
    const waiting = this.#waiting;
    if (!waiting) return nothing;
    return html`<div class="lf-awaited">
      <button
        type="button"
        ${offeredAction("inline", "lf-new-reply")}
        data-lf-news
        @click=${this.#showAnswer}
      >
        ${iconTemplate("down", "lf-action-icon")}${waiting.label}
      </button>
    </div>`;
  }

  /** @param {string} key */
  #answerNode(key) {
    return key.startsWith(FACE)
      ? this.#transcript.node.querySelector(
          `${WORKING}[data-lf-face="${CSS.escape(key.slice(FACE.length))}"]`,
        )
      : this.#transcript.messageNode(key);
  }

  // Read where the box stands at its size, after layout and before the frame is shown.
  #fitAnswer() {
    const unfitted = this.#unfitted;
    this.#unfitted = null;
    const scroller = this.#outlets.scroller?.(this.#transcript.node);
    if (!unfitted || !scroller) return;
    const { answer, before } = unfitted;
    const turn = this.#transcript.messageNode(answer.turn);
    if (!turn) return;
    /** @type {NodeListOf<HTMLElement>} */
    const working = this.#transcript.node.querySelectorAll(WORKING);
    const work = [...working].find((node) => renderedOrder(turn, node) < 0);
    const message = answer.reply ?? (work ? FACE + work.dataset.lfFace : null);
    if (!message) return;
    const waiting = this.#waiting;
    // An answer folding the work before it into less room moves nothing either, though
    // it takes over a New message the work left waiting. Its later growth is placed again
    // too, as a followed answer's is (`placesEnd`).
    if (!waiting && scroller.scrollHeight <= before.extent + 0.5) {
      this.#followed = answer;
      return;
    }
    // A reader whose wheel or key has the box scrolling stands where it takes them
    // (header), though the box hasn't moved yet: the browser applies that scroll a frame
    // or more after the input, and a write of the box meanwhile cancels it. The delayed
    // write below asks again, for an input made since.
    const atEnd =
      !readerScrolls(scroller) && before.limit - scroller.scrollTop <= SCROLL_SLACK;
    const pad = Number.parseFloat(getComputedStyle(scroller).paddingTop);
    const from = () =>
      turn.getBoundingClientRect().top - scroller.getBoundingClientRect().top - pad;
    if (
      !waiting &&
      atEnd &&
      scroller.scrollHeight - scroller.scrollTop - from() <= scroller.clientHeight
    ) {
      scrollToEnd(scroller);
      this.#followed = answer;
      return;
    }
    const next = {
      message,
      label: answer.reply ? "New reply" : "New message",
      scroller,
    };
    if (waiting?.message === next.message) return;
    this.#stopWaiting();
    this.#waiting = next;
    scroller.addEventListener("scroll", this.#sawAnswer, { passive: true });
    // New reply joins the box, whose children other observers watch, so it is drawn in
    // the next frame, after the transcript is drawn.
    nextRender(() => {
      if (this.#waiting !== next) return;
      this.repaint();
      if (waiting || !atEnd || !turn.isConnected || readerScrolls(scroller)) return;
      // The user's turn stands wholly in sight, between the box's top edge and New
      // reply's ground, its head first where it is taller than that.
      const foot = this.node.querySelector(".lf-awaited")?.getBoundingClientRect();
      const below = foot ? turn.getBoundingClientRect().bottom - foot.top : 0;
      const by = Math.min(Math.max(below, 0), from());
      moveScrollerBy(scroller, by);
    });
  }

  #stopWaiting() {
    this.#waiting?.scroller.removeEventListener("scroll", this.#sawAnswer);
    this.#waiting = null;
  }

  // Shows the answer waiting past the box's foot: its start comes into sight. The press
  // that took New reply away leaves the user on the thread, as showing a thread's held
  // news does.
  #showAnswer = () => {
    const waiting = this.#waiting;
    if (!waiting) return;
    focusDestination(wholeThread(this.node), "move");
    this.#stopWaiting();
    this.repaint();
    const node = this.#answerNode(waiting.message);
    if (node) scrollIntoView(node, { block: "start" });
  };

  // Scrolling the answer's start into sight above New reply takes New reply away, the
  // box keeping its height. A scroll Leaf makes, as keeping the box's foot beside a
  // growing field (scrolling.js, `keepFoot`), is not the user going there.
  #sawAnswer = () => {
    const waiting = this.#waiting;
    if (!waiting || !browserScrolls(waiting.scroller)) return;
    const node = this.#answerNode(waiting.message);
    const press = this.node.querySelector(".lf-new-reply");
    if (!node || !press) return;
    // Focusing New reply can scroll this box to reveal the press. That scroll must not
    // remove the focused press before its Enter can activate it.
    if (press === focused()) return;
    if (node.getBoundingClientRect().top >= press.getBoundingClientRect().top) return;
    this.#stopWaiting();
    this.repaint();
  };

  // A notice on a head line standing in the thread, as a margin card's row of presses
  // does, stands in a track that takes its width from the heads' track
  // (annotation-chrome.css), so the notice takes only the room the heads leave beside
  // each one's name and time, its padding and its controls' room included. A head lends
  // that room to its words while its controls hide, and the controls stand over whatever
  // runs into it when they show (controls.css), so the fit keeps it, and Edit covers no
  // name or time beside news. Where the room is short of its count the notice is cut
  // (held-news.js, `newsNotice`).
  // The room is the notice's width and the narrowest head's spare width together,
  // which the two tracks trade one for one, so drawing the notice at it changes nothing
  // it was read from. A notice at a finger's floor can still leave a head short, and
  // the head then gives up its parts in their order (surfaces.css): where a name is cut
  // to less than an em, none of it shows (`data-lf-nameless`), so no sliver of a letter
  // or an ellipsis stands in the head. The fit reads what of each name the notice
  // leaves as drawn, and a hidden name keeps its box, so the reading holds.
  // The tracks can't size this themselves: every head the transcript shows bounds the
  // room, but only the first message's and the one standing beside the line keep to the
  // heads' track, and a later head spans both until it scrolls beside the line
  // (thread-preview.js, `data-lf-beside-actions`), so a track sized by its heads would
  // widen and narrow the notice as the user scrolls; and no track hides a name its
  // width cuts below an em.
  #fitLineNews() {
    const notice = this.#news.node;
    const heads = [];
    for (const head of this.node.querySelectorAll(
      ".lf-thread-transcript .lf-msg-head",
    )) {
      if (!head.checkVisibility()) continue;
      const style = getComputedStyle(head);
      const name = head.querySelector(":scope > b");
      const time = head.querySelector(":scope > .lf-msg-meta > time");
      // The controls' room is as wide as their group (controls.css).
      const controls =
        head
          .querySelector(":scope > .lf-msg-control-room > .lf-msg-controls")
          ?.getBoundingClientRect().width ?? 0;
      const need =
        parseFloat(style.paddingInlineStart) +
        parseFloat(style.paddingInlineEnd) +
        controls +
        wordsWidth(name) +
        (name && time ? parseFloat(style.columnGap) : 0) +
        wordsWidth(time);
      heads.push({ name, spare: head.getBoundingClientRect().width - need });
    }
    if (!heads.length || !notice.isConnected) {
      this.#clearLineNews();
      return;
    }
    const width = notice.getBoundingClientRect().width;
    const spare = Math.min(...heads.map((head) => head.spare));
    notice.style.setProperty("--lf-news-room", roomPx(Math.max(0, width + spare)));
    const nameless = heads.map(
      ({ name }) =>
        !!name &&
        name.scrollWidth > name.clientWidth &&
        name.clientWidth < parseFloat(getComputedStyle(name).fontSize),
    );
    heads.forEach(({ name }, at) => {
      if (name) keeps(name, "data-lf-nameless", nameless[at] ? "" : null);
    });
  }

  // A render fits it again, and a head's time changes size while news waits as it
  // ticks on from "just now". The notice and a name change size
  // because of the fit itself, so watching them would deliver the fit its own change,
  // and a time's change fits it in the next frame, since the fit resizes boxes the
  // observer's delivery has already passed.
  #watchLineNews() {
    this.#lineNews.disconnect();
    for (const time of this.node.querySelectorAll(
      ".lf-thread-transcript .lf-msg-head > .lf-msg-meta > time",
    ))
      this.#lineNews.observe(time);
    this.#fitLineNews();
  }

  #releaseLineNews() {
    this.#lineNews.disconnect();
    this.#clearLineNews();
  }

  // The fit writes the notice's room and each name it hides, and a message's head
  // outlives the notice (each MessageView keeps its own, messages.js), so both go together.
  #clearLineNews() {
    this.#news.node.style.removeProperty("--lf-news-room");
    for (const name of this.node.querySelectorAll(
      ".lf-thread-transcript .lf-msg-head > b[data-lf-nameless]",
    ))
      keeps(name, "data-lf-nameless", null);
  }

  #releaseHeaderSlot() {
    if (this.#observedHeader) this.#sizes.unobserve(this.#observedHeader);
    this.#observedHeader = null;
    this.#releaseHeaderItems();
    keeps(this.#news.node, "data-lf-room", null);
    this.#news.node.style.removeProperty("--lf-thread-news-start");
    this.#news.node.style.removeProperty("--lf-thread-news-visible-end");
  }

  #releaseHeaderItems() {
    for (const { node } of this.#headerSlot?.items ?? []) {
      node.classList.toggle("lf-held-header-item", false);
      node.style.removeProperty("--lf-held-header-width");
    }
    this.#headerSlot = null;
  }

  #retainHeaderSlot({ observe = true } = {}) {
    const news = this.#model?.news;
    if (observe && !news) {
      this.#releaseHeaderSlot();
      return;
    }
    const content = this.node.querySelector(":scope > .lf-thread-content");
    const first = content?.querySelector(
      ":scope > .lf-thread-transcript > :nth-child(1 of .lf-msg, .lf-thread-checkpoint)",
    );
    /** @type {HTMLElement | null | undefined} */
    const header =
      first?.querySelector(":scope > .lf-summary-checkpoint > .lf-summary-header") ??
      first?.querySelector(":scope > .lf-msg-head");
    if (!header) {
      this.#releaseHeaderSlot();
      return;
    }
    const box = header.getBoundingClientRect();
    if (!box.width) return;
    const allocates = header.classList.contains("lf-msg-head");
    if (observe && this.#observedHeader !== header) {
      if (this.#observedHeader) this.#sizes.unobserve(this.#observedHeader);
      this.#sizes.observe(header);
      this.#observedHeader = header;
    }
    let slot = this.#headerSlot;
    if (!slot || slot.header !== header || slot.boxWidth !== box.width || !news) {
      // A new width is a user reflow. Read its unconstrained allocation on an
      // invisible copy, without transient writes to real words.
      const resizing = allocates && slot?.header === header;
      let reading = header;
      if (resizing) {
        reading = header.cloneNode(true);
        Object.assign(reading.style, {
          position: "absolute",
          visibility: "hidden",
          inlineSize: layoutPx(box.width),
          margin: "0",
          anchorName: "none",
        });
        for (const node of words(reading)) {
          node.classList.toggle("lf-held-header-item", false);
          node.style.removeProperty("--lf-held-header-width");
        }
        header.after(reading);
      } else this.#releaseHeaderItems();
      const originals = words(header)[Symbol.iterator]();
      const items = [];
      for (const measured of words(reading)) {
        const original = originals.next();
        if (original.done) break;
        items.push({
          node: original.value,
          width: measured.getBoundingClientRect().width,
        });
      }
      if (resizing) reading.remove();
      slot = { header, items, boxWidth: box.width, held: observe };
      this.#headerSlot = slot;
      for (const { node, width } of allocates ? items : []) {
        // Keep the author's current width before the first held render, while
        // its receipt can still take unused room on that first presentation.
        if (!observe && node.classList.contains("lf-msg-meta")) continue;
        node.classList.toggle("lf-held-header-item", true);
        node.style.setProperty("--lf-held-header-width", layoutPx(width));
      }
    }
    if (observe && !slot.held) {
      for (const item of allocates ? slot.items : []) {
        if (item.node.classList.contains("lf-msg-meta"))
          item.width = Math.max(item.width, item.node.getBoundingClientRect().width);
        item.node.classList.toggle("lf-held-header-item", true);
        item.node.style.setProperty("--lf-held-header-width", layoutPx(item.width));
      }
      slot.held = true;
    }
    // The notice's readings are lengths from the header's start: where the words end,
    // which the notice starts after, and where the header's line stops showing, which
    // it stops before (surfaces.css, `.lf-thread-content > .lf-thread-news`).
    const notice = this.#news.node;
    const right = Math.max(
      box.left,
      ...slot.items.map(({ node }) => node.getBoundingClientRect().right),
    );
    notice.style.setProperty("--lf-thread-news-start", layoutPx(right - box.left));
    if (news) {
      // While news stands, the notice holds the room of the widest count it says, so
      // later news never narrows or widens it under the pointer.
      keeps(notice, "data-lf-room", NEWS_ROOM);
      const shown = shownRect(header, new Map());
      if (shown)
        notice.style.setProperty(
          "--lf-thread-news-visible-end",
          layoutPx(Math.max(0, shown.right - box.left)),
        );
    } else keeps(notice, "data-lf-room", null);
  }

  // The words the thread is about, over its to-dos and messages (`quoteReading`), in
  // three lines: where they still stand on the page, the container's way there goes to
  // them; where they no longer do, as for a thread a revision detached from its
  // passage, the quotation the thread kept is all that is left of them, so Full quote
  // shows the whole of it, its press standing above the words it grows so the press
  // never moves itself. The quote's status word leads its words, so the three lines
  // never cut it. Full quote shows only where three lines cut them, and the quote stays
  // whole while the view stands. Where the words stand is read from the page, which the
  // thread's pass reads again after drawing (presentation.js, `readTargets`) and a data
  // refresh changes without changing the thread, so the quote draws by an effect of its
  // own that follows that reading as well as the thread.
  #drawQuote() {
    this.#quoteEffect ??= effect(() => {
      const thread = this.#shown.value.source;
      documentChanged();
      const quote = quoteReading(thread, this.#commands);
      const expanded = this.#quoteExpanded.value;
      untracked(() => {
        keepsHidden(this.#quoteHead, !quote);
        keeps(this.#quoteHead, "data-lf-detached", quote?.detached ? "" : null);
        keeps(this.#quoteHead, "title", (quote?.place && quote.trail) || null);
        render(this.#quoteTemplate(quote, expanded), this.#quoteHead);
      });
    });
    return this.#quoteHead;
  }

  /** @param {ReturnType<typeof quoteReading>} quote @param {boolean} expanded */
  #quoteTemplate(quote, expanded) {
    if (!quote) return nothing;
    const status = quote.status
      ? html`<span class="lf-anchor-status">${voiced(quote.status)}</span>`
      : nothing;
    // Quoted words with no place of their own stand under the headings over them, so a
    // status arriving, as a revision that rewrites them while the thread is open sends,
    // takes a line the label already holds rather than growing the head under the
    // user's controls.
    const where = quote.place || quote.trail;
    const label =
      where || quote.status
        ? html`<p class="lf-quote-label">
            ${status}${where && quote.status ? " · " : ""}${where}
          </p>`
        : nothing;
    if (!quote.words) return label;
    const press = quote.localReading
      ? html`<button
          type="button"
          ${offeredAction(
            "inline",
            "lf-thread-disclosure lf-quote-expand lf-disclosure-marker",
          )}
          aria-label="Full quote"
          hidden
          aria-expanded=${String(expanded)}
          aria-controls=${this.#quoteId}
          @click=${() => {
            this.#quoteExpanded.value = !this.#quoteExpanded.peek();
          }}
        >
          Full quote
        </button>`
      : nothing;
    return html`${label}${press}
      <blockquote
        ${ref(this.#watchQuote)}
        id=${this.#quoteId}
        class="lf-thread-quote"
        data-lf-expanded=${String(quote.localReading && expanded)}
      >
        ${quote.words}
      </blockquote>`;
  }

  /** @param {Element | undefined} node */
  #watchQuote = (node) => {
    this.#quoteSize.disconnect();
    if (node) this.#quoteSize.observe(node);
  };

  #fitQuote() {
    const quote = this.#quoteHead.querySelector(":scope > .lf-thread-quote");
    const press = this.#quoteHead.querySelector(":scope > .lf-quote-expand");
    if (quote && press)
      keeps(
        press,
        "hidden",
        !this.#quoteExpanded.peek() && quote.scrollHeight <= quote.clientHeight
          ? ""
          : null,
      );
  }

  // Whether the progress behind the working message stood open when last drawn
  // (transcript.js, `progressOpen`).
  get progressOpen() {
    return this.#transcript.progressOpen;
  }

  // Resolve and Reopen are one toggle, so every surface draws it as one check, drawn
  // done on a resolved thread (browser/AGENTS.md, "Controls are few and quiet"), in one corner:
  // settling moves nothing beside it. A margin card once said Reopen as a word.
  /** @param {ThreadViewModel} model
   * @param {NonNullable<ThreadViewModel["settlement"]>} state */
  #settlement(model, state) {
    const reopen = state.kind === "unresolve";
    const word = reopen ? "Reopen" : "Resolve";
    const label =
      reopen && model.resolvedBy
        ? `✓ ${model.resolvedBy} · ${state.label}`
        : state.label;
    return html`<button
      ${offeredAction("symbol", reopen ? "lf-reopen" : "lf-resolve", label, {
        action: reopen ? "reopen" : "resolve",
      })}
      data-lf-disc
      data-lf-tone=${reopen ? "positive" : "ink"}
      ${commandsOn(`On a thread's ${word} button`, (button) => [
        {
          id: reopen ? "thread.reopen" : "thread.resolve",
          keys: PRESS,
          title: word.toLowerCase(),
          control: button,
          run: this.#settle,
        },
      ])}
    ></button>`;
  }

  // What the thread holds, shown by a press on one of its controls. Where showing it
  // takes the pressed control away, as a held settlement does Resolve, the press leaves
  // the user on the thread's title.
  #showNews() {
    if (!this.#model?.news) return;
    const restoreFocus = holdFocus(this.node);
    this.#model.news.open();
    restoreFocus?.(this.node);
  }

  // A press means what its control drew, and shows what the thread holds; where the
  // thread already stands as the press means, as one resolved elsewhere whose news
  // waits, it sends nothing (actions.js, `settle`).
  #settle = () => {
    const model = this.#model;
    const { landing } = this.#outlets;
    this.#showNews();
    if (!model.resolved) dismissReply(model.key);
    void settleThread({
      parent: () => this.#model.id,
      key: model.key,
      resolved: model.resolved,
      // Where the container says a settlement takes the user, as the floating panel
      // moves on to the next thread and a margin card to the next at its passage, else
      // closes onto it (`ThreadOutlets`, `landing`), else the thread's own.
      prepareLanding: () => landing?.(model.resolved) ?? this.#prepareThreadLanding(),
      // The reader a way back reopens the thread in, which its container names
      // (`ViewOutlets`, `reader`).
      reader: this.#outlets.reader ?? null,
      ...this.#commands.settlement,
    }).catch(() => {});
  };

  // Reopening lands in the reply on every card, even when Lit retains the pressed
  // button, wherever the thread stands its reply box and its settlement, as the
  // floating panel stands them apart. A page thread also moves into or out of its
  // seat's Resolved disclosure (inline.js), so keep its destination in view once the
  // departing pixels finish.
  #prepareThreadLanding = () => {
    const reopening = this.#model.resolved;
    const mayLand = retainUserIntent({
      source:
        [this.node, ...Object.values(this.#apart)].find((at) =>
          currentLocationIn(at),
        ) ?? this.node,
      available: () => this.node.isConnected,
    });
    return async () => {
      // The summary is semantically available at once, but a long departing card
      // still puts it below the viewport. Keep this gesture's original authority
      // while its pixels leave; a later user move still vetoes the landing.
      await this.#retirement?.catch(() => {});
      const place = this.#fold?.querySelector(":scope > summary") ?? this.node;
      const places = [place, ...Object.values(this.#apart)];
      if (!mayLand() || !places.some((at) => currentLocationIn(at))) return false;
      if (reopening) this.#commands.landInThread(this.#reply?.input ?? this.node);
      // A floating card stands itself (`CardOutlets`, `endNewsMoves`), so landing in
      // it scrolls nothing into view.
      const control = focused();
      if (!this.#outlets.endNewsMoves && control) scrollThreadIntoView(place, control);
      return true;
    };
  };

  // Every thread keeps its reply box. A resolved thread's says that a reply reopens it
  // (events.md), as the floating panel's field does.
  /** @param {ThreadViewModel} model */
  #createReply(model) {
    const commands = this.#commands.reply;
    const { hint, hintParts, hintLead, ...options } =
      this.#outlets.reply?.options ?? {};
    // The box's empty words say the thread as this view draws it, held news included,
    // so they change with its settlement and notice, when the user shows the news, and
    // not before. They read the drawn reading as a signal, so the box draws them again
    // with each reading the thread draws.
    /** @returns {DrawnThread} */
    const drawn = () => {
      const { resolved, resolvedBy, attention } = this.#shown.value;
      return { resolved, resolvedBy, attention };
    };
    return createReplyView(
      model.key,
      {
        ...commands,
        actions: {
          ...commands.actions,
          reply: (key, text, options) => {
            // The user's turn takes New reply away, with the paint it brings.
            const stood = this.#waiting;
            this.#stopWaiting();
            const flight = commands.actions.reply(key, text, options);
            if (!flight && stood) this.repaint();
            return flight;
          },
        },
      },
      () => this.repaint(),
      {
        hint: hint
          ? () => hint(drawn())
          : () => (drawn().resolved ? REOPEN_HINT : REPLY_HINT),
        ...(hintParts && { hintParts: () => hintParts(drawn()) }),
        ...(hintLead && { hintLead: () => hintLead(drawn()) }),
        // A container says what the box reads and how a send lands there, as a margin
        // card moves with the send it presents (`ThreadOutlets`, `reply`).
        ...options,
        editLast: this.#rewrites.editLast,
      },
    );
  }

  commit() {
    this.#transcript.commit(this.#model);
  }

  // The reply being written in this thread, which no view holds, comes into this one
  // once it is `shown` (replies.js, `claim`).
  /** @param {() => boolean} shown */
  claimReply(shown) {
    this.#reply?.claim(shown);
  }

  retire() {
    this.#reply?.cancelDictation();
    this.#transcript.retire();
  }

  dispose() {
    this.#stopWaiting();
    this.#received = null;
    this.#sizes.disconnect();
    this.#releaseHeaderSlot();
    this.#lineNews.disconnect();
    this.#quoteSize.disconnect();
    this.#quoteEffect?.();
    this.#quoteEffect = null;
    this.#continuity?.release();
    this.retire();
    this.#reply?.dispose();
    this.#reply = null;
  }
}
