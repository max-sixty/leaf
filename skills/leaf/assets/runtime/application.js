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
import { createDelivery } from "./delivery.js";
import {
  createProjectionPresentation,
  shallowSigs as projectionShallowSigs,
} from "./projection/presentation.js";
import { projectionDeferred } from "./projection/state.js";
import { createProjectionCommands } from "./projection/commands.js";
import { createDataProjection } from "./projection/data.js";
import { createConversationPresentation } from "./conversation/presentation.js";
import { renderMarginThread } from "./conversation/inline.js";
import { conversationBox as buildConversationBox } from "./conversation/box.js";
import {
  focusSurface,
  registerThreadSurface as registerSurface,
  renderSurfaces,
} from "./conversation/surfaces.js";
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
  const ledger = createPendingLedger({ newAttempt, now: saidNow });
  const hasPending = ledger.hasUnresolved;
  const engagement = dependencies.createEngagement({
    hasPending,
    fabAnchorAt: dependencies.activeActionAnchor,
    targetChooserOpen: dependencies.targetChooserOpen,
    pageComposerDrawing: dependencies.pageComposerDrawing,
  });
  let conversation;
  let stateApplication;
  let queuedInvalidation = false;

  const stateApplying = () => stateApplication?.isApplying() ?? false;

  const pendingEntries = ledger.snapshot;
  const currentReceipts = () => readApplication().authoritative?.browser.receipts ?? [];
  const pendingApprovals = () => readApplication().effective.pendingApprovals;
  const pendingRequests = () => readApplication().effective.pendingRequests;
  const openAsks = () => readOpenAsks(pendingRequests());
  const unansweredAsks = () => readUnansweredAsks(pendingRequests());
  const approvalBlockingAsks = () => readApprovalBlockingAsks(pendingRequests());
  const watchAsks = (owner, callback) => observeAsks(owner, pendingRequests, callback);

  const releasableActions = () =>
    ledger
      .snapshot()
      .filter(
        (entry) =>
          entry.answered &&
          entry.event.kind === "action" &&
          (entry.rejected || (entry.presented && entry.readEvent)),
      );

  const releasePending = async () => {
    const candidates = releasableActions();
    if (!candidates.length) return false;
    const attempts = new Set(candidates.map((entry) => entry.event.attempt));
    const stillCurrent = () =>
      releasableActions().some((entry) => attempts.has(entry.event.attempt));
    await Promise.all([
      whenWidgetsPresented([...new Set(candidates.map((entry) => entry.event.widget))]),
      whenApplicationRegionsPresented(
        ["projection:chrome", "conversation", "asks"],
        stillCurrent,
      ),
    ]);
    // Waiting can cross a newer publication. Retire only the candidates selected
    // before the wait and only if their semantic settlement still permits release.
    const released = releasableActions().filter((entry) =>
      attempts.has(entry.event.attempt),
    );
    // Widget updates and the conversation, projection, and Ask owners have now committed
    // this surviving semantic reading. Paint its command surface while the same pending
    // records still stand; removing an accounted record is then a semantic no-op.
    if (released.length) paintKeys();
    for (const entry of released) ledger.remove(entry);
    return released.length > 0;
  };

  const releasePendingSafely = (context) => {
    void releasePending().catch((error) => console.error(`leaf: ${context}`, error));
  };

  let invalidating = false;
  const invalidateDom = () => {
    if (stateApplying()) {
      queuedInvalidation = true;
      return undefined;
    }
    if (invalidating) return undefined;
    invalidating = true;
    try {
      projection.present(readApplication());
      return backgroundConversation(
        conversation.apply(readApplication()),
        "conversation preparation",
      );
    } finally {
      invalidating = false;
    }
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
  const backgroundConversation = (prepared, context) => {
    if (!prepared?.catch) return prepared;
    return prepared.catch((error) => {
      console.error(`leaf: ${context}`, error);
    });
  };
  const presentConversation = () => conversation.apply(readApplication());
  const refreshConversation = () =>
    backgroundConversation(presentConversation(), "conversation preparation");

  function startPost(event) {
    const entry = ledger.enqueue(event);
    if (!entry) {
      notice(`Couldn't send — attempt ${event.attempt} is already in use`);
      return null;
    }
    let presentationError = null;
    let conversationPresentation = Promise.resolve();
    try {
      pendingTraffic(readApplication().effective.delivery);
      projection.stageOptimistic(entry);
      // Desired state changes at enqueue even where the widget has already painted the
      // same value. Conversation gestures are folded in this call stack before transport.
      projection.present(readApplication());
      conversationPresentation = backgroundConversation(
        conversation.apply(readApplication()),
        "optimistic conversation preparation",
      );
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
      presentation: conversationPresentation,
    });
  }

  const post = (event) => startPost(event)?.answer ?? Promise.resolve(null);

  function dispatchWidget(descriptor, command) {
    const reading = applicationState.selectWidget(descriptor).read();
    if (command.kind === "undo") {
      const candidate = Object.values(reading.actions)
        .flatMap(({ undo }) => undo)
        .find(
          (event) => event.attempt === command.target || event.id === command.target,
        );
      if (!candidate) return null;
      // A receipt proves acceptance, but the action remains in the ledger until its
      // authoritative projection has presented. Do not let an older durable action
      // leapfrog that proof: the incomplete reading may still change which commands
      // the page can honestly offer. The exact action still may withdraw itself,
      // including before its own forward POST settles, because the ordered ledger owns
      // both attempts together.
      const acceptedPresentationPending = readApplication().unresolved.some(
        (entry) =>
          entry.event.kind === "action" &&
          entry.answered &&
          entry.readEvent &&
          entry.readEvent.id !== candidate.id &&
          !entry.presented,
      );
      if (acceptedPresentationPending) return null;
      runtime.undoing = true;
      paintKeys();
      const started = startPost({ kind: "undo", undoes: candidate.id });
      if (!started) {
        runtime.undoing = false;
        paintKeys();
        return null;
      }
      return started.answer
        .then((accepted) => {
          if (accepted) notice("Took back your last change — sent");
          return accepted;
        })
        .finally(() => {
          runtime.undoing = false;
          paintKeys();
        });
    }
    const entry =
      command.kind === "action"
        ? reading.actions[command.verb]
        : command.kind === "request"
          ? reading.requests[command.verb]
          : null;
    if (!entry?.available) return null;
    return (
      startPost({
        kind: command.kind,
        revision: runtime.currentRevision,
        widget: descriptor.id,
        action: command.verb,
        detail: structuredClone(command.detail ?? {}),
        ...(command.references && {
          references: structuredClone(command.references),
        }),
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

  const replyView = {
    createReply,
    revealReplyEditor: dependencies.revealReplyEditor,
    wireInput: dependencies.wireInput,
  };
  const settlementView = { pendingEntries: ledger.snapshot, setResolved };
  const reactionView = {
    buildSurface: dependencies.buildReactSurface,
    closeReactionMode: dependencies.closeReactionMode,
    currentRevision: () => runtime.currentRevision,
    sendReaction: (event, chip, where) =>
      dependencies.sendReaction(event, chip, where, post),
    withdraw: projectionCommands.withdraw,
  };
  const inlineView = {
    reply: replyView,
    settlement: settlementView,
    reaction: reactionView,
    showThread: dependencies.showThread,
    landInConversation: dependencies.landInConversation,
  };
  const cardView = {
    reply: replyView,
    settlement: settlementView,
    reaction: reactionView,
    anchors: {
      isMarked: dependencies.anchorPaint.isMarked,
      placedAt: dependencies.anchorPaint.placedAt,
    },
    travel: {
      focusSurface,
      panelCovers: dependencies.panelCovers,
      setPanel: dependencies.setPanel,
      scrollToThread: dependencies.anchorTravel.scrollToThread,
      retainPanelLanding: dependencies.retainPanelLanding,
      retainNarrowing: dependencies.retainThreadNarrowing,
      showThread: dependencies.showThread,
    },
  };
  const listView = {
    card: cardView,
    closeReactionMode: reactionView.closeReactionMode,
    isMarked: dependencies.anchorPaint.isMarked,
    placedAt: dependencies.anchorPaint.placedAt,
    panelIsOpen: dependencies.panelIsOpen,
    scrollToElement: dependencies.anchorTravel.scrollToElement,
    setThreadCount: dependencies.setThreadCount,
    onListChanged: dependencies.onConversationChanged,
    refreshAnchorHover: dependencies.anchorPaint.refreshHover,
    repaintConversation: refreshConversation,
  };
  const surfaceView = {
    ...inlineView,
    composition: dependencies.compositionSurface,
  };

  const margin = dependencies.createMarginProjection({
    panelIsOpen: dependencies.panelIsOpen,
    bottomChromeBoxes: dependencies.margin.bottomChromeBoxes,
    designModeActive: dependencies.margin.designModeActive,
    comparisonBase: dependencies.margin.comparisonBase,
    comparisonChanges: dependencies.margin.comparisonChanges,
    inlineComparison: dependencies.margin.inlineComparison,
    toggleInlineComparison: dependencies.margin.toggleInlineComparison,
    leavePageMap: dependencies.margin.leavePageMap,
    openPageMap: dependencies.margin.openPageMap,
    pageMapDialogContains: dependencies.margin.pageMapDialogContains,
    renderPageMapDialog: dependencies.margin.renderPageMapDialog,
    openAsks,
    standsWith: dependencies.margin.standsWith,
    revealConversation: dependencies.margin.revealConversation,
    goToAsk: dependencies.margin.goToAsk,
    renderMarginThread: (host, thread) => renderMarginThread(host, thread, inlineView),
    placedAt: dependencies.anchorPaint.placedAt,
    showThread: dependencies.showThread,
    scrollToElement: dependencies.anchorTravel.scrollToElement,
    scrollToThread: dependencies.anchorTravel.scrollToThread,
    landInConversation: dependencies.landInConversation,
  });

  conversation = createConversationPresentation({
    available: dependencies.conversationAvailable ?? true,
    panelIsOpen: dependencies.panelIsOpen,
    setThreadCount: dependencies.setThreadCount,
    onConversationChanged: dependencies.onConversationChanged,
    listView,
    inlineView,
    surfaceView,
    anchorPaint: dependencies.anchorPaint,
    anchorControls: dependencies.anchorControls,
    drawingPaint: dependencies.drawingPaint,
    pageGeometry: dependencies.pageGeometry,
    readDraft: dependencies.readConversationDraft,
    activeActionAnchor: dependencies.activeActionAnchor,
    renderMargin: margin.renderMargin,
    renderSurfaces,
  });

  const applyConversation = () => conversation.apply(readApplication());
  const prepareProjection = () => projection.prepare(readApplication());
  const presentProjection = (prepared) =>
    projection.present(readApplication(), prepared);
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
    paintApproval: dependencies.state.paintApproval,
    renderStatus: dependencies.state.renderStatus,
    renderVersions: dependencies.state.renderVersions,
    stateSignoff: dependencies.state.stateSignoff,
    renderOthers: dependencies.state.renderOthers,
    applyConversation,
    renderAsks: dependencies.renderAsks,
    prepareProjection,
    presentProjection,
    accountPending,
    panelIsOpen: dependencies.panelIsOpen,
    paintKeys,
  });

  const flushQueuedInvalidation = async () => {
    if (!queuedInvalidation || stateApplying()) return;
    queuedInvalidation = false;
    if (retryProjection()) {
      releasePendingSafely("queued pending release");
      return;
    }
    await invalidateDom();
  };
  const receiveState = (state) =>
    stateApplication.receiveState(state).finally(async () => {
      // External wakes read the latest semantic root, including local gestures made
      // while an accepted reading was still preparing its views.
      try {
        await flushQueuedInvalidation();
      } catch (error) {
        // A retry's presentation failure does not change the accepted reading.
        console.error("leaf: queued projection retry", error);
      }
    });

  delivery = createDelivery({
    ledger,
    currentReceipts,
    applyAcceptedState: receiveState,
    settleRejected: () =>
      stateApplication.runSerialized(async () => {
        projection.present(readApplication());
        const prepared = conversation.apply(readApplication());
        releasePendingSafely("rejected event presentation");
        await prepared;
      }),
    settlementChanged: (_entry, accepted) => {
      if (accepted) {
        // A poll can account for the attempt before delivery marks its entry answered.
        // Retry after ledger.accept; release itself waits for every owning presentation
        // region before undo and other semantic readers may observe the entry leave.
        releasePendingSafely("accepted event reconciliation");
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
    renderConversation: applyConversation,
    presentProjection,
    receiveState,
  });

  const conversationBox = (owner, hint) =>
    buildConversationBox(owner, hint, {
      createComment,
      onDraftChanged: invalidateDom,
      wireInput: dependencies.wireInput,
    });
  const registerThreadSurface = (owner, adapter) =>
    registerSurface(owner, adapter, {
      invalidate: invalidateDom,
      closeReactionMode: dependencies.closeReactionMode,
      composition: dependencies.compositionSurface,
    });

  application = {
    ...projectionCommands,
    ...projectionUpdates,
    ...engagement,
    approvalBlockingAsks,
    beginRead: beginStateRead,
    conversationBox,
    createComment,
    createPageComment: createComment,
    createReply,
    dispatchWidget,
    hasPending,
    invalidateDom,
    landInConversation: dependencies.landInConversation,
    margin,
    mountConversation: conversation.mount,
    navigateToDatum: dependencies.anchorTravel.navigateToDatum,
    openAsks,
    unansweredAsks,
    paintAcknowledgments: conversation.paintAcknowledgments,
    pendingApprovals,
    pendingRequests,
    post,
    projectData: dataProjection.projectData,
    readAndApply: feed.readAndApply,
    receiveState,
    refreshConversation,
    presentConversation,
    refreshNarrowing: conversation.refreshNarrowing,
    registerThreadSurface,
    resetAuthoredPage: projection.resetAuthoredPage,
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
export const conversationBox = (...args) => app().conversationBox(...args);
export const createComment = (...args) => app().createComment(...args);
export const createReply = (...args) => app().createReply(...args);
export const dispatchWidget = (...args) => app().dispatchWidget(...args);
export const hasPending = (...args) => app().hasPending(...args);
export const invalidateDom = (...args) => app().invalidateDom(...args);
export const landInConversation = (...args) => app().landInConversation(...args);
export const midComposition = (...args) => app().midComposition(...args);
export const navigateToDatum = (...args) => app().navigateToDatum(...args);
export const openAsks = (...args) => app().openAsks(...args);
export const unansweredAsks = (...args) => app().unansweredAsks(...args);
export const pendingApprovals = (...args) => app().pendingApprovals(...args);
export const pendingRequests = (...args) => app().pendingRequests(...args);
export const post = (...args) => app().post(...args);
export const projectData = (...args) => app().projectData(...args);
export const readAndApply = (...args) => app().readAndApply(...args);
export const receiveState = (...args) => app().receiveState(...args);
export const refreshConversation = (...args) => app().refreshConversation(...args);
export const registerThreadSurface = (...args) => app().registerThreadSurface(...args);
export const shallowSigs = (...args) => app().shallowSigs(...args);
export const startFeed = (...args) => app().startFeed(...args);
export const unaccountedGesture = (...args) => app().unaccountedGesture(...args);
export const undoable = (...args) => app().undoable(...args);
export const undoLast = (...args) => app().undoLast(...args);
export const watchAsks = (...args) => app().watchAsks(...args);
export const watchUpdates = (...args) => app().watchUpdates(...args);
export const wireInput = (...args) => app().wireInput(...args);
