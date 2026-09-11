/* Leaf runtime boot and application composition root. */
import chromeSheet from "./runtime/chrome.css" with { type: "css" };
import { containedPage, runtime } from "./runtime/context.js";
import { chromeRoot } from "./runtime/chrome.js";
import { marksSheet } from "./runtime/shadow.js";
import { reportPageError, uploadMedia } from "./runtime/layer-client.js";
import { promoteDeferredModals } from "./runtime/deferred-modals.js";
import { upgradeWidgets } from "./runtime/widget-loader.js";
import { captureAuthoredFacets } from "./runtime/projection/authored.js";
import {
  settlePageInterface,
  PAGE_INTERFACE,
  PAGE_PAINT_ATTRIBUTE,
  PRESENTATION,
} from "./runtime/presentation.js";
import { mountApplication } from "./runtime/application.js";
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
  createTargetChooser,
  targetChooserHintLayer,
  pageSearchSurface,
} from "./runtime/composing/target-chooser.js";
import { createStandingElement } from "./runtime/composing/standing.js";
import {
  createReactionController,
  reactionTokens,
  sendReaction,
  undoSentence,
} from "./runtime/reactions.js";
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
import { allThreads } from "./runtime/conversation/state.js";
import { anchorLabel } from "./runtime/conversation/messages.js";
import {
  createConversationLanding,
  revealConversation,
  retainConversationFocus,
  retainPanelLanding,
  standingConversation,
  wireThreadLanding,
} from "./runtime/conversation/landing.js";
import { createPanelComposer } from "./runtime/conversation/panel.js";
import { focusSurface } from "./runtime/conversation/surfaces.js";
import { focusedThreadOf } from "./runtime/conversation/focus.js";
import { mountThreadList } from "./runtime/conversation/thread-list.js";
import { wireThreadCards } from "./runtime/conversation/thread-card.js";
import {
  revealThread,
  wireNarrowing,
  widen,
} from "./runtime/conversation/narrowing.js";
import {
  panel,
  closeBtn,
  panelFoot,
  threadsBox,
  mountPanelReadingRegion,
  panelWouldCover,
} from "./runtime/conversation/panel-elements.js";
import { createMarginProjection } from "./runtime/margin-projection.js";
import { createPageMapDialog } from "./runtime/page-map-dialog.js";
import { createAskView } from "./runtime/asks/view.js";
import { askActionLayer, ASK_CONTROL } from "./runtime/asks/view-elements.js";
import { createDesignMode, inspectEl, legendRoot } from "./runtime/design.js";
import { createChromeLayout } from "./runtime/chrome-layout.js";
import {
  createPanelVisibility,
  createThreadPanelController,
  THREAD_PANEL_KEY,
} from "./runtime/thread-panel.js";
import {
  createTrays,
  asksPanel,
  currentTray,
  othersBtn,
  othersPanel,
  reserveListClearance,
} from "./runtime/trays.js";
import { createAuxiliaryChromeNavigation } from "./runtime/auxiliary-chrome.js";
import { createAuxiliaryModality } from "./runtime/auxiliary-modality.js";
import { restoreReaderView } from "./runtime/restore-state.js";
import { readerStore } from "./runtime/storage.js";
import { createVersionController, versionBtn, versionMenu } from "./runtime/version.js";
import {
  banner,
  foldBannerRow,
  isSignoffDeclared,
  loadIcon,
  mountBanner,
  paintApproval,
  renderStatus,
  reserveBannerControls,
  stateSignoff,
  toggleBtn,
} from "./runtime/banner.js";
import { overflowMenu, showNews } from "./runtime/banner-shelf.js";
import {
  leavesOffered,
  othersLinks,
  paintLeavesOffer,
  renderOthers,
  declareLeavesKeys,
} from "./runtime/live-leaves.js";
import { acceptData, notifyDataSubscribers } from "./runtime/data.js";
import { replaceClaimState } from "./runtime/updates.js";
import {
  createGoToSequence,
  goToHintLayer,
} from "./runtime/keyboard/go-to-sequence.js";
import { createPageKeys } from "./runtime/keyboard/page.js";
import { mountKeyboard } from "./runtime/keyboard/controller.js";
import { registerPageScopes } from "./runtime/keyboard/register.js";
import { commandReferenceDialog } from "./runtime/keyboard/command-reference.js";
import {
  bottomChromeBoxes,
  closeShortcutShelf,
  mountShortcutBar,
  SHORTCUT_HELP,
  renderShortcutBar,
  shortcutBarEl,
  standingStatusBoxes,
  bottomStatusEl,
} from "./runtime/keyboard/shortcut-bar.js";
import { activeRowLabel } from "./runtime/keyboard/dispatch.js";
import {
  focused,
  keys,
  paintKeys,
  reflectFirstScopes,
} from "./runtime/keyboard/scopes.js";
import { watchDisclosures } from "./runtime/keyboard/disclosure.js";
import { createStanding } from "./runtime/standing.js";
import { mountRepaint, repaint, repaintPage } from "./runtime/repaint.js";
import { layoutMarginRows } from "./runtime/margin-layout.js";
import {
  createNavigation,
  placeThreadEdge,
  glideTo,
  stopGlide,
} from "./runtime/navigation.js";
import { focusDestination, letGo } from "./runtime/focus.js";
import { announce, liveEl, notice } from "./runtime/notifications.js";
import { mediaViewer } from "./runtime/media.js";
import { offer } from "./runtime/widget-elements.js";
import { FOCUSABLE } from "./runtime/reach.js";

let app;
const paintVersionApproval = () =>
  paintApproval(app.pendingApprovals(), app.unansweredAsks());
let threadPanelController;
let trays;
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
let pageKeys;

const panelVisibility = createPanelVisibility();
const { panelIsOpen } = panelVisibility;
const auxiliaryModality = createAuxiliaryModality({ chromeRoot, focusable: FOCUSABLE });
const navigation = createNavigation({
  panelIsOpen,
  coveringAuxiliaryScroller: auxiliaryModality.coveringScroller,
});
const panelModality = auxiliaryModality.registerAuxiliarySurface({
  surface: panel,
  scroller: () => threadsBox,
  covers: navigation.panelCovers,
  focus: () => threadsBox,
  dismiss: () => threadPanelController.setPanel(false),
});

const targetPaintCaps = {
  clearAim: targetPaint.clearAim,
  paintAim: targetPaint.paintAim,
  paintTrace: targetPaint.paintTrace,
  setTargets: targetPaint.setTargets,
  shifted: targetPaint.shifted,
  geometryChanged: targetPaint.geometryChanged,
};
const anchorPaint = createAnchorPaint({
  targetPaint: targetPaintCaps,
  pointer: pointerAt,
  focusedAnchorThreadId: () =>
    focused()?.closest?.(".lf-conversation-thread")?.dataset.thread ??
    focusedThreadOf()?.dataset.id,
  hoveredPanelThreadId: () =>
    threadsBox.querySelector(":scope > .lf-thread:hover")?.dataset.id ?? null,
  panelThreadForId: (id) =>
    id
      ? threadsBox.querySelector(`:scope > .lf-thread[data-id="${CSS.escape(id)}"]`)
      : null,
});
const drawingPaint = createDrawingPaint({
  anchors: anchorPaint,
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
  banner,
  announce,
  repaint,
});
aim = createAim({
  refreshAim: () => pageGeometry.refreshAim(),
  commentOnTarget: (...args) => responseSurface.commentOnTarget(...args),
  standDown: (...args) => responseSurface.standDown(...args),
  drawModeActive: () => drawing.drawModeActive(),
  designMode,
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
  anchors: anchorPaint,
  currentThreads: allThreads,
  refreshConversation: () => app.refreshConversation(),
  announce,
  focused,
});
landing = createConversationLanding({
  setPanel: (...args) => threadPanelController.setPanel(...args),
  scrollToThread: anchorTravel.scrollToThread,
  revealThread: (id) => revealThread(id, app.refreshNarrowing),
});
const anchorControls = createAnchorControls({
  commentOnTarget: (...args) => responseSurface.commentOnTarget(...args),
  openThread: (...args) => app.margin.openPageThread(...args),
  withdrawReaction: (...args) => app.withdraw(...args),
  labelAnchor: anchorLabel,
  invalidateConversation: () => app.refreshConversation(),
  invalidatePageGeometry: pageGeometry.invalidate,
  messageReferenceRoot: panel,
  draftQuote: composerQuote,
  presentedControl: (control) =>
    pageMapDialog?.presentedControl(control) ?? app.margin.presentedControl(control),
  focused,
  keys,
  paintKeys,
});

const version = createVersionController({
  designModeActive: designMode.active,
  paintLegend: designMode.paintLegend,
  midComposition: () => app.midComposition(),
  readAndApply: (...args) => app.readAndApply(...args),
  banner,
  stateSignoff: (next) => stateSignoff(next, layout.syncLayout, paintVersionApproval),
  landedAt: (...args) => asks.landedAt(...args),
  setLanded: (...args) => asks.setLanded(...args),
  resetAuthoredPage: (...args) => app.resetAuthoredPage(...args),
  readableDestination: anchorTravel.readableDestination,
  scrollToElement: anchorTravel.scrollToElement,
});

const inputs = createCompositionInputs({
  uploadMedia,
  inputHint: () => ({
    box: pageKeys.commentBox(),
    label: activeRowLabel(pageKeys.commentRows()),
  }),
});

app = mountApplication({
  createEngagement,
  targetChooserOpen: () => targets.targetChooserOpen(),
  pageComposerDrawing: () => panelComposer.pageComposerDrawing(),
  wireInput: inputs.wireInput,
  anchorPaint,
  anchorControls,
  drawingPaint,
  pageGeometry,
  anchorTravel,
  readConversationDraft: () => ({
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
  landInConversation: (...args) => landing.landInConversation(...args),
  showThread: (...args) => landing.showThread(...args),
  setPanel: (...args) => threadPanelController.setPanel(...args),
  panelIsOpen,
  panelCovers: () => layout.panelCovers(),
  onConversationChanged: repaint,
  retainPanelLanding: (source) => retainPanelLanding(source, panelIsOpen),
  retainConversationFocus: () => retainConversationFocus(panelIsOpen),
  revealReplyEditor: (input, behavior) =>
    revealConversation(
      input.closest(".lf-thread, .lf-conversation-thread, .lf-conversation"),
      input,
      behavior,
    ),
  setThreadCount: (count) => {
    toggleBtn.textContent = count === null ? "Threads" : `Threads (${count})`;
  },
  buildReactSurface: (...args) => reactions.buildReactSurface(...args),
  closeReactionMode: () => reactions.setReact(false),
  sendReaction,
  updateFab: (...args) => responseSurface.updateFab(...args),
  createMarginProjection,
  margin: {
    bottomChromeBoxes,
    designModeActive: designMode.active,
    comparisonBase: version.comparisonBase,
    comparisonChanges: version.comparisonChanges,
    inlineComparison: version.inlineComparison,
    toggleInlineComparison: version.toggleInlineComparison,
    leavePageMap: (...args) => pageMapDialog.leavePageMap(...args),
    openPageMap: (...args) => pageMapDialog.openPageMap(...args),
    pageMapDialogContains: (...args) => pageMapDialog.pageMapDialogContains(...args),
    renderPageMapDialog: (...args) => pageMapDialog.renderPageMapDialog(...args),
    standsWith: (...args) => asks.standsWith(...args),
    revealConversation,
    goToAsk: (...args) => asks.goToAsk(...args),
  },
  state: {
    prepareActivation: (state) => version.prepareActivation(state, layout.syncLayout),
    acceptData,
    notifyDataSubscribers,
    replaceClaimState,
    isSignoffDeclared,
    paintApproval: paintVersionApproval,
    renderStatus,
    renderVersions: version.renderVersions,
    stateSignoff: (next) => stateSignoff(next, layout.syncLayout, paintVersionApproval),
    renderOthers,
  },
  feed: {
    prepareActivation: (state) => version.prepareActivation(state, layout.syncLayout),
    notifyDataSubscribers,
    renderStatus,
  },
});

pageMapDialog = createPageMapDialog({
  activeInMargin: app.margin.pageMapActive,
  activateItem: app.margin.activateMapItem,
  faceFor: app.margin.faceForMap,
  focusFallback: app.margin.focusMapControl,
});

// Ask view is constructed below by its owner factory; all accesses above are inert closures.
asks = createAskView({
  panelIsOpen,
  pendingRequests: app.pendingRequests,
  readingBlock: version.readingBlock,
  focusForNavigation: app.margin.focusForNavigation,
  presentedControl: app.margin.presentedControl,
  setPanel: (...args) => threadPanelController.setPanel(...args),
  setOpenTray: (...args) => trays.setOpenTray(...args),
  trayCovers: () => trays.traysEdge.over.matches,
  readableDestination: anchorTravel.readableDestination,
  scrollToElement: anchorTravel.scrollToElement,
  refreshConversation: () => app.refreshConversation(),
  placeBulkAnswer: (button) => versionBtn.before(button),
  announce,
  repaint,
});

const standingElement = createStandingElement({
  isAskControl: (node) => node?.matches?.(ASK_CONTROL),
  askPlace: asks.askPlace,
  standingIn: asks.standingIn,
});

panelComposer = createPanelComposer({
  designModeActive: designMode.active,
  wireInput: inputs.wireInput,
  createPageComment: app.createPageComment,
  showThread: landing.showThread,
  setPanel: (...args) => threadPanelController.setPanel(...args),
  paintDrawings: () => drawingPaint.paint(allThreads()),
});
selectionComposer = createSelectionComposer({
  panelIsOpen,
  setReact: (...args) => reactions.setReact(...args),
  designModeActive: designMode.active,
  marginOpenInlineThread: app.margin.openInlineThread,
  threadTransitionOrigin: app.margin.threadTransitionOrigin,
  anchorStands: (...args) => responseSurface.anchorStands(...args),
  anchorTargetAt: (...args) => responseSurface.anchorTargetAt(...args),
  bringForward: (...args) => responseSurface.bringForward(...args),
  fabAnchorAt: (...args) => responseSurface.fabAnchorAt(...args),
  fabPositioned: (...args) => responseSurface.fabPositioned(...args),
  beginFabFocus: (...args) => responseSurface.beginFabFocus(...args),
  endFabFocus: (...args) => responseSurface.endFabFocus(...args),
  refreshFab: (...args) => responseSurface.refreshFab(...args),
  showFab: (...args) => responseSurface.showFab(...args),
  formatGoToAddress: (...args) => goToSequence.formatGoToAddress(...args),
  createComment: app.createComment,
  focusSurface,
  showThread: landing.showThread,
  refreshConversation: app.refreshConversation,
  wireInput: inputs.wireInput,
});
responseSurface = createResponseSurface({
  panelCovers: navigation.panelCovers,
  markAt: anchorPaint.markAt,
  scrollToElement: anchorTravel.scrollToElement,
  visualActionAnchor: anchorControls.visualActionAnchor,
  hideComposer: selectionComposer.hideComposer,
  openComposer: selectionComposer.openComposer,
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
  banner,
  bottomChromeBoxes,
  closeShortcutShelf: (...args) => closeShortcutShelf(...args),
  closeVersionMenu: version.closeVersionMenu,
  versionMenuIsOpen: () => versionMenu.matches(":popover-open"),
  openPageThread: app.margin.openPageThread,
  drawModeActive: () => drawing.drawModeActive(),
  refreshConversation: app.refreshConversation,
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
  visualActionAnchor: anchorControls.visualActionAnchor,
  standingConversation,
  standingElement,
});
targets = createTargetChooser({
  scrollToRange: anchorTravel.scrollToRange,
  banner,
  bottomChromeBoxes,
  shortcutBarEl,
  standingStatusBoxes,
  commentOnTarget: responseSurface.commentOnTarget,
  updateFab: responseSurface.updateFab,
  fabAnchorAt: responseSurface.fabAnchorAt,
});
drawing = createDrawingController({
  anchors: { aimTargetAt, resolveAnchor, pendingAt: anchorPaint.pendingAt },
  pageGeometry: { refreshAim: pageGeometry.refreshAim },
  pointer: pointerAt,
  visibleTargets: targets.visibleTargets,
  pageDrawing: panelComposer.pageComposerDrawing,
  composerDraft: () => ({
    open: composerOpen,
    anchor: pendingAnchor,
    drawing: pendingDrawing,
  }),
  openAnchoredDrawing: (anchor, drawing) =>
    selectionComposer.openComposer(anchor, "", { carry: true, drawing }),
  openPageDrawing: panelComposer.openPageDrawing,
  setDesignMode: designMode.setActive,
  closeTargetChooser: targets.closeTargetChooser,
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
    chromeRoot,
  },
  foldBannerRow,
  scheduleThreadPreviewPosition: app.margin.scheduleThreadPreviewPosition,
  bottomChromeBoxes,
  reserveListClearance,
  restateTrayEdge: () => trays.traysEdge.state(),
  syncAuxiliarySurfaces: auxiliaryModality.sync,
  syncReactLayout: reactions.syncReactLayout,
  refreshFab: responseSurface.refreshFab,
  dockSeats: anchorControls.dockSeats,
  pageShifted: pageGeometry.pageShifted,
  layoutMarginRows,
  repaint,
  repaintPage,
});
threadPanelController = createThreadPanelController({
  visibility: panelVisibility,
  layout,
  elements: { panel, toggleBtn },
  hideTray: ({ remember }) => {
    if (currentTray()) trays.setOpenTray(null, { remember });
  },
  activeInlineThread: app.margin.activeInlineThread,
  showThread: landing.showThread,
  refreshConversation: app.refreshConversation,
  closeReactionMode: () => reactions.setReact(false),
  closePreview: app.margin.closePreview,
  syncGeneral: panelComposer.syncGeneral,
  refreshHover: anchorPaint.refreshHover,
  rememberOpen: (open) => readerStore.set(THREAD_PANEL_KEY, open ? "1" : "0"),
  modality: panelModality,
  repaint,
});
trays = createTrays({
  landEdge: layout.landEdge,
  moveContentFrame: layout.moveContentFrame,
  panelIsOpen,
  setPanel: threadPanelController.setPanel,
  syncLayout: layout.syncLayout,
  closePreview: app.margin.closePreview,
  leavesOffered,
  paintLeavesOffer,
  renderAsks: asks.renderAsks,
  renderMargin: app.margin.renderMargin,
  registerAuxiliarySurface: auxiliaryModality.registerAuxiliarySurface,
});
const auxiliaryChrome = createAuxiliaryChromeNavigation({
  panelIsOpen,
  setPanel: threadPanelController.setPanel,
  setOpenTray: trays.setOpenTray,
  openInlineThread: app.margin.openInlineThread,
});
goToSequence = createGoToSequence({
  panelIsOpen,
  panelCovers: navigation.panelCovers,
  elements: { banner, toggleBtn, shortcutBarEl },
  standingStatusBoxes,
  directDestinations: () => [version.CHOOSER, selectionComposer.KEPT_DRAFT],
  captureAuxiliaryChromeState: auxiliaryChrome.captureAuxiliaryChromeState,
  restoreAuxiliaryChromeState: auxiliaryChrome.restoreAuxiliaryChromeState,
  setPanel: threadPanelController.setPanel,
  setOpenTray: trays.setOpenTray,
  scrollToElement: anchorTravel.scrollToElement,
  showThread: landing.showThread,
  leavesOffered,
  othersLinks,
  activateMarginEntry: app.margin.activateMarginEntry,
  activeInlineThread: app.margin.activeInlineThread,
  marginEntryKind: app.margin.marginEntryKind,
  visibleMarginEntries: app.margin.visibleMarginEntries,
  glideTo,
  placeThreadEdge,
  seenScroller: navigation.seenScroller,
  stopGlide,
  coveringAuxiliarySurface: auxiliaryModality.coveringSurface,
  enterPageMap: pageMapDialog.enterPageMap,
  leavePageMap: pageMapDialog.leavePageMap,
  pageMapIsActive: pageMapDialog.pageMapIsActive,
});
pageKeys = createPageKeys({
  panelIsOpen,
  coveringAuxiliarySurface: auxiliaryModality.coveringSurface,
  stepReading: navigation.stepReading,
  openAsks: app.openAsks,
  GO_TO_SCOPE: goToSequence.GO_TO_SCOPE,
  OPEN_GO_TO: goToSequence.OPEN_GO_TO,
  undoable: app.undoable,
  undoLast: app.undoLast,
  unaccountedGesture: app.unaccountedGesture,
  setPanel: threadPanelController.setPanel,
  setOpenTray: trays.setOpenTray,
  captureAuxiliaryChromeState: auxiliaryChrome.captureAuxiliaryChromeState,
  restoreAuxiliaryChromeState: auxiliaryChrome.restoreAuxiliaryChromeState,
  widen: () => widen(app.refreshNarrowing),
  landIn: landing.landIn,
  stepAsk: asks.stepAsk,
  stepThread: (dir) =>
    navigation.stepThread(dir, {
      openPageThread: app.margin.openPageThread,
      scrollToThread: anchorTravel.scrollToThread,
      activeInlineThread: app.margin.activeInlineThread,
    }),
  composerHolds: selectionComposer.composerHolds,
  focusedResponseOption: selectionComposer.focusedResponseOption,
  responseOptionsAreOpen: selectionComposer.responseOptionsAreOpen,
  responseReactionButtons: selectionComposer.responseReactionButtons,
  setResponseOptions: selectionComposer.setResponseOptions,
  stepResponseOptions: selectionComposer.stepResponseOptions,
  dismissFab: responseSurface.dismissFab,
  fabAnchorAt: responseSurface.fabAnchorAt,
  fabOptionsAvailable: responseSurface.fabOptionsAvailable,
  commentOnAddressable: responseSurface.commentOnAddressable,
  focusFabComment: responseSurface.focusFabComment,
  showFabOptions: responseSurface.showFabOptions,
  updateFab: responseSurface.updateFab,
  hasReactionTarget: reactions.hasReactionTarget,
  REACT: reactions.REACT,
  reactionTokens,
  setReact: reactions.setReact,
  undoSentence: () => undoSentence(app.undoable),
  designModeActive: designMode.active,
  setDesignMode: designMode.setActive,
  PAGE_SEARCH: targets.PAGE_SEARCH,
  REPEAT_PAGE_SEARCH: targets.REPEAT_PAGE_SEARCH,
  TARGET_CHOOSER_SCOPE: targets.TARGET_CHOOSER_SCOPE,
  PAGE_SEARCH_SCOPE: targets.PAGE_SEARCH_SCOPE,
  openTargetChooser: targets.openTargetChooser,
  AIM: aim.AIM,
  drawModeActive: drawing.drawModeActive,
  setDrawMode: drawing.setDrawMode,
  generalHint: panelComposer.generalHint,
  CHOOSER: version.CHOOSER,
  NEWEST: version.NEWEST,
  VERSIONS: version.VERSIONS,
  activeInlineThread: app.margin.activeInlineThread,
  keyboardRung: app.margin.keyboardRung,
  standingElement,
  actionRow: asks.actionRow,
});
const standing = createStanding({
  markHere: asks.markHere,
  paintStanding: anchorPaint.paintStanding,
  renderShortcutBar: () => renderShortcutBar(goToSequence.goToStatus),
  paintGoToHints: goToSequence.paintGoToHints,
  paintTargetChooserHints: targets.paintTargetChooserHints,
  paintCoreControls: pageKeys.paintCoreControls,
  paintInputs: inputs.paintInputs,
});

const skipToChrome = offer("button", "lf-skip", "Skip to Leaf controls");
skipToChrome.onclick = () => {
  for (const control of banner.querySelectorAll(FOCUSABLE)) {
    control.focus({ preventScroll: true });
    if (control.matches(":focus")) return;
  }
  focusDestination(banner);
};

document.adoptedStyleSheets = [chromeSheet, marksSheet];
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
  targetChooserHintLayer,
  pageSearchSurface,
  targetPaint.visualMarkLayer,
  drawingPaint.layer,
  targetPaint.targetTraceBox,
  targetPaint.aimBox,
  fabBar,
  liveEl,
  mediaViewer,
  commandReferenceDialog,
  auxiliaryModality.scrim,
  bottomStatusEl,
  shortcutBarEl,
  inspectEl,
);
document.body.prepend(skipToChrome);
document.body.append(chromeRoot);
mountPanelReadingRegion();
version.mount();
mountBanner({
  approveVersion: () =>
    app.post({
      kind: "done",
      revision: runtime.currentRevision,
      version: runtime.currentStamp,
      text: "Looks good",
    }),
  paintApproval: paintVersionApproval,
});
reserveBannerControls();
registerPageScopes(pageKeys.scopes, SHORTCUT_HELP, pageKeys.typing, auxiliaryModality);
auxiliaryModality.mount();
panelComposer.mount();
selectionComposer.mount();
responseSurface.mount();
reactions.mount();
targets.mount();
drawing.mount();
aim.mount();
targetPaint.mountTargetPaint();
anchorPaint.mount();
anchorControls.mount();
anchorTravel.mount();
pageGeometry.mount();
pageMapDialog.mount(chromeRoot);
asks.mount();
app.margin.mount();
app.mountConversation();
mountThreadList(panelIsOpen);
wireThreadLanding();
wireThreadCards();
wireNarrowing(app.refreshNarrowing);
trays.mountTrays();
threadPanelController.mountThreadPanel();
layout.mountLayoutObservers();
goToSequence.mountGoToSequence();
mountShortcutBar({
  setGoToSequence: goToSequence.setGoToSequence,
  setReact: reactions.setReact,
  captureReturnPlace: version.captureReturnPlace,
});
mountKeyboard({
  goToSequenceActive: goToSequence.goToSequenceActive,
  setGoToSequence: goToSequence.setGoToSequence,
  REACT: reactions.REACT,
  setReact: reactions.setReact,
  captureReturnPlace: version.captureReturnPlace,
});
declareLeavesKeys();
pageKeys.declareFindBoxKeys();
pageKeys.declareResponseOptionKeys();
watchDisclosures(document);
mountRepaint({
  reflectFirstScopes,
  paintStandingContent: standing.paintStandingContent,
  syncLayout: layout.syncLayout,
  pageShifted: pageGeometry.pageShifted,
  paintStandingGeometry: standing.paintStandingGeometry,
});

window.leafInteractionGalleryFrame?.mount({
  toggleBtn,
  panelIsOpen,
  setPanel: threadPanelController.setPanel,
  detachComposer: selectionComposer.detachComposer,
  fabInput,
  openComposer: selectionComposer.openComposer,
  closePreview: app.margin.closePreview,
  openInlineThread: app.margin.openInlineThread,
  threadTransitionOrigin: app.margin.threadTransitionOrigin,
  currentTray,
  setOpenTray: trays.setOpenTray,
});

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
document.addEventListener("lf-actions", () => void syncInteractionGallery());
document.addEventListener(PAGE_INTERFACE, (event) =>
  event.detail.pending.push(syncInteractionGallery()),
);

if (!containedPage) {
  restoreReaderView({
    commentsEdge: layout.commentsEdge,
    traysEdge: trays.traysEdge,
    setPanel: threadPanelController.setPanel,
    restoreTrays: trays.restoreTrays,
    setDesignMode: designMode.setActive,
  });
  letGo();
}
const { landArrival, savedView } = version.installArrival();
const savedComposer = selectionComposer.pendingComposer();

function presentPage() {
  if (document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented)) return;
  setAnchoringReady(true);
  try {
    app.refreshConversation();
  } catch (error) {
    setAnchoringReady(false);
    throw error;
  }
  document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.presented, "1");
  responseSurface.updateFab();
  trays.restoreTray();
  showNews(othersBtn, leavesOffered());
  paintKeys();
  document.dispatchEvent(new Event("lf-actions"));
  paintVersionApproval();
  repaint();
  layoutMarginRows();
  landArrival();
  if (savedView && savedView.revision < runtime.currentRevision)
    notice(`Updated to ${runtime.currentLabel}`, { background: true });
  selectionComposer.openDraft(savedComposer);
  promoteDeferredModals();
  document.dispatchEvent(new Event(PRESENTATION));
}

async function startPage() {
  const [upgraded] = await Promise.all([
    upgradeWidgets({
      buildReactionBar: () =>
        reactions.buildReactBar({
          withdrawReaction: app.withdraw,
          postReaction: app.post,
        }),
    }),
    loadIcon().catch((error) => console.error(error)),
  ]);
  if (!upgraded) return;
  layout.syncLayout();
  captureAuthoredFacets();
  asks.buildBulkAnswers();
  asks.syncAsks();
  await settlePageInterface();
  document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.upgraded, "1");
  app.startFeed(presentPage, initialStateRead);
}

startPage().catch((error) => {
  window.dispatchEvent(new Event("lf-startup-failed"));
  reportPageError(`page failed to start: ${error?.message ?? error}`);
  renderStatus(error);
});
