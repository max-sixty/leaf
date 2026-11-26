/* Leaf runtime boot and application composition root. */
// Leaf's Lit loads in any document and inserts natively until the page installs its
// mover (dom/dom-move.js); importing the mover's focus accounting first installs both
// before any module the boot loads can render.
import "./runtime/dom/move-focus.js";
import { registerSampleCommand, onSampleNotice } from "./runtime/host/sample-child.js";
import "./runtime/stage-integration.js";
import { hostDeclaredElements } from "./runtime/host/element-integration.js";
import "./runtime/transport/interaction-log.js";
// Restored panels and the first keyboard gesture share the ordinary synchronous
// control routes, so their controls must be upgraded before those routes mount.
import "/vendor/webawesome-chrome.js";
import {
  offlineInteractive,
  runtime,
  annotationMode,
} from "./runtime/state/context.js";
import { initializeServedDocument } from "./runtime/state/document-identity.js";
import { chromeRoot, chromeForeground } from "./runtime/base/chrome.js";
import { landingPlace } from "./runtime/readings/reading-place.js";
import { arrive, beginArrival, mountHistory } from "./runtime/records/history.js";
import { entryView } from "./runtime/records/views.js";
import { holdArrivingBounds } from "./runtime/readings/bounds.js";
import {
  chromeSheet,
  marksSheet,
  annotationSheets,
} from "./runtime/base/stylesheets.js";
import { reportPageError, uploadMedia } from "./runtime/transport/layer-client.js";
import { prepareDocument, upgradeWidgets } from "./runtime/records/widget-loader.js";
import {
  markPagePresented,
  markPageUpgraded,
  whenArrived,
  arrivalsOutstanding,
  pageReadiness,
  settlePageInterface,
  afterPresentation,
  deferredArrival,
  PRESENTATION,
} from "./runtime/readings/presentation.js";
import { pagePresented } from "./runtime/base/page-paint.js";
import { renderingState, observePreparations } from "./runtime/base/rendering.js";
import { nextFrame } from "./runtime/lib/frame-pass.js";
import { observeQueuedWork } from "./runtime/lib/queued-work.js";
import { mountApplication } from "./runtime/host/application.js";
import { beginRead } from "./runtime/host/state-feed.js";
import {
  applicationState,
  whenApplicationPresented,
} from "./runtime/state/semantic-state.js";
import { createEngagement } from "./runtime/annotations/composing/engagement.js";
import { createCompositionInputs } from "./runtime/annotations/composing/input.js";
import {
  composerOpen,
  composerQuote,
  fabBar,
  pendingAbout,
  pendingAnchor,
  pendingDrawing,
} from "./runtime/annotations/composing/selection.js";
import { createResponseSurface } from "./runtime/annotations/composing/surface.js";
import { createPassageSelection } from "./runtime/annotations/composing/capture.js";
import { createDrawingController } from "./runtime/annotations/composing/drawing.js";
import { createRegionCapture } from "./runtime/annotations/composing/region-capture.js";
import { createDrawingInk } from "./runtime/annotations/composing/drawing-ink.js";
import { createAim } from "./runtime/annotations/composing/aim.js";
import {
  createTargetPicker,
  targetPickerHintLayer,
} from "./runtime/annotations/composing/target-picker.js";
import { createCurrentTarget } from "./runtime/annotations/composing/current-target.js";
import {
  createReactionController,
  reactionEmoji,
  sendReaction,
} from "./runtime/annotations/reactions.js";
import { createAnchorPlacement } from "./runtime/annotations/anchor-placement.js";
import { createAnchorControls } from "./runtime/annotations/anchor-controls.js";
import { createAnchorTravel } from "./runtime/features/anchor-travel.js";
import {
  aimTargetAt,
  aimTargets,
  resolveAnchor,
  setAnchoringReady,
} from "./runtime/readings/anchor-resolution.js";
import { refuseBareText } from "./runtime/readings/passages.js";
import { createPageGeometry } from "./runtime/panel/page-geometry.js";
import {
  aimLayer,
  clearAim,
  geometryChanged,
  labelAim,
  paintAim,
  shifted,
} from "./runtime/readings/target-paint.js";
import { pointerAt } from "./runtime/base/pointer.js";
import { createWritingResume } from "./runtime/records/drafts.js";
import { allThreads } from "./runtime/records/thread/state.js";
import { anchorLabel } from "./runtime/records/thread/messages.js";
import { createThreadAddress } from "./runtime/records/thread/address.js";
import {
  declareThreadKeys,
  landIn,
  landInThread,
  landSent,
  scrollThreadIntoView,
  currentLocationThread,
} from "./runtime/records/thread/landing.js";
import { createFloatingPanel } from "./runtime/panel/floating-panel.js";
import { currentLocationThreadId } from "./runtime/records/thread/focus.js";
import { createPageMapDialog } from "./runtime/panel/page-map-dialog.js";
import { createObligationView } from "./runtime/records/obligations/view.js";
import { createQueueWalk } from "./runtime/panel/queue-walk.js";
import { createChangeWalk } from "./runtime/panel/change-walk.js";
import {
  commandHintLayer,
  createCommandHints,
} from "./runtime/readings/key-badges/command-hints.js";
import {
  createDesignMode,
  inspectEl,
  legendRoot,
} from "./runtime/annotations/design.js";
import { marginBarLayer } from "./runtime/features/margin-bars.js";
import { createPageLayout } from "./runtime/panel/page-layout.js";
import { restoreUserView } from "./runtime/state/restore-state.js";
import {
  annotationsHidden,
  ANNOTATIONS_TOGGLE,
  restoreAnnotations,
} from "./runtime/annotations/annotation-layer.js";
import { restoreThreadsInPanel } from "./runtime/records/thread/threads-in-panel.js";
import { createAnchorPaint } from "./runtime/annotations/anchor-paint.js";
import { createVisualMarkPaint } from "./runtime/annotations/visual-mark-paint.js";
import {
  createVersionController,
  takeInitialDocument,
} from "./runtime/features/version.js";
import { loadIcon, mountPageStatus } from "./runtime/panel/page-status.js";
import "./runtime/panel/page-about.js";
// Defined before any widget's module loads, so a template that draws an age needs no
// import.
import "./runtime/age.js";

import { nativeLayers } from "./runtime/dom/keyboard/layer-stack.js";
import { mountPreviews } from "./runtime/annotations/preview.js";

import { leavesOffered } from "./runtime/host/live-leaves.js";
import { acceptData, notifyDataSubscribers } from "./runtime/host/data.js";
import {
  createGoToSequence,
  goToHintLayer,
} from "./runtime/panel/page-keys/go-to-sequence.js";
import { coverBoxes } from "./runtime/dom/geometry.js";
// The page's own keyboard parts join the register as this module evaluates; every other
// owner contributes its own as it is constructed below.
import { declareCurrentLocation } from "./runtime/panel/page-keys/page.js";
import { letHeldKeysGo, mountKeyboard } from "./runtime/panel/page-keys/controller.js";
import { paintCoreControls } from "./runtime/dom/keyboard/control-keys.js";
import { paintTouchControls } from "./runtime/panel/page-keys/touch-controls.js";
import { paintCloseRequests } from "./runtime/dom/keyboard/close-requests.js";
import {
  commandReferenceDialog,
  mountCommandReference,
} from "./runtime/panel/page-keys/command-reference.js";
import { paintStatusContext } from "./runtime/panel/page-keys/status-context.js";
import {
  paintKeys,
  reflectFirstScopes,
  reflectKeys,
} from "./runtime/dom/keyboard/scopes.js";
import { mountRepaint, repaint, repaintPage } from "./runtime/dom/repaint.js";
import { openDocumentLayout } from "./runtime/readings/content-layout.js";
import { createNavigation, placeThreadEdge } from "./runtime/panel/navigation.js";
import {
  declareReading,
  focusDestination,
  releaseFocus,
  focused,
} from "./runtime/dom/focus.js";
import { announce, liveEl, notice } from "./runtime/transport/notifications.js";
import { mediaViewer } from "./runtime/records/media.js";
import { retainUserIntent, restrictUserIntent } from "./runtime/dom/user-intent.js";
import { installMoveSelection } from "./runtime/dom/dom-move.js";
import { holdSelection } from "./runtime/dom/native-selection.js";

// Leaf's selection writer keeps a page selection across `setChildLists`'s moves
// (dom/dom-move.js), installed before the boot draws anything.
installMoveSelection(holdSelection);

// The boot runs in a function, since a compiled module awaits nothing at its top
// level (`topLevelAwaitRule` in eslint.config.mjs says why). Its rejection names
// an incomplete startup through the same boundary, wherever boot stopped.
async function boot() {
  await document.documentElement.lfSample?.ready;
  initializeServedDocument();
  const initialStateRead = beginRead();
  const initialDocument = takeInitialDocument();
  if (!(await prepareDocument(initialDocument))) return letHeldKeysGo();
  holdArrivingBounds();
  hostDeclaredElements();

  // A published shell may bundle the entry without publishing its source modules beside
  // it. Keep the synchronous validation seam on Leaf's own bootstrap element so render
  // checks can inspect either distribution without turning it into a package API. These
  // scene readings answer different questions: which readiness fact the page has yet to state
  // (`pageReadiness`), how many arrivals it has yet to land (`arrivalsOutstanding`),
  // whether its counted queue or complete finite preparation has
  // settled (`renderingState`), and which native layers expose reading and controls.
  // Job lifecycle tracing binds at enqueue without replacing any rendering callback, and
  // widget preparation tracing at each declaration and its settlement.
  const validationEntry = [...document.scripts].find((script) =>
    script.hasAttribute("data-lf-entry"),
  );
  if (validationEntry) {
    validationEntry.lfReadiness = pageReadiness;
    validationEntry.lfArrivalsOutstanding = arrivalsOutstanding;
    validationEntry.lfRenderingState = renderingState;
    validationEntry.lfObserveQueuedWork = observeQueuedWork;
    validationEntry.lfObserveWidgetPreparations = observePreparations;
    validationEntry.lfNativeLayers = nativeLayers;
  }

  // Automatic recovery belongs to this arrival. A press made while its presentation
  // waits owns the page; recovery must not capture a fresh focus intent after that wait.
  const recoverComposer = retainUserIntent({ since: 0 });

  // This declaration belongs to the executable document lifetime. The revision capture
  // includes it in executable identity, so selecting another presentation retires this
  // module graph through the ordinary document replacement and draft carry owners.
  const overlaySelected = annotationMode === "overlay";
  const annotationRenderer = overlaySelected
    ? await import("./runtime/annotations/annotation-overlay/index.js")
    : null;
  if (validationEntry && annotationRenderer)
    validationEntry.lfFloatingSelections = annotationRenderer.floatingSelections;

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
  /** @type {ReturnType<typeof createTargetPicker>} */
  let targets;
  /** @type {ReturnType<typeof createReactionController>} */
  let reactions;
  /** @type {ReturnType<typeof createPageGeometry>} */
  let pageGeometry;

  /** @type {ReturnType<typeof createFloatingPanel>} */
  let floatingPanel;
  const navigation = createNavigation({
    placedAt: (id) => anchorPlacement.placedAt(id),
    savedAt: (context) => anchorPlacement.savedAt(context),
    showDraft: (context) => writingResume.showDraft(context),
    threadDestinations: {
      openPageThread: (...args) => app.threadDestinations.openPageThread(...args),
      threadAtCurrentLocation: (node) =>
        app.threadDestinations.threadAtCurrentLocation(node),
    },
  });

  // The fixed furniture every generated-hint map is spread around: the boxes the chrome
  // covers (dom/geometry.js, `coverBoxes`). Both maps read the same boxes.
  const hintChrome = { barriers: () => coverBoxes() };
  const anchorPlacement = createAnchorPlacement();
  // Every page marks its commented words, previews their threads under the pointer
  // and opens one on a press, whoever draws its margin.
  const anchorPaint = createAnchorPaint({
    targetPaint: createVisualMarkPaint(),
    pointer: pointerAt,
    currentLocationThreadId,
    rowThread: (under) => floatingPanel?.hoveredThread(under) ?? null,
    threadRow: (id) => floatingPanel?.threadRow(id) ?? null,
    marginThread: () => app?.overlay?.pointedThread() ?? null,
    placedAt: (id) => anchorPlacement.placedAt(id),
    pendingAt: () => anchorPlacement.pendingAt(),
    settle: () => anchorPlacement.settle(),
  });
  anchorPlacement.hearPlaced((change) => anchorPaint.replace(change));
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
  const aim = createAim({
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
    refreshAnchorHover: anchorPaint.refreshHover,
    aim: { isOn: aim.aimIsOn, target: aim.aimedTarget },
    pointer: pointerAt,
    designMode,
    pointerModeActive: () => drawing.drawModeActive() || regionCapture.active(),
    targetPaint: { clearAim, geometryChanged, labelAim, paintAim, shifted },
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
  declareThreadKeys(() => app.threadDestinations.threadHere() ?? null);
  const anchorControls = createAnchorControls({
    commentOnTarget: (...args) => responseSurface.commentOnTarget(...args),
    openThread: (...args) => app.threadDestinations.openPageThread(...args),
    withdrawReaction: (...args) => app.withdraw(...args),
    labelAnchor: anchorLabel,
    invalidateThread: () => app.refreshThread(),
    invalidatePageGeometry: pageGeometry.invalidate,
    placement: anchorPlacement,
    messageReferenceRoot: chromeRoot,
    draftQuote: composerQuote,
    focused,
    paintKeys,
  });

  // Where the user is in the chrome's thread views, a margin card or entry and the
  // panel's thread, which a revision carries.
  const captureChrome = () => {
    const margin = app?.overlay?.captureCurrentLocation() ?? null;
    const panel = floatingPanel.captureCurrentLocation();
    return margin || panel ? { margin, panel } : null;
  };

  const version = createVersionController({
    initialDocument,
    openThread: (id, options) =>
      app.threadDestinations.openPageThread(id, {
        reader: "standing",
        ...options,
        travel: false,
      }),
    refreshThread: () => app.refreshThread(),
    midComposition: (...args) => app.midComposition(...args),
    hasPending: () => app.hasPending(),
    readAndApply: (...args) => app.readAndApply(...args),
    syncLayout: () => layout.syncLayout(),
    captureRetainedCurrentLocation: captureChrome,
    /** @param {ReturnType<typeof captureChrome>} location */
    restoreRetainedCurrentLocation: async (location) => {
      if (!location) return false;
      const panel = floatingPanel.restoreCurrentLocation(location.panel);
      const margin = app?.overlay?.restoreCurrentLocation(location.margin) ?? false;
      return (await margin) || (await panel);
    },
    captureObligationCurrentLocation: () => items.captureCurrentLocation(),
    restoreObligationCurrentLocation: (currentLocation) =>
      items.restoreCurrentLocation(currentLocation),
    versions: {
      press: () => floatingPanel.doors.versions.press(),
      shows: () => floatingPanel.doors.versions.shows(),
      get scope() {
        return floatingPanel.doors.versions.scope;
      },
    },
  });

  const inputs = createCompositionInputs({
    uploadMedia,
    inputHint: () => responseSurface.commentHint(),
  });

  app = mountApplication({
    arriveAtQueueItem: (item) => queueWalk.arriveAtItem(item),
    showTodo: (todo) => floatingPanel?.showTodo(todo),
    nextObligationWithin: (options) => queueWalk.nextWithin(options),
    goToObligation: (record) => queueWalk.goToObligation(record),
    createEngagement,
    targetPickerOpen: () => targets.targetPickerOpen(),
    wireInput: inputs.wireInput,
    anchorPlacement,
    anchorPaint,
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
        return anchor ? { anchor, about: pendingAbout } : null;
      },
      node: () => fabBar,
      open: (...args) => responseSurface.commentOnTarget(...args),
      outlet: () => responseSurface?.fabInlineOutlet() ?? null,
      seat: (...args) => responseSurface.seatFab(...args),
      restore: (...args) => responseSurface?.restoreFab(...args) ?? false,
      finishPlacement: () => responseSurface?.finishPlacement(),
    },
    landInThread,
    landSent,
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
      resumeDraft: (context, route) => writingResume.resumeDraft(context, route),
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

  // The control the user sees for `control`: the margin's copy of one it presents.
  /** @param {Element} control */
  const presentedControl = (control) =>
    app.overlay?.presentedControl(control) ?? control;
  // The obligation view is constructed below by its owner factory; all accesses above are inert closures.
  items = createObligationView({
    focusForNavigation,
    presentedControl,
    prepareNavigationStep: anchorTravel.prepareNavigationStep,
    arrive: anchorTravel.arrive,
    openPageThread: app.threadDestinations.openPageThread,
    threadLanding: anchorTravel.threadLanding,
    repaint,
  });
  const queueWalk = createQueueWalk({
    arriveAtRecord: items.arriveAtRecord,
    arriveAtThread: navigation.arriveAtThread,
    threadPlace: (id) => app.threadDestinations.threadPlace(id),
    prepareNavigationStep: anchorTravel.prepareNavigationStep,
    arrive: anchorTravel.arrive,
    announce,
  });
  createChangeWalk();
  const commandHints = createCommandHints({
    presentedControl,
    coveredEntry: () => responseSurface.coveredEntry(),
  });

  const currentTarget = createCurrentTarget({
    currentLocationIn: items.currentLocationIn,
  });

  floatingPanel = createFloatingPanel({
    wireInput: inputs.wireInput,
    observeFeedback: app.read.observeFeedback,
    threadActions: app.threadActions,
    registerChromeThreadPresentation: app.registerChromeThreadPresentation,
    obligations: { choicesOf: items.choicesOf },
    queueActions: app.queueActions,
    arrivesAt: (item) => queueWalk.arrivesAt(item),
    onMe: queueWalk.onMe,
    withdraw: app.withdraw,
    placedAt: anchorPlacement.placedAt,
    openThreadSubject: (id, options) =>
      app.threadDestinations.openThreadSubject(id, options),
    showsOnPage: (key) => app.threadDestinations.showsOnPage(key),
    annotationsHidden,
    // Resume writing is built once the thread destinations it reveals in stand.
    resumeDraft: (context) => writingResume.resumeDraft(context),
  });
  // The page's general comment box is the floating panel's field.
  const generalComment = floatingPanel.pageComment;
  const passageSelection = createPassageSelection({
    restore: anchorTravel.restoreSelection,
  });
  responseSurface = createResponseSurface({
    rememberSelection: passageSelection.remember,
    createPlacement: annotationRenderer?.createFloatingResponsePlacement,
    landIn,
    threadHere: () => app.threadDestinations.threadHere(),
    threadAtCurrentLocation: () => app.threadDestinations.threadAtCurrentLocation(),
    threadTarget: (id) => app.threadDestinations.threadTarget(id),
    currentTarget,
    markAt: anchorPaint.markAt,
    scrollToElement: anchorTravel.scrollToElement,
    scrollToPassage: anchorTravel.scrollToPassage,
    scrollToRange: anchorTravel.scrollToRange,
    visualActionAnchor: anchorControls.visualActionAnchor,
    designModeActive: designMode.active,
    designTarget: designMode.target,
    openOnDesign: designMode.open,
    isReactArmed: () => reactions.isReactArmed(),
    reactionContextContains: (...args) =>
      Boolean(reactions.reactionContextContains(...args)),
    reactionEmoji,
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
    landSent,
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
    scrollToPassage: anchorTravel.scrollToPassage,
    hintChrome,
    commentOnTarget: responseSurface.commentOnTarget,
    updateFab: responseSurface.updateFab,
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
      responseSurface.openComposer(anchor, "", { drawing }),
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
    refreshCrosshair: pageGeometry.refreshCrosshair,
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
    revealInThread: (context, intent, route) =>
      app.threadDestinations.openThreadDraft(context, intent, route),
    holdsThreadDraft: (context) => app.threadDestinations.holdsThreadDraft(context),
  });
  const goToSequence = createGoToSequence({
    doors: floatingPanel.doors,
    hintChrome,
    openPageMap: (...args) => pageMapDialog.openPageMap(...args),
    directDestinations: () => [
      writingResume.command,
      passageSelection.command,
      navigation.alignTop,
      app.read.firstUnreadCommand,
      version.PICKER,
      ANNOTATIONS_TOGGLE,
    ],
    scrollToElement: anchorTravel.scrollToElement,
    leavesOffered,
    marginEntries: app.overlay ?? null,
    placeThreadEdge,
    stepReading: navigation.stepReading,
  });
  const currentLocationPainters = {
    markHere: items.markHere,
    paintCurrentLocation: () => anchorPaint.paintCurrentLocation(),
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
    restFab: responseSurface.restFab,
  };

  if (!offlineInteractive) {
    // A served page's bootstrap adopted the chrome's sheet for the first paint, with the
    // panel's row it stands there (bootstrap.js, `standRow`); it keeps its place after
    // the annotations' sheets.
    document.adoptedStyleSheets = [
      ...document.adoptedStyleSheets.filter((sheet) => sheet !== chromeSheet),
      ...annotationSheets,
      chromeSheet,
      marksSheet,
    ];
    // One permanent home for the chrome's foreground; none of these live descendants is
    // reparented.
    chromeForeground.append(
      aimLayer,
      liveEl,
      mediaViewer,
      commandReferenceDialog,
      inspectEl,
    );
    chromeRoot.append(
      legendRoot,
      marginBarLayer,
      drawingPaint.layer,
      fabBar,
      chromeForeground,
    );
    // After body, where it stacks over every box the page writes (base.css).
    document.body.after(chromeRoot);
    version.mount();
    mountPageStatus();
    floatingPanel.mount(chromeForeground);
    responseSurface.mount();
    reactions.mount();
    targets.mount();
    drawing.mount();
    aim.mount();
    anchorPaint.mount();
    anchorControls.mount();
    pageGeometry.mount();
    pageMapDialog.mount(chromeForeground);
    items.mount();
    commandHints.mount();
    app.mountAnnotations();
    app.overlay?.mount();
    // Margin rows insert before the permanent foreground home, so these chips are laid
    // out after every target they name.
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
    document.body.after(chromeRoot);
    // Exports retain image inspection, but no page controls. Their other current location is
    // what a widget's own box shows, such as an options group's addition field, and a
    // widget's controls name the keys that reach them there as on a live page.
    mountRepaint({
      publishInputHint: inputs.publishInputHint,
      paintCloseRequests,
      paintCoreControls,
      reflectFirstScopes,
      reflectKeys,
    });
  }
  // Exports keep previews too: a gloss or a timeline's marks say theirs there as well.
  mountPreviews(chromeRoot);

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
  // whose module staged words it cannot read (readings/passages.js, `refusesBareText`) reads past
  // them afterwards, and presented, it would pass for a page whose widgets work.
  let startupFailed = false;
  window.addEventListener("lf-startup-failed", () => (startupFailed = true), {
    once: true,
  });

  if (!offlineInteractive) {
    restoreUserView({ setDesignMode: designMode.setActive });
    restoreAnnotations();
    restoreThreadsInPanel();
    // A page nobody has used starts Tab at the first control. Inputs before the
    // module graph arrived already gave this document a place to keep.
    recoverComposer.handoff(releaseFocus);
  }
  mountHistory({
    followFragment: anchorTravel.followFragment,
    returnToFragment: anchorTravel.returnToFragment,
    view: entryView,
    thread: {
      claim: (url, record, intent) => threadAddress.claim(url, record, intent),
      open: () => openThreadView(),
      focusTarget: (id, part) => app.threadDestinations.threadFocusTarget(id, { part }),
      name: (url) => threadAddress.name(url),
    },
    list: () => floatingPanel.listShown(),
    // A draft's box opens where the user stands, as the walk or Resume writing opened it,
    // with the user on the box, in its words or on a control inside it.
    draft: (key, intent) =>
      key.box && !key.control
        ? writingResume.showDraft(key.draft, { travel: false, intent })
        : writingResume.resumeDraft(key.draft, {
            travel: false,
            intent,
            ...(key.caret && { caret: key.caret }),
            ...(key.control && { control: key.control }),
          }),
  });
  // The document's one arrival (records/history.js, `beginArrival`), whose intent every route
  // it starts runs under, and which the handoff of a reload Leaf asked for joins
  // (features/version.js, `installArrival`).
  const restoration = offlineInteractive ? null : beginArrival();
  // The address the document arrives at, read with its entry and before widgets add
  // their display fragment. Authored fragments take precedence, so a copied heading
  // still reaches its passage.
  const arrivalUrl = new URL(location.href);
  const arrivalIntent = restoration?.intent ?? retainUserIntent({ since: 0 });
  const landFragment = version.aimArrival(arrivalIntent);
  const { landArrival, savedView, restored } = restoration
    ? version.installArrival(restoration)
    : { landArrival: async () => {}, savedView: null, restored: false };
  const savedComposer = offlineInteractive ? null : responseSurface.pendingComposer();
  // The entry's `?thread=` (records/thread/address.js).
  // The thread view standing open: the panel's, else a margin card's.
  /** @returns {import("./runtime/records/thread/address.js").OpenThread | null} */
  function openThreadView() {
    const panel = floatingPanel?.shownThread() ?? null;
    if (panel) return { id: panel, reader: "primary" };
    const card = app?.overlay?.threadPreview.shown() ?? null;
    return card ? { id: card, reader: "card" } : null;
  }
  const threadAddress = createThreadAddress({
    shown: openThreadView,
    putAway: (list, from, intent) => {
      app?.overlay?.threadPreview.close();
      floatingPanel.putThreadAway(list, from, intent);
    },
    openPageThread: (id, options) => app.threadDestinations.openPageThread(id, options),
  });
  threadAddress.followOpenThread();
  // A reload, Leaf's own among them, or Back or Forward from another document,
  // arrives at the entry's record, which returns the user where they left it
  // (records/history.js, `arrive`); the handoff of a reload Leaf asked for adds only what the
  // record doesn't hold (features/version.js). Only a visit the entry kept no record of travels
  // to the thread its address names.
  const threadArrive = restoration?.record
    ? null
    : threadAddress.arrive(arrivalUrl, arrivalIntent, { restored });
  // The arrival holds its work until it has run (records/history.js, `run`).
  /** @param {() => PromiseLike<unknown>} work */
  const arriving = (work) => (restoration ? restoration.run(work) : work());
  if (threadArrive) void arriving(() => afterPresentation(threadArrive));

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
          void import("./runtime/panel/user-view.js")
            .then(({ observeUserView }) => observeUserView())
            .catch(() => {});
        }, 0),
      );
    void arriving(() => whenArrived().then(landFragment));
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
    const arrival = deferredArrival(
      restoration ? arrive(restoration, landArrival) : landArrival(async () => {}),
    );
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
    refuseBareText();
    markPageUpgraded();
    // Restoring an editor requires a visible destination. Its placement certifies
    // drawn content, so it cannot be a prerequisite for revealing the page itself.
    const draftOpened =
      !offlineInteractive &&
      // A thread address takes the reader to its destination, and an entry's record
      // back where they were, which opens the draft only where they were writing it.
      // The saved draft remains available through Resume writing, without taking that
      // arrival's focus.
      !threadArrive &&
      !restoration?.record &&
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
