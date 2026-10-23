import {
  LeafEditorView,
  LeafElement,
  answerWords,
  claimTraversals,
  comparisonChanges,
  consumeAnnotations,
  currentProjection,
  landInThread,
  loadDeferred,
  navigateToDatum,
  obligationActions,
  placePageThreads,
  projectData,
  publishOutput,
  pushEntry,
  queueActions,
  queueItemKey,
  queueTitle,
  readQueues,
  referencedProjection,
  registerThreadPresentation,
  replaceEntry,
  requireReference,
  threadActions,
  threadBox,
  threadInput,
  widgetController,
  wireInput
} from "./bundle-document-identity.js";
import {
  dressSamples,
  wear
} from "./bundle-dress.js";
import {
  CONTRIBUTION_ENTRY_SCHEMA,
  contributionEntry,
  contributionItemKey,
  presentContributionEntry,
  presentContributionReceipts,
  registerContribution
} from "./bundle-contribution-model.js";
import "./bundle-projection~presentation.js";
import {
  HOLDS_WORD,
  HeldReading,
  allButCommandReference,
  anchorLabel,
  answeredInWords,
  beginWalk,
  capturePlace,
  clearDraft,
  copyBlock,
  ensureSyntaxLanguage,
  heldGrowth,
  highlightBlocks,
  inlineMarkdownFragment,
  keepView,
  langForPath,
  listWalkPosition,
  loadDraft,
  loadMarkdown,
  markdownReady,
  markdownSourceOffset,
  markdownWords,
  obligationsIn,
  openingView,
  paintMarkdown,
  placeKeeper,
  quietWord,
  readObligations,
  readThreads,
  releaseOutlets,
  renderMarkdown,
  restorePlace,
  rowWalk,
  saveDraft,
  sendDraft,
  synNodes,
  syntax,
  tabStore,
  threadSummary,
  threadSurface,
  tokenLines,
  watchDraft
} from "./bundle-user-place.js";
import {
  DISCLOSE,
  aborted,
  bodyText,
  dataBody,
  failSoft,
  once,
  placesFailure,
  quoted,
  reportFailure,
  setChildLists,
  setChildren,
  setRenderedChildren,
  shadowStage
} from "./bundle-keyboard~disclosure.js";
import {
  fitsWhole,
  retainUserIntent,
  scrollIntoReadingBand,
  scrollIntoView
} from "./bundle-user-intent.js";
import {
  isCanonicalMediaUrl,
  scopedMediaUrl
} from "./bundle-media.js";
import {
  backgroundFlash,
  foldBlock,
  foldDuration,
  motion,
  onMotionPreferenceChange,
  reducedMotion,
  returnDuration,
  scrollBehavior
} from "./bundle-motion.js";
import "./bundle-page-controls.js";
import {
  addressableLabel,
  addressableName,
  addressableWord,
  addressedElements,
  fragmentTarget,
  projectedDatum,
  registerVisualParts
} from "./bundle-visual-parts.js";
import {
  initialRender
} from "./bundle-initial-render.js";
import "./bundle-chrome.js";
import {
  PAGE_INTERFACE,
  PRESENTATION,
  afterPresentation,
  ago,
  atScrollEnd,
  clockValue,
  compoundReadingRegionId,
  deferredArrival,
  pageScroller,
  preserveReadingRegions,
  quietSince,
  regionScrollBehavior,
  registerReadingRegion,
  scrollLimit,
  scrollerFor,
  shortAgo,
  showReadingSubject,
  watchReadingRegionTransitions
} from "./bundle-presence.js";
import {
  alignText,
  authoredScope,
  closestAcross,
  elementById,
  excerptWords,
  inChrome,
  renderRetired,
  says,
  textNodesUnder,
  wrote
} from "./bundle-passage-facts.js";
import {
  LAYOUT,
  LayerRefused,
  PAGE_PAINT_ATTRIBUTE,
  PRESS,
  PRESSABLE,
  announce,
  closeNativeLayer,
  commandScope,
  commandsOn,
  cycledRow,
  declarationFor,
  dragging,
  el,
  elementsDeclaring,
  frameFor,
  generated,
  generatedElement,
  growthIsSeen,
  iconElement,
  iconTemplate,
  inBaseLayer,
  keys,
  labelOf,
  landingInsets,
  layerFact,
  layoutChanged,
  matchesWhen,
  measure,
  motionPreview,
  notice,
  offer,
  offered,
  paintKeys,
  plainPress,
  pressIsKeyboardActivation,
  raiseError,
  reachedForWords,
  registry,
  relabel,
  removeRuntimeRootStyle,
  requestJson,
  rowArrows,
  saying,
  searchField,
  selectableOffer,
  selectableOffered,
  setRuntimeRootStyle,
  showNativeLayer,
  shownParts,
  shownWindow,
  whileConnected,
  worksInside
} from "./bundle-page-paint.js";
import {
  TEXT_BOX,
  TEXT_FIELD,
  afterScript,
  atLayoutPrecision,
  cancelAnimation,
  cancelRender,
  closeLayer,
  currentLocationIn,
  focusDestination,
  focused,
  handBack,
  holdFocus,
  isNativeLayer,
  keeps,
  keepsHidden,
  keepsText,
  layoutPx,
  move,
  nextAnimation,
  nextFrame,
  nextRender,
  onCurrentLocation,
  onUserInput,
  openLayer,
  openerOf,
  rove,
  sizeObserver,
  under,
  whenLeft
} from "./bundle-frame-visibility.js";
import {
  agentName,
  applicationRegionsPresented,
  applicationState,
  offlineInteractive,
  pageUrl,
  projectionRegionsPresented,
  readPart,
  revisionLabel
} from "./bundle-semantic-state.js";
import {
  Z,
  classMap,
  createRef,
  guard,
  html,
  keyed,
  live,
  noChange,
  nothing,
  rankAt,
  ref,
  render,
  repeat,
  styleMap,
  turns,
  unsafeHTML
} from "./bundle-queued-work.js";
import "./bundle-__export.js";

// runtime/indication.js
var INDICATED = PAGE_PAINT_ATTRIBUTE.indicated;
var held = /* @__PURE__ */ new Map();
var painted = /* @__PURE__ */ new Set();
var listening = false;
var resolve = (owner, attribute, key) => {
  const source = referencedProjection(owner, attribute);
  return source ? addressedElements(source, key) : [];
};
function repaint() {
  const next = /* @__PURE__ */ new Set();
  for (const [owner, keys2] of held)
    for (const [attribute, key] of keys2)
      for (const element of resolve(owner, attribute, key)) next.add(element);
  for (const element of painted)
    if (!next.has(element)) element.removeAttribute(INDICATED);
  for (const element of next)
    if (!painted.has(element)) element.setAttribute(INDICATED, "");
  painted = next;
}
function indicate(owner, attribute, key) {
  requireReference("indicate", owner, attribute);
  if (key !== null && (typeof key !== "string" || !key))
    throw new TypeError("indicate key must be a non-empty string or null");
  if (!listening) {
    listening = true;
    document.addEventListener(LAYOUT, () => {
      if (held.size || painted.size) repaint();
    });
  }
  const keys2 = held.get(owner) ?? /* @__PURE__ */ new Map();
  if (key === null) keys2.delete(attribute);
  else keys2.set(attribute, key);
  if (keys2.size) held.set(owner, keys2);
  else held.delete(owner);
  repaint();
  return key !== null && resolve(owner, attribute, key).length > 0;
}

// runtime/reports.js
function reportTarget(target) {
  if (target === null) return null;
  if (target instanceof Element) {
    if (target.id) return { kind: "widget", id: target.id };
  } else if (["widget", "thread"].includes(target?.kind) && typeof target.id === "string" && target.id) {
    return { kind: target.kind, id: target.id };
  }
  throw new TypeError(
    "report target must be a widget element or {kind: 'widget' | 'thread', id}"
  );
}
var targetKey = (target) => target ? JSON.stringify([target.kind, target.id]) : null;
var reportsByTarget = /* @__PURE__ */ new Map();
var reportsFor = (key) => {
  if (!reportsByTarget.has(key))
    reportsByTarget.set(
      key,
      readPart(
        (root) => (root.effective.view?.reports ?? []).filter(
          (report) => key === null || targetKey(report.target) === key
        )
      )
    );
  return reportsByTarget.get(key)();
};
var reportSequence = (target = null) => reportsFor(targetKey(reportTarget(target))).map((report) => structuredClone(report));
var publishedAt = readPart((root) => root.effective.view?.published_at ?? null);
var saidAt = (el2) => closestAcross(el2, ".lf-msg")?.querySelector(":scope > .lf-msg-head time")?.dateTime || publishedAt();
var readHistory = readPart((root) => ({
  phase: root.phase,
  events: root.authoritative?.browser.history ?? []
}));
var reportsPresented = (target = null) => projectionRegionsPresented([...reportWidgets(target)]);
var reportWidgets = (target) => {
  const key = targetKey(reportTarget(target));
  const widgets2 = new Set(target instanceof Element ? [target.id] : []);
  for (const entry of currentProjection().classified.values()) {
    if (entry.terminal || entry.e.kind !== "report") continue;
    if (key === null || key === targetKey({ kind: "widget", id: entry.e.widget }))
      widgets2.add(entry.e.widget);
  }
  return widgets2;
};
var reportsReady = (target) => target.whenReady(
  () => applicationRegionsPresented([
    "projection:chrome",
    `widget:${target.id}:preparation`,
    ...[...reportWidgets(target)].filter((widget) => widget !== target.id).flatMap((widget) => [
      `widget:${widget}:render`,
      `widget:${widget}:preparation`
    ])
  ])
);

// runtime/work.js
var widgets = () => layerFact("$work")?.widgets ?? {};
function specs(role) {
  return Object.entries(widgets()).filter(([, spec]) => spec?.role === role);
}
function workRole(element, role = null) {
  const spec = widgets()[element?.localName];
  return spec && (!role || spec.role === role) ? spec : null;
}
function workElements(root, role, { direct = false } = {}) {
  const tags = new Set(specs(role).map(([tag]) => tag));
  const candidates = [...root.querySelectorAll("*")];
  const boundary = workAncestor(root, "scope");
  return candidates.filter(
    (element) => tags.has(element.localName) && workAncestor(element, "scope") === boundary && (!direct || workAncestor(element.parentElement) === root)
  );
}
var directWorkElements = (root, role) => workElements(root, role, { direct: true });
function workAncestor(element, role) {
  for (let at = element; at; at = at.parentElement) if (workRole(at, role)) return at;
  return null;
}
function stateReport(element, role) {
  const verb = stateVerb(element, role);
  const spec = declarationFor(element, "x-state")[verb];
  return registry.$states[element.localName][verb].writer === "agent" ? [verb, spec] : [null, null];
}
function stateVerb(element, role) {
  const attribute = workRole(element, role)?.state;
  const matches = Object.entries(declarationFor(element, "x-state") ?? {}).filter(
    ([, spec]) => spec.unit === "widget" && spec.record?.kind === "value" && spec.record.attr === attribute
  ).map(([verb]) => verb);
  if (matches.length !== 1)
    throw new Error(
      `leaf: $work ${role} <${element.localName}> state ${attribute} needs one recorded widget verb`
    );
  return matches[0];
}
var roleState = (element, role, read) => read(element).state[stateVerb(element, role)]?.value ?? null;
var actionReports = (element, action) => reportSequence(element).filter(
  (report) => report.source === "report" && report.action === action
);
function workerView(worker, read) {
  const role = workRole(worker, "worker");
  const state = roleState(worker, "worker", read);
  const focus = role.on && worker.getAttribute(role.on);
  const [reportVerb] = stateReport(worker, "worker");
  const reports = reportVerb ? actionReports(worker, reportVerb) : [];
  const heard = reports.at(-1)?.ts ?? saidAt(worker);
  const running = role.running.includes(state);
  const scope = workAncestor(worker, "scope");
  const goal = workAncestor(worker.parentElement, "goal");
  const remit = goal && workAncestor(goal, "scope") === scope ? goal : scope;
  const candidate = focus ? document.getElementById(focus) : null;
  const assignment = candidate && workRole(candidate, "goal") && workAncestor(candidate, "scope") === scope && (remit === scope || remit.contains(candidate)) ? candidate : null;
  return {
    element: worker,
    role,
    state,
    retired: role.retired.includes(state),
    running,
    quiet: running && quietSince(heard),
    heard,
    remit,
    assignment
  };
}
var done = (goal, read) => {
  const role = workRole(goal, "goal");
  return role.done.includes(roleState(goal, "goal", read));
};
function interventions(goal, open) {
  const scope = workAncestor(goal, "scope");
  return obligationsIn(goal, open).map((item) => elementById(
    /** @type {{id: string}} */
    item.source.id
  )).filter(
    (item) => item !== goal && !workRole(item, "goal") && workAncestor(item, "scope") === scope && workAncestor(item.parentElement, "goal") === goal && !quoted(item)
  );
}
function stopped(goal, open, nested, read) {
  const role = workRole(goal, "goal");
  if (read(goal).thread.heldBy) return true;
  if (nested.length) return true;
  if (!role.stopped.includes(roleState(goal, "goal", read))) return false;
  if (open.some((item) => item.source.id === goal.id)) return true;
  const children = directWorkElements(goal, "goal");
  return children.length ? children.some((child) => stopped(child, open, interventions(child, open), read)) : true;
}
function goalView(goal, open, read) {
  const descendants = workElements(goal, "goal");
  const leaves = descendants.filter((item) => !directWorkElements(item, "goal").length);
  const progressLeaves = leaves.length ? leaves : [goal];
  const liveWorkers = directWorkElements(goal, "worker").map((worker) => workerView(worker, read)).filter((worker) => !worker.retired);
  const role = workRole(goal, "goal");
  const state = roleState(goal, "goal", read);
  const [reportVerb] = stateReport(goal, "goal");
  const reports = reportVerb ? actionReports(goal, reportVerb) : [];
  const latestReport = reports.at(-1);
  const reportedStoppedAt = latestReport?.disposition === "effective" && role.stopped.includes(latestReport.detail.value) ? latestReport.ts : null;
  const nested = interventions(goal, open);
  const held2 = Boolean(read(goal).thread.heldBy);
  return {
    element: goal,
    role,
    state,
    title: addressableName(goal) || goal.id,
    done: done(goal, read),
    stopped: stopped(goal, open, nested, read),
    held: held2,
    leaves: progressLeaves,
    finished: progressLeaves.filter((leaf) => done(leaf, read)).length,
    liveWorkers,
    stoppedAt: reportedStoppedAt ?? (role.stoppedAt ? goal.getAttribute(role.stoppedAt) : null)
  };
}
var openWidgetObligations = readPart(
  (root) => root.effective.obligations.user.filter((item) => item.source.kind === "widget")
);
function readWork(scope) {
  const readings = /* @__PURE__ */ new Map();
  const read = (element) => {
    if (!readings.has(element)) readings.set(element, widgetController(element).read());
    return readings.get(element);
  };
  const open = openWidgetObligations();
  const goals = workElements(scope, "goal").map((goal) => goalView(goal, open, read));
  const byElement = new Map(goals.map((goal) => [goal.element, goal]));
  const workers = workElements(scope, "worker").map(
    (worker) => workerView(worker, read)
  );
  const liveWorkers = workers.filter((worker) => !worker.retired);
  const leaves = goals.filter(
    (goal) => !directWorkElements(goal.element, "goal").length
  );
  const stoppedGoals = goals.filter((goal) => goal.stopped).sort((a, b) => {
    const at = a.stoppedAt ? new Date(a.stoppedAt).getTime() : NaN;
    const bt = b.stoppedAt ? new Date(b.stoppedAt).getTime() : NaN;
    return (Number.isFinite(at) ? at : Infinity) - (Number.isFinite(bt) ? bt : Infinity);
  });
  return {
    scope,
    goals,
    byElement,
    leaves,
    done: leaves.filter((goal) => goal.done).length,
    workers,
    liveWorkers,
    running: liveWorkers.filter((worker) => worker.running && !worker.quiet),
    quiet: liveWorkers.filter((worker) => worker.quiet),
    stopped: stoppedGoals
  };
}

// runtime/image-difference.js
var SLIGHT = 48;
var STEP = 4;
var LINE = 40;
var CELL = 4;
var SPACING = 1;
var COARSE = 8;
var THROUGHOUT = 0.5;
var ABSORB = 16;
var MOVED_REACH = 32;
async function differingRegions(a, b) {
  const width = Math.max(a.width, b.width);
  const height = Math.max(a.height, b.height);
  const columns = Math.ceil(width / CELL);
  const one = words(a);
  const other = words(b);
  const struck = new Uint8Array(columns * Math.ceil(height / CELL));
  const coarseColumns = Math.ceil(width / COARSE);
  const coarse = new Uint8Array(coarseColumns * Math.ceil(height / COARSE));
  let changed = 0;
  for (let y = 0; y < height; y += 1) {
    const row = Math.floor(y / CELL) * columns;
    const coarseRow = Math.floor(y / COARSE) * coarseColumns;
    for (let x = 0; x < width; x += 1) {
      const change = pixelChange(a, one, b, other, x, y);
      if (!change) continue;
      changed += 1;
      if (change === STRONG) {
        struck[row + Math.floor(x / CELL)] = 1;
        coarse[coarseRow + Math.floor(x / COARSE)] = 1;
      }
    }
  }
  if (coarse.reduce((sum, square) => sum + square, 0) >= THROUGHOUT * coarse.length)
    return { width, height, changed, throughout: true, regions: [] };
  if (!struck.includes(1))
    return { width, height, changed, throughout: false, regions: [] };
  const { DBSCAN } = await import("/vendor/density-clustering.esm.js");
  const before = blocksOf(a, one, columns);
  const after = blocksOf(b, other, columns);
  const drawnChange = (block, image, pixels2, otherImage, otherPixels) => block.cells.some((cell) => {
    if (!struck[cell]) return false;
    block.ground ??= around(block, image, pixels2) ?? null;
    const box2 = block.boxes.get(cell);
    for (let y = box2.y; y < box2.y + box2.height; y += 1)
      for (let x = box2.x; x < box2.x + box2.width; x += 1) {
        const p = pixels2[y * image.width + x];
        if (block.ground !== null && distance(p, block.ground) <= STEP) continue;
        const q = x < otherImage.width && y < otherImage.height ? otherPixels[y * otherImage.width + x] : void 0;
        if (q === void 0 || distance(p, q) >= SLIGHT) return true;
      }
    return false;
  });
  const touched = (block, image, pixels2, otherImage, otherPixels) => block.frame ? drawnChange(block, image, pixels2, otherImage, otherPixels) : block.cells.some((cell) => struck[cell]);
  const reading = (blocks, image, pixels2, others, otherImage, otherPixels) => blocks.map((block) => {
    if (!touched(block, image, pixels2, otherImage, otherPixels))
      return { state: "same" };
    let found = null;
    let nearest = Infinity;
    for (const candidate of others) {
      if (!touched(candidate, otherImage, otherPixels, image, pixels2)) continue;
      if (candidate.width !== block.width || candidate.height !== block.height)
        continue;
      const far = Math.abs(candidate.x - block.x) + Math.abs(candidate.y - block.y);
      if (far < nearest && alike(image, pixels2, block, otherImage, otherPixels, candidate))
        [found, nearest] = [candidate, far];
    }
    if (!found) return { state: "changed" };
    if (!nearest) return { state: "same" };
    return { state: "moved", d: [found.x - block.x, found.y - block.y] };
  });
  const readBefore = reading(before, a, one, after, b, other);
  const readAfter = reading(after, b, other, before, a, one);
  const owned = new Uint8Array(struck.length);
  for (const block of [...before, ...after])
    for (let r = Math.floor(block.y / CELL); r * CELL < block.y + block.height; r += 1)
      owned.fill(
        1,
        r * columns + Math.floor(block.x / CELL),
        r * columns + Math.ceil((block.x + block.width) / CELL)
      );
  const bare = [];
  for (let cell = 0; cell < struck.length; cell += 1)
    if (struck[cell] && !owned[cell]) {
      const x = cell % columns * CELL;
      const y = Math.floor(cell / columns) * CELL;
      bare.push({
        x,
        y,
        width: Math.min(CELL, width - x),
        height: Math.min(CELL, height - y)
      });
    }
  const unowned = merged(bare, (p, q) => near(p, q, 2 * CELL)).flatMap(
    (box2) => [
      ["before", a],
      ["after", b]
    ].flatMap(([side, image]) => {
      const right = Math.min(box2.x + box2.width, image.width);
      const bottom = Math.min(box2.y + box2.height, image.height);
      return right > box2.x && bottom > box2.y ? [
        {
          x: box2.x,
          y: box2.y,
          width: right - box2.x,
          height: bottom - box2.y,
          side,
          kind: "changed"
        }
      ] : [];
    })
  );
  const regions = [
    ...outlines(before, readBefore, struck, "before", unowned, DBSCAN),
    ...outlines(after, readAfter, struck, "after", unowned, DBSCAN)
  ].sort((p, q) => p.y - q.y || p.x - q.x).map(({ x, y, width: width2, height: height2, side, kind }) => ({
    x,
    y,
    width: width2,
    height: height2,
    side,
    kind
  }));
  return { width, height, changed, throughout: false, regions };
}
function outlines(blocks, states, struck, side, bare, DBSCAN) {
  const marks = [];
  for (const [i, block] of blocks.entries()) {
    const { state, d } = states[i];
    if (state === "same") continue;
    if (state === "moved" && block.frame) continue;
    marks.push({ ...box(block), side, kind: state, d, block });
  }
  const whole = marks.filter(
    (mark) => mark.kind === "changed" && marks.some((inner) => contains(mark, inner)) && blocks.every(
      (block, i) => states[i].state === "changed" || !contains(mark, block)
    )
  );
  const inWhole = (mark) => whole.some((outer) => contains(outer, mark));
  const holds = (mark) => !whole.includes(mark) && (mark.kind === "changed" ? blocks : marks).some(
    (inner) => inner !== mark.block && contains(mark, inner)
  );
  const shown = marks.filter((mark) => !holds(mark) && !inWhole(mark));
  for (const mark of marks) {
    if (!holds(mark) || inWhole(mark) || mark.kind !== "changed") continue;
    const loose = mark.block.cells.filter((cell) => struck[cell]).map((cell) => mark.block.boxes.get(cell)).filter((cellBox) => !shown.some((other) => contains(other, cellBox)));
    for (const group of merged(loose, (p, q) => near(p, q, 2 * CELL))) {
      const host = shown.find(
        (other) => other.kind === "changed" && near(other, group, ABSORB)
      );
      if (host) Object.assign(host, union(host, group));
      else shown.push({ ...group, side, kind: "changed" });
    }
  }
  const joined = join([...shown, ...bare.filter((box2) => box2.side === side)], DBSCAN);
  return joined.filter(
    (mark) => mark.kind !== "moved" || !joined.some((outer) => outer.kind === "changed" && contains(outer, mark))
  );
}
function blocksOf(image, pixels2, columns) {
  const { width, height } = image;
  const belowDiffers = new Uint8Array(width * height);
  const rightDiffers = new Uint8Array(width * height);
  for (let i = 0; i < width * height; i += 1) {
    const p = pixels2[i];
    if (i + width < width * height && p !== pixels2[i + width] && distance(p, pixels2[i + width]) > STEP)
      belowDiffers[i] = 1;
    if ((i + 1) % width && p !== pixels2[i + 1] && distance(p, pixels2[i + 1]) > STEP)
      rightDiffers[i] = 1;
  }
  const acrossRows = new Uint8Array(width * height);
  const acrossColumns = new Uint8Array(width * height);
  for (let i = 0; i < width * height; i += 1) {
    if (belowDiffers[i]) acrossRows[i] = acrossRows[i + width] = 1;
    if (rightDiffers[i]) acrossColumns[i] = acrossColumns[i + 1] = 1;
  }
  const line = new Uint8Array(width * height);
  for (let y = 0; y < height; y += 1) {
    const row = y * width;
    let start = 0;
    for (let x = 1; x <= width; x += 1) {
      const i = row + x;
      if (x < width && acrossRows[i] && acrossRows[i - 1] && !rightDiffers[i - 1])
        continue;
      if (x - start >= LINE && acrossRows[row + start])
        line.fill(1, row + start, row + x);
      start = x;
    }
  }
  for (let x = 0; x < width; x += 1) {
    let start = 0;
    for (let y = 1; y <= height; y += 1) {
      const i = y * width + x;
      if (y < height && acrossColumns[i] && acrossColumns[i - width] && !belowDiffers[i - width])
        continue;
      if (y - start >= LINE && acrossColumns[start * width + x])
        for (let k = start; k < y; k += 1) line[k * width + x] = 1;
      start = y;
    }
  }
  const rows = Math.ceil(height / CELL);
  const ownColumns = Math.ceil(width / CELL);
  const count = ownColumns * rows;
  const boxes = new Int32Array(count * 4).fill(-1);
  const marked = new Uint8Array(count);
  const lined = new Uint8Array(count);
  for (let y = 0; y < height; y += 1)
    for (let x = 0; x < width; x += 1) {
      const i = y * width + x;
      if (!acrossRows[i] && !acrossColumns[i]) continue;
      const cell = Math.floor(y / CELL) * ownColumns + Math.floor(x / CELL);
      if (!line[i]) marked[cell] = 1;
      else lined[cell] = 1;
      const k = cell * 4;
      if (boxes[k] < 0) {
        boxes[k] = boxes[k + 2] = x;
        boxes[k + 1] = boxes[k + 3] = y;
      } else {
        boxes[k] = Math.min(boxes[k], x);
        boxes[k + 1] = Math.min(boxes[k + 1], y);
        boxes[k + 2] = Math.max(boxes[k + 2], x);
        boxes[k + 3] = Math.max(boxes[k + 3], y);
      }
    }
  const parent = Int32Array.from({ length: count }, (_, cell) => cell);
  const root = (cell) => {
    while (parent[cell] !== cell) cell = parent[cell] = parent[parent[cell]];
    return cell;
  };
  const join2 = (one, other) => {
    const [from, to] = [root(one), root(other)];
    if (from !== to) parent[to] = from;
  };
  for (let r = 0; r < rows; r += 1)
    for (let c = 0; c < ownColumns; c += 1) {
      const cell = r * ownColumns + c;
      if (boxes[cell * 4] < 0) continue;
      for (const near2 of [
        cell + 1,
        cell + ownColumns - 1,
        cell + ownColumns,
        cell + ownColumns + 1
      ])
        if (near2 < count && Math.abs(near2 % ownColumns - c) <= 1 && boxes[near2 * 4] >= 0)
          join2(cell, near2);
    }
  const pieces = /* @__PURE__ */ new Map();
  for (let cell = 0; cell < count; cell += 1) {
    const k = cell * 4;
    if (boxes[k] < 0) continue;
    const id = root(cell);
    const piece = pieces.get(id);
    if (!piece)
      pieces.set(id, {
        id,
        left: boxes[k],
        top: boxes[k + 1],
        right: boxes[k + 2],
        bottom: boxes[k + 3],
        marked: !!marked[cell],
        lined: !!lined[cell]
      });
    else {
      piece.left = Math.min(piece.left, boxes[k]);
      piece.top = Math.min(piece.top, boxes[k + 1]);
      piece.right = Math.max(piece.right, boxes[k + 2]);
      piece.bottom = Math.max(piece.bottom, boxes[k + 3]);
      piece.marked ||= !!marked[cell];
      piece.lined ||= !!lined[cell];
    }
  }
  const marks = [...pieces.values()].filter((piece) => piece.marked && !piece.lined).sort((p, q) => p.top - q.top);
  for (const [i, p] of marks.entries()) {
    const height2 = p.bottom - p.top + 1;
    for (let j = i + 1; j < marks.length; j += 1) {
      const q = marks[j];
      if (q.top > p.bottom + SPACING * height2) break;
      const reach = SPACING * Math.min(height2, q.bottom - q.top + 1);
      const across = Math.max(q.left - p.right, p.left - q.right) - 1;
      const down = Math.max(q.top - p.bottom, p.top - q.bottom) - 1;
      if (down < 0 && across >= 0 && across <= reach || across < 0 && down >= 0 && down <= reach)
        join2(p.id, q.id);
    }
  }
  const groups = /* @__PURE__ */ new Map();
  for (let cell = 0; cell < count; cell += 1) {
    const k = cell * 4;
    if (boxes[k] < 0) continue;
    const id = root(cell);
    let group = groups.get(id);
    if (!group)
      groups.set(
        id,
        group = {
          left: Infinity,
          top: Infinity,
          right: -1,
          bottom: -1,
          frame: true,
          cells: [],
          boxes: /* @__PURE__ */ new Map()
        }
      );
    group.left = Math.min(group.left, boxes[k]);
    group.top = Math.min(group.top, boxes[k + 1]);
    group.right = Math.max(group.right, boxes[k + 2]);
    group.bottom = Math.max(group.bottom, boxes[k + 3]);
    if (marked[cell]) group.frame = false;
    const pairCell = Math.floor(cell / ownColumns) * columns + cell % ownColumns;
    group.cells.push(pairCell);
    group.boxes.set(pairCell, {
      x: boxes[k],
      y: boxes[k + 1],
      width: boxes[k + 2] - boxes[k] + 1,
      height: boxes[k + 3] - boxes[k + 1] + 1
    });
  }
  return [...groups.values()].map((group) => ({
    x: group.left,
    y: group.top,
    width: group.right - group.left + 1,
    height: group.bottom - group.top + 1,
    frame: group.frame,
    cells: group.cells,
    boxes: group.boxes
  }));
}
function alike(image, pixels2, block, otherImage, otherPixels, candidate) {
  for (let j = 0; j < block.height; j += 1) {
    const p = (block.y + j) * image.width + block.x;
    const q = (candidate.y + j) * otherImage.width + candidate.x;
    for (let i = 0; i < block.width; i += 1) {
      const u = pixels2[p + i];
      const v = otherPixels[q + i];
      if (u !== v && distance(u, v) >= SLIGHT) return false;
    }
  }
  return true;
}
var box = ({ x, y, width, height }) => ({ x, y, width, height });
var contains = (outer, inner) => outer !== inner && outer.x <= inner.x && outer.y <= inner.y && outer.x + outer.width >= inner.x + inner.width && outer.y + outer.height >= inner.y + inner.height;
var near = (p, q, reach) => p.x - reach < q.x + q.width && q.x - reach < p.x + p.width && p.y - reach < q.y + q.height && q.y - reach < p.y + p.height;
var union = (p, q) => {
  const x = Math.min(p.x, q.x);
  const y = Math.min(p.y, q.y);
  return {
    x,
    y,
    width: Math.max(p.x + p.width, q.x + q.width) - x,
    height: Math.max(p.y + p.height, q.y + q.height) - y
  };
};
function merged(items, joins) {
  const list = items.map((item) => ({ ...item }));
  for (let i = 0; i < list.length; i += 1)
    for (let j = 0; j < list.length; j += 1) {
      if (j === i || !joins(list[i], list[j])) continue;
      list[i] = { ...list[i], ...union(list[i], list[j]) };
      list.splice(j, 1);
      if (j < i) i -= 1;
      j = -1;
    }
  return list;
}
function join(marks, DBSCAN) {
  const moves = merged(
    marks.filter((mark) => mark.kind === "moved"),
    (p, q) => p.d.join() === q.d.join() && near(p, q, MOVED_REACH)
  );
  const changed = marks.filter((mark) => mark.kind === "changed");
  if (changed.length < 2) return [...moves, ...changed];
  const sizes = changed.map((mark) => Math.max(1, Math.min(mark.width, mark.height) - 2)).sort((a, b) => a - b);
  const scale = sizes[Math.floor(sizes.length / 2)];
  const radius = scale * Math.min(2, Math.sqrt(changed.length) / 2);
  const gap = (p, q) => near(p, q, 8) ? 0 : Math.max(
    0,
    p.x - q.x - q.width + 2,
    q.x - p.x - p.width + 2,
    p.y - q.y - q.height + 2,
    q.y - p.y - p.height + 2
  );
  const groups = new DBSCAN().run(changed, radius, 1, gap);
  return [
    ...moves,
    ...groups.map((indices) => ({
      ...changed[indices[0]],
      ...indices.map((i) => changed[i]).reduce(union)
    }))
  ];
}
function around({ x, y, width, height }, image, pixels2) {
  const counts = /* @__PURE__ */ new Map();
  let best;
  const count = (column, row) => {
    if (column < 0 || row < 0 || column >= image.width || row >= image.height) return;
    const p = pixels2[row * image.width + column];
    const n = (counts.get(p) ?? 0) + 1;
    counts.set(p, n);
    if (best === void 0 || n > counts.get(best)) best = p;
  };
  for (let column = x - 1; column <= x + width; column += 1) {
    count(column, y - 1);
    count(column, y + height);
  }
  for (let row = y; row < y + height; row += 1) {
    count(x - 1, row);
    count(x + width, row);
  }
  return best;
}
function words(image) {
  return new Uint32Array(
    image.data.buffer,
    image.data.byteOffset,
    image.width * image.height
  );
}
function distance(p, q) {
  return Math.max(
    Math.abs((p & 255) - (q & 255)),
    Math.abs((p >>> 8 & 255) - (q >>> 8 & 255)),
    Math.abs((p >>> 16 & 255) - (q >>> 16 & 255)),
    Math.abs((p >>> 24) - (q >>> 24))
  );
}
var SLIGHT_CHANGE = 1;
var STRONG = 2;
function pixelChange(a, one, b, other, x, y) {
  const p = x < a.width && y < a.height ? one[y * a.width + x] : void 0;
  const q = x < b.width && y < b.height ? other[y * b.width + x] : void 0;
  if (p === q && p !== void 0) return 0;
  return p === void 0 || q === void 0 || distance(p, q) >= SLIGHT ? STRONG : SLIGHT_CHANGE;
}
var FAINT = 40;
var FAR = 2 * SLIGHT;
function changedPixels(a, b) {
  const width = Math.max(a.width, b.width);
  const height = Math.max(a.height, b.height);
  const one = words(a);
  const other = words(b);
  const change = new Uint8Array(width * height);
  for (let y = 0; y < height; y += 1)
    for (let x = 0; x < width; x += 1)
      change[y * width + x] = pixelChange(a, one, b, other, x, y);
  const masks = {
    before: new Uint8ClampedArray(width * height * 4),
    after: new Uint8ClampedArray(width * height * 4),
    both: new Uint8ClampedArray(width * height * 4)
  };
  const around2 = new Uint8Array(width * height);
  const reached = [];
  for (let i = 0; i < change.length; i += 1) {
    const x = i % width;
    const y = (i - x) / width;
    const edge = x === 0 || y === 0 || x === width - 1 || y === height - 1;
    if (edge && !change[i]) {
      around2[i] = 1;
      reached.push(i);
    }
  }
  for (let n = 0; n < reached.length; n += 1) {
    const i = reached[n];
    const x = i % width;
    for (const j of [
      x > 0 ? i - 1 : -1,
      x < width - 1 ? i + 1 : -1,
      i - width,
      i + width
    ]) {
      if (j < 0 || j >= change.length || change[j] || around2[j]) continue;
      around2[j] = 1;
      reached.push(j);
    }
  }
  const seen = new Uint8Array(width * height);
  for (let start = 0; start < change.length; start += 1) {
    if (!change[start] || seen[start]) continue;
    const run = [start];
    seen[start] = 1;
    const counts = /* @__PURE__ */ new Map();
    let ground;
    for (let n = 0; n < run.length; n += 1) {
      const i = run[n];
      const x = i % width;
      const y = (i - x) / width;
      for (const [nx, ny] of [
        [x - 1, y],
        [x + 1, y],
        [x, y - 1],
        [x, y + 1]
      ]) {
        if (nx < 0 || ny < 0 || nx >= width || ny >= height) continue;
        const j = ny * width + nx;
        if (change[j]) {
          if (!seen[j]) {
            seen[j] = 1;
            run.push(j);
          }
          continue;
        }
        if (!around2[j]) continue;
        const q = other[ny * b.width + nx];
        const count = (counts.get(q) ?? 0) + 1;
        counts.set(q, count);
        if (ground === void 0 || count > counts.get(ground)) ground = q;
      }
    }
    for (const i of run) {
      const x = i % width;
      const y = (i - x) / width;
      const p = x < a.width && y < a.height ? one[y * a.width + x] : void 0;
      const q = x < b.width && y < b.height ? other[y * b.width + x] : void 0;
      const drawsA = q === void 0 || p !== void 0 && (ground === void 0 || distance(p, ground) >= SLIGHT);
      const drawsB = p === void 0 || q !== void 0 && (ground === void 0 || distance(q, ground) >= SLIGHT);
      const mask = drawsA === drawsB ? masks.both : drawsA ? masks.before : masks.after;
      const far = p === void 0 || q === void 0 ? FAR : Math.min(distance(p, q), FAR);
      mask[i * 4 + 3] = FAINT + (255 - FAINT) * far / FAR;
    }
  }
  return { width, height, ...masks };
}
function differenceKind({ changed, throughout, regions }) {
  if (!changed) return "identical";
  if (throughout) return "throughout";
  return regions.length ? "areas" : "slight";
}
function describeDifference(reading) {
  const kind = differenceKind(reading);
  if (kind !== "areas")
    return {
      identical: "identical",
      throughout: "changed throughout",
      slight: "only slight changes"
    }[kind];
  const { changed: changedCount, moved: movedCount } = countAreas(reading.regions);
  const areas = (n) => `${n} ${n === 1 ? "area" : "areas"}`;
  if (!changedCount) return `${areas(movedCount)} moved`;
  return `${areas(changedCount).replace(" ", " changed ")}${movedCount ? `, ${movedCount} moved` : ""}`;
}
function countAreas(regions) {
  const changes = regions.filter((region) => region.kind === "changed");
  const before = changes.filter((region) => region.side === "before");
  const after = changes.filter((region) => region.side === "after");
  const shared = before.filter((p) => after.some((q) => near(p, q, 0))).length;
  return {
    changed: before.length + after.length - shared,
    moved: Math.max(
      ...["before", "after"].map(
        (side) => regions.filter((region) => region.kind === "moved" && region.side === side).length
      )
    )
  };
}
function compareImages(a, b) {
  return differingRegions(pixels(a), pixels(b));
}
function compareImagePixels(a, b) {
  return changedPixels(pixels(a), pixels(b));
}
function pixels(image) {
  const width = image.naturalWidth ?? image.width;
  const height = image.naturalHeight ?? image.height;
  const context = new OffscreenCanvas(width, height).getContext("2d", {
    willReadFrequently: true
  });
  context.drawImage(image, 0, 0);
  return context.getImageData(0, 0, width, height);
}

// runtime/file-api.js
var live2 = readPart((root) => root.document.live);
function boundFile(binding) {
  const writable = () => !offlineInteractive && live2();
  async function request(options = {}) {
    if (!writable()) throw new Error("File editing is available in live pages.");
    try {
      return await requestJson(
        pageUrl(`api/files/${encodeURIComponent(binding)}`),
        { cache: "no-store", ...options },
        "file"
      );
    } catch (error) {
      if (error instanceof LayerRefused)
        throw new Error("Leaf changed while accessing the file.");
      if (error.status === void 0)
        throw new Error("The page's server did not answer.", { cause: error });
      if (error.said === void 0)
        throw new Error(
          error.status < 400 ? "The page's server answered in a form the page cannot read." : `The page's server answered HTTP ${error.status}.`,
          { cause: error }
        );
      throw error;
    }
  }
  return {
    get writable() {
      return writable();
    },
    // The server answers a binding the page lacks as no file, keeping the console
    // clean for a designed state; the editor still shows it as unavailable.
    read: async () => {
      const file = await request();
      if (file === null) throw new Error(`No file is bound as '${binding}'.`);
      return file;
    },
    save: (snapshot) => request({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(snapshot)
    }),
    // Calls back each time an adopted state answer carries a different stamp for this
    // binding, the tab's first answer included, until the returned function stops it.
    // A stamp says only that the file may have moved; `read()`'s revision says whether
    // it did.
    watch(callback) {
      let subscribing = true;
      const stop = applicationState.select((root) => root.authoritative?.files[binding]).subscribe(() => {
        if (!subscribing) callback();
      });
      subscribing = false;
      return stop;
    }
  };
}

// runtime/llm-api.js
var live3 = readPart((root) => root.document.live);
async function generate(request) {
  if (offlineInteractive || !live3())
    throw new Error("LLM generation is available in live pages.");
  return requestJson(
    pageUrl("api/llm"),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request)
    },
    "LLM generation"
  );
}

// runtime/http-api.js
var live4 = readPart((root) => root.document.live);
function connection(name) {
  return {
    async fetch(path) {
      if (offlineInteractive || !live4())
        throw new Error("HTTP connections are available in live pages.");
      return requestJson(
        pageUrl(`api/connections/${encodeURIComponent(name)}`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path })
        },
        "HTTP connection"
      );
    }
  };
}

// runtime/widget-api.js
async function mountSample(frame, options) {
  const owner = await import("./bundle-sample.js");
  return owner.mountSample(frame, options);
}
export {
  CONTRIBUTION_ENTRY_SCHEMA,
  DISCLOSE,
  HOLDS_WORD,
  HeldReading,
  LAYOUT,
  LeafEditorView,
  LeafElement,
  PAGE_INTERFACE,
  PRESENTATION,
  PRESS,
  PRESSABLE,
  TEXT_BOX,
  TEXT_FIELD,
  aborted,
  addressableLabel,
  addressableWord,
  afterPresentation,
  afterScript,
  agentName,
  ago,
  alignText,
  allButCommandReference,
  anchorLabel,
  announce,
  answerWords,
  answeredInWords,
  atLayoutPrecision,
  atScrollEnd,
  authoredScope,
  backgroundFlash,
  beginWalk,
  bodyText,
  boundFile,
  cancelAnimation,
  cancelRender,
  capturePlace,
  claimTraversals,
  classMap,
  clearDraft,
  clockValue,
  closeLayer,
  closeNativeLayer,
  commandScope,
  keys as commands,
  commandsOn,
  compareImagePixels,
  compareImages,
  comparisonChanges,
  compoundReadingRegionId,
  connection,
  consumeAnnotations,
  contributionEntry,
  contributionItemKey,
  copyBlock,
  countAreas,
  createRef,
  currentLocationIn,
  cycledRow,
  dataBody,
  declarationFor,
  deferredArrival,
  describeDifference,
  differenceKind,
  directWorkElements,
  dragging,
  dressSamples,
  el,
  elementById,
  elementsDeclaring,
  ensureSyntaxLanguage,
  excerptWords,
  failSoft,
  fitsWhole,
  focusDestination,
  focused,
  foldBlock,
  foldDuration,
  fragmentTarget,
  frameFor,
  generate,
  generated,
  generatedElement,
  growthIsSeen,
  guard,
  handBack,
  heldGrowth,
  highlightBlocks,
  holdFocus,
  html,
  iconElement,
  iconTemplate,
  inBaseLayer,
  inChrome,
  indicate,
  initialRender,
  inlineMarkdownFragment,
  isCanonicalMediaUrl,
  isNativeLayer,
  keepView,
  keeps,
  keepsHidden,
  keepsText,
  keyed,
  labelOf,
  landInThread,
  landingInsets,
  langForPath,
  layerFact,
  layoutChanged,
  layoutPx,
  listWalkPosition,
  live,
  loadDeferred,
  loadDraft,
  loadMarkdown,
  markdownReady,
  markdownSourceOffset,
  markdownWords,
  matchesWhen,
  measure,
  motion,
  motionPreview,
  mountSample,
  move,
  navigateToDatum,
  nextAnimation,
  nextFrame,
  nextRender,
  noChange,
  nothing,
  notice,
  obligationActions,
  obligationsIn,
  offer,
  offered,
  onCurrentLocation,
  onMotionPreferenceChange,
  onUserInput,
  once,
  openLayer,
  openerOf,
  openingView,
  pageScroller,
  paintKeys,
  paintMarkdown,
  placeKeeper,
  placePageThreads,
  placesFailure,
  plainPress,
  presentContributionEntry,
  presentContributionReceipts,
  preserveReadingRegions,
  pressIsKeyboardActivation,
  projectData,
  projectedDatum,
  publishOutput,
  pushEntry,
  queueActions,
  queueItemKey,
  queueTitle,
  quietSince,
  quietWord,
  quoted,
  raiseError,
  rankAt,
  reachedForWords,
  readHistory,
  readObligations,
  readQueues,
  readThreads,
  readWork,
  reducedMotion,
  ref,
  regionScrollBehavior,
  registerContribution,
  registerReadingRegion,
  registerThreadPresentation,
  registerVisualParts,
  relabel,
  releaseOutlets,
  removeRuntimeRootStyle,
  render,
  renderMarkdown,
  renderRetired,
  repeat,
  replaceEntry,
  reportFailure,
  reportSequence,
  reportsPresented,
  reportsReady,
  restorePlace,
  retainUserIntent,
  returnDuration,
  revisionLabel,
  rove,
  rowArrows,
  rowWalk,
  saidAt,
  saveDraft,
  saying,
  says,
  scopedMediaUrl,
  scrollBehavior,
  scrollIntoReadingBand,
  scrollIntoView,
  scrollLimit,
  scrollerFor,
  searchField,
  selectableOffer,
  selectableOffered,
  sendDraft,
  setChildLists,
  setChildren,
  setRenderedChildren,
  setRuntimeRootStyle,
  shadowStage,
  shortAgo,
  showNativeLayer,
  showReadingSubject,
  shownParts,
  shownWindow,
  Z as signal,
  sizeObserver,
  styleMap,
  synNodes,
  syntax,
  tabStore,
  textNodesUnder,
  threadActions,
  threadBox,
  threadInput,
  threadSummary,
  threadSurface,
  turns as threadTurns,
  tokenLines,
  under,
  unsafeHTML,
  watchDraft,
  watchReadingRegionTransitions,
  wear,
  whenLeft,
  whileConnected,
  widgetController,
  wireInput,
  workAncestor,
  workElements,
  workRole,
  worksInside,
  wrote
};
