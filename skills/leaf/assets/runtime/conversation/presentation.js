/* Conversation presentation across panel, page seats, widget outlets, and margin.

   This owner receives records and narrow view capabilities. It never reads delivery,
   assembles protocol events, or imports state application. It reads the published fold
   for every textual/geometry view. Its presentation ticket commits the conversation
   surfaces together with preparation for frozen widgets newly joined to the panel. */
import { clocked } from "../presence.js";
import { setChildren } from "../dom-children.js";
import { el } from "../widget-elements.js";
import { elementById, inChrome } from "../passages.js";
import { conversationState } from "./state.js";
import { renderConversations } from "./inline.js";
import { holdScrollPosition, renderThreads } from "./thread-list.js";
import { threadsBox } from "./panel-elements.js";
import { paintAcknowledgmentsNow } from "./acknowledgments.js";
import { paintNarrowing, revealThread } from "./narrowing.js";
import { removeConversationNode } from "./reaction-strips.js";
import { attachApplicationPresentation, readApplication } from "../semantic-state.js";

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
  let presentationHandle = null;
  let activePresentation = null;
  const presentation = () => {
    presentationHandle ??= attachApplicationPresentation("conversation", document);
    return presentationHandle;
  };

  function present(value, paint) {
    let resolve;
    const completion = new Promise((done) => {
      resolve = done;
    });
    const pending = { resolve };
    const prior = activePresentation;
    activePresentation = pending;
    const ready = presentation().present(value, completion);
    prior?.resolve();
    let painted;
    try {
      painted = paint();
    } catch (error) {
      // The retained prior conversation is the fallback. Leave this attempt pending
      // so readiness cannot call it current; a later paint supersedes the hold.
      throw error;
    }
    return Promise.resolve(painted).then(async (proof) => {
      resolve(proof);
      await ready;
      if (activePresentation === pending) activePresentation = null;
    });
  }

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
    const painted = anchorPaint.paint({
      threads: [],
      draft: readDraft(),
      actionAnchor: activeActionAnchor(),
    });
    if (painted) anchorControls.render(painted);
    drawingPaint.paint([]);
    renderSurfaces([], anchorPaint.placedAt, surfaceView);
    renderConversations([], inlineView);
    renderMargin();
    paintAcknowledgments();
    onConversationChanged();
    pageGeometry.pageShifted();
  }

  function renderCurrent() {
    const { all: threads, listed: conversations } = conversationState();
    renderHolds(threads);
    const painted = anchorPaint.paint({
      threads,
      draft: readDraft(),
      actionAnchor: activeActionAnchor(),
    });
    if (painted) anchorControls.render(painted);
    drawingPaint.paint(threads);
    renderSurfaces(conversations, anchorPaint.placedAt, surfaceView);
    const prepared = renderThreads(threads, listView);
    renderConversations(conversations, inlineView);
    renderMargin();
    paintAcknowledgments();
    pageGeometry.pageShifted();
    return prepared;
  }

  // Each clock tick reads the current semantic root, never a retained presentation
  // input that could omit later local gestures or a newer accepted reading.
  const paintCurrent = clocked(document.body, renderCurrent);

  function apply(snapshot) {
    return present(snapshot.effective.conversation, () => {
      if (snapshot.phase !== "ready") {
        setUnavailable(snapshot.phase);
        return undefined;
      }
      return paintCurrent();
    });
  }

  function repaintCurrent() {
    return present(readApplication().effective.conversation, () => paintCurrent());
  }

  function refreshNarrowing() {
    return present(readApplication().effective.conversation, () => {
      const threads = conversationState().all;
      const prepared = renderThreads(threads, listView);
      paintAcknowledgments();
      return prepared;
    });
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
