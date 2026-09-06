/* This module owns conversation seats rendered into the page, outside the retained
 * Threads list. */
import { landInConversation, SAY_BOX, showThread } from "./landing.js";
import { ago } from "../presence.js";
import { renderMessageMarkdown, syncEdited } from "./messages.js";
import { el, offer } from "../widget-elements.js";
import { seatRoot, turns } from "./model.js";
import { settlementControl } from "./folding.js";
import { wireReply } from "./replies.js";
import { focused } from "../keyboard/scopes.js";
import { setChildren } from "./reconcile.js";
import { paintReactStrips } from "./reaction-strips.js";
import { elementById } from "../passages.js";
import { registry } from "../registry.js";
import { loadDraft } from "../drafts.js";

/* Textual conversation views rendered outside the retained Threads list.

   A Thread Button uses an already-open panel; with the panel closed, its comment opens
   inline at every width and the card overlays the page where no beside posture fits. An
   interactive reply embedded in a message explicitly opens the complete panel view. */
function paintConversationBody(body, message) {
  const words = message.text ?? "";
  if (message.suggestion) body.textContent = words;
  else body.innerHTML = renderMessageMarkdown(words);
  if (message.drawing)
    body.append(el("span", "lf-drawing-reference", "Drawing comment"));
}

function conversationMessageNode(thread, message) {
  let node = thread.querySelector(
    `:scope > .lf-conversation-msg[data-event="${message.id}"]`,
  );
  if (node) {
    const time = node.querySelector("time");
    const when = ago(message.ts);
    if (time.textContent !== when) time.textContent = when;
    syncEdited(node.querySelector(":scope > .lf-conversation-head"), message);
    const body = node.querySelector(":scope > .lf-conversation-body");
    const revision = message.edited?.id ?? "";
    if (node.lfRevision !== revision) {
      paintConversationBody(body, message);
      node.lfRevision = revision;
    }
    return node;
  }
  node = offer("div", `lf-conversation-msg ${message.author}`);
  node.dataset.event = message.id;
  const head = el("div", "lf-conversation-head");
  head.append(
    el("b", "", message.author === "claude" ? message.agent || "Agent" : "You"),
    el("time", "", ago(message.ts)),
  );
  syncEdited(head, message);
  const body = el("div", "lf-conversation-body");
  paintConversationBody(body, message);
  node.lfRevision = message.edited?.id ?? "";
  node.append(head, body);
  if (message.markup) {
    const open = offer(
      "button",
      "lf-btn lf-conversation-open",
      "Open interactive reply in Threads",
    );
    open.onclick = () => showThread(message.id);
    node.append(open);
  }
  return node;
}

function conversationThreadNode(host, t, collapsible = false) {
  let thread = host.querySelector(
    `:scope > .lf-conversation-thread[data-thread="${CSS.escape(t.root.id)}"]`,
  );
  const wantedTag = collapsible ? "DETAILS" : "DIV";
  if (thread && thread.tagName !== wantedTag) {
    thread.remove();
    thread = null;
  }
  if (!thread) {
    thread = offer(collapsible ? "details" : "div", "lf-conversation-thread");
    thread.dataset.thread = t.root.id;
    thread.tabIndex = -1;
  }
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
  const messages = turns(t).map((message) => conversationMessageNode(thread, message));
  let tail;
  if (t.resolved) {
    tail = thread.querySelector(":scope > .lf-conversation-resolved");
    const settledBy =
      t.resolved.author === "claude"
        ? `✓ Resolved by ${t.resolved.agent || "Agent"}`
        : "✓ Resolved";
    if (!tail) {
      tail = offer("div", "lf-conversation-resolved");
      tail.append(el("span"), settlementControl(t));
    }
    if (tail.firstChild.textContent !== settledBy)
      tail.firstChild.textContent = settledBy;
  } else if (t.root.response?.kind === "version") {
    // The page seat shows what the reader proposed. Their reply workspace remains
    // in Threads; the agent's response is the next authored version.
    tail = thread.querySelector(":scope > .lf-conversation-actions");
    if (!tail) {
      tail = offer("div", "lf-conversation-actions");
      tail.append(settlementControl(t));
    }
  } else {
    tail = thread.querySelector(":scope > .lf-say");
    if (!tail) {
      tail = offer("div", "lf-say");
      const input = offer("textarea");
      const send = offer("button", "lf-btn primary", "Send");
      const actions = offer("div", "lf-conversation-actions");
      actions.append(send, settlementControl(t));
      tail.append(input, actions);
      wireReply(t, input, send);
    }
  }
  const receipts = [...thread.querySelectorAll(":scope > .lf-receipt")];
  const after = new Map(
    receipts.map((receipt) => [receipt.dataset.receiptId, receipt]),
  );
  const placed = new Set();
  const messageRows = messages.flatMap((message) => {
    const receipt = after.get(message.dataset.event);
    if (receipt) placed.add(receipt);
    return receipt ? [message, receipt] : [message];
  });
  const standing = focused();
  const heldFocus = thread.contains(standing);
  setChildren(thread, [
    ...(summary ? [summary] : []),
    ...messageRows,
    ...receipts.filter((receipt) => !placed.has(receipt)),
    ...(tail ? [tail] : []),
  ]);
  // Settlement replaces the focused controls in either tail shape. Transfer only
  // that removed focus; a later gesture elsewhere remains where the reader put it.
  if (heldFocus && !thread.contains(standing))
    landInConversation(thread.querySelector(SAY_BOX) ?? thread);
  if (collapsible) paintReactStrips(thread, t);
  return thread;
}

export function renderThreadSurface(host, threads) {
  const receipts = [...host.querySelectorAll(":scope > .lf-receipt")];
  setChildren(host, [
    ...threads.map((thread) => conversationThreadNode(host, thread, true)),
    ...receipts,
  ]);
}

export function renderConversations(threads) {
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
    if (!owned.length) continue;
    const first = host.lfFirstMessage;
    const hold = registry[owner.localName]?.["x-conversation"]?.hold;
    const pending = hold || loadDraft("say:" + owner.id) !== null ? first : null;
    const receipts = [...host.querySelectorAll(":scope > .lf-receipt")];
    setChildren(host, [
      ...receipts,
      ...owned.map((thread) => conversationThreadNode(host, thread)),
      ...(pending ? [pending] : []),
    ]);
  }
}

export function renderMarginThread(host, thread) {
  const node = conversationThreadNode(host, thread);
  setChildren(host, [node]);
  return node;
}
