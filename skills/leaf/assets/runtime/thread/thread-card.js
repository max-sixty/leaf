/* One synchronous Lit owner for complete panel, page, outlet and margin threads.

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
   room for its new receipt without moving the author or time already standing.

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
import { html, render, nothing, ref } from "../../vendor/browser-runtime.js";
import { turns, threadKey, threadSummary } from "./model.js";
import { anchorLabel, MessageView, messageReading } from "./messages.js";
import { offer, reachedForWords, measure, reserve } from "../widget-elements.js";
import { keeps, keepsHidden, layoutPx } from "../keeps.js";
import { commandsOn, keys } from "../keyboard/scopes.js";
import { PRESS } from "../keyboard/bindings.js";
import { pressIsKeyboardActivation } from "../pointer.js";
import {
  createReplyView,
  replyIsEditing,
  replyAvailable,
  dismissReply,
  threadHoldsDraft,
} from "./replies.js";
import {
  settleThread,
  landGesture,
  foldOut,
  finishFold,
  isFolding,
} from "./folding.js";
import { iconTemplate } from "../icons.js";
import { SAY_BOX } from "./selectors.js";
import { focusThread, threadFocusStop } from "./focus.js";
import { renderMarkdown } from "../markdown.js";
import {
  summaryRanges,
  unreadBoundaries,
  withPendingProgress,
} from "./summary-ranges.js";
import { threadAttention, workflowLabel } from "./workflow.js";
import { growthAfterIsSeen, growthIsSeen, seenRect, shownRect } from "../geometry.js";
import { ago, shortAgo } from "../presence.js";
import { retainUserIntent } from "../user-intent.js";
import { scrollThreadIntoView, replyPinned } from "./reply-landing.js";
import { threadRewrites } from "./message-edit.js";
import { HeldNews, newsNotice } from "./held-news.js";
import { ReplyContinuity } from "./reply-continuity.js";

function quoteReading(thread, anchors) {
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
// banner and Tasks. The work is read from the thread's workflows and to-dos, not from
// whose turn the thread is, since the agent can be working on one message while an ask
// in the same thread waits on the user. A message's work speaks before a to-do's, and
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
  const todo = (thread.todos ?? []).find(({ line }) => line);
  const [words, live, condition, agent] = running
    ? [running.detail || said, true, null, running.agent]
    : todo
      ? [todo.line, true, null, null]
      : stopped
        ? [stopped.detail, false, workflowLabel(stopped), stopped.agent]
        : [said, false, null, null];
  if (!words || (!pending.length && !live && !condition)) return null;
  const agentMessage = messages.findLast((message) => message.author === "agent");
  return Object.freeze({
    who: agent || agentMessage?.by || "Agent",
    words: words.trim().replace(/\.$/, ""),
    live,
    condition,
  });
}

export function threadReading(thread, surface, commands, options) {
  const { visible = true, kept = null, grow = false, search = null } = options;
  const panel = surface === "panel";
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
  // An answer says what it leaves (`--ask`, `--todo`); its head says so while that
  // stands: the prose ask the user still owes, the to-do still open on the thread.
  const asking = thread.user_prompt?.message;
  const openTodos = new Set((thread.todos ?? []).map(({ id }) => id));
  const leaves = (message) =>
    message.ask && message.id === asking
      ? "Waiting on me"
      : message.todo && openTodos.has(message.id)
        ? "To-do open"
        : null;
  const messages = turns(thread).map((message) =>
    messageReading(message, {
      panel,
      nativeAuthored:
        typeof commands.nativeAuthored === "function"
          ? commands.nativeAuthored(message)
          : Boolean(commands.nativeAuthored ?? panel),
      reactions: panel || surface === "outlet" ? message.reactions : null,
      workflows: message.workflows,
      leaves: leaves(message),
    }),
  );
  return Object.freeze({
    key: threadKey(thread),
    summary: threadSummary(thread),
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
    visible,
    // A card the panel keeps though its view no longer admits it, and why ("news" or
    // "draft", thread-list-view.js, `keeping`). While the news that changed it would
    // move what the user sees it waits behind the card's notice (held-news.js); once
    // shown, the card keeps the shape it stood in until it goes, so showing it moves
    // nothing: the room of its reply box, on which an open card's room rests, and the
    // control row above its first message, where Reopen wears Resolve's face.
    kept,
    grow,
    folding: false,
    search,
    quote: panel ? quoteReading(thread, commands.anchors) : null,
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
    resolvedBy:
      thread.resolved?.author === "agent"
        ? `✓ Resolved by ${thread.resolved.agent}`
        : panel
          ? ""
          : "✓ Resolved",
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
    reread: (held) => threadReading(held, surface, commands, options),
  });
}

// The working message's contents: the step of work in hand, drawn as a message is,
// with who is working at its head, but dimmed under a passing sheen while the work
// runs, as a title being generated is. The disclosure of the progress messages it
// stands for holds its head's end, so a new step moves nothing beside it. It is the
// transcript's last child, so it stands at the conversation's inset on every surface
// and scrolls with it.
function workingView(working, toggle) {
  return html`<div class="lf-msg-head">
      ${working.who ? html`<b>${working.who}</b>` : nothing}
      ${
        working.condition
          ? html`<span class="lf-msg-meta">${working.condition}</span>`
          : nothing
      }
      <span class="lf-thread-working-toggle">${toggle}</span>
    </div>
    <div class="lf-thread-working-words" aria-live="polite">${working.words}</div>`;
}

function navigationSummary(model, control) {
  if (model.surface !== "panel") return nothing;
  const pendingTitle = model.titlePending;
  const title = model.summary.topic;
  const latest = model.summary.latest;
  // The reserved box under the title's control carries that control's words.
  const status =
    control ?? (model.resolved ? "Resolved" : model.attention?.label || "");
  const draft = threadHoldsDraft(
    model.key,
    model.messages.map(({ id }) => id),
  );
  // While a title is on its way, the title slot says so in words drawn apart from any
  // title; the theme keeps the placeholder muted while naming is under way.
  // The meta row digests a folded card. What the open card shows elsewhere is marked
  // `data-lf-folded`: the draft stands in the reply box and the unread messages behind
  // their boundary, so typing or an arriving reply doesn't grow the row and move the
  // card under the reader.
  return html`<summary
    class="lf-thread-summary"
    data-lf-reflow="text"
    title=${pendingTitle ? nothing : title}
  >
    <span class="lf-thread-topic" data-lf-pending-title=${pendingTitle ? "" : nothing}
      >${pendingTitle ? "Generating title" : title}</span
    >
    <span class="lf-thread-meta">
      ${
        draft
          ? html`<span class="lf-thread-draft" data-lf-folded>Draft</span>`
          : nothing
      }
      ${
        status
          ? html`<span
              class=${
                control && model.news
                  ? "lf-thread-status lf-thread-notice lf-thread-notice-news"
                  : "lf-thread-status"
              }
              data-lf-settlement=${control ? "" : nothing}
              data-lf-turn=${model.attention?.kind === "needs_user" ? "user" : nothing}
              data-lf-folded=${model.statusFolded ? "" : nothing}
              title=${
                model.attention?.secondary
                  ? `${status} · ${model.attention.secondary}`
                  : status
              }
              >${status}</span
            >`
          : nothing
      }
      ${
        model.unreadCount
          ? html`<span
              class="lf-thread-notice lf-thread-unread"
              data-lf-folded
              aria-label=${`${model.unreadCount} unread`}
              >${model.unreadCount} unread</span
            >`
          : nothing
      }
    </span>
    <span class="lf-thread-trailing">
      ${
        latest
          ? html`<time
              class="lf-thread-recency"
              datetime=${latest}
              title=${`Last message activity ${new Date(latest).toLocaleString()}`}
              aria-label=${`Last message activity ${ago(latest)}`}
              >${shortAgo(latest)}</time
            >`
          : nothing
      }
    </span>
  </summary>`;
}

function readBoundary() {
  const node = document.createElement("div");
  node.className = "lf-read-boundary";
  node.setAttribute("role", "separator");
  return node;
}

function paintBoundary(node, kind) {
  keeps(node, "data-kind", kind);
  keeps(
    node,
    "aria-label",
    kind === "new" ? "New since I last looked" : "End of this new section",
  );
}

let nextViewId = 0;
// The margin card's controls stand over its transcript, so each message's head keeps
// their width clear and its words end before them. Applying that allocation can wrap
// a header and resize the controls' ancestors. Write it in the next rendering pass:
// ResizeObserver cannot deliver those shallower boxes again in the controls' delivery.
const marginControlsSizes = sizeObserver((entries) => {
  nextRender(() => {
    for (const { target, borderBoxSize } of entries)
      target.parentElement?.style.setProperty(
        "--lf-margin-controls-width",
        layoutPx(borderBoxSize[0].inlineSize),
      );
  });
});

// A panel card's reply row is pinned over the turns above it at the list's foot, so the
// card states the row's height and a landing in those turns stops above it (chrome.css).
// The row grows with its draft, so the height is read rather than a token.
const replyRowSizes = sizeObserver((entries) => {
  for (const { target, borderBoxSize } of entries)
    target.parentElement?.style.setProperty(
      "--lf-thread-reply-h",
      `${borderBoxSize[0].blockSize}px`,
    );
});

export class ThreadView {
  #commands;
  #messageCommands;
  #rewrites;
  #model = null;
  #messages = new Map();
  #reply = null;
  #replyShown = false;
  #draftFrame = 0;
  #outletReplyShown = null;
  #settlements = new Map();
  #actions = document.createElement("span");
  #transcript = document.createElement("div");
  #working = document.createElement("div");
  // Each pending progress range's covered message ids, as last drawn, so a fold that
  // takes the range over can take its disclosure state with it.
  #pendingCovers = new Map();
  #pendingOpen = false;
  #checkpoints = new Map();
  #markers = new Map();
  #expandedSummaries = new Set();
  #quoteExpanded = false;
  #marginControls = null;
  #marginControlsRow = null;
  #viewId = ++nextViewId;
  // What a thread in the page's flow holds back says so in its control row (held-news.js).
  #news = newsNotice();
  #titleNews = newsNotice(true);
  #titleControl = null;
  #lastMessage = null;
  #continuity = null;
  #heldNews = null;
  #replyReservation = null;
  #received = null;
  #headerSlot = null;
  #newsReserved = false;
  #observedHeader = null;
  #quoteNode = null;
  #watchQuote = (node) => {
    if (this.#quoteNode) this.#sizes.unobserve(this.#quoteNode);
    this.#quoteNode = node;
    if (node) this.#sizes.observe(node);
  };
  #watchMarginControls = (node) => {
    if (this.#marginControlsRow) marginControlsSizes.unobserve(this.#marginControlsRow);
    this.#marginControlsRow = node;
    if (node) marginControlsSizes.observe(node);
  };
  #sizes = sizeObserver(() => {
    this.#retainHeaderSlot();
    this.#measureQuote();
  });

  constructor(surface, commands) {
    this.#commands = commands;
    // A rewrite of one of the user's messages (`message-edit.js`). Opening or closing
    // it paints at once, so its editor takes or gives back the focus in the same press.
    this.#rewrites = threadRewrites({
      thread: () => this.#model.key,
      views: () =>
        (this.#model?.messages ?? []).flatMap(
          ({ key }) => this.#messages.get(key) ?? [],
        ),
      paint: (message) => this.repaint({ writing: message }),
      send: (id, text, options) =>
        this.#speak(
          () => commands.reply.actions.edit(this.#model.key, id, text, options),
          options.attempt,
          "reply",
        ),
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
    this.node = document.createElement(
      surface === "outlet" || surface === "panel" ? "details" : "div",
    );
    this.#continuity = new ReplyContinuity(this.node);
    // A card draws what its hold releases at once, so an arrival lands on the thread
    // as it now stands (held-news.js).
    if (surface === "panel")
      this.#heldNews = new HeldNews(
        this.node,
        () => this,
        () => {
          // Disclosure changes this card's mechanical reading of the complete received
          // descriptor. Draw it in that operation; later geometry or server readings
          // may supersede a global paint while its widget proof waits.
          this.repaint();
          commands.repaintThread();
        },
      );
    // A panel card's disclosure is the thread list's to write, from its one choice.
    if (surface !== "panel") {
      this.node.tabIndex = -1;
      this.node.classList.add("lf-page-thread", "lf-ui");
      this.node.dataset.lfRuntime = ""; // passages.js, leafSurface
      this.node.dataset.lfGen = "1";
      this.node.dataset.lfOffer = "";
    }
    this.#actions.className = "lf-thread-meta-actions";
    this.#transcript.className = "lf-thread-transcript";
    this.#working.className = "lf-thread-working";
    // Native disclosure opens at the attribute checkpoint; queued toggle may arrive
    // after paint. Release held news here so the first opened body is current,
    // whether a summary, the panel list's choice (a walk to the card) or a
    // programmatic native open revealed it.
    if (surface === "outlet" || surface === "panel")
      new MutationObserver(() => {
        if (this.node.open) this.#model?.news?.open();
        else this.#reply?.cancelDictation();
      }).observe(this.node, { attributeFilter: ["open"] });
    this.node.addEventListener("animationend", () => {
      this.node.classList.toggle("grow", false);
    });
    this.node.addEventListener("lf-reveal", (event) => {
      const message = event.detail?.target?.closest?.(".lf-msg[data-lf-summary]");
      const id = message?.dataset.lfSummary;
      if (!id || this.#expandedSummaries.has(id)) return;
      this.#expandedSummaries.add(id);
      this.repaint();
    });
    if (surface === "panel") {
      // A press on the title chooses at its click, which lands it; focus arriving on the
      // title any other way chooses at once (thread-list-view.js).
      this.node.addEventListener("click", (event) => {
        if (event.target.closest(".lf-thread-summary")?.parentElement !== this.node)
          return;
        event.preventDefault();
        this.#commands.choose();
      });
    }
  }

  setMarginControls(controls) {
    this.#marginControls = controls;
  }

  get model() {
    return this.#model;
  }

  // The next reading draws the thread as it stands, whatever it holds (held-news.js).
  releaseNews() {
    this.#heldNews?.release();
  }

  // Local disclosure and draft changes repaint the complete received descriptor,
  // never feed a held presentation back into the news owner's input.
  repaint(options) {
    this.present(this.#received, options);
  }

  // The last of the thread a reader can see, after which its news grows: a folded
  // outlet's summary, which a reopening unfolds, and otherwise its last message. A
  // closed panel card has none, since news draws nothing its title row shows.
  get #foot() {
    if (this.node.localName === "details" && !this.node.open)
      return this.node.querySelector(":scope > .lf-page-thread-summary:not([hidden])");
    return this.#lastMessage;
  }

  // What the thread draws after its messages that its settlement swaps: the reply box
  // while it stands open, a page thread's row holding Reopen once resolved; none while
  // the thread is folded, where neither shows. A resolved panel card's Reopen stands in
  // its title, which keeps its size.
  get #settlementRow() {
    if (this.node.localName === "details" && !this.node.open) return null;
    return this.node.querySelector(
      ":scope > .lf-thread-reply, :scope > .lf-page-thread-resolved",
    );
  }

  // The node a message the thread draws stands in, after which a change to it grows;
  // none while the thread is folded, where no message shows.
  #messageNode(key) {
    if (this.node.localName === "details" && !this.node.open) return null;
    return this.#messages.get(key)?.node ?? null;
  }

  // The checkpoint a summary the thread draws stands in; none while the thread is
  // folded.
  #summaryNode(id) {
    if (this.node.localName === "details" && !this.node.open) return null;
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
  // would move visible words. An idle open panel card permits a suffix append to move
  // its reply row and later cards. Existing-message changes and active compositions
  // retain the hold. A pinned reply can absorb growth at the thread's end, but cannot
  // absorb changes above it or settlement replacing the reply itself.
  newsMoves({ news, changed, folds, appendedAtEnd, footFold }) {
    const pinned = replyPinned(this.#reply?.node);
    // An answer's own fold of the progress run at the thread's end changes only the
    // thread's foot, as the answer's arrival does, unless the user stands on a message
    // the fold would put away, by focus or by a selection reaching into it.
    const foot =
      footFold && !folds.messages.some((key) => standsOn(this.#messageNode(key)));
    const idleAppend =
      this.#model?.surface === "panel" &&
      this.node.open &&
      !replyIsEditing(this.#model.key) &&
      appendedAtEnd &&
      !news.settled &&
      !news.summaries &&
      !changed.size &&
      (foot || (!folds.messages.length && !folds.summaries.length));
    const followed = (pinned && !news.settled) || idleAppend ? this.#foot : null;
    return (
      [
        ...[...changed].map((message) => this.#messageNode(message)),
        (news.appended || news.settled) && this.#foot,
      ].some((node) => node && node !== followed && growthAfterIsSeen(node)) ||
      (!(idleAppend && foot) &&
        [
          ...folds.messages.map((message) => this.#messageNode(message)),
          ...folds.summaries.map((summary) => this.#summaryNode(summary)),
        ].some((node) => node && growthIsSeen(node))) ||
      Boolean(news.settled && this.#settlementRow && growthIsSeen(this.#settlementRow))
    );
  }

  present(model, { retaining = false, viewChanged = false, writing = null } = {}) {
    this.#received = model;
    const prior = this.#model;
    // The list chooses membership. The complete thread owns its outgoing paint and
    // retirement, keeping the last shown reading until its root gives back its room.
    if (model.surface === "panel") {
      if (retaining || !model.resolved || model.visible) finishFold(this.node);
      const folding =
        !retaining &&
        model.resolved &&
        (isFolding(this.node) ||
          (prior &&
            !viewChanged &&
            !prior.resolved &&
            !prior.folding &&
            prior.visible &&
            !model.visible &&
            foldOut(this.node, this.#commands.repaintThread)));
      if (folding) {
        this.retire();
        model = Object.freeze({
          ...prior,
          id: model.id,
          folding: true,
          grow: false,
          settlement: Object.freeze({ ...prior.settlement, pending: false }),
        });
        if (standingIn(this.node)) focusDestination(this.#commands.listRoot, "return");
      }
    }
    if (this.#heldNews)
      model = Object.freeze(
        this.#heldNews.hold({ threads: [model] }, { row: false }).threads[0],
      );
    // Capture the standing words only when news starts waiting, before its update
    // removes a receipt. This allocation lives with the held view, not its reading.
    if (model.news && !prior?.news) this.#retainHeaderSlot({ observe: false });
    // The messages being rewritten, whose own changes of height the held extent follows
    // (ReplyContinuity): the one a rewrite gesture names, and every one whose rewrite
    // stands open, a save closing it among them.
    const rewritten = new Set(
      [...this.#messages.values()]
        .filter((view) => view.editing)
        .map(({ node }) => node),
    );
    if (writing) rewritten.add(writing);
    const bodyPlace = this.#continuity?.before([...rewritten]);
    const restoreFocus = holdFocus(this.node);
    const standing = focused();
    const priorSummaries = new Set(prior?.summaries.map(({ id }) => id) ?? []);
    // Only a summary that was not standing before can swallow what the user
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
    if (model.quote?.words !== prior?.quote?.words) this.#quoteExpanded = false;
    this.#model = model;
    const reply = model.reply || replyIsEditing(model.key);
    this.#replyShown = reply;
    // News holds the native card's room independently of its editing session.
    if (reply || !model.kept) this.#replyReservation = null;
    else if (!this.#replyReservation && this.#reply?.node.isConnected) {
      const slot = offer("div", "lf-thread-reply");
      slot.style.height = `${this.#reply.node.getBoundingClientRect().height}px`;
      this.#replyReservation = slot;
    }
    const replySlot = reply || Boolean(this.#replyReservation);
    const panel = model.surface === "panel";
    const marginControls = model.surface === "margin" ? this.#marginControls : null;
    // Where the settlement stands, decided once: the container it renders in and the
    // face it wears both follow from it.
    // - "title": a resolved panel card's title holds its one control, Reopen, or, while
    //   the thread holds news, the notice in Reopen's place, since the card has no other
    //   row to draw it in without growing.
    // - "margin": a margin card's own controls row.
    // - "row": a resolved page or outlet thread's own row, with room for the word.
    // - "head": the head's controls row, which reserves the room of one icon control
    //   (shadow.css, `--lf-thread-action-room`) beside the first message's own
    //   controls, so whatever stands there is the check: Resolve, or the Reopen in its
    //   place while a reply box holds a resolved card open. The word, wider, ran over
    //   the message's pencil.
    const settlementPlace = marginControls
      ? "margin"
      : model.resolved && !replySlot && !model.folding
        ? panel
          ? "title"
          : "row"
        : "head";
    const headerSettlement = settlementPlace === "title";
    const notice = headerSettlement ? this.#titleNews : this.#news;
    if (model.news) notice.set(model.news);
    const news = model.news ? notice.node : nothing;
    this.node.classList.toggle("lf-thread-compact", panel);
    const hiding = !model.visible && !model.folding && !this.node.hidden;
    if (hiding) this.retire();
    keepsHidden(this.node, !model.visible && !model.folding);
    this.node.classList.toggle("lf-going", model.folding);
    this.node.classList.toggle("lf-thread", panel && !model.folding);
    // Entry motion belongs to the retained node. Navigation can cancel it; a
    // later descriptor repaint must not resurrect that canceled native cue.
    if (model.folding) this.node.classList.toggle("grow", false);
    else if (!prior && model.grow) this.node.classList.toggle("grow", true);
    this.node.toggleAttribute("inert", model.folding);
    keeps(this.node, panel ? "data-id" : "data-thread", model.id);
    keeps(this.node, "data-resolved", model.resolved);
    keeps(this.node, "data-attempt", model.attempt || null);
    // A page, outlet or margin card is itself where a send or a walk stands the user, so
    // it carries the thread's name; a panel card is named by its summary, which takes
    // the focus there.
    if (!panel) {
      keeps(this.node, "role", this.node.localName === "details" ? null : "group");
      keeps(this.node, "aria-label", `Thread, ${model.summary.topic}`);
    }
    if (model.surface === "outlet" && this.#outletReplyShown !== reply) {
      this.node.toggleAttribute("open", reply);
      // Chrome drops scroll anchoring for a layout that both opens or shuts a `details`
      // and changes what it holds, so an outlet folding above the screen as the agent
      // resolves it would carry what the user reads by the fold's height. Laying out
      // the disclosure before the render below changes the thread lets anchoring take
      // each change.
      this.node.getBoundingClientRect();
      this.#outletReplyShown = reply;
    }
    const wanted = new Set(model.messages.map((message) => message.key));
    for (const [key, view] of this.#messages) if (!wanted.has(key)) view.retire();
    const settlement = model.settlement
      ? this.#settlement(model, settlementPlace)
      : null;
    // The title holds one control, Reopen or the notice in its place, and the card's
    // notice stands there or in a row of its own. Whichever takes the place of the one
    // the user stands on takes them with it, as anything replacing a node hands its
    // focus across.
    const titleControl = headerSettlement ? (model.news ? news : settlement) : null;
    const successor = model.news ? notice.node : titleControl;
    const handedOn =
      standing &&
      standing !== successor &&
      [this.#titleControl, this.#news.node, this.#titleNews.node].includes(standing)
        ? successor
        : null;
    this.#titleControl = titleControl;
    let threadActions = null;
    if (settlementPlace === "head" || settlementPlace === "margin") {
      const actions = marginControls
        ? [marginControls.nav, settlement, marginControls.close].filter(Boolean)
        : [settlement].filter(Boolean);
      setChildren(this.#actions, actions);
      threadActions = actions.length || model.news ? this.#actions : null;
    }
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
    const standingToggle = this.node.querySelector(".lf-summary-expand:focus");
    const rangeState = describedRanges.map((range) => {
      if (range.kind === "message") return range;
      const forced = Boolean(range.summary.protected?.length);
      const searchMatch = range.messages.some((message) =>
        model.search?.messages.includes(message.id),
      );
      return {
        ...range,
        expanded:
          forced || searchMatch || this.#expandedSummaries.has(range.summary.id),
        forced: forced || searchMatch,
        requiredText: searchMatch
          ? "Matching messages kept open"
          : "Messages kept open · current work",
      };
    });
    const boundaries = panel ? unreadBoundaries(rangeState) : new Map();
    // The progress no answer has folded yet stands behind the working message's disclosure.
    const pendingRanges = rangeState.filter((range) => range.summary?.pending);
    this.#pendingOpen = pendingRanges.some((range) => range.expanded);
    const pendingToggle = pendingRanges.length
      ? this.#summaryToggle(pendingRanges, true, false)
      : nothing;
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
      return { key: message.key, node: view.node };
    });
    this.#lastMessage = messages.at(-1)?.node ?? null;
    const messageNodes = new Map(messages.map(({ key, node }) => [key, node]));
    // Each message, behind its read boundary, in the transcript or its checkpoint.
    const markers = new Map();
    const placed = (key, summary) => {
      const node = messageNodes.get(key);
      keeps(node, "data-lf-summary", summary);
      const kind = boundaries.get(key);
      if (!kind) return [node];
      const marker = this.#markers.get(key) ?? readBoundary();
      paintBoundary(marker, kind);
      markers.set(key, marker);
      return [marker, node];
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
      render(workingView(model.working, pendingToggle), this.#working);
      transcript.push(this.#working);
    }
    this.#checkpoints = checkpoints;
    this.#markers = markers;
    keeps(this.#transcript, "data-lf-reflow", panel ? "append" : null);
    if (reply && !this.#reply) this.#reply = this.#createReply(model);
    const body = html`
      ${
        model.quote
          ? html`<header class="lf-thread-head">
              ${
                model.quote.localReading
                  ? html`<button
                      type="button"
                      class="lf-thread-disclosure lf-quote-expand"
                      aria-label="Full quote"
                      hidden
                      aria-expanded=${String(this.#quoteExpanded)}
                      aria-controls=${`lf-quote-${this.#viewId}`}
                      @click=${this.#toggleQuote}
                    >
                      Full quote
                    </button>`
                  : nothing
              }
              <blockquote
                ${model.quote.localReading ? ref(this.#watchQuote) : nothing}
                id=${`lf-quote-${this.#viewId}`}
                class=${`lf-quote${model.quote.anchored && !model.quote.found ? " detached" : ""}`}
                data-expanded=${String(model.quote.localReading && this.#quoteExpanded)}
                role=${model.quote.found ? "button" : nothing}
                tabindex=${model.quote.found ? "0" : nothing}
                title=${model.quote.title ?? nothing}
                @click=${this.#quotePressed}
                ${commandsOn("On a comment's quoted passage", [
                  {
                    id: "passage.return",
                    keys: PRESS,
                    description: "Return to the quoted passage on the page",
                    title: "return to the passage",
                    when: () => Boolean(model.quote.found),
                    run: this.#returnToQuote,
                  },
                ])}
              >
                <span class="lf-quote-label">${model.quote.label}</span>
                ${
                  model.quote.outdated
                    ? html`<span class="lf-anchor-status">Earlier data</span>`
                    : model.quote.changed
                      ? html`<span class="lf-anchor-status">Changed</span>`
                      : nothing
                }
              </blockquote>
            </header>`
          : nothing
      }
      ${this.#transcript}
      ${
        threadActions
          ? marginControls
            ? html`<div
                class="lf-margin-thread-controls"
                ${ref(this.#watchMarginControls)}
              >
                ${news}${threadActions}
              </div>`
            : html`<div class="lf-thread-controls" data-lf-reflow="text">
                ${news}${threadActions}
              </div>`
          : nothing
      }
    `;
    setChildLists(transcriptLists);
    render(
      html`
        ${navigationSummary(
          model,
          !headerSettlement
            ? null
            : model.news
              ? model.news.label
              : settlement && (model.resolvedBy || "Resolved"),
        )}
        ${titleControl ?? nothing}
        ${
          model.surface === "outlet"
            ? html`<summary
                class="lf-page-thread-summary lf-ui"
                data-lf-gen="1"
                data-lf-offer=""
                ?hidden=${!model.resolved}
              >
                ${
                  model.news?.reopened
                    ? html`<span class="lf-thread-notice lf-thread-notice-news"
                        >${model.news.label}</span
                      >`
                    : html`Resolved · ${model.messages.length}
                      message${model.messages.length === 1 ? "" : "s"}${
                        model.news
                          ? html` ·
                              <span class="lf-thread-notice lf-thread-notice-news"
                                >${model.news.label}</span
                              >`
                          : nothing
                      }`
                }
              </summary>`
            : nothing
        }
        ${
          model.surface === "margin"
            ? body
            : html`<div class="lf-thread-content">${body}</div>`
        }
        ${replySlot ? (this.#continuity?.gap ?? nothing) : nothing}
        ${reply ? this.#reply.node : (this.#replyReservation ?? nothing)}
        ${
          settlementPlace === "row"
            ? html`<div class="lf-page-thread-resolved lf-ui">
                <span
                  >${
                    model.resolvedBy ? html`<span>${model.resolvedBy}</span>` : nothing
                  }</span
                >
                ${news}${settlement}
              </div>`
            : nothing
        }
      `,
      this.node,
    );
    if (!marginControls && model.news)
      measure(this.node, () => this.#retainHeaderSlot());
    else this.#releaseHeaderSlot();
    this.#continuity?.after(bodyPlace);
    this.#measureQuote();
    // A summary gathering the message the user stands on moves it; a page thread whose
    // render took their place puts them in its reply, or on the thread itself.
    // Handing it on is the card's own act, which the list holding the card defers to.
    // A progress disclosure the user stood on that this render replaced, as the
    // answer's head takes it over from the working message, hands them to its successor.
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
    const handOn = handedOn ?? toggleHandedOn;
    restoreFocus?.(
      panel
        ? handOn && (() => (focusDestination(handOn, "return"), true))
        : toggleHandedOn
          ? () => (focusDestination(toggleHandedOn, "return"), true)
          : () =>
              this.#commands.landInThread(
                this.node.querySelector(SAY_BOX) ?? this.node,
              ),
    );
    return this.node;
  }

  // The same native layout that clips the preview decides whether there is
  // anything to disclose. Read it synchronously after render, before the frame
  // paints; resizes update it through this card's shared size observation.
  #measureQuote() {
    const quote = this.#quoteNode;
    const control = quote?.previousElementSibling;
    if (control?.classList.contains("lf-quote-expand"))
      keeps(
        control,
        "hidden",
        !this.#quoteExpanded && quote.scrollHeight <= quote.clientHeight ? "" : null,
      );
  }

  #releaseHeaderSlot() {
    if (this.#observedHeader) this.#sizes.unobserve(this.#observedHeader);
    this.#observedHeader = null;
    this.#releaseHeaderItems();
    this.#newsReserved = false;
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
    const controls = content?.querySelector(":scope > .lf-thread-controls");
    const first = content?.querySelector(
      ":scope > .lf-thread-transcript > :nth-child(1 of .lf-msg, .lf-thread-checkpoint)",
    );
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
      // invisible copy, as reserve does, without transient writes to real words.
      const resizing = allocates && this.#headerSlot?.header === header;
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
        for (const node of reading.children) {
          node.classList.toggle("lf-held-header-item", false);
          node.style.removeProperty("--lf-held-header-width");
        }
        header.after(reading);
      } else this.#releaseHeaderItems();
      const widths = [...reading.children].map(
        (node) => node.getBoundingClientRect().width,
      );
      if (resizing) reading.remove();
      const items = [...header.children].map((node, index) => ({
        node,
        width: widths[index],
      }));
      this.#headerSlot = { header, items, boxWidth: box.width, held: observe };
      for (const { node, width } of allocates ? items : []) {
        // Keep the author's standing width before the first held render, while
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
      if (!this.#newsReserved) {
        reserve(this.#news.node, [this.#model.news.label]);
        this.#newsReserved = true;
      }
      const line = controls.getBoundingClientRect();
      const shown = shownRect(controls, new Map());
      if (shown)
        controls.style.setProperty(
          "--lf-thread-news-visible-end",
          layoutPx(Math.max(0, shown.right - line.left)),
        );
    } else this.#newsReserved = false;
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

  // `counted` names how many messages the toggle shows. The working message's own toggle
  // leaves the count out, since a count that grew with each step would move it.
  // Whether the progress behind the working message stood open when last drawn, opened by
  // the reader or by a search matching it, so each step that joins it shows: held news
  // counts those steps as news here (held-news.js).
  get progressOpen() {
    return this.#pendingOpen;
  }

  #summaryToggle(ranges, progress = false, counted = true) {
    const ids = ranges.map((range) => range.summary.id);
    const expanded = ranges.every((range) => range.expanded);
    const count = ranges.reduce((total, range) => total + range.messages.length, 0);
    const label = counted
      ? `${expanded ? (progress ? "Hide" : "Collapse") : "Show"} ${count} ${
          progress ? "progress" : "earlier"
        } message${count === 1 ? "" : "s"}`
      : `${expanded ? "Hide" : "Show"} progress`;
    return html`<button
      type="button"
      class="lf-thread-disclosure lf-summary-expand"
      data-summary-toggle=${ids[0]}
      aria-expanded=${String(expanded)}
      aria-controls=${ids
        .map((id) => `lf-summary-originals-${this.#viewId}-${id}`)
        .join(" ")}
      @click=${() => this.#setSummaryExpanded(ids, !expanded)}
    >
      ${label}
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

  // The panel's resolved title keeps its state label as the reopening action.
  // Other surfaces use Reopen or the completed check in Resolve's place.
  #settlement(model, place) {
    const state = model.settlement;
    const reopen = state.kind === "unresolve";
    const header = place === "title";
    // A margin card's controls row draws Resolve as the check and Reopen as the word.
    const icon = place === "head" || (place === "margin" && !model.resolved);
    const face = `${state.kind} ${place}`;
    let button = this.#settlements.get(face);
    if (!button) {
      button = offer(
        "button",
        `lf-btn ${reopen ? "lf-reopen" : "lf-resolve"} ${header ? "lf-thread-header-action lf-thread-action" : icon ? "lf-icon-action" : "lf-thread-action"}`,
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
          when: () => !this.#model.settlement?.pending && !this.#model.folding,
          run: this.#settle,
        },
      ]);
    }
    keeps(button, "aria-busy", state.pending && !model.folding);
    if (header) {
      keeps(button, "aria-label", `${model.resolvedBy || "Resolved"} · Reopen thread`);
      keeps(button, "title", `${model.resolvedBy || "Resolved"} · Reopen thread`);
    } else if (icon) {
      const label = model.folding ? "Resolved" : state.label;
      keeps(button, "aria-label", label);
      keeps(button, "title", label);
    }
    render(
      header
        ? model.resolvedBy || "Resolved"
        : icon
          ? iconTemplate("check", "lf-action-icon")
          : state.label,
      button,
    );
    return button;
  }

  // What the thread holds, shown by a press on one of its controls. Where showing it
  // takes the pressed control away, as a held settlement does Resolve, the press leaves
  // the user on the thread's title.
  #showNews() {
    if (!this.#model?.news) return;
    const restoreFocus = holdFocus(this.node);
    this.#model.news.open();
    restoreFocus?.(threadFocusStop(this.node));
  }

  // A press means what its control drew, and shows what the thread holds; where the
  // thread already stands as the press means, as one resolved elsewhere whose news
  // waits, it sends nothing (actions.js, `settle`).
  #settle = () => {
    const model = this.#model;
    if (model.folding) return;
    this.#showNews();
    if (!model.resolved) dismissReply(model.key);
    void settleThread({
      parent: () => this.#model.id,
      key: model.key,
      resolved: model.resolved,
      prepareLanding:
        model.surface === "panel"
          ? () => this.#prepareLanding(model.resolved)
          : model.surface === "margin"
            ? model.resolved
              ? null
              : this.#marginControls?.prepareLanding
            : this.#prepareInlineLanding,
      ...this.#commands.settlement,
    }).catch(() => {});
  };

  // A thread on the page changes shape as it settles: a resolved outlet folds to its
  // summary, and a reopened one unfolds under it. Where the user still stands in it, land
  // it around their focus, which a thread too tall to show leaves where it is.
  #prepareInlineLanding = () => {
    const mayLand = retainUserIntent({
      source: this.node,
      available: () => this.node.isConnected,
    });
    const land = (may = mayLand) => {
      if (!may() || !standingIn(this.node)) return false;
      scrollThreadIntoView(this.node, focused());
      return true;
    };
    return { optimistic: () => land(), reverse: land };
  };

  // Local reading belongs to this retained card, not the event log. Its trigger
  // stands above the growing quote so a press never moves its own target.
  #toggleQuote = () => {
    this.#quoteExpanded = !this.#quoteExpanded;
    this.repaint();
  };

  // A pointer press that ended holding the quote's words took them rather than the trip.
  #quotePressed = (event) => {
    if (!pressIsKeyboardActivation(event) && reachedForWords(event.currentTarget))
      return;
    this.#returnToQuote();
  };

  #returnToQuote = () => {
    const model = this.#model;
    if (!model.quote?.anchored || !model.quote.found) return;
    const travel = this.#commands.travel;
    // The trip promises to show the passage, so it clears the panel where the panel
    // stands over most of it and leaves the panel open beside one seen where it stands.
    travel.scrollToThread(model.id, {
      part: "reply",
    });
  };

  #createReply(model) {
    const panel = model.surface === "panel";
    const replyChanged = () => {
      if (!this.#reply) return;
      this.#draftFrame ||= nextRender(() => {
        this.#draftFrame = 0;
        if (!this.#reply) return;
        if (panel || this.#model.resolved) this.repaint();
        if (this.#model.resolved) this.#commands.reply.changed();
      });
    };
    const { actions } = this.#commands.reply;
    const commands = {
      ...this.#commands.reply,
      actions: {
        ...actions,
        reply: (key, text, options) =>
          this.#speak(
            () => actions.reply(key, text, options),
            options.attempt,
            "thread",
          ),
      },
    };
    return createReplyView(model.key, commands, {
      onChange: replyChanged,
      editLast: this.#rewrites.editLast,
      reveal: panel
        ? () => this.#commands.listRoot.revealNavigation(this.#model.id)
        : null,
      sizes: panel ? replyRowSizes : null,
      redraw: () => this.repaint(),
    });
  }

  #prepareLanding(reopen) {
    const { travel, listRoot } = this.#commands;
    // The cards the list's walks step through (thread-list-view.js, `walkRows`).
    const walked = () => listRoot.walkRows().flatMap(({ thread }) => thread ?? []);
    const mayLand = travel.retainPanelLanding(this.node);
    const shownCard = () =>
      !this.node.hidden && this.node.isConnected ? this.node : null;
    let mayRestore = () => false;
    if (!reopen) {
      const at = walked().indexOf(this.node);
      return {
        optimistic: () => {
          if (!mayLand()) return false;
          const kept = walked();
          const destination = kept[at] ?? kept[at - 1] ?? listRoot;
          if (destination !== listRoot) {
            listRoot.revealNavigation(destination.dataset.id);
            // The user goes on to the next thread, which the list lands in view.
            focusThread(destination, "move");
          } else focusDestination(destination, "move");
          mayRestore = travel.retainPanelLanding(destination);
          return true;
        },
        reverse: (may = mayRestore) => {
          if (may() && mayLand.available()) {
            const card = shownCard();
            // The undo takes the user to the thread it reopened, an arrival that shows
            // what the thread holds, its reopening included.
            if (card) focusThread(card, "move");
          }
        },
      };
    }
    return this.#goWithThread({ part: "reply", always: true });
  }

  // A turn of the user's own in a panel thread: `post` sends it and answers the send.
  // Where the turn takes the thread out of the view the user wrote it in, as a reply
  // under "Waiting on you" or a rewrite under Resolved does, the view widens to show
  // it and the user goes with it, landing on `part`, and back if the log refuses
  // it while they have not acted since.
  #speak(post, attempt, part) {
    const landing =
      this.#model.surface === "panel"
        ? this.#goWithThread({ part, always: false })
        : null;
    const answer = post();
    if (landing && answer)
      void landGesture({
        landing,
        answer,
        standing: () =>
          this.#commands.settlement
            .pendingEntries()
            .some(({ event }) => event.attempt === attempt),
      }).catch(() => {});
    return answer;
  }

  // Carrying the user with the thread into the view that holds it as it now stands:
  // always, for a Reopen, or, for another turn, only where the view leaves it out.
  #goWithThread({ part, always }) {
    const { travel } = this.#commands;
    const mayLand = travel.retainPanelLanding(this.node);
    const shownCard = () =>
      !this.node.hidden && this.node.isConnected ? this.node : null;
    // Until the user arrives with the thread, the gesture's own lease stands for them.
    let mayRestore = mayLand;
    const narrowing = travel.retainNarrowing();
    // The card leaves the view the turn was written in: hidden, or drawn only for the
    // turn's words on their way (thread-list-view.js, `keepsForWords`).
    const leftOut = () =>
      this.node.hidden || this.#commands.listRoot.keepsForWords(this.#model.id);
    return {
      optimistic: async () => {
        if (!mayLand()) return false;
        if (!always && !leftOut()) return false;
        const arriving = travel.showThread(this.#model.id, { part });
        narrowing.replaced();
        if (!(await arriving)) return false;
        const destination = shownCard();
        if (destination) mayRestore = travel.retainPanelLanding(destination);
        return Boolean(destination);
      },
      // The view the turn widened goes back with the user, while Threads is open and
      // they have not acted since (the user's decision, 2026-10-07): an undo's intent,
      // or for a refusal the landing's own, governs the whole reversal, so a later input
      // keeps both the view and the focus where the user took them.
      reverse: async (may = null) => {
        const acting = may ?? mayRestore;
        if (!mayLand.available() || !acting()) return;
        await narrowing.restore(() =>
          travel.showThread(this.#model.id, { part: "thread" }),
        );
      },
    };
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

  retire() {
    this.#reply?.cancelDictation();
    for (const view of this.#messages.values()) view.retire();
  }

  dispose() {
    this.#sizes.disconnect();
    this.#quoteNode = null;
    this.#releaseHeaderSlot();
    if (this.#marginControlsRow) marginControlsSizes.unobserve(this.#marginControlsRow);
    this.#heldNews?.dispose();
    this.#continuity?.release();
    this.retire();
    this.#reply?.dispose();
    this.#reply = null;
  }
}
