import {
  KINDS,
  activateContributionControl,
  annotationItems,
  clearContributionControls,
  closeVersionMenu,
  compareContributions,
  contributionControlKey,
  contributionEntries,
  contributionEntryRecord,
  contributionSource,
  entryControls,
  latestChip,
  latestVersionLabel,
  marginInventory,
  materializeContributionControls,
  presentContributionReceipts,
  presentingContributions,
  registerContribution,
  spokenSubject,
  versionBtn,
  versionMenu,
  versionMenuIsOpen,
  versionPicker,
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
  allButCommandReference,
  allThreads,
  alreadyShown,
  anchorLabel,
  askHolding,
  askPlace,
  beginThreadSeats,
  beginWalk,
  blocksOnScreen,
  bringBackSurfaceOf,
  captureDraftEditing,
  capturePlace,
  claimed,
  clearDraft,
  clearThreadMirrors,
  commandShortcut,
  commitThreadSeats,
  completeReadingReturn,
  coveringAuxiliarySurface,
  createReplyView,
  declareSide,
  dismissReplyAt,
  draftContexts,
  draftEditingDestination,
  draftEditingStands,
  finishFold,
  fitsWhole,
  focusThread,
  focusedInView,
  focusedThreadTarget,
  formatDeclaredMarkdown,
  hasFolding,
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
  landingRoom,
  landingTarget,
  latestTurn,
  listWalkPosition,
  loadDraft,
  loadMarkdown,
  loadMessageMarkdown,
  markdownReady,
  messageReading,
  messageText,
  mountFirstMessage,
  newsNotice,
  openMessageEditIn,
  openingPassage,
  pageCommand,
  pageReadingBlock,
  pageScope,
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
  prepareEntry,
  rawOffsetFits,
  readAsks,
  readThreads,
  readingReturn,
  registerWritingDestination,
  reindexPassageOwners,
  rememberPassageParts,
  rememberWriting,
  renderMarginThread,
  renderSeats,
  renderSurfaces,
  renderThreadMirrors,
  replaceEntry,
  replyAvailable,
  replyDestination,
  replyDraftContext,
  restoreDraftEditing,
  restorePlace,
  restoreReplyEditing,
  restrictUserIntent,
  retainThreadSeats,
  retainUserIntent,
  returnToBannerControl,
  revealHeld,
  rowWalk,
  saveDraft,
  scrollIntoReadingBand,
  scrollIntoView,
  scrollThreadIntoView,
  sendLanding,
  sendMessage,
  settleAcceptedDrafts,
  showHeld,
  showHeldThread,
  showNews,
  strongestWorkflow,
  surfaceFocusTarget,
  tabStore,
  textBlocks,
  threadAttention,
  threadFocusDestination,
  threadFocusStop,
  threadList,
  threadPart,
  threadReading,
  threadReplyInput,
  threadRewrites,
  threadState,
  transferDraft,
  watchDraft,
  watchDrafts,
  watchThreadSurfaces,
  whenFolded,
  wholeThread,
  workflowLabel
} from "./bundle-chrome.js";
import {
  aborted,
  authoredStates,
  commitWidgetDescriptors,
  quoted,
  rememberAuthoredParents,
  stageAuthoredStates,
  stageWidgetDescriptors
} from "./bundle-widget-upgrade.js";
import {
  scrollBehavior
} from "./bundle-motion.js";
import {
  commitPoint,
  livePoint,
  settleResidency
} from "./bundle-content-layout.js";
import {
  ADDRESSABLE,
  addressableLabel,
  addressableWord,
  addressedElements,
  anchorForRange,
  anchoringIsReady,
  fragmentTarget,
  referencedProjection,
  requireReference,
  resolveAnchor,
  revealAddressed,
  sectionOf,
  targetElement,
  targetPlace,
  targetSegments,
  visualPartLabel
} from "./bundle-visual-parts.js";
import {
  initialOrigin,
  restoreInitialSource,
  unmarkedCopy
} from "./bundle-initial-render.js";
import {
  PRESENTATION,
  SCROLL_SLACK,
  activityTransitionDue,
  ago,
  chosenSince,
  clocked,
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
  readingPaint,
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
  serverNow,
  settlePageInterface,
  shownRegionBounds,
  tickClock,
  watchReadingRegionTransitions
} from "./bundle-presence.js";
import {
  orderChildren,
  patchRetains,
  patchTree,
  setChildren
} from "./bundle-stylesheets.js";
import {
  DATUM,
  TEXT_BLOCK,
  alignInlineText,
  authored,
  closestAcross,
  elementById,
  excerptWords,
  inChrome,
  labelWords,
  pageDocument,
  pageParts,
  pageReadingVersion,
  rangeOf,
  readingFrom,
  selectEnds,
  textNodesUnder,
  wrote
} from "./bundle-passage-facts.js";
import {
  PAGE_PAINT_ATTRIBUTE,
  PRESS,
  PRESSABLE,
  TEXT_ENTRY,
  admitResponse,
  announce,
  claimsEsc,
  clamp,
  clippedPlace,
  clipsPast,
  clipsPastSurfaces,
  closeNativeLayer,
  containingView,
  countTraffic,
  el,
  frameFor,
  growthIsSeen,
  intersect,
  keys,
  labelOf,
  landingBand,
  layerHeaders,
  layoutChanged,
  matchesWhen,
  notice,
  offer,
  paintKeys,
  placeBox,
  placeHolder,
  pointerAt,
  postEvent,
  presented,
  pruneScopedElements,
  randomId,
  reachedForWords,
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
  skipped,
  tagsDeclaring,
  union,
  watchOwner,
  watchPendingTraffic,
  watchRoom,
  whenNone,
  whileConnected
} from "./bundle-page-paint.js";
import {
  LIVE_ROOT,
  PRESENTATION_ORDER,
  agentLabel,
  annotationMode,
  applicationPresenter,
  applicationState,
  attachApplicationPresentation,
  documentChanged,
  layerRoot,
  offlineData,
  offlineInteractive,
  offlineState,
  pageUrl,
  presentDocument,
  projectView,
  projectionRegionsPresented,
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
  handBack,
  holdFocus,
  inputCount,
  keeps,
  keepsHidden,
  move,
  nextAnimation,
  nextRender,
  onPress,
  onSampleVisibility,
  onStanding,
  onUserInput,
  openLayer,
  openerOf,
  pressing,
  readCaret,
  readSampleVisibility,
  renderedOrder,
  renderedUnder,
  renderingState,
  sampleVisibility,
  shadowHost,
  sizeObserver,
  standingIn,
  takesLetters,
  typesText,
  under,
  upFrom,
  whenLeft
} from "./bundle-sample-visibility.js";
import {
  M,
  PENDING,
  actionForWidget,
  anchorKey,
  askValue,
  bindQueuedWork,
  collectReads,
  editable,
  foldWidgetStates,
  isMessageEvent,
  isThreadEvent,
  moved,
  outsideReading,
  projectionOrigins,
  reactionsAt,
  stateCoordinate,
  threadKey,
  threadNames,
  threadSummary,
  tokenChoices,
  untracked
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

// runtime/page-sheets.js
var APPARATUS = ":not(:where(.lf-chrome, .lf-chrome *, .lf-ui, .lf-ui *))";
var NAMES_WIDGET = /(?:^|[\s>+~(,&|])[a-z][\w]*-|[.#]lf-|\[\s*data-lf-/i;
var NOT_SELECTORS = /"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|:{1,2}(?:lang|dir|state|part|highlight|nth-[a-z-]+)\([^)]*\)/gi;
var namesWidget = (text) => NAMES_WIDGET.test(text.replace(NOT_SELECTORS, ""));
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
function narrowRules(rules, named) {
  for (const rule of rules) {
    if (rule instanceof CSSKeyframesRule || rule instanceof CSSImportRule) continue;
    let within = named;
    if (rule instanceof CSSScopeRule)
      within ||= namesWidget(rule.start ?? "") || namesWidget(rule.end ?? "");
    if (rule instanceof CSSStyleRule) {
      const list = members(rule.selectorText);
      if (!named) {
        const next = list.map(
          ([member, pseudo]) => namesWidget(member) ? member : narrow(member, pseudo)
        ).join(", ");
        if (next !== rule.selectorText) rule.selectorText = next;
      }
      within ||= list.every(([member]) => namesWidget(member));
    }
    if (rule.cssRules) narrowRules(rule.cssRules, within);
  }
}
function narrowSheet(sheet2, runtime2) {
  const owner = sheet2.ownerNode;
  if (sheet2.href && new URL(sheet2.href).origin !== window.origin && !owner?.hasAttribute?.("crossorigin"))
    return;
  if (!narrowed.has(sheet2)) {
    narrowed.add(sheet2);
    if (!runtime2) narrowRules(sheet2.cssRules, false);
    else
      for (const rule of sheet2.cssRules)
        if (rule instanceof CSSLayerBlockRule && rule.name === "lf-theme")
          narrowRules(rule.cssRules, false);
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
  new MutationObserver((records) => {
    for (const record of records)
      for (const node of record.addedNodes)
        if (node instanceof HTMLLinkElement)
          node.addEventListener("load", keepPageRulesOffLayer, { once: true });
    keepPageRulesOffLayer();
  }).observe(document.head, {
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
  const x = view.textDirection === Direction.LTR ? box.left : box.right;
  return {
    destination,
    rectangle: { left: x, right: x, top: box.top, bottom: box.bottom }
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
  const x = horizontal === "center" ? (rectangle.left - margins.left + rectangle.right + margins.right - left - right) / 2 : travel(
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
    left: port.scrollWidth > port.clientWidth ? x / scaleX : 0,
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
var recordFormat = (kind) => `leaf-${kind}/6`;

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
  .cm-line { padding: 0; }
  /* The placeholder is a layer under the words, as a textarea's is, never content in
     the line: a widget in an empty line is what the platform would draw the caret
     against. Both layers share one grid cell, inside the host's padding. */
  .lf-field { display: grid; }
  .lf-field > * { grid-area: 1 / 1; min-width: 0; }
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
  /* The placeholder is a single line, so it stands where a last line would. */
  .lf-field-placeholder { padding-inline-end: var(--lf-field-end-room); }
  /* The action stands beside more than the last line under a finger, whose hit box is
     taller than a line, and in a scrolled field, which carries other lines past it. */
  @media (pointer: coarse) {
    .lf-field { padding-inline-end: var(--lf-field-end-room); }
    .lf-field-placeholder { padding-inline-end: 0; }
    .cm-line.lf-field-last::after { content: none; }
  }
  :host(:state(scrolls)) .lf-field { padding-inline-end: var(--lf-field-end-room); }
  :host(:state(scrolls)) .cm-line.lf-field-last::after { content: none; }
  /* A draft wears the sent message's faces. Strong, emphasis and strikethrough are the
     elements themselves, which the platform dresses here as it does in the message;
     the rest read the theme's tokens, since its element rules stop at this root. A
     heading is bold, as the platform draws one, at the size of the words around it. A
     block is drawn line by line, so a code block's frame is each line's sides, closed
     above its first line and below its last. */
  .lf-md-mark { color: var(--muted); }
  code { font-family: var(--mono); font-size: var(--code-inline-size);
    background: var(--code-bg); border-radius: var(--code-inline-r);
    padding: var(--code-inline-pad); box-decoration-break: slice; }
  .lf-md-heading { font-weight: bold; }
  .lf-md-link { color: var(--accent); text-decoration: underline var(--link-underline);
    text-underline-offset: var(--link-underline-offset); }
  .lf-md-quote { border-inline-start: var(--quote-rule); font-style: var(--quote-style);
    padding-inline-start: var(--quote-inset); color: var(--muted); }
  .lf-md-code-block { font-family: var(--mono); font-size: var(--code-size);
    line-height: var(--code-line); color: var(--code-ink); background: var(--pre-bg);
    font-variant-ligatures: none; border-inline: 1px solid var(--code-border);
    padding-inline: var(--pre-inset); }
  .lf-md-code-first { border-block-start: 1px solid var(--code-border);
    border-start-start-radius: var(--r); border-start-end-radius: var(--r); }
  .lf-md-code-last { border-block-end: 1px solid var(--code-border);
    border-end-start-radius: var(--r); border-end-end-radius: var(--r); }
`);
var ownerStep = StateEffect2.define();
var hide = Decoration.replace({});
var dim = Decoration.mark({ class: "lf-md-mark" });
var link = Decoration.mark({ class: "lf-md-link" });
var line = (cls) => Decoration.line({ class: cls });
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
  for (const { token, from, to, contentFrom, contentTo, escapes } of placed) {
    const syntax = touches(state, from, to) ? dim : hide;
    const text = state.doc.sliceString(from, to);
    if (token.type === "code_inline" || contentFrom !== void 0) {
      const words2 = token.type === "code_inline" ? [from + token.markup.length, to - token.markup.length] : [contentFrom, contentTo];
      if (words2[0] > words2[1]) continue;
      if (INLINE[token.type]) add(from, to, INLINE[token.type]);
      else if (token.type === "link_open" && token.meta.linked)
        add(words2[0], words2[1], link);
      add(from, words2[0], syntax);
      add(words2[1], to, syntax);
    } else if (token.type === "text") {
      for (const at of escapes ?? [])
        add(at, at + 1, touches(state, at, at + 2) ? dim : hide);
    } else if (token.type === "heading_open") {
      const end = from + text.trimEnd().length;
      const atx = text.match(/^ {0,3}#{1,6}(?:[ \t]+|$)/);
      lines(from, end, (each) => {
        const underline = !atx && each.to >= end;
        if (underline) add(each.from, each.to, dim);
        else out.push(line("lf-md-heading").range(each.from));
      });
      if (atx) add(from, from + atx[0].length, syntax);
    } else if (token.type === "fence" || token.type === "code_block") {
      const end = from + text.trimEnd().length;
      const fenced = /^ {0,3}(`{3,}|~{3,})/.test(text);
      lines(from, end, (each) => {
        const ends = [
          each.from <= from ? " lf-md-code-first" : "",
          each.to >= end ? " lf-md-code-last" : ""
        ].join("");
        out.push(line(`lf-md-code-block${ends}`).range(each.from));
        if (fenced && (each.from === from || /^ {0,3}(`{3,}|~{3,})\s*$/.test(each.text)))
          add(each.from, each.to, dim);
      });
    } else if (token.type === "blockquote_open") {
      lines(from, from + text.trimEnd().length, (each) => {
        out.push(line("lf-md-quote").range(each.from));
        const mark = each.text.match(/^ {0,3}> ?/);
        if (mark) add(each.from, each.from + mark[0].length, dim);
      });
    } else if (token.type === "list_item_open") {
      const mark = text.match(/^ {0,3}(?:[*+-]|\d{1,9}[.)])/);
      if (mark) add(from, from + mark[0].length, dim);
    }
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
  // The field's one model. Until the element first connects it is a bare EditorState,
  // which holds the value, selection and configuration without a DOM; connecting hands
  // it to the view that edits it from then on. A composer built and never shown pays
  // for no editor.
  #model;
  #view = null;
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
          return {
            caret,
            scaleX,
            scaleY,
            top: box.top + this.clientTop * scaleY,
            left: box.left + this.clientLeft * scaleX,
            // client dimensions round fractional CSS sizes. Keep the trailing
            // edges on the actual box, inset by its native border and scrollbar.
            bottom: box.bottom - (this.offsetHeight - this.clientTop - this.clientHeight) * scaleY,
            right: box.right - (this.offsetWidth - this.clientLeft - this.clientWidth) * scaleX
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
  // scroller too. Editor updates and size changes share its read/write phase: the room
  // changes layout there, rather than feeding back into resize observer delivery.
  #overflow = sizeObserver(() => this.#measureOverflow());
  #measureOverflow() {
    this.#view?.requestMeasure({
      key: this.#overflow,
      read: () => this.scrollHeight > this.clientHeight,
      write: (scrolls) => {
        if (scrolls) this.#internals.states.add("scrolls");
        else this.#internals.states.delete("scrolls");
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
    this.#frame.append(this.#placeholderLayer);
    this.#root.append(this.#frame);
    this.#model = this.#create("");
    this.addEventListener("mousedown", (event) => this.#pressPadding(event));
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
          {
            key: "Shift-Enter",
            run: (view) => (view.dispatch(view.state.replaceSelection("\n")), true)
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
    if (this.#view) return;
    if (!this.hasAttribute("role")) this.setAttribute("role", "textbox");
    if (!this.hasAttribute("aria-multiline"))
      this.setAttribute("aria-multiline", "true");
    if (!this.hasAttribute("tabindex")) this.tabIndex = 0;
    this.#internals ??= this.attachInternals();
    this.#root.adoptedStyleSheets = [sheet];
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
      }
    });
    this.#model = null;
    this.#sizes.observe(this);
    this.#overflow.observe(this);
    this.#overflow.observe(this.#view.scrollDOM);
    this.#view.scrollDOM.removeAttribute("tabindex");
    this.#describe();
    this.#paintEmpty();
    this.#internals.states.add("ready");
    this.#measureOverflow();
  }
  #beforeEdit() {
    this.dispatchEvent(new Event("lf-before-edit", { bubbles: true }));
  }
  // A move between parents reconnects within the task and keeps its editor.
  disconnectedCallback() {
    queueMicrotask(() => {
      if (this.isConnected || !this.#view) return;
      this.#model = this.#view.state;
      this.#sizes.disconnect();
      this.#overflow.disconnect();
      this.#view.destroy();
      this.#view = null;
      this.#internals.states.delete("ready");
    });
  }
  #describe() {
    const content = this.#view?.contentDOM;
    if (!content || !("ariaDescribedByElements" in content)) return;
    const root = (
      /** @type {Document | ShadowRoot} */
      this.getRootNode()
    );
    content.ariaDescribedByElements = (this.getAttribute("aria-describedby") ?? "").split(/\s+/).filter(Boolean).map((id) => root.getElementById(id)).filter(Boolean);
  }
  // The editor adapter places its recorded caret without native scrolling. The
  // field reveals itself separately when its caller requests ordinary focus.
  focus(options) {
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
    if (event.button !== 0 || !this.#view) return;
    const area = this.#view.scrollDOM.getBoundingClientRect();
    const { clientX: x, clientY: y } = event;
    if (x >= area.left && x < area.right && y >= area.top && y < area.bottom) return;
    event.preventDefault();
    const clamp2 = (value, low, high) => Math.min(Math.max(value, low), high - 1);
    const at = this.#view.posAtCoords(
      { x: clamp2(x, area.left, area.right), y: clamp2(y, area.top, area.bottom) },
      false
    );
    this.#view.focus();
    this.#view.dispatch({ selection: { anchor: at } });
  }
  get #state() {
    return this.#view?.state ?? this.#model;
  }
  #apply(spec) {
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
  // last words, or `none` while its last line is blank. A sent message keeping the
  // draft's wrapping holds the same.
  get endRoom() {
    if (parseFloat(getComputedStyle(this.#frame).paddingInlineEnd) > 0)
      return "every-line";
    return lastWithWords(this.#state) ? "last-line" : "none";
  }
  get writingEndRoom() {
    return parseFloat(getComputedStyle(this).getPropertyValue("--lf-field-end-room"));
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
  get writingInlineSize() {
    const frame = getComputedStyle(this.#frame);
    return parseFloat(frame.inlineSize) + parseFloat(frame.paddingInlineEnd);
  }
  set value(text) {
    text = String(text ?? "").replace(/\r\n?/g, "\n");
    if (text === this.value) return;
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
fabOptions.setAttribute("role", "group");
fabOptions.setAttribute("aria-label", "Other responses");
var fabSuggest = responseAction(el("button", "lf-ui lf-fab-suggest"), {
  icon: "edit",
  label: "Suggest",
  collapse: true
});
fabOptions.append(fabSuggest);
fabBar.append(fab, fabOptions);
var composer = el("div", "lf-ui lf-composer");
composer.id = "lf-composer";
var composerQuote = el("blockquote", "lf-ui lf-quote detached");
composerQuote.id = "lf-composer-quote";
var suggestRow = el("label", "lf-suggest-row");
var suggestCheck = document.createElement("input");
suggestCheck.type = "checkbox";
suggestCheck.name = "suggest-replacement";
suggestRow.append(suggestCheck, document.createTextNode("Suggest replacement text"));
var composerInput = fabInput;
composerInput.setAttribute("aria-describedby", composerQuote.id);
var composerSend = el("button", "lf-btn", "Comment");
var composerField = document.createDocumentFragment();
composerField.append(composerInput);
composer.append(composerQuote, suggestRow, composerSend);
fabBar.prepend(composer);
var pendingAnchor = null;
var pendingAbout = null;
var pendingDrawing = null;
function wordsOf(element) {
  const range = document.createRange();
  range.selectNodeContents(element);
  const words2 = anchorForRange(range);
  return words2.quote?.trim() ? words2 : null;
}
var composerOpen = false;
function createSelectionComposer({
  panelIsOpen,
  setReact,
  reactionTokens: reactionTokens2,
  reactionAvailable: reactionAvailable2,
  designModeActive,
  openPageThread,
  threadTransitionOrigin,
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
  const DRAFT_FORMAT = recordFormat("draft");
  const composerCtx = (anchor) => COMPOSER_KEY + anchorKey(anchor);
  let syncComposer;
  let pendingRevision = null;
  const composerDraftValue = (text = syncComposer.value()) => JSON.stringify({
    format: DRAFT_FORMAT,
    text,
    anchor: pendingAnchor,
    revision: pendingRevision,
    suggest: suggestCheck.checked,
    about: pendingAbout,
    drawing: pendingDrawing,
    touched: Date.now()
  });
  const saveComposerDraft = (text = syncComposer.value()) => saveDraft(composerCtx(pendingAnchor), composerDraftValue(text));
  const parsedRecords = /* @__PURE__ */ new Map();
  const composerRecord = (ctx) => {
    const stored = loadDraft(ctx);
    const known = parsedRecords.get(ctx);
    if (known?.stored === stored) return known.record;
    let record = null;
    try {
      record = JSON.parse(stored);
      if (!Number.isInteger(record?.revision)) record = null;
      else if (record.format !== DRAFT_FORMAT) record = { ...record, drawing: null };
    } catch {
      record = null;
    }
    parsedRecords.set(ctx, { stored, record });
    return record;
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
    if (!record.text && !drawing) clearDraft(ctx);
    else saveDraft(ctx, JSON.stringify({ ...record, format: DRAFT_FORMAT, drawing }));
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
    suggestRow.style.display = pendingAnchor?.quote && !pendingAbout && !pendingDrawing ? "flex" : "none";
    const suggest = !suggestCheck.checked;
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
    suggestCheck.checked = Boolean(suggest);
    if (suggestCheck.checked && syncComposer.hasMedia()) {
      suggestCheck.checked = false;
      syncSuggestMode();
      notice("Remove attached images before suggesting replacement text");
      focusDestination(composerInput, "return");
      return;
    }
    if (suggestCheck.checked && !syncComposer.value() && pendingAnchor?.quote)
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
  function setResponseOptions(open, { focus = null, place = true } = {}) {
    const next = Boolean(open && fabAnchorAt() && responseOptionsAvailable());
    if (next === responseOptionsOpen) {
      if (next && focus) focusResponseOption(focus);
      return next;
    }
    if (next) setReact(false);
    responseOptionsOpen = next;
    fabBar.classList.toggle("lf-response-open", next);
    if (place && fabAnchorAt()) showFab(fabAnchorAt());
    if (next && focus) focusResponseOption(focus);
    paintKeys();
    return next;
  }
  function syncResponseOptions(anchor = fabAnchorAt()) {
    keepsHidden(
      fabSuggest,
      !(anchor?.quote && !designModeActive() && (!composerOpen || !pendingAbout && !pendingDrawing))
    );
    if (responseOptionsOpen && !responseOptionsAvailable())
      setResponseOptions(false, { place: false });
  }
  function resetResponseOptions() {
    setResponseOptions(false, { place: false });
  }
  function showComposer(open) {
    if (open && composerField.hasChildNodes()) composer.append(composerField);
    if (!open) syncComposer?.cancelDictation();
    if (composerOpen && !open && composerHolds())
      notice("Draft kept \u2014 g i resumes writing");
    composerOpen = open;
    composer.style.display = open ? "contents" : "none";
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
    suggestCheck.checked = Boolean(suggest);
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
      suggest: suggest === void 0 ? suggestCheck.checked : suggest,
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
    if (carriedDraft) transferDraft(previousCtx, ctx, composerDraftValue());
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
    suggestCheck.checked = false;
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
    if (ctx && text && !loadDraft(ctx) && !suggestCheck.checked && !pendingAbout && !pendingDrawing && !syncComposer.hasMedia())
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
      hint: () => suggestCheck.checked ? "Replacement text" : pendingAbout ? "About the layer" : "Comment\u2026",
      sends: () => suggestCheck.checked ? "suggest" : "comment",
      sendBtn: composerSend,
      allowsMedia: () => suggestCheck.checked ? "Images can be added to comments, not replacement text" : true,
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
        const suggestion = suggestCheck.checked;
        const about = pendingAbout;
        const drawing = pendingDrawing && sentDrawing(structuredClone(pendingDrawing));
        const transition = threadTransitionOrigin?.(composerInput, fabFrameAt());
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
        if (shouldReveal || panelIsOpen()) {
          const destination = await revealSent({
            part: shouldReveal ? "thread" : "reply",
            focus: shouldReveal,
            travel: false,
            flash: false,
            intent: shouldReveal ? restrictUserIntent(currentIntent, revealAvailable) : currentIntent,
            transition
          });
          const thread = destination && closestAcross(destination, THREAD);
          if (shouldReveal && mayReveal() && thread)
            currentIntent.handoff(() => landSent(thread));
        }
      }
    });
    suggestCheck.onchange = () => setSuggestionMode(suggestCheck.checked);
    fabSuggest.onclick = () => setSuggestionMode(!suggestCheck.checked);
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
    ready: savedReadingSettled,
    keys: () => reactionTokens2().slice(0, 9).map((_, index) => String(index + 1)),
    label: () => {
      const count = Math.min(reactionTokens2().length, 9);
      return count > 1 ? `1\u2013${count}` : "1";
    },
    description: () => `Put a reaction on the response target: ${reactionTokens2().slice(0, 9).map(([name, entry], index) => `${index + 1} ${entry.glyph} ${name}`).join(", ")}`,
    title: "react",
    when: () => reactionAvailable2() && !takesLetters(focused()) && responseReactionButtons().length > 0,
    run: (binding) => responseReactionButtons()[+binding - 1]?.click()
  };
  const RESPONSE_MOVE = {
    id: "response.move",
    keys: ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"],
    description: "Move through other responses",
    title: "move",
    repeat: true,
    when: () => focusedResponseOption(),
    run: stepResponseOptions
  };
  const RESPONSE_ACTIVATE = {
    id: "response.activate",
    keys: PRESS,
    description: "Use the focused response",
    title: "choose",
    when: () => focusedResponseOption() && (!focused().classList.contains("lf-react") || reactionAvailable2()),
    run: () => focused()?.click()
  };
  const RESPONSE_CLOSE = {
    id: "response.close",
    keys: ["Escape"],
    description: "Close other responses",
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

// runtime/projection-watch.js
var presentations = 0;
var heard = /* @__PURE__ */ new Set();
document.addEventListener(PRESENTATION, () => {
  presentations += 1;
  const round = {};
  for (const moved2 of [...heard]) moved2(round);
});
var presented2 = outsideReading(
  () => presentations,
  (moved2) => {
    heard.add(moved2);
    return () => heard.delete(moved2);
  }
);
function watchProjection(owner, paint, ready = null) {
  let read2 = null;
  const moved2 = () => read2 === null || [...read2].some(([reading, value]) => reading.read() !== value);
  let key = 0;
  let queued = false;
  let subscribed = [];
  let unsubscribe = null;
  const update = () => {
    if (queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      if (!unsubscribe || !owner.isConnected) return;
      if (moved2()) key += 1;
      draw(key);
    });
  };
  const follow = () => {
    for (const stop2 of subscribed) stop2();
    subscribed = unsubscribe && read2 ? [...read2].map(
      ([reading, value]) => reading.subscribe((now) => now !== value && update())
    ) : [];
  };
  const draw = readingPaint(owner, () => {
    if (ready !== null && !ready()) return draw.forget();
    const outcome = collectReads(() => {
      presented2.read();
      return paint();
    });
    read2 = outcome.reads;
    follow();
    if ("error" in outcome) throw outcome.error;
    return outcome.value;
  });
  const stopLifetime = watchOwner(owner, {
    connect() {
      const stops = [];
      if (ready)
        stops.push(
          watchPresentation(() => (moved2() || draw.owes(key)) && ready() && update())
        );
      unsubscribe = () => {
        for (const stop2 of stops) stop2();
      };
      follow();
      update();
    },
    disconnect() {
      unsubscribe();
      unsubscribe = null;
      follow();
    }
  });
  const stop = () => {
    stopLifetime();
    draw.stop();
  };
  stop.refresh = () => draw.owes(key) && owner.isConnected ? draw(key) : draw.refresh();
  return stop;
}

// runtime/anchor-travel.js
var scrollingBoxFor = (element) => scrollersOf(element).next().value ?? null;
function scrollToFragment(element) {
  scrollIntoView(element, { behavior: "auto", block: "start" });
}
function createAnchorTravel({
  anchors,
  surfaces,
  currentThreads,
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
  async function arrive(resolve, { intent, present = null, keep = false, departure = null }) {
    const first = resolve();
    const holder = first && placeHolder(first.where);
    if (!holder || !intent()) return false;
    if (!keep) intent.handoff(() => surfaces.clearFor(holder));
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
          scroll: input ? [
            { at: input, block: "nearest" },
            {
              at: current.where,
              when: () => !readableDestination(current.where) || !readableDestination(input)
            }
          ] : [{ at: current.where }]
        };
      },
      {
        intent: mayArrive,
        departure,
        present: async () => {
          const current = resolve();
          if (!current) return;
          if (!readableDestination(current.where))
            mayArrive.handoff(() => {
              scrollIntoView(current.where, { behavior: "instant", block: "center" });
            });
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
  function prepareTrip({ landing = null, url, keep = false, intent }) {
    const write = prepareEntry();
    const continuing = landing && stillLanded();
    const arrival = landing && {
      landing,
      passage: () => openingPassage(landing())
    };
    let moving;
    return {
      plan(where, { there = (readable) => readable(where), required = [] } = {}) {
        if (where && !keep)
          intent.handoff(() => {
            for (const place of /* @__PURE__ */ new Set([where, ...required])) surfaces.clearFor(place);
          });
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
        write(
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
  async function navigateToDatum2(owner, attribute, key, { success = "", missing = "" } = {}) {
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
    const moving = departure.plan(destination);
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
        return where && { where, focus: where, scroll: moving ? [{ at: where }] : [] };
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
    const selected = surfaces.selectedSurface();
    const seen = clippedPlace(
      where,
      selected ? clipsPast([selected]) : /* @__PURE__ */ new Map(),
      destination
    );
    return seen && { holder, destination, seen };
  }
  function readableDestination(where) {
    const shown = seenOf(where);
    if (!shown) return false;
    const { holder, destination, seen } = shown;
    const box = scrollingBoxFor(holder);
    const band = box ? landingBand(box) : shownBox(pageScroller);
    const close = (a, b) => Math.abs(a - b) <= 0.5;
    return destination.top >= band.top - 0.5 && destination.bottom <= band.bottom + 0.5 && close(seen.top, destination.top) && close(seen.right, destination.right) && close(seen.bottom, destination.bottom) && close(seen.left, destination.left);
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
  async function scrollToThread(id, { part = null, focus = true, keep = false, presented: presented3 = null, intent } = {}) {
    const mayArrive = retainTravel(intent);
    const thread = threadNames(currentThreads()).get(id);
    const anchor = thread?.anchor;
    const status = anchors.placedAt(id)?.status;
    const hydrating = anchor?.datum && status !== "outdated" || anchor?.visual;
    const destination = threadDestination(id);
    const landing = () => threadDestination(id);
    const departure = prepareTrip({ landing, keep, intent: mayArrive });
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
          if (presented3) await presented3;
          if (mayArrive()) await refreshThread();
        },
        keep
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
var pairSources = (source, live, pairs) => {
  live = initialOrigin(source) === source ? live : initialOrigin(source);
  pairs.set(source, live);
  const held = source.localName === "template" ? source.content : source;
  const shown = live.localName === "template" ? live.content : live;
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
var versionsToWalk = () => versionCount() > 1;
var behindCurrent = () => runtime.active !== null && runtime.currentRevision !== null && !runtime.showsActive;
var shownBehind = () => runtime.currentStamp === null ? "An older draft" : runtime.active.version === null ? `v${runtime.currentStamp}` : `v${runtime.currentStamp} of ${runtime.active.version}`;
var versionsWalkable = false;
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
      token: `Showing ${currentVersionToken()}`,
      compared: diffOn || diffPendingBase !== null,
      news: behind,
      keyTitle: offered ? diffPendingBase !== null ? `${currentLabel}: loading a comparison with v${diffPendingBase}${newer}` : diffOn ? `${currentLabel}: showing what changed since v${diffBase} \u2014 pick a version, or press Compare again to stop${newer}` : `${currentLabel}: versions; read one, or mark what changed since it${newer}` : currentLabel,
      ariaLabel: offered ? diffPendingBase !== null ? `${currentLabel}: loading comparison with v${diffPendingBase}; open versions${newer}` : diffOn ? `${currentLabel}: comparing with v${diffBase}; open versions${newer}` : `${currentLabel}: open versions${newer}` : currentLabel
    }),
    latest: Object.freeze({
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
      base: diffPendingBase ?? (diffOn ? diffBase : null),
      currentRevision: runtime.currentRevision,
      on: diffOn,
      pendingBase: diffPendingBase,
      baseRevision: stamped(diffBase)?.revision ?? null
    })
  });
}
function paintPicker() {
  const model = pickerModel(runtime.state);
  versionPicker.present(model);
  showNews(latestChip, model.latest.news);
  repaint();
  const walkable = versionsToWalk();
  if (walkable !== versionsWalkable) {
    versionsWalkable = walkable;
    paintKeys();
  }
}
var pickerWatch = null;
var presentPicker = () => pickerWatch?.refresh();
var versionsReading = () => pickerModel(runtime.state);
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
var diffOn = false;
var diffBase = null;
var comparisonGeneration = 0;
var diffPendingBase = null;
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
      bindingAttrs.add(input.source);
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
      const { value } = askValue(now, verb, true);
      if (JSON.stringify(value) === JSON.stringify(askValue(before, verb, true).value))
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
    before === null ? `New since v${diffBase}` : `v${diffBase} \u2192 ${current}`
  );
  label.id = inlineId(target);
  label.setAttribute(
    "aria-label",
    before === null ? `New since version ${diffBase}` : `Inline comparison from version ${diffBase} to ${current}`
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
  return before === null ? `v${diffBase} had nothing here` : `showing an inline diff from v${diffBase}`;
}
function closeInlineComparison(target) {
  const entry = inlineOpen.get(target);
  inlineOpen.delete(target);
  target.classList.remove("lf-version-inline");
  for (const node of entry?.nodes ?? []) node.remove();
  paintInlineInsertions();
  layoutChanged(target);
  return `inline diff from v${diffBase} hidden`;
}
var inlineComparison = (target) => diffOn && diffBefore.has(target) && (diffBefore.get(target) === null || diffBefore.get(target) !== wrote(target)) ? {
  id: inlineId(target),
  open: inlineOpen.has(target),
  offer: `v${diffBase} \u2192 ${currentVersionToken()}`
} : null;
function toggleInlineComparison(target) {
  if (!inlineComparison(target)) return null;
  const said = inlineOpen.has(target) ? closeInlineComparison(target) : openInlineComparison(target);
  announceComparison();
  return said;
}
var comparable = (version) => {
  const base = stamped(version);
  return runtime.currentRevision !== null && base !== void 0 && base.revision < runtime.currentRevision;
};
function setDiff(on, base, pendingBase = null) {
  diffOn = on;
  diffPendingBase = pendingBase;
  if (on) diffBase = base;
  if (!on) {
    diffRequest++;
    for (const target of [...inlineOpen.keys()]) closeInlineComparison(target);
    diffBefore.clear();
    for (const b of diffMarked) b.classList.remove("lf-ins-block");
    diffMarked.clear();
  }
  presentPicker();
  announceComparison();
}
function announceComparison() {
  comparisonGeneration += 1;
  document.dispatchEvent(new CustomEvent("lf-comparison"));
}
async function showComparison(base) {
  setDiff(false, null, base);
  const mine = ++diffRequest;
  const baseVersion = stamped(base);
  const baseRevision = baseVersion?.revision;
  if (baseRevision == null) {
    diffPendingBase = null;
    presentPicker();
    notice(`Couldn't load v${base}`);
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
      diffPendingBase = null;
      presentPicker();
      notice(`Couldn't load v${base}`);
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
var pressComparison = (base) => diffOn && base === diffBase || diffPendingBase === base ? setDiff(false) : showComparison(base);
var comparisonBase = () => diffOn ? diffBase : null;
var selectedBase = () => diffPendingBase ?? comparisonBase();
function comparisonChanges(owner = null) {
  const changes = diffOn ? [...diffMarked] : [];
  return owner ? changes.filter((block) => block !== owner && under(block, owner)) : changes;
}
function watchComparison(owner, callback) {
  const paint = readingPaint(owner, () => callback());
  const read2 = () => paint(comparisonGeneration);
  const stop = whileConnected(owner, (signal) => {
    document.addEventListener("lf-comparison", read2, { signal });
    read2();
  });
  return () => {
    stop();
    paint.stop();
  };
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
  retireProjectionCoverage,
  syncLayout,
  captureRetainedStanding = () => null,
  restoreRetainedStanding = () => false,
  captureAskStanding = () => null,
  restoreAskStanding = () => {
  }
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
  const atVersionBoundary = (end) => versionPicker.atBoundary(end);
  const numberedVersionRoutes = () => versionPicker.numberedRoutes();
  const OPEN_NUMBER = {
    id: "version.open-number",
    keys: () => numberedVersionRoutes().map(({ binding }) => binding),
    routes: numberedVersionRoutes,
    label: () => {
      const routes = numberedVersionRoutes();
      return routes.length > 1 ? `${routes[0].binding}\u2013${routes.at(-1).binding}` : routes[0]?.binding;
    },
    description: "Open a numbered version",
    title: "open version",
    when: () => versionsToWalk() && numberedVersionRoutes().length > 0
    // The focused menu and its fixed picker delegate each numbered key to the
    // native row. Its view closes the menu and activates that exact entry once.
  };
  const NEWEST = {
    id: "version.current",
    keys: ["v"],
    title: "open the current page",
    // A stamped row is deliberately historical, including the newest one. This key names
    // the live page instead, sharing the same route as the arrival chip while the focused
    // row remains Enter's exact-version destination.
    run: () => goActive()
  };
  const [walk, edge] = rowWalk({
    id: "version",
    noun: "Version",
    plural: "versions",
    rows: () => versionPicker.rows(),
    steps: ["later", "earlier", "latest", "earliest"],
    // A press at either end lands on the row it started from and calls nothing here:
    // the walk states a comparison, so landing is not free — it would re-fetch the base
    // and say its count again for a press that moved nothing.
    //
    // The comparison the row states: its own version as the base, or none at all where
    // that version is not older than the one being read. So the user walks down to mark
    // from further back and back up to stop, and the row that stops it is the version
    // they are reading — the end of the walk in the direction they came from, which is
    // why it needs no key of its own and no user has to be told where it is — and,
    // the page having no key for a comparison, the whole of the way off one.
    landed: (row) => {
      const version = +row.dataset.lfVersion;
      if (comparable(version)) showComparison(version);
      else setDiff(false);
    }
  });
  const VERSION_WALK = {
    ...walk,
    description: "Walk the versions, marking what changed since the one shown",
    title: "walk \u2014 marking changes",
    when: versionsToWalk
  };
  const VERSION_EDGE = { ...edge, when: versionsToWalk };
  const VERSIONS = {
    title: "In the versions menu",
    ready: savedReadingSettled,
    root: () => versionMenu,
    when: versionsOffered,
    at: versionMenuIsOpen,
    // Opening the modal reference dismisses this popover. Retain the menu-boundary
    // reading so the reference documents its rows as unavailable in the remaining scene.
    liveInCommandReference: true,
    // A picker over the page suspends the page, which the two transient contexts above
    // this one always did and this one did not — so a user in the middle of choosing a
    // version could press `l` and take focus out of the menu into the leaves drawer, `d`
    // and scroll a page they were not looking at, or `c` and open the composer under the
    // list. None of it fails loudly: the press does exactly what it says on a page the
    // user has stopped reading. The worst of them was a page-level key that set a
    // comparison base, which the walk they were standing in then disagreed with — that
    // key is the menu's own business now, and the claim is what would have held it either
    // way. The claim is also what narrows the line to the menu's own keys, so what the
    // picker takes and what it offers are one statement rather than a suspension the
    // surfaces have to be told about separately.
    claims: allButCommandReference,
    rows: [
      VERSION_WALK,
      VERSION_EDGE,
      OPEN_NUMBER,
      // Two rows, both live at either end of a one-row menu, so the line prints both at
      // once — and while they shared a word it printed it twice, leaving the user to
      // tell them apart by their keycaps. The direction is the whole difference between
      // them and it is what each says.
      //
      // Their `when` reads where focus stands, which is a dispatch question: the press
      // closes the menu only from the end it is held to. The reference asks a different
      // one — does this scene offer the capability — and it asks it of a menu the modal
      // has just dismissed, so a position predicate answers no for both and the pair
      // would be the only rows in this scope the reference can never name. They say so
      // themselves, and the reference marks them unreachable the way it marks the
      // numbered destinations beside them.
      {
        id: "version.leave-forward",
        keys: ["Tab"],
        description: "Leave the versions menu forward",
        title: "leave forward",
        native: true,
        // A held Tab is still one continuous trip through the controls. When its repeated
        // keydown reaches the boundary, closing is part of that press just as it is for a
        // fresh Tab; only the platform's focus move remains native.
        repeat: true,
        when: () => atVersionBoundary(-1),
        commandReferenceWhen: () => true,
        run: closeVersionMenu
      },
      {
        id: "version.leave-backward",
        keys: ["Shift+Tab"],
        description: "Leave the versions menu backward",
        title: "leave backward",
        native: true,
        repeat: true,
        when: () => atVersionBoundary(0),
        commandReferenceWhen: () => true,
        run: closeVersionMenu
      },
      // The menu is a layer over the page and its parent is the page, so the one press
      // that closes it lands the user back there rather than on the picker in the
      // banner, which is chrome they may never have stood on: `g V` runs the press from
      // the picker, and the browser would hand focus back to it. Leaf performs the whole
      // result — close, then land — so the press is not the platform's to complete.
      {
        id: "version.close",
        keys: ["Escape"],
        description: "Close the versions menu",
        title: "close",
        // Exact travel is the menu's unfamiliar action and keeps the compact line's
        // second slot from either door. Escape remains live and stays in the complete
        // reference as the platform-standard close.
        promoteEscape: false,
        run: () => closeLayer(closeVersionMenu, () => returnToBannerControl(versionBtn))
      }
    ]
  };
  const PICKER = {
    id: "version.open",
    ready: savedReadingSettled,
    keys: ["Shift+v"],
    description: "The versions, and what each one changed",
    title: "versions",
    control: versionBtn,
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
      closeVersionMenu();
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
    for (const node of authoredHeadNodes) node.remove();
    const next = /* @__PURE__ */ new Set();
    for (const node of doc.head.children) {
      if (!versionedHeadNode(node)) continue;
      const imported = document.importNode(node, true);
      if (imported.localName === "link" || imported.localName === "style")
        imported.addEventListener("load", keepPageRulesOffLayer, { once: true });
      document.head.append(imported);
      next.add(imported);
    }
    authoredHeadNodes = next;
    let marker = document.querySelector('meta[name="lf-revision"][data-lf-runtime]');
    if (!marker) {
      marker = document.createElement("meta");
      marker.name = "lf-revision";
      marker.dataset.lfRuntime = "1";
      document.head.append(marker);
    }
    marker.content = String(revision.revision);
  }
  const upgraded = (element) => Boolean(registry[element.localName]?.["x-upgrade"]);
  function widgetKeys(source) {
    const keys2 = /* @__PURE__ */ new Map();
    const counts = /* @__PURE__ */ new Map();
    for (const element of elementsWithin(source)) {
      if (!upgraded(element)) continue;
      if (element.id) keys2.set(element, element.id);
      else {
        const seen = counts.get(element.localName) ?? 0;
        counts.set(element.localName, seen + 1);
        keys2.set(element, `${element.localName}#${seen}`);
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
      // Ask standing is the fallback for unnamed controls. An exact editor already
      // has a replacement identity, so its parent ask does not also own focus.
      askStanding: draftEditing ? null : captureAskStanding()
    };
  }
  async function landContinuity(land2) {
    try {
      await land2();
    } catch (error) {
      reportPageError(error, `Revision continuity failed`);
    }
  }
  async function restoreEditingContinuity(continuity, currentIntent) {
    if (!currentIntent()) return;
    const { draftEditing, replyThread, replyInView, askStanding } = continuity;
    restoreAskStanding(askStanding);
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
    const editingContinuity = captureEditingContinuity();
    const comparedFrom = selectedBase();
    if (comparedFrom !== null) setDiff(false);
    const live = pageDocument();
    const carry = captureCarry(live, authoredSource);
    const source = pageDocument(doc);
    const arrivingWidgets = documentWidgetDigests(doc);
    const arrivingRoot = layerRoot(doc);
    const rules = patchRules(doc);
    retireProjectionCoverage();
    revisionDocuments.delete(target.revision);
    const isAuthored = authored(live);
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
    await patchDocument(live, () => {
      authoredHtmlAttributes = replaceAuthoredAttributes(
        document.documentElement,
        doc.documentElement,
        authoredHtmlAttributes
      );
      for (const name of ["data-lf-review", "data-lf-layout"])
        keeps(document.documentElement, name, doc.documentElement.getAttribute(name));
      authoredBodyAttributes = replaceAuthoredAttributes(
        document.body,
        doc.body,
        authoredBodyAttributes
      );
      activateHead(doc, target);
      sourcePairs.set(source, live);
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
      reindexPassageOwners(live);
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
    const activates = (retains) => target.revision > runtime.currentRevision && !hasPending() && (!midComposition(retains) || forceActivation) && !versionMenuIsOpen();
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
        [...places].flatMap(
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
    const regions = new Map(readingRegions().map((region) => [region.id, region]));
    const active = regions.get(view.activeRegion) ?? containingReadingRegionFor(focusedInView()) ?? readingRegionFor(pageReadingBlock());
    if (active) reveal(active.host, currentIntent);
    const restored = /* @__PURE__ */ new Set();
    const activeReading = active && view.regions?.[active.id];
    const activeScroller = active && effectiveScroller(regions.get(active.id));
    if (activeReading && (hasLandmark(activeReading) || rawOffsetFits(activeReading, activeScroller) && activeScroller !== pageScroller)) {
      restorePlace(activeReading, regions.get(active.id), currentIntent);
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
      const region = regions.get(id);
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
  const places = /* @__PURE__ */ new Map();
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
      places.set(id, {
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
  const writing = /* @__PURE__ */ new WeakMap();
  const ownEnd = /* @__PURE__ */ new WeakMap();
  const wrote2 = (box, from) => {
    if (box.scrollTop !== from) writing.set(box, inputCount());
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
    for (const map of [places, subjectPlaces])
      for (const id of map.keys()) if (id !== PAGE && !present.has(id)) map.delete(id);
  };
  function recordPlaces(boxes, { standing: standing2 = false } = {}) {
    if (shifting || compositionChanges.size || !regionsSettled()) return;
    dropGonePlaces();
    for (const box of boxes) {
      const region = regionForBox(box);
      if (region === void 0 || held(box)) continue;
      if (region && !(under(region.host, pageDocument()) && shownRegionBounds(region)))
        continue;
      const before = places.get(region ? region.id : PAGE);
      const acted = standing2 || readerChose(box, before?.choices ?? 0) || inputSince(box, before?.inputs ?? 0);
      if (before && !acted) continue;
      const reading = capturePlace(region);
      places.set(reading.scroller, {
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
      const place = places.get(region.id);
      if (!place) return;
      if (!subjectPlaces.has(region.id)) subjectPlaces.set(region.id, /* @__PURE__ */ new Map());
      subjectPlaces.get(region.id).set(region.subject, place.reading);
      return;
    }
    holds.delete(region.id);
    const reading = subjectPlaces.get(region.id)?.get(region.subject);
    if (!reading) {
      places.delete(region.id);
      return;
    }
    places.set(region.id, {
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
      const recorded = new Map(places);
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
      const reading = change.captured.get(region2.id) ?? places.get(region2.id)?.reading;
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
    const rest = (seen) => nextRender(() => {
      if (seen !== scrolls) return rest(scrolls);
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
        if (writing.has(box)) {
          if (!inputSince(box, writing.get(box))) ownEnd.set(box, scrollChoices());
          writing.delete(box);
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
      latest: goActive,
      toggle: repaint
    });
    keys(
      versionMenu,
      "In the versions menu",
      [
        VERSION_WALK,
        VERSION_EDGE,
        OPEN_NUMBER,
        // The browser's own, the row being a real <button> — no `run`, or the press would
        // click a control the platform has already activated. The word is the line's all the
        // same, and the keys are the shared fact rather than this row's reading of it:
        // spelled by hand, it said Enter and left Space unnamed on a control that answers
        // both.
        {
          id: "version.activate",
          keys: PRESS,
          title: "open that version"
        },
        NEWEST
      ],
      { when: versionsToWalk, ready: savedReadingSettled }
    );
    pickerWatch = watchProjection(document.body, paintPicker);
    presentPicker();
  }
  function paintShortcuts() {
    keeps(
      latestChip,
      "title",
      `${latestChip.dataset.lfKeyTitle} (${commandShortcut(PICKER.id)} ${labelOf(NEWEST)})`
    );
  }
  pageScope("versions", VERSIONS);
  return {
    PICKER,
    paintShortcuts,
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
  return place?.isConnected ? place : null;
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
function headingFor(place, outline) {
  let above = null;
  for (const heading of outline) {
    if (renderedUnder(heading, place)) return heading;
    if (renderedOrder(heading, place) < 0) above = heading;
    else break;
  }
  return above;
}
var headings = /* @__PURE__ */ new WeakMap();
function threadSection(t, outline, placedAt) {
  const place = threadPlace(t, placedAt);
  const unplaced = Boolean((t.detached_from || t.anchor) && !placedAt(t.id));
  let kept = headings.get(t);
  if (!kept || kept.place !== place || kept.outline !== outline) {
    kept = {
      place,
      outline,
      heading: place && !inChrome(place) ? headingFor(place, outline) : null
    };
    headings.set(t, kept);
  }
  return Object.freeze({
    unplaced,
    section: kept.heading ? subjectLabel(kept.heading) : ""
  });
}
var lastMoved = (thread, now) => {
  const latest = threadSummary(thread).latest;
  return latest ? Date.parse(latest) : now;
};
function inRecentOrder(threads) {
  const now = serverNow();
  const seat = new Map(threads.map((t, i) => [t, i]));
  const moved2 = new Map(threads.map((t) => [t, lastMoved(t, now)]));
  return [...threads].sort(
    (a, b) => moved2.get(b) - moved2.get(a) || seat.get(a) - seat.get(b)
  );
}

// runtime/annotation-inventory.js
var annotationSelection = (root) => ({
  projection: root.effective.projection,
  asks: root.effective.asks,
  workflows: root.effective.workflows,
  revision: root.document.revision,
  todos: root.authoritative?.browser.todos ?? null
});
function createAnnotationInventory({
  readAsks: readAsks2,
  placedAt,
  openThread,
  goToAsk,
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
  const pointName = (words2) => {
    const excerpt = words2 && excerptWords(words2, 32);
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
    const slot = pointed ? `point:${pointed.key}` : target;
    let group = groups.get(slot);
    if (!group) {
      const key = pointed ? `${targetPath(target)}@${pointed.key}` : targetPath(target);
      const word = addressableWord(target);
      group = {
        key,
        target,
        point: pointed?.element ?? null,
        pointWords: pointed?.words ?? null,
        word,
        subject: null,
        title: null,
        items: [],
        offers: []
      };
      groups.set(slot, group);
    }
    return group;
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
      kind: receipt.next_actor === "user" || receipt.condition ? "waiting" : receipt.at_work ? "activity" : receipt.stage === "picked_up" ? "pickup" : receipt.stage === "queued" ? "queued" : "sent",
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
      const attention = threadAttention(thread);
      const onUser = attention?.kind === "needs_user";
      const unread = thread.unread.length;
      const placement = placedAt(id);
      const point = livePoint(target, placement?.point);
      const pointed = point ? { key: placement.pointRow, element: point, words: placement.pointWords } : null;
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
          text: labelWords(
            thread.root.text || anchorLabel(thread.anchor, thread.root.about)
          ),
          thread,
          // The Thread record already combines server attention with the local workflow
          // overlay. Margin and Page Map carry that reading rather than deriving another
          // answer from raw turn or workflow fields.
          userAttention: onUser ? {
            label: attention.label,
            reason: thread.attention?.reason ?? "workflow"
          } : null,
          unread,
          // Page Map lists each thread on its own row, so the word goes on the row
          // rather than on an aggregate.
          ...onUser || thread.attention?.reason === "todo" ? { mapContext: attention.label } : unread ? { mapContext: `${unread} unread` } : {},
          // Work decorates the thread control; it never replaces the control's
          // comment face or its disclosure action.
          workflowReceipt: onUser ? null : attention?.workflow,
          activate: () => openThread(id)
        },
        pointed
      );
    }
    for (const ask of readAsks2().user) {
      const id = ask.id;
      const target = askPlace(ask).node;
      if (!target) continue;
      add(groups, target, {
        kind: "ask",
        id: `ask:${id}`,
        // The group this row stands in already names the ask; the row says why it is
        // there, since these are the asks the user owes.
        text: "Waiting on me",
        // The marker's own label is the question, which says more than the kind its
        // glyph already shows.
        label: addressableLabel(target) || null,
        activate: () => {
          const asks = readAsks2().user.filter((ask2) => ask2.source.kind === "widget");
          const next = asks.find((candidate) => candidate.id === id);
          if (next) goToAsk(next, asks);
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
        // margin entry's relation, to the shortcut bar's word for the press, and to the
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
      if (todo.owner !== "agent" || todo.subject.kind !== "widget" && todo.subject.kind !== "element" || todo.revision > runtime.currentRevision)
        continue;
      if (activityAlreadyShown.has(`widget:${todo.subject.id}`)) continue;
      const target = elementById(todo.subject.id);
      const { running } = todo;
      const label = running ? "Working" : "To-do open";
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
    entries = marginInventory(
      collected.sort(
        (left, right) => comesBefore(left.point ?? left.target, right.point ?? right.target)
      ).map((group) => {
        const subject = outlineSubjectFor(group.target, subjects, outline);
        targets.set(group.key, group.target);
        if (group.point) points.set(group.key, group.point);
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
  function registerReactSurface(surface, { palette, target, trigger }) {
    surfaces.set(surface, { palette, target, trigger });
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
          className: `lf-react ${HOLDS_WORD}`,
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
            notice("That reaction target is no longer available");
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
        const seen = (trigger) => seenRect(trigger, clipsPastSurfaces());
        reactDeparture = whenNone([picker.trigger], seen, () => {
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
  const reactTargetWord = () => reactSurface === marginSurface ? anchorWord(marginAnchor) : typeof pickerFor(reactSurface)?.target === "function" ? pickerFor(reactSurface).target() : pickerFor(reactSurface)?.target ?? "the target";
  const REACT = {
    title: "With reactions open",
    ready: savedReadingSettled,
    escape: "inner",
    // Opening the modal reference dismisses this transient mode. Its section still reads
    // the liveness captured at that boundary rather than listing every conditional choice.
    liveInCommandReference: true,
    at: () => reactArmed,
    // The open list is where the mode stands, so a surface covering the page keeps it
    // when the list is inside that surface: a reply's strip in a covering Threads panel
    // lost every row to the panel's floor, and the stray key closed the list. The
    // margin's list has no node of its own and stands wherever its entry does.
    root: () => reactSurface instanceof Element ? reactSurface : document,
    claims: allButCommandReference,
    rows: [
      {
        id: "reaction.choose",
        runFromCommandReference: false,
        keys: () => reactionTokens().slice(0, 9).map((_, i) => String(i + 1)),
        label: () => {
          const n = Math.min(reactionTokens().length, 9);
          return n > 1 ? `1\u2013${n}` : "1";
        },
        description: () => `Put a reaction on ${reactTargetWord()}: ${reactionTokens().slice(0, 9).map(([name, entry], i) => `${i + 1} ${entry.glyph} ${name}`).join(", ")}`,
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
        runFromCommandReference: false,
        keys: ["Tab", "Shift+Tab", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"],
        description: "Move through reactions",
        title: "move",
        repeat: true,
        run: stepResponse
      },
      {
        id: "response.activate",
        runFromCommandReference: false,
        keys: PRESS,
        description: "Use the focused response",
        title: "choose",
        when: () => responseChoices(reactSurface).includes(focused()),
        run: () => focused()?.click()
      },
      {
        id: "reaction.cancel",
        keys: ["Escape"],
        description: "Close response choices",
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
    watchProjection(document.body, () => {
      margin();
      if (reactArmed && reactSurface === marginSurface && (!marginTarget?.isConnected || fabTargetAt() !== marginTarget))
        setReact(false);
      else if (reactArmed && reactSurface === marginSurface) marginOffer?.update();
    });
  }
  pageScope("reactions", REACT);
  pageCommand({
    id: "reaction.open",
    ready: savedReadingSettled,
    touch: false,
    keys: ["e"],
    description: () => `Open reactions \u2014 ${reactionTokens().slice(0, 9).map(([name, entry]) => `${entry.glyph} ${name}`).join(", ")} \u2014 for the selection, the focused item, or the open reply`,
    title: "reactions",
    // Reachable from a reply in a Threads panel covering the page, as `c` is; under a
    // covering surface the page's own targets are out of reach.
    covering: true,
    when: () => reactionAvailable() && reactionTokens().length > 0 && (coveringAuxiliarySurface() ? reactionTarget()?.kind === "surface" : hasReactionTarget()) && (anchoringIsReady() || !pageSelection()),
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
var undoSentence = (undoable) => {
  const event = undoable();
  return event?.token ? `Undo: ${event.token} reaction on ${reactionPlace(event)}` : "Undo the latest update";
};

// runtime/queue-api.js
var queueItemKey = (item) => JSON.stringify([item.kind, item.id]);
var readQueues = readPart((root) => root.effective.queues);
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
    if (offlineInteractive) return offlineState();
    const signal = globalThis.AbortSignal.timeout(bound);
    let res;
    try {
      res = await fetch(pageUrl("api/state"), {
        headers: layerHeaders(),
        // Coalescing bounds concurrency; this bounds its other dimension. A proxy that
        // never answers cannot own the page's single read slot forever.
        signal
      });
    } catch {
      return null;
    }
    if (!admitResponse(res)) return null;
    if (!res.ok) return null;
    try {
      return await res.json();
    } catch (error) {
      if (signal.aborted) return null;
      throw error;
    }
  } finally {
    countTraffic("heard");
  }
}
function buffer(bound) {
  return readState(bound).then(
    (state) => ({ state }),
    (error) => ({ error })
  );
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
  async function readNothing() {
    readAnswered = false;
    if (runtime.statePhase === "waiting") applicationState.setPhase("offline");
    applicationState.setReach(runtime.keyRefused ? "refused" : "unreachable");
    await invalidateDom2();
    await tick();
  }
  async function readAndApply(read2 = buffer(STATE_READ_TIMEOUT_MS)) {
    const answer = await read2;
    if ("error" in answer) throw answer.error;
    const { state } = answer;
    if (!state) {
      await readNothing();
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
      ask();
    };
    const feedQuiet = () => !reading && !applyingReads && !stateApplying();
    const askOnce = async () => {
      const returned = readingReturn();
      try {
        const state = await readState(STATE_READ_TIMEOUT_MS);
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
          void readNothing().then(async () => {
            await present();
            if (!applyingReads && !stateApplying()) completeReadingReturn(returned);
          }).catch(failed);
        }
      } catch (error) {
        failed(error);
      }
    };
    const ask = () => {
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
            if (observed !== freshness && observed !== runtime.reading) ask();
            else if (returned !== null && observed === runtime.reading && feedQuiet()) {
              await invalidateDom2();
              await present();
              if (feedQuiet()) completeReadingReturn(returned);
            }
            freshness = observed;
          }
        } catch {
          if (listening !== interval) return;
          ask();
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
          void ask();
        else if (readAnswered) void heartbeat();
        else void ask();
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
      const left = applicationState.present(receipts);
      for (const receipt of receipts)
        if (receipt.attempt) handles.get(receipt.attempt)?.resolveRead(receipt);
      return left.length > 0;
    },
    /** @param {DeliveryHandle} entry */
    nameEvents(entry) {
      return applicationState.nameEvents(entry.event.attempt);
    }
  };
}

// runtime/pending/dispatch.js
function createCommandDispatch() {
  const ledger = createPendingLedger({
    newAttempt: randomId,
    enqueue: (event) => applicationState.enqueue(
      event,
      saidNow(),
      isThreadEvent(event) ? messageText(event) : void 0
    )
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
    return entry.answer;
  };
  const post2 = (event) => startPost(event) ?? Promise.resolve(null);
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
    return startPost(actionForWidget(descriptor, command, revision));
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
var readEventAnswer = (response, answer) => response.ok && answer?.ok === true && answer.state ? "accepted" : answer?.final === true ? "refused" : "incomplete";
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
    let announced = false;
    const retry = async (message) => {
      if (!announced) notice(message);
      announced = true;
      await retryPause();
    };
    for (; ; ) {
      if (!ledger.nameEvents(entry)) return { accepted: null };
      const { event } = entry;
      if (entry.admitted) return { accepted: entry.admitted };
      const sent = await Promise.race([
        postEvent(event).then(
          (response) => ({ response }),
          (error) => ({ error })
        ),
        entry.read.then((accepted2) => ({ accepted: accepted2 }))
      ]);
      if (sent.accepted) return { accepted: sent.accepted };
      if (sent.error) {
        await retry(
          runtime.keyRefused ? "Key refused \u2014 open Leaf's link in a new tab and the change will send" : "Connection lost \u2014 retrying the change\u2026"
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
        entry.read.then((accepted2) => ({ accepted: accepted2 }))
      ]);
      if (decoded.accepted) return { accepted: decoded.accepted };
      if (decoded.error) {
        await retry("Couldn't read the answer \u2014 retrying the change\u2026");
        continue;
      }
      const answer = decoded.answer;
      const reading = readEventAnswer(sent.response, answer);
      const accepted = reading === "accepted" && answer.state.browser?.receipts?.find(
        (candidate) => candidate.attempt === event.attempt
      );
      if (accepted)
        return {
          accepted,
          application: applyAnswerState(applyAcceptedState, answer.state)
        };
      if (reading === "refused" && (!("attempt" in answer) || answer.attempt === event.attempt) && answer.ok === false) {
        return {
          accepted: null,
          state: answer.state,
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
                  const kept = refusedWords(refused.map(({ attempt }) => attempt));
                  notice(kept ? `${refusal}. ${kept}` : refusal);
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
  let response;
  try {
    response = await postEvent(event);
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
  const reading = readEventAnswer(response, answer);
  if (answer?.state) await applyAnswerState(applyState, answer.state);
  return reading === "incomplete" ? "unreached" : reading;
}

// runtime/undo.js
var WAIT = "Wait for the current change to finish before undoing";
var words = {
  resolve: "Reopened the thread",
  unresolve: "Resolved the thread again",
  action: "Undid the latest update",
  done: "Undid the approval",
  todo_end: "Put the to-do back on me"
};
function createUndo({ post: post2, stateApplying, unaccountedGesture }) {
  const reversals = /* @__PURE__ */ new Map();
  function retainReversal(attempt, reverse) {
    const { effective, unresolved } = readApplication();
    if (effective.view) {
      const liveAttempts = /* @__PURE__ */ new Set([
        ...effective.view.undo.map(({ event }) => event.attempt),
        ...unresolved.map((entry) => entry.event.attempt)
      ]);
      for (const kept of reversals.keys())
        if (!liveAttempts.has(kept)) reversals.delete(kept);
    }
    reversals.set(attempt, reverse);
  }
  function undoable() {
    if (stateApplying()) return null;
    const head = runtime.undo[0];
    return head?.newest ? head.event : null;
  }
  function withdrawable(event) {
    if (event.kind !== "action" && String(event.id).startsWith(PENDING)) return false;
    return !applicationState.unpresented().some(
      (entry) => entry.event.kind === "action" && (entry.admitted?.id ?? entry.localId) !== event.id
    );
  }
  function withdraw(event) {
    if (!withdrawable(event)) {
      notice(WAIT);
      return null;
    }
    const reverse = reversals.get(event.attempt);
    const mayLand = retainUserIntent();
    const answer = post2({ kind: "undo", undoes: event.id }).then((accepted) => {
      if (accepted)
        notice(
          `${event.token ? `Undid the ${event.token} reaction` : words[event.kind]} \u2014 sent`
        );
      return accepted;
    });
    if (reverse)
      void answer.then(async (accepted) => {
        if (!accepted) return;
        reversals.delete(event.attempt);
        await whenDocumentPresented();
        await reverse(mayLand);
      }).catch(() => {
      });
    return answer;
  }
  function undoLast() {
    if (stateApplying() || unaccountedGesture()) {
      notice(WAIT);
      return null;
    }
    const event = undoable();
    return event ? withdraw(event) : null;
  }
  pageCommand({
    id: "history.undo",
    ready: savedReadingSettled,
    keys: ["z"],
    description: () => undoSentence(undoable),
    title: "undo",
    touch: "Undo",
    menu: "page",
    // Dead while the page holds a gesture no log read accounts for, this one's own send
    // included. The line drops the chip for as long as that is true rather than
    // promising a press that would undo the wrong thing.
    when: () => !unaccountedGesture() && Boolean(undoable()),
    run: (...args) => undoLast(...args)
  });
  return {
    retainReversal,
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
    if (snapshot === void 0 && Object.values(declaredInputs).some(({ source }) => root.hasAttribute(source)))
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
  const panels = /* @__PURE__ */ new Set();
  let mounted = false;
  let primary = null;
  const presenter = applicationPresenter({
    region: "thread",
    order: PRESENTATION_ORDER.thread,
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
    let prepared = null;
    const livePanels = [...panels].filter((panel) => panel.threadsBox.isConnected);
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
        prepared = Promise.all(
          livePanels.map(
            ({ controller, view }) => controller.renderThreads(collection, view, resume)
          )
        );
        void prepared.catch(() => {
        });
        renderSeats(listed, inlineView);
        return Promise.race([
          Promise.all([
            surfaces.completion,
            prepared.then((candidates) => {
              if (current() && primaryCandidate?.current())
                return primaryCandidate.paint().then(() => candidates);
              return candidates;
            })
          ]),
          cancelled.then(() => null)
        ]).then(
          resume((result) => {
            if (!result) return;
            const [, candidates] = result;
            if (!current()) return;
            for (const candidate of candidates) candidate?.commit();
            readTargets();
            surfaces.commit();
            commitThreadSeats(batch);
            surfaceView.composition.finishPlacement();
            untracked(renderAnnotations);
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
      await Promise.all(
        livePanels.map(async ({ controller, view }) => {
          if (!primary) return controller.restoreThreadList();
          controller.cancel();
          const fallback = await controller.renderThreads(readThreads(), view);
          if (current()) fallback?.commit();
        })
      );
      if (!current()) return;
      retainThreadSeats(batch);
      throw error;
    }
  }
  function onReveal({ threadsBox, view }, event) {
    const target = event.detail?.target;
    const thread = target && closestAcross(target, ".lf-thread");
    if (!thread) return;
    const id = thread.dataset.id;
    if (thread.hidden) {
      const { mayReveal } = event.detail;
      const revealed = view.narrowing.revealThread(id);
      if (revealed)
        event.detail.present(
          revealed.then(() => {
            if (mayReveal() && thread.isConnected) threadsBox.revealNavigation(id);
          })
        );
    } else threadsBox.revealNavigation(id);
  }
  function attach(panel) {
    const listener = (event) => onReveal(panel, event);
    panel.threadsBox.addEventListener("lf-reveal", listener);
    panel.detach = () => panel.threadsBox.removeEventListener("lf-reveal", listener);
  }
  function registerPanel({ controller, threadsBox, view }) {
    const panel = { controller, threadsBox, view, detach: () => {
    } };
    panels.add(panel);
    if (mounted) {
      attach(panel);
      void present();
    }
    return {
      update: present,
      unregister() {
        if (!panels.delete(panel)) return;
        panel.detach();
        controller.cancel();
        if (mounted) void present();
      }
    };
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
  function primaryOwnsMessage(message) {
    return primary?.ownsMessage(message) ?? false;
  }
  function mount() {
    mounted = true;
    for (const panel of panels) attach(panel);
  }
  return {
    mount,
    present,
    registerPanel,
    registerPrimary,
    primaryOwnsMessage
  };
}

// runtime/annotation-view.js
function createAnnotationView(owner, render, inventory, invalidate, retire) {
  if (!(owner instanceof Element))
    throw new TypeError("consumeAnnotations needs an Element owner");
  if (!owner.isConnected)
    throw new TypeError("An annotation view needs a connected owner");
  if (typeof render !== "function")
    throw new TypeError("consumeAnnotations needs a synchronous render callback");
  let active = true;
  let places = /* @__PURE__ */ new Map();
  let offers = /* @__PURE__ */ new Set();
  const stopSide = declareSide((node) => {
    for (const [row, entry] of places)
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
      const result = render(entries, {
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
      places = nextPlaces;
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
    places.clear();
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
  panelIsOpen,
  showThread,
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
  const threadHere = () => heldThread() ?? preview?.accompanied() ?? null;
  const threadAtStanding = () => {
    const held = heldThread();
    if (held) return held.dataset.thread ?? held.dataset.id;
    const active = focused();
    const ids = active ? threadIdsAt(active) : [];
    const shown = threadHere();
    const shownId = shown?.dataset.thread ?? shown?.dataset.id;
    if ((!active || active === document.body) && shownId) return shownId;
    return ids.includes(shownId) ? shownId : ids[0] ?? null;
  };
  const replyThreadAtStanding = () => {
    const id = threadAtStanding();
    const thread = allThreads().find((candidate) => candidate.id === id);
    return thread && replyAvailable(thread) ? id : null;
  };
  const threadFocusTarget = (id, { part = null } = {}) => part === "message" ? null : surfaceFocusTarget(id, { part }) ?? preview?.focusTarget(id, { part }) ?? null;
  async function openPageThread(id, {
    part = null,
    focus = true,
    travel: travel2 = true,
    flash = true,
    scroll = true,
    intent = retainUserIntent(),
    transition = null
  } = {}) {
    if (!intent()) return null;
    const trip = travel2 && scroll;
    const selected = presentation;
    if (selected?.owner.isConnected) {
      const thread = threadNames(readThreads().threads).get(id);
      if (!thread) return null;
      opening?.abort();
      const abort = new AbortController();
      opening = abort;
      const cancelled = aborted(abort.signal);
      const whileCurrent = (work) => Promise.race([work, cancelled]);
      const request = {
        message: part === "message" ? thread.msgs.find((message) => message.id === id)?.key ?? null : null,
        part,
        focus,
        signal: abort.signal,
        current: () => !abort.signal.aborted && presentation === selected && selected.owner.isConnected && (focus === false ? intent.available() : intent())
      };
      const mayPresent2 = () => !abort.signal.aborted && presentation === selected && selected.owner.isConnected && (focus === false ? intent.available() : intent());
      const arriving = restrictUserIntent(intent, mayPresent2);
      const departure = focus !== false && trip ? prepareTrip({
        landing: () => selected.reader.destination(thread.key, request),
        intent: arriving
      }) : null;
      showHeld(id);
      const result = selected.open(thread.key, request);
      const selectedLayout = result?.then ? await whileCurrent(result) : result;
      if (!mayPresent2()) return null;
      if (selectedLayout !== false) await whileCurrent(selected.reader.update());
      if (!mayPresent2()) return null;
      const destination = selectedLayout === false ? null : selected.reader.destination(thread.key, request);
      if (destination !== null) {
        if (!(destination instanceof Element) || !destination.isConnected || !renderedUnder(destination, selected.owner) || !selected.reader.ownsDestination(destination))
          throw new TypeError(
            "A Thread destination must be a retained part of its registered presentation"
          );
        if (focus === false) {
          await whileCurrent(reveal(destination, intent).ready);
          return mayPresent2() ? destination : null;
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
    const mayPresent = () => focus === false ? intent.available() : intent();
    if (!panelIsOpen() && part !== "message") {
      const localPart = part ?? "reply";
      const openSurface = async () => {
        if (preview) intent.handoff(preview.close);
        if (trip) {
          if (!await scrollToThread(id, { part: localPart, focus, intent }))
            return null;
        } else {
          await reveal(surfaceFocusTarget(id, { part: localPart }), intent).ready;
          const current = surfaceFocusTarget(id, { part: localPart });
          if (!current || !mayPresent() || focus !== false && !intent.handoff(() => {
            focusDestination(current, "move");
            if (scroll) scrollIntoView(current, { block: "nearest" });
          }))
            return null;
        }
        return surfaceFocusTarget(id, { part: localPart });
      };
      if (surfaceFocusTarget(id, { part: localPart })) return openSurface();
      if (showHeldThread(id) && surfaceFocusTarget(id, { part: localPart }))
        return openSurface();
      let opened = null;
      if (preview)
        intent.handoff(() => {
          opened = preview.open(id, { transition });
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
          const current = threadFocusTarget(id, { part });
          if (!current || !mayPresent() || focus !== false && !intent.handoff(() => {
            focusDestination(current, "move");
            if (scroll)
              scrollIntoView(current, {
                behavior: scrollBehavior(),
                block: "nearest"
              });
          }))
            return null;
        }
        return threadFocusTarget(id, { part });
      }
      const held = revealHeld([id]);
      if (held) {
        await held.presented;
        if (!mayPresent()) return null;
      }
      if (surfaceFocusTarget(id, { part: localPart })) return openSurface();
    }
    return showThread(id, { part: part ?? "reply", focus, flash, scroll, intent });
  }
  async function openThreadDraft(context, intent) {
    const thread = threadHolding(context);
    if (!thread) return null;
    if (context.startsWith("reply:"))
      return openPageThread(thread.id, { part: "reply", intent });
    const name = context.slice(context.indexOf(":") + 1);
    const landed = await openPageThread(name, { part: "message", intent });
    const card = landed && closestAcross(landed, THREAD);
    return card ? openMessageEditIn(card, name) : null;
  }
  function threadHolding(context) {
    const name = context.slice(context.indexOf(":") + 1);
    return context.startsWith("reply:") ? allThreads().find((each) => threadKey(each) === name) : allThreads().find((each) => each.msgs.some(({ id }) => id === name));
  }
  return {
    register,
    openPageThread,
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

// runtime/thread/mirrors.js
var registrations = /* @__PURE__ */ new WeakMap();
function registerMirrorConsumer(owner, render, { commands }) {
  if (registrations.has(owner))
    throw new Error(`mountThreadViews(${owner.localName}) registered twice`);
  let active = true;
  let generation = 0;
  let pending = null;
  let queued = false;
  let outlets = /* @__PURE__ */ new Set();
  const clear = () => {
    for (const outlet of outlets) {
      clearThreadMirrors(outlet);
      delete outlet.dataset.lfThreadSurface;
    }
    outlets = /* @__PURE__ */ new Set();
  };
  const report = (error) => reportPageError(error, `Thread mirrors in ${owner.localName}#${owner.id} failed`);
  async function reconcile() {
    const current = ++generation;
    pending?.abort();
    const abort = new AbortController();
    pending = abort;
    const cancelled = aborted(abort.signal);
    const collection = readThreads();
    const byKey = new Map(collection.threads.map((thread) => [thread.key, thread]));
    const selected = /* @__PURE__ */ new Map();
    let accepting = true;
    const mirrors = {
      signal: abort.signal,
      thread(key, outlet) {
        if (!accepting || abort.signal.aborted)
          throw new Error("Thread mirrors belong to their current render callback");
        const thread = byKey.get(key);
        if (!thread) throw new Error(`No Thread has key ${key}`);
        if ([...selected.values()].some((threads2) => threads2.includes(thread)))
          throw new Error("A consumer may render a Thread only once");
        const threads = selected.get(outlet) ?? [];
        threads.push(thread);
        selected.set(outlet, threads);
      }
    };
    try {
      const rendering = render(collection, mirrors);
      if (rendering?.then) await Promise.race([rendering, cancelled]);
      accepting = false;
      if (!active || current !== generation || abort.signal.aborted) return;
      if (!owner.isConnected) return;
      for (const outlet of selected.keys()) {
        if (!outlet.isConnected) selected.delete(outlet);
        else if (!under(outlet, owner))
          throw new Error(
            `mountThreadViews(${owner.localName}) returned an outlet outside its widget`
          );
      }
      for (const outlet of outlets)
        if (!selected.has(outlet)) {
          clearThreadMirrors(outlet);
          delete outlet.dataset.lfThreadSurface;
        }
      outlets = new Set(selected.keys());
      for (const [outlet, threads] of selected) {
        outlet.toggleAttribute("data-lf-thread-surface", true);
        renderThreadMirrors(outlet, threads, commands);
      }
    } catch (error) {
      if (!active || current !== generation || abort.signal.aborted) return;
      clear();
      report(error);
    } finally {
      accepting = false;
    }
  }
  const update = () => {
    if (!active || queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      if (active && owner.isConnected) void reconcile();
    });
  };
  const stop = watchProjection(owner, reconcile);
  const handle = Object.freeze({
    update,
    unregister() {
      if (!active) return;
      active = false;
      ++generation;
      pending?.abort();
      stop();
      registrations.delete(owner);
      clear();
    }
  });
  registrations.set(owner, handle);
  return handle;
}
function createPrimaryReader(owner, render, commands, update) {
  let active = true;
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
        newsMoves: ({ news, changed, folds }) => parts.some(
          (part) => (news.appended || news.settled || changed.has(part.messageKey) || folds.messages.includes(part.messageKey) || folds.summaries.length) && growthIsSeen(part.node)
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
            const order = shown.get(key)?.source.msgs.map((message) => message.key);
            return partsOf(key, "message").toSorted(
              (a, b) => (order?.indexOf(a.messageKey) ?? 0) - (order?.indexOf(b.messageKey) ?? 0)
            ).map((view) => view.message);
          },
          send: (id, text, options) => commands.reply.actions.edit(key, id, text, options),
          paint: (node) => partsOf(key, "message").find((view) => view.message.node === node)?.draw(),
          box: () => replyOf(key),
          home: (node) => node.closest(THREAD),
          opening: () => shown.get(key)?.news?.open(),
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
    pending?.abort();
    const abort = new AbortController();
    pending = abort;
    void cancelled.then(() => abort.abort());
    const candidate = held.prepare(
      {
        threads: collection.threads.map(
          (thread) => threadReading(thread, "outlet", { ...commands, nativeAuthored: true }, {})
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
      if (message !== null && !thread.msgs.some((item) => item.key === message))
        throw new Error(`Thread ${key} has no message ${message}`);
      const identity2 = JSON.stringify([kind, key, message]);
      if (nominations.some(
        (item) => item.identity === identity2 || item.key === key && (item.kind === "thread" || kind === "thread")
      ))
        throw new Error("A primary reader may nominate each Thread part only once");
      nominations.push({ identity: identity2, kind, key, message, outlet, thread, options });
    };
    const finish = () => {
      accepting = false;
      if (!active || current !== generation || abort.signal.aborted) return null;
      for (const item of nominations)
        if (!item.outlet.isConnected || !under(item.outlet, owner))
          throw new Error(
            "A primary Thread outlet must remain inside its connected owner"
          );
      selected = nominations;
      shown = new Map(candidate.reading.threads.map((thread) => [thread.key, thread]));
      nativeMessages.clear();
      for (const item of nominations)
        for (const message of item.thread.msgs)
          if (item.kind === "thread" || item.message === message.key)
            nativeMessages.add(message.id);
      return {
        paint: async () => {
          await paint(current);
          if (active && current === generation && !abort.signal.aborted)
            candidate.commit();
        },
        current: () => active && current === generation && !abort.signal.aborted
      };
    };
    try {
      const rendering = render(
        shownCollection,
        Object.freeze({
          signal: abort.signal,
          thread: (key, outlet) => nominate("thread", key, null, outlet),
          message: (key, id, outlet) => nominate("message", key, id, outlet),
          reply: (key, outlet, options) => nominate("reply", key, null, outlet, options)
        })
      );
      if (rendering?.then)
        return Promise.race([rendering, aborted(abort.signal)]).then(finish).finally(() => {
          accepting = false;
        });
      return finish();
    } catch (error) {
      accepting = false;
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
          view = new ThreadView("outlet", { ...commands, nativeAuthored: true });
        else {
          const node = document.createElement("div");
          node.className = "lf-page-thread lf-ui lf-primary-part";
          node.dataset.lfPart = item.kind;
          node.tabIndex = -1;
          node.dataset.lfRuntime = "";
          node.dataset.lfGen = "1";
          node.dataset.lfOffer = "";
          if (item.kind === "message") {
            const message = new MessageView({
              ...commands,
              edit: rewritesOf(item.key).edit
            });
            message.node.classList.add("lf-primary-message");
            node.append(message.node);
            view = {
              node,
              message,
              messageKey: item.message,
              reading: null,
              // Draws the message again at once, as its rewrite opens or closes.
              draw() {
                message.present(this.reading, { headerControls: this.notice.node });
                message.commit();
              },
              dispose: () => message.retire()
            };
          } else {
            let joined = false;
            const { hint, accessibleName, sent } = item.options;
            const reply = createReplyView(item.key, commands.reply, {
              onChange: () => {
                if (joined) void update().catch(() => {
                });
              },
              editLast: rewritesOf(item.key).editLast,
              hint,
              accessibleName,
              sent
            });
            joined = true;
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
      } else {
        keeps(view.node, "data-thread", item.thread.id);
        keeps(view.node, "data-attempt", item.thread.root.attempt ?? null);
        const news = shown.get(item.key)?.news;
        const first = selected.find((part) => part.key === item.key && part.kind === "message") ?? selected.find((part) => part.key === item.key);
        const notice2 = Boolean(news) && first === item;
        if (notice2) view.notice.set(news);
        keepsHidden(view.notice.node, !notice2);
        if (item.kind === "message") {
          const message = item.thread.msgs.find((entry) => entry.key === item.message);
          view.reading = messageReading(message, {
            panel: false,
            nativeAuthored: true,
            reactions: message.reactions,
            workflows: message.workflows
          });
          view.draw();
        } else {
          keepsHidden(view.node, !replyAvailable(item.thread));
          if (view.notice.node.parentNode !== view.node)
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
      const parts = destinations.get(item.key) ?? [];
      parts.push(view);
      destinations.set(item.key, parts);
    }
    for (const [parent, nodes] of children) orderChildren(parent, nodes);
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
function createReadTracking({ markRead, openThread, firstUnreadBtn }) {
  let coverage = /* @__PURE__ */ new WeakMap();
  const renderedBodies = /* @__PURE__ */ new Map();
  const refusedThisVisit = /* @__PURE__ */ new Set();
  const sizes = sizeObserver(() => scheduleScan());
  const frameWatches = [];
  const committedThreads = M(
    /** @type {ReturnType<typeof readThreads>["threads"]} */
    []
  );
  let threadsPresented = false;
  let presentationGeneration = 0;
  let visitGeneration = 0;
  let scheduled = false;
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
    const live = new Set(
      unreadIn(readThreads().threads).map(({ item }) => keyOf(item))
    );
    return unreadIn(committedThreads.value).filter(({ item }) => live.has(keyOf(item)));
  };
  function firstUnread() {
    const target = actionableUnread().sort(
      (a, b) => moved(a.message).seq - moved(b.message).seq
    )[0];
    if (target) void openThread(target.item.message, { part: "message" });
  }
  const firstUnreadCommand = {
    id: "thread.unread.first",
    ready: savedReadingSettled,
    keys: ["u"],
    description: "Go to the first unread message",
    title: "first unread",
    touch: false,
    covering: true,
    control: () => firstUnreadBtn,
    when: () => actionableUnread().length > 0,
    run: firstUnread
  };
  function scan(sampleBand) {
    if (!threadsPresented || document.visibilityState !== "visible" || !document.hasFocus())
      return;
    const band = sampleBand ?? containingView();
    if (!band || sampleBand?.visible === false) return;
    const candidates = new Map(
      actionableUnread().map(({ item }) => [item.message, item])
    );
    if (!candidates.size) return;
    const clips = /* @__PURE__ */ new Map();
    const completed = /* @__PURE__ */ new Map();
    for (const [node, rendered] of renderedBodies) {
      const { body, id, version } = rendered;
      if (!node.isConnected || !body.isConnected) {
        sizes.unobserve(body);
        renderedBodies.delete(node);
        continue;
      }
      const item = candidates.get(id);
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
    if (completed.size) {
      const items = [...completed.values()];
      const visit = visitGeneration;
      void markRead(items).then((outcome) => {
        if (outcome === "refused" && visit === visitGeneration)
          for (const item of items) refusedThisVisit.add(keyOf(item));
      });
    }
  }
  let exposureGeneration = 0;
  function scheduleScan() {
    exposureGeneration++;
    if (scheduled) return;
    scheduled = true;
    nextRender(() => {
      scheduled = false;
      if (!sampleVisibility()) return scan();
      const generation = exposureGeneration;
      void readSampleVisibility().then((reading) => {
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
    frameWatches.push(
      onSampleVisibility(() => {
        if (sampleVisibility()?.visible) scheduleScan();
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
  function observeMessage(body, message) {
    if (!(body instanceof Element))
      throw new TypeError("A message body must be an Element");
    if (!renderedBodies.has(body)) sizes.observe(body);
    const registration = {
      body,
      id: message.id,
      version: message.version
    };
    renderedBodies.set(body, registration);
    scheduleScan();
    return () => {
      if (renderedBodies.get(body) !== registration) return;
      sizes.unobserve(body);
      renderedBodies.delete(body);
    };
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
      const count = unread.length;
      keepsHidden(firstUnreadBtn, count === 0);
      keeps(
        firstUnreadBtn,
        "aria-label",
        `${count} unread ${count === 1 ? "message" : "messages"}. Go to first unread message`
      );
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
    const land2 = sendLanding(ta);
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
    if (sent) land2();
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
    page: view.document,
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
function userObligations(page, threadView) {
  const held = /* @__PURE__ */ new Map();
  for (const ask of page.asks.user)
    held.set(JSON.stringify(["page", ask.id]), {
      source: ask.id,
      thread: null
    });
  for (const ask of threadView.asks.user) {
    const version = ask.source.kind === "reply" ? ask.source.version : null;
    held.set(JSON.stringify(["thread", ask.thread, ask.id, version]), {
      source: ask.id,
      thread: ask.thread
    });
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
  const obligations = userObligations(reading.page, reading.thread);
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
  const obligations = userObligations(reading.page, reading.thread);
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
      message.edited ? `${agent} updated a ${verb}` : `${agent} ${verb === "reply" ? "replied" : "commented"}`
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
      obligations.length === 1 ? "Input needed" : `${plural(obligations.length, "item")} waiting on me`
    );
  if (availability.length) clauses.push(`${agentLabel()} active on this page`);
  return clauses.join("; ");
}

// runtime/state-application.js
function createStateApplication({
  prepareActivation,
  acceptData: acceptData2,
  notifyDataSubscribers: notifyDataSubscribers2,
  isSignoffDeclared,
  stateSignoff,
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
        stateSignoff(isSignoffDeclared());
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
        ["projection:chrome", "thread", "asks", "queue"],
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
  const projection = createProjectionPresentation();
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
    withdraw: (candidate) => undo.withdraw(candidate),
    onCollision: (attempt) => notice(`Couldn't send \u2014 attempt ${attempt} is already in use`)
  });
  const { post: post2 } = commandDispatch;
  const undo = createUndo({
    post: post2,
    stateApplying,
    unaccountedGesture: engagement.unaccountedGesture
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
    openThread: openPageThread,
    firstUnreadBtn: dependencies.firstUnreadBtn
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
    retainReversal: undo.retainReversal
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
  const cardView = {
    reply: replyView,
    settlement: settlementView,
    reaction: reactionView,
    read: read2,
    openThread: inlineView.openThread,
    anchors: {
      placedAt: dependencies.anchorPlacement.placedAt
    },
    travel: {
      scrollToThread: dependencies.anchorTravel.scrollToThread
    }
  };
  const surfaceView = {
    ...inlineView,
    composition: dependencies.compositionSurface
  };
  const annotations = createAnnotationInventory({
    readAsks,
    placedAt: dependencies.anchorPlacement.placedAt,
    openThread: openPageThread,
    goToAsk: dependencies.annotationCommands.goToAsk,
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
  const renderAnnotations = clocked(document.body, () => {
    if (!onPaper.matches) {
      const entries = refreshAnnotationInventory();
      overlay?.paint(entries);
    }
  });
  const annotationInputs = readPart(annotationSelection);
  const mountAnnotations = () => {
    watchProjection(
      document.body,
      () => {
        annotationInputs();
        renderAnnotations();
      },
      () => projectionRegionsPresented([])
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
    renderMarginThread: (host, thread, controls) => renderMarginThread(host, thread, inlineView, controls),
    placedAt: dependencies.anchorPlacement.placedAt,
    scrollToElement: dependencies.anchorTravel.scrollToElement
  });
  const threadDestinations = createThreadDestinations({
    threadIdsAt: annotations.threadIdsAt,
    placedAt: dependencies.anchorPlacement.placedAt,
    panelIsOpen: dependencies.panelIsOpen,
    showThread: dependencies.showThread,
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
    // stopped drawing: the surface drawing it, its margin card, or the panel.
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
  const registerThreadPanel = ({ controller, threadsBox, view }) => threadPresenter.registerPanel({
    controller,
    threadsBox,
    view: {
      ...view,
      card: {
        ...cardView,
        nativeAuthored: (message) => !threadPresenter.primaryOwnsMessage(message),
        travel: { ...cardView.travel, ...view.travel }
      },
      placedAt: dependencies.anchorPlacement.placedAt,
      repaintThread: refreshThread
    }
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
  const consumeAnnotations2 = (owner, render) => {
    requirePageAnnotations();
    if (annotationRegistration)
      throw new Error("The document already has a page annotation view");
    const registration = /* @__PURE__ */ Symbol("page annotation view");
    annotationRegistration = registration;
    const retire = () => {
      if (annotationRegistration === registration) annotationRegistration = null;
    };
    try {
      return createAnnotationView(owner, render, annotations, invalidateDom2, retire);
    } catch (error) {
      retire();
      throw error;
    }
  };
  const watchThreadSurfaces2 = () => watchThreadSurfaces(threadSurfaceCommands);
  const placePageThreads3 = (owner, render) => {
    requirePageAnnotations();
    return placePageThreads(owner, render, threadSurfaceCommands);
  };
  const mountThreadViews2 = (owner, render) => registerMirrorConsumer(owner, render, { commands: inlineView });
  const attachPresentation = (owner, { render, reveal: reveal3 }) => {
    const reader = createPrimaryReader(
      owner,
      render,
      inlineView,
      () => threadPresenter.present()
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
  const presentThreads = (owner, spec, yields) => {
    const entry = { owner, spec, attached: null };
    if (yields) {
      if (yielding)
        throw new Error("The page already has a yielding Thread presentation");
      yielding = entry;
      if (!authored2) entry.attached = attachPresentation(owner, spec);
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
      authored2 = entry;
      if (handOff)
        queueMicrotask(() => {
          if (authored2 === entry) handOff();
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
    mountThread: threadPresenter.mount,
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
    mountThreadViews: mountThreadViews2,
    registerThreadPanel,
    retireProjectionCoverage: projection.retireProjectionCoverage,
    threadActions: threadActions2,
    queueActions: queueActions2,
    openAsk(id) {
      const ask = readAsks().all.find((item) => item.id === id);
      if (!ask) return Promise.resolve(false);
      if (ask.source.kind === "approval")
        return queueActions2.open(JSON.stringify(["ask", ask.id]));
      if (ask.source.kind === "reply") {
        showHeld(ask.thread);
        return threadDestinations.openPageThread(ask.message, {
          part: "message"
        });
      }
      return dependencies.annotationCommands.goToAsk(ask, readAsks().all);
    },
    // The On me walk within one region (queue-walk.js), the walk an `lf-tally` steps.
    nextAsk: (options) => dependencies.nextAskWithin(options),
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
var mountThreadViews = (...args) => app().mountThreadViews(...args);
var registerThreadPresentation = (...args) => app().registerThreadPresentation(...args);
var threadActions = Object.freeze({
  open: (...args) => app().threadActions.open(...args),
  create: (...args) => app().threadActions.create(...args),
  reply: (...args) => app().threadActions.reply(...args),
  resolve: (...args) => app().threadActions.resolve(...args),
  reopen: (...args) => app().threadActions.reopen(...args),
  setReaction: (...args) => app().threadActions.setReaction(...args)
});
var askActions = Object.freeze({
  open: (...args) => app().openAsk(...args),
  next: (...args) => app().nextAsk(...args)
});
var queueActions = Object.freeze({
  open: (...args) => app().queueActions.open(...args),
  done: (...args) => app().queueActions.done(...args)
});
var wireInput = (...args) => app().wireInput(...args);

// runtime/thread/landing.js
var threadReturns = /* @__PURE__ */ new WeakMap();
var threadLandingStart = (held, target, threadsBox) => {
  if (!landingBand(threadsBox)) return null;
  const targetBox = shownBox(target);
  const last = target === held ? targetBox.bottom : targetBox.top;
  const transcript = held.querySelector(".lf-thread-transcript");
  const latest = target === held && transcript ? latestTurn(transcript) : null;
  const candidates = [
    ...held.querySelectorAll(
      ":scope > *, :scope > .lf-thread-content > *, .lf-thread-transcript .lf-msg .lf-msg-body > *, .lf-thread-transcript .lf-msg .lf-msg-text > *"
    ),
    target,
    ...latest ? [latest] : []
  ].filter((node) => node !== held).map((node) => ({ node, box: shownBox(node) })).filter(
    ({ node, box }) => node === target || node === latest || getComputedStyle(node).display !== "contents" && box.height > 0 && box.top <= last && targetBox.bottom - box.top <= landingRoom(node, target).height
  ).sort((a, b) => a.box.top - b.box.top);
  return candidates[0]?.node ?? null;
};
var landLatest = (thread, threadsBox, behavior = scrollBehavior()) => {
  const start = threadLandingStart(thread, thread, threadsBox);
  scrollIntoView(start ?? thread, { behavior, block: start ? "start" : "end" });
};
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
var boxHandsBack = () => Boolean(backFromBox()) || Boolean(focused(document)?.closest?.(".lf-thread-panel"));
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
      keys: ["Escape"],
      description: "Leave the box, keeping what is typed",
      title: () => backFromBox()?.line ?? "back to list",
      // The thread the box belongs to, or the panel's list from its own find box. A
      // page text box that is neither leaves the row dead and the page's rung in place,
      // which is the honest answer: nothing there to go back to.
      when: leavesBox,
      run: () => {
        const back = backFromBox();
        dismissReplyAt(focused());
        const panelList = focused(document)?.closest?.(".lf-thread-panel")?.querySelector(".lf-threads");
        deepFocus()?.blur();
        const target = back?.target ?? panelList;
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
  if (!fitsWhole(thread) && alreadyShown(thread)) {
    focusThread(thread, "return");
    return;
  }
  focusThread(thread, "move");
  scrollIntoView(threadFocusStop(thread), { block: "nearest" });
}
var cardThread = () => {
  const thread = focusedThreadTarget();
  return thread?.localName === "details" && !thread.open ? null : thread;
};
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
var retainPanelLanding = (source, panelIsOpen, threadsBox) => retainUserIntent({ source, available: panelIsOpen, fallback: threadsBox });
var standing = () => closestAcross(focused(), ".lf-thread");
var land = (thread, behavior, threadsBox, arriving = false) => {
  if (!thread || !threadsBox.contains(thread)) return;
  if (takesLetters(focused())) return;
  const place = () => {
    if (takesLetters(focused())) return;
    if (arriving && !fitsWhole(thread)) landLatest(thread, threadsBox, behavior);
    else scrollThreadIntoView(thread, focused(), behavior);
  };
  if (arriving || hasFolding(threadsBox)) {
    const mayLand = retainUserIntent({
      source: thread,
      available: () => thread.isConnected
    });
    const finish = bindQueuedWork(() => {
      if (mayLand() && standing() === thread) place();
    });
    void whenFolded(threadsBox).then(whenDocumentPresented).catch(() => {
    }).then(finish);
    return;
  }
  place();
};
var arrivingAtTitle = () => Boolean(focused()?.matches?.(".lf-thread-summary"));
var landWalkedThread = (thread, threadsBox) => land(thread, void 0, threadsBox, arrivingAtTitle());
function wireThreadLanding(threadsBox) {
  const pressedHere = () => pressing()?.path.includes(threadsBox) ?? false;
  let visibleTitle = null;
  const readVisibleTitle = () => {
    const title = focused();
    const band = landingBand(threadsBox);
    const box = title && shownBox(title);
    visibleTitle = title?.matches?.(".lf-thread-summary") && threadsBox.contains(title) && band && box.top >= band.top - 1 && box.bottom <= band.bottom + 1 ? title : null;
  };
  threadsBox.addEventListener("scroll", readVisibleTitle);
  addEventListener("resize", () => {
    const title = visibleTitle;
    const mayLand = retainUserIntent({ source: title });
    nextRender(() => {
      const thread = standing();
      if (title && mayLand() && focused() === title && thread && threadsBox.contains(thread))
        scrollThreadIntoView(thread, title, "instant");
      readVisibleTitle();
    });
  });
  onPress((start, path) => {
    if (!path.includes(threadsBox)) return null;
    const pressedThread = start.target.closest?.(".lf-thread") ?? null;
    return (end, completed) => {
      if (!completed) return;
      const thread = standing() ?? pressedThread;
      if (thread && !reachedForWords(thread)) {
        if (standing() !== thread) focusThread(thread, "move");
        land(thread, "instant", threadsBox);
      }
    };
  });
  onStanding((node, cause) => {
    if (!node || !under(node, threadsBox)) return;
    nextRender(readVisibleTitle);
    if (pressedHere() || cause === "return") return;
    const thread = standing();
    if (thread) land(thread, void 0, threadsBox, arrivingAtTitle());
  });
}
var listNode = (id, threadsBox, preferMessage = false) => {
  const threadId = threadNames(allThreads()).get(id)?.id ?? id;
  const message = `.lf-msg[data-mid="${CSS.escape(id)}"]`;
  const thread = `.lf-thread[data-id="${CSS.escape(threadId)}"]`;
  const node = preferMessage || id !== threadId ? threadsBox.querySelector(message) ?? threadsBox.querySelector(thread) : threadsBox.querySelector(thread) ?? threadsBox.querySelector(message);
  return node?.closest(".lf-thread[hidden]") ? null : node;
};
async function showThreadNow(id, part, focus, flash, revealThread, threadsBox, mayArrive, scroll) {
  const mayPresent = () => focus === false ? mayArrive.available() : mayArrive();
  const revealDestination = bindQueuedWork(() => {
    const node2 = listNode(id, threadsBox, part === "message");
    const going = node2?.closest(".lf-going");
    if (node2 && !going && !threadsBox.keepsForWords(id)) return { node: node2 };
    if (!mayArrive()) return null;
    if (going) finishFold(going);
    const ready = revealThread(threadNames(allThreads()).get(id)?.id ?? id);
    return ready ? { ready } : null;
  });
  threadsBox.querySelector(
    `.lf-thread[data-id="${CSS.escape(threadNames(allThreads()).get(id)?.id ?? id)}"], .lf-msg[data-mid="${CSS.escape(id)}"]`
  )?.classList.toggle("grow", false);
  threadsBox.revealNavigation(threadNames(allThreads()).get(id)?.id ?? id);
  const destination = revealDestination();
  if (!destination) return null;
  let node = destination.node;
  if (destination.ready) {
    await destination.ready;
    if (!mayPresent()) return null;
    node = listNode(id, threadsBox, part === "message");
  }
  if (mayArrive())
    threadsBox.revealNavigation(threadNames(allThreads()).get(id)?.id ?? id);
  node = listNode(id, threadsBox, part === "message");
  if (!node || !mayPresent()) return null;
  if (node.closest(".lf-summary-originals[hidden]")) {
    if (!mayArrive()) return null;
    await reveal(node, mayArrive).ready;
    if (!mayPresent()) return null;
  }
  await whenDocumentPresented().catch(() => {
  });
  node = listNode(id, threadsBox, part === "message");
  if (!node || !mayPresent()) return null;
  const thread = node.closest(".lf-thread");
  if (focus) {
    const destination2 = node === thread ? threadFocusDestination(thread, { part }) : node;
    mayArrive.handoff(() => {
      if (destination2 === thread) focusThread(thread, "move");
      else focusDestination(destination2, "move");
    });
  }
  const directThread = node === thread && standingIn(thread);
  const aim = directThread ? landingTarget(thread, threadReplyInput(thread) ?? focused()) : { node };
  const target = aim.node ?? thread;
  const long = directThread && (target !== thread || aim.block === "end");
  const start = long ? threadLandingStart(thread, target, threadsBox) : null;
  if (scroll && mayArrive())
    scrollIntoView(start ?? target, {
      behavior: scrollBehavior(),
      // A long thread begins at the clean content boundary chosen above. A short card
      // is context in full; a requested message keeps the least-moving direct route.
      block: start ? "start" : long ? aim.block ?? "start" : target === thread ? "center" : "nearest"
    });
  const revealed = aim.block === "end" && thread.querySelector(":scope > .lf-thread-reply") || target;
  revealed.classList.toggle("grow", false);
  if (flash && mayArrive()) {
    revealed.classList.toggle("flash", true);
    setTimeout(() => revealed.classList.toggle("flash", false), 1300);
  }
  return focus ? focused() : node;
}
var listedThreads = (ids, threadsBox) => ids.map((id) => listNode(id, threadsBox)).filter((node) => node?.matches(".lf-thread") && !node.closest(".lf-going"));
var accompaniedThread = (ids, threadsBox) => listedThreads(ids, threadsBox).find((node) => node.open) ?? null;
function accompanyThread(ids, threadsBox) {
  const expanded = accompaniedThread(ids, threadsBox);
  const thread = expanded ?? listedThreads(ids, threadsBox)[0];
  if (!thread) return;
  threadsBox.revealNavigation(thread.dataset.id);
  if (expanded && alreadyShown(thread)) return;
  scrollIntoView(thread, {
    behavior: scrollBehavior(),
    block: fitsWhole(thread) ? "nearest" : "start"
  });
}
function createThreadLanding({ setPanel, revealThread, threadsBox }) {
  const landIn = (destination) => {
    const prepared = prepareLanding(destination);
    if (!prepared) return false;
    const { box } = prepared;
    box.lfRevealReply?.();
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
  const showThread = (id, {
    part = "reply",
    focus = true,
    flash = true,
    scroll = true,
    intent = retainUserIntent({
      source: focused(),
      available: () => threadsBox.isConnected,
      fallback: threadsBox
    })
  } = {}) => {
    if (!intent.handoff(() => setPanel(true))) return Promise.resolve(null);
    if (part === "message" && !threadsBox.querySelector(`.lf-msg[data-mid="${CSS.escape(id)}"]`))
      showHeld(id);
    const ready = showThreadNow(
      id,
      part,
      focus,
      flash,
      revealThread,
      threadsBox,
      intent,
      scroll
    );
    return ready.then(
      (arrived) => arrived,
      () => null
    );
  };
  return {
    landIn,
    landInThread: landInThread2,
    landSent,
    showThread,
    accompaniedThread: (ids) => accompaniedThread(ids, threadsBox),
    accompanyThread: (ids) => accompanyThread(ids, threadsBox)
  };
}
function declareThreadKeys(landIn, narrowing) {
  pageScope("thread", {
    title: "In a thread",
    root: focused,
    when: () => threadList().length > 0,
    at: () => Boolean(heldThread()),
    rows: [
      {
        id: "thread.primary",
        keys: ["Enter"],
        description: () => resolutionControl(cardThread())?.matches(".lf-reopen") ? "Reopen it" : "Write a reply",
        title: () => resolutionControl(cardThread())?.matches(".lf-reopen") ? "reopen" : "reply",
        // A panel title's bar keeps its room for resolution; the reply box under it
        // already names its key, and the reference lists this row.
        lineWhen: () => !focused()?.matches?.(".lf-thread-summary"),
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
        keys: ["r"],
        description: () => resolutionControl(heldThread())?.matches(".lf-reopen") ? "Reopen it" : "Resolve it",
        title: () => resolutionControl(heldThread())?.matches(".lf-reopen") ? "reopen" : "resolve",
        // Search keeps its next/previous hints; resolution remains in the reference.
        lineWhen: () => !narrowing.threadSearchActive(),
        when: () => resolutionControl(heldThread())?.matches(
          ':not(:disabled, [aria-disabled="true"])'
        ),
        run: () => resolutionControl(heldThread()).click()
      }
    ]
  });
}

// runtime/queue-title.js
function queueTitle(item) {
  const thread = readThreads().threads.find((thread2) => thread2.id === item.thread);
  const own = elementById(item.subject.id);
  const topic = thread ? threadSummary(thread).topic : "";
  if (item.title) return item.title;
  if (item.kind === "work" && item.detail) return item.detail;
  const sent = item.answer?.message && thread?.msgs.find((message) => message.id === item.answer.message);
  if (sent) return sent.body.text.trim() || topic;
  if (item.subject.kind === "widget") {
    const ask = own && askHolding(readAsks().all, own);
    return ask && addressableLabel(askPlace(ask).context) || addressableLabel(own) || topic || item.id;
  }
  return topic || item.id;
}

// runtime/asks/answer.js
function ownedAskControl(source, commandSource) {
  const selector = tagsDeclaring((entry) => entry["x-awaits"]).join(",");
  return !selector || closestAcross(commandSource, selector) === source;
}
function askWords(ask) {
  if (ask.answer === null) return "";
  if (ask.source.kind === "approval") return "Approved";
  if (ask.source.kind === "reply")
    return ask.answer.value.text ?? ask.answer.value.token ?? "";
  const source = elementById(ask.source.id);
  const formatter = (
    /** @type {{answerWords?: (value: unknown, element: Element) => unknown}} */
    customElements.get(ask.source.tag)?.answerWords
  );
  return String(source && formatter ? formatter(ask.answer.value, source) : "").replace(/\s+/g, " ").trim();
}
function askEnding(ask) {
  if (ask.status === "withdrawn") return "Withdrawn";
  if (ask.status === "answered_elsewhere") return "Answered elsewhere";
  const words2 = askWords(ask);
  return words2 ? `Answered: ${words2}` : "Answered";
}

// runtime/data.js
function acceptData(candidate, taken) {
  return applicationState.acceptData(candidate, taken);
}
var subscriptions = /* @__PURE__ */ new Set();
var subscriptionSequence = 0;
function readingIdentity(reading) {
  return reading ? JSON.stringify([
    reading.contract,
    reading.revision ?? null,
    reading.run ?? null,
    reading.error ?? null,
    Object.hasOwn(reading, "value")
  ]) : null;
}
async function notifyDataSubscribers() {
  const version = runtime.data.version;
  deliveries += 1;
  const round = {};
  for (const delivered of [...deliveryListeners]) delivered(round);
  const current = [...subscriptions];
  for (const subscription of current) subscription.notify();
  const regions = current.map((subscription) => subscription.region);
  await whenApplicationRegionsPresented(
    regions,
    () => runtime.data.version === version
  );
  if (version !== null && runtime.data.version === version)
    setRuntimeRootAttribute(document.body, PAGE_PAINT_ATTRIBUTE.dataVersion, version);
}
var declaredInput = (element, input) => {
  const declaration = registry[element.localName]?.["x-data"]?.[input];
  if (!declaration)
    throw new Error(
      `watchData(${element.localName}, ${input}) input is not declared by this widget`
    );
  return declaration;
};
function dataReader(element, input) {
  const declaration = declaredInput(element, input);
  const source = element.getAttribute(declaration.source);
  const selected = applicationState.select(
    (root) => source && Object.hasOwn(root.data.sources, source) ? root.data.sources[source] : null
  );
  let shown;
  let taken = -1;
  const delivered = outsideReading(
    () => {
      if (taken !== deliveries) {
        taken = deliveries;
        shown = untracked(selected.read);
      }
      return shown;
    },
    (moved2) => {
      deliveryListeners.add(moved2);
      return () => deliveryListeners.delete(moved2);
    }
  );
  stagedReadings.add(selected);
  let reported = null;
  return () => {
    selected.read();
    const sourceStore = (
      /** @type {{contract: string, revision?: string} | null} */
      delivered.read()
    );
    const incompatible = sourceStore && sourceStore.contract !== declaration.contract;
    if (incompatible && reported !== sourceStore) {
      reported = sourceStore;
      reportPageError(
        `data source ${source} carries contract ${sourceStore.contract}; <${element.localName}> input ${input} requires ${declaration.contract}`
      );
    }
    if (incompatible || !source || !sourceStore || !Object.hasOwn(sourceStore, "value"))
      return null;
    return structuredClone({
      source,
      ...sourceStore,
      origin: {
        input,
        source,
        contract: declaration.contract,
        revision: sourceStore.revision
      }
    });
  };
}
var deliveries = 0;
var deliveryListeners = /* @__PURE__ */ new Set();
var stagedReadings = /* @__PURE__ */ new WeakSet();
var stagesOnly = (reading) => stagedReadings.has(reading);
function joinDataDelivery(region) {
  const subscription = { region, notify() {
  } };
  subscriptions.add(subscription);
  return () => subscriptions.delete(subscription);
}
function watchData(element, input, callback) {
  const declaration = declaredInput(element, input);
  const source = element.getAttribute(declaration.source);
  const paint = readingPaint(element, callback);
  const selectedSource = applicationState.select(
    (root) => source && Object.hasOwn(root.data.sources, source) ? root.data.sources[source] : null
  );
  let completion = Promise.resolve();
  const region = `data:${element.id}:${input}:${++subscriptionSequence}`;
  let presentation = null;
  const subscription = { region, notify: () => notifySelected() };
  let stopSelection;
  let pendingDelivery = null;
  let stopped = false;
  let stopLifetime = null;
  function disconnect() {
    subscriptions.delete(subscription);
    stopSelection?.();
    stopSelection = null;
    pendingDelivery = null;
    presentation?.disconnect();
    presentation = null;
  }
  function stop() {
    if (stopped) return;
    stopped = true;
    stopLifetime?.();
    disconnect();
    paint.stop();
  }
  const deliver = (snapshot, identity2) => {
    if (paint.owes(identity2)) {
      if (snapshot)
        snapshot.origin = {
          input,
          source,
          contract: declaration.contract,
          revision: snapshot.revision
        };
      const rendering = paint(identity2, structuredClone(snapshot));
      completion = Promise.resolve(rendering).catch(() => {
      });
    }
    return completion;
  };
  const update = (sourceStore) => {
    const identity2 = readingIdentity(sourceStore);
    const incompatible = sourceStore && sourceStore.contract !== declaration.contract;
    if (incompatible && paint.owes(identity2))
      reportPageError(
        `data source ${source} carries contract ${sourceStore.contract}; watchData(${element.localName}, ${input}) requires ${declaration.contract}`
      );
    if (incompatible || !source || !sourceStore || !Object.hasOwn(sourceStore, "value"))
      return deliver(null, identity2);
    return deliver({ source, ...sourceStore }, identity2);
  };
  const stage = (sourceStore) => {
    const identity2 = readingIdentity(sourceStore);
    if (!pendingDelivery && !paint.owes(identity2)) return;
    pendingDelivery = { sourceStore, ticket: presentation.present(identity2) };
  };
  function notifySelected() {
    const pending = pendingDelivery;
    if (!pending) return;
    pendingDelivery = null;
    pending.ticket.resolve(update(pending.sourceStore));
  }
  function connect() {
    if (stopped || stopSelection || !element.isConnected) return;
    presentation = attachApplicationPresentation(region, element);
    const mount = presentation;
    let mounting = true;
    stopSelection = selectedSource.subscribe((sourceStore) => {
      if (mounting) {
        const rendering = update(sourceStore);
        if (!stopped) mount.present(readingIdentity(sourceStore)).resolve(rendering);
        return rendering;
      }
      stage(sourceStore);
    });
    mounting = false;
    if (stopped) {
      stopSelection();
      stopSelection = null;
      return;
    }
    subscriptions.add(subscription);
  }
  stopLifetime = watchOwner(element, { connect, disconnect });
  stop.refresh = paint.refresh;
  return stop;
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

export {
  initializeServedDocument,
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
  fab,
  composerQuote,
  pendingAnchor,
  pendingAbout,
  pendingDrawing,
  composerOpen,
  createSelectionComposer,
  watchProjection,
  currentProjection,
  inPageOrder,
  pageOutline,
  threadSection,
  inRecentOrder,
  createAnchorTravel,
  versionsReading,
  comparisonChanges,
  watchComparison,
  createVersionController,
  reactionTokens,
  reactionAvailable,
  paintBarReactions,
  createReactionController,
  sendReaction,
  queueItemKey,
  readQueues,
  beginRead,
  mountApplication,
  threadBox2 as threadBox,
  dispatchWidget,
  invalidateDom,
  landInThread,
  navigateToDatum,
  projectData,
  placePageThreads2 as placePageThreads,
  consumeAnnotations,
  mountThreadViews,
  registerThreadPresentation,
  threadActions,
  askActions,
  queueActions,
  wireInput,
  threadInput,
  standingThread,
  leavesBox,
  retainPanelLanding,
  landWalkedThread,
  wireThreadLanding,
  createThreadLanding,
  declareThreadKeys,
  queueTitle,
  ownedAskControl,
  askWords,
  askEnding,
  acceptData,
  notifyDataSubscribers,
  dataReader,
  stagesOnly,
  joinDataDelivery,
  watchData,
  loadDeferred
};
