/* This module composes panel reconciliation: it wires the conversation owners together
 * and owns the render pass that runs them. */
import { foldThreads } from "./model.js";
import { setThreads, threadList } from "./state.js";

import { renderConversations } from "./inline.js";

import { holdScrollPosition, renderThreads } from "./thread-list.js";

import { clocked } from "../presence.js";

import { runtime } from "../context.js";
import { PENDING } from "./identity.js";
import { outbox, pendingMessages } from "../outbox.js";
import { setChildren } from "../dom-children.js";

import { el } from "../widget-elements.js";
import { elementById, inChrome } from "../passages.js";

import { paintAnchors, placedAt } from "../anchors.js";
import { paintDrawings } from "../composing/drawing.js";

import { repaint } from "../repaint.js";

import { threadsBox } from "./panel.js";

import { toggleBtn } from "../banner.js";
import { renderMargin } from "../living-margin.js";
import { paintAcknowledgmentsNow } from "./acknowledgments.js";
import { renderSurfaces } from "./surfaces.js";
import { paintNarrowing, revealThread } from "./narrowing.js";
import { removeConversationNode } from "./reaction-strips.js";

/* Conversation state and panel reconciliation.

   The thread list reconciles nodes rather than rebuilding them. `setChildren` preserves
   existing message, reply, and textarea nodes when the same event still stands.
   Applying a state must not discard a reader's caret, focus, reply text, or filter
   state. Reconciliation preserves node identity; the list's own hold, rather than the
   browser's scroll anchoring, preserves viewport position. Tests pin the thread's box
   rather than a particular scroll offset. */
export const renderPanel = clocked(document.body, () =>
  renderPanelNow(runtime, outbox),
);
// Until the first state answer, [] means "not
// read", not "no comments": a Threads panel restored or opened during startup keeps its
// general box usable while the list says what it is waiting for. A receipt repaints on
// the heartbeat's clock and not only on the log's, because its age is half of what it
// says and a claim nobody renews is exactly the one whose age has stopped moving. Keeping
// the last fold is what makes that cheap: folding walks the projected messages, and a
// second walk every two seconds would answer nothing the last one didn't.
export const paintAcknowledgments = clocked(document.body, (...args) =>
  holdScrollPosition(() => paintAcknowledgmentsNow(...args)),
);

// A walk or a tray row travelling to a question the narrowing hid (asks/view.js
// goToAsk → reveal) reveals outside-in through this event, which does not bubble
// — it is dispatched on each ancestor, this list among them; the list answers as the
// panel's own showThread does, by letting the narrowing go. Synchronous, so the focus
// the traveller lands next finds a card with a box.
// Wired once the chrome is mounted (leaf.js): the list is the panel's, an owner that
// imports this module back.
export function mountConversation() {
  threadsBox.addEventListener("lf-reveal", (event) => {
    const hidden = event.detail?.target?.closest?.(".lf-thread[hidden]");
    if (hidden) revealThread(hidden.dataset.id);
  });
}
const waitingNote = el("div", "lf-empty", "Loading current threads…");

// An unresolved hold thread is the pause. Derive the mark from the thread fold so
// resolution removes it and undo restores it without a second state store.
function renderHolds(threads) {
  for (const node of document.querySelectorAll("[data-lf-held]"))
    node.removeAttribute("data-lf-held");
  for (const thread of threads) {
    // The attribute names a thread, and a hold the log has not named yet has only the
    // name this page gave it. The mark arrives with the answer, a breath later.
    if (thread.resolved || !thread.root.holds) continue;
    if (thread.root.id.startsWith(PENDING)) continue;
    const target = elementById(thread.root.holds);
    if (target && !inChrome(target)) target.dataset.lfHeld = thread.root.id;
  }
}

// The panel and the page marks are two views of the same threads, and the paint pass
// reports back to the list renderThreads just reconciled — always render them as a pair.
function renderPanelNow(currentRuntime, currentOutbox) {
  if (currentRuntime.statePhase !== "ready") {
    waitingNote.textContent =
      currentRuntime.statePhase === "offline"
        ? "Current threads are unavailable while the server is offline."
        : "Loading current threads…";
    setChildren(threadsBox, [waitingNote], removeConversationNode);
    toggleBtn.textContent = "Threads";
    // Nothing read yet, so nothing to count and nothing to narrow. The same writer, so
    // the button says exactly what it will say the moment the log arrives empty.
    paintNarrowing([], []);
    setThreads([]);
    paintDrawings([]);
    renderSurfaces([], placedAt);
    renderConversations([]);
    renderMargin();
    paintAcknowledgments();
    repaint();
    return;
  }
  const threads = foldThreads(
    currentRuntime.browser?.conversation?.threads ?? [],
    pendingMessages(currentOutbox, currentRuntime.browser?.receipts ?? []),
  );
  setThreads(threads);
  const conversations = threadList();
  renderHolds(threads);
  // The marks first, because the list is ordered by where they landed: one resolution of
  // every anchor, read by the page for its paint and by the panel for its order. Resolving
  // a second time for the order would be a second answer to where a thread is, free to
  // disagree with the first over a page that changed between them — and it would walk the
  // document's whole text again to say it.
  paintAnchors(threads);
  paintDrawings(threads);
  renderSurfaces(conversations, placedAt);
  const prepared = renderThreads(threads);
  renderConversations(conversations);
  renderMargin();
  paintAcknowledgments();
  return prepared;
}
