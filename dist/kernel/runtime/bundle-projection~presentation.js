import {
  isPagePaint,
  renderQuiet
} from "./bundle-user-intent.js";
import {
  authoredStates,
  widgetElement
} from "./bundle-keyboard~disclosure.js";
import {
  authored,
  authoredScope,
  elementById,
  inChrome,
  pageDocument,
  pageQueryAll,
  renderRetired
} from "./bundle-passage-facts.js";
import {
  PAGE_PAINT_ATTRIBUTE,
  reportPageError,
  requestJson,
  setRuntimeRootAttribute
} from "./bundle-page-paint.js";
import {
  decisionFor,
  registry,
  watchOwner
} from "./bundle-arrivals.js";
import {
  PRESENTATION_ORDER,
  applicationPresenter,
  applicationState,
  offlineData,
  offlineInteractive,
  pageUrl,
  projectionRegionsPresented,
  readPart,
  runtime,
  watchPresentation,
  whenApplicationRegionsPresented
} from "./bundle-semantic-state.js";
import {
  keeps
} from "./bundle-frame-visibility.js";
import {
  J,
  Z,
  d,
  projectionOrigins
} from "./bundle-queued-work.js";

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
var currentProjection = readPart((root) => root.effective.projection);
var widgetStates = readPart((root) => root.effective.widgets);
function createProjectionPresentation() {
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
  function presentCurrent() {
    const projection = currentProjection();
    if (phase() === "waiting" || !answered()) {
      return projection;
    }
    for (const entry of projection.classified.values())
      for (const id of entry.restated ?? [])
        keeps(elementById(id), PAGE_PAINT_ATTRIBUTE.restated, "1");
    paintSettlements(widgetStates());
    const originTargets = paintStateOrigins(projection);
    renderQuiet(document.body, originTargets);
    return projection;
  }
  function paintReading() {
    return presentCurrent();
  }
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
var outputObservers = /* @__PURE__ */ new Set();
function observeOutputs(observe) {
  outputObservers.add(observe);
  return () => outputObservers.delete(observe);
}
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
  for (const observe of outputObservers)
    observe({
      element,
      output,
      contract: declaration.contract,
      value: reading === null ? null : reading.value
    });
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
        let seen = d(selected.read);
        stopAccepted = selected.subscribe((now) => {
          if (now === seen) return;
          seen = now;
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

export {
  createProjectionPresentation,
  shallowSigs,
  requireReference,
  referencedProjection,
  acceptData,
  notifyDataSubscribers,
  observeOutputs,
  publishOutput,
  dataReader,
  joinDataDelivery,
  loadDeferred
};
