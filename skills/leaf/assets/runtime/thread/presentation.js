/* Thread presentation across panel, page seats, widget outlets, and margin.

   This owner receives records and narrow view capabilities. It never reads delivery,
   assembles protocol events, or imports state application. It reads the published fold
   for every textual/geometry view. It is an epoch presenter: the publication claims its
   region and the pass paints it, after the projection whose provenance words its
   passages resolve over. Its presentation ticket commits the thread surfaces
   together with preparation for frozen widgets newly joined to the panel. Surface
   callbacks nominate outlets during preparation; their seats, composer and ownership
   commit together after every required member is ready. A mechanical
   repaint — a draft, a hover, a narrowing — claims the same region through `present`.
   Reply continuity begins after commit and runs independently: its selected route may
   itself need this renderer to finish. Its caret follows the actual returned editor;
   its failures reach the page's existing asynchronous error channel. */
import { clocked } from "../presence.js";
import { keeps } from "../keeps.js";
import { reportPageError } from "../layer-client.js";
import { closestAcross, elementById, inChrome } from "../passages.js";
import { threadState, readThreads } from "./state.js";
import { holdReply } from "./focus.js";
import { holdReplyCompositions } from "./replies.js";
import {
  renderSeats,
  beginThreadSeats,
  commitThreadSeats,
  retainThreadSeats,
} from "./inline.js";
import { applicationPresenter, PRESENTATION_ORDER, readPart } from "../semantic-state.js";
import { runtime } from "../context.js";

const readDocument = readPart((root) => root.document);

// Each held element names the thread holding it, decided whole before any is written, so
// an element that stays held is not cleared and marked again.
function renderHolds(threads) {
  const held = new Map();
  for (const thread of threads) {
    if (thread.resolved || !thread.root.holds || thread.root.pending) continue;
    const target = elementById(thread.root.holds);
    if (target && !inChrome(target)) held.set(target, thread.id);
  }
  for (const node of document.querySelectorAll("[data-lf-held]"))
    if (!held.has(node)) node.removeAttribute("data-lf-held");
  for (const [target, id] of held) keeps(target, "data-lf-held", id);
}

export function createThreadPresentation({
  available = true,
  inlineView,
  surfaceView,
  anchorPlacement,
  anchorPaint,
  anchorControls,
  drawingPaint,
  pageGeometry,
  readDraft,
  activeActionAnchor,
  renderAnnotations,
  renderSurfaces,
  openThread,
  continueThread,
  read,
}) {
  const panels = new Set();
  let mounted = false;
  let primary = null;

  // The parts of the root a thread presentation draws: the fold itself, whose records
  // already carry the receipts and attention the workflows give them, and the document
  // whose messages, descriptors and revision the cards name. A publication that moves
  // neither — a widget's own action, say — claims nothing, and the current presentation
  // carries into the new epoch. The margin this presentation renders once it commits
  // also draws the Questions and the workflows; its own watcher follows those
  // (`annotationSelection`).
  //
  // Before the page has read the log, an epoch with no thread draws the same line about
  // waiting, and repainting the margin and the anchors to say it again is work done
  // ahead of the first paint the user is waiting on, so all of them read as one
  // unchanging value. A thread the user starts in that window is drawn, and so is its
  // removal, the refusal of the last send included. A user who opens the panel then
  // asks for the reading directly, through `present`, and gets it: every phase owes a
  // reading when asked. A page that draws no thread surface (`available` false, as an
  // offline export does) owes no reading at all.
  const presenter = applicationPresenter({
    region: "thread",
    order: PRESENTATION_ORDER.thread,
    reading: () =>
      !available
        ? null
        : runtime.statePhase === "waiting" && !threadState().all.length
          ? "waiting"
          : { phase: runtime.statePhase, thread: threadState(), document: readDocument() },
    paint: async (value, current) => {
      const phase = runtime.statePhase;
      // A pass reads the latest root. Clock changes claim another pass through the
      // same presenter, so its current predicate also retires in-flight preparation.
      if (phase === "ready") await paintCurrent(current);
      else {
        paintCurrent.stop();
        await startRender(current);
      }
      return value;
    },
  });

  const present = () => presenter.present();

  let surfaceGeneration = 0;
  let cancelCurrentRender = () => {};
  const startRender = (presenting) => {
    cancelCurrentRender();
    /** @type {PromiseWithResolvers<void>} */
    const { promise: cancelled, resolve } = Promise.withResolvers();
    cancelCurrentRender = resolve;
    return renderReading(cancelled, presenting);
  };

  async function renderReading(cancelled, presenting) {
    const generation = ++surfaceGeneration;
    read.begin();
    const current = () => generation === surfaceGeneration && presenting();
    const batch = beginThreadSeats();
    // The reply the user is writing, which this pass may take off the surface drawing it
    // (thread/focus.js, `holdReply`).
    const restoreReply = holdReply(openThread);
    let prepared = null;
    const livePanels = [...panels].filter((panel) => panel.threadsBox.isConnected);
    let surfaces = null;
    try {
      const { all: threads } = threadState();
      const collection = readThreads();
      const listed = collection.threads;
      const continueReplies = holdReplyCompositions(threads, continueThread);
      renderHolds(threads);
      const readTargets = () => {
        const anchors = anchorPlacement.read({
          threads,
          draft: readDraft(),
          actionAnchor: activeActionAnchor(),
        });
        if (anchors) {
          anchorPaint?.paint(anchors);
          anchorControls.render(anchors);
        }
        drawingPaint.paint();
      };
      readTargets();
      surfaces = renderSurfaces(collection, anchorPlacement, surfaceView);
      void surfaces.completion.catch(() => {});
      const primaryPreparation = primary?.owner.isConnected
        ? primary.prepare(collection, cancelled)
        : null;
      const paintPrepared = (primaryCandidate) => {
        if (!current()) return;
        prepared = Promise.all(
          livePanels.map(({ controller, view }) =>
            controller.renderThreads(collection, view),
          ),
        );
        void prepared.catch(() => {});
        renderSeats(listed, inlineView);
        // Capture every core message and approval age before yielding to a package.
        // Their shared clock refreshes this whole presentation, including its outlets.
        // Register the cohort's commit before yielding: its synchronous writes belong
        // to this requested reading, while preparation and continuity remain separate.
        return Promise.race([
          Promise.all([
            surfaces.completion,
            prepared.then((candidates) => {
              if (current() && primaryCandidate?.current())
                return primaryCandidate.paint().then(() => candidates);
              return candidates;
            }),
          ]),
          cancelled.then(() => null),
        ]).then((result) => {
          if (!result) return;
          const [, candidates] = result;
          if (!current()) return;
          for (const candidate of candidates) candidate?.commit();
          // Preparation may materialize or retire targets without another publication.
          // Preserve immediate semantic paint, then refresh the same directory and its
          // retained decoration before any nominated surface actually moves.
          readTargets();
          surfaces.commit();
          commitThreadSeats(batch);
          surfaceView.composition.finishPlacement();
          renderAnnotations();
          pageGeometry.pageShifted();
          read.present();
          // Continuity may reveal a route needing this very presenter. Its work starts
          // after the cohort commits, and never joins the ticket it is completing.
          void continueReplies(restoreReply).catch((error) =>
            reportPageError(error, `Reply continuation failed`),
          );
        });
      };
      await (primaryPreparation?.then
        ? primaryPreparation.then(paintPrepared)
        : paintPrepared(primaryPreparation));
    } catch (error) {
      surfaces?.cancel();
      if (!current()) throw error;
      // Placement and control preparation both read visual coordinates. A failure
      // in either invalidates the proxies retained from the previous reading.
      anchorControls.withholdVisualActions();
      read.abort();
      primary?.cancel();
      // A synchronous sibling failure may leave the panel's widget preparation in
      // flight. Invalidate its private generation before restoring the whole reading.
      await Promise.all(
        livePanels.map(async ({ controller, view }) => {
          if (!primary) return controller.restoreThreadList();
          controller.cancel();
          const fallback = await controller.renderThreads(readThreads(), view);
          if (current()) fallback?.commit();
        }),
      );
      if (!current()) return;
      retainThreadSeats(batch);
      throw error;
    }
  }

  const paintCurrent = clocked(document.body, startRender, present);

  function onReveal({ threadsBox, view }, event) {
    const target = event.detail?.target;
    const thread = target && closestAcross(target, ".lf-thread");
    if (!thread) return;
    const id = thread.dataset.id;
    if (thread.hidden) {
      const { mayReveal } = event.detail;
      const revealed = view.narrowing.revealThread(id);
      if (revealed)
        event.detail.present(
          revealed.then(() => {
            if (mayReveal() && thread.isConnected) threadsBox.revealNavigation(id);
          }),
        );
    } else threadsBox.revealNavigation(id);
  }

  function attach(panel) {
    const listener = (event) => onReveal(panel, event);
    panel.threadsBox.addEventListener("lf-reveal", listener);
    panel.detach = () => panel.threadsBox.removeEventListener("lf-reveal", listener);
  }

  function registerPanel({ controller, threadsBox, view }) {
    const panel = { controller, threadsBox, view, detach: () => {} };
    panels.add(panel);
    if (mounted) {
      attach(panel);
      void present();
    }
    return {
      update: present,
      unregister() {
        if (!panels.delete(panel)) return;
        panel.detach();
        controller.cancel();
        if (mounted) void present();
      },
    };
  }

  function registerPrimary(reader) {
    if (primary) throw new Error("The page already has a primary Thread presentation");
    primary = reader;
    void present();
    return () => {
      if (primary !== reader) return;
      primary = null;
      reader.unregister();
      void present();
    };
  }
  function primaryOwnsMessage(message) {
    return primary?.ownsMessage(message) ?? false;
  }

  function mount() {
    mounted = true;
    for (const panel of panels) attach(panel);
  }

  return {
    mount,
    present,
    registerPanel,
    registerPrimary,
    primaryOwnsMessage,
  };
}
