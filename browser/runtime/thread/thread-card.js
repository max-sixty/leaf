/* One synchronous Lit owner for complete page, outlet and margin threads.

   Every surface uses the same metadata, transcript, message and reply vocabulary.
   Containers own navigation and placement, including whether their transcript scrolls;
   shadow.css owns the conversation's appearance through widget shadow boundaries.
   Conversation flow stays inside a content region, separate from the outer body's
   retained reply space. A margin card instead allocates its own scrolling transcript
   and overlay controls. Thread controls stay outside message and summary folds. MessageView
   owns each complete message, so no container extracts or reparents its header.
   Independent controls stand on its first header line, in the room the line keeps at
   its end, and a held-news notice stands on the same line after the header's words,
   each a box of its own anchored to the header, so no box stands over the words. That
   line reserves a notice's minimum hit area from its first paint; the metadata edge
   measured before news arrives is retained while it waits, including when its
   workflow receipt goes.
   Each message header text item keeps its allocated width while news waits, so a later
   receipt grows only inside its own clipped box. The first notice may use spare
   room for its new receipt without moving the author or time already shown.

   Immutable descriptors contain generated presentation only. Retained native editors,
   margin controls and frozen message widgets keep their mechanical lifetime outside
   those values. The card draws its messages as every reader of a whole thread does,
   folds and working message included (transcript.js), around them its head's controls
   and its reply box.

   A quotation whose original words are no longer on the page keeps a local
   full-reading disclosure, including when a rewritten section still has a navigation
   destination. Its expansion lives with the card through presentation. The owner
   alone renders its native card root and all generated descendants; a failed
   candidate is restored by presenting its committed descriptor again. It owns title
   gesture policy, outgoing fold paint and local draft repaint. Surfaces receive
   whole-thread geometry readings rather than descendant nodes. */
import { nextRender, sizeObserver } from "../rendering.js";
import {
  holdFocus,
  focusDestination,
  focused,
  currentLocationTouches,
  currentLocationIn,
} from "../focus.js";
import { html, render, nothing, share, signal } from "/runtime/framework.js";
import { turns, threadKey } from "./model.js";
import {
  anchorLabel,
  messageReading,
  threadPassage,
  threadSummary,
} from "./messages.js";
import { generatedElement, offeredAction } from "../widget-elements.js";
import { measure } from "../shown-box.js";
import { keeps, layoutPx, roomPx } from "../keeps.js";
import { commandsOn } from "../keyboard/scopes.js";
import { PRESS } from "../keyboard/bindings.js";
import {
  createReplyView,
  replyIsEditing,
  dismissReply,
  threadHoldsDraft,
} from "./replies.js";
import { atScrollEnd } from "../scrolling.js";
import { settleThread } from "./folding.js";
import { answeredInWords } from "../obligations/model.js";
import { SAY_BOX } from "./selectors.js";
import {
  threadAttention,
  todoWord,
  workflowWord,
  hasWorkflowLine,
} from "./workflow.js";
import { leafSays } from "../voice.js";
import { agentName } from "../semantic-state.js";
import { growthIsSeen, shownRect } from "../geometry.js";
import { ago, shortAgo } from "../presence.js";
import { retainUserIntent } from "../user-intent.js";
import { scrollThreadIntoView, pinnedReply } from "./reply-landing.js";
import { threadRewrites } from "./message-edit.js";
import { newsNotice, threadChange } from "./held-news.js";
import { ReplyContinuity } from "./reply-continuity.js";
import { Transcript } from "./transcript.js";

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
 * todos: readonly {id: string, title: string}[], summaries: ThreadRecord["summaries"],
 * messages: readonly MessageReading[], working: WorkingMessage | null,
 * source: ThreadRecord, reread: (held: ThreadRecord) => ThreadReading}} ThreadReading */

// What a thread's head says of the words it is about: the quote, whether it still
// stands on the page, and its hover. A card's head draws it, and so does the floating
// panel's view of a thread (floating-panel.js, `quoteHead`).
/** @param {ThreadRecord} thread
 * @param {Pick<ReturnType<typeof import("../anchor-placement.js").createAnchorPlacement>, "placedAt">} anchors */
export function quoteReading(thread, anchors) {
  const placement = anchors.placedAt(thread.id);
  // A version that rewrote the quoted words left the thread on their section
  // (`rewritten_from`, events.md); the head still names those words, marked as changed.
  const rewritten = thread.rewritten_from;
  const quoted = threadPassage(thread);
  const label = anchorLabel(quoted, thread.root.about);
  if (!label) return null;
  const anchored = Boolean(thread.anchor) || Boolean(thread.detached_from);
  const found = !thread.detached_from && placement != null;
  const outdated = anchored && placement?.status === "outdated";
  const changed =
    Boolean(rewritten) ||
    Boolean(quoted?.quote && placement?.datumElement && !placement.exact);
  return Object.freeze({
    label,
    words: quoted?.quote ?? null,
    anchored,
    found,
    outdated,
    changed,
    // A surviving element can still be a destination after its quoted words
    // have gone (rewritten text, replaced data or a virtual datum). Only a
    // resolved passage can supply the original quote's complete reading.
    localReading: Boolean(quoted?.quote) && placement?.kind !== "passage",
    title: !anchored
      ? null
      : found
        ? outdated
          ? "This comment refers to an earlier data revision"
          : changed
            ? "These words have changed since; jump to their current item"
            : quoted?.quote && placement.kind !== "passage"
              ? "Jump to the quoted item's current location"
              : "Jump to this passage"
        : thread.detached_from
          ? "This passage is no longer in the version shown"
          : "This passage can't be identified in the version shown",
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
const STOPPED = new Set(["ended", "stale", "interrupted"]);
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
  const running = workflows.find(
    (workflow) =>
      !workflow.condition && ["working", "replying"].includes(workflow.stage),
  );
  const runningLine = running && hasWorkflowLine(running) ? running : null;
  const stopped = workflows.find(
    /** @returns {workflow is Extract<import("../framework/application.js").Workflow, {detail: string}>} */
    (workflow) =>
      workflow.condition !== null &&
      STOPPED.has(workflow.condition.kind) &&
      Boolean(workflow.detail),
  );
  const todo = thread.todos.find(
    /** @returns {todo is import("../framework/application.js").WireTodo & {running: NonNullable<import("../framework/application.js").WireTodo["running"]>}} */
    (todo) => todo.running !== null,
  );
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
            words: todo.running.text,
            position: todo.running.seq,
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
          : progressStep;
  if (!step || !step.words || (!pending.length && !step.live && !step.condition))
    return null;
  const { words, position, live, condition, agent } = step;
  const agentMessage = messages.findLast((message) => message.author === "agent");
  // A workflow's detail is explicit agent work text linked to its exact input. A
  // to-do's line can be user-authored, so it supplies no reply visibility evidence.
  const work = runningLine?.detail ? runningLine : !running && !todo ? stopped : null;
  const progress = !work && (running || (!todo && !stopped)) ? pending.at(-1) : null;
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

// The user's open to-dos on a thread, over the conversation about them: each title
// with its Done, the ticked circle it shows wherever Leaf offers it, which tells it from
// the thread head's Resolve check. A thread card once worded it. Done is the user's
// `todo_end`, which takes the line away in the turn it is pressed (queue-api.js,
// `done`). A card draws them at its head, and so does the floating panel's view of a
// thread, under its quote.
/** @param {readonly {id: string, title: string}[]} todos @param {(id: string) => unknown} done */
export function threadTodos(todos, done) {
  if (!todos.length) return nothing;
  return html`<ul class="lf-thread-todos">
    ${todos.map(
      (todo) =>
        html`<li class="lf-thread-todo">
          <span class="lf-thread-todo-title">To-do · ${todo.title}</span
          ><button
            ${offeredAction("symbol", "", undefined, { action: "done" })}
            @click=${() => done(todo.id)}
          ></button>
        </li>`,
    )}
  </ul>`;
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
  const openTodos = new Set(thread.todos.map(({ id }) => id));
  /** @param {ThreadRecord["msgs"][number]} message */
  const leaves = (message) =>
    asking.has(message.id)
      ? leafSays("Waiting on me")
      : message.todo && openTodos.has(message.id)
        ? todoWord(null)
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
        reactions: surface === "outlet" ? message.reactions : null,
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
    // disclosure (inline.js). Who resolved it is said only where it was the agent.
    resolvedBy:
      thread.resolved?.author === "agent"
        ? `✓ Resolved by ${thread.resolved.agent}`
        : "",
    settlement: Object.freeze({
      kind,
      word,
      label,
    }),
    // The user's open to-dos on the thread, each named at the thread's head with its
    // Done (`threadTodos`), as the floating panel's field names one the user stands on
    // in the page.
    todos: Object.freeze(
      thread.userTodos.map(({ id, title }) => Object.freeze({ id, title })),
    ),
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
  if (!node) return 0;
  const range = document.createRange();
  range.selectNodeContents(node);
  return range.getBoundingClientRect().width;
}

/** @typedef {Omit<ThreadReading, "settlement"> & {
 * settlement: ThreadReading["settlement"] | null,
 * news?: import("./held-news.js").NewsNotice | null,
 * change?: import("./held-news.js").ThreadChange | null}} ThreadViewModel */

/** @typedef {Omit<import("./messages.js").MessageCommands, "reply" | "reaction" | "edit"> & {
 * authoredRank?: number,
 * reply: import("./replies.js").ReplyCommands & import("./messages.js").MessageCommands["reply"],
 * read: Pick<ReturnType<typeof import("./read.js").createReadTracking>, "observeMessage" | "observeFeedback">,
 * reaction: Omit<import("./messages.js").MessageCommands["reaction"], "pressed">,
 * settlement: Omit<Parameters<typeof settleThread>[0], "parent" | "key" | "resolved" | "prepareLanding">,
 * todos: {done: (id: string) => unknown},
 * landInThread: import("./replies.js").ReplyCommands["landInThread"]}} ThreadCommands */

/** @typedef {{nav: Element | null, expand: Element, close: Element,
 * anchor: import("./card-anchor.js").CardAnchor,
 * sending: () => void,
 * prepareLanding: NonNullable<Parameters<typeof settleThread>[0]["prepareLanding"]>}} MarginControls */

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
  /** @type {(() => Element | null) | null} */
  #settlesAt = null;
  /** @type {MarginControls | null} */
  #marginControls = null;
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
  #marginNews = sizeObserver(() => nextRender(() => this.#fitMarginNews()));

  /** @param {ThreadCommands} commands @param {ThreadViewModel} model */
  constructor(commands, model) {
    this.#shown = signal(model);
    this.#commands = commands;
    // A rewrite of one of the user's messages (`message-edit.js`). Opening or closing
    // it paints at once, so its editor takes or gives back the focus in the same press.
    this.#rewrites = threadRewrites({
      views: () => this.#transcript.views,
      paint: () => this.repaint(),
      box: () => this.node.querySelector(SAY_BOX),
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
    this.node.classList.add("lf-page-thread", "lf-ui");
    this.node.dataset.lfRuntime = ""; // passages.js, leafSurface
    generatedElement(this.node, { says: false });
    this.node.dataset.lfOffer = "";
  }

  /** @param {MarginControls | null} controls */
  setMarginControls(controls) {
    this.#marginControls = controls;
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

  // Where the seat's flow would grow if the card's settlement changed (inline.js), read
  // as the news comes: before the seat's next open thread, or before its Resolved
  // disclosure, for a resolved card that reopens; the disclosure, while it stands open,
  // for an open card that resolves into it. Null where nothing the seat draws grows.
  /** @param {(() => Element | null) | null} place */
  setSettlesAt(place) {
    this.#settlesAt = place;
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
  // would move visible words. Existing-message changes and active compositions
  // retain the hold. A pinned reply can absorb growth at the thread's end, but cannot
  // absorb changes above it or settlement replacing the reply itself.
  /** @param {import("./held-news.js").ThreadChange} change */
  newsMoves({ news, changed, joined, folds, appendedAtEnd, footFold }) {
    // Settling moves the card between the seat's open threads and its Resolved
    // disclosure, so it grows the seat where the card lands as well as where it stood.
    const lands = news.settled ? this.#settlesAt?.() : null;
    if (lands && growthIsSeen(lands)) return true;
    // Folded in its seat's closed Resolved disclosure, the card moves nothing as it
    // changes otherwise.
    if (this.#fold) return false;
    const pinned = pinnedReply(this.#reply?.node);
    // An answer's own fold of the progress run at the thread's end changes only the
    // thread's foot, as the answer's arrival does, unless the user is on a message
    // the fold would put away, by focus or by a selection reaching into it.
    const foot =
      footFold &&
      !folds.messages.some((key) => currentLocationTouches(this.#messageNode(key)));
    // The margin's floating card grows at one of its own edges: the one its placement
    // does not hold (card-anchor.js, whose send hold arriving words end).
    // News shows at once only where it changes the thread's end and the card holds its
    // top for it with the user not writing in it: the card grows down, moving its reply
    // row and nothing above. A change to the last message is such news where it is a
    // reply still streaming, or where the transcript, at its cap and scrolled to its
    // end, follows it there (thread-preview.js). Anything else would move the head row
    // or the messages being read, so it waits. A settlement keeps the editor it
    // interrupts, as every thread keeps its reply box.
    if (this.#model?.surface === "margin") {
      if (news.settled) return false;
      const last = this.#model.messages.at(-1);
      const list = this.#transcript.node;
      const follows = list.scrollHeight > list.clientHeight + 0.5 && atScrollEnd(list);
      const atEnd =
        (!news.appended || appendedAtEnd) &&
        !news.summaries &&
        [...changed].every(
          (key) => key === last?.key && (last.provisional || follows),
        ) &&
        (foot || (!folds.messages.length && !folds.summaries.length));
      return (
        growthIsSeen(this.node) &&
        (!atEnd || Boolean(this.#marginControls?.anchor.newsMoves(joined)))
      );
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
    // Capture the current words only when news starts waiting, before its update
    // removes a receipt. This allocation lives with the held view, not its reading.
    if (model.news && !prior?.news) this.#retainHeaderSlot({ observe: false });
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
    const marginControls = model.surface === "margin" ? this.#marginControls : null;
    if (marginControls && prior)
      marginControls.anchor.presented(threadChange(prior, model)?.joined);
    // Where the settlement stands:
    // - on a margin card, its own controls row, which also stands the notice before
    //   Previous and Next: its own place with the thread's facts, as the floating
    //   panel's head holds it (the user's choice, 16 October), rather than over the end
    //   of the message head beside it. The notice takes the room the heads leave it
    //   (`#fitMarginNews`).
    // - elsewhere, the head's controls row, which reserves the room of one icon control
    //   (shadow.css, `--lf-thread-action-room`) beside the first message's own
    //   controls. A foot row of its own drew resolved threads unlike open ones.
    const notice = this.#news;
    if (model.news) notice.set(model.news);
    const news = model.news ? notice.node : nothing;
    // Its id names the surface too (`drawnThreadId`).
    keeps(this.node, "data-thread", model.id);
    keeps(this.node, "data-resolved", model.resolved);
    keeps(this.node, "data-attempt", model.attempt || null);
    // A card is itself where a send or a walk stands the user, so it carries the
    // thread's name.
    keeps(this.node, "role", "group");
    keeps(this.node, "aria-label", `Thread, ${model.summary.topic}`);
    const settlement = model.settlement
      ? this.#settlement(model, model.settlement)
      : nothing;
    const threadActions =
      marginControls || model.settlement || model.news
        ? html`<span class="lf-thread-meta-actions">
            ${marginControls ? news : nothing} ${marginControls?.nav ?? nothing}
            ${marginControls?.expand ?? nothing}${settlement}
            ${marginControls?.close ?? nothing}
          </span>`
        : nothing;
    const handedOn = this.#transcript.present(model, {
      arrived: Boolean(prior),
      appends: model.surface === "margin",
    });
    this.#reply ??= this.#createReply(model);
    // In the head place the notice is a box of its own on the first header's line,
    // anchored to the header beside the controls' box at its end (surfaces.css,
    // `.lf-thread-content > .lf-thread-news`); its words change in place.
    keeps(notice.node, "data-lf-reflow", marginControls ? null : "text");
    const body = html`
      ${threadTodos(model.todos, (id) => this.#commands.todos.done(id))}${
        this.#transcript.node
      }
      ${
        threadActions !== nothing
          ? marginControls
            ? html`<div class="lf-margin-thread-controls">${threadActions}</div>`
            : html`${news}
                <div class="lf-thread-controls" data-lf-reflow="text">
                  ${threadActions}
                </div>`
          : nothing
      }
    `;
    render(
      html`
        ${
          model.surface === "margin"
            ? body
            : html`<div class="lf-thread-content">${body}</div>`
        }
        ${this.#continuity?.gap ?? nothing} ${this.#reply.node}
      `,
      this.node,
    );
    if (!marginControls && model.news)
      measure(this.node, () => this.#retainHeaderSlot());
    else this.#releaseHeaderSlot();
    if (marginControls && model.news) measure(this.node, () => this.#watchMarginNews());
    else this.#releaseMarginNews();
    this.#continuity?.after(bodyPlace);
    // The reply box's empty words follow the settlement (`#createReply`).
    if (prior && Boolean(prior.resolved) !== Boolean(model.resolved))
      this.#reply.sync();
    // A page thread whose render took the user's place puts them in its reply, or on
    // the thread itself.
    // Handing it on is the card's own act, which the list holding the card defers to.
    // A progress disclosure the user was on that this render replaced hands them to
    // its successor (transcript.js).
    restoreFocus?.(
      handedOn
        ? () => (focusDestination(handedOn, "return"), true)
        : () =>
            this.#commands.landInThread(this.node.querySelector(SAY_BOX) ?? this.node),
    );
    return this.node;
  }

  // A margin card's notice stands in its actions row, whose track takes its width from
  // the heads' track (annotation-chrome.css), so the notice takes only the room the
  // heads leave beside each one's name and time, its padding and its controls' room
  // included. A head lends that room to its words while its controls hide, and the
  // controls stand over whatever runs into it when they show (controls.css), so the
  // fit keeps it, and Edit covers no name or time beside news. Where the room is short
  // of its count the notice is cut (held-news.js, `newsNotice`).
  // The room is the notice's width and the narrowest head's spare width together,
  // which the two tracks trade one for one, so drawing the notice at it changes nothing
  // it was read from. A notice at a finger's floor can still leave a head short, and
  // the head then gives up, in order, its controls' room, its time and its name
  // (annotation-chrome.css): where less than an em of the name would show, none does
  // (`data-lf-nameless`), so no sliver of a letter or an ellipsis stands in the head.
  #fitMarginNews() {
    const notice = this.#news.node;
    const heads = [];
    for (const head of this.node.querySelectorAll(
      ".lf-thread-transcript .lf-msg-head",
    )) {
      if (!head.checkVisibility()) continue;
      const style = getComputedStyle(head);
      const name = head.querySelector(":scope > b");
      const time = head.querySelector(":scope > .lf-msg-meta > time");
      // The controls' room is as wide as their group, and the head lends it to its
      // words unless it is held whole (controls.css).
      const room = head.querySelector(":scope > .lf-msg-control-room");
      const controls =
        room?.querySelector(":scope > .lf-msg-controls")?.getBoundingClientRect()
          .width ?? 0;
      const held =
        room && getComputedStyle(room).minInlineSize !== "0px" ? controls : 0;
      const need =
        parseFloat(style.paddingInlineStart) +
        parseFloat(style.paddingInlineEnd) +
        controls +
        wordsWidth(name) +
        (name && time ? parseFloat(style.columnGap) : 0) +
        wordsWidth(time);
      heads.push({
        name,
        need,
        spare: head.getBoundingClientRect().width - need,
        // What the head gives up before its name: its time, and its controls' room
        // where that isn't held whole.
        yields: controls - held + wordsWidth(time),
      });
    }
    if (!heads.length || !notice.isConnected) {
      this.#clearMarginNews();
      return;
    }
    const width = notice.getBoundingClientRect().width;
    const spare = Math.min(...heads.map((head) => head.spare));
    notice.style.setProperty("--lf-news-room", roomPx(Math.max(0, width + spare)));
    const taken = notice.getBoundingClientRect().width - width;
    for (const { name, spare, yields } of heads) {
      if (!name) continue;
      const shown = wordsWidth(name) + Math.min(0, spare - taken + yields);
      keeps(
        name,
        "data-lf-nameless",
        shown < parseFloat(getComputedStyle(name).fontSize) ? "" : null,
      );
    }
  }

  // A render fits it again, and a head's time changes size while news waits as it
  // ticks on from "just now". The notice and a name change size
  // because of the fit itself, so watching them would deliver the fit its own change,
  // and a time's change fits it in the next frame, since the fit resizes boxes the
  // observer's delivery has already passed.
  #watchMarginNews() {
    this.#marginNews.disconnect();
    for (const time of this.node.querySelectorAll(
      ".lf-thread-transcript .lf-msg-head > .lf-msg-meta > time",
    ))
      this.#marginNews.observe(time);
    this.#fitMarginNews();
  }

  #releaseMarginNews() {
    this.#marginNews.disconnect();
    this.#clearMarginNews();
  }

  // The fit writes the notice's room and each name it hides, and a message's head
  // outlives the notice (each MessageView keeps its own, messages.js), so both go together.
  #clearMarginNews() {
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
    this.#news.node.removeAttribute("data-room");
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
      // While news stands, the notice keeps the width of the count it first showed, so
      // later news never narrows or widens it under the pointer.
      if (!notice.hasAttribute("data-room")) notice.dataset.room = news.text;
      const shown = shownRect(header, new Map());
      if (shown)
        notice.style.setProperty(
          "--lf-thread-news-visible-end",
          layoutPx(Math.max(0, shown.right - box.left)),
        );
    } else notice.removeAttribute("data-room");
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
      reopen && model.resolvedBy ? `${model.resolvedBy} · ${state.label}` : state.label;
    return html`<button
      ${offeredAction("symbol", reopen ? "lf-reopen" : "lf-resolve", label, {
        action: reopen ? "reopen" : "resolve",
      })}
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
    this.#showNews();
    if (!model.resolved) dismissReply(model.key);
    void settleThread({
      parent: () => this.#model.id,
      key: model.key,
      resolved: model.resolved,
      prepareLanding:
        model.surface === "margin" && !model.resolved
          ? (this.#marginControls?.prepareLanding ?? null)
          : this.#prepareThreadLanding,
      ...this.#commands.settlement,
    }).catch(() => {});
  };

  // Reopening lands in the reply on every card, even when Lit retains the pressed
  // button. A page thread also moves into or out of its seat's Resolved disclosure
  // (inline.js), so keep its destination in view once the departing pixels finish.
  #prepareThreadLanding = () => {
    const reopening = this.#model.resolved;
    const mayLand = retainUserIntent({
      source: this.node,
      available: () => this.node.isConnected,
    });
    return async () => {
      // The summary is semantically available at once, but a long departing card
      // still puts it below the viewport. Keep this gesture's original authority
      // while its pixels leave; a later user move still vetoes the landing.
      await this.#retirement?.catch(() => {});
      const place = this.#fold?.querySelector(":scope > summary") ?? this.node;
      if (!mayLand() || !currentLocationIn(place)) return false;
      if (reopening)
        this.#commands.landInThread(this.node.querySelector(SAY_BOX) ?? this.node);
      const control = focused();
      if (this.#model.surface !== "margin" && control)
        scrollThreadIntoView(place, control);
      return true;
    };
  };

  // Every thread keeps its reply box. A resolved thread's says that a reply reopens it
  // (events.md), as the floating panel's field does.
  /** @param {ThreadViewModel} model */
  #createReply(model) {
    const commands = this.#commands.reply;
    return createReplyView(
      model.key,
      {
        ...commands,
        actions: {
          ...commands.actions,
          reply: (key, text, options) => {
            // The operation owns this promise before it publishes the local turn.
            const anchor = this.#marginControls?.anchor;
            anchor?.sending(options.attempt);
            const flight = commands.actions.reply(key, text, options);
            if (!flight) anchor?.writing();
            return flight;
          },
        },
      },
      () => this.repaint(),
      {
        hint: () => (this.#model?.resolved ? "Reply to reopen" : "Reply"),
        editLast: this.#rewrites.editLast,
        // A margin card moves with the send it presents (thread-preview.js).
        sending: () => this.#marginControls?.sending?.(),
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
    this.#sizes.disconnect();
    this.#releaseHeaderSlot();
    this.#marginNews.disconnect();
    this.#continuity?.release();
    this.retire();
    this.#reply?.dispose();
    this.#reply = null;
  }
}
