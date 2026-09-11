/* Fixed composition root for browser state, optimistic work, and presentation.

   Importing this module is inert. leaf.js supplies the concrete feature views once and
   mounts the application before widget upgrade; exported functions are stable closures
   for the public widget API and fail clearly if invoked before that boundary. */
import { runtime } from "./context.js";
import { newAttempt } from "./drafts.js";
import { saidNow } from "./presence.js";
import { announce, notice } from "./notifications.js";
import {
  openAsks as readOpenAsks,
  unansweredAsks as readUnansweredAsks,
  watchAsks as observeAsks,
} from "./asks/model.js";
import { paintKeys } from "./keyboard/scopes.js";
import { pendingTraffic } from "./traffic.js";
import { createPendingLedger } from "./pending/state.js";
import {
  pendingApprovals as pendingApprovalEvents,
  pendingRequests as pendingRequestEvents,
  unresolvedAttempts,
} from "./pending/model.js";
import { createDelivery } from "./delivery.js";
import {
  createProjectionPresentation,
  shallowSigs as projectionShallowSigs,
  standingState as projectionStandingState,
} from "./projection/presentation.js";
import { currentProjection, projectionDeferred } from "./projection/state.js";
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
import { createRequests } from "./requests.js";
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

  const readings = () => ({
    phase: runtime.statePhase,
    view: runtime.view,
    conversation: runtime.browser?.conversation,
    pendingEntries: ledger.snapshot(),
    receipts: runtime.browser?.receipts ?? [],
  });
  const conversationReadings = () => ({
    phase: runtime.statePhase,
    serverThreads: runtime.browser?.conversation?.threads ?? [],
    receipts: runtime.browser?.receipts ?? [],
    pendingEntries: ledger.snapshot(),
  });
  const pendingEntries = ledger.snapshot;
  const currentReceipts = () => runtime.browser?.receipts ?? [];
  const pendingApprovals = () =>
    pendingApprovalEvents(pendingEntries(), currentReceipts());
  const pendingRequests = () =>
    pendingRequestEvents(pendingEntries(), currentReceipts());
  const openAsks = () => readOpenAsks(pendingRequests());
  const unansweredAsks = () => readUnansweredAsks(pendingRequests());
  const watchAsks = (owner, callback) => observeAsks(owner, pendingRequests, callback);

  const releasePending = () => {
    const released = projection.releasableEntries(ledger.snapshot());
    for (const entry of released) ledger.remove(entry);
    return released.length > 0;
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
      projection.present(readings());
      return backgroundConversation(
        conversation.apply(conversationReadings()),
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
      if (releasePending()) paintKeys();
      document.dispatchEvent(new Event("lf-actions"));
    },
    onDomIntroduced: () => {
      invalidateDom();
      dependencies.pageGeometry.pageShifted();
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
  const refreshConversation = () =>
    backgroundConversation(
      conversation.apply(conversationReadings()),
      "conversation preparation",
    );

  function post(event) {
    const entry = ledger.enqueue(event);
    if (!entry) {
      notice(`Couldn't send — attempt ${event.attempt} is already in use`);
      return Promise.resolve(null);
    }
    let staged = false;
    let presentationError = null;
    try {
      pendingTraffic(unresolvedAttempts(ledger.snapshot()));
      staged = projection.stageOptimistic(entry);
      // Desired state changes at enqueue even where the widget has already painted the
      // same value. Conversation gestures are folded in this call stack before transport.
      projection.present(readings());
      backgroundConversation(
        conversation.apply(conversationReadings()),
        "optimistic conversation preparation",
      );
    } catch (error) {
      presentationError = error;
    } finally {
      try {
        if (staged || event.kind === "done" || event.kind === "request")
          document.dispatchEvent(new Event("lf-actions"));
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
    return entry.answer;
  }

  const projectionCommands = createProjectionCommands({
    post,
    stateApplying,
    unaccountedGesture: engagement.unaccountedGesture,
  });
  const projectionUpdates = createProjectionUpdates({
    projectionCommitted: projection.projectionCommitted,
    coordinateProjectionCommitted: projection.coordinateProjectionCommitted,
  });
  const requests = createRequests({ post, pendingRequests });

  const createComment = (event) =>
    post({ kind: "comment", revision: runtime.currentRevision, ...event });
  const createReply = (event) =>
    post({ kind: "reply", revision: runtime.currentRevision, ...event });
  const setResolved = (parent, resolved) =>
    post({
      kind: resolved ? "resolve" : "unresolve",
      parent,
    });

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

  const applyConversation = () => conversation.apply(conversationReadings());
  const presentProjection = () => projection.present(readings());
  const accountPending = (receipts) => {
    const removed = ledger.account(receipts);
    const released = releasePending();
    if (removed || released) paintKeys();
  };

  stateApplication = createStateApplication({
    prepareActivation: dependencies.state.prepareActivation,
    acceptData: dependencies.state.acceptData,
    notifyDataSubscribers: dependencies.state.notifyDataSubscribers,
    replaceClaimState: dependencies.state.replaceClaimState,
    isSignoffDeclared: dependencies.state.isSignoffDeclared,
    paintApproval: dependencies.state.paintApproval,
    renderStatus: dependencies.state.renderStatus,
    renderVersions: dependencies.state.renderVersions,
    stateSignoff: dependencies.state.stateSignoff,
    renderOthers: dependencies.state.renderOthers,
    applyConversation,
    presentProjection,
    accountPending,
    panelIsOpen: dependencies.panelIsOpen,
    refreshHover: dependencies.anchorPaint.refreshHover,
    repaint: dependencies.onConversationChanged,
    paintKeys,
    retainConversationFocus: dependencies.retainConversationFocus,
    updateFab: dependencies.updateFab,
  });

  const flushQueuedInvalidation = async () => {
    if (!queuedInvalidation || stateApplying()) return;
    queuedInvalidation = false;
    if (retryProjection()) {
      if (releasePending()) paintKeys();
      document.dispatchEvent(new Event("lf-actions"));
      return;
    }
    await invalidateDom();
  };
  const receiveState = (state) =>
    stateApplication.receiveState(state).finally(async () => {
      // External wakes that arrived while the candidate was fallible now read either
      // the adopted state or the complete snapshot rollback restored.
      try {
        await flushQueuedInvalidation();
      } catch (error) {
        // This retry happens after the state transaction has committed or rolled back.
        // Its presentation failure must not replace that canonical transaction result.
        console.error("leaf: queued projection retry", error);
      }
    });

  delivery = createDelivery({
    ledger,
    currentReceipts: () => runtime.browser?.receipts ?? [],
    applyAcceptedState: receiveState,
    settleRejected: () =>
      stateApplication.runSerialized(async () => {
        projection.present(readings());
        const prepared = conversation.apply(conversationReadings());
        releasePending();
        await prepared;
      }),
    settlementChanged: (_entry, accepted) => {
      if (accepted) {
        // A poll can account for the attempt before delivery marks its entry answered.
        // Retry release after that candidate has committed and ledger.accept has run;
        // this is the point undo and other semantic readers may observe the entry leave.
        void stateApplication
          .runSerialized(() => {
            if (!releasePending()) return;
            paintKeys();
            document.dispatchEvent(new Event("lf-actions"));
          })
          .catch((error) =>
            console.error("leaf: accepted event reconciliation", error),
          );
        return;
      }
      paintKeys();
      // An accepted response's state application owns the semantic repaint once its
      // awaited presentation commits. A definitive refusal has no state application,
      // so its completed local reconciliation emits the change here.
      document.dispatchEvent(new Event("lf-actions"));
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
    panelIsOpen: dependencies.panelIsOpen,
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
    ...requests,
    ...engagement,
    beginRead: beginStateRead,
    conversationBox,
    createComment,
    createPageComment: createComment,
    createReply,
    currentProjection,
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
    refreshNarrowing: conversation.refreshNarrowing,
    registerThreadSurface,
    requestAvailable: requests.requestAvailable,
    resetAuthoredPage: projection.resetAuthoredPage,
    setResolved,
    shallowSigs: projectionShallowSigs,
    standingState: projectionStandingState,
    startFeed: feed.startFeed,
    watchRequestLifecycle: requests.watchRequestLifecycle,
    watchAsks,
    wireInput: dependencies.wireInput,
  };
  return application;
}

export const actionAvailable = (...args) => app().actionAvailable(...args);
export const actionSequence = (...args) => app().actionSequence(...args);
export const actionStands = (...args) => app().actionStands(...args);
export const beginRead = (...args) => app().beginRead(...args);
export const conversationBox = (...args) => app().conversationBox(...args);
export const createComment = (...args) => app().createComment(...args);
export const createReply = (...args) => app().createReply(...args);
export const currentProjectionReading = (...args) => app().currentProjection(...args);
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
export const requestAvailable = (...args) => app().requestAvailable(...args);
export const sendAction = (...args) => app().sendAction(...args);
export const sendRequest = (...args) => app().sendRequest(...args);
export const shallowSigs = (...args) => app().shallowSigs(...args);
export const startFeed = (...args) => app().startFeed(...args);
export const standingState = (...args) => app().standingState(...args);
export const unaccountedGesture = (...args) => app().unaccountedGesture(...args);
export const undoable = (...args) => app().undoable(...args);
export const undoableAction = (...args) => app().undoableAction(...args);
export const undoLast = (...args) => app().undoLast(...args);
export const withdraw = (...args) => app().withdraw(...args);
export const watchActions = (...args) => app().watchActions(...args);
export const watchAsks = (...args) => app().watchAsks(...args);
export const watchRequestLifecycle = (...args) => app().watchRequestLifecycle(...args);
export const watchUpdates = (...args) => app().watchUpdates(...args);
export const wireInput = (...args) => app().wireInput(...args);
