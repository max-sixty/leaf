/* Fixed composition root for browser state, optimistic work, and presentation.

   Importing this module is inert. leaf.js supplies the concrete feature views once and
   mounts the application before widget upgrade; exported functions are stable closures
   for the public widget API and fail clearly if invoked before that boundary. */
import { annotationMode, runtime } from "./context.js";
import {
  applicationState,
  setPresentationFailureReporter,
  whenApplicationRegionsPresented,
  whenWidgetsPresented,
  presentDocument,
  projectionRegionsPresented,
  readPart,
} from "./semantic-state.js";
import { announce, notice } from "./notifications.js";
import { readAsks } from "./asks/model.js";
import { watchPendingTraffic } from "./traffic.js";
import { createCommandDispatch } from "./pending/dispatch.js";
import { createDelivery, deliverBookkeeping } from "./delivery.js";
import { keepRefusedWords } from "./drafts.js";
import { createProjectionPresentation } from "./projection/presentation.js";
import { createUndo } from "./undo.js";
import { createDataProjection } from "./projection/data.js";
import { createThreadPresentation } from "./thread/presentation.js";
import {
  annotationSelection,
  createAnnotationInventory,
} from "./annotation-inventory.js";
import { createAnnotationView } from "./annotation-view.js";
import { createInlineContributions } from "./inline-contributions.js";
import { presentingContributions, watchContributions } from "./contributions.js";
import { watchProjection } from "./projection-watch.js";
import { clocked } from "./presence.js";
import { createThreadDestinations } from "./thread/destination.js";
import { createThreadActions } from "./thread/actions.js";
import { createQueueActions } from "./queue-api.js";
import { registerMirrorConsumer, createPrimaryReader } from "./thread/mirrors.js";
import { createReadTracking } from "./thread/read.js";
import { renderMarginThread } from "./thread/inline.js";
import { showHeld } from "./thread/held-news.js";
import { threadBox as buildThreadBox } from "./thread/box.js";
import { isMessageEvent } from "./pending/model.js";
import {
  placePageThreads as registerPageConsumer,
  renderSurfaces,
  watchThreadSurfaces as watchSurfaces,
} from "./thread/surfaces.js";
import { createStateApplication } from "./state-application.js";
import { createStateFeed } from "./state-feed.js";
import { reportCarried, reportPageError } from "./layer-client.js";

const commandDispatch = createCommandDispatch();
let application = null;
const app = () => {
  if (!application) throw new Error("Leaf application has not been mounted");
  return application;
};

export function mountApplication(dependencies) {
  if (application) throw new Error("Leaf application mounted twice");
  // A renderer's rejection reaches the coordinator after a paint may have reported it.
  setPresentationFailureReporter(reportCarried);
  const { ledger } = commandDispatch;
  watchPendingTraffic(applicationState.select((root) => root.effective.sending));
  const hasPending = () => ledger.snapshot().length > 0;
  const engagement = dependencies.createEngagement({
    hasPending,
    fabAnchorAt: dependencies.activeActionAnchor,
    targetPickerOpen: dependencies.targetPickerOpen,
  });
  let threadPresenter;
  let stateApplication;
  let queuedInvalidation = false;

  const stateApplying = () => stateApplication?.isApplying() ?? false;

  // The destinations are built after the overlay, whose thread preview they take, and
  // the views built below before them hold this forwarder to open a thread.
  const openPageThread = (...args) => threadDestinations.openPageThread(...args);

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
        ["projection:chrome", "thread", "asks", "queue"],
        stillCurrent,
      ),
    ]);
    // Waiting can cross a newer publication. Retire only the candidates selected
    // before the wait and only if their semantic settlement still permits release.
    const released = ledger
      .releasable()
      .filter((entry) => attempts.has(entry.event.attempt));
    // Widget updates and the thread, projection, and ask owners have now committed
    // this surviving semantic reading; removing an accounted record is a semantic no-op,
    // and a key whose liveness read the record hears it leave through its own reading.
    if (!released.length) return false;
    ledger.release(released);
    return true;
  };

  const releasePendingSafely = (context) => {
    void releasePending().catch((error) => reportCarried(error, context));
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

  // The drag that deferred the projection has ended: present the reading it held.
  const projection = createProjectionPresentation({
    onDeferredReady: () => {
      invalidateDom();
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

  /** @param {import("./pending/state.js").DeliveryHandle} entry */
  function afterEnqueue(entry) {
    // Enqueue has already published and claimed its presentation, whose coordinator
    // reports any failed paint. The entry's answer describes the server's durable
    // decision, so a local announcement failure is reported here rather
    // than turning an accepted gesture into an apparent refusal, and it cannot strand
    // the gesture before transport or leave later sends behind an unanswered entry.
    try {
      if (isMessageEvent(entry.event)) announce("Message sent");
      if (entry.event.kind === "edit") announce("Message edited");
    } catch (error) {
      reportPageError(error, "optimistic presentation");
    } finally {
      void delivery.drain();
    }
  }

  commandDispatch.mount({
    afterEnqueue,
    withdraw: (candidate) => undo.withdraw(candidate),
    onCollision: (attempt) =>
      notice(`Couldn't send — attempt ${attempt} is already in use`),
  });

  const { post } = commandDispatch;

  const undo = createUndo({
    post,
    stateApplying,
    unaccountedGesture: engagement.unaccountedGesture,
  });

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
    openThread: openPageThread,
    firstUnreadBtn: dependencies.firstUnreadBtn,
  });

  const threadActions = createThreadActions({
    post,
    withdraw: undo.withdraw,
    sendReaction: dependencies.sendReaction,
    currentRevision: () => runtime.currentRevision,
    open: openPageThread,
  });
  const queueActions = createQueueActions({
    post,
    arrive: (item) => dependencies.arriveAtQueueItem(item),
  });
  const replyView = {
    actions: threadActions,
    wireInput: dependencies.wireInput,
    landSent: dependencies.landSent,
    landInThread: dependencies.landInThread,
    changed: refreshThread,
  };
  const settlementView = {
    pendingEntries: ledger.snapshot,
    actions: threadActions,
    retainReversal: undo.retainReversal,
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
    openThread: openPageThread,
    landInThread: dependencies.landInThread,
  };
  const cardView = {
    reply: replyView,
    settlement: settlementView,
    reaction: reactionView,
    read,
    openThread: inlineView.openThread,
    anchors: {
      placedAt: dependencies.anchorPlacement.placedAt,
    },
    travel: {
      scrollToThread: dependencies.anchorTravel.scrollToThread,
    },
  };
  const surfaceView = {
    ...inlineView,
    composition: dependencies.compositionSurface,
  };

  const annotations = createAnnotationInventory({
    readAsks,
    placedAt: dependencies.anchorPlacement.placedAt,
    openThread: openPageThread,
    goToAsk: dependencies.annotationCommands.goToAsk,
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
    dependencies.annotationCommands.renderPageMapDialog(entries);
    return entries;
  }
  const renderAnnotations = clocked(document.body, () => {
    if (!onPaper.matches) {
      const entries = refreshAnnotationInventory();
      overlay?.paint(entries);
    }
  });
  // The inventory lists the marks the projection's chrome paints, reading their nodes,
  // which the watcher cannot track, so it reads the parts that move them itself, and
  // reads them once that region has committed.
  const annotationInputs = readPart(annotationSelection);
  const mountAnnotations = () => {
    watchProjection(
      document.body,
      () => {
        annotationInputs();
        renderAnnotations();
      },
      () => projectionRegionsPresented([]),
    );
    document.addEventListener("lf-comparison", renderAnnotations);
    onPaper.addEventListener("change", () => {
      if (!onPaper.matches) renderAnnotations.refresh();
    });
    watchContributions(({ immediate }) => {
      renderAnnotations();
      if (immediate) overlay?.flushLayout();
    });
  };
  const overlay = dependencies.createMarginProjection?.({
    inventory: annotations,
    refreshInventory: refreshAnnotationInventory,
    renderAnnotations,
    openPageThread,
    panelIsOpen: dependencies.panelIsOpen,
    panel: dependencies.panel,
    accompaniedThread: dependencies.accompaniedThread,
    accompanyThread: dependencies.accompanyThread,
    designModeActive: dependencies.annotationCommands.designModeActive,
    pointerModeActive: dependencies.annotationCommands.pointerModeActive,
    leavePageMap: dependencies.annotationCommands.leavePageMap,
    openPageMap: dependencies.annotationCommands.openPageMap,
    pageMapDialogContains: dependencies.annotationCommands.pageMapDialogContains,
    scrollThreadIntoView: dependencies.annotationCommands.scrollThreadIntoView,
    renderMarginThread: (host, thread, controls) =>
      renderMarginThread(host, thread, inlineView, controls),
    placedAt: dependencies.anchorPlacement.placedAt,
    scrollToElement: dependencies.anchorTravel.scrollToElement,
  });
  const threadDestinations = createThreadDestinations({
    threadIdsAt: annotations.threadIdsAt,
    placedAt: dependencies.anchorPlacement.placedAt,
    panelIsOpen: dependencies.panelIsOpen,
    showThread: dependencies.showThread,
    scrollToThread: dependencies.anchorTravel.scrollToThread,
    arrive: dependencies.anchorTravel.arrive,
    prepareTrip: dependencies.anchorTravel.prepareTrip,
    preview: overlay?.threadPreview,
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
    // A native Tab visit outside a displaced row retains editing without taking focus.
    continueThread: (id, intent) =>
      threadDestinations.openPageThread(id, {
        part: "reply",
        focus: false,
        travel: false,
        flash: false,
        intent,
      }),
    read,
  });
  const registerThreadPanel = ({ controller, threadsBox, view }) =>
    threadPresenter.registerPanel({
      controller,
      threadsBox,
      view: {
        ...view,
        card: {
          ...cardView,
          nativeAuthored: (message) => !threadPresenter.primaryOwnsMessage(message),
          travel: { ...cardView.travel, ...view.travel },
        },
        placedAt: dependencies.anchorPlacement.placedAt,
        repaintThread: refreshThread,
      },
    });

  const accountPending = (receipts) => {
    ledger.present(receipts);
    releasePendingSafely("receipt presentation");
  };

  stateApplication = createStateApplication({
    prepareActivation: dependencies.state.prepareActivation,
    acceptData: dependencies.state.acceptData,
    notifyDataSubscribers: dependencies.state.notifyDataSubscribers,
    isSignoffDeclared: dependencies.state.isSignoffDeclared,
    stateSignoff: dependencies.state.stateSignoff,
    accountPending,
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
    applyAcceptedState: receiveState,
    refusedWords: keepRefusedWords,
    settleRejected: async (entry, state) => {
      if (state)
        await receiveState(state).catch((error) =>
          reportCarried(error, "state in refused event response"),
        );
      let dependents = [];
      await stateApplication.runSerialized(async () => {
        dependents = ledger.refuse(entry);
        const prepared = invalidateDom();
        releasePendingSafely("rejected event presentation");
        await prepared;
      });
      return dependents;
    },
    settlementChanged: (entry, accepted) => {
      if (accepted) {
        // A poll can present the attempt before its POST answers. Retry after
        // ledger.accept; release itself waits for every owning presentation region
        // before undo and other semantic readers may observe the entry leave.
        releasePendingSafely("accepted event reconciliation");
        // In that ordering a gesture that is not an action left on accept; the
        // descriptor invalidation an entry leaving on presentation gets belongs to
        // whichever edge actually retires it.
        if (!applicationState.entry(entry.event.attempt)) invalidateDom();
      }
    },
  });

  const feed = createStateFeed({
    prepareActivation: dependencies.state.prepareActivation,
    stateApplying,
    invalidateDom,
    receiveState,
  });

  const threadBox = (owner, hint) =>
    buildThreadBox(owner, hint, {
      createComment: (command) => threadActions.create(command)?.delivery ?? null,
      onDraftChanged: invalidateDom,
      wireInput: dependencies.wireInput,
    });
  const threadSurfaceCommands = {
    invalidate: invalidateDom,
    composition: dependencies.compositionSurface,
    reveal: openPageThread,
  };
  // data-annotations=page is the one switch that hands presentation to the page: both
  // page consumers refuse a document that keeps Leaf's own margin.
  const requirePageAnnotations = () => {
    if (annotationMode !== "page")
      throw new Error("Page annotation presentation requires data-annotations=page");
  };
  let annotationRegistration = null;
  const consumeAnnotations = (owner, render) => {
    requirePageAnnotations();
    if (annotationRegistration)
      throw new Error("The document already has a page annotation view");
    const registration = Symbol("page annotation view");
    annotationRegistration = registration;
    const retire = () => {
      if (annotationRegistration === registration) annotationRegistration = null;
    };
    try {
      return createAnnotationView(owner, render, annotations, invalidateDom, retire);
    } catch (error) {
      retire();
      throw error;
    }
  };
  // The widgets declaring x-thread-surface, registered for as long as they stand, once
  // the registry that names them has loaded.
  const watchThreadSurfaces = () => watchSurfaces(threadSurfaceCommands);
  const placePageThreads = (owner, render) => {
    requirePageAnnotations();
    return registerPageConsumer(owner, render, threadSurfaceCommands);
  };
  const mountThreadViews = (owner, render) =>
    registerMirrorConsumer(owner, render, { commands: inlineView });

  // One reader is the page's primary at a time (thread/destination.js). Leaf's own
  // chrome registers one that yields (`registerChromeThreadPresentation`, which the
  // runtime alone is handed): a reader the page's package registers
  // takes the place while it stands, since the author's presentation outranks Leaf's
  // defaults, and the chrome's returns when it leaves. `primary` says which holds it. The
  // chrome's `yielded`, asked before its reader goes, returns how to hand the reader
  // taking its place the conversation it shows, which runs once the package holds its
  // registration, as that reader may ask it to present.
  const attachPresentation = (owner, { render, reveal }) => {
    const reader = createPrimaryReader(owner, render, inlineView, () =>
      threadPresenter.present(),
    );
    const detachDestination = threadDestinations.register(owner, reveal, reader);
    let detachPresentation;
    try {
      detachPresentation = threadPresenter.registerPrimary(reader);
    } catch (error) {
      detachDestination();
      reader.unregister();
      throw error;
    }
    return {
      reader,
      detach() {
        detachDestination();
        detachPresentation();
      },
    };
  };
  let yielding = null;
  let authored = null;
  const restoreYielding = () => {
    if (yielding && !yielding.attached)
      yielding.attached = attachPresentation(yielding.owner, yielding.spec);
  };
  const presentThreads = (owner, spec, yields) => {
    const entry = { owner, spec, attached: null };
    if (yields) {
      if (yielding)
        throw new Error("The page already has a yielding Thread presentation");
      yielding = entry;
      // A package's reader registered first keeps the place.
      if (!authored) entry.attached = attachPresentation(owner, spec);
    } else {
      const displaced = yielding?.attached;
      const handOff = displaced ? yielding.spec.yielded() : null;
      if (displaced) {
        displaced.detach();
        yielding.attached = null;
      }
      try {
        entry.attached = attachPresentation(owner, spec);
      } catch (error) {
        if (displaced) restoreYielding();
        throw error;
      }
      authored = entry;
      if (handOff)
        queueMicrotask(() => {
          if (authored === entry) handOff();
        });
    }
    let active = true;
    return Object.freeze({
      get primary() {
        return Boolean(entry.attached);
      },
      update: ({ release = false } = {}) => {
        if (release) entry.attached?.reader.release();
        return threadPresenter.present();
      },
      unregister() {
        if (!active) return;
        active = false;
        entry.attached?.detach();
        entry.attached = null;
        if (yielding === entry) yielding = null;
        if (authored === entry) {
          authored = null;
          restoreYielding();
        }
      },
    });
  };

  application = {
    withdraw: undo.withdraw,
    midComposition: engagement.midComposition,
    threadBox,
    hasPending,
    invalidateDom,
    landInThread: dependencies.landInThread,
    annotations,
    renderAnnotations,
    mountAnnotations,
    overlay,
    threadDestinations,
    read,
    mountThread: threadPresenter.mount,
    mountRead: read.mount,
    registerThreadPresentation: (owner, spec) => presentThreads(owner, spec, false),
    registerChromeThreadPresentation: (owner, spec) =>
      presentThreads(owner, spec, true),
    navigateToDatum: dependencies.anchorTravel.navigateToDatum,
    post,
    projectData: dataProjection.projectData,
    readAndApply: feed.readAndApply,
    refreshThread,
    presentThread,
    watchThreadSurfaces,
    placePageThreads,
    consumeAnnotations,
    mountThreadViews,
    registerThreadPanel,
    retireProjectionCoverage: projection.retireProjectionCoverage,
    threadActions,
    queueActions,
    openAsk(id) {
      const ask = readAsks().all.find((item) => item.id === id);
      if (!ask) return Promise.resolve(false);
      if (ask.source.kind === "approval")
        return queueActions.open(JSON.stringify(["ask", ask.id]));
      if (ask.source.kind === "reply") {
        showHeld(ask.thread);
        return threadDestinations.openPageThread(ask.message, {
          part: "message",
        });
      }
      return dependencies.annotationCommands.goToAsk(ask, readAsks().all);
    },
    // The On me walk within one region (queue-walk.js), the walk an `lf-tally` steps.
    nextAsk: (options) => dependencies.nextAskWithin(options),
    startFeed: feed.startFeed,
    wireInput: dependencies.wireInput,
  };
  return application;
}

export const threadBox = (...args) => app().threadBox(...args);
export const dispatchWidget = commandDispatch.dispatchWidget;
export const invalidateDom = (...args) => app().invalidateDom(...args);
export const landInThread = (...args) => app().landInThread(...args);
export const navigateToDatum = (...args) => app().navigateToDatum(...args);
// The one route to a thread by its root id: the thread's inline destination while
// it has one, Threads otherwise, the same choice a mark and t/T make.
export const openThread = (...args) => app().threadDestinations.openPageThread(...args);
export const post = commandDispatch.post;
export const projectData = (...args) => app().projectData(...args);
export const placePageThreads = (...args) => app().placePageThreads(...args);
export const consumeAnnotations = (...args) => app().consumeAnnotations(...args);
export const mountThreadViews = (...args) => app().mountThreadViews(...args);
export const registerThreadPresentation = (...args) =>
  app().registerThreadPresentation(...args);
export const threadActions = Object.freeze({
  open: (...args) => app().threadActions.open(...args),
  create: (...args) => app().threadActions.create(...args),
  reply: (...args) => app().threadActions.reply(...args),
  resolve: (...args) => app().threadActions.resolve(...args),
  reopen: (...args) => app().threadActions.reopen(...args),
  setReaction: (...args) => app().threadActions.setReaction(...args),
});
export const askActions = Object.freeze({
  open: (...args) => app().openAsk(...args),
  next: (...args) => app().nextAsk(...args),
});
export const queueActions = Object.freeze({
  open: (...args) => app().queueActions.open(...args),
  done: (...args) => app().queueActions.done(...args),
});
export const wireInput = (...args) => app().wireInput(...args);
