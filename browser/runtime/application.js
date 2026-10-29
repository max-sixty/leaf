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
  applicationPresenter,
  PRESENTATION_DOM,
  readPart,
} from "./semantic-state.js";
import { announce } from "./notifications.js";
import { answeredInWords, readObligations } from "./obligations/model.js";
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
import { createThreadDestinations } from "./thread/destination.js";
import { createThreadActions } from "./thread/actions.js";
import { createQueueActions, queueItemKey } from "./queue-api.js";
import { createPrimaryReader } from "./thread/primary-reader.js";
import { nextRender } from "./rendering.js";
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
import { raiseError } from "./errors.js";

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
        ["projection:chrome", "thread", "obligations"],
        stillCurrent,
      ),
    ]);
    // Waiting can cross a newer publication. Retire only the candidates selected
    // before the wait and only if their semantic settlement still permits release.
    const released = ledger
      .releasable()
      .filter((entry) => attempts.has(entry.event.attempt));
    // Widget updates and the thread, projection, and obligation owners have now committed
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

  createProjectionPresentation();
  // A widget's drawn marks reach it through `projectMarked` (leaf-element.js).
  createDataProjection({ invalidateDom });

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
      if (isMessageEvent(entry.event)) announce("Message added");
      if (entry.event.kind === "edit") announce("Message edited");
    } catch (error) {
      reportPageError(error, "optimistic presentation");
    } finally {
      void delivery.drain();
    }
  }

  commandDispatch.mount({
    afterEnqueue,
    // A widget's gesture is announced by the name the widget gave it, the name its undo
    // is announced by too. The live region alone says it: the pick is drawn where the
    // user made it, and the margin's receipt says it was saved.
    named: (entry, says) => {
      undo.retainGesture(entry.event.attempt, { says });
      void entry.answer.then((admitted) => {
        if (admitted) announce(says);
      });
    },
    withdraw: (candidate) => undo.withdraw(candidate),
    onCollision: (attempt) =>
      raiseError(`Couldn't send — attempt ${attempt} is already in use`),
  });

  const { post } = commandDispatch;

  const undo = createUndo({
    post,
    stateApplying,
    unaccountedGesture: engagement.unaccountedGesture,
    openThread: openPageThread,
    threadPlace: (id) => dependencies.anchorTravel.threadDestination(id),
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
  };
  const settlementView = {
    pendingEntries: ledger.snapshot,
    actions: threadActions,
    landedAway: undo.landedAway,
    returnToThread: undo.returnToThread,
  };
  const reactionView = {
    registerSurface: dependencies.registerReactSurface,
    actions: threadActions,
  };
  const inlineView = {
    reply: replyView,
    settlement: settlementView,
    reaction: reactionView,
    // A thread's head ends the user's to-do on it with its own Done.
    todos: { done: (id) => queueActions.done(queueItemKey({ kind: "todo", id })) },
    read,
    openThread: openPageThread,
    landInThread: dependencies.landInThread,
  };
  const surfaceView = {
    ...inlineView,
    composition: dependencies.compositionSurface,
  };

  const annotations = createAnnotationInventory({
    readObligations,
    placedAt: dependencies.anchorPlacement.placedAt,
    openThread: openPageThread,
    goToObligation: dependencies.annotationCommands.goToObligation,
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
  // The margin's annotations, which the margin's own geometry and contributions also
  // redraw directly. `refresh()` redraws them once they have been drawn.
  let annotationsDrawn = false;
  const renderAnnotations = () => {
    annotationsDrawn = true;
    if (!onPaper.matches) {
      const entries = refreshAnnotationInventory();
      overlay?.paint(entries);
    }
  };
  renderAnnotations.refresh = () => {
    if (annotationsDrawn) renderAnnotations();
  };
  // The inventory lists the marks the projection's chrome paints, reading their nodes,
  // which signals cannot track, so it reads the parts that move them itself, and
  // reads them once that region has committed. What the thread pass decides about
  // each thread, where it is placed and whether a widget seats or holds it, and the
  // ages the margin shows are followed with the rest of what this paint reads, so a
  // commit that moves one and the clock repaint them by the same proof.
  const annotationInputs = readPart(annotationSelection);
  let marginPresentation = null;
  const mountAnnotations = () => {
    const presentation = applicationPresenter({
      region: "annotations",
      after: PRESENTATION_DOM.obligations,
      reading: () => annotationInputs(),
      paint: renderAnnotations,
    });
    marginPresentation = presentation;
    void presentation.present();
    // A paint on paper read no ages, so the return to screen paints through the
    // presenter, which follows them again.
    onPaper.addEventListener("change", () => {
      if (!onPaper.matches) void presentation.present();
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
    designModeActive: dependencies.annotationCommands.designModeActive,
    pointerModeActive: dependencies.annotationCommands.pointerModeActive,
    leavePageMap: dependencies.annotationCommands.leavePageMap,
    openPageMap: dependencies.annotationCommands.openPageMap,
    pageMapDialogContains: dependencies.annotationCommands.pageMapDialogContains,
    scrollThreadIntoView: dependencies.annotationCommands.scrollThreadIntoView,
    renderMarginThread: (host, thread, controls) =>
      renderMarginThread(host, thread, inlineView, controls),
    placedAt: dependencies.anchorPlacement.placedAt,
    marksFor: (id) => dependencies.anchorPaint?.marksFor(id) ?? [],
    scrollToElement: dependencies.anchorTravel.scrollToElement,
    openInPanel: dependencies.annotationCommands.openInPanel,
  });
  const threadDestinations = createThreadDestinations({
    threadIdsAt: annotations.threadIdsAt,
    placedAt: dependencies.anchorPlacement.placedAt,
    scrollToThread: dependencies.anchorTravel.scrollToThread,
    arrive: dependencies.anchorTravel.arrive,
    prepareNavigationStep: dependencies.anchorTravel.prepareNavigationStep,
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
    renderSurfaces,
    // Where a thread stands now, put up for a user carried there from a box a surface
    // stopped drawing: the surface drawing it, its margin card, or the floating panel.
    openThread: (id, options) =>
      threadDestinations.openPageThread(id, { ...options, travel: false }),
    // A native Tab visit outside a displaced row retains editing without taking focus.
    continueThread: (id, intent) =>
      threadDestinations.openPageThread(id, {
        part: "reply",
        focus: false,
        travel: false,
        scroll: false,
        intent,
      }),
    returnToPage: threadDestinations.returnToPage,
    // The thread a margin entry stands for, which a user on it goes on with when the
    // thread leaves the margin.
    threadAt: (node) => overlay?.entryThread(node) ?? null,
    // The margin's own commit, which reply continuity waits for; before the margin
    // mounts there is nothing to wait for.
    marginCommitted: () => marginPresentation?.committed() ?? Promise.resolve(),
    read,
  });
  const accountPending = (receipts) => {
    ledger.present(receipts);
    releasePendingSafely("receipt presentation");
  };

  stateApplication = createStateApplication({
    prepareActivation: dependencies.state.prepareActivation,
    acceptData: dependencies.state.acceptData,
    notifyDataSubscribers: dependencies.state.notifyDataSubscribers,
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
        // In that ordering a gesture that is not an action leaves on accept rather
        // than with the reading that logged it, so this edge claims the document pass
        // that draws the page without it.
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

  // One reader is the page's primary at a time (thread/destination.js). Leaf's own
  // chrome registers one that yields (`registerChromeThreadPresentation`, which the
  // runtime alone is handed): a reader the page's package registers
  // takes the place while it stands, since the author's presentation outranks Leaf's
  // defaults, and the chrome's returns when it leaves. `primary` says which holds it. The
  // chrome's `yielded`, asked before its reader goes, returns how to hand the reader
  // taking its place the conversation it shows, which runs once the package holds its
  // registration, as that reader may ask it to present.
  // A presentation that makes room for the agent's answer to the user's last turn
  // itself says so (`answersAtOnce`), and its reader draws that answer at once.
  const attachPresentation = (
    owner,
    { render, reveal, answersAtOnce = false },
    onFailure = undefined,
  ) => {
    const reader = createPrimaryReader(
      owner,
      render,
      inlineView,
      () => threadPresenter.present(),
      { answersAtOnce, onFailure },
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
  // A package's reader takes the place from the chrome's.
  const takePlace = (entry) => {
    const displaced = yielding?.attached;
    const handOff = displaced ? yielding.spec.yielded() : null;
    if (displaced) {
      displaced.detach();
      yielding.attached = null;
    }
    try {
      entry.attached = attachPresentation(entry.owner, entry.spec, () =>
        nextRender(() => fallBack(entry)),
      );
    } catch (error) {
      if (displaced) restoreYielding();
      throw error;
    }
    authored = entry;
    if (handOff)
      queueMicrotask(() => {
        if (authored === entry) handOff();
      });
  };
  // A package's reader whose pass failed holds nothing: its threads, and the asks in
  // them, would stand in no surface the user can reach, and opening one would ask the
  // failed reader again. So it gives the place back to the chrome's, whose floating
  // panel draws them, until the package asks to draw again (`update`), when it takes
  // the place, and the thread open in the panel, back. It gives way on the next frame,
  // once the failed pass has rejected the `update` that asked for it, unless a later
  // pass of its own has painted by then.
  const fallBack = (entry) => {
    if (authored !== entry || !entry.attached?.reader.failed) return;
    entry.attached.detach();
    entry.attached = null;
    restoreYielding();
  };
  const presentThreads = (owner, spec, yields) => {
    const entry = { owner, spec, attached: null };
    if (yields) {
      if (yielding)
        throw new Error("The page already has a yielding Thread presentation");
      yielding = entry;
      // A package's reader registered first keeps the place.
      if (!authored) entry.attached = attachPresentation(owner, spec);
    } else takePlace(entry);
    let active = true;
    return Object.freeze({
      get primary() {
        return Boolean(entry.attached);
      },
      update: ({ release = false } = {}) => {
        if (active && authored === entry && !entry.attached) takePlace(entry);
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
    mountRead: read.mount,
    registerThreadPresentation: (owner, spec) => presentThreads(owner, spec, false),
    registerChromeThreadPresentation: (owner, spec) =>
      presentThreads(owner, spec, true),
    navigateToDatum: dependencies.anchorTravel.navigateToDatum,
    post,
    readAndApply: feed.readAndApply,
    refreshThread,
    presentThread,
    watchThreadSurfaces,
    placePageThreads,
    consumeAnnotations,
    threadActions,
    queueActions,
    settlement: settlementView,
    openObligation(id) {
      const item = readObligations().all.find((item) => item.id === id);
      if (!item) return Promise.resolve(false);
      if (item.source.kind === "update" || item.source.kind === "todo")
        return queueActions.open(JSON.stringify([item.source.kind, item.id]));
      if (item.thread !== null && answeredInWords(item)) {
        showHeld(item.thread);
        return threadDestinations.openPageThread(item.message, {
          part: "message",
        });
      }
      return dependencies.annotationCommands.goToObligation(
        item,
        readObligations().all,
      );
    },
    // The On me walk within one region (queue-walk.js), the walk an `lf-tally` steps.
    nextObligation: (options) => dependencies.nextObligationWithin(options),
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
export const post = commandDispatch.post;
export const placePageThreads = (...args) => app().placePageThreads(...args);
export const consumeAnnotations = (...args) => app().consumeAnnotations(...args);
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
export const obligationActions = Object.freeze({
  open: (...args) => app().openObligation(...args),
  next: (...args) => app().nextObligation(...args),
});
export const queueActions = Object.freeze({
  open: (...args) => app().queueActions.open(...args),
  done: (...args) => app().queueActions.done(...args),
});
export const wireInput = (...args) => app().wireInput(...args);
