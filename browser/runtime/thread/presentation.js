/* Thread presentation across page seats, widget outlets, the primary reader and the
   margin.

   This owner receives records and narrow view capabilities. It never reads delivery,
   assembles protocol events, or imports state application. It reads the published fold
   for every textual/geometry view. It is an epoch presenter: the publication claims its
   region and the pass paints it, after the projection whose provenance words its
   passages resolve over. Its presentation ticket commits the thread surfaces
   together with the primary reader's preparation. Surface
   callbacks nominate outlets during preparation; their seats, composer and ownership
   commit together after every required member is ready. A mechanical
   repaint — a draft, a hover — claims the same region through `present`.
   Reply continuity begins after commit and runs independently: its selected route may
   itself need this renderer to finish. Its caret follows the actual returned editor;
   its failures reach the page's existing asynchronous error channel. */
import { untracked } from "/vendor/browser-runtime.js";
import { keeps } from "../keeps.js";
import { reportPageError } from "../layer-client.js";
import { elementById, inChrome } from "../passages.js";
import { threadState, readThreads } from "./state.js";
import { holdThreadPlace } from "./focus.js";
import { holdReplyCompositions } from "./replies.js";
import { surfaceFocusTarget } from "./surfaces.js";
import {
  renderSeats,
  beginThreadSeats,
  commitThreadSeats,
  retainThreadSeats,
} from "./inline.js";
import { applicationPresenter, PRESENTATION_DOM } from "../semantic-state.js";
import { runtime } from "../context.js";

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
  returnToPage,
  threadAt,
  read,
}) {
  let primary = null;

  // The paint follows what it reads, before it waits for preparation and in the
  // continuations it resumes after (`renderReading`). The margin this presentation
  // renders once it commits also draws the Questions and the workflows; its own watcher
  // follows those (`annotationSelection`).
  //
  // Before the page has read the log, an epoch with no thread draws the same line about
  // waiting, and repainting the margin and the anchors to say it again is work done
  // ahead of the first paint the user is waiting on, so all of them read as one
  // unchanging value. A thread the user starts in that window is drawn, and so is its
  // removal, the refusal of the last send included. A caller that asks for the reading
  // directly, through `present`, gets it: every phase owes a reading when asked. A page that draws no thread surface (`available` false, as an
  // offline export does) owes no reading at all.
  const presenter = applicationPresenter({
    region: "thread",
    after: PRESENTATION_DOM.projection,
    reading: () =>
      !available
        ? null
        : runtime.statePhase === "waiting" && !threadState().all.length
          ? "waiting"
          : true,
    // A pass reads the latest root. The time it shows is followed with the rest of what
    // it reads, so a clock change claims another pass through the same presenter, whose
    // current predicate also retires in-flight preparation.
    paint: async (value, current, resume) => {
      await startRender(current, resume);
      return value;
    },
  });

  const present = () => presenter.present();

  let surfaceGeneration = 0;
  let cancelCurrentRender = () => {};
  const startRender = (presenting, resume = (run) => run) => {
    cancelCurrentRender();
    /** @type {PromiseWithResolvers<void>} */
    const { promise: cancelled, resolve } = Promise.withResolvers();
    cancelCurrentRender = resolve;
    return renderReading(cancelled, presenting, resume);
  };

  // A continuation the pass resumes joins its reads, of the publication and the clock.
  async function renderReading(cancelled, presenting, resume) {
    const generation = ++surfaceGeneration;
    read.begin();
    const current = () => generation === surfaceGeneration && presenting();
    const batch = beginThreadSeats();
    // Where the user is on a thread, which this pass may take off the surface drawing
    // it (thread/focus.js, `holdThreadPlace`).
    const restorePlace = holdThreadPlace(openThread, {
      threadAt,
      seated: (id) => Boolean(surfaceFocusTarget(id, { part: "thread" })),
    });
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
        renderSeats(listed, inlineView);
        // Capture every core message age before yielding to a package.
        // Their shared clock refreshes this whole presentation, including its outlets.
        // Register the cohort's commit before yielding: its synchronous writes belong
        // to this requested reading, while preparation and continuity remain separate.
        return Promise.race([
          Promise.all([
            surfaces.completion,
            // The reader paints after this stretch, so what it reads is its own.
            Promise.resolve().then(() =>
              current() && primaryCandidate?.current()
                ? primaryCandidate.paint()
                : null,
            ),
          ]).then(() => true),
          cancelled.then(() => false),
        ]).then(
          resume((completed) => {
            if (!completed || !current()) return;
            // Preparation may materialize or retire targets without another publication.
            // Preserve immediate semantic paint, then refresh the same directory and its
            // retained decoration before any nominated surface actually moves.
            readTargets();
            surfaces.commit();
            commitThreadSeats(batch);
            // The margin is an owner of its own, with its own watcher; this pass only
            // refreshes it over the targets it moved, so what it reads is not this paint's.
            untracked(renderAnnotations);
            pageGeometry.pageShifted();
            read.present();
            // Continuity may reveal a route needing this very presenter. Its work starts
            // after the cohort commits, and never joins the ticket it is completing.
            // Once the user is placed, a thread the primary held as the last resort goes
            // back to the page where the page now draws its place (thread/destination.js,
            // `returnToPage`).
            void continueReplies(restorePlace)
              .then(returnToPage)
              .catch((error) => reportPageError(error, `Reply continuation failed`));
          }),
        );
      };
      await (primaryPreparation?.then
        ? primaryPreparation.then(resume(paintPrepared))
        : paintPrepared(primaryPreparation));
    } catch (error) {
      surfaces?.cancel();
      if (!current()) throw error;
      // Placement and control preparation both read visual coordinates. A failure
      // in either invalidates the proxies retained from the previous reading.
      anchorControls.withholdVisualActions();
      read.abort();
      primary?.cancel();
      if (!current()) return;
      retainThreadSeats(batch);
      throw error;
    }
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
  return {
    present,
    registerPrimary,
  };
}
