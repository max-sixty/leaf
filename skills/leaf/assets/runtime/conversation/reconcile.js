/* This module composes panel reconciliation: it wires the conversation owners together
 * and owns the render pass that runs them. */
import { buildThreads, conversational } from "./model.js";

import { renderConversations } from "./inline.js";

import { holdScrollPosition, renderThreads } from "./thread-list.js";

import { clocked } from "../presence.js";

import { setReact } from "../reactions.js";

import { runtime } from "../context.js";

import { el } from "../widget-elements.js";
import { elementById, inChrome } from "../passages.js";

import { paintAnchors, placedAt } from "../anchors.js";

import { paintHere } from "../keyboard/scopes.js";

import { threadsBox } from "./panel.js";

import { toggleBtn } from "../banner.js";
import { renderMargin } from "../living-margin.js";
import { paintAcknowledgmentsNow } from "./acknowledgments.js";
import { renderSurfaces } from "./surfaces.js";
import { paintNarrowing, widen } from "./narrowing.js";

/* Conversation state and panel reconciliation.

   The thread list reconciles nodes rather than rebuilding them. `setChildren` preserves
   existing message, reply, and textarea nodes when the same event still stands.
   Applying a state must not discard a reader's caret, focus, reply text, or disclosure
   state. Reconciliation preserves node identity; the list's own hold, rather than the
   browser's scroll anchoring, preserves viewport position. Tests pin the thread's box
   rather than a particular scroll offset. */
export const reactDone = () => setReact(false);

export const renderPanel = clocked(document.body, renderPanelNow);
// A reaction list owns the keyboard until it closes. Reconciliation can remove its
// surface without a local gesture, so every removal path disarms it before detaching
// the node; otherwise digits would keep acting on a reply no longer on screen.
export function removeNode(node) {
  if (node.matches?.(".lf-react-open") || node.querySelector?.(".lf-react-open"))
    reactDone();
  node.remove();
}
// The threads the panel last reconciled. Until the first state answer, [] means "not
// read", not "no comments": a Threads panel restored or opened during startup keeps its
// general box usable while the list says what it is waiting for. A receipt repaints on
// the heartbeat's clock and not only on the log's, because its age is half of what it
// says and a claim nobody renews is exactly the one whose age has stopped moving. Keeping
// the last fold is what makes that cheap: buildThreads walks the log and the page, and a
// second walk every two seconds would answer nothing the last one didn't.
let listedThreads = [];

// The open threads, in the order t/T walk. The list is the panel's own children rather
// than a record kept beside them: a thread the log settles is renamed out of them in
// that frame (foldOut), which takes it out of the walk and out of x's press in one
// stroke.
// Cards a narrowing hid keep their nodes (thread-list.js) and are walked by nothing.
export const openThreads = () => [
  ...threadsBox.querySelectorAll(":scope > .lf-thread:not([hidden])"),
];
export const paintAcknowledgments = clocked(document.body, (...args) =>
  holdScrollPosition(() => paintAcknowledgmentsNow(...args)),
);

// A walk or a tray row travelling to a question the narrowing hid (asks/view.js
// goToAsk → reveal) reveals outside-in through this event, which does not bubble
// — it is dispatched on each ancestor, this list among them; the list answers as the
// panel's own showThread does, by letting the narrowing go. Synchronous, so the focus
// the traveller lands next finds a card with a box.
// Wired once the chrome is mounted (chrome.js): the list is the panel's, an owner that
// imports this module back.
export function mountConversation() {
  threadsBox.addEventListener("lf-reveal", (event) => {
    if (event.detail?.target?.closest?.(".lf-thread[hidden]")) widen();
  });
}
// The reconcile's one mover, shared by the list and the resolved disclosure: make
// `parent`'s children `nodes`, in that order, touching nothing already in its place.
// Not touching it matters beyond economy: reinserting a node restarts its CSS
// animations, drops any focus and caret inside it, and swaps it out from under a
// pressed pointer, which swallows the click. Stale nodes go first for the same
// reason — with one removed mid-list, everything after it is exactly one place
// forward, so the walk keeps those where they stand instead of reinserting each.
export function setChildren(parent, nodes) {
  const keep = new Set(nodes);
  for (const child of [...parent.childNodes]) if (!keep.has(child)) removeNode(child);
  let cursor = parent.firstChild;
  for (const node of nodes) {
    if (node === cursor) cursor = cursor.nextSibling;
    else parent.insertBefore(node, cursor);
  }
}

const waitingNote = el("div", "lf-empty", "Loading current threads…");

// An unresolved hold thread is the pause. Derive the mark from the thread fold so
// resolution removes it and undo restores it without a second state store.
function renderHolds(threads) {
  for (const node of document.querySelectorAll("[data-lf-held]"))
    node.removeAttribute("data-lf-held");
  for (const thread of threads) {
    if (thread.resolved || !thread.root.holds) continue;
    const target = elementById(thread.root.holds);
    if (target && !inChrome(target)) target.dataset.lfHeld = thread.root.id;
  }
}

// The panel and the page marks are two views of the same threads, and the paint pass
// reports back to the list renderThreads just reconciled — always render them as a pair.
function renderPanelNow() {
  if (runtime.statePhase !== "ready") {
    waitingNote.textContent =
      runtime.statePhase === "offline"
        ? "Current threads are unavailable while the server is offline."
        : "Loading current threads…";
    setChildren(threadsBox, [waitingNote]);
    toggleBtn.textContent = "Threads";
    // Nothing read yet, so nothing to count and nothing to narrow. The same writer, so
    // the button says exactly what it will say the moment the log arrives empty.
    paintNarrowing([], []);
    listedThreads = [];
    renderSurfaces(listedThreads, placedAt);
    renderConversations(listedThreads);
    renderMargin();
    paintAcknowledgments();
    paintHere();
    return;
  }
  const threads = buildThreads();
  renderHolds(threads);
  listedThreads = threads.filter(conversational);
  // The marks first, because the list is ordered by where they landed: one resolution of
  // every anchor, read by the page for its paint and by the panel for its order. Resolving
  // a second time for the order would be a second answer to where a thread is, free to
  // disagree with the first over a page that changed between them — and it would walk the
  // document's whole text again to say it.
  paintAnchors(threads);
  renderSurfaces(listedThreads, placedAt);
  const prepared = renderThreads(threads);
  renderConversations(listedThreads);
  renderMargin();
  paintAcknowledgments();
  return prepared;
}

export const threadList = () => listedThreads;
