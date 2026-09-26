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
import { createReadTracking } from "./thread/read.js";
import { renderMarginThread } from "./thread/inline.js";
import { threadBox as buildThreadBox } from "./thread/box.js";
import { messageText } from "./thread/messages.js";
import { isThreadEvent } from "./pending/model.js";
import {
  focusSurface,
  consumeThreads as registerConsumer,
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
    targetChooserOpen: dependencies.targetChooserOpen,
    pageComposerDrawing: dependencies.pageComposerDrawing,
  });
  let threadPresenter;
  let stateApplication;
  let queuedInvalidation = false;

  const stateApplying = () => stateApplication?.isApplying() ?? false;

  const currentReceipts = () => readApplication().authoritative?.browser.receipts ?? [];
  const pendingApprovals = () => readApplication().effective.pendingApprovals;
  const acceptedApprovals = () => readApplication().effective.thread.collection.done;
  const pendingRequests = () => readApplication().effective.pendingRequests;
  const openAsks = readOpenAsks;
  const unansweredAsks = readUnansweredAsks;
  const approvalBlockingAsks = readApprovalBlockingAsks;
  const watchAsks = observeAsks;

  const releasableEntries = () =>
    ledger
      .snapshot()
      .filter(
        (entry) =>
          entry.answered &&
          (entry.rejected ||
            (entry.event.kind === "action" && entry.presented && entry.readEvent)),
      );

  const releasePending = async () => {
    const candidates = releasableEntries();
    if (!candidates.length) return false;
    const attempts = new Set(candidates.map((entry) => entry.event.attempt));
    const stillCurrent = () =>
      releasableEntries().some((entry) => attempts.has(entry.event.attempt));
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
    const released = releasableEntries().filter((entry) =>
      attempts.has(entry.event.attempt),
    );
    // Widget updates and the thread, projection, and Ask owners have now committed
    // this surviving semantic reading. Paint its command surface while the same pending
    // records still stand; removing an accounted record is then a semantic no-op.
    if (released.length) paintKeys();
    for (const entry of released) ledger.remove(entry);
    return released.length > 0;
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
      pendingTraffic(readApplication().effective.delivery);
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
    const entry =
      command.kind === "action"
        ? reading.actions[command.verb]
        : command.kind === "request"
          ? reading.requests[command.verb]
          : null;
    if (!entry?.available) return null;
    const request = descriptor.declaration["x-request"];
    let sourceRevision = null;
    if (command.kind === "request" && request?.records) {
      const field = request.verbs?.[command.verb]?.unit;
      const unit = command.detail?.[field];
      const seat = reading.requestUnits?.[unit];
      if (
        typeof unit !== "string" ||
        !unit ||
        seat?.phase !== "ready" ||
        seat.seat.offered === false
      )
        return null;
      sourceRevision = seat.seat.source_revision;
    }
    return (
      startPost({
        kind: command.kind,
        revision: runtime.currentRevision,
        widget: descriptor.id,
        action: command.verb,
        detail: structuredClone(command.detail ?? {}),
        ...(sourceRevision != null && { source_revision: sourceRevision }),
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
  const createReply = (event) =>
    post({ kind: "reply", revision: runtime.currentRevision, ...event });
  const setResolved = (parent, resolved) =>
    startPost({
      kind: resolved ? "resolve" : "unresolve",
      parent,
    }) ?? { answer: Promise.resolve(null), presentation: Promise.resolve() };
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
  });

  const replyView = {
    createReply,
    revealReplyEditor: dependencies.revealReplyEditor,
    wireInput: dependencies.wireInput,
  };
  const settlementView = { pendingEntries: ledger.snapshot, setResolved };
  const reactionView = {
    registerSurface: dependencies.registerReactSurface,
    currentRevision: () => runtime.currentRevision,
    sendReaction: (event, chip, where) =>
      dependencies.sendReaction(event, chip, where, post),
    withdraw: projectionCommands.withdraw,
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
      isMarked: dependencies.anchorPaint.isMarked,
      placedAt: dependencies.anchorPaint.placedAt,
    },
    travel: {
      focusSurface,
      scrollToThread: dependencies.anchorTravel.scrollToThread,
      retainPanelLanding: dependencies.retainPanelLanding,
      retainNarrowing: dependencies.retainThreadNarrowing,
      showThread: dependencies.showThread,
    },
  };
  const listView = {
    card: cardView,
    isMarked: dependencies.anchorPaint.isMarked,
    placedAt: dependencies.anchorPaint.placedAt,
    panelIsOpen: dependencies.panelIsOpen,
    scrollToElement: dependencies.anchorTravel.scrollToElement,
    setThreadCounts: dependencies.setThreadCounts,
    onListChanged: dependencies.onThreadChanged,
    refreshAnchorHover: dependencies.anchorPaint.refreshHover,
    repaintThread: refreshThread,
  };
  const surfaceView = {
    ...inlineView,
    composition: dependencies.compositionSurface,
  };

  const margin = dependencies.createMarginProjection({
    panelIsOpen: dependencies.panelIsOpen,
    bottomChromeBoxes: dependencies.margin.bottomChromeBoxes,
    designModeActive: dependencies.margin.designModeActive,
    pointerModeActive: dependencies.margin.pointerModeActive,
    comparisonBase: dependencies.margin.comparisonBase,
    comparisonChanges: dependencies.margin.comparisonChanges,
    inlineComparison: dependencies.margin.inlineComparison,
    toggleInlineComparison: dependencies.margin.toggleInlineComparison,
    leavePageMap: dependencies.margin.leavePageMap,
    openPageMap: dependencies.margin.openPageMap,
    pageMapDialogContains: dependencies.margin.pageMapDialogContains,
    renderPageMapDialog: dependencies.margin.renderPageMapDialog,
    openAsks,
    scrollThreadIntoView: dependencies.margin.scrollThreadIntoView,
    goToAsk: dependencies.margin.goToAsk,
    renderMarginThread: (host, thread, controls) =>
      renderMarginThread(host, thread, inlineView, controls),
    placedAt: dependencies.anchorPaint.placedAt,
    showThread: dependencies.showThread,
    scrollToElement: dependencies.anchorTravel.scrollToElement,
    scrollToThread: dependencies.anchorTravel.scrollToThread,
  });

  threadPresenter = createThreadPresentation({
    available: dependencies.threadAvailable ?? true,
    listView,
    inlineView,
    surfaceView,
    anchorPaint: dependencies.anchorPaint,
    anchorControls: dependencies.anchorControls,
    drawingPaint: dependencies.drawingPaint,
    pageGeometry: dependencies.pageGeometry,
    readDraft: dependencies.readThreadDraft,
    activeActionAnchor: dependencies.activeActionAnchor,
    renderMargin: margin.renderMargin,
    renderSurfaces,
    read,
  });

  const accountPending = (receipts) => {
    const removed = ledger.account(receipts);
    if (removed) paintKeys();
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
        // A poll can account for the attempt before delivery marks its entry answered.
        // Retry after ledger.accept; release itself waits for every owning presentation
        // region before undo and other semantic readers may observe the entry leave.
        releasePendingSafely("accepted event reconciliation");
        // Poll presentation can account for the attempt before this POST answers.
        // In that ordering accept() removes it; the same descriptor invalidation
        // belongs to whichever accounting edge actually retires the ledger record.
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
  const consumeThreads = (owner, render) =>
    registerConsumer(owner, render, {
      invalidate: invalidateDom,
      composition: dependencies.compositionSurface,
      reveal: dependencies.showThread,
    });

  application = {
    ...projectionCommands,
    ...projectionUpdates,
    ...engagement,
    approvalBlockingAsks,
    beginRead: beginStateRead,
    threadBox,
    createComment,
    createPageComment: createComment,
    createReply,
    dispatchWidget,
    hasPending,
    invalidateDom,
    landInThread: dependencies.landInThread,
    margin,
    read,
    mountThread: threadPresenter.mount,
    mountRead: read.mount,
    navigateToDatum: dependencies.anchorTravel.navigateToDatum,
    openAsks,
    unansweredAsks,
    pendingApprovals,
    acceptedApprovals,
    pendingRequests,
    post,
    projectData: dataProjection.projectData,
    readAndApply: feed.readAndApply,
    receiveState,
    refreshThread,
    presentThread,
    consumeThreads,
    forgetAuthoredOwners: projection.forgetAuthoredOwners,
    retireProjectionCoverage: projection.retireProjectionCoverage,
    setResolved,
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
export const createReply = (...args) => app().createReply(...args);
export const dispatchWidget = (...args) => app().dispatchWidget(...args);
export const hasPending = (...args) => app().hasPending(...args);
export const invalidateDom = (...args) => app().invalidateDom(...args);
export const landInThread = (...args) => app().landInThread(...args);
export const midComposition = (...args) => app().midComposition(...args);
export const navigateToDatum = (...args) => app().navigateToDatum(...args);
export const openAsks = (...args) => app().openAsks(...args);
// The one route to a thread by its root id: the thread's inline destination while
// it has one, Threads otherwise, the same choice a mark and t/T make.
export const openThread = (...args) => app().margin.openPageThread(...args);
export const unansweredAsks = (...args) => app().unansweredAsks(...args);
export const pendingApprovals = (...args) => app().pendingApprovals(...args);
export const acceptedApprovals = (...args) => app().acceptedApprovals(...args);
export const pendingRequests = (...args) => app().pendingRequests(...args);
export const post = (...args) => app().post(...args);
export const projectData = (...args) => app().projectData(...args);
export const readAndApply = (...args) => app().readAndApply(...args);
export const receiveState = (...args) => app().receiveState(...args);
export const refreshThread = (...args) => app().refreshThread(...args);
export const consumeThreads = (...args) => app().consumeThreads(...args);
export const shallowSigs = (...args) => app().shallowSigs(...args);
export const startFeed = (...args) => app().startFeed(...args);
export const unaccountedGesture = (...args) => app().unaccountedGesture(...args);
export const undoable = (...args) => app().undoable(...args);
export const undoLast = (...args) => app().undoLast(...args);
export const watchAsks = (...args) => app().watchAsks(...args);
export const watchUpdates = (...args) => app().watchUpdates(...args);
export const wireInput = (...args) => app().wireInput(...args);
