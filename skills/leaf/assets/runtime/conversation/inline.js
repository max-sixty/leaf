/* This module owns conversation seats rendered into the page, outside the retained
 * Threads list. */
import { SAY_BOX } from "./selectors.js";
import { ago } from "../presence.js";
import { renderMessageMarkdown, syncEdited, syncStreamState } from "./messages.js";
import { markdownReady } from "../markdown.js";
import { el, offer } from "../widget-elements.js";
import { seatRoot, turns } from "./model.js";
import { settlementControl } from "./folding.js";
import { wireReply } from "./replies.js";
import { focused } from "../keyboard/scopes.js";
import { setChildren } from "../dom-children.js";
import { paintReactStrips, removeConversationNode } from "./reaction-strips.js";
import { elementById } from "../passages.js";
import { registry } from "../registry.js";
import { loadDraft } from "../drafts.js";

/* Textual conversation views rendered outside the retained Threads list.

   A thread margin entry uses an already-open panel; with the panel closed, its comment opens
   inline at every width and the card overlays the page where no beside posture fits. An
   interactive reply embedded in a message explicitly opens the complete panel view. */
function paintConversationBody(body, message) {
  const words = message.text ?? "";
  if (message.suggestion) body.textContent = words;
  else body.innerHTML = renderMessageMarkdown(words);
  if (message.drawing)
    body.append(el("span", "lf-drawing-reference", "Drawing comment"));
}

// What a painted body was made from: the prose revision, and whether the Markdown
// renderer had arrived when it was painted. A message the reader sends paints in their
// gesture, before the lazy import it needs has necessarily landed.
const inlineRevision = (message) =>
  `${message.edited?.id ?? ""}:${message.stream_state ? message.text : ""}:${markdownReady() ? "md" : "raw"}`;

function conversationMessageNode(thread, message, commands) {
  // By its event, or — while the log is still answering for words the reader just sent —
  // by the attempt both the pending record and the server's event carry. Found that way,
  // the node the send drew is renamed rather than replaced, so the reader keeps the
  // caret, focus and selection they have in it.
  let node =
    thread.querySelector(`:scope > .lf-conversation-msg[data-event="${message.id}"]`) ??
    (message.attempt
      ? thread.querySelector(
          `:scope > .lf-conversation-msg[data-attempt="${message.attempt}"]`,
        )
      : null);
  if (node) {
    if (node.dataset.event !== message.id) node.dataset.event = message.id;
    if (message.pending) node.setAttribute("aria-busy", "true");
    else node.removeAttribute("aria-busy");
    const time = node.querySelector("time");
    const when = ago(message.ts);
    if (time.textContent !== when) time.textContent = when;
    const head = node.querySelector(":scope > .lf-conversation-head");
    syncEdited(head, message);
    syncStreamState(node, head, message);
    const body = node.querySelector(":scope > .lf-conversation-body");
    const revision = inlineRevision(message);
    if (node.lfRevision !== revision) {
      paintConversationBody(body, message);
      node.lfRevision = revision;
    }
    return node;
  }
  node = offer("div", `lf-conversation-msg ${message.author}`);
  node.dataset.event = message.id;
  if (message.attempt) node.dataset.attempt = message.attempt;
  if (message.pending) node.setAttribute("aria-busy", "true");
  const head = el("div", "lf-conversation-head");
  head.append(
    el("b", "", message.author === "claude" ? message.agent || "Agent" : "You"),
    el("time", "", ago(message.ts)),
  );
  syncEdited(head, message);
  syncStreamState(node, head, message);
  const body = el("div", "lf-conversation-body");
  paintConversationBody(body, message);
  node.lfRevision = inlineRevision(message);
  node.append(head, body);
  if (message.markup) {
    const open = offer(
      "button",
      "lf-btn lf-conversation-open",
      "Open interactive reply in Threads",
    );
    open.onclick = () => commands.showThread(message.id);
    node.append(open);
  }
  return node;
}

function conversationThreadNode(host, t, collapsible, commands) {
  const removeNode = (node) =>
    removeConversationNode(node, commands.reaction.closeReactionMode);
  let thread =
    host.querySelector(
      `:scope > .lf-conversation-thread[data-thread="${CSS.escape(t.root.id)}"]`,
    ) ??
    (t.root.attempt
      ? host.querySelector(
          `:scope > .lf-conversation-thread[data-attempt="${CSS.escape(t.root.attempt)}"]`,
        )
      : null);
  const wantedTag = collapsible ? "DETAILS" : "DIV";
  if (thread && thread.tagName !== wantedTag) {
    removeNode(thread);
    thread = null;
  }
  if (!thread) {
    thread = offer(collapsible ? "details" : "div", "lf-conversation-thread");
    if (t.root.attempt) thread.dataset.attempt = t.root.attempt;
    thread.tabIndex = -1;
  }
  if (thread.dataset.thread !== t.root.id) thread.dataset.thread = t.root.id;
  // Read at use, not captured: the log answering for a comment the reader just sent
  // renames this node rather than replacing it, and the controls below outlive that.
  const liveId = () => thread.dataset.thread;
  let summary = null;
  if (collapsible) {
    summary = thread.querySelector(":scope > .lf-conversation-summary");
    if (!summary) summary = offer("summary", "lf-conversation-summary");
    const resolved = Boolean(t.resolved);
    if (thread.lfResolved !== resolved) thread.open = !resolved;
    thread.lfResolved = resolved;
    summary.hidden = !resolved;
    summary.textContent = `Resolved · ${turns(t).length} message${
      turns(t).length === 1 ? "" : "s"
    }`;
  }
  // Turns only: a reaction on a message is the panel's strip to show, and the seat is
  // the textual projection of the exchange.
  const messages = turns(t).map((message) =>
    conversationMessageNode(thread, message, commands),
  );
  const standing = focused();
  const heldFocus = thread.contains(standing);
  let tail;
  let resolve;
  let actions;
  if (t.resolved) {
    thread.querySelector(":scope > .lf-thread-head")?.remove();
    tail = thread.querySelector(":scope > .lf-conversation-resolved");
    const settledBy =
      t.resolved.author === "claude"
        ? `✓ Resolved by ${t.resolved.agent || "Agent"}`
        : "✓ Resolved";
    if (!tail) {
      tail = offer("div", "lf-conversation-resolved");
      tail.append(el("span"), settlementControl(t, { liveId, ...commands.settlement }));
    }
    if (tail.firstChild.textContent !== settledBy)
      tail.firstChild.textContent = settledBy;
  } else {
    resolve =
      thread.querySelector(":scope > .lf-thread-head > .lf-resolve") ??
      settlementControl(t, { liveId, ...commands.settlement });
    actions = thread.querySelector(":scope > .lf-thread-head");
    if (!actions) actions = offer("header", "lf-thread-head");
    actions.append(resolve);
    if (t.root.response?.kind !== "version") {
      tail = thread.querySelector(":scope > .lf-say");
      if (!tail) {
        tail = offer("div", "lf-say");
        const input = offer("textarea");
        input.name = "reply";
        const send = offer("button", "lf-btn primary", "Send");
        tail.append(input, send);
        wireReply(t, input, send, {
          liveId,
          createReply: commands.reply.createReply,
          revealReplyEditor: commands.reply.revealReplyEditor,
          wireInput: commands.reply.wireInput,
        });
      }
    }
  }
  const receipts = [...thread.querySelectorAll(":scope > .lf-receipt")];
  // Message-owned receipts live in their message headers. A direct child has no source
  // message, so it is the full-width fallback immediately before the thread's tail.
  setChildren(
    thread,
    [
      ...(summary ? [summary] : []),
      ...(actions ? [actions] : []),
      ...messages,
      ...receipts,
      ...(tail ? [tail] : []),
    ],
    removeNode,
  );
  // Settlement replaces the focused controls in either tail shape. Transfer only
  // that removed focus; a later gesture elsewhere remains where the reader put it.
  if (heldFocus && !thread.contains(standing))
    commands.landInConversation(thread.querySelector(SAY_BOX) ?? thread);
  if (collapsible) paintReactStrips(thread, t, commands.reaction);
  return thread;
}

export function renderThreadSurface(host, threads, commands) {
  const removeNode = (node) =>
    removeConversationNode(node, commands.reaction.closeReactionMode);
  const receipts = [...host.querySelectorAll(":scope > .lf-receipt")];
  setChildren(
    host,
    [
      ...threads.map((thread) => conversationThreadNode(host, thread, true, commands)),
      ...receipts,
    ],
    removeNode,
  );
}

export function renderConversations(threads, commands) {
  const removeNode = (node) =>
    removeConversationNode(node, commands.reaction.closeReactionMode);
  for (const host of document.querySelectorAll(
    ".lf-conversation[data-lf-conversation]",
  )) {
    const owner = elementById(host.dataset.lfConversation);
    const owned = threads.filter((thread) => seatRoot(thread) === owner.id);
    // Before the first comment, conversationBox's first-message composer is already
    // the complete view. An externally arriving root may find unsent first-message
    // words here, so the root does not get to take their only box. A hold-capable seat
    // stays reachable after every root so an ordinary conversation cannot remove the
    // stronger send route.
    const first = host.lfFirstMessage;
    const hold = registry[owner.localName]?.["x-conversation"]?.hold;
    const pending =
      !owned.length || hold || loadDraft("say:" + owner.id) !== null ? first : null;
    const receipts = [...host.querySelectorAll(":scope > .lf-receipt")];
    setChildren(
      host,
      [
        ...receipts,
        ...owned.map((thread) => conversationThreadNode(host, thread, false, commands)),
        ...(pending ? [pending] : []),
      ],
      removeNode,
    );
  }
}

export function renderMarginThread(host, thread, commands) {
  const node = conversationThreadNode(host, thread, false, commands);
  setChildren(host, [node], (removed) =>
    removeConversationNode(removed, commands.reaction.closeReactionMode),
  );
  return node;
}
