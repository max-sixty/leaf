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
  createTargetSelection,
  selectionLayer,
  selectionSearch,
} from "./runtime/composing/targets.js";
import { createStandingItem } from "./runtime/composing/standing.js";
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
  panelIsOpen,
} from "./runtime/conversation/panel-elements.js";
import { createLivingMargin } from "./runtime/living-margin.js";
import { createPageMap } from "./runtime/page-map.js";
import { createAskView } from "./runtime/asks/view.js";
import { askActionLayer, ASK_CONTROL } from "./runtime/asks/view-elements.js";
import { createDesignController, inspectEl, legendRoot } from "./runtime/design.js";
import { createChromeLayout } from "./runtime/chrome-layout.js";
import { createPanelWorkspace, PANEL_KEY } from "./runtime/panel-workspace.js";
import {
  createTrays,
  asksPanel,
  currentTray,
  othersBtn,
  othersPanel,
  reserveListClearance,
} from "./runtime/trays.js";
import { createWorkspaceNavigation } from "./runtime/workspace.js";
import { restoreArrangements } from "./runtime/arrangements.js";
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
import { createAddress, addressLayer } from "./runtime/keyboard/address.js";
import { createPageKeys } from "./runtime/keyboard/page.js";
import { mountKeyboard } from "./runtime/keyboard/controller.js";
import { registerPageScopes } from "./runtime/keyboard/register.js";
import { shortcutReferenceDialog } from "./runtime/keyboard/reference.js";
import {
  bottomChromeBoxes,
  less,
  mountShortcutBar,
  REFERENCE,
  renderLine,
  shortcutBarEl,
  walkPositionBoxes,
  walkPositionEl,
} from "./runtime/keyboard/shortcut-bar.js";
import { activeRowLabel, availableCommands } from "./runtime/keyboard/dispatch.js";
import { focused, paintKeys, reflectFirstScopes } from "./runtime/keyboard/scopes.js";
import { watchDisclosures } from "./runtime/keyboard/disclosure.js";
import { createStanding } from "./runtime/standing.js";
import { mountRepaint, repaint, repaintPage } from "./runtime/repaint.js";
import { layoutMarginRows } from "./runtime/margin-layout.js";
import {
  placeThreadEdge,
  seenScroller,
  glideTo,
  stopGlide,
  stepThread,
} from "./runtime/navigation.js";
import { focusDestination, letGo } from "./runtime/focus.js";
import { announce, liveEl, notice } from "./runtime/notifications.js";
import { mediaViewer } from "./runtime/media.js";
import { offer } from "./runtime/widget-elements.js";
import { FOCUSABLE } from "./runtime/reach.js";

let app;
let panelWorkspace;
let trays;
let layout;
let landing;
let pageMap;
let asks;
let panelComposer;
let selectionComposer;
let responseSurface;
let drawing;
let aim;
let targets;
let reactions;
let pageGeometry;
let address;
let pageKeys;

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
const design = createDesignController({
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
  drawingIsOn: () => drawing.isDrawing(),
  design,
});
pageGeometry = createPageGeometry({
  refreshAnchorHover: anchorPaint.refreshHover,
  aim: { isOn: aim.aimIsOn, target: aim.aimedTarget },
  pointer: pointerAt,
  design,
  targetPaint: targetPaintCaps,
  shiftDrawings: drawingPaint.shifted,
  queueLegend: design.queueLegend,
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
  setPanel: (...args) => panelWorkspace.setPanel(...args),
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
});

const version = createVersionController({
  designIsOn: design.isOn,
  paintLegend: design.paintLegend,
  midComposition: () => app.midComposition(),
  readAndApply: (...args) => app.readAndApply(...args),
  banner,
  stateSignoff: (next) => stateSignoff(next, layout.syncLayout),
  landedAt: (...args) => asks.landedAt(...args),
  setLanded: (...args) => asks.setLanded(...args),
  resetAuthoredPage: (...args) => app.resetAuthoredPage(...args),
  readableDestination: anchorTravel.readableDestination,
  scrollToElement: anchorTravel.scrollToElement,
});

const inputs = createCompositionInputs({
  uploadMedia,
  inputAddress: () => ({
    box: pageKeys.commentBox(),
    label: activeRowLabel(pageKeys.commentRows()),
  }),
});

app = mountApplication({
  createEngagement,
  isSelecting: () => targets.isSelecting(),
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
  landInConversation: (...args) => landing.landInConversation(...args),
  showThread: (...args) => landing.showThread(...args),
  setPanel: (...args) => panelWorkspace.setPanel(...args),
  panelIsOpen,
  panelCovers: () => layout.panelCovers(),
  onConversationChanged: repaint,
  retainPanelLanding,
  retainConversationFocus,
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
  createLivingMargin,
  margin: {
    designIsOn: design.isOn,
    comparisonBase: version.comparisonBase,
    comparisonChanges: version.comparisonChanges,
    inlineComparison: version.inlineComparison,
    toggleInlineComparison: version.toggleInlineComparison,
    leavePageMap: (...args) => pageMap.leavePageMap(...args),
    openPageMap: (...args) => pageMap.openPageMap(...args),
    pageMapContextContains: (...args) => pageMap.pageMapContextContains(...args),
    renderPageMap: (...args) => pageMap.renderPageMap(...args),
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
    paintApproval,
    renderStatus,
    renderVersions: version.renderVersions,
    stateSignoff: (next) => stateSignoff(next, layout.syncLayout),
    renderOthers,
  },
  feed: {
    prepareActivation: (state) => version.prepareActivation(state, layout.syncLayout),
    notifyDataSubscribers,
    renderStatus,
  },
});

pageMap = createPageMap({
  activeInMargin: app.margin.pageMapActive,
  activateItem: app.margin.activateMapItem,
  faceFor: app.margin.faceForMap,
  focusFallback: app.margin.focusMapControl,
});

// Ask view is constructed below by its owner factory; all accesses above are inert closures.
asks = createAskView({
  readingBlock: version.readingBlock,
  focusForNavigation: app.margin.focusForNavigation,
  presentedControl: app.margin.presentedControl,
  setPanel: (...args) => panelWorkspace.setPanel(...args),
  showTray: (...args) => trays.showTray(...args),
  trayCovers: () => trays.traysEdge.over.matches,
  readableDestination: anchorTravel.readableDestination,
  scrollToElement: anchorTravel.scrollToElement,
  refreshConversation: () => app.refreshConversation(),
  placeBulkAnswer: (button) => versionBtn.before(button),
  availableCommands,
  announce,
  repaint,
});

const standingItem = createStandingItem({
  isAskControl: (node) => node?.matches?.(ASK_CONTROL),
  askPlace: asks.askPlace,
  standingIn: asks.standingIn,
});

panelComposer = createPanelComposer({
  designIsOn: design.isOn,
  wireInput: inputs.wireInput,
  createPageComment: app.createPageComment,
  showThread: landing.showThread,
  setPanel: (...args) => panelWorkspace.setPanel(...args),
  paintDrawings: () => drawingPaint.paint(allThreads()),
});
selectionComposer = createSelectionComposer({
  setReact: (...args) => reactions.setReact(...args),
  designIsOn: design.isOn,
  marginOpenInlineThread: app.margin.openInlineThread,
  threadTransitionOrigin: app.margin.threadTransitionOrigin,
  anchorStands: (...args) => responseSurface.anchorStands(...args),
  anchorTargetAt: (...args) => responseSurface.anchorTargetAt(...args),
  bringForward: (...args) => responseSurface.bringForward(...args),
  fabAnchorAt: (...args) => responseSurface.fabAnchorAt(...args),
  holdFabLeft: (...args) => responseSurface.holdFabLeft(...args),
  refreshFab: (...args) => responseSurface.refreshFab(...args),
  showFab: (...args) => responseSurface.showFab(...args),
  goAddress: (...args) => address.goAddress(...args),
  createComment: app.createComment,
  focusSurface,
  showThread: landing.showThread,
  refreshConversation: app.refreshConversation,
  wireInput: inputs.wireInput,
});
responseSurface = createResponseSurface({
  markAt: anchorPaint.markAt,
  scrollToElement: anchorTravel.scrollToElement,
  visualActionAnchor: anchorControls.visualActionAnchor,
  hideComposer: selectionComposer.hideComposer,
  openComposer: selectionComposer.openComposer,
  resetResponseOptions: selectionComposer.resetResponseOptions,
  responseOptionsAvailable: selectionComposer.responseOptionsAvailable,
  setResponseOptions: selectionComposer.setResponseOptions,
  syncResponseOptions: selectionComposer.syncResponseOptions,
  designIsOn: design.isOn,
  designTarget: design.target,
  openOnDesign: design.open,
  isReactArmed: () => reactions.isReactArmed(),
  reactionContextContains: (...args) => reactions.reactionContextContains(...args),
  reactionTokens,
  setReact: (...args) => reactions.setReact(...args),
  banner,
  bottomChromeBoxes,
  less: (...args) => less(...args),
  closeVersionMenu: version.closeVersionMenu,
  versionMenuIsOpen: () => versionMenu.matches(":popover-open"),
  openPageThread: app.margin.openPageThread,
  isDrawing: () => drawing.isDrawing(),
  refreshConversation: app.refreshConversation,
});
reactions = createReactionController({
  marginElementChoices: app.margin.marginElementChoices,
  marginElementContextContains: app.margin.marginElementContextContains,
  foldMarginElementOptions: app.margin.foldMarginElementOptions,
  openMarginElementOptions: app.margin.openMarginElementOptions,
  unfoldedMarginElements: app.margin.unfoldedMarginElements,
  designIsOn: design.isOn,
  hideComposer: selectionComposer.hideComposer,
  syncResponseOptions: selectionComposer.syncResponseOptions,
  fabAnchorAt: responseSurface.fabAnchorAt,
  fabReturnTo: responseSurface.fabReturnTo,
  fabTargetAt: responseSurface.fabTargetAt,
  hasPageSelectionTarget: responseSurface.hasPageSelectionTarget,
  showFab: responseSurface.showFab,
  visualActionAnchor: anchorControls.visualActionAnchor,
  standingConversation,
  standingItem,
});
targets = createTargetSelection({
  scrollToRange: anchorTravel.scrollToRange,
  banner,
  bottomChromeBoxes,
  shortcutBarEl,
  walkPositionBoxes,
  walkPositionEl,
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
  setDesign: design.set,
  stopSelecting: targets.stopSelecting,
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
    walkPositionEl,
    chromeRoot,
  },
  foldBannerRow,
  scheduleThreadPreviewPosition: app.margin.scheduleThreadPreviewPosition,
  bottomChromeBoxes,
  reserveListClearance,
  restateTrayEdge: () => trays.traysEdge.state(),
  syncReactLayout: reactions.syncReactLayout,
  refreshFab: responseSurface.refreshFab,
  dockSeats: anchorControls.dockSeats,
  pageShifted: pageGeometry.pageShifted,
  layoutMarginRows,
  repaint,
  repaintPage,
});
panelWorkspace = createPanelWorkspace({
  layout,
  elements: { panel, toggleBtn },
  hideTray: ({ remember }) => {
    if (currentTray()) trays.showTray(null, { remember });
  },
  activeInlineThread: app.margin.activeInlineThread,
  showThread: landing.showThread,
  refreshConversation: app.refreshConversation,
  closeReactionMode: () => reactions.setReact(false),
  closePreview: app.margin.closePreview,
  syncGeneral: panelComposer.syncGeneral,
  refreshHover: anchorPaint.refreshHover,
  rememberOpen: (open) => readerStore.set(PANEL_KEY, open ? "1" : "0"),
  repaint,
});
trays = createTrays({
  landEdge: layout.landEdge,
  moveShell: layout.moveShell,
  panelIsOpen,
  setPanel: panelWorkspace.setPanel,
  syncLayout: layout.syncLayout,
  closePreview: app.margin.closePreview,
  leavesOffered,
  paintLeavesOffer,
  renderAsks: asks.renderAsks,
  renderMargin: app.margin.renderMargin,
});
const workspace = createWorkspaceNavigation({
  setPanel: panelWorkspace.setPanel,
  showTray: trays.showTray,
  openInlineThread: app.margin.openInlineThread,
});
address = createAddress({
  elements: { banner, toggleBtn, shortcutBarEl, walkPositionEl },
  directDestinations: () => [version.CHOOSER, selectionComposer.KEPT_DRAFT],
  workspaceState: workspace.workspaceState,
  restoreWorkspace: workspace.restoreWorkspace,
  setPanel: panelWorkspace.setPanel,
  showTray: trays.showTray,
  scrollToElement: anchorTravel.scrollToElement,
  showThread: landing.showThread,
  leavesOffered,
  othersLinks,
  activateMarginElement: app.margin.activateMarginElement,
  activeInlineThread: app.margin.activeInlineThread,
  marginElementKind: app.margin.marginElementKind,
  visibleMarginElements: app.margin.visibleMarginElements,
  glideTo,
  placeThreadEdge,
  seenScroller,
  stopGlide,
  enterPageMap: pageMap.enterPageMap,
  leavePageMap: pageMap.leavePageMap,
  pageMapIsActive: pageMap.pageMapIsActive,
});
pageKeys = createPageKeys({
  GO: address.GO,
  GOTO: address.GOTO,
  undoable: app.undoable,
  undoLast: app.undoLast,
  unaccountedGesture: app.unaccountedGesture,
  setPanel: panelWorkspace.setPanel,
  showTray: trays.showTray,
  workspaceState: workspace.workspaceState,
  restoreWorkspace: workspace.restoreWorkspace,
  widen: () => widen(app.refreshNarrowing),
  landIn: landing.landIn,
  stepAsk: asks.stepAsk,
  stepThread: (dir) =>
    stepThread(dir, {
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
  commentOnItem: responseSurface.commentOnItem,
  focusFabComment: responseSurface.focusFabComment,
  showFabOptions: responseSurface.showFabOptions,
  updateFab: responseSurface.updateFab,
  hasReactionTarget: reactions.hasReactionTarget,
  REACT: reactions.REACT,
  reactionTokens,
  setReact: reactions.setReact,
  undoSentence: () => undoSentence(app.undoable),
  designIsOn: design.isOn,
  setDesign: design.set,
  PAGE_SEARCH: targets.PAGE_SEARCH,
  REPEAT_PAGE_SEARCH: targets.REPEAT_PAGE_SEARCH,
  SELECT: targets.SELECT,
  startSelecting: targets.startSelecting,
  AIM: aim.AIM,
  isDrawing: drawing.isDrawing,
  setDrawing: drawing.setDrawing,
  generalHint: panelComposer.generalHint,
  CHOOSER: version.CHOOSER,
  NEWEST: version.NEWEST,
  VERSIONS: version.VERSIONS,
  activeInlineThread: app.margin.activeInlineThread,
  keyboardRung: app.margin.keyboardRung,
  standingItem,
  actionRow: asks.actionRow,
});
const standing = createStanding({
  markHere: asks.markHere,
  paintStanding: anchorPaint.paintStanding,
  renderLine,
  paintAddresses: address.paintAddresses,
  paintTargets: targets.paintTargets,
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
  addressLayer,
  askActionLayer,
  selectionLayer,
  selectionSearch,
  targetPaint.visualMarkLayer,
  drawingPaint.layer,
  targetPaint.targetTraceBox,
  targetPaint.aimBox,
  fabBar,
  liveEl,
  mediaViewer,
  shortcutReferenceDialog,
  shortcutBarEl,
  walkPositionEl,
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
  syncLayout: () => layout.syncLayout(),
});
reserveBannerControls();
registerPageScopes(pageKeys.scopes, REFERENCE, pageKeys.typing);
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
pageMap.mount(chromeRoot);
asks.mount();
app.margin.mount();
app.mountConversation();
mountThreadList(panelIsOpen);
wireThreadLanding();
wireThreadCards();
wireNarrowing(app.refreshNarrowing);
trays.mountTrays();
panelWorkspace.mountPanelWorkspace();
layout.mountLayoutObservers();
address.mountAddress();
mountShortcutBar({
  setSequence: address.setSequence,
  setReact: reactions.setReact,
  captureReturnPlace: version.captureReturnPlace,
});
mountKeyboard({
  isSequenceActive: address.isSequenceActive,
  setSequence: address.setSequence,
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
  setPanel: panelWorkspace.setPanel,
  detachComposer: selectionComposer.detachComposer,
  fabInput,
  openComposer: selectionComposer.openComposer,
  closePreview: app.margin.closePreview,
  openInlineThread: app.margin.openInlineThread,
  threadTransitionOrigin: app.margin.threadTransitionOrigin,
  currentTray,
  showTray: trays.showTray,
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
  restoreArrangements({
    commentsEdge: layout.commentsEdge,
    traysEdge: trays.traysEdge,
    setPanel: panelWorkspace.setPanel,
    restoreTrays: trays.restoreTrays,
    setDesign: design.set,
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
  paintApproval();
  repaint();
  layoutMarginRows();
  landArrival();
  if (savedView && savedView.revision < runtime.currentRevision)
    notice(`Updated to ${runtime.currentLabel}`);
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
