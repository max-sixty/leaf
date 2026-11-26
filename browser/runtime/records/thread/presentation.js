/* Thread presentation across widget outlets, the primary reader and the margin.

   This owner receives records and narrow view capabilities. It never reads delivery,
   assembles protocol events, or imports state application. It reads the published fold
   for every textual/geometry view. It is an epoch presenter: the publication claims its
   region and the pass paints it, after the projection whose provenance words its
   passages resolve over. Its presentation ticket commits the thread surfaces
   together with the primary reader's preparation. Surface
   callbacks nominate outlets during preparation; their seats, composer and ownership
   commit together after every required member is ready. A mechanical
   repaint — a draft, a hover — claims the same region through `present`.
   The pass paints no other owner's region: what it decides about a thread reaches the
   margin as readings the margin's paint follows (annotations/anchor-placement.js `placedAt`,
   surfaces.js `claimed`), so a commit that moves one has the margin
   repainted before the pass settles, and one that moves none leaves it drawn once.
   Reply continuity begins once the margin has committed, since the route it lands on
   may be a margin card, and runs independently: its selected route may itself need
   this renderer to finish. Its caret follows the actual returned editor; its failures
   reach the page's existing asynchronous error channel. */
import { reportPageError } from "../../transport/layer-client.js";
import { readThreads, threadList } from "./state.js";
import { holdThreadPlace } from "./focus.js";
import { holdReplyCompositions } from "./replies.js";
import { surfaceFocusTarget } from "./surfaces.js";
import { beginThreadSeats, commitThreadSeats, retainThreadSeats } from "./inline.js";
import { applicationPresenter, PRESENTATION_DOM } from "../../state/semantic-state.js";
import { runtime } from "../../state/context.js";
import { draftAnchor, draftsReading } from "../drafts.js";

/** @typedef {ReturnType<typeof import("./primary-reader.js").createPrimaryReader>} PrimaryReader */
/** @typedef {import("../../state/semantic-state.js").Resume} Resume */
/** @import { PlacementReading, Thread, ThreadDraft, ThreadPlacements } from "./placement.js" */
/** @import { Anchor } from "../../../types/domain.js" */
/** @param {{surfaceView: import("./thread-card.js").ThreadCommands & {composition: import("./surfaces.js").CompositionSurface & {
 * finishPlacement: () => unknown}},
 * anchorPlacement: Pick<ThreadPlacements, "placedAt" | "pendingAt"> & {read: (options: {threads: readonly Thread[],
 * draft: ThreadDraft, actionAnchor: Anchor | null, saved: readonly {context: string, anchor: Anchor}[]}) => PlacementReading | null},
 * anchorPaint: {paint: (reading: PlacementReading) => unknown},
 * anchorControls: {render: (reading: PlacementReading) => unknown, withholdVisualActions: () => unknown},
 * drawingPaint: {paint: () => unknown},
 * pageGeometry: {pageShifted: () => unknown},
 * readDraft: () => ThreadDraft,
 * activeActionAnchor: () => import("../../../types/domain.js").Anchor | null,
 * renderSurfaces: typeof import("./surfaces.js").renderSurfaces,
 * openThread: ReturnType<typeof import("./destination.js").createThreadDestinations>["openPageThread"],
 * continueThread: Parameters<typeof holdReplyCompositions>[1],
 * returnToPage: ReturnType<typeof import("./destination.js").createThreadDestinations>["returnToPage"],
 * threadAt: ReturnType<typeof import("./destination.js").createThreadDestinations>["threadAtCurrentLocation"],
 * travellingTo: (id: string) => boolean,
 * marginCommitted: () => unknown,
 * read: Pick<ReturnType<typeof import("./read.js").createReadTracking>, "begin" | "present" | "abort">}} dependencies */
export function createThreadPresentation({
  surfaceView,
  anchorPlacement,
  anchorPaint,
  anchorControls,
  drawingPaint,
  pageGeometry,
  readDraft,
  activeActionAnchor,
  renderSurfaces,
  openThread,
  continueThread,
  returnToPage,
  threadAt,
  travellingTo,
  marginCommitted,
  read,
}) {
  /** @type {PrimaryReader | null} */
  let primary = null;

  // The paint follows what it reads, before it waits for preparation and in the
  // continuations it resumes after (`renderReading`).
  //
  // Before the page has read the log, an epoch with no thread draws the same line about
  // waiting, and repainting the margin and the anchors to say it again is work done
  // ahead of the first paint the user is waiting on, so all of them read as one
  // unchanging value. A thread the user starts in that window is drawn, and so is its
  // removal, the refusal of the last send included. A caller that asks for the reading
  // directly, through `present`, gets it: every phase owes a reading when asked.
  const presenter = applicationPresenter({
    region: "thread",
    after: PRESENTATION_DOM.projection,
    reading: () =>
      runtime.statePhase === "waiting" && !threadList().length ? "waiting" : true,
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
  /** @param {() => boolean} presenting @param {Resume} [resume] */
  const startRender = (presenting, resume = (run) => run) => {
    cancelCurrentRender();
    /** @type {PromiseWithResolvers<void>} */
    const { promise: cancelled, resolve } = Promise.withResolvers();
    cancelCurrentRender = resolve;
    return renderReading(cancelled, presenting, resume);
  };

  // A continuation the pass resumes joins its reads, of the publication and the clock.
  /** @param {Promise<void>} cancelled @param {() => boolean} presenting @param {Resume} resume */
  async function renderReading(cancelled, presenting, resume) {
    const generation = ++surfaceGeneration;
    read.begin();
    const current = () => generation === surfaceGeneration && presenting();
    const batch = beginThreadSeats();
    // Where the user is on a thread, which this pass may take off the surface drawing
    // it (records/thread/focus.js, `holdThreadPlace`).
    const restorePlace = holdThreadPlace(openThread, {
      threadAt,
      seated: (id) => Boolean(surfaceFocusTarget(id, { part: "thread" })),
      travellingTo,
    });
    /** @type {ReturnType<typeof renderSurfaces> | null} */
    let surfaces = null;
    try {
      const collection = readThreads();
      const { threads } = collection;
      const continueReplies = holdReplyCompositions(threads, continueThread);
      const readTargets = () => {
        const anchors = anchorPlacement.read({
          threads,
          draft: readDraft(),
          actionAnchor: activeActionAnchor(),
          saved: draftsReading().flatMap((saved) => {
            const anchor = draftAnchor(saved);
            return anchor ? [{ context: saved.context, anchor }] : [];
          }),
        });
        if (anchors) {
          anchorPaint.paint(anchors);
          anchorControls.render(anchors);
        }
        drawingPaint.paint();
      };
      readTargets();
      const surface = renderSurfaces(collection, anchorPlacement, surfaceView);
      surfaces = surface;
      void surface.completion.catch(() => {});
      const primaryPreparation = primary?.owner.isConnected
        ? primary.prepare(collection, cancelled)
        : null;
      /** @param {Awaited<ReturnType<PrimaryReader["prepare"]>>} primaryCandidate */
      const paintPrepared = (primaryCandidate) => {
        if (!current()) return;
        // Capture every core message age before yielding to a package.
        // Their shared clock refreshes this whole presentation, including its outlets.
        // Register the cohort's commit before yielding: its synchronous writes belong
        // to this requested reading, while preparation and continuity remain separate.
        return Promise.race([
          Promise.all([
            surface.completion,
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
            surface.commit();
            commitThreadSeats(batch);
            surfaceView.composition.finishPlacement();
            pageGeometry.pageShifted();
            read.present();
            // Continuity lands the user where the pass left their thread, a margin card
            // included, so it starts once the margin has committed (`marginCommitted`)
            // rather than when the whole pass settles. The margin's claim for what this
            // commit moved lands when this stretch's batch ends, so its commit is read a
            // microtask later. A margin owing no repaint has already committed; one that
            // repaints commits after the DOM upstream of it, so a widget holding its
            // commit, as through a drag, still delays continuity. It may reveal a route
            // needing this very presenter, and never joins the ticket it is completing.
            // Once the user is placed, a thread the primary held as the last resort goes
            // back to the page where the page now draws its place
            // (records/thread/destination.js, `returnToPage`).
            void Promise.resolve()
              .then(marginCommitted)
              .then(() => continueReplies(restorePlace))
              .then(returnToPage)
              .catch((error) => reportPageError(error, `Reply continuation failed`));
          }),
        );
      };
      await (primaryPreparation && "then" in primaryPreparation
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

  /** @param {PrimaryReader} reader */
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
