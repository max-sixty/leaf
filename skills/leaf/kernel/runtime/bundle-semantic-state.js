import {
  bindQueuedWork,
  collectReads,
  createPresentationCoordinator,
  createPresentationSchedule,
  createSemanticApplication,
  outsideReading,
  untracked
} from "./bundle-queued-work.js";

// runtime/semantic-state.js
var documentToken = Object.freeze({});
var reportPresentationFailure = (reason) => console.error("leaf: presentation failed", reason);
var presentation = createPresentationCoordinator({
  reportFailure: (reason) => reportPresentationFailure(reason)
});
var schedule = createPresentationSchedule(bindQueuedWork);
var applicationState = createSemanticApplication({
  presentation: {
    begin: (semanticEpoch) => presentation.begin(documentToken, semanticEpoch),
    // The application seals each publication as `begin` returned it.
    seal: (publication) => presentation.seal(
      /** @type {ReturnType<typeof presentation.begin>} */
      publication
    )
  }
});
var readApplication = applicationState.read;
var readPart = (derive) => applicationState.select(derive).read;
var agent = readPart((root) => root.authoritative?.agent ?? null);
var agentName = () => agent() || "the agent";
var agentLabel = () => agentName().replace(/^./, (first) => first.toUpperCase());
var projectView = applicationState.projectView;
var selectWidgets = applicationState.selectWidgets;
var attachApplicationPresentation = (region, renderer) => presentation.attach(region, renderer);
var widgetRegion = (widget, kind) => `widget:${widget}:${kind}`;
var widgetRegions = (widget) => ["render", "preparation"].map((kind) => widgetRegion(widget, kind));
var attachWidgetPresentation = (widget, kind, renderer) => presentation.attach(widgetRegion(widget, kind), renderer);
var currentWidgetParents = readPart((root) => root.effective.widgetParents);
var widgetOrder = (widget) => {
  const parents = currentWidgetParents();
  const seen = /* @__PURE__ */ new Set();
  let depth = 0;
  for (let parent = parents.get(widget); parent; parent = parents.get(parent)) {
    if (seen.has(parent)) break;
    seen.add(parent);
    depth++;
  }
  return -1 / (depth + 1);
};
var queueWidgetUpdate = (widget, update) => schedule.enqueue(
  untracked(() => widgetOrder(widget)),
  update
);
var PRESENTATION_ORDER = Object.freeze({
  projection: 0,
  thread: 1,
  asks: 2,
  queue: 3
});
var documentPresenters = [];
var publications = applicationState.select((root) => root);
var applicationPresenter = ({
  region,
  renderer = document,
  order,
  reading,
  paint,
  failSoft
}) => {
  let readingReads = /* @__PURE__ */ new Map();
  let paintReads = /* @__PURE__ */ new Map();
  let claimed;
  let owed = false;
  let following = [];
  const follow = () => {
    for (const stop of following) stop();
    following = [...paintReads].filter(([reading2]) => reading2.outside).map(
      ([reading2, seen]) => reading2.subscribe((now) => {
        if (owed || now === seen) return;
        const next = read();
        if (next !== null) void claim(next);
      })
    );
  };
  const presenter = schedule.presenter({
    attach: () => presentation.attach(region, renderer),
    order,
    paint: (value, current) => {
      owed = false;
      const reads = /* @__PURE__ */ new Map();
      paintReads = reads;
      const stretch = (run) => {
        const outcome = collectReads(run);
        if (current()) {
          for (const [part2, seen] of outcome.reads)
            if (!reads.has(part2)) reads.set(part2, seen);
          if (paintReads === reads) follow();
          if (moved(outcome.reads)) {
            const next = read();
            if (next !== null) void claim(next);
          }
        }
        if ("error" in outcome) throw outcome.error;
        return outcome.value;
      };
      const resume = (run) => (...args) => stretch(() => run(...args));
      return stretch(() => paint(value, current, resume));
    },
    failSoft
  });
  const read = () => {
    const outcome = collectReads(reading);
    readingReads = outcome.reads;
    if ("error" in outcome) throw outcome.error;
    if (moved(readingReads))
      throw new Error(`the ${region} region's reading moved a part it read`);
    return outcome.value;
  };
  const claim = (value) => {
    claimed = value;
    if (value === null) return schedule.passed();
    owed = true;
    return presenter.sync(value);
  };
  const moved = (reads) => [...reads].some(([part2, seen]) => part2.read() !== seen);
  const present = () => claim(read());
  documentPresenters.push(present);
  claimed = read();
  publications.subscribe(() => {
    const painted = !owed && moved(paintReads);
    if (!painted && !moved(readingReads)) return;
    const value = read();
    if (value === null) claimed = null;
    else if (painted || value !== claimed) void claim(value);
  });
  const disconnect = () => {
    paintReads = /* @__PURE__ */ new Map();
    follow();
    presenter.disconnect();
  };
  return Object.freeze({ present, disconnect });
};
var documentChanges = 0;
var documentChanged = () => documentChanges;
var presentDocument = () => {
  documentChanges += 1;
  for (const present of documentPresenters) void present();
  return schedule.passed();
};
var whenDocumentPresented = () => schedule.passed();
var PresentationRetentionError = class extends AggregateError {
};
var failSoftAfterRetention = (proof) => (reason) => {
  if (reason instanceof PresentationRetentionError) throw reason;
  return proof;
};
var currentEpoch = () => untracked(() => readApplication().semanticEpoch);
var currentApplicationPresentation = () => ({
  document: documentToken,
  semanticEpoch: currentEpoch()
});
var whenApplicationPresented = () => presentation.whenCurrentPresented(currentApplicationPresentation);
var applicationPresented = () => presentation.currentPresented(currentApplicationPresentation);
var whenWidgetsPresented = (widgets) => presentation.whenCurrentRegionsPresented(
  () => ({
    document: documentToken,
    semanticEpoch: currentEpoch()
  }),
  widgets.flatMap(widgetRegions)
);
var whenApplicationRegionsPresented = (regions, current) => presentation.whenCurrentRegionsPresented(
  () => current() ? {
    document: documentToken,
    semanticEpoch: currentEpoch()
  } : null,
  regions
);
var applicationRegionsPresented = (regions) => presentation.currentRegionsPresented(currentApplicationPresentation, regions);
var projectionRegionsPresented = (widgets) => applicationRegionsPresented(["projection:chrome", ...widgets.flatMap(widgetRegions)]);
var watchPresentation = presentation.subscribe;
var proofReadings = /* @__PURE__ */ new WeakSet();
var proofReading = (read) => {
  const reading = outsideReading(read, (moved) => watchPresentation(() => moved({})));
  proofReadings.add(reading);
  return reading;
};
var readsProof = (reading) => proofReadings.has(reading);
var readApplicationPresentation = presentation.read;
function setPresentationFailureReporter(report) {
  reportPresentationFailure = (reason) => report(reason, "Presentation failed");
}
var watchSemantic = (callback) => applicationState.select((root) => root.semanticEpoch).subscribe(() => callback(readApplication()));

// runtime/context.js
var PAGE_PATH = location.pathname;
var LIVE_ROOT = PAGE_PATH.endsWith("/");
var PAGE_ROOT = (
  /** @type {HTMLLinkElement | null} */
  document.querySelector('link[rel="canonical"][data-lf-runtime]')?.href ?? null
);
var served = (
  /** @type {HTMLScriptElement | null} */
  document.querySelector("script[data-lf-runtime][data-lf-server]")?.dataset
);
var DELIVERY = Object.freeze({
  layer: served?.lfLayer,
  release: served?.lfRelease,
  probe: served?.lfProbe
});
var WEBSITE_DELIVERY = DELIVERY.release !== void 0;
var layerRoot = (doc) => doc.querySelector("script[data-lf-runtime][data-lf-entry]")?.dataset.lfEntry.replace(/leaf\.js$/, "") ?? "";
var SHARE_ROOT = served?.lfShareUrl;
function shareUrl() {
  const url = new URL(SHARE_ROOT);
  url.pathname = location.pathname;
  const access = [...url.searchParams];
  url.search = location.search;
  for (const [key, value] of access) url.searchParams.set(key, value);
  url.hash = location.hash;
  return url.href;
}
var pageUrl = (path) => new URL(path, PAGE_ROOT).href;
var offlineMarker = document.querySelector(
  'script[type="application/json"][data-lf-runtime][data-lf-offline]'
);
var offlinePayload = offlineMarker ? JSON.parse(offlineMarker.textContent || "null") : null;
var annotationMode = document.body.getAttribute("data-annotations") ?? "overlay";
var offlineInteractive = offlinePayload !== null;
var offlineState = () => offlineInteractive ? structuredClone(offlinePayload.state) : null;
var offlineData = () => offlineInteractive ? offlinePayload.data : null;
var runtimeModule = (path) => offlineInteractive ? `leaf:${path.startsWith("/") ? path : `/${path}`}` : path;
var servedLayerRoot = layerRoot(document);
var runtimeResource = (path) => {
  if (!offlineInteractive)
    return servedLayerRoot ? new URL(`.${path}`, new URL(servedLayerRoot, document.baseURI)).href : path;
  const located = new URL(path, document.baseURI);
  const resource = offlinePayload.resources[located.pathname];
  if (typeof resource !== "string")
    throw new Error(`Leaf's interactive export is missing ${path}`);
  return resource + located.hash;
};
var part = {
  active: readPart((root) => root.authoritative?.active ?? null),
  browser: readPart((root) => root.authoritative?.browser ?? null),
  revision: readPart((root) => root.document.revision),
  live: readPart((root) => root.document.live),
  stamp: readPart((root) => root.document.stamp ?? null),
  data: readPart((root) => root.data),
  seq: readPart((root) => root.authoritative?.browser.basis.through_seq ?? null),
  reading: readPart((root) => root.authoritative?.reading ?? null),
  state: readPart((root) => root.authoritative),
  phase: readPart((root) => root.phase),
  versions: readPart((root) => root.authoritative?.versions ?? []),
  workflows: readPart((root) => root.effective.workflows),
  view: readPart((root) => root.effective.view),
  undo: readPart((root) => root.effective.view?.undo ?? []),
  todos: readPart((root) => root.authoritative?.browser.todos ?? []),
  receipts: readPart((root) => root.authoritative?.browser.receipts ?? []),
  revisionLabels: readPart((root) => root.authoritative?.revision_labels)
};
var runtime = {
  get active() {
    return part.active();
  },
  get browser() {
    return part.browser();
  },
  // Whether the document shows the active revision. Activation only moves forward
  // (the publisher refuses an answer whose active revision went back), so a document
  // showing any other revision is behind it: an older pin, or a tab the agent has
  // since revised.
  get showsActive() {
    return runtime.active !== null && runtime.currentRevision === runtime.active.revision;
  },
  get currentLabel() {
    return part.live() && runtime.showsActive ? runtime.active.label : runtime.currentStamp === null ? null : `v${runtime.currentStamp}`;
  },
  get currentRevision() {
    return part.revision();
  },
  get currentStamp() {
    return part.live() && runtime.showsActive ? runtime.active.version : part.stamp();
  },
  get data() {
    return part.data();
  },
  get lastEventSeq() {
    return part.seq();
  },
  get reading() {
    return part.reading();
  },
  sessionReference: null,
  // Whether the server's latest answer refused this tab's key (`layer-client.js`).
  keyRefused: false,
  get state() {
    return part.state();
  },
  // The layer's `registry.json`, which fills this once it loads (registry.js).
  registry: (
    /** @type {import("../../../../build/browser/application.ts").SemanticDocument["registry"] & Record<string, any>} */
    {}
  ),
  get statePhase() {
    return part.phase();
  },
  get versions() {
    return part.versions();
  },
  get workflows() {
    return part.workflows();
  },
  // The shown revision's server view, less its basis, as the publisher resolved it.
  get view() {
    return part.view();
  },
  // The gestures that can still be taken back, newest first; empty between versions.
  get undo() {
    return part.undo();
  },
  get todos() {
    return part.todos();
  },
  // The events the server has admitted from this tab's attempts.
  get receipts() {
    return part.receipts();
  }
};
var revisionLabel = (revision) => part.revisionLabels()[revision];

export {
  applicationState,
  readApplication,
  readPart,
  agentName,
  agentLabel,
  projectView,
  selectWidgets,
  attachApplicationPresentation,
  attachWidgetPresentation,
  queueWidgetUpdate,
  PRESENTATION_ORDER,
  applicationPresenter,
  documentChanged,
  presentDocument,
  whenDocumentPresented,
  PresentationRetentionError,
  failSoftAfterRetention,
  whenApplicationPresented,
  applicationPresented,
  whenWidgetsPresented,
  whenApplicationRegionsPresented,
  applicationRegionsPresented,
  projectionRegionsPresented,
  watchPresentation,
  proofReading,
  readsProof,
  readApplicationPresentation,
  setPresentationFailureReporter,
  watchSemantic,
  LIVE_ROOT,
  PAGE_ROOT,
  DELIVERY,
  WEBSITE_DELIVERY,
  layerRoot,
  SHARE_ROOT,
  shareUrl,
  pageUrl,
  annotationMode,
  offlineInteractive,
  offlineState,
  offlineData,
  runtimeModule,
  runtimeResource,
  runtime,
  revisionLabel
};
