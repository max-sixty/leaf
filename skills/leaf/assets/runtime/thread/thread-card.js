/* One synchronous Lit owner for complete page, outlet and margin threads.

   Every surface uses the same metadata, transcript, message and reply vocabulary.
   Containers own navigation and placement, including whether their transcript scrolls;
   shadow.css owns the conversation's appearance through widget shadow boundaries.
   Conversation flow stays inside a content region, separate from the outer body's
   retained reply space. A margin card instead allocates its own scrolling transcript
   and overlay controls. Thread controls stay outside message and summary folds. MessageView
   owns each complete message, so no container extracts or reparents its header.
   Independent controls overlay its first header line. That line reserves a notice's
   minimum hit area from its first paint; the metadata edge measured before news
   arrives is retained while it waits, including when its workflow receipt goes.
   Each message header text item keeps its allocated width while news waits, so a later
   receipt grows only inside its own clipped box. The first notice may use spare
   room for its new receipt without moving the author or time already shown.

   Immutable descriptors contain generated presentation only. Retained native editors,
   margin controls and frozen message widgets keep their mechanical lifetime outside
   those values. The transcript and each summary checkpoint's originals are retained
   containers whose message lists are placed together (`setChildLists`), so a message
   a summary gathers or releases moves straight across with its frames and focus.
   Rejected: nesting the originals in a `repeat` inside the transcript's `repeat`,
   which rebuilt a gathered message's row and reloaded a frame in it.

   A quotation whose original words are no longer on the page keeps a local
   full-reading disclosure, including when a rewritten section still has a navigation
   destination. Its expansion lives with the card through presentation. The owner
   alone renders its native card root and all generated descendants; a failed
   candidate is restored by presenting its committed descriptor again. It owns title
   gesture policy, outgoing fold paint and local draft repaint. Surfaces receive
   whole-thread geometry readings rather than descendant nodes. */
import { nextRender, sizeObserver } from "../rendering.js";
import { setChildLists, setChildren } from "../dom-children.js";
import {
  holdFocus,
  focusDestination,
  focused,
  standsOn,
  standingIn,
} from "../focus.js";
import { html, render, nothing, share, signal } from "/vendor/browser-runtime.js";
import { turns, threadKey } from "./model.js";
import { anchorLabel, MessageView, messageReading, threadSummary } from "./messages.js";
import { offer, measure } from "../widget-elements.js";
import { keeps, keepsHidden, layoutPx } from "../keeps.js";
import { keys } from "../keyboard/scopes.js";
import { PRESS } from "../keyboard/bindings.js";
import {
  createReplyView,
  replyIsEditing,
  replyAvailable,
  dismissReply,
  threadHoldsDraft,
  writingIn,
} from "./replies.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { atScrollEnd } from "../scrolling.js";
import { settleThread } from "./folding.js";
import { iconTemplate } from "../icons.js";
import { SAY_BOX } from "./selectors.js";
import { renderMarkdown } from "../markdown.js";
import { summaryRanges, withPendingProgress } from "./summary-ranges.js";
import { threadAttention, workflowLabel } from "./workflow.js";
import { growthAfterIsSeen, growthIsSeen, seenRect, shownRect } from "../geometry.js";
import { ago, shortAgo } from "../presence.js";
import { retainUserIntent } from "../user-intent.js";
import { scrollThreadIntoView, replyPinned } from "./reply-landing.js";
import { threadRewrites } from "./message-edit.js";
import { newsNotice } from "./held-news.js";
import { ReplyContinuity } from "./reply-continuity.js";

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
// message while an item in the same thread waits on the user. A message's work speaks before a to-do's, and
// a proactive progress message, which takes no request in hand, gives its own words.
// `live` while the work runs; work whose turn ended or went stale without an answer
// says so beside its last line. The progress messages behind it are gathered by
// `withPendingProgress`, and its disclosure shows them. An answer already
// streaming at the thread's end is the agent's next word, so the working message gives way to it
// and the answer's head holds the disclosure, as it will once its fold arrives.
const STOPPED = new Set(["ended", "stale", "interrupted"]);
function workingMessage(thread, attention, messages) {
  if (thread.resolved || messages.at(-1)?.provisional) return null;
  const covered = new Set(thread.summaries.flatMap(({ covers }) => covers));
  const pending = messages.filter(
    (message) => message.progress && !covered.has(message.id),
  );
  const said = pending.at(-1)?.body.plainText ?? "";
  const workflows = thread.workflows ?? [];
  const running = workflows.find(
    (workflow) =>
      !workflow.condition && ["working", "replying"].includes(workflow.stage),
  );
  const stopped = workflows.find(
    (workflow) => STOPPED.has(workflow.condition?.kind) && workflow.detail,
  );
  const todo = thread.todos.find((open) => open.running);
  const [words, live, condition, agent] = running
    ? [running.detail || said, true, null, running.agent]
    : todo
      ? [todo.running.text, true, null, null]
      : stopped
        ? [stopped.detail, false, workflowLabel(stopped), stopped.agent]
        : [said, false, null, null];
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
    timestamp,
    age: timestamp ? ago(timestamp) : null,
    words: words.trim().replace(/\.$/, ""),
    feedback,
    live,
    condition,
  });
}

/** @param {ReturnType<typeof import("./model.js").readThreadRecords>[number]} thread */
export function threadReading(thread, surface, commands) {
  const resolved = Boolean(thread.resolved);
  // A settlement in flight has already flipped `resolved`, because what the page can
  // draw of a gesture stands in the turn that sends it. The control the user is left
  // looking at is therefore the opposite one, offering to take the gesture back, and it
  // wears the word for that: a delivery status is not the result, so there is no
  // "Resolving…" state to name.
  const settling = Boolean(thread.settling);
  const kind = resolved ? "unresolve" : "resolve";
  const word = resolved ? "Reopen" : "Resolve";
  const label = resolved ? word : "Resolve thread";
  const attention = threadAttention(thread);
  // An answer says what it leaves (an lf-ask, `--todo`); its head says so while that
  // stands: the question the user still owes words to, the to-do still open on the
  // thread.
  const asking = thread.user_prompt?.message;
  const openTodos = new Set(thread.todos.map(({ id }) => id));
  const leaves = (message) =>
    message.id === asking
      ? "Waiting on me"
      : message.todo && openTodos.has(message.id)
        ? "To-do open"
        : null;
  const messages = turns(thread).map((message) =>
    messageReading(message, {
      nativeAuthored: Boolean(commands.nativeAuthored),
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
    // A title comes from the agent's answer or beside it, so an untitled thread
    // waits for one only while the agent's work on it is under way. A turn that
    // ended, stalled or was never picked up sends none, and the thread reads its
    // opening words.
    titlePending:
      thread.title == null &&
      thread.attention?.kind === "waiting" &&
      thread.attention.reason === "workflow",
    unreadCount: thread.unread.length,
    id: thread.id,
    attempt: thread.root.attempt ?? null,
    surface,
    resolved,
    attention,
    // A waiting thread's status is the stage of one message's workflow, which that
    // message already draws in its own header. The summary repeats it only for the
    // folded row, where no message shows; whose turn it is stays, since no message
    // says that.
    statusFolded:
      attention?.kind === "waiting" &&
      attention.workflow !== null &&
      messages.some((message) => message.workflow?.id === attention.workflow.id),
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
      pending: settling,
    }),
    reply: replyAvailable(thread),
    summaries: Object.freeze(thread.summaries),
    messages: Object.freeze(messages),
    working: workingMessage(thread, attention, messages),
    // The thread this reads, and the same reading of another state of it: the one a
    // seat holding news draws, the thread as it drew it (held-news.js).
    source: thread,
    reread: (held) => threadReading(held, surface, commands),
  });
}

// The working message's contents: the step of work in hand, drawn as a message is,
// with who is working and when those words were posted at its head, but dimmed under
// a passing sheen while the work runs, as a title being generated is. It shows the
// latest step alone: the earlier ones are superseded, and the answer that folds them
// offers them behind its own
// disclosure. It is the transcript's last child, so it stands at the conversation's
// inset on every surface and scrolls with it. Its head wears a message head's face but
// not its class, since it is no message: a message head's places (a margin's sticky
// head, held news) skip it.
function workingView(working) {
  return html`<div class="lf-thread-working-head">
      ${working.who ? html`<b>${working.who}</b>` : nothing}
      ${
        working.timestamp || working.condition
          ? html`<span class="lf-msg-meta"
              >${
                working.timestamp
                  ? html`<time datetime=${working.timestamp}>${working.age}</time>`
                  : nothing
              }
              ${working.condition}</span
            >`
          : nothing
      }
    </div>
    <div class="lf-thread-working-words">${working.words}</div>`;
}

let nextViewId = 0;
export class ThreadView {
  #commands;
  #messageCommands;
  #rewrites;
  // The model this card shows. A signal, because its commands' liveness reads it, and
  // key and button reflection follow what they read (keyboard/scopes.js).
  #shown = signal(null);
  get #model() {
    return this.#shown.value;
  }
  set #model(model) {
    this.#shown.value = model;
  }
  #messages = new Map();
  #reply = null;
  #replyShown = false;
  #draftFrame = 0;
  #settlements = new Map();
  #settlesAt = null;
  #actions = document.createElement("span");
  #transcript = document.createElement("div");
  #working = document.createElement("div");
  #stopWorkingExposure = null;
  // Each pending progress range's covered message ids, as last drawn, so a fold that
  // takes the range over can take its disclosure state with it.
  #pendingCovers = new Map();
  #pendingOpen = false;
  #checkpoints = new Map();
  #expandedSummaries = new Set();
  #marginControls = null;
  #viewId = ++nextViewId;
  // What a thread in the page's flow holds back says so in its control row (held-news.js).
  #news = newsNotice();
  #continuity = null;
  #received = null;
  #headerSlot = null;
  #observedHeader = null;
  #sizes = sizeObserver(() => this.#retainHeaderSlot());

  constructor(commands) {
    this.#commands = commands;
    // A rewrite of one of the user's messages (`message-edit.js`). Opening or closing
    // it paints at once, so its editor takes or gives back the focus in the same press.
    this.#rewrites = threadRewrites({
      thread: () => this.#model.key,
      views: () =>
        (this.#model?.messages ?? []).flatMap(
          ({ key }) => this.#messages.get(key) ?? [],
        ),
      paint: () => this.repaint(),
      send: (id, text, options) =>
        commands.reply.actions.edit(this.#model.key, id, text, options),
      box: () => this.node.querySelector(SAY_BOX),
      home: () => this.node,
      // Opening a rewrite shows what the thread holds (held-news.js), and unfolds a
      // summary holding the message, since it opens to be seen.
      opening: (id) => {
        this.#showNews();
        const folded = this.#model?.summaries.find(({ covers }) => covers.includes(id));
        if (folded) this.#expandedSummaries.add(folded.id);
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
    this.#continuity = new ReplyContinuity(this.node);
    this.node.tabIndex = -1;
    this.node.classList.add("lf-page-thread", "lf-ui");
    this.node.dataset.lfRuntime = ""; // passages.js, leafSurface
    this.node.dataset.lfGen = "1";
    this.node.dataset.lfOffer = "";
    this.#actions.className = "lf-thread-meta-actions";
    this.#transcript.className = "lf-thread-transcript";
    this.#working.className = "lf-thread-working";
    // The transcript's last child, growing at its foot as steps come (shift_watch.js).
    this.#working.dataset.lfAppendTail = "";
    this.#working.setAttribute("aria-live", "polite");
    this.node.addEventListener("lf-reveal", (event) => {
      /** @type {HTMLElement | undefined} */
      const message = event.detail?.target?.closest?.(".lf-msg[data-lf-summary]");
      const id = message?.dataset.lfSummary;
      if (!id || this.#expandedSummaries.has(id)) return;
      this.#expandedSummaries.add(id);
      this.repaint();
    });
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

  // What holds the card folded away: the closed Resolved disclosure its seat gathers it
  // in (inline.js).
  get #fold() {
    const group = this.node.parentElement;
    return group?.matches(".lf-resolved-threads:not([open])") ? group : null;
  }

  // Where the seat's flow would grow if the card's settlement changed (inline.js), read
  // as the news comes: before the seat's next open thread, or before its Resolved
  // disclosure, for a resolved card that reopens; the disclosure, while it stands open,
  // for an open card that resolves into it. Null where nothing the seat draws grows.
  setSettlesAt(place) {
    this.#settlesAt = place;
  }

  // The last of the thread a reader can see, after which its news grows: the last
  // node its transcript shows, which is the working message while one stands, and none
  // while the thread is folded. Progress behind the working message and originals
  // behind a closed checkpoint stand in the transcript unrendered, so the last message
  // alone may have no box to grow after. A card folded in its seat's Resolved
  // disclosure draws nothing at all.
  get #foot() {
    if (this.#fold) return null;
    return (
      [...this.#transcript.children].findLast((node) => node.checkVisibility()) ?? null
    );
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
    if (this.#fold) return null;
    return this.#messages.get(key)?.node ?? null;
  }

  // The checkpoint a summary the thread draws stands in; none while the thread is
  // folded.
  #summaryNode(id) {
    if (this.#fold) return null;
    return this.#checkpoints.get(id)?.node ?? null;
  }

  ownsMessage(id) {
    return (
      this.#model?.id === id ||
      this.#model?.messages.some((message) => message.id === id)
    );
  }

  // The surface follows the whole thread; only this owner locates its message and
  // reply regions. Geometry readings carry no descendant nodes across that boundary.
  incomingTail(prior, next) {
    const known = new Set(prior.messages.map((message) => message.key));
    const incoming = next.messages.filter(
      (message) => message.author === "agent" && !known.has(message.key),
    );
    const latest = prior.messages.at(-1);
    const nextLatest = next.messages.at(-1);
    const grown =
      latest?.key === nextLatest?.key &&
      nextLatest?.author === "agent" &&
      latest.body.text !== nextLatest.body.text;
    if (!incoming.length && !grown) return null;
    const node = latest && this.#messageNode(latest.key);
    if (!node) return null;
    return {
      id: incoming.at(-1)?.id ?? nextLatest.id,
      tailStart: node.getBoundingClientRect().bottom,
      end: this.node.getBoundingClientRect().bottom,
      box: this.#reply?.node.getBoundingClientRect().top,
      pinned: replyPinned(this.#reply?.node),
    };
  }

  messageTail(id) {
    const message = this.#model.messages.find((message) => message.id === id);
    const node = message && this.#messageNode(message.key);
    return node
      ? {
          bottom: node.getBoundingClientRect().bottom,
          end: this.node.getBoundingClientRect().bottom,
        }
      : null;
  }

  // HeldNews compares readings; this owner decides whether their changed regions
  // would move visible words. Existing-message changes and active compositions
  // retain the hold. A pinned reply can absorb growth at the thread's end, but cannot
  // absorb changes above it or settlement replacing the reply itself.
  newsMoves({ news, changed, folds, appendedAtEnd, footFold }) {
    // Settling moves the card between the seat's open threads and its Resolved
    // disclosure, so it grows the seat where the card lands as well as where it stood.
    const lands = news.settled ? this.#settlesAt?.() : null;
    if (lands && growthIsSeen(lands)) return true;
    // Folded in its seat's closed Resolved disclosure, the card moves nothing as it
    // changes otherwise.
    if (this.#fold) return false;
    const pinned = replyPinned(this.#reply?.node);
    // An answer's own fold of the progress run at the thread's end changes only the
    // thread's foot, as the answer's arrival does, unless the user stands on a message
    // the fold would put away, by focus or by a selection reaching into it.
    const foot =
      footFold && !folds.messages.some((key) => standsOn(this.#messageNode(key)));
    // The margin's floating card grows at one of its own edges: the one its placement
    // does not hold (comment-placement.js, `edgeFor`, which a turn joining may change).
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
      const list = this.#transcript;
      const follows = list.scrollHeight > list.clientHeight + 0.5 && atScrollEnd(list);
      const atEnd =
        (!news.appended || appendedAtEnd) &&
        !news.summaries &&
        [...changed].every(
          (key) => key === last?.key && (last.provisional || follows),
        ) &&
        (foot || (!folds.messages.length && !folds.summaries.length));
      const writing = writingIn(
        this.#reply?.node.querySelector(TEXT_FIELD),
        last?.author === "user" && last.pending,
      );
      const turn = news.appended || news.progress > 0 || footFold;
      return (
        growthIsSeen(this.node) &&
        (!atEnd || writing || this.#marginControls?.heldEdge(turn) === "foot")
      );
    }
    const followed = pinned && !news.settled ? this.#foot : null;
    return (
      [
        ...[...changed].map((message) => this.#messageNode(message)),
        (news.appended || news.settled || news.working) && this.#foot,
      ].some((node) => node && node !== followed && growthAfterIsSeen(node)) ||
      [
        ...folds.messages.map((message) => this.#messageNode(message)),
        ...folds.summaries.map((summary) => this.#summaryNode(summary)),
      ].some((node) => node && growthIsSeen(node)) ||
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
    const rewritten = [...this.#messages.values()]
      .filter((view) => view.editing)
      .map(({ node }) => node);
    const bodyPlace = published ? this.#continuity?.before(rewritten) : null;
    const restoreFocus = holdFocus(this.node);
    const standing = focused();
    const priorSummaries = new Set(prior?.summaries.map(({ id }) => id) ?? []);
    // Only a summary that was not present before can swallow what the user
    // holds or is reading, and reading geometry here forces layout.
    if (prior && model.summaries.some(({ id }) => !priorSummaries.has(id))) {
      const heldMessage = prior.messages.find(({ key }) =>
        this.#messages.get(key)?.node.contains(standing),
      )?.id;
      // Being read is being on screen, on whichever surface holds the card.
      const clips = new Map();
      const beingRead = new Set(
        prior.messages
          .filter(({ key }) => {
            const node = this.#messages.get(key)?.node;
            return node?.isConnected && seenRect(node, clips);
          })
          .map(({ id }) => id),
      );
      for (const summary of model.summaries) {
        if (priorSummaries.has(summary.id)) continue;
        if (
          summary.covers.includes(heldMessage) ||
          summary.covers.some((id) => beingRead.has(id))
        )
          this.#expandedSummaries.add(summary.id);
      }
    }
    this.#model = model;
    const reply = model.reply || replyIsEditing(model.key);
    this.#replyShown = reply;
    const marginControls = model.surface === "margin" ? this.#marginControls : null;
    // Where the settlement stands, decided once: the container it renders in and the
    // face it wears both follow from it.
    // - "margin": a margin card's own controls row, which also stands the notice,
    //   whole, before Previous and Next: its own place with the thread's facts, as the
    //   floating panel's head holds it (the user's choice, 16 October), rather than
    //   over the end of the message head beside it.
    // - "head": the head's controls row, which reserves the room of one icon control
    //   (shadow.css, `--lf-thread-action-room`) beside the first message's own
    //   controls, so whatever stands there is the check: Resolve, or Reopen in its place
    //   on a resolved page or outlet thread, so the two states of one toggle share one
    //   face and one corner. The word, wider, ran over the message's pencil, and a foot
    //   row of its own drew resolved threads unlike open ones.
    const settlementPlace = marginControls ? "margin" : "head";
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
    const wanted = new Set(model.messages.map((message) => message.key));
    for (const [key, view] of this.#messages) if (!wanted.has(key)) view.retire();
    const settlement = model.settlement
      ? this.#settlement(model, settlementPlace)
      : null;
    const actions = marginControls
      ? [
          model.news ? notice.node : null,
          marginControls.nav,
          settlement,
          marginControls.close,
        ].filter(Boolean)
      : [settlement].filter(Boolean);
    setChildren(this.#actions, actions);
    const threadActions = actions.length || model.news ? this.#actions : null;
    // A resolved thread holds no work in hand, so its progress stands as messages.
    const summarized = summaryRanges(model.messages, model.summaries);
    const describedRanges = model.resolved
      ? summarized
      : withPendingProgress(summarized);
    const summaries = new Set(
      describedRanges.flatMap((range) => (range.summary ? [range.summary.id] : [])),
    );
    // Progress the reader opened stays open when a fold takes it over or splits it, the
    // answer's or a summary's: every range that now covers one of its messages takes
    // over the disclosure it stood behind, and so does the toggle the reader stood on.
    const successors = new Map();
    for (const [id, covers] of this.#pendingCovers)
      successors.set(
        id,
        describedRanges.filter((range) =>
          range.summary?.covers.some((covered) => covers.includes(covered)),
        ),
      );
    for (const id of [...this.#expandedSummaries])
      for (const range of successors.get(id) ?? [])
        this.#expandedSummaries.add(range.summary.id);
    for (const id of this.#expandedSummaries)
      if (!summaries.has(id)) this.#expandedSummaries.delete(id);
    this.#pendingCovers = new Map(
      describedRanges
        .filter((range) => range.summary?.pending)
        .map((range) => [range.summary.id, range.summary.covers]),
    );
    /** @type {HTMLElement | null} */
    const standingToggle = this.node.querySelector(".lf-summary-expand:focus");
    const rangeState = describedRanges.map((range) => {
      if (range.kind === "message") return range;
      const forced = Boolean(range.summary.protected?.length);
      return {
        ...range,
        expanded: forced || this.#expandedSummaries.has(range.summary.id),
        forced,
        requiredText: "Messages kept open · current work",
      };
    });
    // The progress no answer has folded yet stands hidden behind the working message,
    // open only where a streaming answer's disclosure opens it.
    const pendingRanges = rangeState.filter((range) => range.summary?.pending);
    this.#pendingOpen = pendingRanges.some((range) => range.expanded);
    // Automatic progress folds name the reply that completed them. Its header owns
    // their disclosure, even when a user's intervening reply split the originals. An
    // answer still streaming at the thread's end holds the pending progress's
    // disclosure the same way, until the fold it brings takes the progress over.
    const progressByReply = new Map();
    const streaming = model.messages.at(-1);
    if (streaming?.provisional && pendingRanges.length)
      progressByReply.set(streaming.id, pendingRanges);
    for (const range of rangeState) {
      if (range.kind !== "summary" || !range.summary.trigger || range.forced) continue;
      const trigger = range.summary.trigger;
      if (!progressByReply.has(trigger)) progressByReply.set(trigger, []);
      progressByReply.get(trigger).push(range);
    }
    const messages = model.messages.map((message) => {
      let view = this.#messages.get(message.key);
      if (!view)
        this.#messages.set(
          message.key,
          (view = new MessageView(this.#messageCommands)),
        );
      view.present(message, {
        arrived: Boolean(prior),
        headerControls: progressByReply.has(message.id)
          ? this.#summaryToggle(progressByReply.get(message.id), true)
          : nothing,
      });
      // A reply still streaming at the thread's end grows at its foot as its words
      // come, as the working message does with each step (shift_watch.js).
      keeps(
        view.node,
        "data-lf-append-tail",
        message.provisional && message === model.messages.at(-1) ? "" : null,
      );
      return { key: message.key, node: view.node };
    });
    const messageNodes = new Map(messages.map(({ key, node }) => [key, node]));
    // Each message, in the transcript or its checkpoint.
    const placed = (key, summary) => {
      const node = messageNodes.get(key);
      keeps(node, "data-lf-summary", summary);
      return [node];
    };
    const checkpoints = new Map();
    const transcript = [];
    const transcriptLists = [[this.#transcript, transcript]];
    for (const range of rangeState) {
      if (range.kind === "message") {
        transcript.push(...placed(range.message.key, null));
        continue;
      }
      const id = range.summary.id;
      const checkpoint = this.#checkpoints.get(id) ?? this.#checkpoint(id);
      checkpoints.set(id, checkpoint);
      this.#paintCheckpoint(checkpoint, range);
      transcript.push(checkpoint.node);
      transcriptLists.push([
        checkpoint.originals,
        range.messages.flatMap((message) => placed(message.key, id)),
      ]);
    }
    if (model.working) {
      keeps(this.#working, "data-lf-live", model.working.live ? "" : null);
      render(workingView(model.working), this.#working);
      transcript.push(this.#working);
    }
    this.#stopWorkingExposure?.();
    this.#stopWorkingExposure = model.working?.feedback
      ? this.#commands.read.observeFeedback(
          this.#working.querySelector(".lf-thread-working-words"),
          {
            ...model.working.feedback,
            presentation_kind: "working_words",
            surface: model.surface,
          },
        )
      : null;
    this.#checkpoints = checkpoints;
    keeps(
      this.#transcript,
      "data-lf-reflow",
      model.surface === "margin" ? "append" : null,
    );
    if (reply && !this.#reply) this.#reply = this.#createReply(model);
    const body = html`
      ${this.#transcript}
      ${
        threadActions
          ? marginControls
            ? html`<div class="lf-margin-thread-controls">${threadActions}</div>`
            : html`<div class="lf-thread-controls" data-lf-reflow="text">
                ${news}${threadActions}
              </div>`
          : nothing
      }
    `;
    setChildLists(transcriptLists);
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
    this.#continuity?.after(bodyPlace);
    // A summary gathering the message the user stands on moves it; a page thread whose
    // render took their place puts them in its reply, or on the thread itself.
    // Handing it on is the card's own act, which the list holding the card defers to.
    // A progress disclosure the user stood on that this render replaced, as the
    // answer's head takes it over from the working message, hands them to its successor.
    /** @type {(id: string) => HTMLElement | null} */
    const toggleFor = (id) =>
      this.node.querySelector(
        `.lf-summary-expand[data-summary-toggle="${CSS.escape(id)}"]`,
      );
    const succeeded = standingToggle?.dataset.summaryToggle;
    const toggleHandedOn =
      standingToggle && !standingToggle.isConnected
        ? ([
            succeeded,
            ...(successors.get(succeeded) ?? []).map(({ summary }) => summary.id),
          ]
            .map(toggleFor)
            .find(Boolean) ?? null)
        : null;
    restoreFocus?.(
      toggleHandedOn
        ? () => (focusDestination(toggleHandedOn, "return"), true)
        : () =>
            this.#commands.landInThread(this.node.querySelector(SAY_BOX) ?? this.node),
    );
    return this.node;
  }

  #releaseHeaderSlot() {
    if (this.#observedHeader) this.#sizes.unobserve(this.#observedHeader);
    this.#observedHeader = null;
    this.#releaseHeaderItems();
    this.#news.node.removeAttribute("data-lf-room");
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
    /** @type {HTMLElement | null} */
    const controls = content?.querySelector(":scope > .lf-thread-controls");
    const first = content?.querySelector(
      ":scope > .lf-thread-transcript > :nth-child(1 of .lf-msg, .lf-thread-checkpoint)",
    );
    /** @type {HTMLElement | null} */
    const header =
      first?.querySelector(":scope > .lf-summary-checkpoint > .lf-summary-header") ??
      first?.querySelector(":scope > .lf-msg-head");
    if (!controls || !header) {
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
    const right = Math.max(
      box.left,
      ...this.#headerSlot.items.map(({ node }) => node.getBoundingClientRect().right),
    );
    controls.style.setProperty("--lf-thread-news-start", layoutPx(right - box.left));
    if (this.#model.news) {
      // While news stands, the notice keeps the width of the words it first showed, so
      // later news never narrows or widens it under the pointer; longer news is cut.
      if (!this.#news.node.hasAttribute("data-lf-room"))
        this.#news.node.dataset.lfRoom = this.#model.news.label;
      const line = controls.getBoundingClientRect();
      const shown = shownRect(controls, new Map());
      if (shown)
        controls.style.setProperty(
          "--lf-thread-news-visible-end",
          layoutPx(Math.max(0, shown.right - line.left)),
        );
    } else this.#news.node.removeAttribute("data-lf-room");
  }

  // A summary's checkpoint: a retained section whose head the template draws, and
  // whose originals hold the retained messages the summary covers.
  #checkpoint(id) {
    const node = document.createElement("section");
    node.className = "lf-thread-checkpoint";
    node.dataset.summaryId = id;
    const originals = document.createElement("div");
    originals.id = `lf-summary-originals-${this.#viewId}-${id}`;
    originals.className = "lf-summary-originals";
    node.append(originals);
    return { node, originals };
  }

  #paintCheckpoint({ node, originals }, range) {
    const progress = Boolean(range.summary.trigger || range.summary.pending);
    keeps(node, "data-expanded", range.expanded);
    keepsHidden(node, progress && !range.expanded);
    keepsHidden(originals, !range.expanded);
    render(
      html`${
        progress
          ? nothing
          : html`<div class="lf-summary-checkpoint">
              <div class="lf-summary-header">
                <div class="lf-summary-label">${range.summary.label}</div>
                ${range.forced ? nothing : this.#summaryToggle([range])}
              </div>
              ${
                range.summary.text
                  ? html`<div
                      class="lf-summary-text"
                      .innerHTML=${renderMarkdown(range.summary.text)}
                    ></div>`
                  : nothing
              }
              ${
                range.forced
                  ? html`<div class="lf-summary-required">${range.requiredText}</div>`
                  : nothing
              }
            </div>`
      }
      ${
        progress && range.forced
          ? html`<div class="lf-summary-required">${range.requiredText}</div>`
          : nothing
      }`,
      node,
      { renderBefore: originals },
    );
  }

  // Whether the progress behind the working message stood open when last drawn, opened by
  // the reader or by a search matching it, so each step that joins it shows: held news
  // counts those steps as news here (held-news.js).
  get progressOpen() {
    return this.#pendingOpen;
  }

  #summaryToggle(ranges, progress = false) {
    const ids = ranges.map((range) => range.summary.id);
    const expanded = ranges.every((range) => range.expanded);
    const count = ranges.reduce((total, range) => total + range.messages.length, 0);
    const subject = `${count} ${progress ? "progress" : "earlier"} message${count === 1 ? "" : "s"}`;
    const label = `${expanded ? (progress ? "Hide" : "Collapse") : "Show"} ${subject}`;
    return html`<button
      type="button"
      class="lf-thread-disclosure lf-summary-expand ${
        progress ? "lf-progress-expand" : ""
      }"
      data-lf-room=${progress ? `Show ${subject}` : nothing}
      data-summary-toggle=${ids[0]}
      aria-expanded=${String(expanded)}
      aria-controls=${ids
        .map((id) => `lf-summary-originals-${this.#viewId}-${id}`)
        .join(" ")}
      @click=${() => this.#setSummaryExpanded(ids, !expanded)}
    >
      ${progress ? html`<span>${label}</span>` : label}
    </button>`;
  }

  #setSummaryExpanded(ids, expanded) {
    for (const id of ids) {
      if (expanded) this.#expandedSummaries.add(id);
      else this.#expandedSummaries.delete(id);
    }
    this.repaint();
    const toggle = this.node.querySelector(
      `.lf-summary-expand[data-summary-toggle="${CSS.escape(ids[0])}"]`,
    );
    if (toggle) {
      focusDestination(toggle, "return");
      scrollThreadIntoView(this.node, toggle, "instant");
    }
  }

  // A thread shows Reopen or the completed check in Resolve's place.
  #settlement(model, place) {
    const state = model.settlement;
    const reopen = state.kind === "unresolve";
    // A margin card's controls row draws Resolve as the check and Reopen as the word.
    const icon = place === "head" || (place === "margin" && !model.resolved);
    const face = `${state.kind} ${place}`;
    let button = this.#settlements.get(face);
    if (!button) {
      button = offer(
        "button",
        `lf-btn ${reopen ? "lf-reopen" : "lf-resolve"} ${icon ? "lf-icon-action" : "lf-thread-action"}`,
      );
      button.type = "button";
      this.#settlements.set(face, button);
      const word = reopen ? "Reopen" : "Resolve";
      keys(button, `On a thread's ${word} button`, [
        {
          id: reopen ? "thread.reopen" : "thread.resolve",
          keys: PRESS,
          description: `${word} it`,
          title: word.toLowerCase(),
          control: button,
          when: () => !this.#model.settlement?.pending,
          run: this.#settle,
        },
      ]);
    }
    keeps(button, "aria-busy", state.pending);
    if (icon) {
      const label =
        reopen && model.resolvedBy
          ? `${model.resolvedBy} · ${state.label}`
          : state.label;
      keeps(button, "aria-label", label);
      keeps(button, "title", label);
    }
    render(icon ? iconTemplate("check", "lf-action-icon") : state.label, button);
    return button;
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
        model.surface === "margin"
          ? model.resolved
            ? null
            : this.#marginControls?.prepareLanding
          : this.#prepareInlineLanding,
      ...this.#commands.settlement,
    }).catch(() => {});
  };

  // A thread on the page moves as it settles: a resolved one into its seat's Resolved
  // disclosure, and a reopened one out of it, ahead of it (inline.js). Land where the
  // user went with it, the thread or the summary of the disclosure folding it, around
  // their focus, which a thread too tall to show leaves where it is.
  #prepareInlineLanding = () => {
    const mayLand = retainUserIntent({
      source: this.node,
      available: () => this.node.isConnected,
    });
    const land = (may = mayLand) => {
      const place = this.#fold?.querySelector(":scope > summary") ?? this.node;
      if (!may() || !standingIn(place)) return false;
      scrollThreadIntoView(place, focused());
      return true;
    };
    return { optimistic: () => land(), reverse: land };
  };

  #createReply(model) {
    const replyChanged = () => {
      if (!this.#reply) return;
      this.#draftFrame ||= nextRender(() => {
        this.#draftFrame = 0;
        if (!this.#reply) return;
        if (this.#model.resolved) this.repaint();
        if (this.#model.resolved) this.#commands.reply.changed();
      });
    };
    return createReplyView(model.key, this.#commands.reply, () => this.repaint(), {
      onChange: replyChanged,
      editLast: this.#rewrites.editLast,
    });
  }

  commit() {
    const wanted = new Set(this.#model.messages.map((message) => message.key));
    for (const [key, view] of this.#messages) {
      if (wanted.has(key)) view.commit();
      else {
        view.retire();
        this.#messages.delete(key);
      }
    }
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
    this.#stopWorkingExposure?.();
    this.#stopWorkingExposure = null;
    this.#reply?.cancelDictation();
    for (const view of this.#messages.values()) view.retire();
  }

  dispose() {
    this.#sizes.disconnect();
    this.#releaseHeaderSlot();
    this.#continuity?.release();
    this.retire();
    this.#reply?.dispose();
    this.#reply = null;
  }
}
