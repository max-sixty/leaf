/* Conversation presentation across panel, page seats, widget outlets, and margin.

   This owner receives records and narrow view capabilities. It never reads delivery,
   assembles protocol events, or imports state application. It reads the published fold
   for every textual/geometry view. Its presentation ticket commits the conversation
   surfaces together with preparation for frozen widgets newly joined to the panel. */
import { clocked } from "../presence.js";
import { elementById, inChrome } from "../passages.js";
import { conversationState } from "./state.js";
import {
  renderConversations,
  beginConversationSeats,
  commitConversationSeats,
  retainConversationSeats,
} from "./inline.js";
import {
  RetainedThreadListError,
  retainedThreadListProof,
  renderThreadListUnavailable,
  renderThreads,
  restoreThreadList,
} from "./thread-list.js";
import { threadsBox } from "./panel-elements.js";
import { revealThread } from "./narrowing.js";
import {
  applicationState,
  attachApplicationPresentation,
  readApplication,
} from "../semantic-state.js";

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

  // Accepted and optimistic conversation changes owe a fresh generated presentation.
  // Register that obligation before publication seals; apply() may run later behind
  // a serialized state application. Unchanged values can retain their prior proof.
  applicationState
    .select((snapshot) =>
      snapshot.phase === "waiting"
        ? null
        : JSON.stringify([snapshot.phase, snapshot.effective.conversation]),
    )
    .subscribe((value) => {
      if (value === null) return;
      let resolve;
      const completion = new Promise((done) => {
        resolve = done;
      });
      const prior = activePresentation;
      activePresentation = { resolve };
      void presentation().present(readApplication().effective.conversation, completion);
      prior?.resolve();
    });

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

  function finishListRecovery(candidate) {
    if (candidate?.recovered)
      throw new RetainedThreadListError(candidate.recovered, candidate.proof);
  }

  let surfaceGeneration = 0;
  async function renderReading(phase = "ready") {
    const generation = ++surfaceGeneration;
    const current = () => generation === surfaceGeneration;
    const batch = beginConversationSeats();
    let prepared = null;
    try {
      const { all, listed } = conversationState();
      const threads = phase === "ready" ? all : [];
      const conversations = phase === "ready" ? listed : [];
      renderHolds(threads);
      const painted = anchorPaint.paint({
        threads,
        draft: readDraft(),
        actionAnchor: activeActionAnchor(),
      });
      if (painted) anchorControls.render(painted);
      drawingPaint.paint(threads);
      renderSurfaces(conversations, anchorPaint.placedAt, surfaceView);
      prepared =
        phase === "ready"
          ? renderThreads(threads, listView)
          : renderThreadListUnavailable(
              phase === "offline"
                ? "Current threads are unavailable while the server is offline."
                : "Loading current threads…",
              listView,
            );
      void prepared.catch(() => {});
      renderConversations(conversations, inlineView);
      renderMargin();
      const candidate = await prepared;
      if (!current()) return;
      candidate?.commit();
      commitConversationSeats(batch);
      pageGeometry.pageShifted();
      finishListRecovery(candidate);
    } catch (error) {
      if (!current() || error instanceof RetainedThreadListError) throw error;
      // A synchronous sibling failure may leave the panel's widget preparation in
      // flight. Invalidate its private generation before restoring the whole reading.
      await restoreThreadList();
      if (!current()) return;
      retainConversationSeats(batch);
      throw error;
    }
  }

  function setUnavailable(phase) {
    paintCurrent.stop();
    return renderReading(phase);
  }
  const renderCurrent = () => renderReading();

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
        candidate?.commit();
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
    refreshNarrowing,
    repaintCurrent,
  };
}
