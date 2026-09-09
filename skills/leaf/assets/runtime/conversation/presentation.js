/* Conversation presentation across panel, page seats, widget outlets, and margin.

   This owner receives records and narrow view capabilities. It never reads delivery,
   assembles protocol events, or imports state application. One synchronous fold updates
   every textual/geometry view immediately; the returned promise only represents frozen
   widget preparation in the retained panel list. */
import { clocked } from "../presence.js";
import { setChildren } from "../dom-children.js";
import { el } from "../widget-elements.js";
import { elementById, inChrome } from "../passages.js";
import { unreadMessages } from "../pending/model.js";
import { foldThreads } from "./model.js";
import { allThreads, setThreads, threadList } from "./state.js";
import { renderConversations } from "./inline.js";
import { holdScrollPosition, renderThreads } from "./thread-list.js";
import { threadsBox } from "./panel-elements.js";
import { paintAcknowledgmentsNow } from "./acknowledgments.js";
import { paintNarrowing, revealThread } from "./narrowing.js";
import { removeConversationNode } from "./reaction-strips.js";

const waitingNote = el("div", "lf-empty", "Loading current threads…");

function renderHolds(threads) {
  for (const node of document.querySelectorAll("[data-lf-held]"))
    node.removeAttribute("data-lf-held");
  for (const thread of threads) {
    if (thread.resolved || !thread.root.holds || thread.root.pending) continue;
    const target = elementById(thread.root.holds);
    if (target && !inChrome(target)) target.dataset.lfHeld = thread.root.id;
  }
}

export function createConversationPresentation({
  panelIsOpen,
  setThreadCount,
  onConversationChanged,
  listView,
  inlineView,
  surfaceView,
  anchorPaint,
  anchorControls,
  drawingPaint,
  pageGeometry,
  readDraft,
  activeActionAnchor,
  renderMargin,
  renderSurfaces,
}) {
  const removeNode = (node) =>
    removeConversationNode(node, inlineView.reaction.closeReactionMode);

  const paintAcknowledgments = clocked(document.body, (...args) =>
    holdScrollPosition(() => paintAcknowledgmentsNow(...args), panelIsOpen),
  );

  function setUnavailable(phase) {
    paintCurrent.stop();
    waitingNote.textContent =
      phase === "offline"
        ? "Current threads are unavailable while the server is offline."
        : "Loading current threads…";
    setChildren(threadsBox, [waitingNote], removeNode);
    setThreadCount(null);
    paintNarrowing([], []);
    setThreads([]);
    const painted = anchorPaint.paint({
      threads: [],
      draft: readDraft(),
      actionAnchor: activeActionAnchor(),
    });
    anchorControls.render(painted);
    drawingPaint.paint([]);
    renderSurfaces([], anchorPaint.placedAt, surfaceView);
    renderConversations([], inlineView);
    renderMargin();
    paintAcknowledgments();
    onConversationChanged();
    pageGeometry.pageShifted();
  }

  function renderCurrent() {
    const threads = allThreads();
    const conversations = threadList();
    renderHolds(threads);
    const painted = anchorPaint.paint({
      threads,
      draft: readDraft(),
      actionAnchor: activeActionAnchor(),
    });
    anchorControls.render(painted);
    drawingPaint.paint(threads);
    renderSurfaces(conversations, anchorPaint.placedAt, surfaceView);
    const prepared = renderThreads(threads, listView);
    renderConversations(conversations, inlineView);
    renderMargin();
    paintAcknowledgments();
    pageGeometry.pageShifted();
    return prepared;
  }

  // The clock replays the canonical installed fold rather than retaining whichever
  // candidate array first caused a timestamp to paint. A failed state application can
  // restore that fold after this synchronous pass, and its next tick must age the
  // restored messages rather than resurrecting the refused candidate.
  const paintCurrent = clocked(document.body, renderCurrent);

  function renderKnown(threads) {
    setThreads(threads);
    return paintCurrent();
  }

  function apply({ phase, serverThreads = [], receipts = [], pendingEntries = [] }) {
    if (phase !== "ready") {
      setUnavailable(phase);
      return undefined;
    }
    return renderKnown(
      foldThreads(serverThreads, unreadMessages(pendingEntries, receipts)),
    );
  }

  function repaintCurrent() {
    return paintCurrent();
  }

  function refreshNarrowing() {
    const threads = allThreads();
    const prepared = renderThreads(threads, listView);
    paintAcknowledgments();
    return prepared;
  }

  function mount() {
    threadsBox.addEventListener("lf-reveal", (event) => {
      const hidden = event.detail?.target?.closest?.(".lf-thread[hidden]");
      if (hidden) revealThread(hidden.dataset.id, refreshNarrowing);
    });
  }

  return {
    apply,
    mount,
    paintAcknowledgments,
    refreshNarrowing,
    repaintCurrent,
  };
}
