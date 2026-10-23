import {
  KINDS,
  activateContributionControl,
  annotationItems,
  clearContributionControls,
  compareContributions,
  contributionControlKey,
  contributionEntries,
  contributionEntryRecord,
  contributionSource,
  entryControls,
  marginInventory,
  materializeContributionControls,
  presentContributionReceipts,
  presentingContributions,
  registerContribution,
  spokenSubject,
  threadMarks,
  watchContributions
} from "./bundle-contribution-model.js";
import {
  createProjectionPresentation
} from "./bundle-projection~presentation.js";
import {
  HOLDS_WORD,
  HeldNews,
  MessageView,
  PAGE_SCOPE,
  SAYS_IN,
  THREAD,
  ThreadView,
  Transcript,
  allButCommandReference,
  allThreads,
  alreadyShown,
  anchorLabel,
  answeredInWords,
  authoredHolder,
  beginThreadSeats,
  beginWalk,
  blocksOnScreen,
  bringBackSurfaceOf,
  captureDraftEditing,
  capturePlace,
  claimed,
  clearDraft,
  commitThreadSeats,
  completeReadingReturn,
  createReplyView,
  declareSide,
  dismissReplyAt,
  draftContexts,
  draftEditingDestination,
  draftEditingStands,
  drawnThreadId,
  fitsWhole,
  focusThread,
  focusedInView,
  focusedThreadTarget,
  formatDeclaredMarkdown,
  hasLandmark,
  heldOut,
  heldThread,
  heldThreadId,
  holdReplyCompositions,
  holdThreadPlace,
  importWidgets,
  isPageWidgetWorkflow,
  isWorkflowProgress,
  keepRefusedWords,
  listWalkPosition,
  loadDraft,
  loadDraftPayload,
  loadMarkdown,
  loadMessageMarkdown,
  markdownReady,
  messageHolding,
  messageReading,
  messageText,
  mountFirstMessage,
  newsNotice,
  obligationHolding,
  obligationPlace,
  openMessageEditIn,
  openingPassage,
  pageCommand,
  pageReadingBlock,
  pageScope,
  pageScopes,
  pageSelection,
  paintMarkdown,
  passageBlock,
  patchDocument,
  placeNode,
  placeOf,
  placeOffset,
  placePageThreads,
  placedMarkdownTokens,
  preloadWidgets,
  prepareAuthoredMessage,
  prepareDeclaredMarkdown,
  rawOffsetFits,
  readObligations,
  readThreads,
  readingReturn,
  registerWritingDestination,
  reindexPassageOwners,
  rememberPassageParts,
  rememberWriting,
  renderMarginThread,
  renderSeats,
  renderSurfaces,
  replyAvailable,
  replyDestination,
  replyDraftContext,
  restoreDraftEditing,
  restorePlace,
  restoreReplyEditing,
  restrictUserIntent,
  retainThreadSeats,
  retainUserIntent,
  revealHeld,
  saveDraft,
  scrollIntoReadingBand,
  scrollIntoView,
  sendLanding,
  sendMessage,
  settleAcceptedDrafts,
  showHeld,
  showHeldThread,
  strongestWorkflow,
  surfaceFocusTarget,
  tabStore,
  textBlocks,
  threadDraft,
  threadIdNamed,
  threadList,
  threadName,
  threadNamed,
  threadPart,
  threadReading,
  threadReplyInput,
  threadRewrites,
  threadState,
  todoLabel,
  transferDraft,
  watchDraft,
  watchDrafts,
  watchThreadSurfaces,
  wholeThread,
  workflowLabel
} from "./bundle-user-intent.js";
import {
  aborted,
  authoredStates,
  commitWidgetDescriptors,
  descriptorStillMatches,
  failSoft,
  failSoftUnreported,
  once,
  orderChildren,
  patchRetains,
  patchTree,
  placesFailure,
  quoted,
  rememberAuthoredParents,
  reportFailure,
  setChildren,
  stageAuthoredStates,
  stageWidgetDescriptors,
  widgetDescriptor
} from "./bundle-keyboard~disclosure.js";
import {
  scrollBehavior
} from "./bundle-motion.js";
import {
  PAGE_CONTROL_RANK,
  commitPoint,
  livePoint,
  registerPageControl,
  settleResidency,
  visibleTargetParts
} from "./bundle-page-controls.js";
import {
  ADDRESSABLE,
  addressableLabel,
  addressableWord,
  addressedElements,
  anchorForRange,
  anchoringIsReady,
  fragmentTarget,
  resolveAnchor,
  revealAddressed,
  sectionOf,
  targetElement,
  targetPlace,
  targetSegments,
  visualPartLabel,
  widgetWord
} from "./bundle-visual-parts.js";
import {
  initialOrigin,
  restoreInitialSource,
  unmarkedCopy
} from "./bundle-initial-render.js";
import {
  SCROLL_SLACK,
  activityTransitionDue,
  ago,
  chosenSince,
  containingReadingRegionFor,
  effectiveScroller,
  markStateApplied,
  moveScrollerBy,
  observeServerNow,
  observeWorkingGrace,
  onReadingInput,
  pageScroller,
  placeKept,
  reachScrollers,
  readingPosture,
  readingRegionFor,
  readingRegions,
  recentReadingRegion,
  regionsSettled,
  saidNow,
  scrollChainOf,
  scrollChoices,
  scrollLimit,
  scrollersOf,
  settlePageInterface,
  shownRegionBounds,
  stopScroll,
  tickClock,
  unconcealedReadingRegions,
  watchReadingRegionTransitions
} from "./bundle-presence.js";
import {
  DATUM,
  TEXT_BLOCK,
  alignInlineText,
  authored,
  authoredScope,
  closestAcross,
  elementById,
  excerptWords,
  inChrome,
  labelWords,
  leafSurface,
  pageDocument,
  pageParts,
  pageRange,
  pageReadingVersion,
  quoteFrom,
  rangeOf,
  readingFrom,
  selectEnds,
  selectionBackward,
  textNodesUnder,
  wrote
} from "./bundle-passage-facts.js";
import {
  LayerRefused,
  PAGE_PAINT_ATTRIBUTE,
  PRESS,
  PRESSABLE,
  TEXT_ENTRY,
  admitReading,
  admitResponse,
  announce,
  ariaShortcuts,
  bindings,
  buttonCommand,
  claimsEsc,
  clamp,
  clippedContents,
  clippedPlace,
  clipsPastSurfaces,
  closeNativeLayer,
  commandAvailable,
  commandRoutes,
  completeData,
  countTraffic,
  dataHeaders,
  el,
  frameFor,
  growthIsSeen,
  hasArea,
  holdingError,
  intersect,
  keys,
  labelOf,
  landingBand,
  landingInsets,
  layerHeaders,
  layoutChanged,
  layoutWindow,
  live,
  matchesWhen,
  notice,
  offer,
  paintKeys,
  paintKeysWithin,
  placeBox,
  placeHolder,
  pointerAt,
  postEvent,
  presented,
  pruneScopedElements,
  raiseError,
  randomId,
  recordInteraction,
  registry,
  repaint,
  reportCarried,
  reportPageError,
  requestJson,
  responseAction,
  restorePointer,
  reveal,
  rowArrows,
  runtimeRootState,
  sameLayer,
  savedReadingSettled,
  saying,
  seenRect,
  sessionIsActive,
  setRuntimeRootAttribute,
  shadowRootsIn,
  showNativeLayer,
  shownBox,
  shownWindow,
  skipped,
  spell,
  tagsDeclaring,
  union,
  watchOwner,
  watchPendingTraffic,
  watchRoom,
  whenNone,
  whileConnected,
  word
} from "./bundle-page-paint.js";
import {
  PRESSES,
  TEXT_BOX,
  TEXT_FIELD,
  afterScript,
  byRenderedOrder,
  canPlaceFocus,
  closeLayer,
  deepFocus,
  drawn,
  focusDestination,
  focused,
  frameVisibility,
  handBack,
  holdFocus,
  holdRendering,
  inputCount,
  isNativeLayer,
  keeps,
  keepsHidden,
  move,
  nextAnimation,
  nextRender,
  onFrameVisibility,
  onStanding,
  onUserInput,
  openLayer,
  openerOf,
  readCaret,
  readSampleVisibility,
  renderedOrder,
  renderedParent,
  renderedUnder,
  renderingState,
  shadowHost,
  sizeObserver,
  takesLetters,
  typesText,
  under,
  upFrom,
  whenLeft
} from "./bundle-frame-visibility.js";
import {
  LIVE_ROOT,
  PRESENTATION_DOM,
  agentLabel,
  annotationMode,
  applicationPresenter,
  applicationState,
  attachApplicationPresentation,
  attachWidgetPresentation,
  documentChanged,
  layerRoot,
  offlineData,
  offlineInteractive,
  offlineState,
  pageUrl,
  presentDocument,
  projectView,
  queueWidgetUpdate,
  readApplication,
  readPart,
  revisionLabel,
  runtime,
  setPresentationFailureReporter,
  watchPresentation,
  whenApplicationRegionsPresented,
  whenDocumentPresented,
  whenWidgetsPresented
} from "./bundle-semantic-state.js";
import {
  J,
  LitElement,
  PENDING,
  W,
  Z,
  actionForWidget,
  anchorKey,
  bindQueuedWork,
  d,
  discussed,
  editable,
  foldWidgetStates,
  isMessageEvent,
  isThreadEvent,
  moved,
  obligationValue,
  projectionOrigins,
  q,
  reactionsAt,
  render,
  stateCoordinate,
  threadKey,
  tokenChoices,
  turns,
  x
} from "./bundle-queued-work.js";

// runtime/document-identity.js
var servedRevision = (
  /** @type {HTMLMetaElement | null} */
  document.querySelector('meta[name="lf-revision"][data-lf-runtime]')?.content
);
var servedStampMarker = (
  /** @type {HTMLMetaElement | null} */
  document.querySelector('meta[name="lf-version"][data-lf-runtime]')
);
var servedExecutable = (
  /** @type {HTMLMetaElement | null} */
  document.querySelector('meta[name="lf-executable"][data-lf-runtime]')?.content
);
var documentWidgetDigests = (doc) => {
  const stated = doc.querySelector('meta[name="lf-widgets"][data-lf-runtime]')?.content;
  return stated ? JSON.parse(stated) : {};
};
var servedWidgets = documentWidgetDigests(document);
function initializeServedDocument() {
  applicationState.identify(
    servedRevision ? parseInt(servedRevision, 10) : null,
    servedStampMarker ? parseInt(servedStampMarker.content, 10) : null,
    LIVE_ROOT
  );
  servedStampMarker?.remove();
}

// runtime/history.js
var claims = /* @__PURE__ */ new Set();
var places = /* @__PURE__ */ new Map();
function readPlace(focus = deepFocus()) {
  const place = placeOf(focus);
  const selection = getSelection();
  const range = selection.rangeCount ? pageRange(selection) : null;
  const ends = range && [
    [new WeakRef(range.startContainer), range.startOffset],
    [new WeakRef(range.endContainer), range.endOffset]
  ];
  if (ends && selectionBackward(selection, range)) ends.reverse();
  return {
    focus: focus && new WeakRef(focus),
    place: place && new WeakRef(place),
    caret: readCaret(focus),
    ends,
    offset: [scrollX, scrollY]
  };
}
function returnPlace(checkpoint) {
  const focus = checkpoint.focus?.deref();
  const place = checkpoint.place?.deref();
  const { caret } = checkpoint;
  const ends = checkpoint.ends?.map(([ref, offset]) => {
    const node = ref.deref();
    const length = node?.nodeType === 3 ? node.length : node?.childNodes.length;
    return [node, Math.min(offset, length ?? offset)];
  });
  if (focus !== document.body && drawn(focus)) {
    focusDestination(focus, "return", { caret });
    if (caret) return;
  } else if (drawn(place)) focusDestination(place, "return");
  else deepFocus()?.blur();
  const selection = getSelection();
  selection.removeAllRanges();
  if (ends?.every(([node]) => node && drawn(node.nodeType === 1 ? node : upFrom(node)))) {
    selectEnds(...ends);
  }
}
var writing = false;
function write(method, state, url) {
  writing = true;
  try {
    history[method](state, "", url);
  } finally {
    writing = false;
  }
}
function pushEntry(url, state = null) {
  write("pushState", state, url);
}
function replaceEntry(url, state = history.state) {
  write("replaceState", state, url);
}
function prepareEntry() {
  const key = window.navigation?.currentEntry?.key;
  const place = readPlace();
  const offset = place.offset;
  const sourceUrl = window.location.href;
  const sourceState = history.state;
  return (url, state, replace) => {
    if (replace) {
      replaceEntry(url, state);
      return;
    }
    const arrival = [scrollX, scrollY];
    if (window.location.href !== sourceUrl || history.state !== sourceState)
      replaceEntry(sourceUrl, sourceState);
    window.scrollTo({ left: offset[0], top: offset[1], behavior: "instant" });
    pushEntry(url, state);
    window.scrollTo({ left: arrival[0], top: arrival[1], behavior: "instant" });
    if (key) places.set(key, place);
  };
}
function claimTraversals(claim, { signal } = {}) {
  claims.add(claim);
  signal?.addEventListener("abort", () => claims.delete(claim), { once: true });
}
var mounted = false;
function mountHistory({ followFragment, returnToFragment }) {
  if (mounted) return;
  mounted = true;
  window.navigation?.addEventListener("navigate", (event) => {
    if (!event.destination.sameDocument || !event.canIntercept) return;
    const url = new URL(event.destination.url);
    if (event.navigationType !== "replace") {
      const live2 = new Set(window.navigation.entries().map((entry) => entry.key));
      for (const key2 of places.keys()) if (!live2.has(key2)) places.delete(key2);
      const key = window.navigation.currentEntry?.key;
      if (key) places.set(key, readPlace());
    }
    if (event.navigationType === "traverse") {
      const handler2 = claimed2(url) ?? returnToFragment(url);
      const place = places.get(event.destination.key);
      const mayReturn = retainUserIntent({ available: () => !event.signal.aborted });
      event.intercept({
        scroll: "manual",
        focusReset: "manual",
        handler: async () => {
          if (!mayReturn()) return;
          const scrollers = /* @__PURE__ */ new Set([
            pageScroller,
            ...unconcealedReadingRegions().map((region) => region.body)
          ]);
          await stopScroll(scrollers);
          if (!mayReturn()) return;
          let work;
          mayReturn.handoff(() => {
            work = handler2?.();
          });
          await work;
          if (!mayReturn()) return;
          if (!handler2) {
            if (place)
              window.scrollTo({
                left: place.offset[0],
                top: place.offset[1],
                behavior: "instant"
              });
            else event.scroll();
          }
          if (place) returnPlace(place);
        }
      });
      return;
    }
    if (writing || event.formData || !url.hash) return;
    const handler = followFragment(url);
    if (handler) event.intercept({ scroll: "manual", focusReset: "manual", handler });
  });
}
function claimed2(url) {
  for (const claim of claims) {
    const handler = claim(url);
    if (handler) return handler;
  }
  return null;
}

// runtime/page-sheets.js
var APPARATUS = ":not(:where(.lf-chrome, .lf-chrome *, .lf-ui, .lf-ui *))";
var narrowed = /* @__PURE__ */ new WeakSet();
function members(text) {
  const found = [];
  let depth = 0;
  let quote = null;
  let start = 0;
  let pseudo = -1;
  for (let at = 0; at < text.length; at++) {
    const ch = text[at];
    if (quote) {
      if (ch === "\\") at++;
      else if (ch === quote) quote = null;
    } else if (ch === '"' || ch === "'") quote = ch;
    else if (ch === "\\") at++;
    else if (ch === "(" || ch === "[") depth++;
    else if (ch === ")" || ch === "]") depth--;
    else if (depth === 0 && ch === ",") {
      found.push([text.slice(start, at), pseudo < 0 ? -1 : pseudo - start]);
      start = at + 1;
      pseudo = -1;
    } else if (depth === 0 && pseudo < 0 && ch === ":" && text[at + 1] === ":")
      pseudo = at;
  }
  found.push([text.slice(start), pseudo < 0 ? -1 : pseudo - start]);
  return found;
}
function narrow(member, pseudo) {
  const selector = pseudo < 0 ? member.trimEnd() : member.slice(0, pseudo);
  const rest = pseudo < 0 ? "" : member.slice(pseudo);
  return selector + APPARATUS + rest;
}
function narrowRules(rules) {
  for (const rule of rules) {
    if (rule instanceof CSSKeyframesRule || rule instanceof CSSImportRule) continue;
    if (rule instanceof CSSStyleRule) {
      const next = members(rule.selectorText).map(([member, pseudo]) => narrow(member, pseudo)).join(", ");
      if (next !== rule.selectorText) rule.selectorText = next;
    }
    if (rule.cssRules) narrowRules(rule.cssRules);
  }
}
function narrowSheet(sheet2, runtime2) {
  const owner = sheet2.ownerNode;
  if (owner?.hasAttribute?.("data-controls")) return;
  if (sheet2.href && new URL(sheet2.href).origin !== window.origin && !owner?.hasAttribute?.("crossorigin"))
    return;
  if (!narrowed.has(sheet2)) {
    narrowed.add(sheet2);
    if (!runtime2) narrowRules(sheet2.cssRules);
    else
      for (const rule of sheet2.cssRules)
        if (rule instanceof CSSLayerBlockRule && rule.name === "lf-theme")
          narrowRules(rule.cssRules);
  }
  for (const rule of sheet2.cssRules)
    if (rule instanceof CSSImportRule && rule.styleSheet)
      narrowSheet(rule.styleSheet, runtime2);
}
var watching = false;
function keepPageRulesOffLayer() {
  for (const sheet2 of document.styleSheets)
    narrowSheet(
      sheet2,
      /** @type {Element | null} */
      sheet2.ownerNode?.hasAttribute("data-lf-runtime")
    );
  if (watching) return;
  watching = true;
  document.addEventListener(
    "load",
    (event) => {
      if (event.target instanceof Element && event.target.matches('link[rel~="stylesheet" i], style'))
        keepPageRulesOffLayer();
    },
    true
  );
  new MutationObserver(keepPageRulesOffLayer).observe(document.head, {
    childList: true,
    subtree: true,
    characterData: true
  });
}

// runtime/editor-view.js
import {
  Compartment,
  Direction,
  EditorState,
  EditorView,
  StateEffect
} from "/vendor/codemirror.esm.js";
function travel(start, end, low, high, alignment, margin, side) {
  if (alignment === "nearest") {
    if (start < low + margin) {
      const movement = start - low - margin;
      return side > 0 && end > high + movement ? end - high + margin : movement;
    }
    if (end > high - margin) {
      const movement = end - high + margin;
      return side < 0 && start - movement < low ? start - low - margin : movement;
    }
    return 0;
  }
  if (alignment === "center" && end - start <= high - low)
    return (start + end - low - high) / 2;
  return alignment === "start" || alignment === "center" && side < 0 ? start - low - margin : end - high + margin;
}
function caretAt(view, at) {
  const position = view.domAtPos(at);
  const caret = document.createRange();
  caret.setStart(position.node, position.offset);
  caret.collapse(true);
  if (caret.getClientRects().length)
    return { destination: caret, rectangle: caret.getBoundingClientRect() };
  const destination = position.node instanceof Element ? position.node : position.node.parentElement;
  const box = destination.getBoundingClientRect();
  const x2 = view.textDirection === Direction.LTR ? box.left : box.right;
  return {
    destination,
    rectangle: { left: x2, right: x2, top: box.top, bottom: box.bottom }
  };
}
function placeWithinEditor(view, selection, options, head) {
  const rectangle = union(
    selection.empty ? [head] : [head, caretAt(view, selection.anchor).rectangle]
  );
  const margins = { top: 0, bottom: 0, left: 0, right: 0 };
  for (const provider of view.state.facet(EditorView.scrollMargins)) {
    const supplied = provider(view);
    if (supplied)
      for (const edge of Object.keys(margins))
        margins[edge] = Math.max(margins[edge], supplied[edge] ?? 0);
  }
  const port = view.scrollDOM;
  const box = port.getBoundingClientRect();
  const { scaleX, scaleY } = view;
  const left = box.left + port.clientLeft * scaleX;
  const top = box.top + port.clientTop * scaleY;
  const right = left + port.clientWidth * scaleX;
  const bottom = top + port.clientHeight * scaleY;
  const side = selection.head < selection.anchor ? -1 : 1;
  const horizontal = view.textDirection === Direction.RTL ? options.x === "start" ? "end" : options.x === "end" ? "start" : options.x : options.x;
  const xMargin = clamp(options.xMargin, -port.offsetWidth, port.offsetWidth);
  const yMargin = clamp(options.yMargin, -port.offsetHeight, port.offsetHeight);
  const x2 = horizontal === "center" ? (rectangle.left - margins.left + rectangle.right + margins.right - left - right) / 2 : travel(
    rectangle.left - margins.left,
    rectangle.right + margins.right,
    left,
    right,
    horizontal,
    xMargin,
    side
  );
  const y = travel(
    rectangle.top - margins.top,
    rectangle.bottom + margins.bottom,
    top,
    bottom,
    options.y,
    yMargin,
    side
  );
  port.scrollBy({
    left: port.scrollWidth > port.clientWidth ? x2 / scaleX : 0,
    top: port.scrollHeight > port.clientHeight ? y / scaleY : 0,
    behavior: "instant"
  });
}
var navigation = new Compartment();
var reveal2 = EditorView.scrollHandler.of((view, selection, options) => {
  const { destination, rectangle } = caretAt(view, selection.head);
  placeWithinEditor(view, selection, options, rectangle);
  scrollIntoView(destination, { block: "nearest", behavior: "instant" });
  return true;
});
var withNavigation = (state) => navigation.get(state) === void 0 ? state.update({ effects: StateEffect.appendConfig.of(navigation.of(reveal2)) }).state : state;
var LeafEditorView = class extends EditorView {
  constructor(config = {}) {
    super({
      ...config,
      state: withNavigation(config.state ?? EditorState.create(config))
    });
    this.scrollDOM.classList.add("scroll");
    this.contentDOM.addEventListener("focus", () => this.placeSelection());
  }
  setState(state) {
    super.setState(withNavigation(state));
  }
  // Safari reveals a retained inactive contenteditable selection even when native
  // focus prevents scrolling. Detach only this editor's selection before arrival,
  // then place its recorded caret; composed ranges reach closed shadow roots.
  focus() {
    if (!canPlaceFocus()) return;
    const selection = this.#selection();
    if (this.root.activeElement !== this.contentDOM && selection.getComposedRanges({
      shadowRoots: this.root instanceof ShadowRoot ? [this.root] : []
    }).some(
      (range) => this.contentDOM.contains(range.startContainer) || this.contentDOM.contains(range.endContainer)
    ))
      selection.removeAllRanges();
    this.contentDOM.focus({ preventScroll: true });
    this.placeSelection();
  }
  // Write the recorded selection into the focused editor's DOM. A move that keeps focus
  // (`moveBefore`) still collapses the native selection, which the view would otherwise
  // read back as its own.
  placeSelection() {
    if (this.root.activeElement !== this.contentDOM) return;
    const { anchor, head } = this.state.selection.main;
    const from = this.domAtPos(anchor);
    const to = this.domAtPos(head);
    this.#selection().setBaseAndExtent(from.node, from.offset, to.node, to.offset);
  }
  // Firefox and WebKit lack ShadowRoot.getSelection; the document holds theirs.
  #selection() {
    return this.root.getSelection?.() ?? this.dom.ownerDocument.getSelection();
  }
};

// runtime/composing/drawing-schema.js
var drawingSchema = { "type": "object", "properties": { "strokes": { "type": "array", "minItems": 1, "maxItems": 32, "items": { "type": "array", "minItems": 2, "maxItems": 256, "items": { "type": "array", "minItems": 2, "maxItems": 2, "prefixItems": [{ "type": "number", "minimum": -33554432, "maximum": 33554432 }, { "type": "number", "minimum": -33554432, "maximum": 33554432 }], "items": false } } }, "box": { "type": "array", "minItems": 2, "maxItems": 2, "prefixItems": [{ "type": "number", "exclusiveMinimum": 0, "maximum": 33554432 }, { "type": "number", "exclusiveMinimum": 0, "maximum": 33554432 }], "items": false }, "frame": { "type": "object", "properties": { "root": { "type": "string", "maxLength": 128, "pattern": "^[A-Za-z][A-Za-z0-9_.:-]*$" }, "path": { "type": "array", "maxItems": 32, "items": { "type": "object", "properties": { "tag": { "type": "string", "maxLength": 128, "pattern": "^[A-Za-z][A-Za-z0-9_.:-]*$" }, "index": { "type": "integer", "minimum": 0, "maximum": 65535 }, "siblings": { "type": "integer", "minimum": 1, "maximum": 65536 }, "shadow": { "type": "boolean" } }, "required": ["tag", "index", "siblings"], "additionalProperties": false } } }, "required": ["root", "path"], "additionalProperties": false }, "says": { "type": "string", "minLength": 1, "maxLength": 500 }, "viewport": { "type": "array", "minItems": 2, "maxItems": 2, "prefixItems": [{ "type": "number", "exclusiveMinimum": 0, "maximum": 33554432 }, { "type": "number", "exclusiveMinimum": 0, "maximum": 33554432 }], "items": false }, "scheme": { "enum": ["light", "dark"] } }, "required": ["strokes", "box", "viewport", "scheme"], "additionalProperties": false };

// runtime/composing/drawing-record.js
var FIELDS = drawingSchema.properties;
var MAX_DRAWING_STROKES = FIELDS.strokes.maxItems;
var MAX_DRAWING_FRAME_DEPTH = FIELDS.frame.properties.path.maxItems;
var MAX_DRAWING_POINTS = FIELDS.strokes.items.maxItems;
var DRAWING_COORDINATE_LIMIT = FIELDS.strokes.items.items.prefixItems[0].maximum;
var MAX_DRAWING_SAYS_LENGTH = FIELDS.says.maxLength;
function sentDrawing(drawing) {
  const { at, ...sent } = drawing;
  return sent;
}

// runtime/protocol.js
var DRAFT_FORMAT = "leaf-draft/17";

// runtime/composing/text-field.js
import {
  EditorView as EditorView2,
  EditorState as EditorState2,
  StateEffect as StateEffect2,
  Compartment as Compartment2,
  Decoration,
  LanguageSupport,
  ViewPlugin,
  keymap,
  history as history2,
  standardKeymap,
  historyKeymap,
  isolateHistory,
  invertedEffects,
  markdownLanguage,
  insertNewlineContinueMarkup
} from "/vendor/codemirror.esm.js";
var insertNewline = standardKeymap.find(({ key }) => key === "Enter").run;
var sheet = new CSSStyleSheet();
sheet.replaceSync(`
  :host { display: block; cursor: text; }
  /* CodeMirror's provider places its defaults in lf-base. This control owns the
     unlayered editor face: the host supplies type and colour, and these are the
     only internal padding declarations before Markdown's explicit insets below. */
  .cm-editor { font: inherit; color: inherit; background-color: transparent; }
  .cm-editor.cm-focused { outline: none; }
  .cm-scroller { font-family: inherit; line-height: inherit; overflow: visible; }
  .cm-content { padding: 0; caret-color: currentColor; min-height: 1lh; }
  /* An empty field draws no editor until the user arrives in it (#build). This box
     holds the empty line's place, as tall as the editor's line, and takes the focus
     that builds the editor. */
  .lf-field-rest { min-height: 1lh; outline: none; }
  .cm-line { padding: 0; }
  /* The placeholder is a layer under the words, as a textarea's is, never content in
     the line: a widget in an empty line is what the platform would draw the caret
     against. Both layers share one grid cell, inside the host's padding. */
  .lf-field { display: grid; }
  .lf-field > * { grid-area: 1 / 1; min-width: 0; }
  /* An owner moving the field's edges can carry the words from where they stood with
     them, by the host's --lf-field-carry, and cut them to the box it draws growing, by
     --lf-field-cut (theme.css): a transform and a cut that move neither the field nor
     its layout. The field's content box cuts off what the field doesn't hold yet,
     such as a new line and its caret, and keeps the travel from widening the host's
     scrolling. A cut naming none is invalid, which leaves the words uncut. */
  .lf-field { overflow: clip; }
  .lf-field > * {
    translate: var(--lf-field-carry);
    clip-path: inset(var(--lf-field-cut));
  }
  /* The placeholder is one line that never widens the box \u2014 a response bar sizes to the
     words \u2014 and shortens with an ellipsis where the box is narrow, so it reads the same
     height whether it shows the plain words or a keyed hint. */
  .lf-field-placeholder { pointer-events: none; white-space: nowrap;
    contain: inline-size; overflow-x: clip; text-overflow: ellipsis;
    color: var(--muted); }
  :host(:not(:state(placeholder-shown))) .lf-field-placeholder { visibility: hidden; }
  /* The trailing action's room, after the last word. A box too narrow for it on the
     word's line takes it on a line of its own, so the field grows rather than run a
     word under the action. */
  .cm-line.lf-field-last::after { content: ""; display: inline-block;
    inline-size: var(--lf-field-end-room); }
  /* In a narrow field, the spacer can wrap by itself after the last word and leave
     that word under Send. Keep both together where the field asks for it. */
  :host([data-lf-end-room-glued]) .cm-line.lf-field-last::after {
    content: "\\00a0"; display: inline; inline-size: auto;
    padding-inline-end: var(--lf-field-end-room); white-space: nowrap;
  }
  /* The placeholder is a single line, so it stands where a last line would. */
  .lf-field-placeholder { padding-inline-end: var(--lf-field-end-room); }
  /* The action stands beside more than the last line under a finger, whose hit box is
     taller than a line, and in a scrolled field, which carries other lines past it. */
  @media (pointer: coarse) {
    .lf-field { padding-inline-end: var(--lf-field-end-room); }
    .lf-field-placeholder { padding-inline-end: 0; }
    .cm-line.lf-field-last::after,
    :host([data-lf-end-room-glued]) .cm-line.lf-field-last::after { content: none; }
  }
  :host([data-scrolls]) .lf-field { padding-inline-end: var(--lf-field-end-room); }
  :host([data-scrolls]) .cm-line.lf-field-last::after,
  :host([data-scrolls][data-lf-end-room-glued]) .cm-line.lf-field-last::after {
    content: none;
  }
  /* A draft wears the sent message's faces. Strong, emphasis and strikethrough are the
     elements themselves, which the platform dresses here as it does in the message;
     the rest read the theme's tokens, since its element rules stop at this root. A
     heading is bold, as the platform draws one, at the size of the words around it. A
     block is drawn line by line, so a code block's frame is each line's sides, closed
     above its first line and below its last. Syntax that holds its room while the
     caret is away, as a code fence's line does, is there unseen and unspoken. */
  .lf-md-mark { color: var(--muted); }
  .lf-md-unseen { color: transparent; }
  code { font-family: var(--mono); font-size: var(--code-inline-size);
    background: var(--code-bg); border-radius: var(--code-inline-r);
    padding: var(--code-inline-pad); box-decoration-break: slice; }
  .lf-md-heading { font-weight: bold; }
  .lf-md-link { color: var(--accent); text-decoration: underline var(--link-underline);
    text-underline-offset: var(--link-underline-offset); }
  .lf-md-quote { border-inline-start: var(--quote-rule); font-style: var(--quote-style);
    padding-inline-start: var(--quote-inset); color: var(--muted);
    --lf-marker-inset: var(--quote-inset); }
  /* A quote's and a list item's words stand where the message's do, and the source's
     marker stands in the inset before them, unseen while the caret is away, so
     revealing it moves no word. A list item's lines stand one list inset in per level,
     under the platform's own list marker, as in the message, so it is the same bullet
     or number at the same place. */
  .lf-md-item { margin-inline-start: calc(var(--lf-list-depth) * var(--list-inset));
    --lf-marker-inset: var(--list-inset); }
  .lf-md-marker { display: inline-flex; justify-content: flex-end; white-space: pre;
    inline-size: var(--lf-marker-inset);
    margin-inline-start: calc(-1 * var(--lf-marker-inset)); }
  .lf-md-listed { display: list-item; }
  .lf-md-disc { list-style-type: disc; }
  .lf-md-circle { list-style-type: circle; }
  .lf-md-square { list-style-type: square; }
  .lf-md-number { list-style-type: decimal; }
  .lf-md-code-block { font-family: var(--mono); font-size: var(--code-size);
    line-height: var(--code-line); color: var(--code-ink); background: var(--pre-bg);
    font-variant-ligatures: none; border-inline: 1px solid var(--code-border);
    padding-inline: var(--pre-inset); }
  .lf-md-code-first { border-block-start: 1px solid var(--code-border);
    border-start-start-radius: var(--r); border-start-end-radius: var(--r); }
  /* A sent pre reserves 8px below its lines for a horizontal scrollbar. */
  .cm-line.lf-md-code-last { border-block-end: 1px solid var(--code-border);
    border-end-start-radius: var(--r); border-end-end-radius: var(--r);
    padding-block-end: 8px; }
  /* Code with no fence lines takes the message's padding at its ends instead. */
  .lf-md-code-bare.lf-md-code-first { padding-block-start: var(--pre-pad-block); }
  .lf-md-code-bare.lf-md-code-last { padding-block-end: calc(var(--pre-pad-block) + 8px); }
`);
var ownerStep = StateEffect2.define();
var hide = Decoration.replace({});
var dim = Decoration.mark({ class: "lf-md-mark" });
var link = Decoration.mark({ class: "lf-md-link" });
var unseen = Decoration.mark({
  class: "lf-md-unseen",
  attributes: { "aria-hidden": "true" }
});
var marker = Decoration.mark({
  class: "lf-md-marker lf-md-unseen",
  attributes: { "aria-hidden": "true" }
});
var shownMarker = Decoration.mark({ class: "lf-md-marker lf-md-mark" });
var line = (cls) => Decoration.line({ class: cls });
var BULLETS = ["lf-md-disc", "lf-md-circle", "lf-md-square"];
var itemLine = (depth, kind, number) => Decoration.line({
  class: kind ? `lf-md-item lf-md-listed ${kind}` : "lf-md-item",
  attributes: {
    style: `--lf-list-depth: ${depth}${kind === "lf-md-number" ? `; counter-set: list-item ${number}` : ""}`
  }
});
var INLINE = {
  code_inline: Decoration.mark({ tagName: "code" }),
  em_open: Decoration.mark({ tagName: "em" }),
  strong_open: Decoration.mark({ tagName: "strong" }),
  s_open: Decoration.mark({ tagName: "s" })
};
var touches = (state, from, to) => state.selection.ranges.some((range) => range.from <= to && range.to >= from);
var read = (state) => {
  return placedMarkdownTokens(state.doc.toString());
};
function decorate(state, placed) {
  const out = [];
  const lists = [];
  const items = /* @__PURE__ */ new Map();
  const code = [];
  const add = (from, to, deco) => {
    if (from >= to) return;
    if (deco === hide && state.doc.sliceString(from, to).includes("\n")) deco = dim;
    out.push(deco.range(from, to));
  };
  const lines = (from, to, each) => {
    for (let at = from; at < to; ) {
      const current = state.doc.lineAt(at);
      each(current);
      at = current.to + 1;
    }
  };
  for (const {
    token,
    from,
    to,
    contentFrom,
    contentTo,
    escapes,
    markers,
    contentLines
  } of placed) {
    const syntax = touches(state, from, to) ? dim : hide;
    if (token.type === "code_inline" || contentFrom !== void 0) {
      const words = token.type === "code_inline" ? [from + token.markup.length, to - token.markup.length] : [contentFrom, contentTo];
      if (words[0] > words[1]) continue;
      if (INLINE[token.type]) add(from, to, INLINE[token.type]);
      else if (token.type === "link_open" && token.meta.linked)
        add(words[0], words[1], link);
      add(from, words[0], syntax);
      add(words[1], to, syntax);
    } else if (token.type === "text") {
      for (const at of escapes ?? [])
        add(at, at + 1, touches(state, at, at + 2) ? dim : hide);
    } else if (token.type === "heading_open") {
      lines(...contentLines, (each) => {
        out.push(line("lf-md-heading").range(each.from));
      });
      for (const [a, b] of markers)
        add(a, b, token.markup.startsWith("#") ? syntax : dim);
    } else if (token.type === "fence" || token.type === "code_block") {
      code.push([from, to]);
      const body = token.content.split("\n");
      const opened = state.doc.lineAt(from).number + (token.type === "fence" ? 1 : 0);
      lines(from, to, (each) => {
        const ends = [
          each.from <= from ? " lf-md-code-first" : "",
          each.to + 1 >= to ? " lf-md-code-last" : "",
          token.type === "code_block" ? " lf-md-code-bare" : ""
        ].join("");
        out.push(line(`lf-md-code-block${ends}`).range(each.from));
        const kept = body[each.number - opened];
        if (kept === void 0 || each.number - opened >= body.length - 1) return;
        const lead = each.text.match(/^[ \t]*/)[0].length;
        add(each.from, each.from + lead - kept.match(/^[ \t]*/)[0].length, hide);
      });
      const fence = touches(state, from, to - 1) ? dim : unseen;
      for (const [a, b] of markers ?? []) add(a, b, fence);
    } else if (token.type === "blockquote_open") {
      lines(from, to, (each) => {
        out.push(line("lf-md-quote").range(each.from));
      });
      for (const [a, b] of markers)
        add(a, b, touches(state, a, b) ? shownMarker : marker);
    } else if (token.type === "bullet_list_open" || token.type === "ordered_list_open") {
      while (lists.at(-1)?.to <= from) lists.pop();
      const ordered = token.type === "ordered_list_open";
      lists.push({ to, next: ordered ? Number(token.attrGet("start") ?? 1) : null });
    } else if (token.type === "list_item_open") {
      while (lists.at(-1)?.to <= from) lists.pop();
      const list = lists.at(-1);
      const depth = lists.length;
      const head = state.doc.lineAt(from);
      const [at, end] = markers[0];
      const start = at - head.text.slice(0, at - head.from).match(/[ \t]*$/)[0].length;
      if (head.text.slice(0, start - head.from).trim()) {
        add(start, end, dim);
        continue;
      }
      lines(head.to + 1, Math.min(to, state.doc.length), (each) => {
        items.set(each.from, { depth, continued: true });
      });
      const kind = list.next === null ? BULLETS[Math.min(depth, BULLETS.length) - 1] : "lf-md-number";
      const shown = state.selection.ranges.some(
        (range) => range.from < end && range.to >= start
      );
      items.set(head.from, { depth, kind: shown ? null : kind, number: list.next });
      if (list.next !== null) list.next++;
      add(start, end, shown ? shownMarker : marker);
    }
  }
  for (const [from, { depth, kind, number, continued }] of items) {
    out.push(itemLine(depth, kind, number).range(from));
    if (!continued || code.some(([a, b]) => from >= a && from < b)) continue;
    add(from, from + state.doc.lineAt(from).text.match(/^[ \t]*/)[0].length, hide);
  }
  return Decoration.set(out, true);
}
var livePreview = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.live = true;
      this.placed = read(view.state);
      this.decorations = decorate(view.state, this.placed);
      this.judged = markdownReady();
      if (!this.judged)
        loadMarkdown().then(
          () => this.live && view.dispatch({}),
          () => {
          }
        );
    }
    destroy() {
      this.live = false;
    }
    update(update) {
      const judged = markdownReady();
      if (update.docChanged || judged !== this.judged) {
        this.judged = judged;
        this.placed = read(update.state);
      } else if (!update.selectionSet) return;
      this.decorations = decorate(update.state, this.placed);
    }
  },
  { decorations: (plugin) => plugin.decorations }
);
var lastLine = Decoration.line({ class: "lf-field-last" });
var lastWithWords = (state) => {
  const last = state.doc.line(state.doc.lines);
  return last.text.trim() ? last : null;
};
var lastLineRoom = EditorView2.decorations.compute(["doc"], (state) => {
  const last = lastWithWords(state);
  return last ? Decoration.set([lastLine.range(last.from)]) : Decoration.none;
});
var LeafText = class extends HTMLElement {
  // The field's one model. Until the field has an editor it is a bare EditorState,
  // which holds the value, selection and configuration without a DOM; building the
  // editor hands it to the view that edits it from then on (`#build`).
  #model;
  #view = null;
  // The empty line's place while the field has no editor, and the node focus lands on
  // there, whichever route brought it.
  #rest = document.createElement("div");
  #nativeInput = false;
  #root;
  #internals = null;
  #editable = new Compartment2();
  #history = new Compartment2();
  #attributes = new Compartment2();
  #placeholderLayer = document.createElement("div");
  #placeholderText = document.createTextNode("");
  #frame = document.createElement("div");
  #readOnly = false;
  #sizes = sizeObserver(() => {
    const view = this.#view;
    if (view?.hasFocus)
      view.requestMeasure({
        key: this,
        read: () => {
          const caret = view.coordsAtPos(view.state.selection.main.head);
          const box = this.getBoundingClientRect();
          const { scaleX, scaleY } = view;
          const inset = landingInsets(this);
          const leading = caret ? Math.max(
            0,
            (parseFloat(getComputedStyle(this).lineHeight) * scaleY - (caret.bottom - caret.top)) / 2
          ) : 0;
          return {
            caret,
            scaleX,
            scaleY,
            top: box.top + (this.clientTop + inset.top) * scaleY + leading,
            left: box.left + (this.clientLeft + inset.left) * scaleX,
            // client dimensions round fractional CSS sizes. Keep the trailing
            // edges on the actual box, inset by its native border and scrollbar.
            bottom: box.bottom - (this.offsetHeight - this.clientTop - this.clientHeight + inset.bottom) * scaleY - leading,
            right: box.right - (this.offsetWidth - this.clientLeft - this.clientWidth + inset.right) * scaleX
          };
        },
        write: ({ caret, top, left, bottom, right, scaleX, scaleY }) => {
          if (!caret) return;
          const wholePixel = (distance) => distance < 0 ? Math.floor(distance) : Math.ceil(distance);
          this.scrollBy({
            top: wholePixel(
              (Math.min(0, caret.top - top) + Math.max(0, caret.bottom - bottom)) / scaleY
            ),
            left: wholePixel(
              (Math.min(0, caret.left - left) + Math.max(0, caret.right - right)) / scaleX
            ),
            behavior: "instant"
          });
        }
      });
  });
  // Host overflow holds the action's room on every line. The host stops at the page's
  // height limit while words grow inside it, so the reading watches the editor's
  // content too. Editor updates and size changes share its read/write phase: the room
  // changes layout there, rather than feeding back into resize observer delivery. The
  // same reading says which edges words run past (`more-above`, `more-below`), read
  // again as the host scrolls, so an owner can show there is more without a scrollbar.
  // A scroll timeline would say it in CSS alone, but Firefox lacks scroll timelines.
  #overflow = sizeObserver(() => this.#measureOverflow());
  #measureOverflow() {
    this.#view?.requestMeasure({
      key: this.#overflow,
      // Words, not the host's padding, run past an edge.
      read: () => {
        const style = getComputedStyle(this);
        return {
          scrolls: this.scrollHeight > this.clientHeight,
          above: this.scrollTop > Number.parseFloat(style.paddingTop) + 1,
          below: this.scrollTop + this.clientHeight < this.scrollHeight - Number.parseFloat(style.paddingBottom) - 1
        };
      },
      write: (reading) => {
        if (this.hasAttribute("data-scrolls") !== reading.scrolls)
          this.toggleAttribute("data-scrolls", reading.scrolls);
        for (const [state, on] of [
          ["more-above", reading.scrolls && reading.above],
          ["more-below", reading.scrolls && reading.below]
        ]) {
          if (this.#internals.states.has(state) === on) continue;
          if (on) this.#internals.states.add(state);
          else this.#internals.states.delete(state);
        }
      }
    });
  }
  static observedAttributes = ["aria-label", "aria-describedby", "placeholder"];
  constructor() {
    super();
    this.#root = this.attachShadow({ mode: "closed", delegatesFocus: true });
    this.#frame.className = "lf-field";
    this.#placeholderLayer.className = "lf-field-placeholder";
    this.#placeholderLayer.setAttribute("aria-hidden", "true");
    this.#placeholderLayer.setAttribute("part", "placeholder");
    const hint = document.createElement("slot");
    hint.name = "placeholder";
    hint.append(this.#placeholderText);
    this.#placeholderLayer.append(hint);
    this.#rest.className = "lf-field-rest";
    this.#rest.append(document.createElement("br"));
    this.#rest.addEventListener("focusin", () => this.#build());
    this.#frame.append(this.#placeholderLayer, this.#rest);
    this.#root.append(this.#frame);
    this.#model = this.#create("");
    this.#dressRest();
    this.addEventListener("mousedown", (event) => this.#pressPadding(event));
    this.addEventListener("dragenter", () => {
      if (!this.#view) this.#build();
    });
    this.addEventListener("scroll", () => this.#measureOverflow(), { passive: true });
    this.#root.addEventListener("beforeinput", () => this.#beforeEdit(), {
      capture: true
    });
    for (const type of ["input", "beforeinput"])
      this.#root.addEventListener(type, (event) => event.stopPropagation());
  }
  // A fresh state holding `text`, caret at its end, under the field's current
  // configuration. A new state is also a new undo history.
  #create(text) {
    return EditorState2.create({
      doc: text,
      selection: { anchor: text.length },
      extensions: [
        // DOM input has already changed the words when CodeMirror reads it, so its
        // bracket started at beforeinput. EditContext leaves rendering to the editor;
        // its transactions, like commands, still start before the DOM changes.
        EditorView2.inputHandler.of((view, _from, _to, _text, insert) => {
          this.#nativeInput = !view.contentDOM.editContext;
          try {
            view.dispatch(insert());
          } finally {
            this.#nativeInput = false;
          }
          return true;
        }),
        this.#history.of(history2()),
        invertedEffects.of(
          (tr) => tr.effects.filter((effect) => effect.is(ownerStep)).map(({ value }) => ownerStep.of({ run: value.back, back: value.run }))
        ),
        keymap.of([
          {
            key: "Enter",
            run: (view) => this.dispatchEvent(new Event("lf-edit-return", { cancelable: true })) && insertNewline(view)
          },
          { key: "Shift-Enter", run: insertNewlineContinueMarkup },
          // Outside a list or quote, a plain new line, which asks to be seen as typing
          // does, so a field at its height limit scrolls to it.
          {
            key: "Shift-Enter",
            run: (view) => (view.dispatch(
              view.state.update(view.state.replaceSelection("\n"), {
                scrollIntoView: true,
                userEvent: "input"
              })
            ), true)
          },
          ...standardKeymap.filter(
            ({ key }) => key !== "Escape" && key !== "Enter" && key !== "Mod-Enter"
          ),
          ...historyKeymap
        ]),
        new LanguageSupport(markdownLanguage),
        livePreview,
        lastLineRoom,
        EditorView2.lineWrapping,
        this.#editable.of(EditorState2.readOnly.of(this.#readOnly)),
        this.#attributes.of(EditorView2.contentAttributes.of(this.#contentAttributes()))
      ]
    });
  }
  attributeChangedCallback(name) {
    if (name === "placeholder") this.#placeholderText.data = this.placeholder;
    if (name === "aria-describedby") return this.#describe();
    this.#dressRest();
    this.#apply({
      effects: this.#attributes.reconfigure(
        EditorView2.contentAttributes.of(this.#contentAttributes())
      )
    });
  }
  // A move by `moveBefore` keeps the editor and its focus but collapses the native
  // selection in it, which CodeMirror would read back as a caret at the start. With this
  // callback the move is no disconnection, and the view puts its caret back as it lands.
  connectedMoveCallback() {
    this.#view?.placeSelection();
  }
  connectedCallback() {
    this.classList.toggle("scroll", true);
    if (this.#view) return;
    if (!this.hasAttribute("role")) this.setAttribute("role", "textbox");
    if (!this.hasAttribute("aria-multiline"))
      this.setAttribute("aria-multiline", "true");
    if (!this.hasAttribute("tabindex")) this.tabIndex = 0;
    this.#internals ??= this.attachInternals();
    this.#root.adoptedStyleSheets = [sheet];
    if (this.#model.doc.length) this.#build();
    else this.#describe();
    this.#paintEmpty();
    this.#internals.states.add("ready");
  }
  // Until the field has an editor, its empty line's place stands in for the editor's
  // content node to assistive technology, so the tree reads the same before and after
  // the editor builds. CodeMirror's node is a multiline textbox, `contenteditable` (its
  // theme makes it plain text only) and `aria-readonly` while the field is read-only,
  // and it wears the field's name, hint and description (`#describe`). This place
  // declares the same, and being editable it is a tab stop where the editor's node is.
  #dressRest() {
    const wanted = {
      ...this.#contentAttributes(),
      role: "textbox",
      "aria-multiline": "true",
      contenteditable: "plaintext-only",
      ...this.#readOnly && { "aria-readonly": "true" }
    };
    for (const name of ["aria-label", "aria-placeholder", "aria-readonly"])
      if (!(name in wanted)) this.#rest.removeAttribute(name);
    for (const [name, value] of Object.entries(wanted))
      if (this.#rest.getAttribute(name) !== value) this.#rest.setAttribute(name, value);
  }
  // A connected field draws its words in an editor, and an empty one builds its editor
  // only when the user arrives in it, by its own `focus()`, a press, or native focus by
  // any route, which lands on the empty line's place, or when words are written into
  // it. Building on arrival hands focus to the words in the same task, so the first key
  // the user types lands in them. A page holding many fields, such as one under each
  // list of options, builds none of them to show itself.
  #build() {
    this.#view = new LeafEditorView({
      root: this.#root,
      parent: this.#frame,
      state: this.#model,
      // Dispatched word changes are the user's. The value setter updates the view
      // directly and silently; an owner's `record` changes no words.
      dispatchTransactions: (transactions, view) => {
        const edited = transactions.some((tr) => tr.docChanged);
        if (edited && !this.#nativeInput) this.#beforeEdit();
        view.update(transactions);
        for (const tr of transactions)
          if (tr.isUserEvent("undo") || tr.isUserEvent("redo")) {
            for (const effect of tr.effects)
              if (effect.is(ownerStep)) effect.value.run();
          }
        this.#paintEmpty();
        this.#measureOverflow();
        if (edited) this.dispatchEvent(new Event("input", { bubbles: true }));
        else if (transactions.some((tr) => tr.isUserEvent("select")))
          this.dispatchEvent(new Event("lf-caret-move", { bubbles: true }));
      }
    });
    this.#model = null;
    this.#sizes.observe(this);
    this.#overflow.observe(this);
    this.#overflow.observe(this.#view.contentDOM);
    this.#view.scrollDOM.removeAttribute("tabindex");
    this.#describe();
    if (this.#root.activeElement === this.#rest) {
      this.#view.contentDOM.focus({ preventScroll: true });
      this.#view.placeSelection();
    }
    this.#rest.hidden = true;
    this.#measureOverflow();
  }
  #beforeEdit() {
    this.dispatchEvent(new Event("lf-before-edit", { bubbles: true }));
  }
  // A move between parents reconnects within the task and keeps its editor.
  disconnectedCallback() {
    queueMicrotask(() => {
      if (this.isConnected) return;
      this.#internals.states.delete("ready");
      if (!this.#view) return;
      this.#model = this.#view.state;
      this.#sizes.disconnect();
      this.#overflow.disconnect();
      this.#view.destroy();
      this.#view = null;
      this.#rest.hidden = false;
    });
  }
  #describe() {
    if (!this.isConnected) return;
    const content = this.#view?.contentDOM ?? this.#rest;
    const root = (
      /** @type {Document | ShadowRoot} */
      this.getRootNode()
    );
    const described = (this.getAttribute("aria-describedby") ?? "").split(/\s+/).filter(Boolean).map((id) => root.getElementById(id)).filter(Boolean);
    const current = content.ariaDescribedByElements ?? [];
    if (described.length !== current.length || described.some((element, at) => element !== current[at]))
      content.ariaDescribedByElements = described;
  }
  // The editor adapter places its recorded caret without native scrolling. The
  // field reveals itself separately when its caller requests ordinary focus.
  focus(options) {
    if (!this.#view && this.isConnected) this.#build();
    if (!this.#view) return;
    this.#view.focus();
    if (this.#root.activeElement !== this.#view.contentDOM) return;
    if (!options?.preventScroll) scrollIntoView(this, { block: "nearest" });
  }
  blur() {
    this.#view?.contentDOM.blur();
  }
  // A press on the box outside the editor's own area — its padding — lands in the words
  // at the nearest character, the way a textarea's does. Presses inside the editor are
  // CodeMirror's to place.
  #pressPadding(event) {
    if (event.button !== 0) return;
    if (!this.#view) {
      event.preventDefault();
      this.focus({ preventScroll: true });
      return;
    }
    const area = this.#view.scrollDOM.getBoundingClientRect();
    const { clientX: x2, clientY: y } = event;
    if (x2 >= area.left && x2 < area.right && y >= area.top && y < area.bottom) return;
    event.preventDefault();
    const clamp2 = (value, low, high) => Math.min(Math.max(value, low), high - 1);
    const at = this.#view.posAtCoords(
      { x: clamp2(x2, area.left, area.right), y: clamp2(y, area.top, area.bottom) },
      false
    );
    this.#view.focus();
    this.#view.dispatch({ selection: { anchor: at } });
  }
  get #state() {
    return this.#view?.state ?? this.#model;
  }
  #apply(spec) {
    if (!this.#view && spec.changes && this.isConnected) this.#build();
    if (this.#view) this.#view.dispatch(spec);
    else this.#model = this.#model.update(spec).state;
  }
  #contentAttributes() {
    const attributes = {
      spellcheck: "true",
      autocorrect: "on",
      autocapitalize: "sentences"
    };
    if (this.placeholder) attributes["aria-placeholder"] = this.placeholder;
    const label = this.getAttribute("aria-label");
    if (label !== null) attributes["aria-label"] = label;
    return attributes;
  }
  #paintEmpty() {
    if (this.#state.doc.length) this.#internals.states.delete("placeholder-shown");
    else this.#internals.states.add("placeholder-shown");
  }
  // Where the field holds its action's room now: `every-line`, `last-line` after its
  // last words, or `none` while its last line is blank.
  get endRoom() {
    if (parseFloat(getComputedStyle(this.#frame).paddingInlineEnd) > 0)
      return "every-line";
    return lastWithWords(this.#state) ? "last-line" : "none";
  }
  get value() {
    return this.#state.doc.toString();
  }
  edit(text) {
    text = String(text).replace(/\r\n?/g, "\n");
    if (text === this.value) return;
    this.#apply({
      changes: { from: 0, to: this.#state.doc.length, insert: text },
      selection: { anchor: text.length },
      userEvent: "input.dictation"
    });
  }
  // Records a change the owner has just made outside the words as a step of the words'
  // history, standing alone: taking the step back calls `undo`, redoing it calls `redo`.
  record(undo, redo) {
    this.#apply({
      effects: ownerStep.of({ run: redo, back: undo }),
      annotations: isolateHistory.of("full")
    });
  }
  // Forgets the history and keeps the words, the caret and the editor's DOM, for a box
  // that takes up a draft as it stands. Dropping the history's field and adding it back
  // starts it empty.
  restartHistory() {
    this.#apply({ effects: this.#history.reconfigure([]) });
    this.#apply({ effects: this.#history.reconfigure(history2()) });
  }
  get naturalBlockSize() {
    const host = getComputedStyle(this);
    return parseFloat(getComputedStyle(this.#frame).blockSize) + parseFloat(host.paddingBlockStart) + parseFloat(host.paddingBlockEnd) + parseFloat(host.borderBlockStartWidth) + parseFloat(host.borderBlockEndWidth);
  }
  set value(text) {
    text = String(text ?? "").replace(/\r\n?/g, "\n");
    if (text === this.value) return;
    if (!this.#view && this.isConnected) this.#build();
    if (!this.#view) {
      this.#model = this.#create(text);
      return;
    }
    const content = this.#view.contentDOM;
    const composing = this.#view.composing && content.editContext;
    if (composing) content.editContext = null;
    const reset = this.#view.state.update({
      changes: { from: 0, to: this.#view.state.doc.length, insert: text },
      selection: { anchor: text.length },
      effects: this.#history.reconfigure([])
    });
    const fresh = reset.state.update({
      effects: this.#history.reconfigure(history2())
    });
    this.#view.update([reset, fresh]);
    if (composing) content.editContext = composing;
    this.#paintEmpty();
    this.#measureOverflow();
  }
  get selectionStart() {
    return this.#state.selection.main.from;
  }
  get selectionEnd() {
    return this.#state.selection.main.to;
  }
  get selectionDirection() {
    const { main } = this.#state.selection;
    return main.empty ? "none" : main.head < main.anchor ? "backward" : "forward";
  }
  // A textarea's clamping: each end within the words, and a start past the end moved to
  // the end.
  setSelectionRange(start, end, direction = "none") {
    const length = this.#state.doc.length;
    const to = Math.min(Math.max(Number(end) || 0, 0), length);
    const from = Math.min(Math.max(Number(start) || 0, 0), to);
    this.#apply({
      selection: direction === "backward" ? { anchor: to, head: from } : { anchor: from, head: to }
    });
  }
  select() {
    this.setSelectionRange(0, this.#state.doc.length);
  }
  get placeholder() {
    return this.getAttribute("placeholder") ?? "";
  }
  set placeholder(text) {
    this.setAttribute("placeholder", text);
  }
  get readOnly() {
    return this.#readOnly;
  }
  set readOnly(on) {
    this.#readOnly = Boolean(on);
    this.#dressRest();
    this.#apply({
      effects: this.#editable.reconfigure(EditorState2.readOnly.of(this.#readOnly))
    });
  }
  get name() {
    return this.getAttribute("name") ?? "";
  }
  set name(value) {
    this.setAttribute("name", value);
  }
};
if (!customElements.get(TEXT_FIELD)) customElements.define(TEXT_FIELD, LeafText);
var textField = () => document.createElement(TEXT_FIELD);

// runtime/composing/selection.js
var fabBar = el("div", "lf-ui lf-fab-bar lf-target-paint");
fabBar.dataset.lfRuntime = "";
fabBar.setAttribute("role", "group");
fabBar.setAttribute("aria-label", "Respond");
var fabInput = textField();
fabInput.className = "lf-ui lf-response-control lf-fab-input";
fabInput.name = "comment";
fabInput.placeholder = "Comment\u2026";
fabInput.setAttribute("aria-label", "Comment");
var fab = responseAction(el("button", "lf-ui lf-fab"), {
  icon: "comment",
  label: "Comment",
  behavior: "disclosure"
});
fab.id = "lf-comment-button";
fab.title = "Comment";
var fabOptions = el("span", "lf-response-options");
fabOptions.id = "lf-response-options";
fabOptions.popover = "auto";
fabOptions.setAttribute("role", "group");
fabOptions.setAttribute("aria-label", "Other responses");
var fabSuggest = responseAction(el("button", "lf-ui lf-fab-suggest"), {
  icon: "edit",
  label: "Suggest",
  collapse: true
});
fabOptions.append(fabSuggest);
var fabOptionsTrigger = responseAction(
  el("button", "lf-ui lf-response-trigger"),
  {
    icon: "more",
    label: "Other responses",
    collapse: true,
    behavior: "disclosure"
  }
);
fabOptionsTrigger.setAttribute("aria-controls", fabOptions.id);
fabOptionsTrigger.setAttribute("aria-expanded", "false");
fabOptionsTrigger.popoverTargetElement = fabOptions;
fabBar.append(fab, fabOptionsTrigger, fabOptions);
var composer = el("div", "lf-ui lf-composer");
composer.id = "lf-composer";
var composerQuote = el("blockquote", "lf-ui lf-quote detached");
composerQuote.id = "lf-composer-quote";
var composerInput = fabInput;
composerInput.setAttribute("aria-describedby", composerQuote.id);
var composerSend = el("button", "lf-btn", "Comment");
var composerField = document.createDocumentFragment();
composerField.append(composerInput);
composer.append(composerQuote, composerSend);
fabBar.prepend(composer);
var pendingAnchor = null;
var pendingAbout = null;
var pendingDrawing = null;
function wordsOf(element) {
  const range = document.createRange();
  range.selectNodeContents(element);
  const words = anchorForRange(range);
  return words.quote?.trim() ? words : null;
}
var composerOpen = false;
function createSelectionComposer({
  setReact,
  reactionTokens: reactionTokens2,
  reactionAvailable: reactionAvailable2,
  designModeActive,
  openPageThread,
  anchorTravelAt,
  bringForward,
  fabAnchorAt,
  fabPointAt,
  fabFrameAt,
  fabPositioned,
  beginFabFocus,
  endFabFocus,
  landFabFocus,
  showFab,
  letGoOfFab,
  createComment,
  landSent,
  refreshThread,
  wireInput: wireInput2,
  drawingEdits
}) {
  const closeReactions = () => setReact(false);
  const COMPOSER_KEY = "composer:";
  const composerCtx = (anchor) => COMPOSER_KEY + anchorKey(anchor);
  let syncComposer;
  let pendingRevision = null;
  let suggestionMode = false;
  const composerDraftPayload = () => ({
    format: DRAFT_FORMAT,
    anchor: pendingAnchor,
    revision: pendingRevision,
    suggest: suggestionMode,
    about: pendingAbout,
    drawing: pendingDrawing,
    touched: Date.now()
  });
  const saveComposerDraft = (text = syncComposer.value()) => saveDraft(composerCtx(pendingAnchor), text, composerDraftPayload());
  const composerRecord = (ctx) => {
    const payload = loadDraftPayload(ctx);
    return payload?.format === DRAFT_FORMAT ? { ...payload, text: loadDraft(ctx) } : null;
  };
  const draftDrawing = (anchor) => {
    return composerRecord(composerCtx(anchor))?.drawing ?? null;
  };
  function heldDrawings() {
    const at = composerCtx(pendingAnchor);
    const held = [];
    for (const ctx of draftContexts()) {
      if (!ctx.startsWith(COMPOSER_KEY)) continue;
      const record = composerRecord(ctx);
      const drawing = ctx === at ? pendingDrawing : record?.drawing;
      if (!record || !drawing) continue;
      held.push({ anchor: record.anchor, drawing, open: composerOpen && ctx === at });
    }
    return held;
  }
  function setDraftDrawing(anchor, drawing) {
    const ctx = composerCtx(anchor);
    if (ctx === composerCtx(pendingAnchor)) {
      pendingDrawing = drawing;
      saveComposerDraft();
      syncSuggestMode();
      return;
    }
    const record = composerRecord(ctx);
    if (!record) return;
    const { text, ...payload } = record;
    if (!text && !drawing) clearDraft(ctx);
    else saveDraft(ctx, text, { ...payload, drawing });
  }
  const watchHeldDrawings = (callback) => watchDrafts(COMPOSER_KEY, callback);
  function pendingComposer() {
    let best = null;
    for (const ctx of draftContexts()) {
      if (!ctx.startsWith(COMPOSER_KEY)) continue;
      const record = composerRecord(ctx);
      if ((record?.text || record?.drawing) && (!best || record.touched > best.touched))
        best = record;
    }
    return best;
  }
  let composerEpoch = 0;
  const holdsContent = (draft) => Boolean(draft || pendingDrawing);
  const composerHolds = () => holdsContent(syncComposer.value());
  function syncSuggestMode() {
    const suggest = !suggestionMode;
    responseAction(fabSuggest, {
      icon: suggest ? "edit" : "comment",
      label: suggest ? "Suggest" : "Comment",
      collapse: true
    });
    keeps(fabSuggest, "aria-label", suggest ? "Suggest" : "Comment");
    keeps(fabSuggest, "title", suggest ? "Suggest" : "Comment");
    syncComposer();
    syncResponseOptions();
    repaint();
  }
  function setSuggestionMode(suggest) {
    suggestionMode = Boolean(suggest);
    if (suggestionMode && syncComposer.hasMedia()) {
      suggestionMode = false;
      syncSuggestMode();
      raiseError("Remove attached images before suggesting replacement text");
      focusDestination(composerInput, "return");
      return;
    }
    if (suggestionMode && !syncComposer.value() && pendingAnchor?.quote)
      syncComposer.load(seededQuote = pendingAnchor.quote);
    syncSuggestMode();
    saveComposerDraft();
    focusDestination(composerInput, "return");
  }
  let responseOptionsOpen = false;
  const availableResponseOptions = () => [
    ...fabOptions.querySelectorAll(".lf-response-action:not([hidden])")
  ];
  const responseOptionsAreOpen = () => responseOptionsOpen;
  const responseOptionsAvailable = () => availableResponseOptions().length > 0;
  const responseOptionButtons = () => availableResponseOptions().filter((control) => control.checkVisibility());
  const focusedResponseOption = () => responseOptionButtons().includes(focused());
  const responseReactionButtons = () => responseOptionButtons().filter((control) => control.classList.contains("lf-react"));
  function stepResponseOptions(binding) {
    const choices = responseOptionButtons();
    if (!choices.length) return;
    const at = choices.indexOf(focused());
    const backward = [rowArrows(choices[0])[0], "ArrowUp"].includes(binding);
    const next = at < 0 ? backward ? choices.length - 1 : 0 : (at + (backward ? -1 : 1) + choices.length) % choices.length;
    focusDestination(choices[next], "move");
    beginWalk(
      "response-option",
      "Response",
      () => listWalkPosition(responseOptionButtons(), focused())
    );
  }
  const focusResponseOption = (focus) => {
    const mayFocus = retainUserIntent();
    void fabPositioned().then((positioned) => {
      if (!positioned || !responseOptionsOpen) return;
      const options = responseOptionButtons();
      const destination = focus === "reaction" ? options.find((control) => control.classList.contains("lf-react")) : options[0];
      if (destination) mayFocus.handoff(() => focusDestination(destination, "move"));
      paintKeys();
    });
  };
  function setResponseOptions(open, { focus = null } = {}) {
    const next = Boolean(open && fabAnchorAt() && responseOptionsAvailable());
    if (next === responseOptionsOpen) {
      if (next && focus) focusResponseOption(focus);
      return next;
    }
    if (next) setReact(false);
    responseOptionsOpen = next;
    keeps(fabOptionsTrigger, "aria-expanded", String(next));
    if (next) showNativeLayer(fabOptions, { source: fabOptionsTrigger });
    else closeNativeLayer(fabOptions);
    if (next && focus) focusResponseOption(focus);
    paintKeys();
    return next;
  }
  function syncResponseOptions(anchor = fabAnchorAt()) {
    keepsHidden(
      fabSuggest,
      !(anchor?.quote && !designModeActive() && (!composerOpen || !pendingAbout && !pendingDrawing))
    );
    keepsHidden(fabOptionsTrigger, !responseOptionsAvailable());
    if (responseOptionsOpen && !responseOptionsAvailable()) setResponseOptions(false);
  }
  function resetResponseOptions() {
    setResponseOptions(false);
  }
  function showComposer(open) {
    if (open && composerField.hasChildNodes()) composer.append(composerField);
    if (!open) syncComposer?.cancelDictation();
    if (composerOpen && !open && composerHolds())
      notice("Draft kept \u2014 g i resumes writing");
    composerOpen = open;
    composer.toggleAttribute("data-lf-open", open);
    refreshThread();
    repaint();
  }
  let seededQuote = "";
  function adoptComposerDraft({ anchor, revision, text, suggest, about, drawing }) {
    const retargeted = JSON.stringify(pendingAnchor) !== JSON.stringify(anchor);
    if (syncComposer.value() !== text) {
      syncComposer.load(text);
      seededQuote = "";
    }
    pendingAnchor = anchor;
    pendingRevision = revision;
    pendingAbout = about ?? null;
    pendingDrawing = drawing ?? null;
    suggestionMode = Boolean(suggest);
    return retargeted;
  }
  function openComposer(anchor, text, {
    suggest = void 0,
    about = void 0,
    drawing = void 0,
    carry = false,
    focus = true,
    point = void 0,
    revision = applicationState.read().document.revision
  } = {}) {
    closeReactions();
    const ctx = composerCtx(anchor || null);
    const previousCtx = composerCtx(pendingAnchor);
    const drawingSupplied = drawing !== void 0;
    let carriedDraft = false;
    let storedDrawing = null;
    if (previousCtx !== ctx) {
      suggest = suggest === void 0 ? false : suggest;
      about = about === void 0 ? designModeActive() ? "design" : null : about;
      if (seededQuote && composerInput.value === seededQuote) syncComposer.load("");
      seededQuote = "";
      composerEpoch += 1;
      const previousText = syncComposer.value();
      const previousDrawing = pendingDrawing;
      syncComposer.load("");
      const record = text ? null : composerRecord(ctx);
      storedDrawing = composerRecord(ctx)?.drawing ?? null;
      const carrying = carry && previousText && !previousDrawing && !(record?.text || record?.drawing);
      if (carrying) {
        text ||= previousText;
        carriedDraft = true;
      } else if (record) {
        ({ text, suggest, about } = record);
      }
    }
    adoptComposerDraft({
      anchor: anchor || null,
      revision,
      text: text || syncComposer.value(),
      suggest: suggest === void 0 ? suggestionMode : suggest,
      about: about === void 0 ? pendingAbout : about,
      drawing: previousCtx !== ctx ? storedDrawing : pendingDrawing
    });
    const target = pendingAnchor?.section ? elementById(pendingAnchor.section) : null;
    keeps(
      fabBar,
      "data-lf-paint-plane",
      target && inChrome(target) ? "chrome" : "page"
    );
    if (previousCtx !== ctx) syncComposer.arrive();
    if (drawingSupplied) pendingDrawing = drawing ?? null;
    let handoff = 0;
    if (focus) handoff = beginFabFocus();
    else endFabFocus();
    showComposer(true);
    showFab(anchor, { point, reveal: true });
    syncSuggestMode();
    if (focus) {
      const focusEpoch = composerEpoch;
      landFabFocus(handoff, pendingAnchor, () => focusEpoch === composerEpoch);
    }
    watchComposer();
    if (carriedDraft)
      transferDraft(previousCtx, ctx, syncComposer.value(), composerDraftPayload());
    else if (drawingSupplied && JSON.stringify(composerRecord(ctx)?.drawing ?? null) !== JSON.stringify(pendingDrawing)) {
      saveComposerDraft();
      rememberWriting(composerInput);
    }
  }
  function openComposerWithMedia(anchor, images, options = {}) {
    openComposer(anchor, "", { carry: true, ...options });
    return syncComposer.addMedia(images);
  }
  let composerWatch = null;
  function watchComposer() {
    composerWatch?.();
    composerWatch = watchDraft(
      composerCtx(pendingAnchor),
      (value) => {
        if (value === null) return settleComposer();
        const record = composerRecord(composerCtx(pendingAnchor));
        if (!record) return settleComposer();
        const outside = syncComposer.value() !== record.text || JSON.stringify(record.drawing ?? null) !== JSON.stringify(pendingDrawing);
        const retargeted = adoptComposerDraft(record);
        if (retargeted && composerOpen) showFab(pendingAnchor);
        if (outside) syncComposer.arrive();
        syncSuggestMode();
        refreshThread();
      },
      { input: fabInput }
    );
  }
  const hideComposer = () => showComposer(false);
  function leaveComposer(discard) {
    if (discard) clearDraft(composerCtx(pendingAnchor));
    composerWatch?.();
    composerWatch = null;
    syncComposer.load("");
    seededQuote = "";
    suggestionMode = false;
    pendingAnchor = null;
    pendingRevision = null;
    pendingAbout = null;
    pendingDrawing = null;
    syncComposer.arrive();
    syncSuggestMode();
    hideComposer();
  }
  function detachComposer() {
    composerEpoch += 1;
    leaveComposer(false);
  }
  function carryComposerToReply(ctx) {
    if (!pendingAnchor) return;
    const text = syncComposer.value();
    if (ctx && text && !loadDraft(ctx) && !suggestionMode && !pendingAbout && !pendingDrawing && !syncComposer.hasMedia())
      transferDraft(composerCtx(pendingAnchor), ctx, text);
    detachComposer();
    showFab(null);
  }
  function settleComposer() {
    leaveComposer(false);
    letGoOfFab();
  }
  function openDraft(record = pendingComposer(), { focus = true } = {}) {
    if (!record) return false;
    openComposer(record.anchor, record.text, { ...record, focus });
    return true;
  }
  registerWritingDestination(COMPOSER_KEY, (ctx) => {
    const record = composerRecord(ctx);
    if (!record) return null;
    return {
      hasContent: Boolean(record.text || record.drawing),
      // A detached draft's destination is its native editor, not a guessed passage.
      // Arrival clears covering surfaces before this same field is materialized.
      where: anchorTravelAt(record.anchor) ?? composerInput,
      input: () => composerOpen && composerCtx(pendingAnchor) === ctx ? composerInput : null,
      open: () => {
        openDraft(composerRecord(ctx), { focus: false });
        const handoff = beginFabFocus();
        return () => endFabFocus(handoff);
      },
      present: fabPositioned
    };
  });
  function mount() {
    declareResponseOptionKeys();
    syncComposer = wireInput2(composerInput, {
      hint: () => suggestionMode ? "Replacement text" : pendingAbout ? "About the layer" : "Comment\u2026",
      sends: () => suggestionMode ? "suggest" : "comment",
      sendBtn: composerSend,
      allowsMedia: () => suggestionMode ? "Images can be added to comments, not replacement text" : true,
      hasContent: holdsContent,
      save: saveComposerDraft,
      drawing: {
        read: () => pendingDrawing,
        target: () => drawingEdits.target(pendingAnchor),
        replace: (drawn2) => drawingEdits.replace(pendingAnchor, drawn2),
        undoStroke: () => drawingEdits.undoStroke(pendingAnchor),
        remove: () => drawingEdits.remove(pendingAnchor)
      },
      send: async (_text, raw, owns, visible) => {
        const anchor = structuredClone(pendingAnchor);
        const revision = pendingRevision;
        const ctx = composerCtx(anchor);
        const suggestion = suggestionMode;
        const about = pendingAbout;
        const drawing = pendingDrawing && sentDrawing(structuredClone(pendingDrawing));
        const origin = fabFrameAt();
        const point = fabPointAt();
        const epoch = composerEpoch;
        const currentIntent = retainUserIntent();
        const untouched = retainUserIntent({ source: document.documentElement });
        let flight = null;
        const sent = sendMessage(
          ctx,
          () => composerCtx(pendingAnchor) === ctx && owns(),
          (attempt) => {
            if (point) commitPoint(attempt, point, wordsOf(point));
            const event = { anchor, revision, attempt };
            if (raw) event.text = raw;
            if (suggestion) event.suggestion = true;
            if (about) event.about = about;
            if (drawing) event.drawing = drawing;
            return flight = createComment(event);
          }
        );
        if (!sent) return;
        void Promise.resolve(flight).then((accepted) => {
          if (accepted || composerEpoch !== epoch || composerOpen) return;
          const record = composerRecord(ctx);
          if (record && untouched()) untouched.handoff(() => openDraft(record));
        });
        const revealSent = bindQueuedWork(
          (options) => openPageThread(sent.id, options)
        );
        await refreshThread();
        const revealAvailable = () => composerEpoch === epoch && loadDraft(ctx) === null && !pageSelection();
        const mayReveal = () => revealAvailable() && currentIntent();
        const shouldReveal = mayReveal();
        if (shouldReveal) {
          const destination = await revealSent({
            part: "thread",
            focus: true,
            travel: false,
            flash: false,
            intent: restrictUserIntent(currentIntent, revealAvailable),
            origin
          });
          const thread = destination && closestAcross(destination, THREAD);
          if (mayReveal() && thread) currentIntent.handoff(() => landSent(thread));
        }
      }
    });
    fabSuggest.onclick = () => {
      setResponseOptions(false);
      setSuggestionMode(!suggestionMode);
    };
    fabOptions.addEventListener("toggle", () => {
      if (!isNativeLayer(fabOptions)) setResponseOptions(false);
    });
    onStanding((node) => {
      if (node && responseOptionsOpen && !fabBar.contains(node))
        setResponseOptions(false);
    });
    fab.onclick = () => {
      if (!fabAnchorAt()) return;
      openComposer(fabAnchorAt(), "");
    };
  }
  const RESPONSE_OPTIONS_TITLE = "With other responses open";
  const RESPONSE_REACTION = {
    id: "response.reaction.choose",
    touch: false,
    ready: savedReadingSettled,
    keys: () => reactionTokens2().slice(0, 9).map((_, index) => String(index + 1)),
    label: () => {
      const count = Math.min(reactionTokens2().length, 9);
      return count > 1 ? `1\u2013${count}` : "1";
    },
    description: () => reactionTokens2().slice(0, 9).map(([name, entry], index) => `${index + 1} ${entry.glyph} ${name}`).join(", "),
    title: "react",
    when: () => reactionAvailable2() && !takesLetters(focused()) && responseReactionButtons().length > 0,
    run: (binding) => responseReactionButtons()[+binding - 1]?.click()
  };
  const RESPONSE_MOVE = {
    id: "response.move",
    touch: false,
    keys: ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"],
    title: "move",
    repeat: true,
    when: () => focusedResponseOption(),
    run: stepResponseOptions
  };
  const RESPONSE_ACTIVATE = {
    id: "response.activate",
    touch: false,
    keys: PRESS,
    title: "choose",
    when: () => focusedResponseOption() && (!focused().classList.contains("lf-react") || reactionAvailable2()),
    run: () => focused()?.click()
  };
  const RESPONSE_CLOSE = {
    id: "response.close",
    touch: false,
    keys: ["Escape"],
    title: "close",
    // Closing the other responses hands the user back to the bar they opened them from.
    run: () => closeLayer(
      () => setResponseOptions(false),
      () => {
        const back = [fabInput, fab].find((control) => control.checkVisibility());
        if (back) focusDestination(back, "return");
      }
    )
  };
  const responseOptionRows = () => [
    RESPONSE_REACTION,
    RESPONSE_MOVE,
    RESPONSE_ACTIVATE,
    RESPONSE_CLOSE
  ];
  pageScope("response options", {
    title: RESPONSE_OPTIONS_TITLE,
    escape: "inner",
    at: () => responseOptionsAreOpen() && focused() === fabInput,
    rows: responseOptionRows()
  });
  function declareResponseOptionKeys() {
    keys(fabOptions, RESPONSE_OPTIONS_TITLE, responseOptionRows(), {
      when: responseOptionsAreOpen,
      escape: "inner"
    });
  }
  return {
    pendingComposer,
    draftDrawing,
    heldDrawings,
    watchHeldDrawings,
    setDraftDrawing,
    draftKey: composerCtx,
    composerHolds,
    responseOptionsAreOpen,
    responseOptionsAvailable,
    setResponseOptions,
    syncResponseOptions,
    resetResponseOptions,
    openComposer,
    openComposerWithMedia,
    hideComposer,
    detachComposer,
    carryComposerToReply,
    openDraft,
    mount
  };
}

// runtime/keyboard/control-keys.js
var stepsBefore = (scope) => word(scope?.sequencePrefix ?? scope?.sequence) ?? [];
var stepsIn = (scope, row) => [...stepsBefore(scope), labelOf(row)].filter(Boolean);
function commandSteps(id) {
  for (const scope of pageScopes())
    for (const row of scope?.rows ?? [])
      if (row.id === id && bindings(row).length) return stepsIn(scope, row);
  return [];
}
function* namedControls(row) {
  if (row.control)
    yield {
      control: row.control,
      active: live(row) && bindings(row).length > 0,
      press: labelOf(row),
      shortcuts: () => ariaShortcuts([row], false)
    };
  for (const route of commandRoutes(row))
    if (route.control)
      yield {
        control: route.control,
        active: commandAvailable(row, route) && bindings(row).includes(route.binding),
        press: spell(route.binding),
        shortcuts: () => ariaShortcuts([{ keys: [route.binding] }], false)
      };
}
function controlRows() {
  const controls = /* @__PURE__ */ new Map();
  for (const scope of pageScopes())
    for (const row of scope?.rows ?? [])
      for (const named of namedControls(row)) {
        const control = word(named.control);
        if (!control) continue;
        const prior = controls.get(control);
        if (!prior || !prior.active && named.active)
          controls.set(control, { scope, ...named });
      }
  return controls;
}
function paintCoreControls() {
  for (const [control, { scope, active, press, shortcuts }] of controlRows()) {
    if (!("lfKeyTitle" in control.dataset)) control.dataset.lfKeyTitle = control.title;
    const steps = [...stepsBefore(scope), press].filter(Boolean).join(" ");
    keeps(control, "title", control.dataset.lfKeyTitle + (active ? ` (${steps})` : ""));
    if (buttonCommand(control)) continue;
    keeps(control, "aria-keyshortcuts", active && !scope.sequence ? shortcuts() : null);
  }
}

// runtime/references.js
function requireReference(verb, owner, attribute) {
  if (typeof attribute !== "string" || !Object.hasOwn(registry[owner.localName]?.["x-refers"] ?? {}, attribute))
    throw new TypeError(
      `${verb} ${owner.localName} attribute ${String(attribute)} is not declared by x-refers`
    );
}
function referencedProjection(owner, attribute, id = owner.getAttribute(attribute)) {
  if (!id) return null;
  const { tag, key } = registry[owner.localName]["x-refers"][attribute];
  if (tag) {
    const within = registry[tag]["x-unique"][key];
    const scopeOf = (element) => element.parentElement?.closest(within) ?? null;
    const scope2 = scopeOf(owner);
    return [...scope2?.querySelectorAll(tag) ?? []].find(
      (member) => scopeOf(member) === scope2 && member.getAttribute(key) === id
    ) ?? null;
  }
  const scope = authoredScope(owner);
  const page = pageDocument();
  return (scope ? elementById(id, scope) : null) ?? (scope === page || !page ? null : elementById(id, page));
}

// runtime/anchor-travel.js
var scrollingBoxFor = (element) => scrollersOf(element).next().value ?? null;
function scrollToFragment(element) {
  scrollIntoView(element, { behavior: "auto", block: "start" });
}
function createAnchorTravel({
  anchors,
  refreshThread,
  focusForNavigation,
  threadFocusTarget,
  announce: announce2
}) {
  let travelIntent = 0;
  const retainTravel = (retained = retainUserIntent()) => {
    const intent = ++travelIntent;
    return restrictUserIntent(retained, () => intent === travelIntent);
  };
  const journeyPrefix = `${performance.timeOrigin}:`;
  let trips = 0;
  let journey = null;
  onReadingInput((node) => {
    if (!journey || closestAcross(node, `${PRESSES},${PRESSABLE}`) || typesText(node))
      return;
    const passage = passageBlock(node);
    if (!passage) return;
    if (passage !== journey.passage()) journey = null;
  });
  function stillLanded() {
    const where = journey && history.state?.lfJourney === journey.token && journey.landing();
    return Boolean(where && seenOf(where));
  }
  async function arrive(resolve, { intent, present = null, departure = null }) {
    const initial = intent() && resolve();
    if (!initial?.where) return false;
    if (initial.scroll.length)
      await stopScroll(
        /* @__PURE__ */ new Set([
          pageScroller,
          ...unconcealedReadingRegions().map((region) => region.body)
        ])
      );
    if (!intent()) return false;
    const first = resolve();
    const holder = first && placeHolder(first.where);
    if (!holder || !intent()) return false;
    const disclosures = [holder, ...first.reveal ?? []].map(
      (target) => reveal(target, intent)
    );
    const replacedView = disclosures.some((disclosure) => disclosure.replacedView);
    const place = (complete = false) => {
      let completed = false;
      intent.handoff(() => {
        const destination = resolve();
        if (!destination?.where) return;
        if (destination.focus)
          focusForNavigation(destination.focus, "move", { caret: destination.caret });
        const current = resolve();
        if (!current?.where) return;
        if (complete) departure?.commit();
        if (current.selection) {
          const { range, backward } = current.selection;
          const head = [range.startContainer, range.startOffset];
          const tail = [range.endContainer, range.endOffset];
          selectEnds(...backward ? [tail, head] : [head, tail]);
        }
        for (const placement of current.scroll) placeScroll(placement, replacedView);
        completed = true;
      });
      return completed;
    };
    if (replacedView) place();
    await Promise.all(disclosures.map((disclosure) => disclosure.ready));
    if (!intent()) return false;
    if (present) await present();
    if (!intent()) return false;
    return place(true);
  }
  async function restoreSelection(anchor, { backward, intent }) {
    const mayArrive = retainTravel(intent);
    const resolve = () => {
      const target = resolveAnchor(anchor);
      const segments = targetSegments(target);
      if (!segments.length) return null;
      const range = rangeOf(segments);
      return {
        where: range,
        focus: targetPlace(target),
        selection: { range, backward },
        scroll: [{ at: range }]
      };
    };
    const destination = resolve();
    const source = anchor.datum && sectionOf(anchor);
    if (!destination && !source) return false;
    const departure = prepareTrip({
      intent: mayArrive,
      landing: () => resolve()?.where
    });
    departure.plan(destination?.where ?? source, {
      there: (readable) => Boolean(destination && readable(destination.where))
    });
    if (source) {
      const hydration = revealAddressed(source, anchor.datum);
      if (hydration?.then) await hydration;
      if (!mayArrive() || sectionOf(anchor) !== source) return false;
    }
    return arrive(resolve, { intent: mayArrive, departure });
  }
  async function arriveEditor(resolve, { intent, caret }) {
    const mayArrive = retainTravel(intent);
    const destination = resolve();
    if (!destination?.where) return null;
    const departure = prepareTrip({
      intent: mayArrive,
      landing: () => resolve()?.where
    });
    departure.plan(destination.where);
    let release = null;
    await arrive(
      () => {
        const current = resolve();
        const input = current?.input();
        return current && {
          where: current.where,
          focus: input,
          caret,
          // The place the words are about comes into view first and the editor
          // last, so a place taller than the window, as a reviewed case is on a
          // phone, never scrolls the caret back out of it.
          scroll: input ? [
            {
              at: current.where,
              behavior: "instant",
              when: () => !readableDestination(current.where) || !readableDestination(input)
            },
            // The subject and editor can occupy different parts of a tall
            // page. Finish on the box the user asked to write in.
            { at: input, block: "nearest", behavior: "instant" }
          ] : [{ at: current.where, behavior: "instant" }]
        };
      },
      {
        intent: mayArrive,
        departure,
        present: async () => {
          const current = resolve();
          if (!current) return;
          if (current.open)
            mayArrive.handoff(() => {
              release = current.open();
            });
          await current.present?.();
        }
      }
    );
    if (typeof release === "function") release();
    return mayArrive() ? resolve()?.input() ?? null : void 0;
  }
  function prepareTrip({ landing = null, url, intent }) {
    const write2 = prepareEntry();
    const continuing = landing && stillLanded();
    const arrival = landing && {
      landing,
      passage: () => openingPassage(landing())
    };
    let moving;
    return {
      plan(where, { there = (readable) => readable(where) } = {}) {
        moving = !(where && there(readableDestination));
        return moving;
      },
      commit() {
        if (moving === void 0) return;
        if (!moving) {
          if (continuing) Object.assign(journey, arrival);
          return;
        }
        journey = arrival && {
          token: journeyPrefix + ++trips,
          ...arrival
        };
        write2(
          url ?? window.location.href,
          journey && { lfJourney: journey.token },
          continuing
        );
      }
    };
  }
  function followFragment(url) {
    const where = fragmentTarget(url.hash);
    return where && fragmentTrip(url, true);
  }
  function returnToFragment(url) {
    const where = fragmentTarget(url.hash);
    return where && !where.checkVisibility() ? fragmentTrip(url, false) : null;
  }
  function fragmentTrip(url, focus) {
    const mayArrive = retainTravel();
    return () => arrive(
      () => {
        const where = fragmentTarget(url.hash);
        return where && {
          where,
          focus: focus ? where : null,
          scroll: [{ at: where, block: "fragment" }]
        };
      },
      { intent: mayArrive }
    );
  }
  async function navigateToDatum2(owner, attribute, key, { success = "", missing = "", focus = true } = {}) {
    const mayArrive = retainTravel();
    requireReference("navigateToDatum", owner, attribute);
    if (typeof key !== "string" || !key)
      throw new TypeError("navigateToDatum key must be a non-empty string");
    let source = referencedProjection(owner, attribute);
    if (!source) {
      if (missing) announce2(missing);
      return false;
    }
    const url = new URL(window.location.href);
    url.hash = source.id;
    const departure = prepareTrip({ url, intent: mayArrive });
    const hydration = revealAddressed(source, key);
    if (hydration?.then) await hydration;
    if (!mayArrive()) return false;
    source = referencedProjection(owner, attribute);
    if (!source) {
      if (missing) announce2(missing);
      return false;
    }
    const destination = addressedElements(source, key)[0] ?? null;
    departure.plan(destination);
    if (!destination) {
      await arrive(
        () => {
          const where = referencedProjection(owner, attribute);
          return where && { where, focus: null, scroll: [{ at: where, block: "start" }] };
        },
        { intent: mayArrive, departure }
      );
      if (mayArrive() && missing) announce2(missing);
      return false;
    }
    const arrived = await arrive(
      () => {
        const source2 = referencedProjection(owner, attribute);
        const where = source2 && addressedElements(source2, key)[0];
        return where && {
          where,
          focus: focus ? where : null,
          scroll: [
            { at: where, block: "start", when: () => !readableDestination(where) }
          ]
        };
      },
      { intent: mayArrive, departure }
    );
    if (mayArrive() && (arrived ? success : missing))
      announce2(arrived ? success : missing);
    return arrived;
  }
  function placeScroll({ at, align = at, block = "center", behavior = scrollBehavior(), when }, replacedView) {
    if (when && !when()) return;
    if (block === "fragment") scrollToFragment(at);
    else
      scrollIntoView(at, {
        alignment: align,
        behavior: replacedView ? "instant" : behavior,
        block
      });
  }
  function scrollToElement(element, behavior = scrollBehavior(), block = "center") {
    const { replacedView } = reveal(element, retainUserIntent());
    placeScroll({ at: element, behavior, block }, replacedView);
  }
  function seenOf(where) {
    const holder = placeHolder(where);
    if (!holder) return null;
    const destination = placeBox(where);
    const seen2 = clippedPlace(where, /* @__PURE__ */ new Map(), destination);
    return seen2 && { holder, destination, seen: seen2 };
  }
  function readableDestination(where) {
    const shown = seenOf(where);
    if (!shown) return false;
    const { holder, destination, seen: seen2 } = shown;
    const box = scrollingBoxFor(holder);
    const band = box ? landingBand(box) : shownBox(pageScroller);
    const close = (a, b) => Math.abs(a - b) <= 0.5;
    return destination.top >= band.top - 0.5 && destination.bottom <= band.bottom + 0.5 && close(seen2.top, destination.top) && close(seen2.right, destination.right) && close(seen2.bottom, destination.bottom) && close(seen2.left, destination.left);
  }
  function scrollToRange(where, behavior = scrollBehavior()) {
    const holder = placeHolder(where);
    if (!holder) return;
    const { replacedView } = reveal(holder, retainUserIntent());
    placeScroll({ at: where, behavior }, replacedView);
  }
  const threadDestination = (id) => {
    const placement = anchors.placedAt(id);
    const segment = targetSegments(placement)[0];
    const where = segment ? rangeOf([segment]) : targetElement(placement) ?? targetPlace(placement);
    return livePoint(targetElement(placement) ?? targetPlace(placement), placement?.point) ?? where;
  };
  async function scrollToThread(id, { part = null, focus = true, presented: presented2 = null, intent } = {}) {
    const mayArrive = retainTravel(intent);
    const thread = threadNamed(id);
    const anchor = thread?.anchor;
    const status = anchors.placedAt(id)?.status;
    const hydrating = anchor?.datum && status !== "outdated" || anchor?.visual;
    const destination = threadDestination(id);
    const landing = () => threadDestination(id);
    const departure = prepareTrip({ landing, intent: mayArrive });
    if (destination || hydrating) departure.plan(destination);
    if (hydrating) {
      const source = sectionOf(anchor);
      const hydration = source && revealAddressed(source, anchor.visual ?? anchor.datum);
      if (hydration?.then) await hydration;
      if (!mayArrive() || sectionOf(anchor) !== source) return false;
      await refreshThread();
      if (!mayArrive()) return false;
    }
    return arrive(
      () => {
        const where = threadDestination(id);
        if (!where) return null;
        const target = focus && part && threadFocusTarget(id, { part });
        return {
          where,
          focus: target,
          scroll: [
            ...target ? [{ at: target, block: "nearest" }] : [],
            { at: where, when: () => !readableDestination(where) }
          ]
        };
      },
      {
        intent: mayArrive,
        departure,
        present: async () => {
          if (presented2) await presented2;
          if (mayArrive()) await refreshThread();
        }
      }
    );
  }
  return {
    prepareTrip,
    arrive,
    arriveEditor,
    restoreSelection,
    followFragment,
    returnToFragment,
    navigateToDatum: navigateToDatum2,
    scrollToElement,
    readableDestination,
    scrollToRange,
    scrollToThread,
    threadDestination
  };
}

// runtime/carry.js
var holdsValue = (node) => node.matches(TEXT_BOX) || node.tagName === "INPUT" && node.type !== "file";
var holdsTick = (node) => node.tagName === "INPUT" && (node.type === "checkbox" || node.type === "radio");
function captureCarry(root, authored2) {
  const active = focused(document);
  const partOwner = active?.hasAttribute("data-lf-carry") ? active.parentElement?.closest("[id]") : null;
  const records = [];
  const held = /* @__PURE__ */ new Map();
  const regionBodies = new Set(readingRegions().map(({ body }) => body));
  for (const node of root.querySelectorAll("[id]")) {
    const wrote2 = authored2.querySelector(`#${CSS.escape(node.id)}`);
    if (wrote2?.localName !== node.localName) continue;
    const record = { id: node.id, name: node.localName };
    const focusPart = node === partOwner;
    if (node === active || focusPart) {
      record.focus = true;
      if (focusPart) {
        record.part = active.getAttribute("data-lf-carry");
        record.partName = active.localName;
      }
    }
    if (node.localName === "details" && node.open !== wrote2.open)
      record.open = node.open;
    if (!skipped(node)) {
      if (node.scrollTop && !regionBodies.has(node)) record.scrollTop = node.scrollTop;
      if (node.scrollLeft) record.scrollLeft = node.scrollLeft;
    }
    if (holdsValue(node) && node.value !== wrote2.value) record.value = node.value;
    if (holdsTick(node) && node.checked !== wrote2.checked)
      record.checked = node.checked;
    if (node === active || focusPart) {
      const caret = readCaret(active);
      if (caret) record.caret = caret;
    }
    if (Object.keys(record).length === 2) continue;
    records.push(record);
    held.set(record.id, node);
  }
  return { records, held };
}
function restoreCarry(records, held = /* @__PURE__ */ new Map(), handoffFocus = (move2) => move2()) {
  const positions = [];
  for (const record of records ?? []) {
    const arrived = document.getElementById(record.id);
    if (!arrived || arrived === held.get(record.id)) continue;
    if (arrived.localName !== record.name) continue;
    if (record.open !== void 0)
      arrived.open = record.open;
    if (record.value !== void 0 && holdsValue(arrived)) arrived.value = record.value;
    if (record.checked !== void 0 && holdsTick(arrived))
      arrived.checked = record.checked;
    positions.push([arrived, record]);
  }
  const restoreFocus = (parts) => handoffFocus(() => {
    for (const [arrived, record] of positions) {
      if (!record.focus || record.part !== void 0 !== parts) continue;
      const target = record.part === void 0 ? arrived : [
        ...arrived.querySelectorAll(
          `[data-lf-carry="${CSS.escape(record.part)}"]`
        )
      ].find(
        (node) => node.parentElement?.closest("[id]") === arrived && node.localName === record.partName
      );
      if (target) focusDestination(target, "return", { caret: record.caret });
    }
  });
  restoreFocus(false);
  return () => {
    for (const [arrived, record] of positions) {
      if (!arrived.isConnected) continue;
      if (record.scrollTop) arrived.scrollTop = record.scrollTop;
      if (record.scrollLeft) arrived.scrollLeft = record.scrollLeft;
    }
    restoreFocus(true);
  };
}

// runtime/version-picker.js
var LATEST_FAILED = "Latest edit couldn't be shown";
var INITIAL_LATEST = "New page available \u2192 open v999";
var VersionPicker = class {
  #activate = null;
  #compare = null;
  #latest = null;
  configure({ activate, compare, latest }) {
    this.#activate = activate;
    this.#compare = compare;
    this.#latest = latest;
  }
  activate(entry) {
    this.#activate?.(entry);
  }
  compare(version) {
    this.#compare?.(version);
  }
  latest() {
    this.#latest?.();
  }
};
var versionPicker = new VersionPicker();
var latestVersionLabel = ({ failed = false, activeLabel = null } = {}) => failed ? LATEST_FAILED : activeLabel ? `New page available \u2192 open ${activeLabel}` : INITIAL_LATEST;

// runtime/version.js
var PRIVATE_REVISION_PARAM = "_leaf-revision";
function authoredAttributes(root) {
  root = document.documentElement.lfInitial.authoredShell(root);
  const attributes = /* @__PURE__ */ new Map();
  for (const { name, value } of root.attributes) {
    if (name.startsWith("data-lf-")) continue;
    if (name === "class") {
      const authoredClasses = [...root.classList].filter((token) => !token.startsWith("lf-")).join(" ");
      if (authoredClasses) attributes.set(name, authoredClasses);
    } else attributes.set(name, value);
  }
  return attributes;
}
var versionedHeadNode = (node) => !node.hasAttribute("data-lf-runtime") && (node.localName === "title" || node.localName === "style" || node.localName === "base" || node.localName === "meta" && (node.hasAttribute("name") || node.hasAttribute("property")) || node.localName === "link");
var pairSources = (source, live2, pairs) => {
  live2 = initialOrigin(source) === source ? live2 : initialOrigin(source);
  pairs.set(source, live2);
  const held = source.localName === "template" ? source.content : source;
  const shown = live2.localName === "template" ? live2.content : live2;
  const children = [...shown.childNodes].filter(
    (child) => !child.matches?.("[data-lf-prepaint], script[data-lf-initial]")
  );
  for (const [at, child] of [...held.childNodes].entries()) {
    const original = initialOrigin(child);
    const peer = original === child ? children[at] : original;
    if (peer) pairSources(child, peer, pairs);
  }
  return pairs;
};
var initialDocument = (() => {
  const main = pageDocument();
  const source = main ? unmarkedCopy(main) : null;
  return {
    authoredBodyAttributes: authoredAttributes(document.body),
    authoredHeadNodes: new Set([...document.head.children].filter(versionedHeadNode)),
    authoredHtmlAttributes: authoredAttributes(document.documentElement),
    source,
    pairs: main ? pairSources(source, main, /* @__PURE__ */ new WeakMap()) : /* @__PURE__ */ new WeakMap()
  };
})();
var stamped = (version) => runtime.versions.find((candidate) => candidate.version === version);
var currentVersionToken = () => runtime.currentStamp === null ? "Draft" : `v${runtime.currentStamp}`;
var draftRevisions = () => {
  const revisions = /* @__PURE__ */ new Set();
  if (runtime.currentStamp === null && runtime.currentRevision !== null)
    revisions.add(runtime.currentRevision);
  if (runtime.active?.version === null) revisions.add(runtime.active.revision);
  return revisions;
};
var versionCount = () => runtime.versions.length + draftRevisions().size;
var versionsOffered = () => versionCount() > 0;
var behindCurrent = () => runtime.active !== null && runtime.currentRevision !== null && !runtime.showsActive;
var shownBehind = () => runtime.currentStamp === null ? "An older draft" : runtime.active.version === null ? `v${runtime.currentStamp}` : `v${runtime.currentStamp} of ${runtime.active.version}`;
function menuRows(state, notes) {
  const latest = state.versions.at(-1)?.version;
  const entries = state.versions.map((entry) => ({
    revision: entry.revision,
    version: entry.version,
    name: `v${entry.version}${entry.version === latest ? " (latest version)" : ""}`,
    note: notes[entry.version] ?? null,
    current: entry.version === runtime.currentStamp,
    active: false,
    comparable: comparable(entry.version)
  }));
  for (const revision of draftRevisions()) {
    const active = revision === state.active.revision;
    entries.push({
      revision,
      version: null,
      name: `${active ? "Current" : "This view"} \xB7 ${revision === runtime.currentRevision ? runtime.currentLabel ?? revisionLabel(revision) : state.active.label}`,
      note: null,
      current: revision === runtime.currentRevision,
      active,
      comparable: false
    });
  }
  entries.sort(
    (left, right) => right.revision - left.revision || (right.version ?? Infinity) - (left.version ?? Infinity)
  );
  return Object.freeze(entries.map((entry) => Object.freeze(entry)));
}
function pickerModel(state) {
  const offered = state !== null && versionsOffered();
  const behind = behindCurrent();
  const sourceFailed = LIVE_ROOT && Boolean(state?.source_error);
  const currentLabel = runtime.currentLabel ?? "Draft";
  const newer = behind ? `; ${runtime.active.label} available` : "";
  return Object.freeze({
    picker: Object.freeze({
      offered,
      token: currentVersionToken(),
      compared: diffOn.value || diffPendingBase.value !== null,
      news: behind,
      keyTitle: offered ? diffPendingBase.value !== null ? `${currentLabel}: loading a comparison with v${diffPendingBase.value}${newer}` : diffOn.value ? `${currentLabel}: showing what changed since v${diffBase.value} \u2014 pick a version, or press Compare again to stop${newer}` : `${currentLabel}: versions; read one, or mark what changed since it${newer}` : currentLabel,
      ariaLabel: offered ? diffPendingBase.value !== null ? `${currentLabel}: loading comparison with v${diffPendingBase.value}; open versions${newer}` : diffOn.value ? `${currentLabel}: comparing with v${diffBase.value}; open versions${newer}` : `${currentLabel}: open versions${newer}` : currentLabel
    }),
    latest: Object.freeze({
      // The agent's latest save failed its check, so the page shows the last one that
      // passed; `error` is what the check said.
      failed: sourceFailed,
      error: sourceFailed ? state.source_error : null,
      disabled: sourceFailed,
      keyTitle: sourceFailed ? state.source_error : "Open the current page",
      label: latestVersionLabel({
        failed: sourceFailed,
        activeLabel: behind ? runtime.active.label : null
      }),
      shown: behind ? shownBehind() : null,
      news: sourceFailed || behind
    }),
    rows: state === null || runtime.active === null ? Object.freeze([]) : menuRows(state, runtime.browser?.version_notes ?? {}),
    selection: Object.freeze({
      base: diffPendingBase.value ?? (diffOn.value ? diffBase.value : null),
      currentRevision: runtime.currentRevision,
      on: diffOn.value,
      pendingBase: diffPendingBase.value,
      baseRevision: stamped(diffBase.value)?.revision ?? null
    })
  });
}
var holdFailedSave = holdingError();
function paintPicker() {
  const model = pickerModel(runtime.state);
  holdFailedSave(
    model.latest.failed ? "Latest edit not shown: it failed its check (see Versions)" : null
  );
  repaint();
}
var versionsReading = () => pickerModel(runtime.state);
registerPageControl({
  key: "versions",
  rank: PAGE_CONTROL_RANK.versions,
  label: "Versions",
  value: () => versionsReading().picker.token,
  shortcut: () => commandSteps("version.open"),
  disabled: () => !versionsReading().picker.offered,
  group: "page"
});
registerPageControl({
  key: "latest",
  rank: PAGE_CONTROL_RANK.latest,
  label: () => versionsReading().latest.label,
  offered: () => versionsReading().latest.news,
  disabled: () => versionsReading().latest.disabled,
  urgent: "new",
  press: () => versionPicker.latest(),
  group: "page"
});
var diffBlockSel = () => [
  TEXT_BLOCK,
  "aside",
  ...tagsDeclaring((e) => e["x-owners"] && (e["x-content"] ?? "markup") === "markup"),
  // Preserving widgets contribute their own prose. The leaf-blocks-only rule
  // below avoids counting nested blocks twice and keeps base and live readings
  // symmetric: a draft's authored <pre> and rendered body key the same words.
  ...tagsDeclaring((e) => e["x-verbatim"])
].join(",");
var diffOpaqueSel = () => [
  ...tagsDeclaring(
    (e) => e["x-upgrade"] && !e["x-verbatim"] && e["x-content"] === "data"
  ),
  // External data is absent from both authored documents. Its seat is opaque, and
  // the authored binding and immutable selector below are the comparison key.
  ...tagsDeclaring((e) => e["x-upgrade"] && e["x-data"]),
  ...Object.entries(registry.$decisions).filter(([, { retires }]) => Object.keys(retires).length).map(([owner]) => owner),
  "svg"
].join(",");
var diffOn = Z(false);
var diffBase = Z(null);
var comparisonGeneration = Z(0);
var diffPendingBase = Z(null);
var diffMarked = /* @__PURE__ */ new Set();
var diffBefore = /* @__PURE__ */ new Map();
var inlineOpen = /* @__PURE__ */ new Map();
var diffRequest = 0;
function diffWords(block) {
  if (!block.querySelector("[data-lf-source-words]")) return wrote(block);
  const source = block.cloneNode(true);
  for (const island of source.querySelectorAll("[data-lf-source-words]"))
    island.replaceWith(document.createTextNode(island.dataset.lfSourceWords));
  return wrote(source);
}
function diffBlocks(root) {
  const pairs = [];
  const [blocks, opaque] = [diffBlockSel(), diffOpaqueSel()];
  const authoredHere = authored(root);
  for (const body of root.querySelectorAll(".lf-markdown-body")) {
    const owner = body.parentElement;
    if (inChrome(owner) || owner.closest(opaque)) continue;
    pairs.push([owner, `markdown:${body.dataset.lfSourceWords}`]);
  }
  for (const b of root.querySelectorAll(blocks)) {
    if (inChrome(b) || b.closest(opaque) || b.closest(".lf-markdown-body")) continue;
    if (b.querySelector(blocks)) continue;
    let key = diffWords(b);
    for (const [attr, edge] of Object.entries(
      registry[b.localName]?.["x-says"] ?? {}
    )) {
      const said = b.getAttribute(attr);
      if (said) key = edge === "before" ? `${said} ${key}` : `${key} ${said}`;
    }
    if (key) pairs.push([b, key]);
  }
  for (const w of root.querySelectorAll(opaque)) {
    if (!authoredHere(w) || inChrome(w) || w.parentElement?.closest(opaque)) continue;
    const entry = registry[w.localName] ?? {};
    const bindingAttrs = /* @__PURE__ */ new Set();
    for (const input of Object.values(entry["x-data"] ?? {})) {
      if (input.source) bindingAttrs.add(input.source);
      if (input.reference) bindingAttrs.add(input.reference);
    }
    const binding = [...bindingAttrs].sort().map((attr) => [attr, w.getAttribute(attr)]);
    pairs.push([w, ` ${w.tagName}#${w.id}${JSON.stringify(binding)}`]);
  }
  return pairs;
}
async function baseReading(baseRevision, throughSeq) {
  const params = new URLSearchParams({
    revision: String(baseRevision),
    through_seq: String(throughSeq)
  });
  const res = await fetch(pageUrl(`api/view?${params}`));
  if (!admitReading(res)) throw new LayerRefused("Leaf changed while comparing");
  if (!res.ok) throw new Error(`couldn't project revision r${baseRevision}`);
  return (await res.json()).browser;
}
function inOrder(before, after) {
  const lengths = before.map(() => after.map(() => 0));
  const at = (i, j) => lengths[i]?.[j] ?? 0;
  for (let i = before.length - 1; i >= 0; i--)
    for (let j = after.length - 1; j >= 0; j--)
      lengths[i][j] = before[i] === after[j] ? at(i + 1, j + 1) + 1 : Math.max(at(i + 1, j), at(i, j + 1));
  const kept = /* @__PURE__ */ new Set();
  for (let i = 0, j = 0; i < before.length && j < after.length; )
    if (before[i] === after[j]) {
      kept.add(before[i]);
      i++;
      j++;
    } else if (at(i + 1, j) >= at(i, j + 1)) i++;
    else j++;
  return kept;
}
function applyDiff(doc, baseAuthored, baseVersion, baseReading2) {
  const baseView = baseReading2.views[String(stamped(baseVersion).revision)];
  const baseProjection = projectView(baseView);
  const declaredAlike = ({ e, spec }) => {
    const current = baseAuthored.get(e.widget)?.specs.get(e.action);
    return current?.unit === spec.unit && JSON.stringify(current.record ?? null) === JSON.stringify(spec.record ?? null);
  };
  const baseWidgets = foldWidgetStates(baseAuthored, {
    ...baseProjection,
    desired: new Map(
      [...baseProjection.desired].filter(([, entry]) => declaredAlike(entry))
    )
  });
  for (const [id, { state, specs }] of baseWidgets)
    for (const [verb, spec] of specs) {
      if (spec.record?.kind !== "body" || !/** @type {{action: string | null}} */
      state[verb].action)
        continue;
      const body = doc.getElementById(id)?.querySelector(":scope > .lf-markdown-body");
      if (body) paintMarkdown(body, state[verb].value);
    }
  const base = /* @__PURE__ */ new Map();
  for (const [, key] of diffBlocks(doc)) base.set(key, (base.get(key) ?? 0) + 1);
  for (const [b, key] of diffBlocks(document.body)) {
    const left = base.get(key) ?? 0;
    if (left > 0) base.set(key, left - 1);
    else {
      b.classList.add("lf-ins-block");
      diffMarked.add(b);
    }
  }
  const mark = (target) => {
    if (diffMarked.has(target)) return;
    target.classList.add("lf-ins-block");
    diffMarked.add(target);
  };
  for (const [id, now] of readApplication().effective.widgets) {
    const before = baseWidgets.get(id);
    const widget = elementById(id);
    if (!before || !widget || inChrome(widget) || quoted(widget)) continue;
    for (const [verb, spec] of now.specs) {
      if (!spec.record || spec.record.kind === "body" || !before.specs.has(verb))
        continue;
      if (spec.record.kind === "position") {
        const was = before.state[verb].value;
        const placed = Object.values(was).flat();
        for (const [container, ids2] of Object.entries(now.state[verb].value)) {
          const stayed = was[container] ?? [];
          const kept = inOrder(
            stayed.filter((unit) => ids2.includes(unit)),
            ids2.filter((unit) => stayed.includes(unit))
          );
          for (const unit of ids2) {
            if (!placed.includes(unit) || kept.has(unit)) continue;
            const moved2 = elementById(unit);
            if (moved2) mark(moved2);
          }
        }
        continue;
      }
      const { value } = obligationValue(now, verb, true);
      if (JSON.stringify(value) === JSON.stringify(obligationValue(before, verb, true).value))
        continue;
      const ids = (
        /** @type {string[]} */
        value
      );
      const picked = spec.record.kind === "attribute" && ids.length === 1 ? elementById(ids[0]) : null;
      mark(picked ?? widget);
    }
  }
  const opaque = diffOpaqueSel();
  for (const block of diffMarked) {
    if (!block.matches(ADDRESSABLE) || block.closest(opaque)) continue;
    const baseBlock = doc.getElementById(block.id);
    diffBefore.set(block, baseBlock ? wrote(baseBlock) : null);
  }
  return diffMarked.size;
}
var inlineId = (target) => `lf-version-inline-${target.id}`;
var authoredReading = (target) => readingFrom(textNodesUnder(target, "wrote"));
function pointAt(target, reading, offset) {
  if (!reading.units.length) return { node: target, offset: 0 };
  return offset === reading.units.length ? reading.units.at(-1).end : reading.units[offset].start;
}
function insertAt(target, reading, offset, node) {
  const point = pointAt(target, reading, offset);
  if (point.node.nodeType === Node.ELEMENT_NODE) {
    move(point.node, node, point.node.childNodes[point.offset] ?? null);
    return;
  }
  const text = point.node;
  if (point.offset === 0) move(text.parentNode, node, text);
  else if (point.offset === text.data.length)
    move(text.parentNode, node, text.nextSibling);
  else move(text.parentNode, node, text.splitText(point.offset));
}
function rangeAt(reading, start, end) {
  const first = reading.units[start];
  const last = reading.units[end - 1];
  if (!first || !last) return null;
  const range = document.createRange();
  range.setStart(first.start.node, first.start.offset);
  range.setEnd(last.end.node, last.end.offset);
  return range;
}
function paintInlineInsertions() {
  const ranges = [...inlineOpen.values()].flatMap((entry) => entry.ranges);
  if (ranges.length) CSS.highlights.set("lf-version-insert", new Highlight(...ranges));
  else CSS.highlights.delete("lf-version-insert");
}
function openInlineComparison(target) {
  const before = diffBefore.get(target);
  const reading = authoredReading(target);
  const current = currentVersionToken();
  const label = el(
    "span",
    "lf-ui lf-quiet lf-version-inline-label",
    before === null ? `New since v${diffBase.value}` : `v${diffBase.value} \u2192 ${current}`
  );
  label.id = inlineId(target);
  label.setAttribute(
    "aria-label",
    before === null ? `New since version ${diffBase.value}` : `Inline comparison from version ${diffBase.value} to ${current}`
  );
  const nodes = [label];
  const additions = [];
  const insertions = [{ offset: 0, node: label }];
  let afterOffset = 0;
  let hasTextChange = false;
  for (const run of before === null ? [] : alignInlineText(before, reading.text)) {
    if (run.kind === "delete") {
      const dropped = el("span", "lf-ui lf-version-inline-deletion");
      dropped.append(el("del", "", run.text));
      nodes.push(dropped);
      insertions.push({ offset: afterOffset, node: dropped });
      hasTextChange = true;
    } else {
      const length = [...run.text].length;
      if (run.kind === "insert") {
        additions.push([afterOffset, afterOffset + length]);
        hasTextChange = true;
      }
      afterOffset += length;
    }
  }
  insertions.sort((left, right) => right.offset - left.offset).forEach(({ offset, node }) => insertAt(target, reading, offset, node));
  const currentReading = authoredReading(target);
  const ranges = additions.map(([start, end]) => rangeAt(currentReading, start, end)).filter(Boolean);
  target.classList.toggle("lf-version-inline", hasTextChange);
  inlineOpen.set(target, { nodes, ranges });
  paintInlineInsertions();
  layoutChanged(target);
  return before === null ? `v${diffBase.value} had nothing here` : `showing an inline diff from v${diffBase.value}`;
}
function closeInlineComparison(target) {
  const entry = inlineOpen.get(target);
  inlineOpen.delete(target);
  target.classList.remove("lf-version-inline");
  for (const node of entry?.nodes ?? []) node.remove();
  paintInlineInsertions();
  layoutChanged(target);
  return `inline diff from v${diffBase.value} hidden`;
}
var inlineComparison = (target) => diffOn.value && diffBefore.has(target) && (diffBefore.get(target) === null || diffBefore.get(target) !== wrote(target)) ? {
  id: inlineId(target),
  open: inlineOpen.has(target),
  offer: `v${diffBase.value} \u2192 ${currentVersionToken()}`
} : null;
function toggleInlineComparison(target) {
  if (!inlineComparison(target)) return null;
  const said = inlineOpen.has(target) ? closeInlineComparison(target) : openInlineComparison(target);
  comparisonGeneration.value += 1;
  return said;
}
var comparable = (version) => {
  const base = stamped(version);
  return runtime.currentRevision !== null && base !== void 0 && base.revision < runtime.currentRevision;
};
function setDiff(on, base, pendingBase = null) {
  W(() => {
    diffOn.value = on;
    diffPendingBase.value = pendingBase;
    if (on) diffBase.value = base;
    if (!on) {
      diffRequest++;
      for (const target of [...inlineOpen.keys()]) closeInlineComparison(target);
      diffBefore.clear();
      for (const b of diffMarked) b.classList.remove("lf-ins-block");
      diffMarked.clear();
    }
    comparisonGeneration.value += 1;
  });
}
async function showComparison(base) {
  setDiff(false, null, base);
  const mine = ++diffRequest;
  const baseVersion = stamped(base);
  const baseRevision = baseVersion?.revision;
  if (baseRevision == null) {
    diffPendingBase.value = null;
    raiseError(`Couldn't load v${base}`);
    return;
  }
  const documentRequest = authoredDocument(baseVersion.url);
  let doc;
  let reading;
  let baseAuthored;
  try {
    while (mine === diffRequest) {
      const throughSeq = runtime.lastEventSeq;
      [doc, reading] = await Promise.all([
        documentRequest,
        baseReading(baseRevision, throughSeq)
      ]);
      if (mine !== diffRequest) return;
      if (runtime.lastEventSeq === throughSeq) break;
    }
    if (mine !== diffRequest) return;
    baseAuthored = stageAuthoredStates(doc, /* @__PURE__ */ new Map());
    await prepareDeclaredMarkdown(doc);
  } catch {
    if (mine === diffRequest) {
      diffPendingBase.value = null;
      raiseError(`Couldn't load v${base}`);
    }
    return;
  }
  if (mine !== diffRequest) return;
  const n = applyDiff(doc, baseAuthored, base, reading);
  setDiff(true, base);
  notice(
    n ? `${n} changed passage${n === 1 ? "" : "s"} since v${base}` : `No text changes since v${base}`
  );
}
var pressComparison = (base) => diffOn.value && base === diffBase.value || diffPendingBase.value === base ? setDiff(false) : showComparison(base);
var comparisonBase = () => diffOn.value ? diffBase.value : null;
var selectedBase = () => diffPendingBase.value ?? comparisonBase();
function comparisonChanges(owner = null) {
  comparisonGeneration.value;
  const changes = diffOn.value ? [...diffMarked] : [];
  return owner ? changes.filter((block) => block !== owner && under(block, owner)) : changes;
}
async function authoredDocument(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`couldn't load ${url} (${response.status})`);
  const doc = new DOMParser().parseFromString(await response.text(), "text/html");
  return restoreInitialSource(doc);
}
var revisionDocuments = /* @__PURE__ */ new Map();
function revisionDocument(revision) {
  if (!revisionDocuments.has(revision.revision))
    revisionDocuments.set(
      revision.revision,
      authoredDocument(revision.url).catch((error) => {
        revisionDocuments.delete(revision.revision);
        throw error;
      })
    );
  return revisionDocuments.get(revision.revision);
}
function createVersionController({
  compositionInput,
  openThread,
  refreshThread,
  midComposition,
  hasPending,
  readAndApply,
  syncLayout,
  captureRetainedStanding = () => null,
  restoreRetainedStanding = () => false,
  captureObligationStanding = () => null,
  restoreObligationStanding = () => {
  },
  // The chrome's Versions, which `g V` opens or puts away (floating-panel.js, `doors`).
  versions
}) {
  let {
    authoredBodyAttributes,
    authoredHeadNodes,
    authoredHtmlAttributes,
    source: authoredSource
  } = initialDocument;
  const sourcePairs = initialDocument.pairs;
  initialDocument = null;
  let authoredWidgets = servedWidgets;
  let authoredRoot = layerRoot(document);
  const VIEW_KEY = "lf-view";
  const HANDOFF_KEY = "lf-revision-handoff";
  const PICKER = {
    id: "version.open",
    ready: savedReadingSettled,
    keys: ["Shift+v"],
    title: "versions",
    run: () => versions.press(),
    // The same predicate the menu's Escape stands on, so the key cannot open a layer the
    // way out is not live over. The walk being empty is the menu's business, not this key's.
    when: versionsOffered
  };
  let forceActivation = false;
  const goVersion = (version) => {
    if (version === runtime.currentStamp) return;
    const target = stamped(version);
    if (!target) return;
    const url = new URL(target.url, location.href);
    url.searchParams.set("pin", "");
    location.href = url.href;
  };
  const goActive = () => {
    if (!runtime.active) return;
    if (LIVE_ROOT) {
      if (runtime.showsActive) return;
      forceActivation = true;
      readAndApply();
      return;
    }
    location.href = PAGE_SCOPE || "/";
  };
  function replaceAuthoredAttributes(target, source, prior) {
    const runtimeState = runtimeRootState(target);
    const next = authoredAttributes(source);
    const tokens = (value) => new Set(value?.split(" "));
    const nextTokens = tokens(next.get("class"));
    for (const token of tokens(prior.get("class")))
      if (!nextTokens.has(token)) target.classList.remove(token);
    for (const token of nextTokens)
      if (!target.classList.contains(token)) target.classList.add(token);
    const declared = new Set(source.style);
    const priorStyle = document.createElement(target.localName).style;
    priorStyle.cssText = prior.get("style") ?? "";
    for (const property of priorStyle)
      if (!runtimeState.styles.has(property) && !declared.has(property))
        target.style.removeProperty(property);
    const existing = new Set(target.style);
    for (const property of declared) {
      if (runtimeState.styles.has(property)) continue;
      const value = source.style.getPropertyValue(property);
      const priority = source.style.getPropertyPriority(property);
      if (!existing.has(property) || target.style.getPropertyValue(property) !== value || target.style.getPropertyPriority(property) !== priority)
        target.style.setProperty(property, value || " ", priority);
    }
    const plain = (name) => name !== "class" && name !== "style" && !runtimeState.attributes.has(name);
    for (const name of prior.keys())
      if (plain(name) && !next.has(name)) target.removeAttribute(name);
    for (const [name, value] of next) if (plain(name)) keeps(target, name, value);
    return next;
  }
  function activateHead(doc, revision) {
    const source = [...doc.head.children].filter(versionedHeadNode);
    const current = [...document.head.children].filter(
      (node) => authoredHeadNodes.has(node)
    );
    if (current.length !== authoredHeadNodes.size || current.length !== source.length || current.some((node, index) => !node.isEqualNode(source[index]))) {
      for (const node of authoredHeadNodes) node.remove();
      const next = /* @__PURE__ */ new Set();
      for (const node of source) {
        const imported = document.importNode(node, true);
        document.head.append(imported);
        next.add(imported);
      }
      authoredHeadNodes = next;
    }
    let marker2 = document.querySelector('meta[name="lf-revision"][data-lf-runtime]');
    if (!marker2) {
      marker2 = document.createElement("meta");
      marker2.name = "lf-revision";
      marker2.dataset.lfRuntime = "1";
      document.head.append(marker2);
    }
    marker2.content = String(revision.revision);
  }
  const upgraded = (element) => Boolean(registry[element.localName]?.["x-upgrade"]);
  function widgetKeys(source) {
    const keys2 = /* @__PURE__ */ new Map();
    const counts = /* @__PURE__ */ new Map();
    for (const element of elementsWithin(source)) {
      if (!upgraded(element)) continue;
      if (element.id) keys2.set(element, element.id);
      else {
        const seen2 = counts.get(element.localName) ?? 0;
        counts.set(element.localName, seen2 + 1);
        keys2.set(element, `${element.localName}#${seen2}`);
      }
    }
    return keys2;
  }
  function* elementsWithin(root) {
    const inner = root.localName === "template" ? root.content : root;
    for (const child of inner.children) {
      yield child;
      yield* elementsWithin(child);
    }
  }
  const RESOURCE_ATTRIBUTES = ["src", "href", "srcset", "poster", "data", "style"];
  const unrooted = (value, root) => root && value.includes(root) ? value.split(root).join("/") : value;
  const sameValue = (name, held2, value, arrivingRoot) => RESOURCE_ATTRIBUTES.includes(name) ? unrooted(held2, authoredRoot) === unrooted(value, arrivingRoot) : held2 === value;
  function sameAuthoredMarkup(before, after, arrivingRoot) {
    const strip = (element, root) => {
      const copy = element.cloneNode(true);
      if (!root) return copy;
      for (const node of [copy, ...elementsWithin(copy)])
        for (const name of RESOURCE_ATTRIBUTES) {
          const value = node.getAttribute(name);
          if (value?.includes(root)) node.setAttribute(name, unrooted(value, root));
        }
      return copy;
    };
    return strip(before, authoredRoot).isEqualNode(strip(after, arrivingRoot));
  }
  const shell = (element) => {
    const copy = element.cloneNode(false);
    for (const child of element.childNodes) copy.append(child.cloneNode(false));
    return copy;
  };
  const reachesMembers = (before, after, arrivingRoot) => registry[before.localName]?.["x-patch"] === "members" && sameAuthoredMarkup(shell(before), shell(after), arrivingRoot);
  function patchRules(doc) {
    const source = pageDocument(doc);
    const arrivingWidgets = documentWidgetDigests(doc);
    const arrivingRoot = layerRoot(doc);
    const heldKeys = widgetKeys(authoredSource);
    const arrivingKeys = widgetKeys(source);
    return {
      pairs: sourcePairs,
      contains: under,
      declared: upgraded,
      reaches: (before, after) => reachesMembers(before, after, arrivingRoot),
      unchanged: (before, after) => {
        const digest = authoredWidgets[heldKeys.get(before)];
        return Boolean(digest) && arrivingWidgets[arrivingKeys.get(after)] === digest;
      },
      same: (before, after) => sameAuthoredMarkup(before, after, arrivingRoot),
      sameValue: (name, held2, value) => sameValue(name, held2, value, arrivingRoot)
    };
  }
  function captureEditingContinuity() {
    const draftEditing = captureDraftEditing();
    return {
      draftEditing,
      replyThread: draftEditing?.mirrored ? heldThreadId() : null,
      // A replaced reply box takes focus back either way, but is brought into view only
      // where it marked the user's place (user-place.js, `focusedInView`).
      replyInView: focusedInView() !== null,
      // Obligation standing is the fallback for unnamed controls. An exact editor already
      // has a replacement identity, so its parent obligation does not also own focus.
      obligationStanding: draftEditing ? null : captureObligationStanding()
    };
  }
  async function landContinuity(land) {
    try {
      await land();
    } catch (error) {
      reportPageError(error, `Revision continuity failed`);
    }
  }
  async function restoreEditingContinuity(continuity, currentIntent) {
    if (!currentIntent()) return;
    const { draftEditing, replyThread, replyInView, obligationStanding } = continuity;
    restoreObligationStanding(obligationStanding);
    const mayRestore = restrictUserIntent(
      currentIntent,
      () => draftEditingStands(draftEditing)
    );
    if (!mayRestore()) return;
    if (restoreDraftEditing(draftEditing, focused())) return;
    const input = replyThread ? await restoreReplyEditing(draftEditing, async () => {
      await refreshThread();
      return mayRestore() ? replyDestination(replyThread, openThread, mayRestore, {
        scroll: replyInView
      }) : null;
    }) : draftEditingDestination(draftEditing, mayRestore.handoff);
    if (!replyThread && input)
      mayRestore.handoff(() => focusDestination(input, "return"));
    if (mayRestore()) restoreDraftEditing(draftEditing, input);
  }
  async function activateRevision(doc, target) {
    const currentIntent = retainUserIntent();
    const view = captureView();
    const retainedStanding = captureRetainedStanding();
    const editingContinuity = captureEditingContinuity();
    const comparedFrom = selectedBase();
    if (comparedFrom !== null) setDiff(false);
    const live2 = pageDocument();
    const carry = captureCarry(live2, authoredSource);
    const source = pageDocument(doc);
    const arrivingWidgets = documentWidgetDigests(doc);
    const arrivingRoot = layerRoot(doc);
    const rules = patchRules(doc);
    revisionDocuments.delete(target.revision);
    const isAuthored = authored(live2);
    const generated = (node) => (node.nodeType === Node.ELEMENT_NODE || node.parentElement !== null) && !isAuthored(node);
    const arrived = [];
    const descriptorStages = [];
    const prior = readApplication().document;
    rememberAuthoredParents(source);
    const sourceAuthored = stageAuthoredStates(source, /* @__PURE__ */ new Map());
    const sourceDescriptors = stageWidgetDescriptors(source, {
      kind: "page",
      revision: target.revision
    });
    const touched2 = [];
    const arrive = (node, parent) => {
      const arriving = document.importNode(node, true);
      pairSources(node, arriving, sourcePairs);
      if (arriving.nodeType === Node.ELEMENT_NODE) {
        rememberPassageParts(arriving);
        rememberAuthoredParents(arriving, parent);
        const descriptors2 = stageWidgetDescriptors(arriving, {
          kind: "page",
          revision: target.revision
        });
        descriptorStages.push(descriptors2);
        commitWidgetDescriptors(descriptors2);
        formatDeclaredMarkdown(arriving);
        arrived.push(arriving);
      }
      return arriving;
    };
    let restoreCarryScroll;
    await patchDocument(live2, () => {
      authoredHtmlAttributes = replaceAuthoredAttributes(
        document.documentElement,
        doc.documentElement,
        authoredHtmlAttributes
      );
      keeps(
        document.documentElement,
        "data-lf-layout",
        doc.documentElement.getAttribute("data-lf-layout")
      );
      authoredBodyAttributes = replaceAuthoredAttributes(
        document.body,
        doc.body,
        authoredBodyAttributes
      );
      activateHead(doc, target);
      sourcePairs.set(source, live2);
      patchTree(authoredSource, source, {
        ...rules,
        arrive,
        generated,
        touched: (element) => touched2.push(element)
      });
      keepPageRulesOffLayer();
      restoreCarryScroll = restoreCarry(
        carry.records,
        carry.held,
        currentIntent.handoff
      );
      reindexPassageOwners(live2);
      pruneScopedElements();
      return {
        roots: [...arrived, ...touched2],
        widgets: arrived.flatMap((root) => [root, ...elementsWithin(root)]).filter((element) => upgraded(element) && element.id).map((element) => element.id)
      };
    });
    authoredWidgets = arrivingWidgets;
    authoredSource = source;
    authoredRoot = arrivingRoot;
    const nextAuthored = new Map(
      [...prior.authored].filter(
        ([id]) => prior.descriptors.get(id)?.document.kind === "thread"
      )
    );
    for (const [id, value] of sourceAuthored) nextAuthored.set(id, value);
    const arrivedDescriptors = /* @__PURE__ */ new Map();
    for (const stage of descriptorStages)
      for (const [id, value] of stage.descriptors) arrivedDescriptors.set(id, value);
    const descriptors = /* @__PURE__ */ new Map();
    for (const [id, incoming] of sourceDescriptors.descriptors)
      descriptors.set(
        id,
        arrivedDescriptors.get(id) ?? prior.descriptors.get(id) ?? incoming
      );
    for (const [id, descriptor] of prior.descriptors)
      if (descriptor.document.kind === "thread") descriptors.set(id, descriptor);
    const retired = new Set(
      [...prior.descriptors].filter(
        ([id, descriptor]) => descriptor.document.kind === "page" && !sourceDescriptors.descriptors.has(id)
      ).map(([id]) => id)
    );
    commitWidgetDescriptors({ bindings: [] }, retired);
    return {
      document: {
        ...prior,
        revision: target.revision,
        stamp: target.version ?? null,
        authored: nextAuthored,
        descriptors
      },
      // The incoming publication opens recovered editors. State application alone
      // adopts this capture and proves that epoch before returning mechanical places.
      // This continuation never enters the semantic document snapshot.
      land: () => landContinuity(async () => {
        releaseHolds();
        settleResidency();
        syncLayout();
        if (currentIntent()) {
          restoreView(view, currentIntent);
          restoreRetainedStanding(retainedStanding);
          restoreCarryScroll();
          await restoreEditingContinuity(editingContinuity, currentIntent);
        }
        if (comparedFrom !== null) showComparison(comparedFrom);
        notice(`Updated to ${target.label}`, { background: true });
      })
    };
  }
  async function prepareActivation(state) {
    const target = state.active;
    if (!LIVE_ROOT || runtime.currentRevision === null || target.revision <= runtime.currentRevision)
      return null;
    const activates = (retains) => target.revision > runtime.currentRevision && !hasPending() && (!midComposition(retains) || forceActivation);
    if (!servedExecutable || target.executable !== servedExecutable)
      return {
        revision: target.revision,
        activates: () => activates(),
        install: reloadInto(target)
      };
    let doc;
    try {
      doc = await revisionDocument(target);
      await preloadWidgets(pageDocument(doc));
    } catch (error) {
      reportPageError(error, `revision ${target.revision} failed to load`);
      return null;
    }
    return {
      revision: target.revision,
      activates: () => activates(
        (node) => (
          // Installation closes inline comparisons, which can own the comment’s
          // rendered subject independently of the authored patch.
          selectedBase() === null && patchRetains(authoredSource, pageDocument(doc), node, patchRules(doc))
        )
      ),
      install: () => {
        forceActivation = false;
        return activateRevision(doc, target);
      }
    };
  }
  const reloadInto = (target) => () => {
    forceActivation = false;
    const view = captureView();
    const editingContinuity = captureEditingContinuity();
    tabStore.set(VIEW_KEY, JSON.stringify(view));
    tabStore.set(
      HANDOFF_KEY,
      JSON.stringify({
        revision: target.revision,
        url: location.href,
        view,
        retainedStanding: captureRetainedStanding(),
        ...editingContinuity,
        carry: captureCarry(pageDocument(), authoredSource).records,
        comparison: selectedBase(),
        pointer: pointerAt()
      })
    );
    const marked = new URL(location.href);
    marked.searchParams.set(PRIVATE_REVISION_PARAM, String(target.revision));
    replaceEntry(marked);
    location.reload();
    return new Promise(() => {
    });
  };
  function captureView() {
    dropGonePlaces();
    const blocks = textBlocks();
    const active = activeReadingRegion(readingRegions(), blocks);
    const view = Object.assign(capturePlace(null, blocks), {
      revision: runtime.currentRevision,
      activeRegion: active?.id,
      regions: Object.fromEntries(
        [...places2].flatMap(
          ([id, { reading }]) => id === PAGE ? [] : [[id, reading]]
        )
      )
    });
    for (const region of readingRegions()) {
      if (!shownRegionBounds(region)) continue;
      if (readingPosture(region) === "bounded" || region.id === active?.id)
        view.regions[region.id] = capturePlace(region, blocks);
    }
    return view;
  }
  function restoreView(view, currentIntent) {
    releaseHolds();
    const regions2 = new Map(readingRegions().map((region) => [region.id, region]));
    const active = regions2.get(view.activeRegion) ?? containingReadingRegionFor(focusedInView()) ?? readingRegionFor(pageReadingBlock());
    if (active) reveal(active.host, currentIntent);
    const restored = /* @__PURE__ */ new Set();
    const activeReading = active && view.regions?.[active.id];
    const activeScroller = active && effectiveScroller(regions2.get(active.id));
    if (activeReading && (hasLandmark(activeReading) || rawOffsetFits(activeReading, activeScroller) && activeScroller !== pageScroller)) {
      restorePlace(activeReading, regions2.get(active.id), currentIntent);
      restored.add(activeScroller);
    } else {
      restorePlace(view, null, currentIntent);
      restored.add(pageScroller);
    }
    if (!restored.has(pageScroller) && (hasLandmark(view) || rawOffsetFits(view, pageScroller))) {
      restorePlace(view, null, currentIntent);
      restored.add(pageScroller);
    }
    for (const [id, reading] of Object.entries(view.regions ?? {})) {
      const region = regions2.get(id);
      if (!region || !shownRegionBounds(region)) continue;
      const box = effectiveScroller(region);
      if (restored.has(box)) continue;
      if (!hasLandmark(reading) && !rawOffsetFits(reading, box)) continue;
      restorePlace(reading, region, currentIntent);
      restored.add(box);
    }
  }
  const activeReadingRegion = (candidates = readingRegions(), blocks = textBlocks()) => {
    const focusedRegion = containingReadingRegionFor(focusedInView());
    if (focusedRegion && candidates.some(({ id }) => id === focusedRegion.id))
      return focusedRegion;
    const recent = candidates.find(({ id }) => id === recentReadingRegion()?.id);
    if (recent) return recent;
    return candidates.map((region) => [region, blocksOnScreen(region, blocks).next().value?.[1]]).filter(([, rect]) => rect).sort(([, a], [, b]) => a.top - b.top)[0]?.[0];
  };
  const PAGE = "$page";
  const places2 = /* @__PURE__ */ new Map();
  let placeCount = 0;
  let shifting = false;
  const holds = /* @__PURE__ */ new Map();
  const subjectPlaces = /* @__PURE__ */ new Map();
  let reapply = null;
  const boxId = (box) => box === pageScroller ? PAGE : regionForBox(box)?.id;
  const held = (box) => {
    const id = boxId(box);
    return id === void 0 ? null : holdOf(id);
  };
  function holdOf(id) {
    const hold = holds.get(id);
    if (!hold) return null;
    const box = hold.box.deref();
    const region = box && boxId(box) === id ? regionForBox(box) : void 0;
    const moved2 = region === void 0 ? "gone" : movedAway(box, hold, region);
    const acted = Boolean(box) && inputSince(box, hold.since);
    if (!moved2 && !acted && hold.currentIntent()) return hold;
    holds.delete(id);
    if (moved2 === "carried" || !moved2 && acted)
      places2.set(id, {
        reading: moved2 ? capturePlace(region) : hold.reading,
        at: ++placeCount,
        choices: scrollChoices(),
        inputs: moved2 ? inputCount() : hold.since
      });
    return null;
  }
  const movedAway = (box, hold, region) => {
    const settling = reapply !== null;
    const node = placeNode(hold.reading);
    if (!node) return settling ? null : "gone";
    if (boxOf(node) !== box) return "gone";
    const now = placeOffset(hold.reading, region);
    if (now === null) return settling ? null : "gone";
    const scrolled = box.scrollTop - hold.top;
    const shifted = now - hold.offset;
    if (Math.abs(shifted) <= SCROLL_SLACK) {
      hold.top = box.scrollTop;
      return null;
    }
    if (Math.abs(scrolled) <= SCROLL_SLACK) return null;
    if (Math.abs(shifted + scrolled) <= SCROLL_SLACK) return "carried";
    return settling ? null : "carried";
  };
  const touched = /* @__PURE__ */ new WeakMap();
  const inputSince = (box, count) => (touched.get(box) ?? 0) > count;
  const writing2 = /* @__PURE__ */ new WeakMap();
  const ownEnd = /* @__PURE__ */ new WeakMap();
  const wrote2 = (box, from) => {
    if (box.scrollTop !== from) writing2.set(box, inputCount());
  };
  const readerChose = (box, count) => chosenSince(box, Math.max(count, ownEnd.get(box) ?? 0));
  const inputBox = (element, event) => {
    if (!element) return pageScroller;
    const chain = [];
    for (const box of scrollChainOf(element)) {
      chain.push(box);
      if (getComputedStyle(box).overscrollBehaviorY !== "auto") break;
    }
    const innermost = chain[0] ?? pageScroller;
    if (event.type !== "wheel" || !event.deltaY) return innermost;
    const down = event.deltaY > 0;
    return chain.find(
      (box) => down ? box.scrollTop < scrollLimit(box) - SCROLL_SLACK : box.scrollTop > SCROLL_SLACK
    ) ?? innermost;
  };
  const regionForBox = (box) => box === pageScroller ? null : readingRegions().find(
    (region) => region.body === box && readingPosture(region) === "bounded"
  );
  const boxOf = (node) => effectiveScroller(containingReadingRegionFor(node));
  const dropGonePlaces = () => {
    const present = new Set(readingRegions().map(({ id }) => id));
    for (const map of [places2, subjectPlaces])
      for (const id of map.keys()) if (id !== PAGE && !present.has(id)) map.delete(id);
  };
  function recordPlaces(boxes, { standing = false } = {}) {
    if (shifting || compositionChanges.size || !regionsSettled()) return;
    dropGonePlaces();
    for (const box of boxes) {
      const region = regionForBox(box);
      if (region === void 0 || held(box)) continue;
      if (region && !(under(region.host, pageDocument()) && shownRegionBounds(region)))
        continue;
      const before = places2.get(region ? region.id : PAGE);
      const acted = standing || readerChose(box, before?.choices ?? 0) || inputSince(box, before?.inputs ?? 0);
      if (before && !acted) continue;
      const reading = capturePlace(region);
      places2.set(reading.scroller, {
        reading,
        at: acted ? ++placeCount : 0,
        choices: scrollChoices(),
        inputs: inputCount()
      });
    }
  }
  function placeFor(box, recorded, before) {
    const own = box === pageScroller ? PAGE : regionForBox(box).id;
    let found = null;
    for (const [id, entry] of recorded) {
      if (!before && id !== own) continue;
      const node = placeNode(entry.reading);
      const carried = node ? boxOf(node) === box : id === own && (entry.reading.end || rawOffsetFits(entry.reading, box));
      if ((carried || id === own || before?.has(id)) && !(found?.at > entry.at))
        found = { ...entry, lands: carried || node && under(box, node) };
    }
    return found?.lands ? found : null;
  }
  function restoreShifted(shifted, currentIntent, recorded) {
    shifting = false;
    if (compositionChanges.size) return;
    if (!currentIntent()) return;
    const page = shifted.find(({ region }) => !region);
    if (page?.band) {
      const from = pageScroller.scrollTop;
      moveScrollerBy(pageScroller, -page.band);
      placeKept(pageScroller);
      wrote2(pageScroller, from);
    }
    const boxes = new Map(page ? [[pageScroller, /* @__PURE__ */ new Set()]] : []);
    const returning = /* @__PURE__ */ new Set();
    const touch = (box) => boxes.get(box) ?? boxes.set(box, /* @__PURE__ */ new Set()).get(box);
    const idOf = (box) => box === pageScroller ? PAGE : readingRegions().find(({ body }) => body === box)?.id;
    for (const { region, from, to, returned } of shifted) {
      if (!region || !shownRegionBounds(region)) continue;
      if (returned) returning.add(to);
      touch(to);
      if (from && from !== to && !returned) touch(to).add(idOf(from));
    }
    for (const [box, before] of boxes) {
      const region = regionForBox(box);
      if (region === void 0) continue;
      const place = placeFor(box, recorded, returning.has(box) ? null : before);
      if (!place || readerChose(box, place.choices)) continue;
      const from = box.scrollTop;
      restorePlace(place.reading, region, currentIntent);
      wrote2(box, from);
      holds.set(region ? region.id : PAGE, {
        box: new WeakRef(box),
        reading: place.reading,
        since: inputCount(),
        offset: placeOffset(place.reading, region),
        top: box.scrollTop,
        currentIntent
      });
    }
    watchHolds();
    for (const id of [...holds.keys()]) holdOf(id);
  }
  const SETTLING = 12;
  const SETTLING_MS = 1e3;
  let reapplyTimer;
  const stopReapplying = () => {
    reapply?.disconnect();
    clearTimeout(reapplyTimer);
    reapply = null;
  };
  const releaseHolds = () => {
    holds.clear();
    stopReapplying();
  };
  function watchHolds() {
    stopReapplying();
    if (!holds.size) return;
    const again = frameFor(document.documentElement, () => {
      for (const id of [...holds.keys()]) {
        const hold = holdOf(id);
        if (!hold) continue;
        const box = hold.box.deref();
        const region = regionForBox(box);
        const now = placeOffset(hold.reading, region);
        if (now === null || Math.abs(now - hold.offset) <= SCROLL_SLACK) continue;
        const from = box.scrollTop;
        restorePlace(hold.reading, region, hold.currentIntent);
        wrote2(box, from);
        hold.offset = placeOffset(hold.reading, region);
        hold.top = box.scrollTop;
      }
      if (!holds.size) stopReapplying();
    });
    let deliveries2 = 0;
    const observer = sizeObserver(() => {
      if (reapply !== observer) return;
      if (++deliveries2 > SETTLING) return stopReapplying();
      again();
    });
    reapply = observer;
    reapplyTimer = setTimeout(stopReapplying, SETTLING_MS);
    const settled = () => nextAnimation(() => {
      if (reapply !== observer) return;
      const { updatesSettled, preparationsSettled } = renderingState();
      if (updatesSettled && preparationsSettled && regionsSettled()) stopReapplying();
      else settled();
    });
    settled();
    reapply.observe(pageDocument());
    for (const hold of holds.values()) {
      const box = hold.box.deref();
      if (box && box !== pageScroller)
        for (const child of box.children) reapply.observe(child);
    }
  }
  const compositionChanges = /* @__PURE__ */ new Map();
  const ownBoxes = (owner) => readingRegions().filter(
    (region) => readingPosture(region) === "bounded" && under(region.body, owner) && shownRegionBounds(region)
  ).map((region) => region.body);
  function showSubject(phase, region) {
    const box = region.body;
    const own = regionForBox(box) && box.checkVisibility();
    if (phase === "leaving") {
      if (own) recordPlaces([box]);
      const place = places2.get(region.id);
      if (!place) return;
      if (!subjectPlaces.has(region.id)) subjectPlaces.set(region.id, /* @__PURE__ */ new Map());
      subjectPlaces.get(region.id).set(region.subject, place.reading);
      return;
    }
    holds.delete(region.id);
    const reading = subjectPlaces.get(region.id)?.get(region.subject);
    if (!reading) {
      places2.delete(region.id);
      return;
    }
    places2.set(region.id, {
      reading,
      at: ++placeCount,
      choices: scrollChoices(),
      inputs: inputCount()
    });
    if (own) restorePlace(reading, regionForBox(box));
  }
  function readingRegionTransition({
    phase,
    owner,
    region,
    cancelled,
    retained,
    shifted
  }) {
    if (phase === "leaving" || phase === "showing") {
      showSubject(phase, region);
      return;
    }
    if (phase === "shift") {
      const currentIntent = retainUserIntent();
      const recorded = new Map(places2);
      shifting = true;
      nextRender(() => restoreShifted(shifted, currentIntent, recorded));
      return;
    }
    if (cancelled || [...compositionChanges.keys()].some(
      (ancestor) => ancestor !== owner && under(owner, ancestor)
    )) {
      compositionChanges.delete(owner);
      return;
    }
    if (phase === "before") {
      if (retained && compositionChanges.has(owner)) {
        compositionChanges.get(owner).currentIntent = retainUserIntent();
        return;
      }
      const captured = new Map(
        ownBoxes(owner).map((box) => {
          const region2 = regionForBox(box);
          return [region2.id, capturePlace(region2)];
        })
      );
      compositionChanges.set(owner, { currentIntent: retainUserIntent(), captured });
      return;
    }
    const change = compositionChanges.get(owner);
    compositionChanges.delete(owner);
    if (!change?.currentIntent()) return;
    for (const box of ownBoxes(owner)) {
      const region2 = regionForBox(box);
      const reading = change.captured.get(region2.id) ?? places2.get(region2.id)?.reading;
      if (reading && (hasLandmark(reading) || rawOffsetFits(reading, box)))
        restorePlace(reading, region2, change.currentIntent);
    }
  }
  let readingContinuityInstalled = false;
  function installReadingContinuity() {
    if (readingContinuityInstalled) return;
    readingContinuityInstalled = true;
    watchReadingRegionTransitions(readingRegionTransition);
    const moving = /* @__PURE__ */ new Set();
    let scrolls = 0;
    let resting = false;
    const rest = (seen2) => nextRender(() => {
      if (seen2 !== scrolls) return rest(scrolls);
      resting = false;
      const boxes = [...moving];
      moving.clear();
      recordPlaces(boxes);
    });
    const scrolled = (event) => {
      moving.add(event.target === document ? pageScroller : event.target);
      scrolls++;
      if (resting) return;
      resting = true;
      rest(scrolls);
    };
    document.addEventListener("scroll", scrolled, { capture: true, passive: true });
    document.addEventListener(
      "scrollend",
      ({ target }) => {
        const box = target === document ? pageScroller : target;
        if (writing2.has(box)) {
          if (!inputSince(box, writing2.get(box))) ownEnd.set(box, scrollChoices());
          writing2.delete(box);
        }
        nextRender(() => recordPlaces([box]));
      },
      { capture: true, passive: true }
    );
    for (const type of ["popstate", "hashchange"]) addEventListener(type, releaseHolds);
    const recordStanding = () => {
      const at = focused();
      if (!at || !under(at, pageDocument())) return;
      const box = boxOf(at);
      recordPlaces([box], { standing: true });
      nextRender(() => recordPlaces([box], { standing: true }));
    };
    onStanding(recordStanding);
    onReadingInput(recordStanding);
    onUserInput((event) => {
      if (event.type === "keydown" || event.type === "input") recordStanding();
      if (!["wheel", "touchstart", "keydown", "pointerdown"].includes(event.type))
        return;
      const at = event.type === "keydown" ? focused() : event.composedPath()[0];
      const element = at instanceof Element ? at : at?.parentElement;
      const box = inputBox(element, event);
      touched.set(box, inputCount());
      held(box);
    });
    nextRender(
      () => recordPlaces([
        pageScroller,
        ...readingRegions().filter((region) => readingPosture(region) === "bounded").map((region) => region.body)
      ])
    );
  }
  function installArrival() {
    installReadingContinuity();
    const navigationType = (
      /** @type {PerformanceNavigationTiming | undefined} */
      performance.getEntriesByType("navigation")[0]?.type
    );
    const handoff = (() => {
      const serialized = tabStore.get(HANDOFF_KEY);
      tabStore.set(HANDOFF_KEY, null);
      try {
        const value = JSON.parse(serialized || "null");
        return LIVE_ROOT && navigationType === "reload" && value?.url === location.href && Number.isInteger(value.revision) && value.revision <= runtime.currentRevision && Number.isInteger(value.view?.revision) && value.view.revision < runtime.currentRevision ? value : null;
      } catch {
        return null;
      }
    })();
    const savedView = (() => {
      try {
        return JSON.parse(tabStore.get(VIEW_KEY) || "null");
      } catch {
        return null;
      }
    })();
    addEventListener("pagehide", () => {
      if (!anchoringIsReady()) return;
      tabStore.set(VIEW_KEY, JSON.stringify(captureView()));
    });
    const currentIntent = retainUserIntent({ fallback: compositionInput, since: 0 });
    const restoreCarryScroll = handoff && restoreCarry(handoff.carry, /* @__PURE__ */ new Map(), currentIntent.handoff);
    const landArrival = () => landContinuity(async () => {
      if (!currentIntent()) return;
      if (handoff) {
        restorePointer(handoff.pointer);
        restoreView(handoff.view, currentIntent);
        restoreRetainedStanding(handoff.retainedStanding);
        restoreCarryScroll();
        await restoreEditingContinuity(handoff, currentIntent);
        if (handoff.comparison !== null && stamped(handoff.comparison))
          showComparison(handoff.comparison);
        return;
      }
      if (navigationType === "navigate" && !aimedAt && savedView && savedView.revision !== runtime.currentRevision)
        restoreView(savedView, currentIntent);
    });
    return { landArrival, savedView };
  }
  let aimedAt = null;
  function aimArrival() {
    const fresh = (
      /** @type {PerformanceNavigationTiming | undefined} */
      performance.getEntriesByType("navigation")[0]?.type === "navigate"
    );
    const arrivedAt = location.hash;
    const currentIntent = retainUserIntent({ since: 0 });
    return function landFragment() {
      aimedAt ??= fresh && fragmentTarget(arrivedAt);
      if (!aimedAt || !currentIntent()) return;
      reveal(aimedAt, currentIntent);
      scrollToFragment(aimedAt);
    };
  }
  function mount() {
    versionPicker.configure({
      activate: (entry) => {
        if (entry.version !== null) goVersion(entry.version);
        else if (entry.active) goActive();
      },
      compare: pressComparison,
      latest: goActive
    });
    x(paintPicker);
  }
  return {
    PICKER,
    prepareActivation,
    aimArrival,
    installArrival,
    mount
  };
}

// runtime/projection/state.js
var currentProjection = readPart((root) => root.effective.projection);

// runtime/thread/placement.js
var threadPlace = (t, placedAt) => {
  const place = placedAt(t.id)?.place ?? (t.anchor ? sectionOf(t.anchor) : null);
  return place?.isConnected && !leafSurface(place) ? place : null;
};
var inPageOrder = (threads, placedAt) => byRenderedOrder(threads, (t) => threadPlace(t, placedAt));
var outlined = null;
function pageOutline() {
  const key = [pageReadingVersion(), documentChanged()];
  if (outlined?.key.every((part, index) => part === key[index]))
    return outlined.outline;
  const outline = Object.freeze(
    byRenderedOrder(pageParts("h1, h2, h3, h4, h5, h6"), (heading) => heading)
  );
  outlined = { key, outline };
  return outline;
}
var subjectLabel = (target) => addressableLabel(target) || addressableWord(target);
function outlineSubjectFor(target, peers = [target], outline = pageOutline()) {
  const label = subjectLabel(target);
  const repeated = outline.includes(target) && peers.some(
    (candidate) => candidate !== target && outline.includes(candidate) && subjectLabel(candidate) === label
  );
  return { label, context: repeated ? regionLabel(target) : "" };
}
function regionLabel(node) {
  for (let region = readingRegionFor(node); region; region = readingRegionFor(upFrom(region.host))) {
    const label = region.host.getAttribute("aria-label")?.trim();
    if (label) return label;
  }
  return "";
}

// runtime/annotation-inventory.js
var annotationSelection = (root) => ({
  projection: root.effective.projection,
  obligations: root.effective.obligations,
  workflows: root.effective.workflows,
  revision: root.document.revision,
  todos: root.authoritative?.browser.todos ?? null
});
function createAnnotationInventory({
  readObligations: readObligations2,
  placedAt,
  openThread,
  goToObligation,
  scrollToElement
}) {
  const humanized = (value) => String(value ?? "").replace(/[-_]+/g, " ").trim();
  function targetPath(target) {
    const host = shadowHost(target.getRootNode());
    const prefix = host ? `${targetPath(host)}/shadow/` : "";
    if (target.id) return `${prefix}id:${target.id}`;
    const steps = [];
    let from = "path:";
    for (let node = target; node; ) {
      if (node.dataset?.lfProjection && node.hasAttribute("data-lf-datum")) {
        from = `datum:${node.dataset.lfProjection}/${node.dataset.lfDatum}:`;
        break;
      }
      const parent = node.parentElement ?? (node.parentNode instanceof ShadowRoot ? node.parentNode : null);
      if (!parent) break;
      const siblings = [...parent.children].filter(
        (candidate) => !candidate.classList.contains("lf-ui") && !candidate.hasAttribute("data-lf-gen")
      );
      steps.push(`${node.localName}:${siblings.indexOf(node)}`);
      if (node.localName === "main" || parent instanceof ShadowRoot) break;
      node = parent;
    }
    return `${prefix}${from}${steps.reverse().join("/")}`;
  }
  const standsBy = (group) => group.point ?? targetSegments(group.passage)[0]?.node ?? group.target;
  const startsAt = (group) => targetSegments(group.passage)[0]?.start ?? -1;
  function comesBefore(left, right) {
    if (left === right) return 0;
    if (!left) return 1;
    if (!right) return -1;
    return renderedOrder(left, right);
  }
  const targets = /* @__PURE__ */ new Map();
  const itemSources = /* @__PURE__ */ new WeakMap();
  const targetFor = (entry) => entry ? targets.get(entry.key) ?? null : null;
  const points = /* @__PURE__ */ new Map();
  const entryPoint = (entry) => entry ? livePoint(targetFor(entry), points.get(entry.key)) : null;
  const entryPlace = (entry) => entryPoint(entry) ?? targetFor(entry);
  const passages = /* @__PURE__ */ new Map();
  const entryPassage = (entry) => entry ? passages.get(entry.key) ?? null : null;
  const pointName = (words) => {
    const excerpt = words && excerptWords(words, 32);
    return excerpt ? `\u201C${excerpt}\u201D` : null;
  };
  const sourceItem = (item) => itemSources.get(item);
  function captureItem(item) {
    const { activate, discloses, thread, ...data } = item;
    const snapshot = Object.freeze({
      ...data,
      carriesWorkflow: Boolean(workflowReceipt([item]))
    });
    itemSources.set(snapshot, { activate, discloses, thread });
    return snapshot;
  }
  const workflows = () => runtime.workflows;
  const workflowReceipt = (items) => {
    const receipts = new Set(items.map((item) => item.workflowReceipt?.id));
    return strongestWorkflow(
      workflows().filter(
        (workflow) => receipts.has(workflow.id) && isWorkflowProgress(workflow)
      )
    );
  };
  function groupFor(groups, target, pointed = null) {
    const key = pointed ? `${targetPath(target)}@${pointed.key}` : targetPath(target);
    const slot = pointed ? `point:${key}` : target;
    let group = groups.get(slot);
    if (!group) {
      const word2 = addressableWord(target);
      group = {
        key,
        target,
        point: pointed?.element ?? null,
        passage: pointed?.passage ?? null,
        pointWords: pointed?.words ?? null,
        word: word2,
        subject: null,
        title: null,
        items: [],
        offers: []
      };
      groups.set(slot, group);
    }
    return group;
  }
  function passageRow(target, passage) {
    const segments = targetSegments(passage);
    const page = textNodesUnder(target);
    const at = page.findIndex(({ node }) => node === segments[0].node);
    const before = at < 0 ? page : [...page.slice(0, at), { ...page[at], end: segments[0].start }];
    const words = quoteFrom(segments);
    return JSON.stringify([words, quoteFrom(before).split(words).length - 1]);
  }
  function add(groups, target, item, pointed = null) {
    if (!target?.isConnected || inChrome(target)) return;
    const group = groupFor(groups, target, pointed);
    group.items.push(item);
  }
  function visibleWidgetWorkflows() {
    return workflows().filter(
      (workflow) => isPageWidgetWorkflow(workflow, runtime.currentRevision)
    );
  }
  function agentWorkflowFace(receipt) {
    if (!receipt) return null;
    const label = workflowLabel(receipt);
    if (!label) return null;
    return {
      kind: (
        // A receipt handed back to the user always carries its failure.
        receipt.condition ? "waiting" : receipt.at_work ? "activity" : receipt.stage === "picked_up" ? "pickup" : receipt.stage === "queued" ? "queued" : "sent"
      ),
      text: label,
      context: [receipt.ts ? ago(receipt.ts) : "", receipt.detail].filter(Boolean).join(" \xB7 ")
    };
  }
  const marginThreadItem = (thread) => thread ? `comment:${threadKey(thread)}` : null;
  let entries = Object.freeze([]);
  const watchers = /* @__PURE__ */ new Set();
  const threadHasDiscussion = (thread) => replyAvailable(thread) || heldOut(thread.id);
  function threadIdsAt(node) {
    const place = placeOf(node);
    let best = null;
    for (const thread of threadList()) {
      if (!threadHasDiscussion(thread)) continue;
      const placement = placedAt(thread.id);
      const target = placement?.place;
      if (!target || !under(place, target)) continue;
      const point = livePoint(target, placement.point);
      const rank = !point ? 1 : under(place, point) ? 2 : 0;
      if (best && target === best.target && point === best.point) {
        best.ids.push(thread.id);
        continue;
      }
      if (!best || (target === best.target ? rank >= best.rank : under(target, best.target)))
        best = { target, point, rank, ids: [thread.id] };
    }
    return best?.ids ?? [];
  }
  function collectEntries() {
    const groups = /* @__PURE__ */ new Map();
    const receiptByCoordinate = /* @__PURE__ */ new Map();
    for (const receipt of visibleWidgetWorkflows()) {
      const coordinate = (
        /** @type {[string, string, string]} */
        receipt.coordinate
      );
      receiptByCoordinate.set(stateCoordinate(...coordinate), receipt);
    }
    for (const thread of threadList()) {
      if (!threadHasDiscussion(thread) || !thread.anchor || claimed(thread.id))
        continue;
      const id = thread.id;
      const target = placedAt(id)?.place;
      const placement = placedAt(id);
      const point = livePoint(target, placement?.point);
      const pointed = point ? { key: placement.pointRow, element: point, words: placement.pointWords } : targetSegments(placement).length ? {
        key: passageRow(target, placement),
        passage: placement,
        words: thread.anchor.quote
      } : null;
      add(
        groups,
        target,
        {
          kind: "comment",
          // One row for one thread, across the log answering for it. A thread the
          // user just opened is known by its attempt until the log names it, and a row
          // whose identity changed there would be rebuilt — taking with it the reply box
          // the send had just put them in.
          id: marginThreadItem(thread),
          text: threadName(thread),
          thread,
          // The Thread record already combines server attention with the local workflow
          // overlay. Margin and Page Map carry that reading rather than deriving another
          // answer from raw turn or workflow fields. Work decorates the thread control;
          // it never replaces the control's comment face or its disclosure action.
          ...threadMarks(thread),
          activate: () => openThread(id)
        },
        pointed
      );
    }
    for (const item of readObligations2().user) {
      const id = item.id;
      const target = obligationPlace(item).node;
      if (!target) continue;
      add(groups, target, {
        kind: "on-me",
        id: `on-me:${id}`,
        // The group this row stands in already names the obligation; the row says why it is
        // there, since these are the obligations the user owes.
        text: "Waiting on me",
        // The marker's own label is the question, which says more than the kind its
        // glyph already shows.
        label: addressableLabel(target) || null,
        activate: () => {
          const items = readObligations2().user.filter(
            (item2) => item2.source.kind === "widget"
          );
          const next = items.find((candidate) => candidate.id === id);
          if (next) goToObligation(next, items);
        }
      });
    }
    const projection = currentProjection();
    const activityAlreadyShown = /* @__PURE__ */ new Set();
    const acknowledged = /* @__PURE__ */ new Set();
    for (const [coordinate, entry] of projection.desired) {
      if (entry.e.kind !== "action") continue;
      const target = elementById(entry.unit) ?? elementById(entry.e.widget);
      if (!target) continue;
      const receipt = receiptByCoordinate.get(coordinate);
      if (!receipt) continue;
      const account = [
        addressableWord(target),
        humanized(entry.e.action),
        addressableLabel(target)
      ].filter(Boolean).join(" \xB7 ");
      const face = agentWorkflowFace(receipt);
      if (!face) continue;
      if (face.kind === "activity")
        activityAlreadyShown.add(`widget:${receipt.subject.id}`);
      acknowledged.add(target);
      add(groups, target, {
        kind: face.kind,
        id: `acknowledgment:${receipt.id}`,
        text: labelWords(`${face.text} \xB7 ${account}`),
        workflowFace: Object.freeze({ ...KINDS[face.kind], label: face.text }),
        workflowReceipt: receipt,
        ...face.context ? { context: face.context } : {},
        activate: () => revealTarget(target, `${face.text}: ${account}`, scrollToElement)
      });
    }
    for (const origin of projectionOrigins(authoredStates(), projection)) {
      const target = elementById(origin.unit);
      if (!target) continue;
      if (origin.origin === "user" && acknowledged.has(target)) continue;
      const face = KINDS[origin.origin];
      add(groups, target, {
        kind: origin.origin,
        id: `state-origin:${origin.origin}:${origin.unit}`,
        // Durable provenance belongs in Page Map rather than another target margin entry:
        // it remains explicit without changing the page's action density or geometry.
        marker: false,
        text: labelWords(
          [face.label, addressableWord(target), addressableLabel(target)].filter(Boolean).join(" \xB7 ")
        ),
        activate: () => revealTarget(
          target,
          `${face.label}: ${addressableLabel(target) || addressableWord(target)}`,
          scrollToElement
        )
      });
    }
    const base = comparisonBase();
    comparisonChanges().forEach((target, index) => {
      const account = `${addressableWord(target)} changed${base == null ? "" : ` since v${base}`}`;
      const inline = inlineComparison(target);
      const mapAccount = inline ? `${addressableWord(target)} changed` : account;
      add(groups, target, {
        kind: "change",
        id: `change:${targetPath(target)}:${index}`,
        text: labelWords(
          [mapAccount, addressableLabel(target)].filter(Boolean).join(" \xB7 ")
        ),
        // A disclosure has to say what it holds, or its one word reports a fact and
        // promises nothing. The margin entry's quieter line carries it, and a block the
        // comparison holds nothing for has none, so no margin entry offers a press it has
        // not got.
        ...inline ? { context: inline.offer, mapContext: inline.offer } : {},
        // What a Change reading holds, where the comparison kept the base version's
        // words for this block: pressing it splices dropped text into the current
        // passage and paints additions there, so the user learns what changed without
        // travelling to the other version and back. Where it kept none, the press is the
        // travel it always was, and `discloses` answering null is what says so — to the
        // margin entry's relation, to the hint's word for the press, and to the
        // reference.
        discloses: () => inlineComparison(target),
        activate: () => {
          const said = toggleInlineComparison(target);
          revealTarget(
            target,
            said ? `${account} \xB7 ${said}` : account,
            scrollToElement
          );
        }
      });
    });
    for (const todo of runtime.todos) {
      if (todo.owner !== "agent" || todo.state !== "open" || todo.subject.kind !== "widget" && todo.subject.kind !== "element" || todo.revision > runtime.currentRevision)
        continue;
      if (activityAlreadyShown.has(`widget:${todo.subject.id}`)) continue;
      const target = elementById(todo.subject.id);
      const { running } = todo;
      const label = todoLabel(running);
      const account = [todo.agent, running?.text ?? todo.title].filter(Boolean).join(" \xB7 ");
      const age = running && ago(running.ts);
      add(groups, target, {
        kind: "activity",
        id: `todo:${todo.id}`,
        text: labelWords(account),
        workflowFace: Object.freeze({ ...KINDS.activity, label }),
        context: [age && `Checked in ${age}`, running && todo.title].filter(Boolean).join(" \xB7 "),
        activate: () => revealTarget(target, account, scrollToElement)
      });
    }
    for (const offered of contributionEntries()) {
      const target = offered.target();
      if (!target?.isConnected || inChrome(target)) continue;
      const group = groupFor(groups, target);
      if (group.offers.some((candidate) => candidate.key === offered.key))
        throw new TypeError(
          `Duplicate margin contribution key for ${target.id || targetPath(target)}: ${offered.key}`
        );
      group.offers.push(offered);
      const subject = offered.reading.subject;
      if (String(subject ?? "").trim()) {
        if (group.subject && group.subject !== String(subject).trim())
          throw new TypeError(
            `Conflicting margin contribution subjects for ${target.id || targetPath(target)}`
          );
        group.subject = String(subject).trim();
      }
      for (const item of offered.reading.readings) {
        const kind = item.kind ?? "action";
        if (!KINDS[kind]) throw new TypeError(`Unknown margin reading kind: ${kind}`);
        group.items.push({
          marker: false,
          ...item,
          owner: offered.key,
          kind,
          activate: () => offered.registration.activateReading(item.id)
        });
      }
    }
    const outline = pageOutline();
    const collected = [...groups.values()];
    const subjects = collected.filter((group) => !group.subject).map((group) => group.target);
    targets.clear();
    points.clear();
    passages.clear();
    entries = marginInventory(
      collected.sort(
        (left, right) => comesBefore(standsBy(left), standsBy(right)) || startsAt(left) - startsAt(right)
      ).map((group) => {
        const subject = outlineSubjectFor(group.target, subjects, outline);
        targets.set(group.key, group.target);
        if (group.point) points.set(group.key, group.point);
        if (group.passage) passages.set(group.key, group.passage);
        return Object.freeze({
          key: group.key,
          targetId: group.target.id,
          title: labelWords(
            [
              group.subject ? null : subject.context,
              group.word,
              group.subject ?? addressableLabel(group.target),
              // A pointed row is named by the words it stands by, so it and the
              // target's own row do not read alike.
              pointName(group.pointWords)
            ].filter(Boolean).join(" \xB7 ")
          ),
          offers: Object.freeze(group.offers.map((offered) => offered.model)),
          items: Object.freeze(group.items.map(captureItem)),
          workflowReceipt: workflowReceipt(group.items)
        });
      })
    );
    for (const watcher of watchers) watcher(entries);
    return entries;
  }
  function revealTarget(target, account, scrollToElement2) {
    if (!target?.isConnected) return;
    scrollToElement2(target, scrollBehavior(), "nearest");
    notice(account);
  }
  return Object.freeze({
    collect: collectEntries,
    read: () => entries,
    watch(watcher) {
      watchers.add(watcher);
      try {
        watcher(entries);
      } catch (error) {
        watchers.delete(watcher);
        throw error;
      }
      return () => watchers.delete(watcher);
    },
    targetFor,
    entryPoint,
    entryPlace,
    entryPassage,
    sourceItem,
    workflowReceipt,
    targetPath,
    threadItem: marginThreadItem,
    threadIdsAt,
    activate: (item) => sourceItem(item)?.activate()
  });
}

// runtime/reactions.js
var reactionVocabulary = () => registry.$reactions?.tokens ?? {};
var reactionTokens = () => Object.entries(reactionVocabulary());
var reactionAvailable = () => readThreads().phase === "ready";
var anchorChoices = (anchor) => reactionAvailable() ? tokenChoices(
  reactionVocabulary(),
  anchor ? reactionsAt(allThreads(), anchor) : []
) : [];
function reactionChip({ name, glyph, label }, pressed) {
  const chip = offer("button", `lf-react ${HOLDS_WORD}`);
  chip.dataset.token = name;
  chip.title = label;
  chip.setAttribute("aria-label", label);
  responseAction(chip, { glyph, label: name, collapse: true });
  keys(chip, "On a reaction", [
    {
      id: `reaction.${name}`,
      ready: savedReadingSettled,
      when: reactionAvailable,
      keys: [],
      control: chip,
      title: label,
      run: () => pressed(name)
    }
  ]);
  return chip;
}
function paintBarReactions(anchor) {
  const by = new Map(anchorChoices(anchor).map((choice) => [choice.name, choice]));
  for (const chip of fabBar.querySelectorAll(".lf-react-palette > .lf-react")) {
    const inForce = by.get(chip.dataset.token)?.inForce;
    keeps(chip, "aria-pressed", String(Boolean(inForce)));
    keeps(chip, "aria-busy", String(Boolean(inForce?.pending)));
  }
}
function createReactionController({
  marginEntryChoices,
  marginEntryContextContains,
  openMarginEntryOptions,
  designModeActive,
  hideComposer,
  syncResponseOptions,
  fabAnchorAt,
  fabReturnPlaces,
  fabTargetAt,
  hasPageSelectionTarget,
  showFab,
  showFabOptions,
  updateFab,
  standingThread: standingThread2,
  standingTarget
}) {
  const surfaces = /* @__PURE__ */ new WeakMap();
  const marginSurface = /* @__PURE__ */ Symbol("margin reactions");
  let marginOffer = null;
  let marginTarget = null;
  let marginAnchor = null;
  let pageCommands = null;
  const marginReactionKey = (name, ordinal) => `reaction:${String(ordinal).padStart(4, "0")}:${name}`;
  function registerReactSurface(surface, { palette, trigger }) {
    surfaces.set(surface, { palette, trigger });
    return {
      toggle: () => setReact(!(reactArmed && reactSurface === surface), { surface }),
      close: () => {
        if (reactSurface === surface) setReact(false);
      }
    };
  }
  function buildReactBar(commands) {
    pageCommands = commands;
    const palette = el("span", "lf-react-palette");
    palette.setAttribute("role", "group");
    palette.setAttribute("aria-label", "Reactions for this selection or element");
    for (const choice of tokenChoices(reactionVocabulary(), []))
      palette.append(reactionChip(choice, (token) => reactHere(token, commands)));
    fabOptions.append(palette);
    syncResponseOptions();
  }
  const anchorWord = (anchor) => {
    if (!anchor) return "the target";
    if (anchor.quote) return "the selection";
    const addressable = elementById(anchor.section);
    if (anchor.visual)
      return visualPartLabel(addressable, anchor.visual) ?? anchor.visual;
    return addressableWord(addressable) || "the element";
  };
  async function reactHere(name, commands, anchor = fabAnchorAt()) {
    const choice = anchorChoices(anchor).find((choice2) => choice2.name === name);
    if (!choice) return;
    const { inForce } = choice;
    const returnTo = fabReturnPlaces();
    if (!anchor) return;
    let sent;
    if (inForce) sent = commands.withdrawReaction(inForce);
    else {
      const event = {
        kind: "comment",
        revision: runtime.currentRevision,
        token: name,
        anchor: structuredClone(anchor)
      };
      if (designModeActive()) event.about = "design";
      sent = sendReaction(event, anchorWord(anchor), commands.postReaction);
    }
    closeLayer(
      () => {
        hideComposer();
        showFab(null);
        setReact(false);
      },
      () => handBack(...returnTo)
    );
    getSelection()?.removeAllRanges();
    await sent;
  }
  let reactArmed = false;
  let reactRaised = false;
  let releaseMarginOptions = null;
  const reactLayer = {};
  const reactFrom = () => openerOf(reactLayer);
  let reactSurface = null;
  let reactDeparture = null;
  const latestAgentStrip = (held) => held.querySelector(".lf-react-strip.lf-open");
  const pickerFor = (surface) => surfaces.get(surface);
  function reactionTarget() {
    const said = standingThread2();
    const strip = said && latestAgentStrip(said.held);
    if (strip) return { kind: "surface", surface: strip };
    if (fabAnchorAt()) return { kind: "anchor" };
    if (hasPageSelectionTarget()) return { kind: "selection" };
    const target = standingTarget();
    return target ? { kind: "target", target } : null;
  }
  const hasReactionTarget = () => Boolean(reactionTarget());
  function raiseMarginSurface() {
    const anchor = fabAnchorAt();
    const target = anchor && fabTargetAt();
    if (!pageCommands || !target || !openMarginEntryOptions) return false;
    fabBar.dataset.lfMarginRaised = "1";
    marginAnchor = structuredClone(anchor);
    marginOffer = registerContribution({
      key: "responses",
      target,
      read: () => ({
        side: "after",
        entries: anchorChoices(marginAnchor).map((choice, ordinal) => ({
          key: marginReactionKey(choice.name, ordinal),
          activation: choice.name,
          glyph: choice.glyph,
          label: choice.label,
          rank: "secondary",
          className: "lf-react",
          pressed: Boolean(choice.inForce)
        })),
        readings: []
      }),
      activate: (name) => reactHere(name, pageCommands, marginAnchor)
    });
    marginTarget = target;
    const release = openMarginEntryOptions(target, "responses");
    if (release) {
      releaseMarginOptions = release;
      return true;
    }
    marginOffer.unregister();
    marginOffer = null;
    marginTarget = null;
    marginAnchor = null;
    return false;
  }
  function lowerMarginSurface() {
    releaseMarginOptions?.();
    releaseMarginOptions = null;
    marginOffer?.unregister();
    marginOffer = null;
    marginTarget = null;
    marginAnchor = null;
    delete fabBar.dataset.lfMarginRaised;
  }
  function closeSurface(surface) {
    if (surface === marginSurface) return;
    surface?.classList.remove("lf-react-open");
    reactDeparture?.();
    reactDeparture = null;
    const picker = pickerFor(surface);
    if (picker) closeNativeLayer(picker.palette);
    picker?.trigger.setAttribute("aria-expanded", "false");
  }
  function syncReactLayout() {
    return reactArmed && reactSurface === marginSurface;
  }
  function setReact(on, { surface = null } = {}) {
    if (on && !reactionAvailable()) return;
    if (!on && !reactArmed) {
      const residue = marginOffer || fabBar.hasAttribute("data-lf-margin-raised");
      if (!residue) return;
      closeSurface(reactSurface);
      lowerMarginSurface();
      repaint();
      return;
    }
    if (on === reactArmed && (surface === reactSurface || !surface)) return;
    if (on && claimsEsc(focused())) return;
    const closingActive = on ? null : focused();
    if (!on) {
      closeReact(closingActive);
      repaint();
      return;
    }
    closeSurface(reactSurface);
    if (on) {
      openLayer(reactLayer);
      if (surface) reactSurface = surface;
      else {
        const target = reactionTarget();
        if (target?.kind === "surface") reactSurface = target.surface;
        else if (target?.kind === "anchor" || target?.kind === "target") {
          if (target.kind === "target") {
            showFab(target.target.anchor, {
              place: false
            });
            reactRaised = true;
          }
          if (!raiseMarginSurface()) {
            if (reactRaised) showFab(null);
            reactRaised = false;
            reactSurface = null;
            openLayer(reactLayer, null);
            raiseError("That reaction target is no longer available");
            return;
          }
          reactSurface = marginSurface;
        } else {
          reactSurface = null;
          openLayer(reactLayer, null);
          return;
        }
      }
      if (reactSurface !== marginSurface && !pickerFor(reactSurface)) {
        reactSurface = null;
        openLayer(reactLayer, null);
        return;
      }
      reactArmed = true;
      if (reactSurface !== marginSurface) {
        reactSurface.classList.add("lf-react-open");
        const picker = pickerFor(reactSurface);
        scrollIntoReadingBand(picker.trigger, picker.trigger, "nearest", "instant");
        showNativeLayer(picker.palette, { source: picker.trigger });
        const opened = reactSurface;
        const seen2 = (trigger) => seenRect(trigger, clipsPastSurfaces());
        reactDeparture = whenNone([picker.trigger], seen2, () => {
          if (reactSurface === opened) setReact(false);
        });
        picker.trigger.setAttribute("aria-expanded", "true");
        const first = surface && reactFrom() === picker.trigger && picker.palette.querySelector(".lf-react");
        if (first) focusDestination(first, "move");
      }
      announce(`React \u2014 ${saying(REACT.rows)}`);
    }
    repaint();
  }
  function closeReact(active) {
    const from = reactFrom();
    const trigger = pickerFor(reactSurface)?.trigger;
    const input = fabBar.querySelector(".lf-fab-input");
    const owed = fabBar.contains(from) || marginOffer?.contains(active) || active === document.body || active?.closest?.(".lf-react-palette");
    const candidates = from ? [input, from, trigger] : [input];
    closeLayer(
      () => {
        closeSurface(reactSurface);
        reactArmed = false;
        reactSurface = null;
        openLayer(reactLayer, null);
        if (reactRaised) showFab(null);
        reactRaised = false;
        lowerMarginSurface();
        if (fabAnchorAt()) showFab(fabAnchorAt());
      },
      owed && (() => handBack(...candidates.filter(drawn)))
    );
  }
  function responseChoices(surface) {
    if (!surface) return [];
    if (surface === marginSurface) return marginEntryChoices(fabTargetAt());
    return [...surface.querySelectorAll(".lf-react-palette > .lf-react")].filter(
      (choice) => choice.checkVisibility()
    );
  }
  function stepResponse(binding) {
    const choices = responseChoices(reactSurface);
    if (!choices.length) return;
    const at = choices.indexOf(focused());
    const backward = [rowArrows(choices[0])[0], "ArrowUp", "Shift+Tab"].includes(
      binding
    );
    const next = at < 0 ? backward ? choices.length - 1 : 0 : (at + (backward ? -1 : 1) + choices.length) % choices.length;
    focusDestination(choices[next], "move");
    beginWalk(
      "reaction",
      "Reaction",
      () => listWalkPosition(responseChoices(reactSurface), focused())
    );
  }
  const REACT = {
    title: "With reactions open",
    ready: savedReadingSettled,
    escape: "inner",
    // Opening the modal reference dismisses this transient mode. Its section still reads
    // the liveness captured at that boundary rather than listing every conditional choice.
    liveInCommandReference: true,
    at: () => reactArmed,
    // The open list is where the mode stands. The margin's list has no node of its own
    // and stands wherever its entry does.
    root: () => reactSurface instanceof Element ? reactSurface : document,
    claims: allButCommandReference,
    rows: [
      {
        id: "reaction.choose",
        touch: false,
        runFromCommandReference: false,
        keys: () => reactionTokens().slice(0, 9).map((_, i) => String(i + 1)),
        label: () => {
          const n = Math.min(reactionTokens().length, 9);
          return n > 1 ? `1\u2013${n}` : "1";
        },
        description: () => reactionTokens().slice(0, 9).map(([name, entry], i) => `${i + 1} ${entry.glyph} ${name}`).join(", "),
        title: "react",
        when: reactionAvailable,
        run: (binding) => {
          if (reactSurface === marginSurface) {
            const ordinal = +binding - 1;
            const token = reactionTokens()[ordinal]?.[0];
            if (token)
              marginOffer?.activate(marginReactionKey(token, ordinal), {
                origin: focused(),
                input: "keyboard",
                surface: "margin"
              });
            return;
          }
          pickerFor(reactSurface)?.palette.querySelectorAll(".lf-react")[+binding - 1]?.click();
        }
      },
      {
        id: "reaction.move",
        touch: false,
        runFromCommandReference: false,
        keys: ["Tab", "Shift+Tab", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"],
        title: "move",
        repeat: true,
        run: stepResponse
      },
      {
        id: "response.activate",
        touch: false,
        runFromCommandReference: false,
        keys: PRESS,
        title: "choose",
        when: () => responseChoices(reactSurface).includes(focused()),
        run: () => focused()?.click()
      },
      {
        id: "reaction.cancel",
        touch: false,
        keys: ["Escape"],
        title: "cancel",
        run: () => setReact(false)
      }
    ]
  };
  const isReactArmed = () => reactArmed;
  const reactionContextContains = (node) => reactArmed && reactSurface === marginSurface && marginEntryContextContains?.(fabTargetAt(), node);
  function mount() {
    document.addEventListener("lf-margin-entry-options-closed", () => {
      if (reactArmed && reactSurface === marginSurface) setReact(false);
    });
    const margin = readPart((root) => ({
      threads: root.effective.thread.all,
      annotations: annotationSelection(root)
    }));
    x(() => {
      margin();
      d(() => {
        if (reactArmed && reactSurface === marginSurface && (!marginTarget?.isConnected || fabTargetAt() !== marginTarget))
          setReact(false);
        else if (reactArmed && reactSurface === marginSurface) marginOffer?.update();
      });
    });
  }
  pageScope("reactions", REACT);
  pageCommand({
    id: "reaction.open",
    ready: savedReadingSettled,
    touch: false,
    keys: ["e"],
    description: "On the selection, the focused item or the open reply",
    title: "reactions",
    when: () => reactionAvailable() && reactionTokens().length > 0 && hasReactionTarget() && (anchoringIsReady() || !pageSelection()),
    run: () => {
      if (pageSelection() && !fabAnchorAt()) updateFab();
      if (composerOpen && fabAnchorAt()) showFabOptions({ reaction: true });
      else setReact(true);
    }
  });
  return {
    registerReactSurface,
    buildReactBar,
    hasReactionTarget,
    syncReactLayout,
    setReact,
    isReactArmed,
    reactionContextContains,
    mount
  };
}
async function sendReaction(event, where, postReaction) {
  const sent = await postReaction(event);
  if (sent) announce(`${event.token} on ${where}`);
  return sent;
}
function reactionPlace(event) {
  if (event.kind === "reply") return "the reply";
  if (!event.anchor) return "the page";
  return anchorLabel(event.anchor, event.about);
}

// runtime/queue-api.js
var queueItemKey = (item) => JSON.stringify([item.kind, item.id]);
var readQueues = readPart((root) => root.effective.queues);
var readPlan = readPart((root) => root.effective.plan);
function createQueueActions({ post: post2, arrive }) {
  return Object.freeze({
    open(key) {
      const reading = readQueues();
      const item = [...reading.on_user, ...reading.on_agent, ...reading.done].find(
        (candidate) => queueItemKey(candidate) === key
      );
      return item?.offers.open ? arrive(item) : Promise.resolve(false);
    },
    done(key) {
      const reading = readQueues();
      const item = reading.on_user.find((candidate) => queueItemKey(candidate) === key);
      if (!item?.offers.done) return null;
      const delivery = post2({ kind: "todo_end", todo: item.id, outcome: "done" });
      announce("Done");
      return delivery;
    }
  });
}

// runtime/state-feed.js
async function readState(bound) {
  countTraffic("asked");
  try {
    if (offlineInteractive) return { state: offlineState(), fault: null };
    const signal = globalThis.AbortSignal.timeout(bound);
    const held = runtime.data;
    let res;
    try {
      res = await fetch(pageUrl("api/state"), {
        headers: layerHeaders(dataHeaders(held)),
        // Coalescing bounds concurrency; this bounds its other dimension. A proxy that
        // never answers cannot own the page's single read slot forever.
        signal
      });
    } catch {
      return NOTHING;
    }
    if (!admitResponse(res)) return NOTHING;
    if (!res.ok) {
      if (res.status === 401 || NO_SERVER_BEHIND.has(res.status)) return NOTHING;
      const answer = await res.json().catch(() => null);
      return { state: null, fault: answer?.error ?? `HTTP ${res.status}` };
    }
    try {
      return { state: completeData(await res.json(), held), fault: null };
    } catch (error) {
      if (signal.aborted) return NOTHING;
      throw error;
    }
  } finally {
    countTraffic("heard");
  }
}
function buffer(bound) {
  return readState(bound).catch((error) => ({ error }));
}
function beginRead() {
  return buffer(FIRST_READ_TIMEOUT_MS);
}
function createStateFeed({
  stateApplying,
  invalidateDom: invalidateDom2,
  receiveState,
  prepareActivation
}) {
  let readAnswered = false;
  function failed(error) {
    readAnswered = false;
    reportCarried(error, `read failed`);
    applicationState.setReach("broken");
  }
  async function tick() {
    if (stateApplying()) return;
    await tickClock(reportCarried);
    if (stateApplying()) return;
    document.dispatchEvent(new Event("lf-tick"));
  }
  async function readNothing(fault = null) {
    readAnswered = false;
    if (runtime.statePhase === "waiting") applicationState.setPhase("offline");
    if (fault !== null) applicationState.setReach("faulted", fault);
    else applicationState.setReach(runtime.keyRefused ? "refused" : "unreachable");
    await invalidateDom2();
    await tick();
  }
  async function readAndApply(read2 = buffer(STATE_READ_TIMEOUT_MS)) {
    const answer = await read2;
    if ("error" in answer) throw answer.error;
    const { state, fault } = answer;
    if (!state) {
      await readNothing(fault);
      return;
    }
    await receiveState(state);
    readAnswered = true;
  }
  async function heartbeat() {
    if (stateApplying()) return;
    try {
      if (runtime.statePhase === "ready" && runtime.state && !runtime.showsActive) {
        const activation = await prepareActivation(runtime.state);
        if (activation?.activates()) await receiveState(runtime.state);
      }
      await tick();
    } catch (error) {
      readAnswered = false;
      reportCarried(error, `tick failed`);
    }
  }
  function startFeed(present, initialRead = beginRead()) {
    const readAndPresent = async () => {
      try {
        await readAndApply(initialRead);
      } catch (error) {
        failed(error);
        return;
      } finally {
        releaseSlot();
      }
      try {
        await present();
      } catch (error) {
        failed(error);
      }
    };
    let reading = true;
    let readQueued = false;
    let applyingReads = 0;
    const releaseSlot = () => {
      reading = false;
      if (!readQueued) return;
      readQueued = false;
      item();
    };
    const feedQuiet = () => !reading && !applyingReads && !stateApplying();
    const askOnce = async () => {
      const returned = readingReturn();
      try {
        const { state, fault } = await readState(STATE_READ_TIMEOUT_MS);
        if (state) {
          applyingReads += 1;
          void receiveState(state).then(
            async () => {
              readAnswered = true;
              await present();
              if (applyingReads === 1 && !stateApplying())
                completeReadingReturn(returned);
            },
            async (error) => {
              failed(error);
              await present();
            }
          ).catch((error) => {
            reportCarried(error, `presentation failed`);
          }).finally(() => {
            applyingReads -= 1;
          });
        } else {
          void readNothing(fault).then(async () => {
            await present();
            if (!applyingReads && !stateApplying()) completeReadingReturn(returned);
          }).catch(failed);
        }
      } catch (error) {
        failed(error);
      }
    };
    const item = () => {
      if (reading) {
        readQueued = true;
        return;
      }
      reading = true;
      void askOnce().finally(releaseSlot);
    };
    const pageIsVisible = () => document.visibilityState !== "hidden";
    let feedStarted = false;
    let listening = null;
    let freshness = null;
    let nextLook = null;
    const stopListening = () => {
      clearTimeout(nextLook);
      nextLook = null;
      listening?.abort();
      listening = null;
      freshness = null;
    };
    const listen = () => {
      if (!feedStarted || !pageIsVisible() || !sessionIsActive() || listening) return;
      const interval = new AbortController();
      listening = interval;
      const look = async () => {
        let delay = LOOK_MS;
        const returned = readingReturn();
        try {
          const response = await fetch(pageUrl("api/news"), {
            headers: layerHeaders(),
            signal: globalThis.AbortSignal.any([
              interval.signal,
              globalThis.AbortSignal.timeout(STATE_READ_TIMEOUT_MS)
            ])
          });
          if (listening !== interval) return;
          if (!admitResponse(response))
            throw new Error("news belongs to another delivery");
          if (!response.ok) throw new Error(`news returned HTTP ${response.status}`);
          const observed = await response.text();
          if (listening === interval) {
            if (observed !== freshness && observed !== runtime.reading) item();
            else if (returned !== null && observed === runtime.reading && feedQuiet()) {
              await invalidateDom2();
              await present();
              if (feedQuiet()) completeReadingReturn(returned);
            }
            freshness = observed;
          }
        } catch {
          if (listening !== interval) return;
          item();
          delay = TICK_MS;
        }
        if (listening === interval) nextLook = setTimeout(look, delay);
      };
      void look();
    };
    document.addEventListener("visibilitychange", () => {
      if (!pageIsVisible()) {
        stopListening();
        return;
      }
      const returned = readingReturn();
      void invalidateDom2().then(present).then(() => {
        if (offlineInteractive || !sessionIsActive()) completeReadingReturn(returned);
      }).catch((error) => reportCarried(error, `return presentation failed`));
      listen();
    });
    document.addEventListener("lf-session-active", listen);
    const initialPresentation = readAndPresent();
    if (offlineInteractive) return;
    initialPresentation.finally(() => {
      feedStarted = true;
      setInterval(() => {
        if (!pageIsVisible()) return;
        if (readAnswered && sessionIsActive() && (activityTransitionDue(runtime.state) || freshness !== null && freshness !== runtime.reading))
          void item();
        else if (readAnswered) void heartbeat();
        else void item();
        void present();
      }, TICK_MS);
      listen();
    });
  }
  return { readAndApply, startFeed };
}
var TICK_MS = 2e3;
var LOOK_MS = 250;
var FIRST_READ_TIMEOUT_MS = 12e4;
var STATE_READ_TIMEOUT_MS = 1e4;
var NOTHING = Object.freeze({ state: null, fault: null });
var NO_SERVER_BEHIND = /* @__PURE__ */ new Set([502, 503, 504]);

// runtime/pending/state.js
function createPendingLedger({ newAttempt, enqueue }) {
  const handles = /* @__PURE__ */ new Map();
  const snapshot = () => readApplication().unresolved;
  const sending = () => readApplication().effective.sending;
  return {
    /** @param {PendingCommand} event */
    enqueue(event) {
      const attempted = { ...event, attempt: event.attempt || newAttempt() };
      if (applicationState.entry(attempted.attempt)) return null;
      const { promise: answer, resolve } = Promise.withResolvers();
      const { promise: read2, resolve: resolveRead } = Promise.withResolvers();
      const current = () => applicationState.entry(attempted.attempt);
      const handle = {
        get event() {
          return current()?.event ?? attempted;
        },
        get admitted() {
          return current()?.admitted ?? null;
        },
        answer,
        read: read2,
        resolve(value) {
          resolve(value);
          handles.delete(attempted.attempt);
        },
        resolveRead
      };
      handles.set(attempted.attempt, handle);
      enqueue(attempted);
      return handle;
    },
    snapshot,
    nextSending: () => {
      const [attempt] = sending();
      return attempt ? handles.get(attempt) : null;
    },
    releasable: () => applicationState.releasable(),
    /** @param {readonly Pick<Entry, "event">[]} entries */
    release: (entries) => applicationState.release(new Set(entries.map((entry) => entry.event.attempt))),
    /** The gestures refused with `entry`, each answered null here.
     * @param {DeliveryHandle} entry @returns {{attempt: string, answer: Promise<Event | null>}[]} */
    refuse(entry) {
      return applicationState.refuse(entry.event.attempt).flatMap((attempt) => {
        const handle = handles.get(attempt);
        handle?.resolve(null);
        return handle ? [{ attempt, answer: handle.answer }] : [];
      });
    },
    /** @param {DeliveryHandle} entry @param {Event} event */
    accept(entry, event) {
      applicationState.accept(entry.event.attempt, event);
    },
    /** @param {Event[]} receipts */
    present(receipts) {
      applicationState.present(receipts);
      for (const receipt of receipts)
        if (receipt.attempt) handles.get(receipt.attempt)?.resolveRead(receipt);
    },
    /** @param {DeliveryHandle} entry */
    nameEvents(entry) {
      return applicationState.nameEvents(entry.event.attempt);
    }
  };
}

// runtime/pending/dispatch.js
function createCommandDispatch() {
  const submitted = /* @__PURE__ */ new Set();
  const ledger = createPendingLedger({
    newAttempt: randomId,
    enqueue: (event) => {
      if (!submitted.has(event.attempt)) {
        submitted.add(event.attempt);
        recordInteraction("event_submit", { kind: event.kind, attempt: event.attempt });
      }
      return applicationState.enqueue(
        event,
        saidNow(),
        isThreadEvent(event) ? messageText(event) : void 0
      );
    }
  });
  let dependencies = null;
  const current = () => {
    if (!dependencies) throw new Error("Leaf application has not been mounted");
    return dependencies;
  };
  const startPost = (event) => {
    const { onCollision, afterEnqueue } = current();
    const entry = ledger.enqueue(event);
    if (!entry) {
      onCollision(event.attempt);
      return null;
    }
    afterEnqueue(entry);
    return entry;
  };
  const post2 = (event) => startPost(event)?.answer ?? Promise.resolve(null);
  const dispatchWidget2 = (descriptor, command) => {
    const { withdraw } = current();
    const reading = applicationState.selectWidget(descriptor).read();
    if (command.kind === "undo") {
      const candidate = Object.values(reading.actions).flatMap(({ undo }) => undo).find(
        (event) => "attempt" in event && event.attempt === command.target || event.id === command.target
      );
      return candidate ? withdraw(candidate) : null;
    }
    const revision = readApplication().document.revision;
    if (revision === null) return null;
    const action = reading.actions[command.verb];
    if (!action)
      throw new Error(
        `<${descriptor.tag} id="${descriptor.id}"> cannot dispatch ${JSON.stringify(command.verb)}; its user verbs are: ${Object.keys(reading.actions).join(", ") || "none"}`
      );
    if (!action.available) return null;
    const entry = startPost(actionForWidget(descriptor, command, revision));
    if (!entry) return null;
    if (command.says) current().named(entry, command.says);
    return entry.answer;
  };
  return Object.freeze({
    ledger,
    /** @param {DispatchDependencies} installed */
    mount(installed) {
      dependencies = installed;
    },
    post: post2,
    dispatchWidget: dispatchWidget2
  });
}

// runtime/delivery.js
var RETRY_MS = 2e3;
var retryPause = () => new Promise((resolve) => setTimeout(resolve, RETRY_MS));
var acceptedAnswer = (response, answer) => response.ok && !!answer && "state" in answer && !("final" in answer);
var refusedAnswer = (answer) => !!answer && "final" in answer;
var applyAnswerState = (apply, state) => apply(state).catch((error) => reportCarried(error, "state in event response"));
function createDelivery({
  ledger,
  applyAcceptedState,
  settleRejected,
  settlementChanged,
  refusedWords
}) {
  let draining = false;
  async function deliver(entry) {
    const retrying = holdingError();
    const retry = async (message) => {
      retrying(message);
      await retryPause();
    };
    try {
      return await tries(entry, retry);
    } finally {
      retrying(null);
    }
  }
  async function tries(entry, retry) {
    for (; ; ) {
      if (!ledger.nameEvents(entry)) return { accepted: null };
      const { event } = entry;
      if (entry.admitted) return { accepted: entry.admitted };
      const held = runtime.data;
      const sent = await Promise.race([
        postEvent(event, held).then(
          (response) => ({ response }),
          (error) => ({ error })
        ),
        entry.read.then((accepted) => ({ accepted }))
      ]);
      if (sent.accepted) return { accepted: sent.accepted };
      if (sent.error) {
        await retry(
          runtime.keyRefused ? "Key refused \u2014 open Leaf's link in a new tab and the change will send" : "Connection lost \u2014 keep this page open while it retries"
        );
        continue;
      }
      if (!sent.response) return { accepted: null };
      if (sent.response.status === 503) {
        await retry("The server isn't ready yet \u2014 retrying the change\u2026");
        continue;
      }
      const decoded = await Promise.race([
        sent.response.json().then(
          (answer2) => ({ answer: answer2 }),
          (error) => ({ error })
        ),
        entry.read.then((accepted) => ({ accepted }))
      ]);
      if (decoded.accepted) return { accepted: decoded.accepted };
      if (decoded.error) {
        await retry("Couldn't read the answer \u2014 retrying the change\u2026");
        continue;
      }
      const answer = decoded.answer;
      if (acceptedAnswer(sent.response, answer)) {
        const accepted = answer.state.browser?.receipts?.find(
          (candidate) => candidate.attempt === event.attempt
        );
        if (accepted)
          return {
            accepted,
            application: applyAnswerState(
              applyAcceptedState,
              completeData(answer.state, held)
            )
          };
      }
      if (refusedAnswer(answer) && (!("attempt" in answer) || answer.attempt === event.attempt)) {
        return {
          accepted: null,
          state: completeData(answer.state, held),
          refusal: `Couldn't send \u2014 ${answer.error || "the server refused it"}`
        };
      }
      await retry("Server answer was incomplete \u2014 retrying the change\u2026");
    }
  }
  async function drain() {
    if (draining) return;
    draining = true;
    try {
      for (; ; ) {
        const entry = ledger.nextSending();
        if (!entry) break;
        const { accepted, application: application2, refusal, state } = await deliver(entry);
        if (accepted) ledger.accept(entry, accepted);
        let dependents = [];
        try {
          if (!accepted) {
            dependents = await settleRejected(entry, state);
          }
          settlementChanged(entry, accepted);
        } catch (error) {
          reportCarried(error, "event settlement");
        } finally {
          if (application2) void application2.finally(() => entry.resolve(accepted));
          else {
            entry.resolve(accepted);
            if (refusal) {
              const refused = [
                { attempt: entry.event.attempt, answer: entry.answer },
                ...dependents
              ];
              void Promise.all(refused.map(({ answer }) => answer)).then(
                () => afterScript(() => {
                  const { said, field } = refusedWords(
                    refused.map(({ attempt }) => attempt)
                  );
                  raiseError(said ? `${refusal}. ${said}` : refusal, {
                    subject: field
                  });
                })
              );
            }
          }
        }
      }
    } finally {
      draining = false;
    }
  }
  return { drain };
}
async function deliverBookkeeping(event, applyState) {
  const held = runtime.data;
  let response;
  try {
    response = await postEvent(event, held);
  } catch {
    return "unreached";
  }
  if (!response || response.status === 503) return "unreached";
  let answer;
  try {
    answer = await response.json();
  } catch {
    return "unreached";
  }
  if (answer && "state" in answer)
    await applyAnswerState(applyState, completeData(answer.state, held));
  return acceptedAnswer(response, answer) ? "accepted" : refusedAnswer(answer) ? "refused" : "unreached";
}

// runtime/undo.js
var WAIT = "Wait for the current change to finish before undoing";
var quoted2 = (words, cap = 60) => `\u201C${excerptWords(words, cap)}\u201D`;
function widgetNamed(id) {
  const element = elementById(id);
  if (!element) return "a widget";
  const label = addressableLabel(element);
  return label ? quoted2(label) : `the ${addressableWord(element)}`;
}
function actionWords(event, gesture) {
  const widget = widgetNamed(event.widget);
  switch (gesture?.form) {
    case "choice":
      return `chose ${gesture.chosen.map((words) => quoted2(words)).join(", ") || "nothing"} in ${widget}`;
    case "move":
      return `moved ${quoted2(gesture.unit)} to ${quoted2(gesture.to)} in ${widget}`;
    case "edit":
      return `edited ${widget}`;
    case "add":
      return `added ${quoted2(gesture.words)} to ${widget}`;
    case "verb":
      return `recorded \u201C${gesture.verb}\u201D on ${widget}`;
    default:
      return `updated ${widget}`;
  }
}
var TODO_ENDINGS = {
  done: (title) => `marked ${title} done`,
  failed: (title) => `marked ${title} failed`,
  dropped: (title) => `dropped ${title}`
};
function gestureWords(event, gesture) {
  if (event.token) return `${event.token} reaction on ${reactionPlace(event)}`;
  switch (event.kind) {
    case "resolve":
    case "unresolve": {
      const thread = threadNamed(event.parent);
      const name = thread ? quoted2(threadName(thread), 48) : "a thread";
      return `${event.kind === "resolve" ? "resolved" : "reopened"} ${name}`;
    }
    case "todo_end": {
      const todo = runtime.todos.find(({ id }) => id === event.todo);
      return TODO_ENDINGS[event.outcome](todo ? quoted2(todo.title) : "a to-do");
    }
    default:
      return actionWords(event, gesture);
  }
}
function placeOf2(event) {
  if (["resolve", "unresolve", "reply"].includes(event.kind))
    return { thread: threadIdNamed(event.parent), nodes: [] };
  const id = event.kind === "action" ? event.widget : event.anchor?.section;
  if (!id) return null;
  const held = messageHolding(id);
  if (held)
    return { thread: held.thread, message: held.message, nodes: [held.element] };
  return { fragment: id, nodes: [elementById(id)] };
}
var seen = (where) => Boolean(where && seenRect(placeHolder(where), /* @__PURE__ */ new Map(), placeBox(where)));
var KEYS_HELD = /* @__PURE__ */ new Set(["Shift", "Control", "Alt", "Meta", "CapsLock", "Fn"]);
function createUndo({
  post: post2,
  stateApplying,
  unaccountedGesture,
  openThread,
  threadPlace: threadPlace2
}) {
  const gestures = /* @__PURE__ */ new Map();
  function retainGesture(attempt, facts) {
    const { effective, unresolved } = readApplication();
    if (effective.view) {
      const liveAttempts = /* @__PURE__ */ new Set([
        ...effective.view.undo.map(({ event }) => event.attempt),
        ...unresolved.map((entry) => entry.event.attempt)
      ]);
      for (const kept of gestures.keys())
        if (!liveAttempts.has(kept)) gestures.delete(kept);
    }
    gestures.set(attempt, { ...gestures.get(attempt), ...facts });
  }
  const said = (event) => {
    const gesture = runtime.undo.find((entry) => entry.event.id === event.id)?.gesture;
    return gestures.get(event.attempt)?.says ?? gestureWords(event, gesture);
  };
  const takes = (event) => [said(event), ago(event.ts)].filter(Boolean).join(" \xB7 ");
  const head = () => {
    const [first] = runtime.undo;
    return first?.newest ? first.event : null;
  };
  function undoable() {
    return stateApplying() ? null : head();
  }
  function withdrawable(event) {
    if (event.kind !== "action" && String(event.id).startsWith(PENDING)) return false;
    return !applicationState.unpresented().some(
      (entry) => entry.event.kind === "action" && (entry.admitted?.id ?? entry.localId) !== event.id
    );
  }
  function withdraw(event) {
    if (!withdrawable(event)) {
      raiseError(WAIT);
      return null;
    }
    const reverse = gestures.get(event.attempt)?.reverse;
    const taken = takes(event);
    const mayLand = retainUserIntent();
    const answer = post2({ kind: "undo", undoes: event.id }).then((accepted) => {
      if (accepted) {
        notice(`Undid: ${taken} \u2014 sent`);
        gestures.delete(event.attempt);
      }
      return accepted;
    });
    if (reverse)
      void answer.then(async (accepted) => {
        if (!accepted) return;
        await whenDocumentPresented();
        await reverse(mayLand);
      }).catch(() => {
      });
    return answer;
  }
  let armed = null;
  function disarm() {
    armed?.stop();
    armed = null;
  }
  onUserInput((event) => {
    if (!armed || event.type === "wheel" || event.type === "blur") return;
    if (event.type === "keydown" && (event.repeat || KEYS_HELD.has(event.key))) return;
    if ((event.type === "pointerdown" || event.type === "touchstart") && inChrome(
      /** @type {Node} */
      event.composedPath()[0]
    ))
      return;
    armed.inputs.push(inputCount());
    if (armed.inputs.length > 1) disarm();
  });
  const armedFor = (event) => armed?.id === event.id && armed.shown && armed.inputs.every((input) => input === inputCount());
  const drawingsOf = (id) => [
    ...[...document.querySelectorAll(THREAD)].filter(
      (node) => drawnThreadId(
        /** @type {HTMLElement} */
        node
      ) === id
    ),
    surfaceFocusTarget(id, { part: "thread" })
  ];
  const inView = (place) => [
    ...place.thread ? [threadPlace2(place.thread), ...drawingsOf(place.thread)] : [],
    ...place.nodes
  ].some(seen);
  function needsShowing(entry) {
    if (entry.picked_up) return true;
    if (gestures.get(entry.event.attempt)?.reverse) return false;
    const place = placeOf2(entry.event);
    return Boolean(place) && !inView(place);
  }
  async function show(event) {
    const place = placeOf2(event);
    if (!place) return [];
    if (place.thread) {
      const opened = await openThread(place.message ?? place.thread, {
        part: place.message ? "message" : "thread"
      });
      return [opened, ...place.nodes].filter(Boolean);
    }
    const url = new URL(window.location.href);
    url.hash = place.fragment;
    if (window.navigation)
      await window.navigation.navigate(url.href).finished.catch(() => {
      });
    else window.location.assign(url);
    return place.nodes.filter(Boolean);
  }
  function arm(event) {
    disarm();
    let stop = () => {
    };
    const current = { id: event.id, stop: () => stop(), inputs: [], shown: false };
    armed = current;
    notice(`Press again to undo: ${takes(event)}`);
    void show(event).then((nodes) => {
      if (armed !== current) return;
      current.shown = true;
      if (!nodes.length) return;
      let landed = false;
      stop = whenNone(
        nodes,
        (node, clips) => {
          const shown = seenRect(node, clips);
          landed ||= Boolean(shown);
          return shown;
        },
        () => {
          if (landed && armed === current) disarm();
        }
      );
    });
  }
  function undoLast() {
    if (stateApplying() || unaccountedGesture()) {
      raiseError(WAIT);
      return null;
    }
    const event = undoable();
    if (!event) return null;
    if (!armedFor(event) && needsShowing(runtime.undo[0])) {
      arm(event);
      return null;
    }
    disarm();
    return withdraw(event);
  }
  pageCommand({
    id: "history.undo",
    ready: savedReadingSettled,
    keys: ["z"],
    // Said from the list the page holds rather than `undoable`, so a reading being
    // applied leaves the words standing while it holds the press back. The menu's row
    // cuts long words, so it says the age at its end rather than after them. The words
    // stand whether the press will show or take: which it does turns on where the user
    // is reading when they press, which a scroll changes without a repaint.
    description: () => head() ? `Undo: ${takes(head())}` : "Undo the latest update",
    title: "undo",
    touch: () => head() ? `Undo: ${said(head())}` : "Undo",
    touchValue: () => head() ? ago(head().ts) : "",
    menu: "page",
    // Dead while the page holds a gesture no log read accounts for, this one's own send
    // included. The line drops the chip for as long as that is true rather than
    // promising a press that would undo the wrong thing.
    when: () => !unaccountedGesture() && Boolean(undoable()),
    run: (...args) => undoLast(...args)
  });
  return {
    retainGesture,
    undoable,
    undoLast,
    withdraw
  };
}

// runtime/projection/data.js
var projectedDescendants = (root) => [root, ...shadowRootsIn(root)].flatMap((scope) => [...scope.querySelectorAll(DATUM)]).filter((element) => element.dataset.lfProjection === root.id);
function createDataProjection({ invalidateDom: invalidateDom2 }) {
  let dataPaintQueued = false;
  const changedRoots = /* @__PURE__ */ new Set();
  function applyProjection(root) {
    changedRoots.add(root);
    if (dataPaintQueued) return;
    dataPaintQueued = true;
    queueMicrotask(() => {
      dataPaintQueued = false;
      for (const changed of changedRoots)
        if (changed.isConnected) reachScrollers(changed);
      changedRoots.clear();
      invalidateDom2();
    });
  }
  function projectData2(root, datums, { snapshot } = {}) {
    if (!root.id)
      throw new TypeError("projectData root needs an id to name its projection");
    const declaredInputs = registry[root.localName]?.["x-data"] ?? {};
    if (snapshot === void 0 && Object.values(declaredInputs).some(
      ({ source, reference }) => source && root.hasAttribute(source) || reference && root.hasAttribute(reference)
    ))
      throw new Error(
        `projectData(${root.id}) must receive the snapshot that supplied its records`
      );
    const stampBasis = (node) => {
      keeps(node, "data-lf-source", snapshot?.source ?? null);
      keeps(node, "data-lf-source-revision", snapshot?.revision ?? null);
    };
    stampBasis(root);
    const projected = projectedDescendants(root);
    const keys2 = /* @__PURE__ */ new Set();
    const identities = /* @__PURE__ */ new Set();
    const nodes = /* @__PURE__ */ new Set();
    for (const {
      node,
      key,
      label,
      identity: identity2,
      origin = snapshot?.origin ?? null
    } of datums) {
      if (typeof key !== "string" || !key)
        throw new TypeError(`projectData(${root.id}) keys must be non-empty strings`);
      if (keys2.has(key))
        throw new Error(`projectData(${root.id}) received duplicate key ${key}`);
      keys2.add(key);
      if (identity2 !== void 0) {
        if (typeof identity2 !== "string" || !identity2)
          throw new TypeError(
            `projectData(${root.id}) identity for ${key} must be a non-empty string`
          );
        if (identities.has(identity2))
          throw new Error(
            `projectData(${root.id}) received duplicate identity ${identity2}`
          );
        identities.add(identity2);
      }
      if (node === root || nodes.has(node))
        throw new Error(`projectData(${root.id}) reused the node for key ${key}`);
      if (!under(node, root))
        throw new Error(`projectData(${root.id}) datum ${key} is outside its root`);
      nodes.add(node);
      const priorLabel = node.dataset.lfDatumLabel;
      if (label !== void 0) {
        keeps(node, "data-lf-datum-label", label);
        if (!node.hasAttribute("aria-label") && (!node.hasAttribute("aria-description") || node.getAttribute("aria-description") === priorLabel))
          keeps(node, "aria-description", label);
      } else if (priorLabel !== void 0) {
        if (node.getAttribute("aria-description") === priorLabel)
          node.removeAttribute("aria-description");
        delete node.dataset.lfDatumLabel;
      }
      keeps(node, "data-lf-gen", "1");
      keeps(node, "data-lf-projection", root.id);
      keeps(node, "data-lf-datum", key);
      stampBasis(node);
      keeps(node, "data-lf-identity", identity2 ?? null);
      keeps(node, "data-lf-origin", origin === null ? null : JSON.stringify(origin));
    }
    for (const node of projected)
      if (!nodes.has(node)) {
        delete node.dataset.lfGen;
        delete node.dataset.lfProjection;
        delete node.dataset.lfDatum;
        delete node.dataset.lfIdentity;
        delete node.dataset.lfSource;
        delete node.dataset.lfSourceRevision;
        delete node.dataset.lfOrigin;
        const label = node.dataset.lfDatumLabel;
        if (label !== void 0) {
          if (node.getAttribute("aria-description") === label)
            node.removeAttribute("aria-description");
          delete node.dataset.lfDatumLabel;
        }
      }
    applyProjection(root);
  }
  return { projectData: projectData2 };
}

// runtime/thread/presentation.js
function renderHolds(threads) {
  const held = /* @__PURE__ */ new Map();
  for (const thread of threads) {
    if (thread.resolved || !thread.root.holds || thread.root.pending) continue;
    const target = elementById(thread.root.holds);
    if (target && !inChrome(target)) held.set(target, thread.id);
  }
  for (const node of document.querySelectorAll("[data-lf-held]"))
    if (!held.has(node)) node.removeAttribute("data-lf-held");
  for (const [target, id] of held) keeps(target, "data-lf-held", id);
}
function createThreadPresentation({
  available = true,
  inlineView,
  surfaceView,
  anchorPlacement,
  anchorPaint,
  anchorControls,
  drawingPaint,
  pageGeometry,
  readDraft,
  activeActionAnchor,
  renderAnnotations,
  renderSurfaces: renderSurfaces2,
  openThread,
  continueThread,
  threadAt,
  read: read2
}) {
  let primary = null;
  const presenter = applicationPresenter({
    region: "thread",
    after: PRESENTATION_DOM.projection,
    reading: () => !available ? null : runtime.statePhase === "waiting" && !threadState().all.length ? "waiting" : true,
    // A pass reads the latest root. The time it shows is followed with the rest of what
    // it reads, so a clock change claims another pass through the same presenter, whose
    // current predicate also retires in-flight preparation.
    paint: async (value, current, resume) => {
      await startRender(current, resume);
      return value;
    }
  });
  const present = () => presenter.present();
  let surfaceGeneration = 0;
  let cancelCurrentRender = () => {
  };
  const startRender = (presenting, resume = (run) => run) => {
    cancelCurrentRender();
    const { promise: cancelled, resolve } = Promise.withResolvers();
    cancelCurrentRender = resolve;
    return renderReading(cancelled, presenting, resume);
  };
  async function renderReading(cancelled, presenting, resume) {
    const generation = ++surfaceGeneration;
    read2.begin();
    const current = () => generation === surfaceGeneration && presenting();
    const batch = beginThreadSeats();
    const restorePlace2 = holdThreadPlace(openThread, {
      threadAt,
      seated: (id) => Boolean(surfaceFocusTarget(id, { part: "thread" }))
    });
    let surfaces = null;
    try {
      const { all: threads } = threadState();
      const collection = readThreads();
      const listed = collection.threads;
      const continueReplies = holdReplyCompositions(threads, continueThread);
      renderHolds(threads);
      const readTargets = () => {
        const anchors = anchorPlacement.read({
          threads,
          draft: readDraft(),
          actionAnchor: activeActionAnchor()
        });
        if (anchors) {
          anchorPaint?.paint(anchors);
          anchorControls.render(anchors);
        }
        drawingPaint.paint();
      };
      readTargets();
      surfaces = renderSurfaces2(collection, anchorPlacement, surfaceView);
      void surfaces.completion.catch(() => {
      });
      const primaryPreparation = primary?.owner.isConnected ? primary.prepare(collection, cancelled) : null;
      const paintPrepared = (primaryCandidate) => {
        if (!current()) return;
        renderSeats(listed, inlineView);
        return Promise.race([
          Promise.all([
            surfaces.completion,
            // The reader paints after this stretch, so what it reads is its own.
            Promise.resolve().then(
              () => current() && primaryCandidate?.current() ? primaryCandidate.paint() : null
            )
          ]).then(() => true),
          cancelled.then(() => false)
        ]).then(
          resume((completed) => {
            if (!completed || !current()) return;
            readTargets();
            surfaces.commit();
            commitThreadSeats(batch);
            surfaceView.composition.finishPlacement();
            d(renderAnnotations);
            pageGeometry.pageShifted();
            read2.present();
            void continueReplies(restorePlace2).catch(
              (error) => reportPageError(error, `Reply continuation failed`)
            );
          })
        );
      };
      await (primaryPreparation?.then ? primaryPreparation.then(resume(paintPrepared)) : paintPrepared(primaryPreparation));
    } catch (error) {
      surfaces?.cancel();
      if (!current()) throw error;
      anchorControls.withholdVisualActions();
      read2.abort();
      primary?.cancel();
      if (!current()) return;
      retainThreadSeats(batch);
      throw error;
    }
  }
  function registerPrimary(reader) {
    if (primary) throw new Error("The page already has a primary Thread presentation");
    primary = reader;
    void present();
    return () => {
      if (primary !== reader) return;
      primary = null;
      reader.unregister();
      void present();
    };
  }
  return {
    present,
    registerPrimary
  };
}

// runtime/annotation-view.js
function createAnnotationView(owner, render2, inventory, invalidate, retire) {
  if (!(owner instanceof Element))
    throw new TypeError("consumeAnnotations needs an Element owner");
  if (!owner.isConnected)
    throw new TypeError("An annotation view needs a connected owner");
  if (typeof render2 !== "function")
    throw new TypeError("consumeAnnotations needs a synchronous render callback");
  let active = true;
  let places2 = /* @__PURE__ */ new Map();
  let offers = /* @__PURE__ */ new Set();
  const stopSide = declareSide((node) => {
    for (const [row, entry] of places2)
      if (under(node, row)) return inventory.entryPlace(entry);
    return null;
  });
  function paint(entries) {
    if (!active) return;
    if (!owner.isConnected) return unregister();
    const nextPlaces = /* @__PURE__ */ new Map();
    const nextOffers = /* @__PURE__ */ new Set();
    const allowed = new Set(entries);
    let painting = true;
    const admit = (entry) => {
      if (!painting || !allowed.has(entry))
        throw new TypeError("Annotation capabilities belong to their current reading");
    };
    try {
      const result = render2(entries, {
        target: inventory.targetFor,
        activate: inventory.activate,
        items: annotationItems,
        controlKey: contributionControlKey,
        controlRecord: contributionEntryRecord,
        arriving: entries.some(
          (entry) => entry.offers.some((model) => {
            const offered = contributionSource(model);
            const request = offered.focusRequest;
            return request && (request.surface == null || request.surface === "page") && offered.reading.entries.some(
              (item) => item.key === request.key && item.visible
            );
          })
        ),
        place(entry, row) {
          admit(entry);
          if (!(row instanceof Element) || !under(row, owner))
            throw new TypeError("An annotation row must stay inside its owner");
          nextPlaces.set(row, entry);
        },
        controls(entry) {
          admit(entry);
          const retained = new Map(
            entry.offers.map((model) => {
              const offered = contributionSource(model);
              nextOffers.add(offered);
              return [
                model,
                materializeContributionControls(
                  offered,
                  "page",
                  activateContributionControl
                )
              ];
            })
          );
          return entryControls(entry).map(({ offered, record, receipt }) => {
            const control = retained.get(offered).get(record.key);
            presentContributionReceipts(control, receipt, false);
            return control;
          });
        }
      });
      if (result?.then)
        throw new TypeError(
          "Annotation paint must finish inside its inventory reading"
        );
      for (const offered of offers)
        if (!nextOffers.has(offered))
          clearContributionControls(offered, "page", /* @__PURE__ */ new Set());
      offers = nextOffers;
      places2 = nextPlaces;
    } catch (error) {
      for (const offered of nextOffers)
        if (!offers.has(offered)) clearContributionControls(offered, "page", /* @__PURE__ */ new Set());
      throw error;
    } finally {
      painting = false;
    }
  }
  let stopReading = () => {
  };
  function unregister() {
    if (!active) return;
    active = false;
    stopReading();
    stopSide();
    for (const offered of offers) clearContributionControls(offered, "page", /* @__PURE__ */ new Set());
    offers.clear();
    places2.clear();
    retire();
  }
  try {
    stopReading = inventory.watch(paint);
  } catch (error) {
    unregister();
    throw error;
  }
  return Object.freeze({ read: inventory.read, update: invalidate, unregister });
}

// runtime/inline-contributions.js
function createInlineContributions({ targetPath }) {
  const hosts = /* @__PURE__ */ new Map();
  function present() {
    const grouped = /* @__PURE__ */ new Map();
    for (const offered of contributionEntries()) {
      const target = offered.target();
      if (!target?.isConnected || !inChrome(target) || !offered.reading.entries.some((entry) => entry.visible))
        continue;
      const offers = grouped.get(target) ?? [];
      offers.push(offered);
      grouped.set(target, offers);
    }
    for (const [target, { host, offers }] of hosts)
      if (!grouped.has(target)) {
        for (const offered of offers)
          clearContributionControls(offered, "inline", /* @__PURE__ */ new Set());
        host.replaceChildren();
        host.remove();
        hosts.delete(target);
      }
    for (const [target, offers] of grouped) {
      let seat = hosts.get(target);
      if (!seat) {
        const host2 = el("div", "lf-ui lf-margin-inline");
        host2.dataset.lfGen = "1";
        host2.setAttribute("role", "group");
        seat = { host: host2, offers: [] };
        hosts.set(target, seat);
      }
      const { host } = seat;
      for (const offered of seat.offers)
        if (!offers.includes(offered))
          clearContributionControls(offered, "inline", /* @__PURE__ */ new Set());
      seat.offers = offers;
      host.lfTarget = target;
      keeps(host, "data-lf-margin-for", target.id || targetPath(target));
      keeps(
        host,
        "aria-label",
        `Actions for ${spokenSubject(addressableWord(target))}`
      );
      const controls = (side) => offers.filter((offered) => offered.reading.side === side).sort(compareContributions).flatMap((offered) => {
        const materialized = materializeContributionControls(
          offered,
          "inline",
          activateContributionControl
        );
        return offered.reading.entries.filter((entry) => entry.visible).map((entry) => {
          const control = materialized.get(entry.key);
          presentContributionReceipts(control, entry.workflowReceipt, false);
          return control;
        });
      });
      const nodes = [...controls("before"), ...controls("after")];
      for (const node of nodes) node.removeAttribute("data-lf-margin-entry-primary");
      const restoreFocus = holdFocus(host);
      setChildren(host, nodes);
      restoreFocus?.();
      if (target.nextSibling !== host)
        move(target.parentNode, host, target.nextSibling);
    }
  }
  return Object.freeze({ present });
}

// runtime/thread/destination.js
function createThreadDestinations({
  placedAt,
  threadIdsAt,
  scrollToThread,
  arrive,
  prepareTrip,
  preview = null
}) {
  let presentation = null;
  let opening = null;
  function register(owner, open, reader) {
    if (presentation) throw new Error("The page already has a Thread presentation");
    const registration = { owner, open, reader };
    presentation = registration;
    return () => {
      if (presentation === registration) {
        presentation = null;
        opening?.abort();
      }
    };
  }
  const threadTarget = (id) => placedAt(id)?.place ?? null;
  const threadPlace2 = (id) => {
    const thread = allThreads().find((candidate) => candidate.id === id);
    return thread ? threadPlace(thread, placedAt) : null;
  };
  const threadHere = () => {
    const held = heldThread();
    if (held) return held;
    const shown = preview?.accompanied() ?? null;
    const active = focused();
    if (!active || active === document.body) return shown;
    const ids = threadIdsAt(active);
    const drawn2 = [
      shown,
      ...ids.map((id) => surfaceFocusTarget(id, { part: "thread" }))
    ].filter((thread) => thread && ids.includes(drawnThreadId(thread)));
    return drawn2.length === 1 ? drawn2[0] : null;
  };
  const threadAtStanding = () => {
    const here = drawnThreadId(threadHere());
    if (here) return here;
    const active = focused();
    return (active && threadIdsAt(active)[0]) ?? null;
  };
  const replyThreadAtStanding = () => {
    const id = threadAtStanding();
    const thread = allThreads().find((candidate) => candidate.id === id);
    return thread && replyAvailable(thread) ? id : null;
  };
  const threadFocusTarget = (id, { part = null } = {}) => surfaceFocusTarget(id, { part }) ?? preview?.focusTarget(id, { part }) ?? null;
  const DECLINED = /* @__PURE__ */ Symbol("declined");
  const UNDRAWN = /* @__PURE__ */ Symbol("undrawn");
  async function openPageThread(id, {
    part = null,
    focus = true,
    travel: travel2 = true,
    flash = true,
    scroll = true,
    intent = retainUserIntent(),
    origin = null
  } = {}) {
    if (!intent()) return null;
    const trip = travel2 && scroll;
    const selected = presentation?.owner.isConnected ? presentation : null;
    const thread = threadNamed(id);
    if (selected && (!thread || !discussed(thread))) return null;
    const holder = part === "message" ? authoredHolder(id) : null;
    const drawn2 = Boolean(selected && holder && renderedUnder(holder, selected.owner));
    function inPrimary(last2) {
      opening?.abort();
      const abort = new AbortController();
      opening = abort;
      const cancelled = aborted(abort.signal);
      const whileCurrent = (work) => Promise.race([work, cancelled]);
      const request = {
        message: part === "message" ? thread.msgs.find((message) => message.id === id)?.key ?? null : null,
        part,
        focus,
        last: last2,
        signal: abort.signal,
        current: () => !abort.signal.aborted && presentation === selected && selected.owner.isConnected && (focus === false ? intent.available() : intent())
      };
      const mayPresent = () => !abort.signal.aborted && presentation === selected && selected.owner.isConnected && (focus === false ? intent.available() : intent());
      const arriving = restrictUserIntent(intent, mayPresent);
      const departure = focus !== false && trip ? prepareTrip({
        landing: () => selected.reader.destination(thread.key, request),
        intent: arriving
      }) : null;
      const result = selected.open(thread.key, request);
      if (result === false && !drawn2) return mayPresent() ? DECLINED : null;
      return taken(result);
      async function taken(result2) {
        const selectedLayout = result2?.then ? await whileCurrent(result2) : result2;
        if (!mayPresent()) return null;
        if (selectedLayout === false && !drawn2) return DECLINED;
        await whileCurrent(selected.reader.update());
        if (!mayPresent()) return null;
        const destination = selected.reader.destination(thread.key, request);
        if (destination === null) return UNDRAWN;
        if (!(destination instanceof Element) || !destination.isConnected || !renderedUnder(destination, selected.owner) || !selected.reader.ownsDestination(destination))
          throw new TypeError(
            "A Thread destination must be a retained part of its registered presentation"
          );
        if (focus === false) {
          await whileCurrent(reveal(destination, intent).ready);
          return mayPresent() ? destination : null;
        }
        departure?.plan(destination);
        const reached = await whileCurrent(
          arrive(
            () => {
              const current = selected.reader.destination(thread.key, request);
              return current && {
                where: current,
                focus: current,
                scroll: trip ? [{ at: current, block: "nearest" }] : []
              };
            },
            { intent: arriving, departure }
          )
        );
        return reached ? selected.reader.destination(thread.key, request) : null;
      }
    }
    async function onPage() {
      const mayPresent = () => focus === false ? intent.available() : intent();
      const localPart = part ?? "reply";
      if (part === "message") showHeld(id);
      const openSurface = async () => {
        if (preview) intent.handoff(preview.close);
        if (trip) {
          if (!await scrollToThread(id, { part: localPart, focus, intent }))
            return null;
        } else if (focus === false) {
          await reveal(surfaceFocusTarget(id, { part: localPart }), intent).ready;
          if (!mayPresent()) return null;
        } else if (!await arrive(
          () => {
            const current = surfaceFocusTarget(id, { part: localPart });
            return current && {
              where: current,
              focus: current,
              scroll: scroll ? [{ at: current, block: "nearest", behavior: "auto" }] : []
            };
          },
          { intent }
        ))
          return null;
        return surfaceFocusTarget(id, { part: localPart });
      };
      if (surfaceFocusTarget(id, { part: localPart })) return openSurface();
      if (showHeldThread(id) && surfaceFocusTarget(id, { part: localPart }))
        return openSurface();
      const place = preview && !trip ? threadTarget(id) : null;
      const placeDrawn = () => visibleTargetParts(place).length > 0;
      if (place && scroll && !placeDrawn()) {
        await reveal(place, intent).ready;
        if (!mayPresent()) return null;
      }
      let opened = null;
      if (preview && (!place || placeDrawn()))
        intent.handoff(() => {
          opened = preview.open(id, { origin });
        });
      if (opened) {
        if (trip) {
          if (!await scrollToThread(id, {
            part: part ?? "thread",
            focus,
            presented: opened.presented,
            intent
          }))
            return null;
        } else {
          if (!await opened.presented || !mayPresent()) return null;
          if (focus !== false && !await arrive(
            () => {
              const current = threadFocusTarget(id, { part });
              return current && {
                where: current,
                focus: current,
                scroll: scroll ? [{ at: current, block: "nearest" }] : []
              };
            },
            { intent }
          ))
            return null;
        }
        return threadFocusTarget(id, { part });
      }
      const held = revealHeld([threadIdNamed(id)]);
      if (held) {
        await held.presented;
        if (!mayPresent()) return null;
      }
      if (surfaceFocusTarget(id, { part: localPart })) return openSurface();
      return DECLINED;
    }
    const asked = selected ? inPrimary(false) : DECLINED;
    const first = asked instanceof Promise ? await asked : asked;
    if (first !== DECLINED && first !== UNDRAWN) return first;
    const shown = await onPage();
    if (shown !== DECLINED) return shown;
    if (!selected || first !== DECLINED) return null;
    const last = await inPrimary(true);
    return last === DECLINED || last === UNDRAWN ? null : last;
  }
  async function openThreadSubject(id, { intent = retainUserIntent() } = {}) {
    const message = placedAt(id)?.message;
    if (!message) return null;
    const { element } = messageHolding(threadNamed(id).anchor.section);
    const shown = await openPageThread(message, {
      part: "message",
      focus: false,
      travel: false,
      intent
    });
    if (!shown || !element.isConnected) return null;
    const arrived = await arrive(
      () => element.isConnected && {
        where: element,
        focus: element,
        scroll: [{ at: element, block: "nearest" }]
      },
      { intent }
    );
    return arrived ? element : null;
  }
  async function openThreadDraft(context, intent) {
    const thread = threadHolding(context);
    if (!thread) return null;
    const { part, name } = threadDraft(context);
    if (part === "reply") return openPageThread(thread.id, { part: "reply", intent });
    const landed = await openPageThread(name, { part: "message", intent });
    const card = landed && closestAcross(landed, THREAD);
    return card ? openMessageEditIn(card, name) : null;
  }
  function threadHolding(context) {
    const { part, name } = threadDraft(context);
    return part === "reply" ? allThreads().find((each) => threadKey(each) === name) : allThreads().find((each) => each.msgs.some(({ id }) => id === name));
  }
  return {
    register,
    openPageThread,
    openThreadSubject,
    openThreadDraft,
    holdsThreadDraft: (context) => Boolean(threadHolding(context)),
    threadFocusTarget,
    threadHere,
    threadAtStanding,
    replyThreadAtStanding,
    threadTarget,
    threadPlace: threadPlace2
  };
}

// runtime/thread/actions.js
function createThreadActions({
  post: post2,
  withdraw,
  sendReaction: sendReaction2,
  currentRevision,
  open
}) {
  const create = (command) => {
    const {
      text,
      anchor,
      revision = currentRevision(),
      attempt = randomId(),
      holds,
      about,
      drawing,
      suggestion
    } = command;
    if (!text && !drawing) return null;
    const delivery = post2({
      kind: "comment",
      revision,
      ...text !== void 0 && { text },
      ...anchor !== void 0 && { anchor: structuredClone(anchor) },
      ...attempt !== void 0 && { attempt },
      ...holds !== void 0 && { holds },
      ...about !== void 0 && { about },
      ...drawing !== void 0 && { drawing: structuredClone(drawing) },
      ...suggestion !== void 0 && { suggestion }
    });
    return delivery ? Object.freeze({ key: attempt, delivery }) : null;
  };
  const find = (key) => readThreads().threads.find((thread) => thread.key === key);
  const reply = (key, text, { attempt } = {}) => {
    if (!text) return null;
    const thread = find(key);
    if (!thread?.offers.reply) return null;
    return post2({
      kind: "reply",
      revision: currentRevision(),
      parent: thread.root.id,
      text,
      ...attempt && { attempt }
    });
  };
  const edit = (key, messageId, text, { attempt, base } = {}) => {
    const thread = find(key);
    if (!thread || thread.settling) return null;
    const message = thread.msgs.find((item) => item.id === messageId);
    if (!message || !editable(message) || !text || text === message.text) return null;
    return post2({
      kind: "edit",
      message: messageId,
      text,
      base,
      ...attempt && { attempt }
    });
  };
  const settle = (key, resolved, { attempt } = {}) => {
    const thread = find(key);
    if (!thread?.offers[resolved ? "resolve" : "reopen"]) return null;
    return post2({
      kind: resolved ? "resolve" : "unresolve",
      parent: thread.root.id,
      ...attempt && { attempt }
    });
  };
  const setReaction = (key, messageKey, token, active) => {
    if (typeof active !== "boolean")
      throw new TypeError("A reaction needs its desired state");
    const thread = find(key);
    const message = thread?.msgs.find((item) => item.key === messageKey);
    const choice = message && message.reactions?.choices.find((item) => item.name === token);
    if (!choice || active === Boolean(choice.inForce)) return null;
    if (choice.inForce) return withdraw(choice.inForce);
    return sendReaction2(
      {
        kind: "reply",
        parent: message.id,
        revision: currentRevision(),
        token
      },
      `${message.agent}'s reply`,
      post2
    );
  };
  return Object.freeze({
    async open(key, { message = null, ...options } = {}) {
      const thread = find(key);
      if (!thread?.offers.open) return null;
      const target = message === null ? thread : thread.msgs.find((item) => item.key === message);
      if (!target) return null;
      return open(
        target.id,
        message === null ? options : { ...options, part: "message" }
      );
    },
    create,
    reply,
    edit,
    resolve: (key, options) => settle(key, true, options),
    reopen: (key, options) => settle(key, false, options),
    setReaction
  });
}

// runtime/thread/primary-reader.js
function createPrimaryReader(owner, render2, commands, update, { answersAtOnce = false, onFailure = () => {
} } = {}) {
  let active = true;
  let failing = false;
  let failed = false;
  let generation = 0;
  let pending = null;
  let selected = [];
  const views = /* @__PURE__ */ new Map();
  const destinations = /* @__PURE__ */ new Map();
  const nativeMessages = /* @__PURE__ */ new Set();
  const held = new HeldNews(
    owner,
    (key) => {
      const parts = destinations.get(key);
      if (!parts?.length) return null;
      const whole = parts.find((part) => part instanceof ThreadView);
      if (whole) return whole;
      return {
        node: drawingOf(parts) ?? parts.at(-1).node,
        progressOpen: parts.some((part) => part.transcript?.progressOpen),
        // A presentation that makes room for the agent's answer to the user's last turn
        // itself (`answersAtOnce`) is handed it whatever it moves. A transcript moves
        // what a card's would (transcript.js, `newsMoves`).
        newsMoves: (held2) => !(answersAtOnce && held2.answers) && parts.some(
          (part) => part.transcript ? part.transcript.newsMoves(held2) : (held2.news.appended || held2.news.settled || held2.changed.has(part.messageKey) || held2.folds.messages.includes(part.messageKey) || held2.folds.summaries.length) && growthIsSeen(part.node)
        )
      };
    },
    () => void update().catch(() => {
    })
  );
  let shown = /* @__PURE__ */ new Map();
  const drawingOf = (parts) => {
    const whole = wholeThread(parts[0].node);
    return whole === parts[0].node ? null : whole;
  };
  const rewrites = /* @__PURE__ */ new Map();
  const partsOf = (key, kind) => selected.filter((item) => item.key === key && item.kind === kind).flatMap((item) => views.get(item.identity) ?? []);
  const replyOf = (key) => {
    for (const view of destinations.get(key) ?? []) {
      const input = !view.node.hidden && threadPart(view.node, "reply");
      if (input) return input;
    }
    return null;
  };
  const rewritesOf = (key) => {
    if (!rewrites.has(key))
      rewrites.set(
        key,
        threadRewrites({
          thread: () => key,
          views: () => {
            const transcript = partsOf(key, "transcript")[0];
            if (transcript) return transcript.transcript.views;
            const order = shown.get(key)?.source.msgs.map((message) => message.key);
            return partsOf(key, "message").toSorted(
              (a, b) => (order?.indexOf(a.messageKey) ?? 0) - (order?.indexOf(b.messageKey) ?? 0)
            ).map((view) => view.message);
          },
          send: (id, text, options) => commands.reply.actions.edit(key, id, text, options),
          paint: (node) => [...partsOf(key, "transcript"), ...partsOf(key, "message")].find((view) => view.transcript || view.message.node === node)?.draw(),
          box: () => replyOf(key),
          home: (node) => node.closest(THREAD),
          opening: (id) => {
            shown.get(key)?.news?.open();
            partsOf(key, "transcript")[0]?.transcript.expandAround(id);
          },
          landInThread: commands.reply.landInThread,
          landSent: commands.reply.landSent
        })
      );
    return rewrites.get(key);
  };
  const clear = () => {
    for (const view of views.values()) {
      view.dispose();
      view.node.remove();
      for (const slot of view.slots ?? []) slot.remove();
    }
    views.clear();
    destinations.clear();
    nativeMessages.clear();
    rewrites.clear();
  };
  function prepare(collection, cancelled) {
    const current = ++generation;
    failing = false;
    pending?.abort();
    const abort = new AbortController();
    pending = abort;
    void cancelled.then(() => abort.abort());
    const candidate = held.prepare(
      {
        threads: collection.threads.map(
          (thread) => threadReading(thread, "outlet", { ...commands, authoredRank: 3 })
        )
      },
      { row: false }
    );
    const byKey = new Map(
      candidate.reading.threads.map((thread) => [thread.key, thread.source])
    );
    const shownCollection = Object.freeze({
      phase: collection.phase,
      threads: Object.freeze([...byKey.values()])
    });
    const nominations = [];
    let accepting = true;
    const nominate = (kind, key, message, outlet, options = {}) => {
      if (!accepting || abort.signal.aborted)
        throw new Error("Thread nominations belong to their current render callback");
      const thread = byKey.get(key);
      if (!thread) throw new Error(`No Thread has key ${key}`);
      if (message !== null && !turns(thread).some((item) => item.key === message))
        throw new Error(`Thread ${key} has no turn ${message}`);
      const identity2 = JSON.stringify([kind, key, message]);
      const covers = (a, b) => a === "thread" || a === "transcript" && b === "message";
      if (nominations.some(
        (item) => item.identity === identity2 || item.key === key && (covers(item.kind, kind) || covers(kind, item.kind))
      ))
        throw new Error("A primary reader may nominate each Thread part only once");
      nominations.push({ identity: identity2, kind, key, message, outlet, thread, options });
    };
    const finish = () => {
      accepting = false;
      if (!active || current !== generation || abort.signal.aborted) return null;
      for (const item of nominations) {
        if (!item.outlet.isConnected || !under(item.outlet, owner))
          throw new Error(
            "A primary Thread outlet must remain inside its connected owner"
          );
      }
      selected = nominations;
      shown = new Map(candidate.reading.threads.map((thread) => [thread.key, thread]));
      nativeMessages.clear();
      for (const item of nominations)
        for (const message of item.thread.msgs)
          if (item.kind === "thread" || item.kind === "transcript" || item.message === message.key)
            nativeMessages.add(message.id);
      return {
        paint: async () => {
          try {
            await paint(current);
          } catch (error) {
            failing ||= current === generation;
            throw error;
          }
          if (active && current === generation && !abort.signal.aborted) {
            candidate.commit();
            failed = false;
          }
        },
        current: () => active && current === generation && !abort.signal.aborted
      };
    };
    try {
      const rendering = render2(
        shownCollection,
        Object.freeze({
          signal: abort.signal,
          thread: (key, outlet) => nominate("thread", key, null, outlet),
          transcript: (key, outlet) => nominate("transcript", key, null, outlet),
          message: (key, id, outlet) => nominate("message", key, id, outlet),
          reply: (key, outlet, options) => nominate("reply", key, null, outlet, options),
          news: (key, outlet) => nominate("news", key, null, outlet)
        })
      );
      if (rendering?.then)
        return Promise.race([rendering, aborted(abort.signal)]).then(finish).catch((error) => {
          failing ||= !abort.signal.aborted;
          throw error;
        }).finally(() => {
          accepting = false;
        });
      return finish();
    } catch (error) {
      accepting = false;
      failing = true;
      throw error;
    }
  }
  async function paint(current) {
    if (!active || generation !== current) return;
    for (const item of selected)
      if (!owner.isConnected || !item.outlet.isConnected || !under(item.outlet, owner))
        throw new Error(
          "A primary Thread outlet must remain inside its connected owner"
        );
    const wanted = new Set(selected.map((item) => item.identity));
    const keys2 = new Set(selected.map((item) => item.key));
    for (const key of rewrites.keys()) if (!keys2.has(key)) rewrites.delete(key);
    for (const [key, view] of views)
      if (!wanted.has(key)) {
        view.dispose();
        view.node.remove();
        for (const slot of view.slots ?? []) slot.remove();
        views.delete(key);
      }
    destinations.clear();
    const children = /* @__PURE__ */ new Map();
    const place = (parent, node) => {
      const nodes = children.get(parent) ?? [];
      nodes.push(node);
      children.set(parent, nodes);
    };
    for (const item of selected) {
      let view = views.get(item.identity);
      if (!view) {
        if (item.kind === "thread")
          view = new ThreadView({ ...commands, authoredRank: 3 });
        else if (item.kind === "news") {
          const notice2 = newsNotice();
          view = { node: notice2.node, notice: notice2, dispose() {
          } };
        } else {
          const node = document.createElement("div");
          node.className = "lf-page-thread lf-ui lf-primary-part";
          node.dataset.lfPart = item.kind;
          node.tabIndex = -1;
          node.dataset.lfRuntime = "";
          node.dataset.lfGen = "1";
          node.dataset.lfOffer = "";
          if (item.kind === "transcript") {
            const transcript = new Transcript({
              commands,
              messageCommands: {
                ...commands,
                reaction: {
                  ...commands.reaction,
                  pressed: () => shown.get(item.key)?.news?.open()
                },
                edit: rewritesOf(item.key).edit
              },
              repaint: () => view.draw(),
              home: () => node
            });
            node.append(transcript.node);
            node.dataset.lfAppendTail = "";
            view = {
              node,
              transcript,
              reading: null,
              drawn: false,
              // Whether the thread's notice stands in its first message's head.
              headNotice: true,
              // Draws the transcript again at once, as a fold or a rewrite opens or
              // closes; a disclosure the draw replaced hands focus to its successor.
              draw() {
                const handedOn = transcript.present(this.reading, {
                  arrived: this.drawn,
                  notice: this.headNotice ? this.notice.node : null
                });
                transcript.commit();
                this.drawn = true;
                if (handedOn) focusDestination(handedOn, "return");
              },
              dispose: () => transcript.retire()
            };
          } else if (item.kind === "message") {
            const message = new MessageView({
              ...commands,
              reaction: {
                ...commands.reaction,
                pressed: () => shown.get(item.key)?.news?.open()
              },
              edit: rewritesOf(item.key).edit
            });
            node.append(message.node);
            view = {
              node,
              message,
              messageKey: item.message,
              reading: null,
              // Whether the thread's notice stands in this message's head.
              headNotice: true,
              // Draws the message again at once, as its rewrite opens or closes.
              draw() {
                message.present(this.reading, {
                  headerControls: this.headNotice ? this.notice.node : void 0
                });
                message.commit();
              },
              dispose: () => message.retire()
            };
          } else {
            let joined2 = false;
            const { hint, hintAside, accessibleName, busy, sent } = item.options;
            const redraw = () => {
              for (const row of node.querySelectorAll(":scope > .lf-thread-reply"))
                if (row !== reply.node) row.remove();
              move(node, reply.node, node.firstChild);
            };
            const reply = createReplyView(item.key, commands.reply, redraw, {
              onChange: () => {
                if (joined2) void update().catch(() => {
                });
              },
              editLast: rewritesOf(item.key).editLast,
              hint,
              hintAside,
              accessibleName,
              busy,
              sent
            });
            joined2 = true;
            node.append(reply.node);
            view = { node, reply, dispose: reply.dispose };
          }
          view.notice = newsNotice();
          view.notice.node.classList.add("lf-primary-news");
        }
        views.set(item.identity, view);
      }
      if (item.kind === "thread") {
        view.present(shown.get(item.key));
        view.commit();
      } else if (item.kind === "news") {
        const news = shown.get(item.key)?.news;
        if (news) view.notice.set(news);
        keepsHidden(view.node, !news);
      } else {
        keeps(view.node, "data-thread", item.thread.id);
        keeps(view.node, "data-attempt", item.thread.root.attempt ?? null);
        const news = shown.get(item.key)?.news;
        const nominated = selected.some(
          (part) => part.key === item.key && part.kind === "news"
        );
        const first = selected.find(
          (part) => part.key === item.key && (part.kind === "message" || part.kind === "transcript")
        ) ?? selected.find((part) => part.key === item.key);
        const notice2 = Boolean(news) && !nominated && first === item;
        if (notice2) view.notice.set(news);
        keepsHidden(view.notice.node, !notice2);
        if (item.kind === "transcript") {
          view.headNotice = !nominated;
          view.reading = shown.get(item.key);
          view.draw();
        } else if (item.kind === "message") {
          const message = item.thread.msgs.find((entry) => entry.key === item.message);
          view.headNotice = !nominated;
          view.reading = messageReading(message, {
            authoredRank: 3,
            reactions: message.reactions,
            workflows: message.workflows
          });
          view.draw();
          keeps(
            view.node,
            "data-lf-append-tail",
            message.provisional && message === item.thread.msgs.at(-1) ? "" : null
          );
        } else {
          keepsHidden(view.node, !replyAvailable(item.thread));
          if (nominated) view.notice.node.remove();
          else if (view.notice.node.parentNode !== view.node)
            move(view.node, view.notice.node, null);
        }
      }
      const slots = view.slots ??= [];
      let destination2 = item.outlet;
      let previous = null;
      let depth = 0;
      for (let host; host = shadowHost(destination2.getRootNode()); ) {
        let slot = slots[depth];
        if (!slot) {
          slot = document.createElement("slot");
          slot.name = "lf-thread-part-" + randomId();
          slots.push(slot);
        }
        keeps(slot, "slot", previous?.name ?? null);
        place(destination2, slot);
        previous = slot;
        destination2 = host;
        depth++;
      }
      for (const slot of slots.splice(depth)) slot.remove();
      keeps(view.node, "slot", previous?.name ?? null);
      place(destination2, view.node);
      if (item.kind === "news") continue;
      const parts = destinations.get(item.key) ?? [];
      parts.push(view);
      destinations.set(item.key, parts);
    }
    for (const [parent, nodes] of children) orderChildren(parent, nodes);
    for (const view of views.values())
      view.reply?.claim(() => view.node.isConnected && !view.node.hidden);
    const widgets = [...readApplication().document.descriptors.values()].filter(
      (descriptor) => descriptor.document.kind === "thread" && renderedUnder(elementById(descriptor.id), owner)
    ).map((descriptor) => descriptor.id);
    await whenWidgetsPresented(widgets);
  }
  const destination = (key, { message = null, part = null } = {}) => {
    const parts = destinations.get(key) ?? [];
    if (message) {
      const id = shown.get(key)?.source.msgs.find((item) => item.key === message)?.id;
      if (!id) return null;
      for (const view of parts) {
        const node = view.node.querySelector(`.lf-msg[data-event="${CSS.escape(id)}"]`);
        if (node) return node;
      }
      return null;
    }
    const first = parts[0]?.node ?? null;
    if (part === "thread") return parts.length && drawingOf(parts) || first;
    return replyOf(key) || first;
  };
  return Object.freeze({
    owner,
    update,
    release: () => held.release(),
    prepare,
    destination,
    ownsMessage: (message) => owner.isConnected && nativeMessages.has(message.id),
    ownsDestination: (node) => [...views.values()].some((view) => under(node, view.node)) || [...destinations.keys()].some((key) => replyOf(key) === node) || [...destinations.values()].some((parts) => drawingOf(parts) === node),
    cancel() {
      ++generation;
      pending?.abort();
      clear();
      held.release();
      if (failing) {
        failing = false;
        failed = true;
        onFailure();
      }
    },
    get failed() {
      return failed;
    },
    unregister() {
      active = false;
      ++generation;
      pending?.abort();
      clear();
      held.dispose();
    }
  });
}

// runtime/thread/read.js
var keyOf = (item) => `${item.message}\0${item.version}`;
var EPSILON = 1;
function mergeIntervals(intervals) {
  const ordered = intervals.sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const [start, end] of ordered) {
    const prior = merged.at(-1);
    if (prior && start <= prior[1] + EPSILON) prior[1] = Math.max(prior[1], end);
    else merged.push([start, end]);
  }
  return merged;
}
function visibleInterval(body, clips, band) {
  if (!presented(body)) return null;
  const box = body.getBoundingClientRect();
  const clipped = seenRect(body, clips);
  if (!clipped || box.width <= 0 || box.height <= 0) return null;
  const shown = intersect(clipped, band);
  if (shown.bottom <= shown.top) return null;
  if (shown.left > box.left + EPSILON || shown.right < box.right - EPSILON) return null;
  return {
    interval: [
      Math.max(0, shown.top - box.top),
      Math.min(box.height, shown.bottom - box.top)
    ],
    height: box.height,
    width: box.width,
    contentHeight: body.scrollHeight
  };
}
function wordsAreVisible(body, clips, band) {
  if (!presented(body) || !body.checkVisibility({ opacityProperty: true }))
    return false;
  const text = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
  const range = document.createRange();
  for (let node = text.nextNode(); node; node = text.nextNode()) {
    if (!node.textContent.trim()) continue;
    const holder = node.parentElement;
    if (!holder || !presented(holder) || !holder.checkVisibility({ opacityProperty: true }))
      continue;
    range.selectNodeContents(node);
    for (const box of range.getClientRects()) {
      const clipped = clippedContents(box, holder, clips);
      if (!clipped) continue;
      const room = shownWindow({ within: clipped, item: holder });
      if (hasArea(intersect(intersect(clipped, room), band))) return true;
    }
  }
  return false;
}
function createReadTracking({ markRead, openThread }) {
  let coverage = /* @__PURE__ */ new WeakMap();
  const renderedBodies = /* @__PURE__ */ new Map();
  const visibleReplies = /* @__PURE__ */ new Set();
  const refusedThisVisit = /* @__PURE__ */ new Set();
  const sizes = sizeObserver(() => scheduleScan());
  const frameWatches = [];
  const committedThreads = Z(
    /** @type {ReturnType<typeof readThreads>["threads"]} */
    []
  );
  let threadsPresented = false;
  let presentationGeneration = 0;
  let visitGeneration = 0;
  let scheduled = false;
  let passWaiters = [];
  function resetExposure() {
    visitGeneration++;
    exposureGeneration++;
    coverage = /* @__PURE__ */ new WeakMap();
    refusedThisVisit.clear();
  }
  const unreadIn = (threads) => threads.flatMap(
    (thread) => thread.unread.map((item) => ({
      thread,
      item,
      message: thread.msgs.find((message) => message.id === item.message)
    }))
  );
  const actionableUnread = () => {
    const live2 = new Set(
      unreadIn(readThreads().threads).map(({ item }) => keyOf(item))
    );
    return unreadIn(committedThreads.value).filter(({ item }) => live2.has(keyOf(item)));
  };
  function firstUnread(thread = null) {
    const target = actionableUnread().filter((each) => thread === null || each.thread.key === thread).sort((a, b) => moved(a.message).seq - moved(b.message).seq)[0];
    return target ? openThread(target.item.message, { part: "message" }) : Promise.resolve();
  }
  const firstUnreadCommand = {
    id: "thread.unread.first",
    ready: savedReadingSettled,
    keys: ["u"],
    title: "first unread",
    touch: false,
    when: () => actionableUnread().length > 0,
    run: () => void firstUnread()
  };
  function scan(sampleBand) {
    if (document.visibilityState !== "visible") return;
    const band = sampleBand ?? layoutWindow();
    if (!band || sampleBand?.visible === false) return;
    const candidates = new Map(
      (threadsPresented ? actionableUnread() : []).map(({ item }) => [
        item.message,
        item
      ])
    );
    const mayRead = threadsPresented && document.hasFocus() && sessionIsActive();
    const clips = /* @__PURE__ */ new Map();
    const completed = /* @__PURE__ */ new Map();
    const unseenWords = [];
    for (const [node, rendered] of renderedBodies) {
      const { body, id, version, feedback } = rendered;
      if (!node.isConnected || !body.isConnected) {
        sizes.unobserve(body);
        renderedBodies.delete(node);
        continue;
      }
      if (feedback) {
        const identity2 = feedback.reply_id ?? `input:${feedback.input_id}`;
        const key2 = `${identity2}:${feedback.presentation_kind}:${feedback.surface}`;
        if (!visibleReplies.has(key2)) {
          if (wordsAreVisible(body, clips, band)) {
            visibleReplies.add(key2);
            recordInteraction("reply_visible", feedback);
          } else unseenWords.push(body);
        }
      }
      const item = mayRead && candidates.get(id);
      const key = item && keyOf(item);
      if (!item || item.version !== version || completed.has(key) || refusedThisVisit.has(key))
        continue;
      const visible = visibleInterval(body, clips, band);
      if (!visible) continue;
      let tracked = coverage.get(body);
      if (!tracked || tracked.key !== key || tracked.width !== visible.width || tracked.height !== visible.height || tracked.contentHeight !== visible.contentHeight) {
        tracked = {
          key,
          width: visible.width,
          height: visible.height,
          contentHeight: visible.contentHeight,
          intervals: []
        };
        coverage.set(body, tracked);
      }
      tracked.intervals = mergeIntervals([...tracked.intervals, visible.interval]);
      if (tracked.intervals.length === 1 && tracked.intervals[0][0] <= EPSILON && tracked.intervals[0][1] >= visible.height - EPSILON) {
        completed.set(key, item);
      }
    }
    if (unseenWords.length) passAfterFades(unseenWords);
    if (completed.size) {
      const items = [...completed.values()];
      const visit = visitGeneration;
      void markRead(items).then((outcome) => {
        if (outcome === "refused" && visit === visitGeneration)
          for (const item of items) refusedThisVisit.add(keyOf(item));
      });
    }
    if (!threadsPresented) return;
    const waiting = passWaiters;
    passWaiters = [];
    for (const then of waiting) then();
  }
  const awaitedRuns = /* @__PURE__ */ new WeakSet();
  function passAfterFades(bodies) {
    for (const body of bodies) {
      const animations = body.getAnimations({ subtree: true });
      for (let at = renderedParent(body); at; at = renderedParent(at))
        animations.push(...at.getAnimations());
      for (const { finished } of animations) {
        if (awaitedRuns.has(finished)) continue;
        awaitedRuns.add(finished);
        finished.then(scheduleScan, scheduleScan);
      }
    }
  }
  function afterPass(then) {
    passWaiters.push(then);
    scheduleScan();
  }
  let exposureGeneration = 0;
  function scheduleScan() {
    exposureGeneration++;
    if (scheduled) return;
    scheduled = true;
    nextRender(() => {
      scheduled = false;
      const asked = readSampleVisibility();
      if (!asked) {
        if (frameVisibility()?.visible !== false) scan();
        return;
      }
      const generation = exposureGeneration;
      void asked.then((reading) => {
        if (generation === exposureGeneration) scan(reading);
      }, reportError);
    });
  }
  function mount() {
    frameWatches.push(watchRoom(scheduleScan));
    addEventListener("focus", scheduleScan);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState !== "visible") resetExposure();
      else scheduleScan();
    });
    addEventListener("blur", resetExposure);
    addEventListener("load", scheduleScan, true);
    document.addEventListener("lf-session-active", scheduleScan);
    frameWatches.push(
      onFrameVisibility((visibility) => {
        if (visibility.visible) scheduleScan();
        else resetExposure();
      })
    );
    addEventListener("pagehide", (event) => {
      exposureGeneration++;
      if (event.persisted) return;
      sizes.disconnect();
      for (const unwatch of frameWatches) unwatch();
      frameWatches.length = 0;
    });
  }
  function observeBody(body, reading) {
    if (!(body instanceof Element))
      throw new TypeError("A message body must be an Element");
    if (!renderedBodies.has(body)) sizes.observe(body);
    const registration = {
      body,
      ...reading
    };
    renderedBodies.set(body, registration);
    scheduleScan();
    return () => {
      if (renderedBodies.get(body) !== registration) return;
      sizes.unobserve(body);
      renderedBodies.delete(body);
    };
  }
  function observeMessage(body, message) {
    return observeBody(body, {
      id: message.id,
      version: message.version,
      feedback: message.author === "agent" ? {
        reply_id: message.id,
        attempt: message.attempt,
        presentation_kind: "message_words",
        reply_kind: message.provisional ? "stream" : message.progress ? "progress" : message.failure ? "failure" : "answer",
        surface: "margin"
      } : null
    });
  }
  function observeFeedback(body, feedback) {
    return observeBody(body, { id: null, version: null, feedback });
  }
  function present() {
    const generation = presentationGeneration;
    const threads = readThreads().threads;
    void whenDocumentPresented().then(() => {
      if (generation !== presentationGeneration) return;
      committedThreads.value = threads;
      threadsPresented = true;
      const unread = unreadIn(threads);
      const current = new Set(unread.map(({ item }) => keyOf(item)));
      for (const key of refusedThisVisit)
        if (!current.has(key)) refusedThisVisit.delete(key);
      scheduleScan();
    }).catch(() => {
      if (generation === presentationGeneration) coverage = /* @__PURE__ */ new WeakMap();
    });
  }
  function begin() {
    presentationGeneration++;
    exposureGeneration++;
    threadsPresented = false;
  }
  function abort() {
    presentationGeneration++;
    threadsPresented = false;
    resetExposure();
  }
  return {
    mount,
    begin,
    abort,
    present,
    observeMessage,
    observeFeedback,
    firstUnread,
    afterPass,
    firstUnreadCommand
  };
}

// runtime/thread/box.js
var threadBox = (el2, hint, { createComment, onDraftChanged, wireInput: wireInput2 }) => {
  if (inChrome(el2) || quoted(el2)) return null;
  const declaration = registry[el2.localName]?.["x-thread-seat"];
  if (!declaration || !matchesWhen(el2, declaration.when))
    throw new TypeError(
      `<${el2.localName}> placed a thread outside its x-thread-seat predicate`
    );
  const box = offer("div", "lf-thread-seat");
  box.dataset.lfRuntime = "";
  box.dataset.lfThreadSeat = el2.id;
  const row = offer("div", "lf-say lf-comment-box");
  const ta = offer(TEXT_FIELD);
  ta.name = "comment";
  const send = offer("button", "lf-btn", "Send");
  const hold = declaration.hold ? offer("button", "lf-btn", declaration.hold) : null;
  const ctx = "say:" + el2.id;
  ta.value = loadDraft(ctx) ?? "";
  ta.setAttribute("aria-label", hint);
  row.append(ta, send, ...hold ? [hold] : []);
  const sendComment = (text, owns, holds = false) => {
    const land = sendLanding(ta);
    const sent = sendMessage(
      ctx,
      owns,
      (attempt) => createComment({
        anchor: { section: el2.id },
        text,
        attempt,
        ...holds && { holds: el2.id }
      })
    );
    if (sent) land();
    return sent;
  };
  const sync = wireInput2(ta, {
    hint,
    sends: "send",
    sendBtn: send,
    altBtn: hold,
    save: (value) => saveDraft(ctx, value),
    // The message stands in the seat's own thread the moment it is sent, and that
    // is the acknowledgement; a notice saying the same thing would be a second one. A
    // user with no view of the seat hears the send from the live region, which `post`
    // writes for every message. The hold says what its press did beyond sending — and
    // names the send too, because it is the later write to that one region and would
    // otherwise be all the user heard.
    send: (_text, raw, owns) => {
      sendComment(raw, owns);
    },
    altSend: hold ? (_text, raw, owns) => {
      if (sendComment(raw, owns, true)) notice("Message sent \u2014 goal paused");
    } : null
  });
  sync();
  box.lfFirstMessage = row;
  whileConnected(
    box,
    () => watchDraft(
      ctx,
      (value) => {
        sync.load(value ?? "");
        onDraftChanged();
      },
      {
        input: ta,
        resume: () => ({ where: el2, input: () => ta })
      }
    )
  );
  mountFirstMessage(box, row);
  return box;
};

// runtime/semantic-news.js
var identity = (record) => record.attempt ?? record.id;
function semanticNewsReading(root) {
  const view = root.effective.view;
  if (!view) throw new Error("The shown page has no browser reading");
  const state = root.authoritative;
  return {
    obligations: view.obligations,
    thread: view.thread,
    workflows: state.workflows,
    activity: state.activity
  };
}
function unreadContent(threadView) {
  return threadView.threads.flatMap(
    (thread) => thread.unread.map(({ message: id, version }) => ({
      thread: thread.id,
      message: thread.msgs.find((message) => message.id === id),
      version
    }))
  ).filter(({ message }) => !message.failure).sort((a, b) => moved(a.message).seq - moved(b.message).seq);
}
function userObligations(items) {
  const held = /* @__PURE__ */ new Map();
  for (const item of items) {
    if (item.next_actor !== "user" || item.source.kind === "update") continue;
    const key = item.thread === null ? ["page", item.id] : ["thread", item.thread, item.id];
    held.set(JSON.stringify(key), { source: item.id, thread: item.thread });
  }
  return held;
}
function responseFailures(workflows) {
  const failures = /* @__PURE__ */ new Map();
  for (const workflow of workflows) {
    if (workflow.condition?.operation !== "response" || !["failed", "interrupted"].includes(workflow.condition.kind))
      continue;
    const source = workflow.response;
    if (!source?.attempt && !source?.id) continue;
    const key = identity(source);
    const failure = {
      key,
      kind: workflow.condition.kind,
      input: workflow.input,
      thread: workflow.thread,
      seq: workflow.seq
    };
    failures.set(key, failure);
  }
  return failures;
}
var agentAvailable = (activity) => activity.held && ["listening", "working"].includes(activity.kind);
function observeSemanticNews(prior, reading) {
  const content = unreadContent(reading.thread);
  const obligations = userObligations(reading.obligations);
  const failures = responseFailures(reading.workflows);
  const available = agentAvailable(reading.activity);
  const first = prior === null;
  const observed = {
    content: new Set(prior?.content),
    failures: new Set(prior?.failures),
    obligations: new Set(obligations.keys()),
    obligationEpisodes: new Map(prior?.obligationEpisodes),
    available,
    availabilityEpisode: prior?.availabilityEpisode ?? 0
  };
  const news = [];
  for (const { thread, message, version } of content) {
    if (!observed.content.has(version))
      news.push({
        kind: "agent_content",
        key: `content:${version}`,
        thread,
        message,
        version
      });
    observed.content.add(version);
  }
  for (const failure of failures.values()) {
    if (!first && !observed.failures.has(failure.key))
      news.push({
        ...failure,
        condition: failure.kind,
        kind: "response_failure",
        key: `response:${failure.key}`
      });
    observed.failures.add(failure.key);
  }
  for (const [key, obligation] of obligations) {
    if (prior?.obligations.has(key)) continue;
    const episode = (observed.obligationEpisodes.get(key) ?? 0) + 1;
    observed.obligationEpisodes.set(key, episode);
    if (!first)
      news.push({
        kind: "user_obligation",
        key: `obligation:${key}:${episode}`,
        sourceKey: key,
        episode,
        ...obligation
      });
  }
  if (available && !prior?.available) {
    observed.availabilityEpisode += 1;
    if (!first)
      news.push({
        kind: "agent_available",
        key: `agent-available:${observed.availabilityEpisode}`
      });
  }
  return { observed, news };
}
function currentSemanticNews(news, reading, observed) {
  const versions = new Set(unreadContent(reading.thread).map(({ version }) => version));
  const obligations = userObligations(reading.obligations);
  const failures = responseFailures(reading.workflows);
  return news.flatMap((item) => {
    switch (item.kind) {
      case "agent_content":
        return versions.has(item.version) ? [item] : [];
      case "response_failure": {
        const current = failures.get(item.key.slice("response:".length));
        return current ? [{ ...item, condition: current.kind }] : [];
      }
      case "user_obligation":
        return obligations.has(item.sourceKey) && item.episode === observed.obligationEpisodes.get(item.sourceKey) ? [item] : [];
      case "agent_available":
        return agentAvailable(reading.activity) && item.key === `agent-available:${observed.availabilityEpisode}` ? [item] : [];
      default:
        throw new Error(`Unknown semantic news kind ${item.kind}`);
    }
  });
}
function combineSemanticNews(older, newer) {
  return [...new Map([...older, ...newer].map((item) => [item.key, item])).values()];
}
var plural = (count, singular, pluralForm = `${singular}s`) => `${count} ${count === 1 ? singular : pluralForm}`;
function semanticNewsNotice(news) {
  if (!news.length) return "";
  const byKind = (kind) => news.filter((item) => item.kind === kind);
  const content = byKind("agent_content");
  const failures = byKind("response_failure");
  const obligations = byKind("user_obligation");
  const availability = byKind("agent_available");
  const clauses = [];
  if (content.length === 1) {
    const { message } = content[0];
    const { agent } = message;
    const verb = message.kind === "reply" ? "reply" : "comment";
    clauses.push(
      message.edited ? `${agent} edited a ${verb}` : `${agent} ${verb === "reply" ? "replied" : "commented"}`
    );
  } else if (content.length) {
    const replies = content.filter(({ message }) => message.kind === "reply");
    const threads = new Set(content.map((item) => item.thread)).size;
    clauses.push(
      replies.length === content.length ? `${plural(content.length, "reply", "replies")} in ${plural(threads, "thread")}` : `${plural(content.length, "agent message")} in ${plural(threads, "thread")}`
    );
  }
  for (const condition of ["failed", "interrupted"]) {
    const count = failures.filter((item) => item.condition === condition).length;
    if (count)
      clauses.push(
        count === 1 ? `Response ${condition}` : `${plural(count, "response")} ${condition}`
      );
  }
  if (obligations.length)
    clauses.push(
      obligations.length === 1 ? "Input needed" : `${obligations.length} waiting on me`
    );
  if (availability.length) clauses.push(`${agentLabel()} active on this page`);
  return clauses.join("; ");
}

// runtime/state-application.js
function createStateApplication({
  prepareActivation,
  acceptData: acceptData2,
  notifyDataSubscribers: notifyDataSubscribers2,
  accountPending
}) {
  let observedSemanticNews = null;
  let presentedNewsReading = null;
  const markupRead = /* @__PURE__ */ new Set();
  let stateApplying = false;
  let admission = Promise.resolve();
  async function runSerialized(operation) {
    const prior = admission;
    const { promise, resolve: release } = Promise.withResolvers();
    admission = promise;
    await prior;
    try {
      return await operation();
    } finally {
      release();
    }
  }
  async function receiveState(state) {
    if (!sameLayer(state.layer.generation)) return;
    const dataChanged = acceptData2(state.data, state.taken);
    const notifyChangedData = () => dataChanged ? notifyDataSubscribers2() : void 0;
    if (applicationState.overtaken(state)) {
      await notifyChangedData();
      return;
    }
    const threads = state.browser.views[state.active.revision].thread.threads;
    const frozenDocuments = [];
    const preparations = [
      prepareActivation(state),
      threads.length ? loadMessageMarkdown() : null
    ];
    for (const thread of threads)
      for (const message of thread.msgs) {
        if (!message.markup) continue;
        const authored2 = prepareAuthoredMessage(message, thread.id);
        frozenDocuments.push(authored2);
        if (markupRead.has(message.id)) continue;
        preparations.push(
          importWidgets(authored2.root).then(() => markupRead.add(message.id))
        );
      }
    const [activation] = await Promise.all(preparations);
    const bodies = new Map(
      threads.flatMap(
        (thread) => thread.msgs.map((message) => {
          const authored2 = message.markup ? prepareAuthoredMessage(message, thread.id).body : null;
          return [
            message.id,
            {
              ...authored2 ?? {},
              text: [messageText(message), authored2?.text].filter(Boolean).join("\n")
            }
          ];
        })
      )
    );
    return runSerialized(async () => {
      const following = activation?.activates() ? activation.revision : null;
      if (!applicationState.canAdopt(state, following)) {
        await notifyChangedData();
        return;
      }
      const installed = following !== null ? await activation.install() : null;
      const prior = installed?.document ?? readApplication().document;
      let authored2 = prior.authored;
      let descriptors = prior.descriptors;
      for (const frozen of frozenDocuments) {
        for (const [id, baseline] of frozen.authored) {
          if (authored2.has(id)) continue;
          if (authored2 === prior.authored) authored2 = new Map(authored2);
          authored2.set(id, baseline);
        }
        for (const [id, descriptor] of frozen.descriptors.descriptors) {
          if (descriptors.has(id)) continue;
          if (descriptors === prior.descriptors) descriptors = new Map(descriptors);
          descriptors.set(id, descriptor);
        }
      }
      const documentCapture = {
        ...prior,
        authored: authored2,
        descriptors,
        messageBodies: bodies
      };
      for (const frozen of frozenDocuments) commitWidgetDescriptors(frozen.descriptors);
      if (!applicationState.adopt(state, documentCapture)) {
        await notifyChangedData();
        return;
      }
      observeServerNow(state.now);
      observeWorkingGrace(state.working_grace_ms);
      stateApplying = true;
      try {
        settleAcceptedDrafts();
        if (installed) await settlePageInterface();
        await whenDocumentPresented();
        if (installed) await installed.land();
        await notifyDataSubscribers2();
        markStateApplied(state);
        accountPending(state.browser.receipts);
        presentedNewsReading = semanticNewsReading(readApplication());
        const reading = observeSemanticNews(observedSemanticNews, presentedNewsReading);
        observedSemanticNews = reading.observed;
        if (reading.news.length) {
          const format = (value) => semanticNewsNotice(
            currentSemanticNews(value, presentedNewsReading, observedSemanticNews)
          );
          notice(format(reading.news), {
            background: true,
            group: {
              key: "semantic-news",
              value: reading.news,
              combine: combineSemanticNews,
              format
            }
          });
        }
      } catch (error) {
        reportCarried(error, `State presentation failed`);
        throw error;
      } finally {
        stateApplying = false;
      }
    });
  }
  return { isApplying: () => stateApplying, receiveState, runSerialized };
}

// runtime/application.js
var commandDispatch = createCommandDispatch();
var application = null;
var app = () => {
  if (!application) throw new Error("Leaf application has not been mounted");
  return application;
};
function mountApplication(dependencies) {
  if (application) throw new Error("Leaf application mounted twice");
  setPresentationFailureReporter(reportCarried);
  const { ledger } = commandDispatch;
  watchPendingTraffic(applicationState.select((root) => root.effective.sending));
  const hasPending = () => ledger.snapshot().length > 0;
  const engagement = dependencies.createEngagement({
    hasPending,
    fabAnchorAt: dependencies.activeActionAnchor,
    targetPickerOpen: dependencies.targetPickerOpen
  });
  let threadPresenter;
  let stateApplication;
  let queuedInvalidation = false;
  const stateApplying = () => stateApplication?.isApplying() ?? false;
  const openPageThread = (...args) => threadDestinations.openPageThread(...args);
  const releasePending = async () => {
    const candidates = ledger.releasable();
    if (!candidates.length) return false;
    const attempts = new Set(candidates.map((entry) => entry.event.attempt));
    const stillCurrent = () => ledger.releasable().some((entry) => attempts.has(entry.event.attempt));
    await Promise.all([
      whenWidgetsPresented([
        ...new Set(
          candidates.filter((entry) => entry.event.kind === "action").map((entry) => entry.event.widget)
        )
      ]),
      whenApplicationRegionsPresented(
        ["projection:chrome", "thread", "obligations"],
        stillCurrent
      )
    ]);
    const released = ledger.releasable().filter((entry) => attempts.has(entry.event.attempt));
    if (!released.length) return false;
    ledger.release(released);
    return true;
  };
  const releasePendingSafely = (context) => {
    void releasePending().catch((error) => reportCarried(error, context));
  };
  const invalidateDom2 = () => {
    if (stateApplying()) {
      queuedInvalidation = true;
      return Promise.resolve();
    }
    return presentDocument();
  };
  createProjectionPresentation();
  const dataProjection = createDataProjection({ invalidateDom: invalidateDom2 });
  let delivery;
  const presentThread = () => threadPresenter.present();
  const refreshThread = () => presentThread().catch(() => void 0);
  function afterEnqueue(entry) {
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
    // A widget's gesture is acknowledged by the name the widget gave it, the name its
    // undo is announced by too.
    named: (entry, says) => {
      undo.retainGesture(entry.event.attempt, { says });
      void entry.answer.then((admitted) => {
        if (admitted) notice(`${says} \u2014 sent`);
      });
    },
    withdraw: (candidate) => undo.withdraw(candidate),
    onCollision: (attempt) => raiseError(`Couldn't send \u2014 attempt ${attempt} is already in use`)
  });
  const { post: post2 } = commandDispatch;
  const undo = createUndo({
    post: post2,
    stateApplying,
    unaccountedGesture: engagement.unaccountedGesture,
    openThread: openPageThread,
    threadPlace: (id) => dependencies.anchorTravel.threadDestination(id)
  });
  const markRead = async (messages) => {
    applicationState.markRead(messages);
    try {
      return await deliverBookkeeping({ kind: "read", messages }, receiveState);
    } finally {
      applicationState.settleMarkRead(messages);
    }
  };
  const read2 = createReadTracking({
    markRead,
    openThread: openPageThread
  });
  const threadActions2 = createThreadActions({
    post: post2,
    withdraw: undo.withdraw,
    sendReaction: dependencies.sendReaction,
    currentRevision: () => runtime.currentRevision,
    open: openPageThread
  });
  const queueActions2 = createQueueActions({
    post: post2,
    arrive: (item) => dependencies.arriveAtQueueItem(item)
  });
  const replyView = {
    actions: threadActions2,
    wireInput: dependencies.wireInput,
    landSent: dependencies.landSent,
    landInThread: dependencies.landInThread,
    changed: refreshThread
  };
  const settlementView = {
    pendingEntries: ledger.snapshot,
    actions: threadActions2,
    retainGesture: undo.retainGesture
  };
  const reactionView = {
    registerSurface: dependencies.registerReactSurface,
    actions: threadActions2
  };
  const inlineView = {
    reply: replyView,
    settlement: settlementView,
    reaction: reactionView,
    read: read2,
    openThread: openPageThread,
    landInThread: dependencies.landInThread
  };
  const surfaceView = {
    ...inlineView,
    composition: dependencies.compositionSurface
  };
  const annotations = createAnnotationInventory({
    readObligations,
    placedAt: dependencies.anchorPlacement.placedAt,
    openThread: openPageThread,
    goToObligation: dependencies.annotationCommands.goToObligation,
    scrollToElement: dependencies.anchorTravel.scrollToElement
  });
  const inlineContributions = createInlineContributions(annotations);
  const onPaper = matchMedia("print");
  function refreshAnnotationInventory() {
    if (onPaper.matches) return annotations.read();
    presentingContributions();
    inlineContributions.present();
    const entries = annotations.collect();
    dependencies.annotationCommands.renderPageMapDialog(entries);
    return entries;
  }
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
  const annotationInputs = readPart(annotationSelection);
  const mountAnnotations = () => {
    const presentation = applicationPresenter({
      region: "annotations",
      after: PRESENTATION_DOM.obligations,
      reading: () => annotationInputs(),
      paint: renderAnnotations
    });
    void presentation.present();
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
    renderMarginThread: (host, thread, controls) => renderMarginThread(host, thread, inlineView, controls),
    placedAt: dependencies.anchorPlacement.placedAt,
    marksFor: (id) => dependencies.anchorPaint?.marksFor(id) ?? [],
    scrollToElement: dependencies.anchorTravel.scrollToElement
  });
  const threadDestinations = createThreadDestinations({
    threadIdsAt: annotations.threadIdsAt,
    placedAt: dependencies.anchorPlacement.placedAt,
    scrollToThread: dependencies.anchorTravel.scrollToThread,
    arrive: dependencies.anchorTravel.arrive,
    prepareTrip: dependencies.anchorTravel.prepareTrip,
    preview: overlay?.threadPreview
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
    // stopped drawing: the surface drawing it, its margin card, or the floating panel.
    openThread: (id, options) => threadDestinations.openPageThread(id, { ...options, travel: false }),
    // A native Tab visit outside a displaced row retains editing without taking focus.
    continueThread: (id, intent) => threadDestinations.openPageThread(id, {
      part: "reply",
      focus: false,
      travel: false,
      flash: false,
      intent
    }),
    // The thread a margin entry stands for, which a user on it goes on with when the
    // thread leaves the margin.
    threadAt: (node) => overlay?.entryThread(node) ?? null,
    read: read2
  });
  const accountPending = (receipts) => {
    ledger.present(receipts);
    releasePendingSafely("receipt presentation");
  };
  stateApplication = createStateApplication({
    prepareActivation: dependencies.state.prepareActivation,
    acceptData: dependencies.state.acceptData,
    notifyDataSubscribers: dependencies.state.notifyDataSubscribers,
    accountPending
  });
  const flushQueuedInvalidation = () => {
    if (!queuedInvalidation || stateApplying()) return Promise.resolve();
    queuedInvalidation = false;
    return invalidateDom2();
  };
  const receiveState = (state) => stateApplication.receiveState(state).finally(() => flushQueuedInvalidation().catch(() => void 0));
  delivery = createDelivery({
    ledger,
    applyAcceptedState: receiveState,
    refusedWords: keepRefusedWords,
    settleRejected: async (entry, state) => {
      if (state)
        await receiveState(state).catch(
          (error) => reportCarried(error, "state in refused event response")
        );
      let dependents = [];
      await stateApplication.runSerialized(async () => {
        dependents = ledger.refuse(entry);
        const prepared = invalidateDom2();
        releasePendingSafely("rejected event presentation");
        await prepared;
      });
      return dependents;
    },
    settlementChanged: (entry, accepted) => {
      if (accepted) {
        releasePendingSafely("accepted event reconciliation");
        if (!applicationState.entry(entry.event.attempt)) invalidateDom2();
      }
    }
  });
  const feed = createStateFeed({
    prepareActivation: dependencies.state.prepareActivation,
    stateApplying,
    invalidateDom: invalidateDom2,
    receiveState
  });
  const threadBox3 = (owner, hint) => threadBox(owner, hint, {
    createComment: (command) => threadActions2.create(command)?.delivery ?? null,
    onDraftChanged: invalidateDom2,
    wireInput: dependencies.wireInput
  });
  const threadSurfaceCommands = {
    invalidate: invalidateDom2,
    composition: dependencies.compositionSurface,
    reveal: openPageThread
  };
  const requirePageAnnotations = () => {
    if (annotationMode !== "page")
      throw new Error("Page annotation presentation requires data-annotations=page");
  };
  let annotationRegistration = null;
  const consumeAnnotations2 = (owner, render2) => {
    requirePageAnnotations();
    if (annotationRegistration)
      throw new Error("The document already has a page annotation view");
    const registration = /* @__PURE__ */ Symbol("page annotation view");
    annotationRegistration = registration;
    const retire = () => {
      if (annotationRegistration === registration) annotationRegistration = null;
    };
    try {
      return createAnnotationView(owner, render2, annotations, invalidateDom2, retire);
    } catch (error) {
      retire();
      throw error;
    }
  };
  const watchThreadSurfaces2 = () => watchThreadSurfaces(threadSurfaceCommands);
  const placePageThreads3 = (owner, render2) => {
    requirePageAnnotations();
    return placePageThreads(owner, render2, threadSurfaceCommands);
  };
  const attachPresentation = (owner, { render: render2, reveal: reveal3, answersAtOnce = false }, onFailure = void 0) => {
    const reader = createPrimaryReader(
      owner,
      render2,
      inlineView,
      () => threadPresenter.present(),
      { answersAtOnce, onFailure }
    );
    const detachDestination = threadDestinations.register(owner, reveal3, reader);
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
      }
    };
  };
  let yielding = null;
  let authored2 = null;
  const restoreYielding = () => {
    if (yielding && !yielding.attached)
      yielding.attached = attachPresentation(yielding.owner, yielding.spec);
  };
  const takePlace = (entry) => {
    const displaced = yielding?.attached;
    const handOff = displaced ? yielding.spec.yielded() : null;
    if (displaced) {
      displaced.detach();
      yielding.attached = null;
    }
    try {
      entry.attached = attachPresentation(
        entry.owner,
        entry.spec,
        () => nextRender(() => fallBack(entry))
      );
    } catch (error) {
      if (displaced) restoreYielding();
      throw error;
    }
    authored2 = entry;
    if (handOff)
      queueMicrotask(() => {
        if (authored2 === entry) handOff();
      });
  };
  const fallBack = (entry) => {
    if (authored2 !== entry || !entry.attached?.reader.failed) return;
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
      if (!authored2) entry.attached = attachPresentation(owner, spec);
    } else takePlace(entry);
    let active = true;
    return Object.freeze({
      get primary() {
        return Boolean(entry.attached);
      },
      update: ({ release = false } = {}) => {
        if (active && authored2 === entry && !entry.attached) takePlace(entry);
        if (release) entry.attached?.reader.release();
        return threadPresenter.present();
      },
      unregister() {
        if (!active) return;
        active = false;
        entry.attached?.detach();
        entry.attached = null;
        if (yielding === entry) yielding = null;
        if (authored2 === entry) {
          authored2 = null;
          restoreYielding();
        }
      }
    });
  };
  application = {
    withdraw: undo.withdraw,
    midComposition: engagement.midComposition,
    threadBox: threadBox3,
    hasPending,
    invalidateDom: invalidateDom2,
    landInThread: dependencies.landInThread,
    annotations,
    renderAnnotations,
    mountAnnotations,
    overlay,
    threadDestinations,
    read: read2,
    mountRead: read2.mount,
    registerThreadPresentation: (owner, spec) => presentThreads(owner, spec, false),
    registerChromeThreadPresentation: (owner, spec) => presentThreads(owner, spec, true),
    navigateToDatum: dependencies.anchorTravel.navigateToDatum,
    post: post2,
    projectData: dataProjection.projectData,
    readAndApply: feed.readAndApply,
    refreshThread,
    presentThread,
    watchThreadSurfaces: watchThreadSurfaces2,
    placePageThreads: placePageThreads3,
    consumeAnnotations: consumeAnnotations2,
    threadActions: threadActions2,
    queueActions: queueActions2,
    settlement: settlementView,
    openObligation(id) {
      const item = readObligations().all.find((item2) => item2.id === id);
      if (!item) return Promise.resolve(false);
      if (item.source.kind === "update" || item.source.kind === "todo")
        return queueActions2.open(JSON.stringify([item.source.kind, item.id]));
      if (item.thread !== null && answeredInWords(item)) {
        showHeld(item.thread);
        return threadDestinations.openPageThread(item.message, {
          part: "message"
        });
      }
      return dependencies.annotationCommands.goToObligation(
        item,
        readObligations().all
      );
    },
    // The On me walk within one region (queue-walk.js), the walk an `lf-tally` steps.
    nextObligation: (options) => dependencies.nextObligationWithin(options),
    startFeed: feed.startFeed,
    wireInput: dependencies.wireInput
  };
  return application;
}
var threadBox2 = (...args) => app().threadBox(...args);
var dispatchWidget = commandDispatch.dispatchWidget;
var invalidateDom = (...args) => app().invalidateDom(...args);
var landInThread = (...args) => app().landInThread(...args);
var navigateToDatum = (...args) => app().navigateToDatum(...args);
var post = commandDispatch.post;
var projectData = (...args) => app().projectData(...args);
var placePageThreads2 = (...args) => app().placePageThreads(...args);
var consumeAnnotations = (...args) => app().consumeAnnotations(...args);
var registerThreadPresentation = (...args) => app().registerThreadPresentation(...args);
var threadActions = Object.freeze({
  open: (...args) => app().threadActions.open(...args),
  create: (...args) => app().threadActions.create(...args),
  reply: (...args) => app().threadActions.reply(...args),
  resolve: (...args) => app().threadActions.resolve(...args),
  reopen: (...args) => app().threadActions.reopen(...args),
  setReaction: (...args) => app().threadActions.setReaction(...args)
});
var obligationActions = Object.freeze({
  open: (...args) => app().openObligation(...args),
  next: (...args) => app().nextObligation(...args)
});
var queueActions = Object.freeze({
  open: (...args) => app().queueActions.open(...args),
  done: (...args) => app().queueActions.done(...args)
});
var wireInput = (...args) => app().wireInput(...args);

// runtime/thread/landing.js
var threadReturns = /* @__PURE__ */ new WeakMap();
function threadInput(node) {
  const held = node && closestAcross(node, SAYS_IN);
  return threadReplyInput(held);
}
var heldThreadOrSeat = () => focused() && closestAcross(focused(), SAYS_IN);
var standingThread = () => {
  const held = heldThreadOrSeat();
  const box = threadReplyInput(held);
  return box ? { held: wholeThread(held), box } : null;
};
var backFromThread = (box) => threadReturns.get(box) ?? null;
function backFromBox() {
  const held = heldThreadOrSeat();
  if (held?.matches(THREAD))
    return { target: wholeThread(held), line: "back to thread" };
  const route = backFromThread(focused());
  return route?.target?.isConnected ? route : null;
}
var boxHandsBack = () => Boolean(backFromBox());
var inBox = () => takesLetters(focused()) || replyDraftContext(focused()) !== null;
var leavesBox = () => inBox() && boxHandsBack();
pageScope("text entry", {
  title: "In a text box",
  root: focused,
  at: inBox,
  claims: (binding) => takesLetters(focused()) && TEXT_ENTRY(binding),
  rows: [
    {
      id: "text.leave",
      touch: false,
      keys: ["Escape"],
      description: "Keeps what is typed",
      title: () => backFromBox()?.line ?? "back",
      // The thread the box belongs to. A page text box that is not in one leaves the
      // row dead and the page's rung in place, which is the honest answer: nothing
      // there to go back to.
      when: leavesBox,
      run: () => {
        const back = backFromBox();
        dismissReplyAt(focused());
        deepFocus()?.blur();
        const target = back?.target;
        if (!target) return;
        if (!target.matches?.(THREAD)) {
          focusDestination(target, "return");
          scrollIntoView(target, { block: "nearest" });
          return;
        }
        standOnThread(target);
      }
    }
  ]
});
function standOnThread(thread) {
  const shown = alreadyShown(thread);
  if (!fitsWhole(thread) && shown) {
    focusThread(thread, "return");
    return;
  }
  focusThread(thread, "move");
  if (!shown) scrollIntoView(thread, { block: "nearest" });
}
var cardThread = () => focusedThreadTarget();
var resolutionControl = (thread) => thread ? threadPart(thread, "settlement") : null;
function prepareLanding({ held = null, box, route = null }) {
  if (!box) return false;
  held ??= closestAcross(box, SAYS_IN);
  if (route && held && !held.hasAttribute("tabindex")) {
    threadReturns.set(box, route);
    whenLeft(box, () => threadReturns.delete(box));
  }
  return { held, box };
}
function createThreadLanding() {
  const landIn = (destination) => {
    const prepared = prepareLanding(destination);
    if (!prepared) return false;
    const { box } = prepared;
    bringBackSurfaceOf(box);
    focusDestination(box, "move");
    if (!alreadyShown(box))
      scrollIntoView(box, {
        block: "nearest",
        behavior: "instant"
      });
    return true;
  };
  const landInThread2 = (box, route = null) => landIn({ box, route });
  const landSent = standOnThread;
  return { landIn, landInThread: landInThread2, landSent };
}
function declareThreadKeys(landIn, threadHere) {
  pageScope("thread", {
    title: "In a thread",
    root: focused,
    when: () => threadList().length > 0,
    at: () => Boolean(threadHere()),
    rows: [
      {
        id: "thread.primary",
        touch: false,
        keys: ["Enter"],
        title: () => resolutionControl(cardThread())?.matches(".lf-reopen") ? "reopen" : "reply",
        when: () => Boolean(threadInput(cardThread())) || resolutionControl(cardThread())?.matches(
          '.lf-reopen:not(:disabled, [aria-disabled="true"])'
        ),
        // Find the thread's own compose row rather than the first text box: a message may
        // contain a widget with an editor of its own before the reply box in DOM order.
        run: () => {
          const thread = cardThread();
          const reopen = resolutionControl(thread)?.matches(".lf-reopen") ? resolutionControl(thread) : null;
          if (reopen) reopen.click();
          else landIn({ held: thread, box: threadInput(thread) });
        }
      },
      {
        id: "thread.resolution.toggle",
        touch: false,
        keys: ["r"],
        title: () => resolutionControl(threadHere())?.matches(".lf-reopen") ? "reopen" : "resolve",
        when: () => resolutionControl(threadHere())?.matches(
          ':not(:disabled, [aria-disabled="true"])'
        ),
        run: () => resolutionControl(threadHere()).click()
      }
    ]
  });
}

// runtime/widget-controller.js
var controllers = /* @__PURE__ */ new WeakMap();
var ancestorRefreshes = /* @__PURE__ */ new Set();
var ancestorRefreshQueued = false;
var selfDrawn = /* @__PURE__ */ new WeakMap();
var drawsItself = (owner, drawing) => selfDrawn.set(owner, drawing);
function widgetMounted(owner, descriptor, parentChanged) {
  if (parentChanged && applicationState.read().document.authored.has(descriptor.id))
    refreshAncestors(owner);
  invalidateDom();
}
function refreshAncestors(owner) {
  for (let ancestor = owner.parentElement; ancestor; ancestor = ancestor.parentElement) {
    const drawing = selfDrawn.get(ancestor);
    if (drawing) ancestorRefreshes.add(drawing);
  }
  if (!ancestorRefreshes.size || ancestorRefreshQueued) return;
  ancestorRefreshQueued = true;
  queueMicrotask(() => {
    ancestorRefreshQueued = false;
    const pending = [...ancestorRefreshes];
    ancestorRefreshes.clear();
    for (const drawing of pending) drawing.refresh();
  });
}
var immutable = (value) => {
  if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) immutable(child);
    Object.freeze(value);
  }
  return value;
};
var unavailable = (reading) => immutable({
  ...structuredClone(reading),
  actions: Object.fromEntries(
    Object.entries(reading.actions).map(([verb, entry]) => [
      verb,
      { ...entry, available: false, undo: [] }
    ])
  )
});
function createWidgetController(owner) {
  const descriptor = widgetDescriptor(owner);
  if (!descriptor)
    throw new Error(
      `leaf: <${owner.localName}>#${owner.id || "(missing id)"} has no captured widget descriptor`
    );
  const selected = applicationState.selectWidget(descriptor);
  let deferred = false;
  let preparationHandle = null;
  const pendingPreparations = /* @__PURE__ */ new Map();
  let preparation = null;
  let preparationBatch = null;
  const read2 = () => descriptorStillMatches(owner, descriptor) ? selected.read() : unavailable(selected.read());
  const prepared = () => {
    if (!preparationHandle && owner.isConnected)
      preparationHandle = attachWidgetPresentation(descriptor.id, "preparation", owner);
    return preparationHandle;
  };
  const holdPreparation = (promise) => {
    if (pendingPreparations.has(promise)) {
      if (owner.isConnected && !pendingPreparations.get(promise))
        pendingPreparations.set(promise, holdRendering());
      return;
    }
    pendingPreparations.set(promise, owner.isConnected ? holdRendering() : null);
    const settled = () => {
      pendingPreparations.get(promise)?.(owner.isConnected ? "settle" : "cancel");
      pendingPreparations.delete(promise);
    };
    Promise.resolve(promise).then(settled, settled);
  };
  const presentPreparation = (handle, { value, completion }) => handle.present(value, (reason) => failSoftUnreported(owner, reason)).resolve(completion);
  const connect = () => d(() => {
    if (!owner.isConnected) return;
    for (const promise of pendingPreparations.keys()) holdPreparation(promise);
    if (preparation && !preparationHandle) {
      const handle = prepared();
      if (handle) presentPreparation(handle, preparation);
    }
  });
  const disconnect = () => {
    preparationHandle?.disconnect();
    preparationHandle = null;
    for (const [promise, release] of pendingPreparations) {
      release?.("cancel");
      pendingPreparations.set(promise, null);
    }
  };
  watchOwner(owner, { connect, disconnect });
  return Object.freeze({
    read: read2,
    dispatch(command) {
      if (!descriptorStillMatches(owner, descriptor)) return null;
      const delivery = dispatchWidget(descriptor, command);
      if (!delivery) return null;
      return immutable({ reading: read2(), delivery });
    },
    // Hold the widget's drawing through a gesture that rewrites its nodes; the release
    // draws the newest reading at once and returns it.
    defer() {
      const drawing = selfDrawn.get(owner);
      if (!drawing)
        throw new Error(`<${owner.localName}> defers only a LeafElement's drawing`);
      if (deferred) throw new Error("Widget presentation is already deferred");
      deferred = true;
      const release = drawing.hold();
      let released = false;
      return () => {
        if (released) return read2();
        released = true;
        deferred = false;
        release();
        invalidateDom();
        return read2();
      };
    },
    present(promise) {
      const value = read2();
      if (!preparationBatch || preparationBatch.value !== value) {
        preparationBatch = { value, promises: [] };
      }
      preparationBatch.promises.push(promise);
      const batch = preparationBatch;
      const completion = Promise.all(batch.promises);
      batch.completion = completion;
      preparation = { value, completion };
      holdPreparation(promise);
      const handle = prepared();
      if (handle) presentPreparation(handle, preparation);
      const clear = () => {
        if (preparationBatch?.completion === completion) preparationBatch = null;
      };
      completion.then(clear, clear);
      return promise;
    }
  });
}
function widgetController(owner) {
  let controller = controllers.get(owner);
  if (!controller) {
    let implementation = null;
    const resolve = () => implementation ??= createWidgetController(owner);
    controller = Object.freeze(
      Object.fromEntries(
        ["read", "dispatch", "defer", "present"].map((method) => [
          method,
          (...args) => resolve()[method](...args)
        ])
      )
    );
    controllers.set(owner, controller);
  }
  return controller;
}

// runtime/data.js
function acceptData(candidate, taken) {
  return applicationState.acceptData(candidate, taken);
}
var joined = /* @__PURE__ */ new Set();
async function notifyDataSubscribers() {
  const version = runtime.data.version;
  deliveries.value += 1;
  await whenApplicationRegionsPresented(
    [...joined],
    () => runtime.data.version === version
  );
  if (version !== null && runtime.data.version === version)
    setRuntimeRootAttribute(document.body, PAGE_PAINT_ATTRIBUTE.dataVersion, version);
}
var declaredInput = (element, input) => {
  const declaration = registry[element.localName]?.["x-data"]?.[input];
  if (!declaration)
    throw new Error(
      `<${element.localName}> input ${input} is not declared by this widget`
    );
  return declaration;
};
var outputOwners = /* @__PURE__ */ new WeakMap();
var outputKeys = /* @__PURE__ */ new WeakMap();
var outputSequence = 0;
function outputKey(element) {
  if (!outputKeys.has(element)) outputKeys.set(element, `output:${++outputSequence}`);
  return outputKeys.get(element);
}
function publishOutput(element, output, value) {
  const declaration = registry[element.localName]?.["x-output"]?.[output];
  if (!declaration)
    throw new Error(
      `publishOutput(${element.localName}, ${output}) output is not declared by this widget`
    );
  if (!element.id) throw new Error("publishOutput requires a widget id");
  let owner = outputOwners.get(element);
  if (!owner) {
    owner = { values: /* @__PURE__ */ new Map(), connected: false };
    outputOwners.set(element, owner);
    watchOwner(element, {
      connect() {
        owner.connected = true;
        for (const [name, reading2] of owner.values)
          applicationState.publishOutput(outputKey(element), name, reading2);
      },
      disconnect() {
        owner.connected = false;
        for (const name of owner.values.keys())
          applicationState.publishOutput(outputKey(element), name, null);
      }
    });
  }
  const reading = value === null ? null : { contract: declaration.contract, value: structuredClone(value) };
  owner.values.set(output, reading);
  if (owner.connected)
    applicationState.publishOutput(outputKey(element), output, reading);
}
function inputBinding(element, declaration) {
  const source = declaration.source ? element.getAttribute(declaration.source) : null;
  const widget = declaration.reference && element.getAttribute(declaration.reference);
  if (source && widget)
    throw new Error(
      `<${element.localName}> input binds both an external source and widget output`
    );
  if (declaration.reference) requireReference("data", element, declaration.reference);
  const selected = applicationState.select((root) => {
    if (source)
      return Object.hasOwn(root.data.sources, source) ? root.data.sources[source] : null;
    if (!widget) return null;
    const producer = referencedProjection(element, declaration.reference, widget);
    if (!producer) return null;
    const key = outputKey(producer);
    const outputs = Object.hasOwn(root.outputs, key) ? root.outputs[key] : null;
    return outputs && Object.hasOwn(outputs, declaration.output) ? outputs[declaration.output] : null;
  });
  const snapshot = (reading, input) => source ? {
    source,
    ...reading,
    origin: {
      input,
      source,
      contract: declaration.contract,
      revision: reading.revision
    }
  } : { ...reading, origin: { derived: [{ widget }] } };
  return { source, widget, selected, snapshot };
}
function dataReader(element, input, accepted) {
  const declaration = declaredInput(element, input);
  const { source, widget, selected, snapshot } = inputBinding(element, declaration);
  let stopAccepted;
  const delivered = J(
    () => {
      deliveries.value;
      return d(selected.read);
    },
    {
      watched() {
        let seen2 = d(selected.read);
        stopAccepted = selected.subscribe((now) => {
          if (now === seen2) return;
          seen2 = now;
          accepted();
        });
      },
      unwatched() {
        stopAccepted?.();
        stopAccepted = null;
      }
    }
  );
  let reported = null;
  let copied = { store: null, value: null };
  return () => {
    const sourceStore = (
      /** @type {{contract: string, revision?: string} | null} */
      widget ? selected.read() : delivered.value
    );
    const incompatible = sourceStore && sourceStore.contract !== declaration.contract;
    if (incompatible && reported !== sourceStore) {
      reported = sourceStore;
      reportPageError(
        `${source ? `data source ${source}` : `widget output ${widget}.${declaration.output}`} carries contract ${sourceStore.contract}; <${element.localName}> input ${input} requires ${declaration.contract}`
      );
    }
    if (incompatible || !sourceStore || !Object.hasOwn(sourceStore, "value"))
      return null;
    if (sourceStore !== copied.store)
      copied = {
        store: sourceStore,
        value: structuredClone(snapshot(sourceStore, input))
      };
    return copied.value;
  };
}
var deliveries = Z(0);
function joinDataDelivery(region) {
  joined.add(region);
  return () => joined.delete(region);
}
async function loadDeferred(manifest, key) {
  const { source, revision } = manifest;
  const current = () => {
    const reading = (
      /** @type {{revision?: string, contract?: unknown} | undefined} */
      runtime.data.sources[source]
    );
    return reading?.revision === revision && reading.contract === manifest.contract && Object.hasOwn(reading, "value");
  };
  if (!current())
    throw new Error(
      `source ${source} revision ${revision} changed before loading deferred ${key}`
    );
  if (offlineInteractive) {
    const records = registry.$data.contracts[manifest.contract].records;
    const item = offlineData().sources[source].value[records.items].find(
      (item2) => item2[records.key] === key
    );
    if (!item)
      throw new Error(`unknown record key '${key}' in data source '${source}'`);
    if (!Object.hasOwn(item, records.deferred))
      throw new Error(
        `record '${key}' in data source '${source}' has no deferred field '${records.deferred}'`
      );
    return structuredClone(item[records.deferred]);
  }
  const params = new URLSearchParams({ source, source_revision: revision, key });
  const answer = await requestJson(
    pageUrl(`api/deferred?${params}`),
    {},
    "deferred value"
  );
  if (!current())
    throw new Error(
      `source ${source} revision ${revision} changed while loading deferred ${key}`
    );
  return structuredClone(answer.value);
}

// runtime/leaf-element.js
var regions = 0;
var UpdateBoundary = class extends LitElement {
  signalUpdateFailed(error) {
    throw error;
  }
  performUpdate() {
    try {
      super.performUpdate();
    } catch (error) {
      this.signalUpdateFailed(error);
    }
  }
};
var LeafElement = class extends q(UpdateBoundary) {
  #signalError = null;
  #stopReadiness = null;
  signalUpdateFailed(error) {
    this.#signalError = { error };
  }
  requestUpdate(...args) {
    const wasPending = this.isUpdatePending;
    const result = super.requestUpdate(...args);
    if (this.hasUpdated && this.isUpdatePending && (!wasPending || !this.#updating))
      d(() => {
        if (this.#connected && this.#region && !this.#ticket)
          this.#ticket = this.#claim();
      });
    return result;
  }
  /** Finish this render when its presentation prerequisites are ready. Readiness
   * does not claim another presentation, which would invalidate its own proof. */
  whenReady(read2) {
    if (d(read2)) return true;
    if (!this.#stopReadiness) {
      this.#stopReadiness = watchPresentation(() => {
        if (!d(read2)) return;
        this.#stopReadiness?.();
        this.#stopReadiness = null;
        super.requestUpdate();
      });
    }
    return false;
  }
  #descriptor = null;
  #controller = null;
  #verbs = [];
  #region = null;
  #regionName = null;
  #connected = false;
  #connectedParent = null;
  // The open claim the next update that draws settles.
  #ticket = null;
  #held = false;
  // The fail-soft box standing until the next update that draws; a `setup()` that threw
  // leaves the element broken, drawing nothing.
  #box = null;
  #broken = false;
  // The claim the update under way draws, settled once `updated` has run too.
  #drawing = null;
  #updating = false;
  // The drawing that follows the update under way, which its claim waits for.
  #work = null;
  #data = /* @__PURE__ */ new Map();
  #leaveData = null;
  #scheduled = null;
  createRenderRoot() {
    return this;
  }
  scheduleUpdate() {
    return this.#scheduled ?? this.#queueUpdate();
  }
  #queueUpdate() {
    if (!this.#descriptor) return super.scheduleUpdate();
    const scheduled = queueWidgetUpdate(
      this.#descriptor.id,
      () => {
        if (this.#scheduled !== scheduled) return;
        this.#scheduled = null;
        return super.scheduleUpdate();
      },
      () => this.updateComplete
    );
    this.#scheduled = scheduled;
    return scheduled;
  }
  connectedCallback() {
    if (once(this)) this.#setup();
    super.connectedCallback();
  }
  #setup() {
    this.#descriptor = widgetDescriptor(this);
    if (this.#descriptor) {
      this.#controller = widgetController(this);
      drawsItself(this, {
        hold: () => this.#hold(),
        refresh: () => this.#refresh()
      });
      this.#verbs = Object.keys(this.#descriptor.declaration["x-state"] ?? {});
    }
    this.#regionName = this.#descriptor ? null : `element:${this.localName}#${this.id}:${++regions}`;
    placesFailure(this, (box) => {
      const root = this.renderRoot ?? this;
      if (root === this && this.shadowRoot) return false;
      if (this.#box?.parentNode === root && this.#box.textContent === box.textContent)
        return true;
      this.#box?.remove();
      this.#box = box;
      root.append(box);
      return true;
    });
    try {
      this.setup();
    } catch (error) {
      this.#broken = true;
      failSoft(this, error);
    }
    watchOwner(this, {
      connect: () => d(() => this.#connect()),
      disconnect: () => this.#disconnect()
    });
  }
  /** The module's one-time build, on the first connection, before the first render. */
  setup() {
  }
  /** The widget's complete reading (`widgetController(this).read()`), collected; null
   *  for an element the registry does not declare a widget, such as a quoted one. */
  get reading() {
    return this.#controller?.read() ?? null;
  }
  /** The widget's state, with every admitted and unresolved record folded in. */
  get state() {
    return this.reading.state;
  }
  /** The widget's controller, for `dispatch` and `present`. */
  get controller() {
    return this.#controller;
  }
  /** The bound reading of a declared `x-data` input, one copy a delivery (data.js). */
  data(input) {
    let read2 = this.#data.get(input);
    if (!read2)
      this.#data.set(input, read2 = dataReader(this, input, () => this.#stage()));
    return read2();
  }
  // The controller's `defer` for this widget, which refuses a second hold and releases
  // once: hold its presentation through a gesture that rewrites its nodes; the release
  // draws the newest reading at once.
  #hold() {
    this.#held = true;
    return () => {
      this.#held = false;
      this.#refresh();
    };
  }
  #complete() {
    if (!this.#controller) return true;
    const { state } = this.#controller.read();
    return this.#verbs.every((verb) => verb in state);
  }
  shouldUpdate(changed) {
    if (!this.#connected || !this.isConnected) {
      return false;
    }
    if (this.#held) return false;
    this.#drawing = this.#ticket;
    this.#ticket = null;
    if (this.#broken) return false;
    if (!this.#complete()) return false;
    return super.shouldUpdate(changed);
  }
  update(changed) {
    super.update(changed);
    this.#box?.remove();
    this.#box = null;
  }
  // An update settles its claim once all of it has run, `updated` included, and one
  // that failed anywhere, its gate too, reports once and shows its failure; Lit has
  // marked it done, so the next move draws again. A draw that `updated` asks for at
  // once, as a module's own paint may, settles its own claim inside this one; with no
  // claim of its own, its failure is the enclosing claimed update's.
  performUpdate() {
    const outer = this.#drawing;
    const updating = this.#updating;
    let outerWork = this.#work;
    this.#drawing = null;
    this.#work = null;
    this.#updating = true;
    try {
      this.#signalError = null;
      super.performUpdate();
      if (this.#signalError) throw this.#signalError.error;
      const work = this.#work;
      if (work && !this.#drawing) {
        if (outer) outerWork = outerWork ? Promise.all([outerWork, work]) : work;
        else if (this.#region) this.#drawing = this.#claim();
      }
      this.#drawing?.resolve(work ?? void 0);
    } catch (error) {
      if (outer && !this.#drawing) throw error;
      this.#failed(error, this.#drawing);
    } finally {
      this.#drawing = outer;
      this.#work = outerWork;
      this.#updating = updating;
    }
  }
  /** Hold the update under way's claim until `work`, drawing that follows the render
   *  asynchronously, lands: highlighting a document, say. An update no move claimed
   *  claims the region for it. The widget's presentation, and the data version a
   *  delivery it draws holds, wait for it. Call it from `render()` or `updated()`. */
  drawing(work) {
    const named = Promise.resolve(work).catch((error) => {
      reportFailure(this, error);
      throw error;
    });
    this.#work = this.#work ? Promise.all([this.#work, named]) : named;
  }
  /** The render drawn again at once, outside any claim and Lit's own schedule, with a
   *  failure thrown rather than shown: the render check's replay
   *  (render-checks/replay.js), which holds a draw of the same reading to change
   *  nothing. `updated()` does not run, since what follows a draw may start
   *  preparation that would claim the widget's presentation and land after the check
   *  reads the page. An update Lit has queued stays queued, with its claim. */
  redraw() {
    render(this.render(), this.renderRoot, this.renderOptions);
  }
  updated(changed) {
    super.updated(changed);
    d(() => paintKeysWithin(this));
  }
  // Every failure is reported here, naming the widget; a claim's rejection then shows
  // the box through the coordinator's fallback, which reports nothing again.
  #failed(error, ticket) {
    if (!ticket) return failSoft(this, error);
    reportFailure(this, error);
    ticket.reject(error);
  }
  // A claim on the region for the reading as it stands, which a failure settles with
  // the fail-soft box.
  #claim() {
    return this.#region.present(
      d(() => this.#controller?.read() ?? {}),
      (reason) => failSoftUnreported(this, reason)
    );
  }
  // Claim the region for a reading that draws later, leaving the claim open.
  #stage() {
    if (!this.#connected || this.#ticket || !this.#region) return;
    this.#ticket = this.#claim();
  }
  // Claim the region for the reading as it stands, and draw it on the next update; a
  // claim the next update cannot draw stays open until one does.
  #present({ now = false } = {}) {
    if (!this.#region) return;
    this.#ticket = this.#claim();
    if (this.#held) return;
    this.requestUpdate();
    if (now) {
      this.#scheduled = null;
      this.performUpdate();
    } else if (this.#descriptor) this.#queueUpdate();
  }
  #refresh() {
    if (this.#connected) this.#present({ now: true });
  }
  #connect() {
    this.#connected = true;
    this.#region = this.#descriptor ? attachWidgetPresentation(this.#descriptor.id, "render", this) : attachApplicationPresentation(this.#regionName, this);
    const parentChanged = this.#connectedParent !== this.parentElement;
    this.#connectedParent = this.parentElement;
    if (registry[this.localName]?.["x-data"])
      this.#leaveData = joinDataDelivery(
        this.#descriptor ? `widget:${this.#descriptor.id}:render` : this.#regionName
      );
    this.#present();
    if (this.#descriptor) widgetMounted(this, this.#descriptor, parentChanged);
  }
  #disconnect() {
    this.#connected = false;
    this.#stopReadiness?.();
    this.#stopReadiness = null;
    this.#leaveData?.();
    this.#leaveData = null;
    this.#ticket = null;
    this.#region?.disconnect();
    this.#region = null;
  }
};

// runtime/queue-title.js
function queueTitle(item) {
  const thread = readThreads().threads.find((thread2) => thread2.id === item.thread);
  const own = elementById(item.subject.id);
  const topic = thread ? threadName(thread) : "";
  const title = item.todo?.title ?? item.obligation?.prompt.text;
  if (title) return title;
  const reply = item.kind === "update" ? item.obligation?.answer?.event?.id : null;
  const sent = reply && thread?.msgs.find((message) => message.id === reply);
  if (sent) return sent.body.text.trim() || topic;
  if (item.subject.kind === "widget") {
    const record = own && obligationHolding(readObligations().all, own);
    return record && addressableLabel(obligationPlace(record).context) || addressableLabel(own) || topic || item.id;
  }
  return topic || item.id;
}

// runtime/obligations/answer.js
function ownedObligationControl(source, commandSource) {
  const selector = tagsDeclaring((entry) => entry["x-awaits"]).join(",");
  return !selector || closestAcross(commandSource, selector) === source;
}
function obligationWord(item) {
  if (item.source.kind === "message") return "Reply";
  if (item.source.kind === "todo") return "To-do";
  const word2 = widgetWord(item.source.tag, elementById(item.source.id));
  return word2.charAt(0).toUpperCase() + word2.slice(1);
}
function answerWords(item) {
  if (item.answer === null) return "";
  if (answeredInWords(item))
    return item.answer.value.text ?? item.answer.value.token ?? "";
  const source = elementById(item.source.id);
  const formatter = (
    /** @type {{answerWords?: (value: unknown, element: Element) => unknown}} */
    customElements.get(item.source.tag)?.answerWords
  );
  return String(source && formatter ? formatter(item.answer.value, source) : "").replace(/\s+/g, " ").trim();
}
function obligationEnding(item) {
  if (item.source.kind === "todo")
    return item.status === "withdrawn" ? "Dropped" : item.answer?.value === "failed" ? "Failed" : "Done";
  if (item.status === "withdrawn") return "Withdrawn";
  if (item.status === "answered_elsewhere") return "Answered elsewhere";
  const words = answerWords(item);
  return words ? `Answered: ${words}` : "Answered";
}

export {
  initializeServedDocument,
  readPlace,
  returnPlace,
  pushEntry,
  replaceEntry,
  claimTraversals,
  mountHistory,
  keepPageRulesOffLayer,
  MAX_DRAWING_STROKES,
  MAX_DRAWING_FRAME_DEPTH,
  MAX_DRAWING_POINTS,
  DRAWING_COORDINATE_LIMIT,
  MAX_DRAWING_SAYS_LENGTH,
  LeafEditorView,
  textField,
  fabBar,
  fabInput,
  fabOptionsTrigger,
  composerQuote,
  pendingAnchor,
  pendingAbout,
  pendingDrawing,
  composerOpen,
  createSelectionComposer,
  currentProjection,
  inPageOrder,
  commandSteps,
  paintCoreControls,
  requireReference,
  referencedProjection,
  createAnchorTravel,
  versionPicker,
  versionsReading,
  comparisonChanges,
  createVersionController,
  reactionTokens,
  reactionAvailable,
  paintBarReactions,
  createReactionController,
  sendReaction,
  queueItemKey,
  readQueues,
  readPlan,
  beginRead,
  mountApplication,
  threadBox2 as threadBox,
  landInThread,
  navigateToDatum,
  projectData,
  placePageThreads2 as placePageThreads,
  consumeAnnotations,
  registerThreadPresentation,
  threadActions,
  obligationActions,
  queueActions,
  wireInput,
  threadInput,
  standingThread,
  leavesBox,
  createThreadLanding,
  declareThreadKeys,
  widgetController,
  acceptData,
  notifyDataSubscribers,
  publishOutput,
  loadDeferred,
  LeafElement,
  queueTitle,
  ownedObligationControl,
  obligationWord,
  answerWords,
  obligationEnding
};
