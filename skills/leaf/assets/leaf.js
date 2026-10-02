/* Leaf runtime boot and application composition root. */
import "./vendor/browser-runtime.js";
import "./runtime/interaction-log.js";
// Restored panels and the first keyboard gesture share the ordinary synchronous
// control routes, so their controls must be upgraded before those routes mount.
import "./vendor/webawesome-chrome.js";
import { passiveSample, offlineInteractive, runtime } from "./runtime/context.js";
import { initializeServedDocument } from "./runtime/document-identity.js";
import { chromeRoot } from "./runtime/chrome.js";
import { readingBlock } from "./runtime/reading-place.js";
import { mountHistory } from "./runtime/history.js";
import { holdArrivingBounds } from "./runtime/bounds.js";
import { chromeSheet, marksSheet } from "./runtime/stylesheets.js";
import { keepPageRulesOffLayer } from "./runtime/page-sheets.js";
import { reportPageError, uploadMedia } from "./runtime/layer-client.js";
import { upgradeWidgets } from "./runtime/widget-loader.js";
import {
  markPagePresented,
  whenArrived,
  pageReadiness,
  settlePageInterface,
  PAGE_INTERFACE,
  PRESENTATION,
} from "./runtime/presentation.js";
import { PAGE_PAINT_ATTRIBUTE } from "./runtime/page-paint.js";
import { nextFrame, renderingSettled } from "./runtime/rendering.js";
import { mountApplication } from "./runtime/application.js";
import {
  applicationState,
  whenApplicationPresented,
} from "./runtime/semantic-state.js";
import { createEngagement } from "./runtime/composing/engagement.js";
import { createCompositionInputs } from "./runtime/composing/input.js";
import {
  createSelectionComposer,
  composerOpen,
  composerQuote,
  fabBar,
  fabInput,
  pendingAbout,
  pendingAnchor,
  pendingDrawing,
} from "./runtime/composing/selection.js";
import { createResponseSurface } from "./runtime/composing/surface.js";
import { createDrawingController } from "./runtime/composing/drawing.js";
import { createDrawingPaint } from "./runtime/composing/drawing-paint.js";
import { createAim } from "./runtime/composing/aim.js";
import {
  createTargetPicker,
  targetPickerHintLayer,
  pageSearchSurface,
} from "./runtime/composing/target-picker.js";
import { createStandingTarget } from "./runtime/composing/standing.js";
import {
  createReactionController,
  reactionTokens,
  sendReaction,
} from "./runtime/reactions.js";
import { createAnchorPlacement } from "./runtime/anchor-placement.js";
import { createAnchorPaint } from "./runtime/anchor-paint.js";
import { createAnchorControls } from "./runtime/anchor-controls.js";
import { createAnchorTravel } from "./runtime/anchor-travel.js";
import {
  aimTargetAt,
  resolveAnchor,
  setAnchoringReady,
} from "./runtime/anchor-resolution.js";
import { createPageGeometry } from "./runtime/page-geometry.js";
import * as targetPaint from "./runtime/target-paint.js";
import { pointerAt } from "./runtime/pointer.js";
import { allThreads, threadList } from "./runtime/thread/state.js";
import { anchorLabel } from "./runtime/thread/messages.js";
import {
  createThreadLanding,
  declareThreadKeys,
  scrollThreadIntoView,
  retainPanelLanding,
  standingThread,
  wireThreadLanding,
} from "./runtime/thread/landing.js";
import { createPanelComposer } from "./runtime/thread/panel.js";
import { focusSurface } from "./runtime/thread/surfaces.js";
import { standingThreadId } from "./runtime/thread/focus.js";
import { createThreadListController } from "./runtime/thread/thread-list.js";
import { createThreadNarrowing } from "./runtime/thread/narrowing.js";
import { createThreadPanelElements } from "./runtime/thread/panel-elements.js";
import { createMarginProjection } from "./runtime/margin-projection.js";
import { createPageMapDialog } from "./runtime/page-map-dialog.js";
import { createAskView } from "./runtime/asks/view.js";
import { askActionLayer, ASK_CONTROL } from "./runtime/asks/view-elements.js";
import { createDesignMode, inspectEl, legendRoot } from "./runtime/design.js";
import { createChromeLayout } from "./runtime/chrome-layout.js";
import { createThreadPanelController } from "./runtime/thread-panel.js";
import {
  createDrawers,
  asksPanel,
  currentDrawer,
  othersPanel,
} from "./runtime/drawers.js";
import { createAuxiliarySurfaces } from "./runtime/auxiliary-surfaces.js";
import { restoreUserView } from "./runtime/restore-state.js";
import { watchProjection } from "./runtime/projection-watch.js";
import { createVersionController } from "./runtime/version.js";
import { versionMenu, versionMenuIsOpen } from "./runtime/version-picker.js";
import {
  banner,
  isSignoffDeclared,
  loadIcon,
  mountBanner,
  paintApproval,
  renderStatus,
  setThreadCounts,
  stateSignoff,
  toggleBtn,
} from "./runtime/banner.js";

initializeServedDocument();
keepPageRulesOffLayer();
holdArrivingBounds();

// A published shell may bundle the entry without publishing its source modules beside
// it. Keep the synchronous validation seam on Leaf's own bootstrap element so render
// checks can inspect either distribution without turning it into a package API. The two
// readings answer different questions: which readiness fact the page has yet to state
// (`pageReadiness`), and whether its chrome and geometry have caught up with the input
// handled since.
const validationEntry = document.querySelector("script[data-lf-entry]");
if (validationEntry) {
  validationEntry.lfReadiness = pageReadiness;
  validationEntry.lfRenderingSettled = renderingSettled;
}
import { overflowMenu } from "./runtime/banner-toolbar.js";
import {
  leavesOffered,
  othersLinks,
  presentLeaves,
  renderOthers,
  declareLeavesKeys,
} from "./runtime/live-leaves.js";
import { acceptData, notifyDataSubscribers } from "./runtime/data.js";
import {
  createGoToSequence,
  goToHintLayer,
} from "./runtime/keyboard/go-to-sequence.js";
import { bannerFoot } from "./runtime/geometry.js";
// The page's own keyboard parts join the register as this module evaluates; every other
// owner contributes its own as it is constructed below.
import { declareStanding } from "./runtime/keyboard/page.js";
import { mountKeyboard } from "./runtime/keyboard/controller.js";
import { paintCoreControls } from "./runtime/keyboard/control-keys.js";
import { paintTouchControls } from "./runtime/keyboard/touch-controls.js";
import { commandReferenceDialog } from "./runtime/keyboard/command-reference.js";
import {
  bottomChromeBoxes,
  collapseShortcutBar,
  mountShortcutBar,
  renderShortcutBar,
  shortcutBarEl,
  standingStatusBoxes,
  bottomStatusEl,
} from "./runtime/keyboard/shortcut-bar.js";
import { focused, paintKeys, reflectFirstScopes } from "./runtime/keyboard/scopes.js";
import { watchDisclosures } from "./runtime/keyboard/disclosure.js";
import { createStanding } from "./runtime/standing.js";
import { mountRepaint, repaint, repaintPage } from "./runtime/repaint.js";
import { layoutMarginRows, syncMarginResidency } from "./runtime/margin-layout.js";
import { openResidency } from "./runtime/content-layout.js";
import {
  createNavigation,
  placeThreadEdge,
  glideTo,
  stopGlide,
} from "./runtime/navigation.js";
import {
  declareCovering,
  declareReading,
  focusDestination,
  releaseFocus,
  tabStops,
} from "./runtime/focus.js";
import { announce, liveEl, notice } from "./runtime/notifications.js";
import { mediaViewer } from "./runtime/media.js";
import { offer } from "./runtime/widget-elements.js";

const panelElements = createThreadPanelElements({ id: "lf-threads" });
const { panel, closeBtn, panelFoot, threadsBox, narrowingView } = panelElements;
const threadListController = createThreadListController(panelElements);
const panelIsOpen = () => auxiliarySurfaces.selectedSurface() === panel;

let app;
const narrowing = createThreadNarrowing({
  view: narrowingView,
  listRoot: threadsBox,
  readThreads: threadList,
  ready: () => runtime.statePhase === "ready",
  repaint: () => app.presentThread(),
});
const paintVersionApproval = () =>
  paintApproval(
    app.pendingApprovals(),
    app.approvalBlockingAsks(),
    app.acceptedApprovals(),
  );
let threadPanelController;
let drawers;
let layout;
let landing;
let pageMapDialog;
let asks;
let panelComposer;
let selectionComposer;
let responseSurface;
let drawing;
let aim;
let targets;
let reactions;
let pageGeometry;
let goToSequence;

const auxiliarySurfaces = createAuxiliarySurfaces({
  chromeRoot,
  band: shortcutBarEl,
  syncLayout: () => layout.syncLayout(),
  afterChange: () => {
    app.renderAnnotations();
    paintKeys();
    repaint();
    anchorPaint.refreshHover();
  },
});
const navigation = createNavigation({
  panelElements,
  openThreads: threadListController.openThreads,
  panelIsOpen,
  narrowing,
  coveringAuxiliaryScroller: auxiliarySurfaces.coveringScroller,
  threadDestinations: {
    openPageThread: (...args) => app.margin.openPageThread(...args),
    scrollToThread: (...args) => anchorTravel.scrollToThread(...args),
    threadHere: () => app.margin.threadHere(),
    threadTarget: (...args) => app.margin.threadTarget(...args),
    inlineThreadView: () => app.margin.inlineThreadView,
  },
});

const targetPaintCaps = {
  clearAim: targetPaint.clearAim,
  paintAim: targetPaint.paintAim,
  paintTrace: targetPaint.paintTrace,
  setTargets: targetPaint.setTargets,
  shifted: targetPaint.shifted,
  geometryChanged: targetPaint.geometryChanged,
};
// The standing furniture every generated-hint map is spread around. Both maps read the
// same three boxes, and they are passed rather than imported so the hint machine keeps
// no ownership edge back to the shortcut bar it is placed against.
const hintChrome = {
  barriers: standingStatusBoxes,
  lineBox: () => shortcutBarEl.getBoundingClientRect(),
  viewportTop: bannerFoot,
};
const anchorPlacement = createAnchorPlacement();
const anchorPaint = createAnchorPaint({
  targetPaint: targetPaintCaps,
  pointer: pointerAt,
  standingThreadId,
  hoveredPanelThreadId: () => {
    const { x, y } = pointerAt();
    const thread = document.elementFromPoint(x, y)?.closest(".lf-thread");
    return thread?.parentElement === threadsBox ? thread.dataset.id : null;
  },
  panelThreadForId: (id) =>
    id
      ? threadsBox.querySelector(`:scope > .lf-thread[data-id="${CSS.escape(id)}"]`)
      : null,
});
const drawingPaint = createDrawingPaint({
  anchors: anchorPlacement,
  activeDrawing: () => drawing.activeDrawing(),
  draftDrawings: () => drawing.draftDrawings(),
});
const designMode = createDesignMode({
  pageGeometry: {
    refreshAim: () => pageGeometry.refreshAim(),
    pageShifted: () => pageGeometry.pageShifted(),
  },
  syncGeneral: () => panelComposer.syncGeneral(),
  composer: {
    showFab: (...args) => responseSurface.showFab(...args),
    openComposer: (...args) => selectionComposer.openComposer(...args),
  },
  closePreview: (...args) => app.margin.closePreview(...args),
  marginTargetAt: (...args) => app.margin.marginTargetAt(...args),
  closeDrawMode: () => drawing.setDrawMode(false, { spoken: false }),
  closeTargetPicker: () => targets.closeTargetPicker(),
  closeReactionMode: () => reactions.setReact(false),
  banner,
  announce,
  repaint,
});
aim = createAim({
  marginTargetAt: (...args) => app.margin.marginTargetAt(...args),
  refreshAim: () => pageGeometry.refreshAim(),
  commentOnTarget: (...args) => responseSurface.commentOnTarget(...args),
  standDown: (...args) => responseSurface.standDown(...args),
  drawModeActive: () => drawing.drawModeActive(),
  designMode,
  targetPicker: {
    active: () => targets.pointerChoosing(),
    choose: (...args) => targets.chooseTarget(...args),
  },
});
pageGeometry = createPageGeometry({
  refreshAnchorHover: anchorPaint.refreshHover,
  aim: { isOn: aim.aimIsOn, target: aim.aimedTarget },
  pointer: pointerAt,
  designMode,
  targetPaint: targetPaintCaps,
  shiftDrawings: drawingPaint.shifted,
  queueLegend: designMode.queueLegend,
  activeActionAnchor: () => responseSurface.fabAnchorAt(),
  refreshActionBar: () => responseSurface.refreshFab(),
});
const anchorTravel = createAnchorTravel({
  anchors: anchorPlacement,
  surfaces: auxiliarySurfaces,
  currentThreads: allThreads,
  refreshThread: () => app.refreshThread(),
  focusForNavigation: (target) => app.margin.focusForNavigation(target),
  threadFocusTarget: (id, options) => app.margin.threadFocusTarget(id, options),
  announce,
});
landing = createThreadLanding({
  threadsBox,
  setPanel: (...args) => threadPanelController.setPanel(...args),
  revealThread: narrowing.revealThread,
  cardTarget: (thread) => app.margin.cardTarget(thread),
});
declareThreadKeys(landing.landIn, narrowing);
const anchorControls = createAnchorControls({
  commentOnTarget: (...args) => responseSurface.commentOnTarget(...args),
  openThread: (...args) => app.margin.openPageThread(...args),
  withdrawReaction: (...args) => app.withdraw(...args),
  labelAnchor: anchorLabel,
  invalidateThread: () => app.refreshThread(),
  invalidatePageGeometry: pageGeometry.invalidate,
  messageReferenceRoot: panel,
  draftQuote: composerQuote,
  focused,
  paintKeys,
});

const version = createVersionController({
  compositionInput: fabInput,
  openThread: (id, options) =>
    app.margin.openPageThread(id, { ...options, travel: false }),
  midComposition: () => app.midComposition(),
  hasPending: () => app.hasPending(),
  readAndApply: (...args) => app.readAndApply(...args),
  forgetAuthoredOwners: (...args) => app.forgetAuthoredOwners(...args),
  retireProjectionCoverage: () => app.retireProjectionCoverage(),
  syncLayout: () => layout.syncLayout(),
  captureRetainedStanding: () => app?.margin.captureStanding() ?? null,
  restoreRetainedStanding: (standing) => app?.margin.restoreStanding(standing) ?? false,
  captureAskStanding: () => asks.captureStanding(),
  restoreAskStanding: (standing) => asks.restoreStanding(standing),
});

const inputs = createCompositionInputs({
  uploadMedia,
  inputHint: () => responseSurface.commentHint(),
});

app = mountApplication({
  panel,
  firstUnreadBtn: panelElements.firstUnreadBtn,
  accompaniedThread: (...args) => landing.accompaniedThread(...args),
  accompanyThread: (...args) => landing.accompanyThread(...args),
  threadAvailable: !offlineInteractive,
  reportPageError,
  createEngagement,
  targetPickerOpen: () => targets.targetPickerOpen(),
  pageComposerDrawing: () => panelComposer.pageComposerDrawing(),
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
    active: () =>
      composerOpen && responseSurface?.fabAnchorAt()
        ? { anchor: responseSurface.fabAnchorAt() }
        : null,
    node: () => fabBar,
    open: (...args) => responseSurface.commentOnTarget(...args),
    outlet: () => responseSurface?.fabInlineOutlet() ?? null,
    seat: (...args) => responseSurface.seatFab(...args),
    restore: (...args) => responseSurface?.restoreFab(...args) ?? false,
  },
  landInThread: (...args) => landing.landInThread(...args),
  landSent: (...args) => landing.landSent(...args),
  showThread: (...args) => landing.showThread(...args),
  panelIsOpen,
  registerReactSurface: (...args) => reactions.registerReactSurface(...args),
  sendReaction,
  updateFab: (...args) => responseSurface.updateFab(...args),
  createMarginProjection,
  margin: {
    designModeActive: designMode.active,
    pointerModeActive: () => designMode.active() || drawing.drawModeActive(),
    comparisonBase: version.comparisonBase,
    comparisonChanges: version.comparisonChanges,
    inlineComparison: version.inlineComparison,
    toggleInlineComparison: version.toggleInlineComparison,
    leavePageMap: (...args) => pageMapDialog.leavePageMap(...args),
    openPageMap: (...args) => pageMapDialog.openPageMap(...args),
    pageMapDialogContains: (...args) => pageMapDialog.pageMapDialogContains(...args),
    renderPageMapDialog: (...args) => pageMapDialog.renderPageMapDialog(...args),
    scrollThreadIntoView,
    goToAsk: (...args) => asks.goToAsk(...args),
  },
  state: {
    prepareActivation: (state) => version.prepareActivation(state),
    acceptData,
    notifyDataSubscribers,
    isSignoffDeclared,
    renderStatus,
    renderVersions: version.renderVersions,
    stateSignoff: (next) => stateSignoff(next, layout.syncLayout, paintVersionApproval),
    renderOthers: offlineInteractive ? () => undefined : renderOthers,
  },
  feed: {
    prepareActivation: (state) => version.prepareActivation(state),
    notifyDataSubscribers,
    renderStatus,
  },
});
app.registerThreadPanel({
  required: true,
  controller: threadListController,
  threadsBox,
  view: {
    narrowing,
    panelIsOpen,
    scrollToElement: anchorTravel.scrollToElement,
    setThreadCounts,
    onListChanged: repaint,
    refreshAnchorHover: anchorPaint.refreshHover,
    travel: {
      showThread: (...args) => landing.showThread(...args),
      retainPanelLanding: (source) =>
        retainPanelLanding(source, panelIsOpen, threadsBox),
      retainNarrowing: narrowing.retainNarrowing,
    },
  },
});
if (offlineInteractive) applicationState.setHostAvailable(false);

// Where a landing in the document goes, which is version continuity's reading of what is
// on screen. Declared beside the let-go that uses it, for the same reason: the owner
// stands by now and nothing has read the register yet.
declareReading(readingBlock);

// And where it goes instead while a surface covers the page: the page is inert under one,
// so the reading above cannot take the user and a step that let go would leave them
// wherever the closing layer happened to drop them. The modality that covers already
// answers both halves for whichever surface is standing — the panel, either drawer — and
// the keyboard register carries the same pair to the dispatcher.
declareCovering({
  surface: auxiliarySurfaces.coveringSurface,
  landing: auxiliarySurfaces.coveringFocus,
});

// The let-go's external readings stand by now, so the scope is declared before anything
// reads the register.
declareStanding({
  pageState: () =>
    Boolean(
      responseSurface.fabAnchorAt() ||
      designMode.active() ||
      drawing.drawModeActive() ||
      app.margin.optionsRung(),
    ),
});

pageMapDialog = createPageMapDialog({
  inventory: app.annotations,
  activeInAnnotations: app.margin.pageMapActive,
  releaseAnnotations: app.margin.releaseForMap,
  annotationFocus: app.margin.mapFocusTarget,
});

// Ask view is constructed below by its owner factory; all accesses above are inert closures.
asks = createAskView({
  panelIsOpen,
  focusForNavigation: app.margin.focusForNavigation,
  presentedControl: app.margin.presentedControl,
  setPanel: (...args) => threadPanelController.setPanel(...args),
  trip: anchorTravel.trip,
  arrive: anchorTravel.arrive,
  refreshThread: () => app.refreshThread(),
  announce,
  repaint,
});

const standingTarget = createStandingTarget({
  isAskControl: (node) => node?.matches?.(ASK_CONTROL),
  standingIn: asks.standingIn,
});

panelComposer = createPanelComposer({
  elements: panelElements,
  openThreads: threadListController.openThreads,
  narrowing,
  designModeActive: designMode.active,
  wireInput: inputs.wireInput,
  createPageComment: app.createPageComment,
  showThread: landing.showThread,
  setPanel: (...args) => threadPanelController.setPanel(...args),
  panelIsOpen,
  stepThread: (...args) => navigation.stepThread(...args),
  firstUnread: () => app.read.firstUnread(),
  unreadCount: () => app.read.unreadCount(),
  paintDrawings: () => drawingPaint.paint(allThreads()),
});
selectionComposer = createSelectionComposer({
  panelIsOpen,
  setReact: (...args) => reactions.setReact(...args),
  reactionTokens,
  designModeActive: designMode.active,
  marginOpenInlineThread: app.margin.openInlineThread,
  threadTransitionOrigin: app.margin.threadTransitionOrigin,
  anchorStands: (...args) => responseSurface.anchorStands(...args),
  anchorTargetAt: (...args) => responseSurface.anchorTargetAt(...args),
  bringForward: (...args) => responseSurface.bringForward(...args),
  fabAnchorAt: (...args) => responseSurface.fabAnchorAt(...args),
  fabPointAt: (...args) => responseSurface.fabPointAt(...args),
  fabFrameAt: () => responseSurface.fabFrameAt(),
  fabPositioned: (...args) => responseSurface.fabPositioned(...args),
  beginFabFocus: (...args) => responseSurface.beginFabFocus(...args),
  endFabFocus: (...args) => responseSurface.endFabFocus(...args),
  landFabFocus: (...args) => responseSurface.landFabFocus(...args),
  showFab: (...args) => responseSurface.showFab(...args),
  formatGoToAddress: (...args) => goToSequence.formatGoToAddress(...args),
  createComment: app.createComment,
  focusSurface,
  showThread: landing.showThread,
  landSent: landing.landSent,
  refreshThread: app.refreshThread,
  wireInput: inputs.wireInput,
});
responseSurface = createResponseSurface({
  panelElements,
  panelIsOpen,
  landIn: landing.landIn,
  setPanel: (...args) => threadPanelController.setPanel(...args),
  threadHere: () => app.margin.threadHere(),
  threadTarget: (thread) =>
    app.margin.threadTarget(thread.dataset.thread ?? thread.dataset.id),
  standingTarget,
  composerHolds: selectionComposer.composerHolds,
  responseOptionsAreOpen: selectionComposer.responseOptionsAreOpen,
  markAt: anchorPaint.markAt,
  scrollToElement: anchorTravel.scrollToElement,
  visualActionAnchor: anchorControls.visualActionAnchor,
  hideComposer: selectionComposer.hideComposer,
  openComposer: selectionComposer.openComposer,
  carryComposerToReply: selectionComposer.carryComposerToReply,
  resetResponseOptions: selectionComposer.resetResponseOptions,
  responseOptionsAvailable: selectionComposer.responseOptionsAvailable,
  setResponseOptions: selectionComposer.setResponseOptions,
  syncResponseOptions: selectionComposer.syncResponseOptions,
  designModeActive: designMode.active,
  designTarget: designMode.target,
  openOnDesign: designMode.open,
  isReactArmed: () => reactions.isReactArmed(),
  reactionContextContains: (...args) => reactions.reactionContextContains(...args),
  reactionTokens,
  setReact: (...args) => reactions.setReact(...args),
  collapseShortcutBar: (...args) => collapseShortcutBar(...args),
  closeVersionMenu: version.closeVersionMenu,
  versionMenuIsOpen,
  openPageThread: app.margin.openPageThread,
  drawModeActive: () => drawing.drawModeActive(),
  refreshThread: app.refreshThread,
  dismissThreadView: () => app.margin.inlineThreadView.dismiss(),
  responseHome: chromeRoot,
});
reactions = createReactionController({
  marginEntryChoices: app.margin.marginEntryChoices,
  marginEntryContextContains: app.margin.marginEntryContextContains,
  foldMarginEntryOptions: app.margin.foldMarginEntryOptions,
  openMarginEntryOptions: app.margin.openMarginEntryOptions,
  unfoldedMarginEntries: app.margin.unfoldedMarginEntries,
  designModeActive: designMode.active,
  hideComposer: selectionComposer.hideComposer,
  syncResponseOptions: selectionComposer.syncResponseOptions,
  fabAnchorAt: responseSurface.fabAnchorAt,
  fabReturnTo: responseSurface.fabReturnTo,
  fabTargetAt: responseSurface.fabTargetAt,
  hasPageSelectionTarget: responseSurface.hasPageSelectionTarget,
  showFab: responseSurface.showFab,
  showFabOptions: responseSurface.showFabOptions,
  updateFab: responseSurface.updateFab,
  standingThread,
  standingTarget,
});
targets = createTargetPicker({
  scrollToRange: anchorTravel.scrollToRange,
  hintChrome,
  commentOnTarget: responseSurface.commentOnTarget,
  updateFab: responseSurface.updateFab,
  fabAnchorAt: responseSurface.fabAnchorAt,
  pointerModeActive: () => designMode.active() || drawing.drawModeActive(),
});
drawing = createDrawingController({
  anchors: { aimTargetAt, resolveAnchor, pendingAt: anchorPlacement.pendingAt },
  pageGeometry: { refreshAim: pageGeometry.refreshAim },
  pointer: pointerAt,
  visibleTargets: targets.visibleTargets,
  pageDrawing: panelComposer.pageComposerDrawing,
  anchoredDrawing: selectionComposer.draftDrawing,
  composerDraft: () => ({
    open: composerOpen,
    anchor: pendingAnchor,
    drawing: pendingDrawing,
  }),
  openAnchoredDrawing: (anchor, drawing) =>
    selectionComposer.openComposer(anchor, "", { carry: true, drawing }),
  openPageDrawing: panelComposer.openPageDrawing,
  setDesignMode: designMode.setActive,
  closeTargetPicker: targets.closeTargetPicker,
  closeReactionMode: () => reactions.setReact(false),
  banner,
  announce,
  paintDrawings: () => drawingPaint.paint(allThreads()),
  shiftDrawingPaint: drawingPaint.shifted,
  repaint,
});

layout = createChromeLayout({
  panelIsOpen,
  elements: {
    panel,
    closeBtn,
    panelFoot,
    threadsBox,
    shortcutBarEl,
    bottomStatusEl,
  },
  scheduleThreadPreviewPosition: app.margin.scheduleThreadPreviewPosition,
  bottomChromeBoxes,
  restateDrawerEdge: () => drawers.drawersEdge.state(),
  syncAuxiliarySurfaces: auxiliarySurfaces.sync,
  syncReactLayout: reactions.syncReactLayout,
  refreshFab: responseSurface.refreshFab,
  pageShifted: pageGeometry.pageShifted,
  repaint,
  repaintPage,
});
threadPanelController = createThreadPanelController({
  narrowing,
  auxiliarySurfaces,
  elements: { panel, toggleBtn, threadsBox, inPanel: panelElements.inPanel },
  threadHere: app.margin.threadHere,
  placedAt: anchorPlacement.placedAt,
  showThread: landing.showThread,
  refreshThread: app.refreshThread,
  closeReactionMode: () => reactions.setReact(false),
  closePreview: app.margin.closePreview,
  syncGeneral: panelComposer.syncGeneral,
});
drawers = createDrawers({
  landEdge: layout.landEdge,
  auxiliarySurfaces,
  closePreview: app.margin.closePreview,
  leavesOffered,
  presentLeaves,
  syncAsks: asks.syncAsks,
});
goToSequence = createGoToSequence({
  panelIsOpen,
  elements: { banner, toggleBtn, threadsBox },
  hintChrome,
  directDestinations: () => [version.PICKER, selectionComposer.KEPT_DRAFT],
  setPanel: threadPanelController.setPanel,
  setOpenDrawer: drawers.setOpenDrawer,
  scrollToElement: anchorTravel.scrollToElement,
  leavesOffered,
  othersLinks,
  activateMarginEntry: app.margin.activateMarginEntry,
  marginEntryKind: app.margin.marginEntryKind,
  visibleMarginEntries: app.margin.visibleMarginEntries,
  glideTo,
  placeThreadEdge,
  seenScroller: navigation.seenScroller,
  stopGlide,
  coveringAuxiliarySurface: auxiliarySurfaces.coveringSurface,
  enterPageMap: pageMapDialog.enterPageMap,
  leavePageMap: pageMapDialog.leavePageMap,
  pageMapIsActive: pageMapDialog.pageMapIsActive,
});
const standing = createStanding({
  markHere: asks.markHere,
  paintStanding: anchorPaint.paintStanding,
  paintSelectedMarginEntries: () =>
    app.margin.paintSelectedMarginEntries([
      { kind: "ask", target: asks.standingIn() },
      {
        kind: "comment",
        target: anchorPlacement.placedAt(standingThreadId())?.place,
      },
    ]),
  paintTouchControls,
  renderShortcutBar: () => renderShortcutBar(goToSequence.goToStatus),
  paintGoToHints: goToSequence.paintGoToHints,
  paintTargetPickerHints: targets.paintTargetPickerHints,
  paintCoreControls,
  paintVersionShortcuts: version.paintShortcuts,
  paintInputs: inputs.paintInputs,
});

const skipToChrome = offer("button", "lf-skip", "Skip to Leaf controls");
skipToChrome.onclick = () => {
  for (const control of tabStops(banner)) {
    control.focus({ preventScroll: true });
    if (control.matches(":focus")) return;
  }
  focusDestination(banner);
};

if (!offlineInteractive) {
  document.adoptedStyleSheets = [
    ...document.adoptedStyleSheets,
    chromeSheet,
    marksSheet,
  ];
  chromeRoot.append(
    banner,
    overflowMenu,
    versionMenu,
    othersPanel,
    asksPanel,
    panel,
    legendRoot,
    goToHintLayer,
    askActionLayer,
    targetPickerHintLayer,
    pageSearchSurface,
    targetPaint.visualMarkLayer,
    drawingPaint.layer,
    targetPaint.targetTraceBox,
    targetPaint.aimBox,
    fabBar,
    liveEl,
    mediaViewer,
    commandReferenceDialog,
    auxiliarySurfaces.scrim,
    bottomStatusEl,
    shortcutBarEl,
    inspectEl,
  );
  document.body.prepend(skipToChrome);
  document.body.append(chromeRoot);
  panelElements.mountReadingRegion();
  panelElements.mountOverlay();
  version.mount();
  mountBanner({
    approveVersion: () => app.post({ kind: "done", version: runtime.currentStamp }),
    paintApproval: paintVersionApproval,
  });
  auxiliarySurfaces.mount();
  // Connect the search field before mount awaits its rendered input: Lit does not
  // resolve updateComplete until connection, and keyboard registration needs that input.
  narrowing.mount();
  await panelComposer.mount();
  selectionComposer.mount();
  responseSurface.mount();
  reactions.mount();
  targets.mount();
  drawing.mount();
  aim.mount();
  targetPaint.mountTargetPaint();
  anchorPaint.mount();
  anchorControls.mount();
  pageGeometry.mount();
  pageMapDialog.mount(chromeRoot);
  asks.mount();
  app.mountAnnotations();
  app.margin.mount();
  app.mountThread();
  app.mountRead();
  threadListController.mountThreadList(panelIsOpen);
  wireThreadLanding(threadsBox);
  drawers.mountDrawers();
  threadPanelController.mountThreadPanel();
  layout.mountLayoutObservers();
  goToSequence.mountGoToSequence();
  mountShortcutBar({
    setGoToSequence: goToSequence.setGoToSequence,
    setReact: reactions.setReact,
  });
  mountKeyboard({
    goToSequenceActive: goToSequence.goToSequenceActive,
    setGoToSequence: goToSequence.setGoToSequence,
    reactArmed: reactions.isReactArmed,
    setReact: reactions.setReact,
  });
  declareLeavesKeys();
  watchDisclosures(document);
  mountRepaint({
    reflectFirstScopes,
    paintStandingContent: standing.paintStandingContent,
    syncLayout: layout.syncLayout,
    pageShifted: pageGeometry.pageShifted,
    paintStandingGeometry: standing.paintStandingGeometry,
  });
} else {
  // An interactive export attaches no chrome, so its standing is only what a widget's
  // own box shows: an options group's addition field paints there as it does live.
  mountRepaint({ paintStandingGeometry: inputs.paintInputs });
}

const replayReady = passiveSample
  ? import("./runtime/interaction-gallery-frame.js").then(({ mountReplay }) =>
      mountReplay({
        toggleBtn,
        panelIsOpen,
        setPanel: threadPanelController.setPanel,
        detachComposer: selectionComposer.detachComposer,
        fabInput,
        fabFrameAt: () => responseSurface.fabFrameAt(),
        openComposer: selectionComposer.openComposer,
        closePreview: app.margin.closePreview,
        openInlineThread: app.margin.openInlineThread,
        threadTransitionOrigin: app.margin.threadTransitionOrigin,
        currentDrawer,
        setOpenDrawer: drawers.setOpenDrawer,
      }),
    )
  : Promise.resolve();

const initialStateRead = app.beginRead();
let interactionGalleryModule;
let interactionGalleryLoading;
let failedInteractionGallery;
async function syncInteractionGallery() {
  const gallery = document.querySelector("[data-interaction-gallery]");
  if (gallery && gallery === failedInteractionGallery) return;
  try {
    if (!gallery && !interactionGalleryModule) return;
    if (!interactionGalleryModule) {
      interactionGalleryLoading ??= import("./runtime/interaction-gallery.js");
      interactionGalleryModule = await interactionGalleryLoading;
    }
    interactionGalleryModule?.installInteractionGallery();
  } catch (error) {
    failedInteractionGallery = gallery;
    if (!interactionGalleryModule) interactionGalleryLoading = null;
    reportPageError(`interaction gallery failed to start: ${error?.message ?? error}`);
  }
}
if (!offlineInteractive) {
  watchProjection(document.body, () => void syncInteractionGallery());
  document.addEventListener(PAGE_INTERFACE, (event) =>
    event.detail.present(syncInteractionGallery()),
  );
}

if (!passiveSample && !offlineInteractive) {
  restoreUserView({
    commentsEdge: layout.commentsEdge,
    drawersEdge: drawers.drawersEdge,
    restoreAuxiliarySurface: auxiliarySurfaces.restore,
    setDesignMode: designMode.setActive,
  });
  // The page has just arrived, so nothing holds focus and the first Tab starts at the
  // skip link. Not the reading landing: a user who has read nothing has no position
  // for the browser to carry on from.
  releaseFocus();
}
mountHistory({
  followFragment: anchorTravel.followFragment,
  returnToFragment: anchorTravel.returnToFragment,
});
const landFragment = version.aimArrival();
const { landArrival, savedView } = offlineInteractive
  ? { landArrival: () => {}, savedView: null }
  : version.installArrival();
const savedComposer = offlineInteractive ? null : selectionComposer.pendingComposer();

async function presentPage() {
  if (document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented)) return;
  await whenApplicationPresented();
  if (document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented)) return;
  setAnchoringReady(true);
  try {
    const draftOpened =
      !offlineInteractive && selectionComposer.openDraft(savedComposer);
    await app.presentThread();
    // Anchoring changes where thread chrome is painted. That final paint is part
    // of initial presentation too: opening interaction before it commits can expose a
    // malformed page that the unanchored provisional pass could not yet inspect.
    await whenApplicationPresented();
    if (draftOpened) {
      await responseSurface.fabPositioned();
      paintKeys();
    }
  } catch (error) {
    setAnchoringReady(false);
    throw error;
  }
  markPagePresented();
  // Optional author context begins after the presented frame. It neither imports
  // checks nor takes geometry on the path that gives the reader the page.
  if (!offlineInteractive && !passiveSample)
    nextFrame(() =>
      setTimeout(() => {
        void import("./runtime/user-view.js")
          .then(({ observeUserView }) => observeUserView())
          .catch(() => {});
      }, 0),
    );
  void whenArrived().then(landFragment);
  anchorControls.publishVisualActions();
  if (offlineInteractive) {
    landFragment();
    document.dispatchEvent(new Event(PRESENTATION));
    return;
  }
  responseSurface.updateFab();
  auxiliarySurfaces.present();
  presentLeaves();
  paintKeys();
  void syncInteractionGallery();
  paintVersionApproval();
  repaint();
  layoutMarginRows();
  landFragment();
  await landArrival();
  if (savedView && savedView.revision < runtime.currentRevision)
    notice(`Updated to ${runtime.currentLabel}`, { background: true });
  document.dispatchEvent(new Event(PRESENTATION));
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
      : loadIcon().catch((error) => console.error(error)),
    replayReady,
  ]);
  if (!upgraded) return;
  if (!offlineInteractive) {
    // Authored residents are read from the upgraded document (content-layout.js).
    openResidency({ rail: true, onRead: syncMarginResidency });
    layout.syncLayout();
    asks.buildBulkAnswers();
    asks.syncAsks();
  }
  await settlePageInterface();
  landFragment();
  document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.upgraded, "1");
  app.startFeed(presentPage, initialStateRead);
}

startPage().catch((error) => {
  const reason = `page failed to start: ${error?.message ?? error}`;
  window.dispatchEvent(new CustomEvent("lf-startup-failed", { detail: { reason } }));
  reportPageError(reason);
  renderStatus(error);
});
