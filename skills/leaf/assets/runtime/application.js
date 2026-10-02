/* Fixed composition root for browser state, optimistic work, and presentation.

   Importing this module is inert. leaf.js supplies the concrete feature views once and
   mounts the application before widget upgrade; exported functions are stable closures
   for the public widget API and fail clearly if invoked before that boundary. */
import { runtime } from "./context.js";
import {
  applicationState,
  readApplication,
  setPresentationFailureReporter,
  whenApplicationRegionsPresented,
  whenWidgetsPresented,
  presentDocument,
} from "./semantic-state.js";
import { newAttempt } from "./drafts.js";
import { saidNow } from "./presence.js";
import { announce, notice } from "./notifications.js";
import {
  approvalBlockingAsks as readApprovalBlockingAsks,
  openAsks as readOpenAsks,
  unansweredAsks as readUnansweredAsks,
  watchAsks as observeAsks,
} from "./asks/model.js";
import { paintKeys } from "./keyboard/scopes.js";
import { pendingTraffic } from "./traffic.js";
import { createPendingLedger } from "./pending/state.js";
import { createDelivery, deliverBookkeeping } from "./delivery.js";
import {
  createProjectionPresentation,
  shallowSigs as projectionShallowSigs,
} from "./projection/presentation.js";
import { projectionDeferred } from "./projection/state.js";
import { createProjectionCommands } from "./projection/commands.js";
import { createDataProjection } from "./projection/data.js";
import { createThreadPresentation } from "./thread/presentation.js";
import { createAnnotationInventory } from "./annotation-inventory.js";
import { createInlineContributions } from "./inline-contributions.js";
import { presentingContributions, watchContributions } from "./contributions.js";
import { watchProjection } from "./projection-watch.js";
import { clocked } from "./presence.js";
import { createThreadDestinations } from "./thread/destination.js";
import { createThreadActions } from "./thread/actions.js";
import { registerMirrorConsumer } from "./thread/mirrors.js";
import { createReadTracking } from "./thread/read.js";
import { renderMarginThread } from "./thread/inline.js";
import { threadBox as buildThreadBox } from "./thread/box.js";
import { messageText } from "./thread/messages.js";
import { isThreadEvent } from "./pending/model.js";
import {
  focusSurface,
  consumeThreads as registerConsumer,
  consumePageThreads as registerPageConsumer,
  renderSurfaces,
} from "./thread/surfaces.js";
import { createStateApplication } from "./state-application.js";
import { beginRead as beginStateRead, createStateFeed } from "./state-feed.js";
import { createProjectionUpdates } from "./updates.js";

let application = null;
const app = () => {
  if (!application) throw new Error("Leaf application has not been mounted");
  return application;
};

export function mountApplication(dependencies) {
  if (application) throw new Error("Leaf application mounted twice");
  setPresentationFailureReporter(dependencies.reportPageError);
  const ledger = createPendingLedger({
    newAttempt,
    enqueue: (event) =>
      applicationState.enqueue(
        event,
        saidNow(),
        isThreadEvent(event) ? messageText(event) : undefined,
      ),
  });
  const hasPending = () => ledger.snapshot().length > 0;
  const engagement = dependencies.createEngagement({
    hasPending,
    fabAnchorAt: dependencies.activeActionAnchor,
    targetPickerOpen: dependencies.targetPickerOpen,
    pageComposerDrawing: dependencies.pageComposerDrawing,
  });
  let threadPresenter;
  let stateApplication;
  let queuedInvalidation = false;

  const stateApplying = () => stateApplication?.isApplying() ?? false;

  const currentReceipts = () => readApplication().authoritative?.browser.receipts ?? [];
  const pendingApprovals = () => readApplication().effective.pendingApprovals;
  const acceptedApprovals = () => readApplication().effective.acceptedApprovals;
  const openAsks = readOpenAsks;
  const unansweredAsks = readUnansweredAsks;
  const approvalBlockingAsks = readApprovalBlockingAsks;
  const watchAsks = observeAsks;

  // Retire the entries the ledger's lifecycle says wait only for release, once every
  // region that draws them has committed the reading that no longer does.
  const releasePending = async () => {
    const candidates = ledger.releasable();
    if (!candidates.length) return false;
    const attempts = new Set(candidates.map((entry) => entry.event.attempt));
    const stillCurrent = () =>
      ledger.releasable().some((entry) => attempts.has(entry.event.attempt));
    await Promise.all([
      whenWidgetsPresented([
        ...new Set(
          candidates
            .filter((entry) => entry.event.kind === "action")
            .map((entry) => entry.event.widget),
        ),
      ]),
      whenApplicationRegionsPresented(
        ["projection:chrome", "thread", "asks"],
        stillCurrent,
      ),
    ]);
    // Waiting can cross a newer publication. Retire only the candidates selected
    // before the wait and only if their semantic settlement still permits release.
    const released = ledger
      .releasable()
      .filter((entry) => attempts.has(entry.event.attempt));
    // Widget updates and the thread, projection, and Ask owners have now committed
    // this surviving semantic reading. Paint its command surface while the same pending
    // records still stand; removing an accounted record is then a semantic no-op.
    if (!released.length) return false;
    paintKeys();
    ledger.release(released);
    return true;
  };

  const releasePendingSafely = (context) => {
    void releasePending().catch((error) => console.error(`leaf: ${context}`, error));
  };

  // The document-wide pass. Every presenter claims its region now and paints the current
  // semantic root on the pass that follows, in the order semantic-state.js declares, so
  // a caller that changes what the page shows only has to say so — it names no renderer
  // and cannot leave one out. What comes back is the whole pass.
  //
  // A state application holds the pass: the reading it is presenting owns the retained
  // surfaces, and a second pass arriving mid-recovery would supersede the one restoring
  // them and leave the fault unaccounted. `flushQueuedInvalidation` runs the one it
  // collected once that reading is on the page.
  const invalidateDom = () => {
    if (stateApplying()) {
      queuedInvalidation = true;
      return Promise.resolve();
    }
    return presentDocument();
  };

  const retryProjection = () => {
    if (!projectionDeferred()) return false;
    if (stateApplying()) {
      queuedInvalidation = true;
      return false;
    }
    invalidateDom();
    return true;
  };

  const projection = createProjectionPresentation({
    onDeferredReady: () => {
      if (!retryProjection()) return;
      releasePendingSafely("deferred pending release");
    },
  });
  const dataProjection = createDataProjection({ invalidateDom });

  let delivery;
  const presentThread = () => threadPresenter.present();
  // A mechanical repaint — a draft, a hover, a narrowing — owes only the threads.
  // The presentation coordinator has already reported any paint that failed, once, for
  // the region that owns it; this observes the rejection rather than accounting for the
  // same fault a second time.
  const refreshThread = () => presentThread().catch(() => undefined);

  function startPost(event) {
    const entry = ledger.enqueue(event);
    if (!entry) {
      notice(`Couldn't send — attempt ${event.attempt} is already in use`);
      return null;
    }
    let presentationError = null;
    let threadPresentation = Promise.resolve();
    try {
      pendingTraffic(readApplication().effective.sending);
      projection.stageOptimistic(entry);
      // Desired state changes at enqueue even where the widget has already painted the
      // same value, so this gesture reaches the page on the pass the enqueue opened,
      // before transport. It claims directly rather than through `invalidateDom`: a
      // state application held on some renderer's preparation holds background repaints,
      // and a user's own gesture is not one of those — what the page can draw of it
      // does not wait for an answer the log has not given.
      // The presentation coordinator reports a failed paint once, for the region that
      // owns it. Observe the pass here so this gesture's own promise carries no
      // unhandled rejection and no second account of one fault.
      threadPresentation = presentDocument().catch(() => undefined);
    } catch (error) {
      presentationError = error;
    } finally {
      try {
        if (entry.message) announce("Message sent");
        paintKeys();
      } catch (error) {
        presentationError ??= error;
      } finally {
        // The durable gesture has entered the one ledger. A local paint failure cannot
        // strand it before transport or leave every later send waiting behind an
        // unanswered entry.
        void delivery.drain();
      }
    }
    // The returned promise describes the server's durable decision. Report a local
    // optimistic-presentation failure without turning an accepted gesture into an
    // apparent refusal for callers that restore drafts or clear busy state from it.
    if (presentationError)
      console.error("leaf: optimistic presentation", presentationError);
    return Object.freeze({
      answer: entry.answer,
      presentation: threadPresentation,
    });
  }

  const post = (event) => startPost(event)?.answer ?? Promise.resolve(null);

  function dispatchWidget(descriptor, command) {
    const reading = applicationState.selectWidget(descriptor).read();
    if (command.kind === "undo") {
      // Only an exact candidate this widget's reading offers, by attempt or id.
      const candidate = Object.values(reading.actions)
        .flatMap(({ undo }) => undo)
        .find(
          (event) => event.attempt === command.target || event.id === command.target,
        );
      return candidate ? projectionCommands.withdraw(candidate) : null;
    }
    if (!reading.actions[command.verb]?.available) return null;
    return (
      startPost({
        kind: "action",
        revision: runtime.currentRevision,
        widget: descriptor.id,
        action: command.verb,
        detail: structuredClone(command.detail ?? {}),
        ...(command.attempt && { attempt: command.attempt }),
      })?.answer ?? null
    );
  }

  const projectionCommands = createProjectionCommands({
    post,
    stateApplying,
    unaccountedGesture: engagement.unaccountedGesture,
  });
  const projectionUpdates = createProjectionUpdates({
    coordinateProjectionCommitted: projection.coordinateProjectionCommitted,
  });

  const createComment = (event) =>
    post({ kind: "comment", revision: runtime.currentRevision, ...event });
  // The one bookkeeping door (delivery.js): the page draws the versions read as it
  // sends them, and they stand read or unread again by whatever the answer says.
  const markRead = async (messages) => {
    applicationState.markRead(messages);
    try {
      return await deliverBookkeeping({ kind: "read", messages }, receiveState);
    } finally {
      applicationState.settleMarkRead(messages);
    }
  };
  const read = createReadTracking({
    markRead,
    showThread: dependencies.showThread,
    firstUnreadBtn: dependencies.firstUnreadBtn,
  });

  const threadActions = createThreadActions({
    post,
    withdraw: projectionCommands.withdraw,
    sendReaction: dependencies.sendReaction,
    currentRevision: () => runtime.currentRevision,
  });
  const replyView = {
    actions: threadActions,
    wireInput: dependencies.wireInput,
    landSent: dependencies.landSent,
  };
  const settlementView = {
    pendingEntries: ledger.snapshot,
    actions: threadActions,
    retainReversal: projectionCommands.retainReversal,
  };
  const reactionView = {
    registerSurface: dependencies.registerReactSurface,
    actions: threadActions,
  };
  const inlineView = {
    reply: replyView,
    settlement: settlementView,
    reaction: reactionView,
    read,
    showThread: dependencies.showThread,
    landInThread: dependencies.landInThread,
  };
  const cardView = {
    reply: replyView,
    settlement: settlementView,
    reaction: reactionView,
    read,
    anchors: {
      placedAt: dependencies.anchorPlacement.placedAt,
    },
    travel: {
      focusSurface,
      scrollToThread: dependencies.anchorTravel.scrollToThread,
    },
  };
  const surfaceView = {
    ...inlineView,
    composition: dependencies.compositionSurface,
  };

  const annotations = createAnnotationInventory({
    openAsks,
    comparisonBase: dependencies.margin.comparisonBase,
    comparisonChanges: dependencies.margin.comparisonChanges,
    inlineComparison: dependencies.margin.inlineComparison,
    toggleInlineComparison: dependencies.margin.toggleInlineComparison,
    placedAt: dependencies.anchorPlacement.placedAt,
    showThread: dependencies.showThread,
    goToAsk: dependencies.margin.goToAsk,
    scrollToElement: dependencies.anchorTravel.scrollToElement,
  });
  const inlineContributions = createInlineContributions(annotations);
  // Print hides contributed controls and cannot supply their visibility reading.
  // Refuse the annotation pass whole until the document returns to screen media.
  const onPaper = matchMedia("print");
  function refreshAnnotationInventory() {
    if (onPaper.matches) return annotations.read();
    presentingContributions();
    inlineContributions.present();
    const entries = annotations.collect();
    dependencies.margin.renderPageMapDialog(entries);
    return entries;
  }
  const renderAnnotations = clocked(document.body, () => {
    if (!onPaper.matches) margin.paint(refreshAnnotationInventory());
  });
  const mountAnnotations = () => {
    watchProjection(document.body, renderAnnotations);
    document.addEventListener("lf-comparison", renderAnnotations);
    onPaper.addEventListener("change", () => {
      if (!onPaper.matches) renderAnnotations.refresh();
    });
    watchContributions(({ immediate }) => {
      renderAnnotations();
      if (immediate) margin.flushLayout();
    });
  };
  const margin = dependencies.createMarginProjection({
    inventory: annotations,
    refreshInventory: refreshAnnotationInventory,
    renderAnnotations,
    openPageThread: (...args) => threadDestinations.openPageThread(...args),
    panelIsOpen: dependencies.panelIsOpen,
    panel: dependencies.panel,
    accompaniedThread: dependencies.accompaniedThread,
    accompanyThread: dependencies.accompanyThread,
    designModeActive: dependencies.margin.designModeActive,
    pointerModeActive: dependencies.margin.pointerModeActive,
    leavePageMap: dependencies.margin.leavePageMap,
    openPageMap: dependencies.margin.openPageMap,
    pageMapDialogContains: dependencies.margin.pageMapDialogContains,
    scrollThreadIntoView: dependencies.margin.scrollThreadIntoView,
    renderMarginThread: (host, thread, controls) =>
      renderMarginThread(host, thread, inlineView, controls),
    placedAt: dependencies.anchorPlacement.placedAt,
    scrollToElement: dependencies.anchorTravel.scrollToElement,
  });
  const threadDestinations = createThreadDestinations({
    placedAt: dependencies.anchorPlacement.placedAt,
    panelIsOpen: dependencies.panelIsOpen,
    showThread: dependencies.showThread,
    scrollToThread: dependencies.anchorTravel.scrollToThread,
    preview: margin.threadPreview,
  });

  threadPresenter = createThreadPresentation({
    available: dependencies.threadAvailable ?? true,
    inlineView,
    surfaceView,
    anchorPlacement: dependencies.anchorPlacement,
    anchorPaint: dependencies.anchorPaint,
    anchorControls: dependencies.anchorControls,
    drawingPaint: dependencies.drawingPaint,
    pageGeometry: dependencies.pageGeometry,
    readDraft: dependencies.readThreadDraft,
    activeActionAnchor: dependencies.activeActionAnchor,
    renderAnnotations,
    renderSurfaces,
    // Where a thread stands now, put up for a user carried there from a box a surface
    // stopped drawing: the surface drawing it, its margin card, or the panel.
    openThread: (id, options) =>
      threadDestinations.openPageThread(id, { ...options, travel: false }),
    read,
  });
  const registerThreadPanel = ({ controller, threadsBox, view, required = false }) => {
    let registration;
    registration = threadPresenter.registerPanel({
      controller,
      threadsBox,
      required,
      view: {
        ...view,
        card: {
          ...cardView,
          nativeAuthored: required,
          showThread: view.travel.showThread,
          travel: { ...cardView.travel, ...view.travel },
        },
        placedAt: dependencies.anchorPlacement.placedAt,
        repaintThread: required ? refreshThread : () => registration.update(),
      },
    });
    return registration;
  };

  const accountPending = (receipts) => {
    const left = ledger.present(receipts);
    if (left) paintKeys();
    releasePendingSafely("receipt presentation");
  };

  stateApplication = createStateApplication({
    prepareActivation: dependencies.state.prepareActivation,
    acceptData: dependencies.state.acceptData,
    notifyDataSubscribers: dependencies.state.notifyDataSubscribers,
    isSignoffDeclared: dependencies.state.isSignoffDeclared,
    renderStatus: dependencies.state.renderStatus,
    renderVersions: dependencies.state.renderVersions,
    stateSignoff: dependencies.state.stateSignoff,
    renderOthers: dependencies.state.renderOthers,
    accountPending,
    paintKeys,
  });

  const flushQueuedInvalidation = () => {
    if (!queuedInvalidation || stateApplying()) return Promise.resolve();
    queuedInvalidation = false;
    return invalidateDom();
  };
  const receiveState = (state) =>
    stateApplication
      .receiveState(state)
      // External wakes read the latest semantic root, including local gestures made
      // while an accepted reading was still preparing its views.
      .finally(() => flushQueuedInvalidation().catch(() => undefined));

  delivery = createDelivery({
    ledger,
    currentReceipts,
    applyAcceptedState: receiveState,
    settleRejected: () =>
      stateApplication.runSerialized(async () => {
        const prepared = invalidateDom();
        releasePendingSafely("rejected event presentation");
        await prepared;
      }),
    settlementChanged: (entry, accepted) => {
      if (accepted) {
        // A poll can present the attempt before its POST answers. Retry after
        // ledger.accept; release itself waits for every owning presentation region
        // before undo and other semantic readers may observe the entry leave.
        releasePendingSafely("accepted event reconciliation");
        // In that ordering a gesture that is not an action left on accept; the same
        // descriptor invalidation belongs to whichever edge actually retires it.
        if (!applicationState.entry(entry.event.attempt)) invalidateDom();
        return;
      }
      paintKeys();
    },
    reportApplicationError: (error) =>
      console.error("leaf: rejected event reconciliation", error),
  });

  const feed = createStateFeed({
    prepareActivation: dependencies.feed.prepareActivation,
    notifyDataSubscribers: dependencies.feed.notifyDataSubscribers,
    renderStatus: dependencies.feed.renderStatus,
    projectionDeferred,
    retryProjection,
    stateApplying,
    releasePending,
    invalidateDom,
    receiveState,
  });

  const threadBox = (owner, hint) =>
    buildThreadBox(owner, hint, {
      createComment,
      onDraftChanged: invalidateDom,
      wireInput: dependencies.wireInput,
    });
  const threadSurfaceCommands = {
    invalidate: invalidateDom,
    composition: dependencies.compositionSurface,
    reveal: dependencies.showThread,
  };
  const consumeThreads = (owner, render) =>
    registerConsumer(owner, render, threadSurfaceCommands);
  const consumePageThreads = (owner, render) =>
    registerPageConsumer(owner, render, threadSurfaceCommands);
  const mountThreadViews = (owner, render) =>
    registerMirrorConsumer(owner, render, { commands: inlineView });

  application = {
    ...projectionCommands,
    ...projectionUpdates,
    ...engagement,
    approvalBlockingAsks,
    beginRead: beginStateRead,
    threadBox,
    createComment,
    createPageComment: createComment,
    dispatchWidget,
    hasPending,
    invalidateDom,
    landInThread: dependencies.landInThread,
    annotations,
    refreshAnnotationInventory,
    renderAnnotations,
    mountAnnotations,
    margin,
    threadDestinations,
    read,
    mountThread: threadPresenter.mount,
    mountRead: read.mount,
    navigateToDatum: dependencies.anchorTravel.navigateToDatum,
    openAsks,
    unansweredAsks,
    pendingApprovals,
    acceptedApprovals,
    post,
    projectData: dataProjection.projectData,
    readAndApply: feed.readAndApply,
    receiveState,
    refreshThread,
    presentThread,
    consumeThreads,
    consumePageThreads,
    mountThreadViews,
    registerThreadPanel,
    forgetAuthoredOwners: projection.forgetAuthoredOwners,
    retireProjectionCoverage: projection.retireProjectionCoverage,
    threadActions,
    shallowSigs: projectionShallowSigs,
    startFeed: feed.startFeed,
    watchAsks,
    wireInput: dependencies.wireInput,
  };
  return application;
}

export const approvalBlockingAsks = (...args) => app().approvalBlockingAsks(...args);
export const beginRead = (...args) => app().beginRead(...args);
export const threadBox = (...args) => app().threadBox(...args);
export const createComment = (...args) => app().createComment(...args);
export const dispatchWidget = (...args) => app().dispatchWidget(...args);
export const hasPending = (...args) => app().hasPending(...args);
export const invalidateDom = (...args) => app().invalidateDom(...args);
export const landInThread = (...args) => app().landInThread(...args);
export const midComposition = (...args) => app().midComposition(...args);
export const navigateToDatum = (...args) => app().navigateToDatum(...args);
export const openAsks = (...args) => app().openAsks(...args);
// The one route to a thread by its root id: the thread's inline destination while
// it has one, Threads otherwise, the same choice a mark and t/T make.
export const openThread = (...args) => app().threadDestinations.openPageThread(...args);
export const unansweredAsks = (...args) => app().unansweredAsks(...args);
export const pendingApprovals = (...args) => app().pendingApprovals(...args);
export const acceptedApprovals = (...args) => app().acceptedApprovals(...args);
export const post = (...args) => app().post(...args);
export const projectData = (...args) => app().projectData(...args);
export const readAndApply = (...args) => app().readAndApply(...args);
export const receiveState = (...args) => app().receiveState(...args);
export const refreshThread = (...args) => app().refreshThread(...args);
export const consumeThreads = (...args) => app().consumeThreads(...args);
export const consumePageThreads = (...args) => app().consumePageThreads(...args);
export const mountThreadViews = (...args) => app().mountThreadViews(...args);
export const registerThreadPanel = (...args) => app().registerThreadPanel(...args);
export const threadActions = Object.freeze({
  reply: (...args) => app().threadActions.reply(...args),
  resolve: (...args) => app().threadActions.resolve(...args),
  reopen: (...args) => app().threadActions.reopen(...args),
  toggleReaction: (...args) => app().threadActions.toggleReaction(...args),
});
export const shallowSigs = (...args) => app().shallowSigs(...args);
export const startFeed = (...args) => app().startFeed(...args);
export const unaccountedGesture = (...args) => app().unaccountedGesture(...args);
export const undoable = (...args) => app().undoable(...args);
export const undoLast = (...args) => app().undoLast(...args);
export const watchAsks = (...args) => app().watchAsks(...args);
export const watchUpdates = (...args) => app().watchUpdates(...args);
export const wireInput = (...args) => app().wireInput(...args);
