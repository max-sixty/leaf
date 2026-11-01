/* Leaf runtime boot and application composition root. */
import { registerSampleCommand, onSampleNotice } from "./runtime/sample-child.js";
import "/runtime/framework.js";
import "./runtime/interaction-log.js";
// Restored panels and the first keyboard gesture share the ordinary synchronous
// control routes, so their controls must be upgraded before those routes mount.
import "./vendor/webawesome-chrome.js";
import { offlineInteractive, runtime, annotationMode } from "./runtime/context.js";
import { initializeServedDocument } from "./runtime/document-identity.js";
import { chromeRoot, chromeForeground } from "./runtime/chrome.js";
import { landingPlace } from "./runtime/reading-place.js";
import { claimTraversals, mountHistory, replaceEntry } from "./runtime/history.js";
import { holdArrivingBounds } from "./runtime/bounds.js";
import { chromeSheet, marksSheet, annotationSheets } from "./runtime/stylesheets.js";
import { reportPageError, uploadMedia } from "./runtime/layer-client.js";
import { prepareDocument, upgradeWidgets } from "./runtime/widget-loader.js";
import {
  markPagePresented,
  markPageUpgraded,
  whenArrived,
  pageReadiness,
  settlePageInterface,
  afterPresentation,
  PRESENTATION,
} from "./runtime/presentation.js";
import { pagePresented } from "./runtime/page-paint.js";
import { nextFrame, renderingState, observePreparations } from "./runtime/rendering.js";
import { observeQueuedWork } from "./runtime/queued-work.js";
import { mountApplication } from "./runtime/application.js";
import { beginRead } from "./runtime/state-feed.js";
import {
  applicationState,
  whenApplicationPresented,
} from "./runtime/semantic-state.js";
import { createEngagement } from "./runtime/composing/engagement.js";
import { createCompositionInputs } from "./runtime/composing/input.js";
import {
  composerOpen,
  composerQuote,
  fabBar,
  fabInput,
  pendingAbout,
  pendingAnchor,
  pendingDrawing,
} from "./runtime/composing/selection.js";
import { createResponseSurface } from "./runtime/composing/surface.js";
import { createPassageSelection } from "./runtime/composing/capture.js";
import { createDrawingController } from "./runtime/composing/drawing.js";
import { createRegionCapture } from "./runtime/composing/region-capture.js";
import { createDrawingInk } from "./runtime/composing/drawing-ink.js";
import { createAim } from "./runtime/composing/aim.js";
import {
  createTargetPicker,
  targetPickerHintLayer,
} from "./runtime/composing/target-picker.js";
import { createCurrentTarget } from "./runtime/composing/current-target.js";
import {
  createReactionController,
  reactionTokens,
  sendReaction,
} from "./runtime/reactions.js";
import { createAnchorPlacement } from "./runtime/anchor-placement.js";
import { createAnchorControls } from "./runtime/anchor-controls.js";
import { createAnchorTravel } from "./runtime/anchor-travel.js";
import {
  aimTargetAt,
  aimTargets,
  fragmentTarget,
  resolveAnchor,
  setAnchoringReady,
} from "./runtime/anchor-resolution.js";
import { createPageGeometry } from "./runtime/page-geometry.js";
import * as targetPaint from "./runtime/target-paint.js";
import { pointerAt } from "./runtime/pointer.js";
import { createWritingResume } from "./runtime/drafts.js";
import { createRewriteRestore } from "./runtime/thread/message-edit.js";
import { allThreads, threadNamed } from "./runtime/thread/state.js";
import { anchorLabel } from "./runtime/thread/messages.js";
import {
  createThreadLanding,
  declareThreadKeys,
  scrollThreadIntoView,
  currentLocationThread,
} from "./runtime/thread/landing.js";
import { createFloatingPanel } from "./runtime/floating-panel.js";
import { currentLocationThreadId } from "./runtime/thread/focus.js";
import { createPageMapDialog } from "./runtime/page-map-dialog.js";
import { createObligationView } from "./runtime/obligations/view.js";
import { createQueueWalk } from "./runtime/queue-walk.js";
import { createChangeWalk } from "./runtime/change-walk.js";
import {
  commandHintLayer,
  createCommandHints,
} from "./runtime/keyboard/command-hints.js";
import { createDesignMode, inspectEl, legendRoot } from "./runtime/design.js";
import { marginBarLayer } from "./runtime/margin-bars.js";
import { createPageLayout } from "./runtime/page-layout.js";
import { restoreUserView } from "./runtime/restore-state.js";
import { createVersionController, takeInitialDocument } from "./runtime/version.js";
import { loadIcon, mountPageStatus } from "./runtime/page-status.js";
import "./runtime/page-about.js";

import { nativeLayers } from "./runtime/keyboard/layer-stack.js";
import { holdToRead } from "./runtime/held-word.js";

import { leavesOffered } from "./runtime/live-leaves.js";
import { acceptData, notifyDataSubscribers } from "./runtime/data.js";
import {
  createGoToSequence,
  goToHintLayer,
} from "./runtime/keyboard/go-to-sequence.js";
import { presented, windowChromeBoxes } from "./runtime/geometry.js";
// The page's own keyboard parts join the register as this module evaluates; every other
// owner contributes its own as it is constructed below.
import { declareCurrentLocation } from "./runtime/keyboard/page.js";
import { mountKeyboard } from "./runtime/keyboard/controller.js";
import { paintCoreControls } from "./runtime/keyboard/control-keys.js";
import { paintTouchControls } from "./runtime/keyboard/touch-controls.js";
import { paintCloseRequests } from "./runtime/keyboard/close-requests.js";
import {
  commandReferenceDialog,
  mountCommandReference,
} from "./runtime/keyboard/command-reference.js";
import { paintStatusContext } from "./runtime/keyboard/status-context.js";
import {
  paintKeys,
  reflectFirstScopes,
  reflectKeys,
} from "./runtime/keyboard/scopes.js";
import { watchDisclosures } from "./runtime/keyboard/disclosure.js";
import { mountRepaint, repaint, repaintPage } from "./runtime/repaint.js";
import { openDocumentLayout } from "./runtime/content-layout.js";
import {
  createNavigation,
  placeThreadEdge,
  glideTo,
  stopGlide,
} from "./runtime/navigation.js";
import {
  declareReading,
  focusDestination,
  releaseFocus,
  focused,
} from "./runtime/focus.js";
import { announce, liveEl, notice } from "./runtime/notifications.js";
import { raiseError } from "./runtime/errors.js";
import { mediaViewer } from "./runtime/media.js";
import { retainUserIntent, restrictUserIntent } from "./runtime/user-intent.js";

// The boot runs in a function, since a compiled module awaits nothing at its top
// level (`topLevelAwaitRule` in eslint.config.mjs says why). Its rejection names
// an incomplete startup through the same boundary, wherever boot stopped.
async function boot() {
  await document.documentElement.lfSample?.ready;
  initializeServedDocument();
  const initialStateRead = beginRead();
  const initialDocument = takeInitialDocument();
  if (!(await prepareDocument(initialDocument))) return;
  holdArrivingBounds();

  // A published shell may bundle the entry without publishing its source modules beside
  // it. Keep the synchronous validation seam on Leaf's own bootstrap element so render
  // checks can inspect either distribution without turning it into a package API. These
  // scene readings answer different questions: which readiness fact the page has yet to state
  // (`pageReadiness`), whether its counted queue or complete finite preparation has
  // settled (`renderingState`), and which native layers expose reading and controls.
  // Job lifecycle tracing binds at enqueue without replacing any rendering callback, and
  // widget preparation tracing at each declaration and its settlement.
  const validationEntry = [...document.scripts].find((script) =>
    script.hasAttribute("data-lf-entry"),
  );
  if (validationEntry) {
    validationEntry.lfReadiness = pageReadiness;
    validationEntry.lfRenderingState = renderingState;
    validationEntry.lfObserveQueuedWork = observeQueuedWork;
    validationEntry.lfObserveWidgetPreparations = observePreparations;
    validationEntry.lfNativeLayers = nativeLayers;
  }

  // Automatic recovery belongs to this arrival. A press made while its presentation
  // waits owns the page; recovery must not capture a fresh focus intent after that wait.
  const recoverComposer = retainUserIntent({ since: 0 });
  // Capture the requested address before widgets add their display fragment. Authored
  // fragments take precedence, so a copied heading still reaches its passage.
  const arrivalUrl = new URL(location.href);
  const threadArrival = retainUserIntent({ since: 0 });

  // This declaration belongs to the executable document lifetime. The revision capture
  // includes it in executable identity, so selecting another presentation retires this
  // module graph through the ordinary document replacement and draft carry owners.
  const overlaySelected = annotationMode === "overlay";
  const annotationRenderer = overlaySelected
    ? await import("./runtime/annotation-overlay/index.js")
    : null;
  if (validationEntry && annotationRenderer)
    validationEntry.lfFloatingSelections = annotationRenderer.floatingSelections;
  annotationRenderer?.mountAnnotationControls();

  /** @type {ReturnType<typeof mountApplication>} */
  let app;
  /** @type {ReturnType<typeof createPageLayout>} */
  let layout;
  /** @type {ReturnType<typeof createPageMapDialog>} */
  let pageMapDialog;
  /** @type {ReturnType<typeof createObligationView>} */
  let items;
  /** @type {ReturnType<typeof createResponseSurface>} */
  let responseSurface;
  /** @type {ReturnType<typeof createDrawingController>} */
  let drawing;
  /** @type {ReturnType<typeof createRegionCapture>} */
  let regionCapture;
  // A draft's drawing put in place, null taking it off, and the page's ink repainted.
  /** @type {Parameters<typeof createDrawingController>[0]["replaceDrawing"]} */
  const replaceDrawing = (anchor, drawn) => {
    responseSurface.setDraftDrawing(anchor, drawn);
    drawingPaint.paint();
  };
  // A composer's own controls for the drawing its draft holds, which the drawing
  // controller answers, and its history's way of putting one back.
  /** @type {Parameters<typeof createResponseSurface>[0]["drawingEdits"]} */
  const drawingEdits = {
    target: (anchor) => drawing.target(anchor),
    undoStroke: (anchor) => drawing.undoStroke(anchor),
    remove: (anchor) => drawing.removeDrawing(anchor),
    replace: replaceDrawing,
  };
  /** @type {ReturnType<typeof createAim>} */
  let aim;
  /** @type {ReturnType<typeof createTargetPicker>} */
  let targets;
  /** @type {ReturnType<typeof createReactionController>} */
  let reactions;
  /** @type {ReturnType<typeof createPageGeometry>} */
  let pageGeometry;
  /** @type {ReturnType<typeof createGoToSequence>} */
  let goToSequence;

  /** @type {ReturnType<typeof createFloatingPanel>} */
  let floatingPanel;
  const navigation = createNavigation({
    placedAt: (id) => anchorPlacement.placedAt(id),
    threadDestinations: {
      openPageThread: (...args) => app.threadDestinations.openPageThread(...args),
      threadAtCurrentLocation: (node) =>
        app.threadDestinations.threadAtCurrentLocation(node),
      threadPlace: (...args) => app.threadDestinations.threadPlace(...args),
    },
  });

  // The fixed furniture every generated-hint map is spread around: the window's declared
  // chrome (geometry.js). Both maps read the same boxes.
  const hintChrome = { barriers: windowChromeBoxes };
  const anchorPlacement = createAnchorPlacement();
  /** @type {ReturnType<NonNullable<typeof annotationRenderer>["createVisualMarkPaint"]> | undefined} */
  let visualMarkPaint;
  /** @type {ReturnType<NonNullable<typeof annotationRenderer>["createAnchorPaint"]> | undefined} */
  let anchorPaint;
  if (annotationRenderer) {
    visualMarkPaint = annotationRenderer.createVisualMarkPaint();
    anchorPaint = annotationRenderer.createAnchorPaint({
      targetPaint: visualMarkPaint,
      pointer: pointerAt,
      currentLocationThreadId,
      currentLocationObligation: () => items.currentLocationIn(),
      rowThread: () => floatingPanel?.hoveredThread() ?? null,
      threadRow: (id) => floatingPanel?.threadRow(id) ?? null,
      marginThread: () => app?.overlay?.pointedThread() ?? null,
    });
  }
  const drawingPaint = createDrawingInk({
    drawings: () => [
      ...(annotationRenderer?.postedDrawings(allThreads(), anchorPlacement) ?? []),
      ...drawing.drawings(),
    ],
  });
  const designMode = createDesignMode({
    pageGeometry: {
      refreshAim: () => pageGeometry.refreshAim(),
      pageShifted: () => pageGeometry.pageShifted(),
    },
    syncGeneral: () => generalComment.sync(),
    composer: {
      showFab: (...args) => responseSurface.showFab(...args),
      openComposer: (...args) => responseSurface.openComposer(...args),
    },
    closePreview: (...args) => app.overlay?.closePreview(...args),
    marginTargetAt: (...args) => app.overlay?.marginTargetAt(...args) ?? null,
    closeDrawMode: () => drawing.setDrawMode(false, { spoken: false }),
    closeTargetPicker: () => targets.closeTargetPicker(),
    closeReactionMode: () => reactions.setReact(false),
    announce,
    repaint,
  });
  aim = createAim({
    marginTargetAt: (...args) => app.overlay?.marginTargetAt(...args) ?? null,
    refreshAim: () => pageGeometry.refreshAim(),
    commentOnTarget: (...args) => responseSurface.commentOnTarget(...args),
    drawModeActive: () => drawing.drawModeActive(),
    designMode,
    targetPicker: {
      active: () => targets.choosing(),
      choose: (...args) => targets.chooseTarget(...args),
    },
  });
  pageGeometry = createPageGeometry({
    refreshAnchorHover: anchorPaint?.refreshHover,
    aim: { isOn: aim.aimIsOn, target: aim.aimedTarget },
    pointer: pointerAt,
    designMode,
    targetPaint,
    visualMarkPaint,
    shiftDrawings: drawingPaint.shifted,
    queueLegend: designMode.queueLegend,
    legendScrolled: designMode.legendScrolled,
    activeActionAnchor: () => responseSurface.fabAnchorAt(),
    refreshActionBar: () => responseSurface.refreshFab(),
  });
  // A placement through the margin where it is mounted, which reveals a hidden row first,
  // with `focusDestination`'s arguments.
  /** @type {typeof focusDestination} */
  const focusForNavigation = (node, cause, options) =>
    app?.overlay?.focusForNavigation
      ? app.overlay.focusForNavigation(node, cause, options)
      : focusDestination(node, cause, options);
  const anchorTravel = createAnchorTravel({
    anchors: anchorPlacement,
    refreshThread: () => app.refreshThread(),
    focusForNavigation,
    threadFocusTarget: (id, options) =>
      app.threadDestinations.threadFocusTarget(id, options),
    clearFor: (destination, landed) =>
      floatingPanel?.clearFor(destination, landed) ?? null,
    announce,
  });
  const landing = createThreadLanding();
  declareThreadKeys(landing.landIn, () => app.threadDestinations.threadHere() ?? null);
  const anchorControls = createAnchorControls({
    commentOnTarget: (...args) => responseSurface.commentOnTarget(...args),
    openThread: (...args) => app.threadDestinations.openPageThread(...args),
    withdrawReaction: (...args) => app.withdraw(...args),
    labelAnchor: anchorLabel,
    invalidateThread: () => app.refreshThread(),
    invalidatePageGeometry: pageGeometry.invalidate,
    messageReferenceRoot: chromeRoot,
    draftQuote: composerQuote,
    focused,
    paintKeys,
  });

  const version = createVersionController({
    initialDocument,
    compositionInput: fabInput,
    openThread: (id, options) =>
      app.threadDestinations.openPageThread(id, { ...options, travel: false }),
    refreshThread: () => app.refreshThread(),
    midComposition: (...args) => app.midComposition(...args),
    hasPending: () => app.hasPending(),
    readAndApply: (...args) => app.readAndApply(...args),
    syncLayout: () => layout.syncLayout(),
    // The chrome the reader stands in: a margin card or entry, and the panel's thread.
    captureRetainedCurrentLocation: () => ({
      margin: app?.overlay?.captureCurrentLocation() ?? null,
      panel: floatingPanel.captureCurrentLocation(),
    }),
    restoreRetainedCurrentLocation: ({ margin, panel }) => {
      const panelShown = floatingPanel.restoreCurrentLocation(panel);
      return (app?.overlay?.restoreCurrentLocation(margin) ?? false) || panelShown;
    },
    captureObligationCurrentLocation: () => items.captureCurrentLocation(),
    restoreObligationCurrentLocation: (currentLocation) =>
      items.restoreCurrentLocation(currentLocation),
    versions: { press: () => floatingPanel.doors.versions.press() },
  });

  const inputs = createCompositionInputs({
    uploadMedia,
    inputHint: () => responseSurface.commentHint(),
  });

  app = mountApplication({
    arriveAtQueueItem: (item) => queueWalk.arriveAtItem(item),
    nextObligationWithin: (options) => queueWalk.nextWithin(options),
    threadAvailable: !offlineInteractive,
    createEngagement,
    targetPickerOpen: () => targets.targetPickerOpen(),
    wireInput: inputs.wireInput,
    anchorPlacement,
    anchorPaint: anchorPaint ?? null,
    anchorControls,
    drawingPaint,
    pageGeometry,
    anchorTravel,
    readThreadDraft: () => ({
      open: composerOpen,
      anchor: pendingAnchor,
      about: pendingAbout,
      drawing: pendingDrawing,
    }),
    activeActionAnchor: () => responseSurface.fabAnchorAt(),
    compositionSurface: {
      active: () => {
        const anchor = composerOpen ? responseSurface?.fabAnchorAt() : null;
        return anchor ? { anchor } : null;
      },
      node: () => fabBar,
      open: (...args) => responseSurface.commentOnTarget(...args),
      outlet: () => responseSurface?.fabInlineOutlet() ?? null,
      seat: (...args) => responseSurface.seatFab(...args),
      restore: (...args) => responseSurface?.restoreFab(...args) ?? false,
      finishPlacement: () => responseSurface?.finishPlacement(),
    },
    landInThread: (...args) => landing.landInThread(...args),
    landSent: (...args) => landing.landSent(...args),
    registerReactSurface: (...args) => reactions.registerReactSurface(...args),
    sendReaction,
    createMarginProjection: annotationRenderer?.createMarginProjection,
    annotationCommands: {
      designModeActive: designMode.active,
      pointerModeActive: () =>
        designMode.active() || drawing.drawModeActive() || regionCapture.active(),
      leavePageMap: (...args) => pageMapDialog.leavePageMap(...args),
      openPageMap: (...args) => pageMapDialog.openPageMap(...args),
      pageMapDialogContains: (...args) => pageMapDialog.pageMapDialogContains(...args),
      renderPageMapDialog: (...args) => pageMapDialog.renderPageMapDialog(...args),
      scrollThreadIntoView,
      openInPanel: (id) => floatingPanel?.openThread(id),
      goToObligation: (...args) => items.goToObligation(...args),
    },
    state: {
      prepareActivation: (state) => version.prepareActivation(state),
      acceptData,
      notifyDataSubscribers,
    },
  });
  if (offlineInteractive) applicationState.setHostAvailable(false);

  // Where a landing in the document goes, which is version continuity's reading of what is
  // on screen. Declared beside the let-go that uses it, for the same reason: the owner
  // stands by now and nothing has read the register yet.
  declareReading(landingPlace);

  // The let-go's external readings stand by now, so the scope is declared before anything
  // reads the register.
  declareCurrentLocation({
    pageState: () =>
      Boolean(
        responseSurface.fabAnchorAt() ||
        designMode.active() ||
        drawing.drawModeActive() ||
        app.overlay?.optionsRung(),
      ),
  });

  pageMapDialog = createPageMapDialog({
    inventory: app.annotations,
    activeInAnnotations: app.overlay?.pageMapActive,
    releaseAnnotations: app.overlay?.releaseForMap,
    annotationFocus: app.overlay?.mapFocusTarget,
  });

  // The obligation view is constructed below by its owner factory; all accesses above are inert closures.
  items = createObligationView({
    focusForNavigation,
    presentedControl: (control) => app.overlay?.presentedControl(control) ?? control,
    prepareNavigationStep: anchorTravel.prepareNavigationStep,
    arrive: anchorTravel.arrive,
    openPageThread: app.threadDestinations.openPageThread,
    announce,
    repaint,
  });
  const queueWalk = createQueueWalk({
    actions: app.queueActions,
    arriveAtRecord: items.arriveAtRecord,
    arriveAtThread: navigation.arriveAtThread,
    threadPlace: (id) => app.threadDestinations.threadPlace(id),
    prepareNavigationStep: anchorTravel.prepareNavigationStep,
    arrive: anchorTravel.arrive,
    readableDestination: anchorTravel.readableDestination,
    showOnMe: () => floatingPanel.showOnMe(),
    announce,
  });
  const changeWalk = createChangeWalk();
  const commandHints = createCommandHints({
    presentedControl: (control) => app.overlay?.presentedControl(control) ?? control,
  });

  const currentTarget = createCurrentTarget({
    currentLocationIn: items.currentLocationIn,
  });

  floatingPanel = createFloatingPanel({
    wireInput: inputs.wireInput,
    observeFeedback: app.read.observeFeedback,
    firstUnread: app.read.firstUnread,
    afterReadingPass: app.read.afterPass,
    threadActions: app.threadActions,
    registerChromeThreadPresentation: app.registerChromeThreadPresentation,
    obligations: { choicesOf: items.choicesOf },
    queueActions: app.queueActions,
    arrivesAt: (item) => queueWalk.arrivesAt(item),
    onMe: queueWalk.onMe,
    withdraw: app.withdraw,
    settlement: app.settlement,
    placedAt: anchorPlacement.placedAt,
    openThreadSubject: (id, options) =>
      app.threadDestinations.openThreadSubject(id, options),
    atLastResort: (key) => app.threadDestinations.atLastResort(key),
    annotationsHidden: () => annotationRenderer?.annotationsHidden() ?? false,
  });
  // The page's general comment box is the floating panel's field.
  const generalComment = floatingPanel.pageComment;
  const passageSelection = createPassageSelection({
    restore: anchorTravel.restoreSelection,
  });
  responseSurface = createResponseSurface({
    rememberSelection: passageSelection.remember,
    createPlacement: annotationRenderer?.createFloatingResponsePlacement,
    landIn: landing.landIn,
    threadHere: () => app.threadDestinations.threadHere(),
    threadAtCurrentLocation: () => app.threadDestinations.threadAtCurrentLocation(),
    threadTarget: (id) => app.threadDestinations.threadTarget(id),
    currentTarget,
    markAt: anchorPaint?.markAt,
    scrollToElement: anchorTravel.scrollToElement,
    scrollToRange: anchorTravel.scrollToRange,
    visualActionAnchor: anchorControls.visualActionAnchor,
    designModeActive: designMode.active,
    designTarget: designMode.target,
    openOnDesign: designMode.open,
    isReactArmed: () => reactions.isReactArmed(),
    reactionContextContains: (...args) =>
      Boolean(reactions.reactionContextContains(...args)),
    reactionTokens,
    setReact: (...args) => reactions.setReact(...args),
    openPageThread: app.threadDestinations.openPageThread,
    drawModeActive: () => drawing.drawModeActive(),
    captureActive: () => regionCapture.active(),
    refreshThread: app.refreshThread,
    dismissThreadView: () => app.overlay?.inlineThreadView.dismiss(),
    pageComment: generalComment,
    responseHome: overlaySelected ? chromeRoot : floatingPanel.responseHome,
    revealResponseHome: overlaySelected ? null : floatingPanel.revealResponse,
    createComment: (command) => app.threadActions.create(command)?.delivery ?? null,
    landSent: landing.landSent,
    wireInput: inputs.wireInput,
    drawingEdits,
  });
  reactions = createReactionController({
    marginEntryChoices: app.overlay?.marginEntryChoices,
    marginEntryContextContains: app.overlay?.marginEntryContextContains,
    openMarginEntryOptions: app.overlay?.openMarginEntryOptions,
    designModeActive: designMode.active,
    hideComposer: responseSurface.hideComposer,
    syncResponseOptions: responseSurface.syncResponseOptions,
    fabAnchorAt: responseSurface.fabAnchorAt,
    fabReturnPlaces: responseSurface.fabReturnPlaces,
    fabTargetAt: responseSurface.fabTargetAt,
    hasPageSelectionTarget: responseSurface.hasPageSelectionTarget,
    showFab: responseSurface.showFab,
    showFabOptions: responseSurface.showFabOptions,
    updateFab: responseSurface.updateFab,
    currentLocationThread,
    currentTarget,
  });
  targets = createTargetPicker({
    scrollToRange: anchorTravel.scrollToRange,
    hintChrome,
    commentOnTarget: responseSurface.commentOnTarget,
    updateFab: responseSurface.updateFab,
    fabAnchorAt: responseSurface.fabAnchorAt,
    pointerModeActive: () => drawing.drawModeActive() || regionCapture.active(),
    readTargets: () => (designMode.active() ? designMode.targets() : aimTargets()),
    armChanged: () => aim.armChanged(),
    searchInPanel: floatingPanel.searchPage,
  });
  drawing = createDrawingController({
    anchors: { aimTargetAt, resolveAnchor },
    pageGeometry: { refreshAim: pageGeometry.refreshAim },
    pointer: pointerAt,
    visibleTargets: targets.visibleTargets,
    anchoredDrawing: responseSurface.draftDrawing,
    heldDrawings: responseSurface.heldDrawings,
    watchHeldDrawings: responseSurface.watchHeldDrawings,
    draftKey: responseSurface.draftKey,
    openAnchoredDrawing: (anchor, drawing) =>
      responseSurface.openComposer(anchor, "", { carry: true, drawing }),
    replaceDrawing,
    setDesignMode: designMode.setActive,
    closeTargetPicker: targets.closeTargetPicker,
    closeReactionMode: () => reactions.setReact(false),
    announce,
    paintDrawings: drawingPaint.paint,
    shiftDrawingPaint: drawingPaint.shifted,
    repaint,
  });
  regionCapture = createRegionCapture({
    closeTargetPicker: targets.closeTargetPicker,
    closeReactionMode: () => reactions.setReact(false),
    parent: chromeForeground,
    visibleTargets: targets.visibleTargets,
    openComposerWithMedia: responseSurface.openComposerWithMedia,
  });

  layout = createPageLayout({
    scheduleThreadPreviewPosition: app.overlay?.scheduleThreadPreviewPosition,
    syncReactLayout: reactions.syncReactLayout,
    refreshFab: responseSurface.refreshFab,
    pageShifted: pageGeometry.pageShifted,
    repaintPage,
  });
  // The sample host binds to this child's owners, rather than importing another
  // window's runtime. This capability is ready before the child presents.
  if (document.documentElement.lfSample) {
    /** @type {AbortController | undefined} */
    let viewOperation;
    onSampleNotice("cancel-view", () => viewOperation?.abort());
    registerSampleCommand("thread", async ({ id, surface }) => {
      viewOperation?.abort();
      viewOperation = new AbortController();
      const { signal } = viewOperation;
      const retained = retainUserIntent({ available: () => !signal.aborted });
      // A host view never takes focus, but newer child input still supersedes it.
      const intent = restrictUserIntent(retained, retained);
      // The host's usable interface includes comments while history still loads.
      // Selecting a saved conversation needs the child's authoritative reading.
      return afterPresentation(async () => {
        if (!intent()) return false;
        if (surface === "panel") {
          /** @type {ReturnType<typeof floatingPanel.showForSample> | null} */
          let shown = null;
          const show = () => (shown = floatingPanel.showForSample({ thread: id }));
          if (!intent.handoff(show)) return false;
          return Boolean(await shown) && intent.available();
        }
        return Boolean(
          await app.threadDestinations.openPageThread(id, {
            focus: false,
            travel: false,
            intent,
          }),
        );
      });
    });
  }

  const writingResume = createWritingResume({
    arriveEditor: anchorTravel.arriveEditor,
    revealInThread: (context, intent) =>
      app.threadDestinations.openThreadDraft(context, intent),
    holdsThreadDraft: (context) => app.threadDestinations.holdsThreadDraft(context),
  });
  const rewriteRestore = createRewriteRestore({
    revealInThread: (context, intent) =>
      app.threadDestinations.openThreadDraft(context, intent),
    holdsThreadDraft: (context) => app.threadDestinations.holdsThreadDraft(context),
  });
  goToSequence = createGoToSequence({
    doors: floatingPanel.doors,
    hintChrome,
    openPageMap: (...args) => pageMapDialog.openPageMap(...args),
    directDestinations: () => [
      writingResume,
      rewriteRestore,
      passageSelection.command,
      navigation.alignTop,
      app.read.firstUnreadCommand,
      version.PICKER,
    ],
    scrollToElement: anchorTravel.scrollToElement,
    leavesOffered,
    marginEntries: app.overlay ?? null,
    glideTo,
    placeThreadEdge,
    stopGlide,
  });
  const currentLocationPainters = {
    markHere: items.markHere,
    paintCurrentLocation: () => anchorPaint?.paintCurrentLocation(),
    paintSelectedMarginEntries: () =>
      app.overlay?.paintSelectedMarginEntries([
        { kind: "on-me", target: items.currentLocationIn() },
        {
          kind: "comment",
          target: anchorPlacement.placedAt(currentLocationThreadId())?.place ?? null,
        },
      ]),
    paintTouchControls,
    paintCloseRequests,
    paintStatusContext: () => paintStatusContext(goToSequence.goToStatus),
    paintGoToHints: goToSequence.paintGoToHints,
    paintTargetPickerHints: targets.paintTargetPickerHints,
    paintCommandHints: commandHints.paint,
    paintCoreControls,
    publishInputHint: inputs.publishInputHint,
  };

  if (!offlineInteractive) {
    document.adoptedStyleSheets = [
      ...document.adoptedStyleSheets,
      ...annotationSheets,
      chromeSheet,
      marksSheet,
    ];
    // One permanent home for the chrome's foreground; none of these live descendants is
    // reparented.
    chromeForeground.append(
      targetPaint.targetTraceLayer,
      targetPaint.aimLayer,
      liveEl,
      mediaViewer,
      commandReferenceDialog,
      inspectEl,
    );
    chromeRoot.append(
      legendRoot,
      marginBarLayer,
      ...(visualMarkPaint ? [visualMarkPaint.layer] : []),
      drawingPaint.layer,
      fabBar,
      chromeForeground,
    );
    document.body.append(chromeRoot);
    version.mount();
    mountPageStatus();
    floatingPanel.mount(chromeForeground);
    responseSurface.mount();
    holdToRead();
    reactions.mount();
    targets.mount();
    drawing.mount();
    aim.mount();
    targetPaint.mountTargetPaint();
    anchorPaint?.mount();
    anchorControls.mount();
    pageGeometry.mount();
    pageMapDialog.mount(chromeForeground);
    items.mount();
    queueWalk.mount();
    changeWalk.mount();
    commandHints.mount();
    app.mountAnnotations();
    app.overlay?.mount();
    // Margin rows insert before the permanent foreground home, so these chips are laid
    // out after every target they name while retaining their native modal ancestor.
    chromeForeground.append(goToHintLayer, commandHintLayer, targetPickerHintLayer);
    app.mountRead();
    layout.mountLayoutObservers();
    goToSequence.mountGoToSequence();
    mountCommandReference({
      beforeOpening: () => {
        goToSequence.setGoToSequence(false);
        reactions.setReact(false);
      },
    });
    watchDisclosures(document);
    mountRepaint({
      ...currentLocationPainters,
      reflectFirstScopes,
      reflectKeys,
      syncLayout: layout.syncLayout,
      pageShifted: pageGeometry.pageShifted,
    });
  } else {
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, chromeSheet];
    chromeRoot.append(mediaViewer);
    document.body.append(chromeRoot);
    // Exports retain image inspection, but no page controls. Their other current location is
    // what a widget's own box shows, such as an options group's addition field.
    mountRepaint({
      publishInputHint: inputs.publishInputHint,
      paintCloseRequests,
      reflectFirstScopes,
      reflectKeys,
    });
  }

  // Widget commands belong to interactive documents, including offline exports.
  // The register admits page and chrome commands only in a live document.
  mountKeyboard({
    goToSequenceActive: goToSequence.goToSequenceActive,
    setGoToSequence: goToSequence.setGoToSequence,
    reactArmed: reactions.isReactArmed,
    setReact: reactions.setReact,
  });
  // A page declared failed (`lf-startup-failed`) is its readable fallback from then on
  // (prepaint.js) and never presents, though a later state answer asks it to. A page
  // whose module staged words it cannot read (passages.js, `refusesBareText`) reads past
  // them afterwards, and presented, it would pass for a page whose widgets work.
  let startupFailed = false;
  window.addEventListener("lf-startup-failed", () => (startupFailed = true), {
    once: true,
  });

  if (!offlineInteractive) {
    restoreUserView({ setDesignMode: designMode.setActive });
    annotationRenderer?.restoreAnnotations();
    // A page nobody has used starts Tab at the first control. Inputs before the
    // module graph arrived already gave this document a place to keep.
    recoverComposer.handoff(releaseFocus);
  }
  mountHistory({
    followFragment: anchorTravel.followFragment,
    returnToFragment: anchorTravel.returnToFragment,
  });
  const landFragment = version.aimArrival();
  const { landArrival, savedView } = offlineInteractive
    ? { landArrival: () => {}, savedView: null }
    : version.installArrival();
  const savedComposer = offlineInteractive ? null : responseSurface.pendingComposer();
  // A thread address follows the same return rule as an authored fragment: keep the
  // entry's working place while its destination is still shown; reveal it again when
  // another view has hidden it. The browser owns the entry in either case.
  /** @param {URL} url @param {boolean} [returning] */
  function threadRoute(url, returning = false) {
    const id = url.searchParams.get("thread");
    if (!id || fragmentTarget(url.hash)) return null;
    const destination = app.threadDestinations.threadFocusTarget(id, {
      part: "thread",
    });
    if (returning && destination && presented(destination)) return null;
    const retained = returning ? retainUserIntent() : threadArrival;
    // This is navigation even without focus on a return, not an editing continuation
    // allowed to materialize after the user has moved elsewhere.
    const intent = restrictUserIntent(retained, retained);
    return async () => {
      if (!intent()) return false;
      if (!threadNamed(id)) {
        raiseError(`Thread ${id} is unavailable`);
        return false;
      }
      const opened = await app.threadDestinations.openPageThread(id, {
        part: "thread",
        focus: !returning,
        history: false,
        intent,
      });
      // Revealing a destination may rename the entry to its enclosing view. This
      // arrival owns the final address, so Reload and copied links reach the thread.
      if (opened && intent()) replaceEntry(url);
      return Boolean(opened);
    };
  }
  claimTraversals((url) => threadRoute(url, true));
  if (arrivalUrl.searchParams.has("thread"))
    void afterPresentation(() => threadRoute(arrivalUrl)?.());

  async function presentPage() {
    // Saved state gates state-dependent interaction, not the commenting interface.
    if (applicationState.read().phase === "waiting" || pagePresented() || startupFailed)
      return;
    await whenApplicationPresented();
    if (applicationState.read().phase === "waiting") return;
    if (pagePresented()) return;
    if (startupFailed) return;
    markPagePresented();
    // Optional author context begins after the presented frame. It neither imports
    // checks nor takes geometry on the path that gives the reader the page.
    if (!offlineInteractive)
      nextFrame(() =>
        setTimeout(() => {
          void import("./runtime/user-view.js")
            .then(({ observeUserView }) => observeUserView())
            .catch(() => {});
        }, 0),
      );
    void whenArrived().then(landFragment);
    if (offlineInteractive) {
      landFragment();
      document.dispatchEvent(new Event(PRESENTATION));
      return;
    }
    paintKeys();
    repaint();
    app.overlay?.flushLayout();
    landFragment();
    // The geometry readers PRESENTATION replaces run in the turn the stamp above opens
    // interaction, after the landing's synchronous part, rather than after an editor
    // the landing waits for: awaited first, a margin map presented its authored spans.
    const arrival = landArrival();
    document.dispatchEvent(new Event(PRESENTATION));
    await arrival;
    const currentRevision = runtime.currentRevision;
    if (savedView && currentRevision !== null && savedView.revision < currentRevision)
      notice(`Updated to ${runtime.currentLabel}`, { background: true });
  }

  async function startPage() {
    const [upgraded] = await Promise.all([
      upgradeWidgets({
        buildReactionBar: () =>
          offlineInteractive
            ? undefined
            : reactions.buildReactBar({
                withdrawReaction: app.withdraw,
                postReaction: app.post,
              }),
      }),
      offlineInteractive
        ? Promise.resolve()
        : loadIcon().catch((error) =>
            reportPageError(error, "tab icon failed to load"),
          ),
    ]);
    if (!upgraded) return;
    app.watchThreadSurfaces();
    // Read native document layout and subscribe annotations to its later changes.
    openDocumentLayout({
      onRead: (changed) => annotationRenderer?.syncMarginContentLayout(changed),
    });
    if (!offlineInteractive) {
      layout.syncLayout();
      items.buildBulkAnswers();
      items.syncObligations();
    }
    await settlePageInterface();
    landFragment();
    // Comments name the shown document, not the private history still loading. Its
    // widgets and words are now settled; prepare the anchor-dependent chrome before
    // opening keyboard capture, so malformed coordinates never become controls.
    setAnchoringReady(true);
    try {
      await app.presentThread();
      await whenApplicationPresented();
    } catch (error) {
      setAnchoringReady(false);
      throw error;
    }
    markPageUpgraded();
    // Restoring an editor requires a visible destination. Its placement certifies
    // drawn content, so it cannot be a prerequisite for revealing the page itself.
    const draftOpened =
      !offlineInteractive &&
      // A thread address takes the reader to its destination. The saved draft
      // remains available through Resume writing, without taking that arrival's focus.
      !threadRoute(arrivalUrl) &&
      recoverComposer() &&
      responseSurface.openDraft(savedComposer);
    if (draftOpened) {
      await app.presentThread();
      await responseSurface.fabPositioned();
    }
    anchorControls.publishVisualActions();
    responseSurface.updateFab();
    paintKeys();
    app.startFeed(presentPage, initialStateRead);
  }

  return startPage();
}

boot().catch((error) => {
  const reason = `page failed to start: ${error?.message ?? error}`;
  window.lfDocumentLifetime.whenActive(`start ${reason}`, () => {
    window.dispatchEvent(
      new CustomEvent("lf-startup-failed", { detail: { reason, error } }),
    );
    reportPageError(error, "page failed to start");
    applicationState.setReach({ reach: "broken" });
  });
});
