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
import { anchorLabel, messageReading, threadSummary } from "./messages.js";
import { generatedElement, offeredAction } from "../widget-elements.js";
import { measure } from "../shown-box.js";
import { keeps, layoutPx, roomPx } from "../keeps.js";
import { commandsOn } from "../keyboard/scopes.js";
import { PRESS } from "../keyboard/bindings.js";
import {
  createReplyView,
  replyIsEditing,
  replyAvailable,
  dismissReply,
  threadHoldsDraft,
} from "./replies.js";
import { atScrollEnd } from "../scrolling.js";
import { settleThread } from "./folding.js";
import { answeredInWords } from "../obligations/model.js";
import { SAY_BOX } from "./selectors.js";
import { threadAttention, todoLabel, workflowLabel } from "./workflow.js";
import { agentName } from "../semantic-state.js";
import { growthIsSeen, shownRect } from "../geometry.js";
import { ago, shortAgo } from "../presence.js";
import { retainUserIntent } from "../user-intent.js";
import { scrollThreadIntoView, replyPinned } from "./reply-landing.js";
import { threadRewrites } from "./message-edit.js";
import { newsNotice, threadChange } from "./held-news.js";
import { ReplyContinuity } from "./reply-continuity.js";
import { Transcript } from "./transcript.js";

// What a thread's head says of the words it is about: the quote, whether it still
// stands on the page, and its hover. A card's head draws it, and so does the floating
// panel's view of a thread (floating-panel.js, `quoteHead`).
export function quoteReading(thread, anchors) {
  const placement = anchors.placedAt(thread.id);
  // A version that rewrote the quoted words left the thread on their section
  // (`rewritten_from`, events.md); the head still names those words, marked as changed.
  const rewritten = thread.rewritten_from;
  const quoted = rewritten ?? thread.detached_from ?? thread.anchor;
  const label = anchorLabel(quoted, thread.root.about);
  if (!label) return null;
  const anchored = Boolean(thread.anchor) || Boolean(thread.detached_from);
  const found = !thread.detached_from && Boolean(placement);
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
// last message logged before them (`workingPlace`): as the face of the progress run
// it follows, or as a face of its own (transcript.js). An answer already
// streaming at the thread's end replaces the working message and pending progress.
const STOPPED = new Set(["ended", "stale", "interrupted"]);
function workingMessage(thread, attention, messages) {
  if (thread.resolved || messages.at(-1)?.provisional) return null;
  const covered = new Set(thread.summaries.flatMap(({ covers }) => covers));
  const pending = messages.filter(
    (message) => message.progress && !covered.has(message.id),
  );
  const said = pending.at(-1)?.body.plainText ?? "";
  // Where each message was said: its own place in the log, which a later edit of it
  // leaves; a message the log does not hold yet comes after everything it does.
  const saidAt = new Map(thread.msgs.map(({ id, seq }) => [id, seq ?? Infinity]));
  const workflows = thread.workflows ?? [];
  const running = workflows.find(
    (workflow) =>
      !workflow.condition && ["working", "replying"].includes(workflow.stage),
  );
  const stopped = workflows.find(
    (workflow) => STOPPED.has(workflow.condition?.kind) && workflow.detail,
  );
  const todo = thread.todos.find((open) => open.running);
  const [words, at, live, condition, agent] = running?.detail
    ? [running.detail, running.detail_seq, true, null, running.agent]
    : running
      ? [said, saidAt.get(pending.at(-1)?.id), true, null, running.agent]
      : todo
        ? [todo.running.text, todo.running.seq, true, null, null]
        : stopped
          ? [
              stopped.detail,
              stopped.detail_seq,
              false,
              workflowLabel(stopped, agentName()),
              stopped.agent,
            ]
          : [said, saidAt.get(pending.at(-1)?.id), false, null, null];
  if (!words || (!pending.length && !live && !condition)) return null;
  const agentMessage = messages.findLast((message) => message.author === "agent");
  // A workflow's detail is explicit agent work text linked to its exact input. A
  // to-do's line can be user-authored, so it supplies no reply visibility evidence.
  const work = running?.detail ? running : !running && !todo ? stopped : null;
  const progress = !work && (running || (!todo && !stopped)) ? pending.at(-1) : null;
  // Date the words being shown, rather than another message or the workflow's
  // liveness condition. A to-do line has no dated source in the thread reading.
  const timestamp = work?.ts ?? progress?.timestamp ?? null;
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
    after: messages.findLast((message) => saidAt.get(message.id) <= at).key,
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

/** @param {ReturnType<typeof import("./model.js").readThreadRecords>[number]} thread */
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
  const leaves = (message) =>
    asking.has(message.id)
      ? "Waiting on me"
      : message.todo && openTodos.has(message.id)
        ? todoLabel(null)
        : null;
  // Completion comes from the server, including the provisional answer. A held
  // reading keeps progress until its completing reply is among the messages shown.
  const presented = new Set(thread.msgs.map(({ id }) => id));
  const messages = turns(thread)
    .filter((message) => !presented.has(message.completed_by))
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
        ? `✓ Resolved by ${/** @type {{agent?: string}} */ (thread.resolved).agent}`
        : "",
    settlement: Object.freeze({
      kind,
      word,
      label,
    }),
    reply: replyAvailable(thread),
    // The user's open to-dos on the thread, each named at the thread's head with its
    // Done (`threadTodos`), as the floating panel's field names one the user stands on
    // in the page.
    todos: Object.freeze(
      thread.userTodos.map(({ id, title }) => Object.freeze({ id, title })),
    ),
    summaries: Object.freeze(thread.summaries),
    messages: Object.freeze(messages),
    working: workingMessage(thread, attention, messages),
    // The thread this reads, and the same reading of another state of it: the one a
    // seat holding news draws, the thread as it drew it (held-news.js).
    source: thread,
    reread: (held) => threadReading(held, surface, commands),
  });
}

// The width `node`'s words take, at the fraction of a pixel they are laid out at,
// whether or not its box cuts them: a cut name's scrollWidth counts its ellipsis, and a
// whole one's rounds.
function wordsWidth(node) {
  if (!node) return 0;
  const range = document.createRange();
  range.selectNodeContents(node);
  return range.getBoundingClientRect().width;
}

export class ThreadView {
  #commands;
  #messageCommands;
  #rewrites;
  // The model this card shows. Commands follow it explicitly; mechanical reads of
  // this paint's output must not subscribe the presenter that writes it.
  #shown = signal(null);
  get #model() {
    return this.#shown.peek();
  }
  set #model(model) {
    this.#shown.value = model;
  }
  #transcript;
  #reply = null;
  #replyShown = false;
  #draftFrame = 0;
  #settlesAt = null;
  #marginControls = null;
  // What a thread in the page's flow holds back says so in its control row (held-news.js).
  #news = newsNotice();
  #continuity = null;
  #received = null;
  #headerSlot = null;
  #observedHeader = null;
  #sizes = sizeObserver(() => this.#retainHeaderSlot());
  #marginNews = sizeObserver(() => nextRender(() => this.#fitMarginNews()));

  constructor(commands) {
    this.#commands = commands;
    // A rewrite of one of the user's messages (`message-edit.js`). Opening or closing
    // it paints at once, so its editor takes or gives back the focus in the same press.
    this.#rewrites = threadRewrites({
      thread: () => this.#model.key,
      views: () => this.#transcript.views,
      paint: () => this.repaint(),
      send: (id, text, options) =>
        commands.reply.actions.edit(this.#model.key, id, text, options),
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

  setMarginControls(controls) {
    this.#marginControls = controls;
  }

  get model() {
    return this.#model;
  }

  // Local disclosure and draft changes repaint the complete received descriptor,
  // never feed a held presentation back into the news owner's input.
  repaint() {
    this.#paint(this.#received);
  }

  // The seat owns placement, including while the card's outgoing pixels still fold
  // outside its Resolved disclosure. Landing and held news read that same placement.
  #foldedInto = null;
  #retirement = null;
  setFoldedInto(group, retirement = null) {
    this.#foldedInto = group;
    this.#retirement = retirement;
  }
  get #fold() {
    return this.#foldedInto && !this.#foldedInto.open ? this.#foldedInto : null;
  }

  // Where the seat's flow would grow if the card's settlement changed (inline.js), read
  // as the news comes: before the seat's next open thread, or before its Resolved
  // disclosure, for a resolved card that reopens; the disclosure, while it stands open,
  // for an open card that resolves into it. Null where nothing the seat draws grows.
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
  #messageNode(key) {
    return this.#fold ? null : this.#transcript.messageNode(key);
  }

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
  newsMoves({ news, changed, joined, folds, appendedAtEnd, footFold }) {
    // Settling moves the card between the seat's open threads and its Resolved
    // disclosure, so it grows the seat where the card lands as well as where it stood.
    const lands = news.settled ? this.#settlesAt?.() : null;
    if (lands && growthIsSeen(lands)) return true;
    // Folded in its seat's closed Resolved disclosure, the card moves nothing as it
    // changes otherwise.
    if (this.#fold) return false;
    const pinned = replyPinned(this.#reply?.node);
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
    // interrupts on its own (`replyAvailable`).
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
        (!atEnd || this.#marginControls?.anchor.newsMoves(joined))
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
  shows(model) {
    const prior = this.#received;
    if (!prior || !this.#drawnWith) return false;
    // A card holding news draws on every pass: what it shows then moves with time and
    // the reader, not with its reading.
    if (this.#model?.news) return false;
    const { reread: _priorReread, ...was } = prior;
    const { reread: _reread, ...now } = model;
    const outside = this.#outside(model);
    return (
      share(was, now) === was &&
      outside.every((part, index) => part === this.#drawnWith[index])
    );
  }

  #drawnWith = null;

  present(model, options = {}) {
    return this.#paint(model, options, true);
  }

  // The caller knows whether this is a publication or a local repaint. Only a
  // publication allocates passive space; disclosures and editors stay intrinsic.
  #paint(model, _options = {}, published = false) {
    this.#received = model;
    this.#drawnWith = this.#outside(model);
    const prior = this.#model;
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
    const reply = model.reply || replyIsEditing(model.key);
    this.#replyShown = reply;
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
    const settlement = model.settlement ? this.#settlement(model) : nothing;
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
    if (reply && !this.#reply) this.#reply = this.#createReply(model);
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
        ${reply ? (this.#continuity?.gap ?? nothing) : nothing}
        ${reply ? this.#reply.node : nothing}
      `,
      this.node,
    );
    if (!marginControls && model.news)
      measure(this.node, () => this.#retainHeaderSlot());
    else this.#releaseHeaderSlot();
    if (marginControls && model.news) measure(this.node, () => this.#watchMarginNews());
    else this.#releaseMarginNews();
    this.#continuity?.after(bodyPlace);
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
  // of its first fact the notice says one count instead (held-news.js, `newsNotice`).
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
      const need =
        parseFloat(style.paddingInlineStart) +
        parseFloat(style.getPropertyValue("--lf-msg-control")) +
        wordsWidth(name) +
        (name && time ? parseFloat(style.columnGap) : 0) +
        wordsWidth(time);
      heads.push({
        name,
        need,
        spare: head.getBoundingClientRect().width - need,
        // What the head gives up before its name.
        yields:
          parseFloat(style.getPropertyValue("--lf-msg-control")) + wordsWidth(time),
      });
    }
    if (!heads.length || !notice.isConnected) {
      notice.style.removeProperty("--lf-news-room");
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
    this.#news.node.style.removeProperty("--lf-news-room");
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
    if (observe && !this.#model?.news) {
      this.#releaseHeaderSlot();
      return;
    }
    const content = this.node.querySelector(":scope > .lf-thread-content");
    const first = content?.querySelector(
      ":scope > .lf-thread-transcript > :nth-child(1 of .lf-msg, .lf-thread-checkpoint)",
    );
    /** @type {HTMLElement | null} */
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
    if (
      this.#headerSlot?.header !== header ||
      this.#headerSlot.boxWidth !== box.width ||
      !this.#model?.news
    ) {
      // A new width is a user reflow. Read its unconstrained allocation on an
      // invisible copy, without transient writes to real words.
      const resizing = allocates && this.#headerSlot?.header === header;
      let reading = header;
      if (resizing) {
        reading = /** @type {HTMLElement} */ (header.cloneNode(true));
        Object.assign(reading.style, {
          position: "absolute",
          visibility: "hidden",
          inlineSize: layoutPx(box.width),
          margin: "0",
          anchorName: "none",
        });
        for (const node of /** @type {HTMLCollectionOf<HTMLElement>} */ (
          reading.children
        )) {
          node.classList.toggle("lf-held-header-item", false);
          node.style.removeProperty("--lf-held-header-width");
        }
        header.after(reading);
      } else this.#releaseHeaderItems();
      const widths = [...reading.children].map(
        (node) => node.getBoundingClientRect().width,
      );
      if (resizing) reading.remove();
      const items = [
        .../** @type {HTMLCollectionOf<HTMLElement>} */ (header.children),
      ].map((node, index) => ({
        node,
        width: widths[index],
      }));
      this.#headerSlot = { header, items, boxWidth: box.width, held: observe };
      for (const { node, width } of allocates ? items : []) {
        // Keep the author's current width before the first held render, while
        // its receipt can still take unused room on that first presentation.
        if (!observe && node.classList.contains("lf-msg-meta")) continue;
        node.classList.toggle("lf-held-header-item", true);
        node.style.setProperty("--lf-held-header-width", layoutPx(width));
      }
    }
    if (observe && !this.#headerSlot.held) {
      for (const item of allocates ? this.#headerSlot.items : []) {
        if (item.node.classList.contains("lf-msg-meta"))
          item.width = Math.max(item.width, item.node.getBoundingClientRect().width);
        item.node.classList.toggle("lf-held-header-item", true);
        item.node.style.setProperty("--lf-held-header-width", layoutPx(item.width));
      }
      this.#headerSlot.held = true;
    }
    // The notice's readings are lengths from the header's start: where the words end,
    // which the notice starts after, and where the header's line stops showing, which
    // it stops before (surfaces.css, `.lf-thread-content > .lf-thread-news`).
    const notice = this.#news.node;
    const right = Math.max(
      box.left,
      ...this.#headerSlot.items.map(({ node }) => node.getBoundingClientRect().right),
    );
    notice.style.setProperty("--lf-thread-news-start", layoutPx(right - box.left));
    if (this.#model.news) {
      // While news stands, the notice keeps the width of the words it first showed, so
      // later news never narrows or widens it under the pointer; longer news is cut.
      if (!notice.hasAttribute("data-room"))
        notice.dataset.room = this.#model.news.label;
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
  // done on a resolved thread (browser/AGENTS.md, "Visual grammar"), in one corner:
  // settling moves nothing beside it. A margin card once said Reopen as a word.
  #settlement(model) {
    const state = model.settlement;
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
          ? this.#marginControls?.prepareLanding
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
      if (this.#model.surface !== "margin") scrollThreadIntoView(place, focused());
      return true;
    };
  };

  #createReply(model) {
    // A settled thread keeps its box while a session stands, which every pass and the
    // margin follow (`replyIsEditing`), so a keystroke repaints this card alone.
    const replyChanged = () => {
      if (!this.#reply) return;
      this.#draftFrame ||= nextRender(() => {
        this.#draftFrame = 0;
        if (!this.#reply) return;
        if (this.#model.resolved) this.repaint();
      });
    };
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
        onChange: replyChanged,
        editLast: this.#rewrites.editLast,
        // A margin card moves with the send it presents (thread-preview.js).
        sending: () => this.#marginControls?.sending?.(),
      },
    );
  }

  commit() {
    this.#transcript.commit();
    if (!this.#replyShown && this.#reply) {
      this.#reply.dispose();
      this.#reply = null;
    }
  }

  // The reply being written in this thread, which no view holds, comes into this one
  // once it is `shown` (replies.js, `claim`).
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
