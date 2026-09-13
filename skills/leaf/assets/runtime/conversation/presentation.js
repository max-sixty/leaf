/* Conversation presentation across panel, page seats, widget outlets, and margin.

   This owner receives records and narrow view capabilities. It never reads delivery,
   assembles protocol events, or imports state application. It reads the published fold
   for every textual/geometry view. Its presentation ticket commits the conversation
   surfaces together with preparation for frozen widgets newly joined to the panel. */
import { clocked } from "../presence.js";
import { elementById, inChrome } from "../passages.js";
import { conversationState } from "./state.js";
import { renderConversations } from "./inline.js";
import {
  holdScrollPosition,
  RetainedThreadListError,
  retainedThreadListProof,
  renderThreadListUnavailable,
  renderThreads,
} from "./thread-list.js";
import { threadsBox } from "./panel-elements.js";
import { paintAcknowledgmentsNow } from "./acknowledgments.js";
import { paintNarrowing, revealThread } from "./narrowing.js";
import { attachApplicationPresentation, readApplication } from "../semantic-state.js";

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
  available = true,
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
    let resolve, reject;
    const completion = new Promise((done, fail) => {
      resolve = done;
      reject = fail;
    });
    const pending = { resolve };
    const prior = activePresentation;
    activePresentation = pending;
    const ready = presentation().present(value, completion, retainedThreadListProof);
    prior?.resolve();
    let painted;
    try {
      painted = paint();
      void Promise.resolve(painted).then(resolve, reject);
    } catch (error) {
      reject(error);
    }
    const clear = () => {
      if (activePresentation === pending) activePresentation = null;
    };
    void ready.then(clear, clear);
    return ready;
  }

  const paintAcknowledgments = (...args) =>
    holdScrollPosition(() => paintAcknowledgmentsNow(...args), panelIsOpen);

  function finishListRecovery(candidate) {
    if (candidate?.recovered)
      throw new RetainedThreadListError(candidate.recovered, candidate.proof);
  }

  async function setUnavailable(phase) {
    paintCurrent.stop();
    const note =
      phase === "offline"
        ? "Current threads are unavailable while the server is offline."
        : "Loading current threads…";
    const prepared = renderThreadListUnavailable(note, listView);
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
    const candidate = await prepared;
    paintAcknowledgments();
    onConversationChanged();
    pageGeometry.pageShifted();
    finishListRecovery(candidate);
  }

  async function renderCurrent() {
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
    const candidate = await prepared;
    paintAcknowledgments();
    pageGeometry.pageShifted();
    finishListRecovery(candidate);
  }

  // Each clock tick reads the current semantic root, never a retained presentation
  // input that could omit later local gestures or a newer accepted reading.
  const paintCurrent = clocked(document.body, () =>
    activePresentation
      ? renderCurrent()
      : present(readApplication().effective.conversation, renderCurrent),
  );

  function apply(snapshot) {
    return present(snapshot.effective.conversation, () => {
      if (!available) return;
      if (snapshot.phase !== "ready") {
        return setUnavailable(snapshot.phase);
      }
      return paintCurrent();
    });
  }

  function repaintCurrent() {
    return present(readApplication().effective.conversation, () => {
      if (available) return paintCurrent();
    });
  }

  function refreshNarrowing() {
    return present(readApplication().effective.conversation, () => {
      if (!available) return;
      const threads = conversationState().all;
      const prepared = renderThreads(threads, listView);
      return Promise.resolve(prepared).then((candidate) => {
        paintAcknowledgments();
        finishListRecovery(candidate);
      });
    });
  }

  function mount() {
    threadsBox.addEventListener("lf-reveal", (event) => {
      const hidden = event.detail?.target?.closest?.(".lf-thread[hidden]");
      if (hidden)
        event.detail?.present?.(revealThread(hidden.dataset.id, refreshNarrowing));
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
