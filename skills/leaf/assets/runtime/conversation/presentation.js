/* Conversation presentation across panel, page seats, widget outlets, and margin.

   This owner receives records and narrow view capabilities. It never reads delivery,
   assembles protocol events, or imports state application. It reads the published fold
   for every textual/geometry view. It is an epoch presenter: the publication claims its
   region and the pass paints it, after the projection whose provenance words its
   passages resolve over. Its presentation ticket commits the conversation surfaces
   together with preparation for frozen widgets newly joined to the panel. A mechanical
   repaint — a draft, a hover, a narrowing — claims the same region through `present`. */
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
  applicationPresenter,
  applicationState,
  PRESENTATION_ORDER,
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
  let painting = false;

  const presenter = applicationPresenter({
    region: "conversation",
    order: PRESENTATION_ORDER.conversation,
    current: () => {
      const root = readApplication();
      return root.phase === "waiting" ? null : root.effective.conversation;
    },
    failSoft: retainedThreadListProof,
    paint: async (value) => {
      if (!available) return value;
      painting = true;
      try {
        const phase = readApplication().phase;
        // The claimed value is the conversation this pass owes. What it draws comes from
        // the current semantic root, which may already carry a newer local gesture.
        await (phase === "ready" ? paintCurrent() : setUnavailable(phase));
      } finally {
        painting = false;
      }
      return value;
    },
  });

  const present = () => presenter.present();

  // Every epoch owes a fresh generated presentation, because this owner reads more of
  // the root than its own fold: thread receipts come from canonical activity and the
  // margin draws the Ask rows beside them. The claim registers that obligation inside
  // the publication that seals membership; the pass paints it. Whether there is a
  // conversation to claim at all is `current`'s answer, above.
  applicationState.select((snapshot) => snapshot.semanticEpoch).subscribe(present);

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

  // A clock tick outside the pass claims its own ticket; inside it, the pass already
  // holds one and claiming a second would be this paint waiting on the pass it is part
  // of. Either way the reading comes from the current semantic root rather than a
  // retained input that could omit a later local gesture or accepted reading.
  //
  // A tick can also land in the middle of a pass paint, while it waits on a frozen
  // widget. That runs `renderReading` again, and `surfaceGeneration` settles which of
  // the two the page keeps: the newer one, exactly as a newer claim supersedes an older
  // reading a rank up. The pass paint then returns having drawn nothing, and its ticket
  // is still honest, because what stands in the region is the newer reading of the same
  // root. The clock has to reach `renderReading` synchronously either way — `clocked`
  // records which relative-time readings a paint made while that paint runs, and a claim
  // that returns before the pass would record none and unsubscribe the conversation from
  // the clock altogether.
  const paintCurrent = clocked(document.body, () =>
    painting ? renderCurrent() : present(),
  );

  function mount() {
    threadsBox.addEventListener("lf-reveal", (event) => {
      const hidden = event.detail?.target?.closest?.(".lf-thread[hidden]");
      if (hidden) event.detail?.present?.(revealThread(hidden.dataset.id, present));
    });
  }

  return {
    mount,
    present,
  };
}
