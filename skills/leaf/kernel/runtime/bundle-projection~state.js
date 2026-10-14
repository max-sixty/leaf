import {
  isPagePaint,
  renderQuiet
} from "./bundle-chrome.js";
import {
  authoredStates,
  widgetElement
} from "./bundle-widget-upgrade.js";
import {
  authored,
  elementById,
  inChrome,
  pageQueryAll,
  renderRetired
} from "./bundle-passage-facts.js";
import {
  PAGE_PAINT_ATTRIBUTE,
  decisionFor,
  dragHeld,
  watchDragRelease
} from "./bundle-page-paint.js";
import {
  PRESENTATION_ORDER,
  applicationPresenter,
  applicationState,
  projectionRegionsPresented,
  readPart,
  watchPresentation
} from "./bundle-semantic-state.js";
import {
  keeps
} from "./bundle-sample-visibility.js";
import {
  PRESENTATION_HELD,
  projectionOrigins
} from "./bundle-queued-work.js";

// runtime/projection/state.js
var deferred = false;
var heard = /* @__PURE__ */ new Set();
var currentProjection = readPart((root) => root.effective.projection);
var projectionDeferred = () => deferred;
function watchProjectionDeferral(moved) {
  heard.add(moved);
  return () => heard.delete(moved);
}
function setProjectionDeferred(next) {
  if (deferred === next) return;
  deferred = next;
  const round = {};
  for (const moved of [...heard]) moved(round);
}

// runtime/projection/presentation.js
function paintStateOrigins(projection) {
  const marks = new Map(
    [PAGE_PAINT_ATTRIBUTE.userOverride, PAGE_PAINT_ATTRIBUTE.reported].map((attr) => [
      attr,
      /* @__PURE__ */ new Set()
    ])
  );
  for (const { origin, unit } of projectionOrigins(authoredStates(), projection)) {
    if (origin === "restated") continue;
    const target = elementById(unit);
    if (!target || inChrome(target)) continue;
    const attr = origin === "user" ? PAGE_PAINT_ATTRIBUTE.userOverride : PAGE_PAINT_ATTRIBUTE.reported;
    marks.get(attr).add(target);
  }
  const touched = /* @__PURE__ */ new Set();
  for (const [attr, wanted] of marks) {
    for (const target of pageQueryAll(`[${attr}]`)) {
      touched.add(target);
      if (!wanted.has(target)) target.removeAttribute(attr);
    }
    for (const target of wanted) {
      touched.add(target);
      keeps(target, attr, "1");
    }
  }
  return touched;
}
function paintSettlements(widgets) {
  for (const [widgetId, { state }] of widgets) {
    const owner = widgetElement(widgetId);
    const decision = owner && decisionFor(owner.localName);
    if (!decision) continue;
    const outcome = state[decision.verb]?.detail?.outcome ?? null;
    keeps(
      owner,
      PAGE_PAINT_ATTRIBUTE.settlement,
      decision.retires[outcome] ? outcome : null
    );
    renderRetired(owner, outcome);
  }
}
var answered = readPart((root) => root.authoritative !== null);
var phase = readPart((root) => root.phase);
var currentProjection2 = readPart((root) => root.effective.projection);
var widgetStates = readPart((root) => root.effective.widgets);
function createProjectionPresentation({ onDeferredReady }) {
  let stopWatchingDrag = null;
  applicationPresenter({
    region: "projection:chrome",
    order: PRESENTATION_ORDER.projection,
    reading: () => answered() ? true : null,
    paint: paintReading
  });
  const coverage = () => {
    const root = applicationState.read();
    if (root.phase === "waiting" || root.authoritative === null || !projectionRegionsPresented([]))
      return;
    const projection = root.effective.projection;
    const records = root.effective.view?.coverage ?? [];
    const ready = records.every((record) => {
      if (record.coordinate === null) return true;
      const e = record.event;
      const target = projection.classified.get(e.kind === "undo" ? e.undoes : e.id);
      return !target || target.terminal || projectionRegionsPresented([target.e.widget]);
    });
    if (ready)
      keeps(document.body, PAGE_PAINT_ATTRIBUTE.applied, String(records.length));
  };
  let coverageQueued = false;
  const updateCoverage = () => {
    if (coverageQueued) return;
    coverageQueued = true;
    queueMicrotask(() => {
      coverageQueued = false;
      coverage();
    });
  };
  watchPresentation(updateCoverage);
  const retireProjectionCoverage = () => document.body.removeAttribute(PAGE_PAINT_ATTRIBUTE.applied);
  function watchProjectionDrag() {
    stopWatchingDrag ??= watchDragRelease(() => {
      unwatchProjectionDrag();
      onDeferredReady();
    });
  }
  function unwatchProjectionDrag() {
    stopWatchingDrag?.();
    stopWatchingDrag = null;
  }
  function presentCurrent() {
    const projection = currentProjection2();
    if (phase() === "waiting" || !answered()) {
      setProjectionDeferred(false);
      return projection;
    }
    if (dragHeld()) {
      setProjectionDeferred(true);
      watchProjectionDrag();
      return projection;
    }
    unwatchProjectionDrag();
    setProjectionDeferred(false);
    for (const entry of projection.classified.values())
      for (const id of entry.restated ?? [])
        keeps(elementById(id), PAGE_PAINT_ATTRIBUTE.restated, "1");
    paintSettlements(widgetStates());
    const originTargets = paintStateOrigins(projection);
    renderQuiet(document.body, originTargets);
    return projection;
  }
  function paintReading() {
    const projection = presentCurrent();
    return projectionDeferred() ? PRESENTATION_HELD : projection;
  }
  return {
    retireProjectionCoverage
  };
}
function shallowSigs(root) {
  const sigs = /* @__PURE__ */ new Map();
  const siblingPositions = /* @__PURE__ */ new Map();
  const isAuthored = (node) => Boolean(node.id) && authored(node)(node);
  for (const node of [root, ...root.querySelectorAll("[id]")]) {
    if (!isAuthored(node)) continue;
    const attrs = Object.fromEntries(
      [...node.attributes].filter((attribute) => !isPagePaint(attribute.name)).map((attribute) => [attribute.name, attribute.value]).sort(([left], [right]) => left.localeCompare(right))
    );
    const parent = node.parentElement;
    let positions = siblingPositions.get(parent);
    if (!positions) {
      positions = /* @__PURE__ */ new Map();
      for (const sibling of parent?.children ?? [])
        if (isAuthored(sibling)) positions.set(sibling, positions.size);
      siblingPositions.set(parent, positions);
    }
    sigs.set(
      node.id,
      JSON.stringify({
        tag: node.tagName,
        attrs,
        parent: parent && isAuthored(parent) ? parent.id : "",
        index: positions.get(node) ?? -1
      })
    );
  }
  return sigs;
}

export {
  currentProjection,
  projectionDeferred,
  watchProjectionDeferral,
  createProjectionPresentation,
  shallowSigs
};
