/* Accepted external values, mounted-widget outputs, and their typed readers.

   The browser orders data readings by when the server took them, independently of
   the log sequence, because overlapping poll and POST responses can order the authorities
   differently. A `LeafElement` reads a bound input through `dataReader`, which yields
   one copy a delivery of `{source, contract, revision, run, updated, value, origin}`,
   or `null` while the bound source has no readable value, and hands the widget only its
   `value` (leaf-element.js, "Bound values"). A widget-output binding yields
   `{contract, value, origin}` with derived-widget provenance, without a fabricated
   source revision or run. Each object value names the snapshot that supplied it
   (`suppliedSnapshot`), so whoever holds the value can name its revision. Outputs join
   the immutable application publication and the same presentation barrier as sources.
   What a source shows moves only as state application delivers, and each element that
   draws data holds the data version until its region has drawn the delivery
   (`joinDataDelivery`). Modules draw the value into the authored seat; they do not
   fetch it, mutate the accepted copy, or keep a hidden current-value map of their own.*/

import { computed, signal, untracked } from "/runtime/framework.js";
import { offlineData, offlineInteractive, pageUrl, runtime } from "./context.js";
import { applicationState, whenApplicationRegionsPresented } from "./semantic-state.js";
import { PAGE_PAINT_ATTRIBUTE } from "./page-paint.js";
import { setRuntimeRootAttribute } from "./root-state.js";
import { registry } from "./registry.js";
import { watchOwner } from "./arrivals.js";
import { referencedProjection, requireReference } from "./references.js";
import { reportPageError, requestJson } from "./layer-client.js";
import { tick } from "./version-signal.js";
import { OUTPUT, outputProducer, refuseOutput } from "./widget-output.js";
export { publishOutput } from "./widget-output.js";
import { attachDeferredLoader } from "./deferred-value.js";
export { loadDeferred } from "./deferred-value.js";

window.addEventListener(OUTPUT, (event) => {
  const element = outputProducer(event);
  if (!element) return;
  try {
    const { output, value } = /** @type {CustomEvent} */ (event).detail;
    acceptOutput(element, output, value);
  } catch (error) {
    refuseOutput(event, error);
  }
});

export function acceptData(candidate, taken) {
  return applicationState.acceptData(candidate, taken);
}

// The regions that hold the data version until they have drawn a delivery.
const joined = new Set();

export async function notifyDataSubscribers() {
  const version = runtime.data.version;
  tick(deliveries);
  await whenApplicationRegionsPresented(
    [...joined],
    () => runtime.data.version === version,
  );
  // The version is presented only once every subscriber has settled, and the state
  // answer carrying it is applied (`markStateApplied`) only after this returns. A
  // rejected package render is reported at its own boundary rather than turning every
  // later state read into the same page-wide failure. A data-only page therefore
  // cannot be read while an asynchronous projection is still pending.
  if (version !== null && runtime.data.version === version)
    setRuntimeRootAttribute(document.body, PAGE_PAINT_ATTRIBUTE.dataVersion, version);
}

const declaredInput = (element, input) => {
  const declaration = registry[element.localName]?.["x-data"]?.[input];
  if (!declaration)
    throw new Error(
      `<${element.localName}> input ${input} is not declared by this widget`,
    );
  return declaration;
};

// A check subscribes before widgets run and keeps the values it exercises. The
// production runtime retains no output history and does no schema validation here.
const outputObservers = new Set();
export function observeOutputs(observe) {
  outputObservers.add(observe);
  return () => outputObservers.delete(observe);
}

// Mounted widgets own their derived values. The publication holds the immutable
// reading, while this weak lifetime record only lets a retained node return with it.
const outputOwners = new WeakMap();
const outputKeys = new WeakMap();
let outputSequence = 0;
function outputKey(element) {
  if (!outputKeys.has(element)) outputKeys.set(element, `output:${++outputSequence}`);
  return outputKeys.get(element);
}
function acceptOutput(element, output, value) {
  const declaration = registry[element.localName]?.["x-output"]?.[output];
  if (!declaration)
    throw new Error(
      `publishOutput(${element.localName}, ${output}) output is not declared by this widget`,
    );
  if (!element.id) throw new Error("publishOutput requires a widget id");
  let owner = outputOwners.get(element);
  if (!owner) {
    owner = { values: new Map(), connected: false };
    outputOwners.set(element, owner);
    watchOwner(element, {
      connect() {
        owner.connected = true;
        for (const [name, reading] of owner.values)
          applicationState.publishOutput(outputKey(element), name, reading);
      },
      disconnect() {
        owner.connected = false;
        for (const name of owner.values.keys())
          applicationState.publishOutput(outputKey(element), name, null);
      },
    });
  }
  const reading =
    value === null
      ? null
      : { contract: declaration.contract, value: structuredClone(value) };
  for (const observe of outputObservers)
    observe({
      element,
      output,
      contract: declaration.contract,
      value: reading === null ? null : reading.value,
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
      `<${element.localName}> input binds both an external source and widget output`,
    );
  if (declaration.reference) requireReference("data", element, declaration.reference);
  const selected = applicationState.select((root) => {
    if (source)
      return Object.hasOwn(root.data.sources, source)
        ? root.data.sources[source]
        : null;
    if (!widget) return null;
    const producer = referencedProjection(element, declaration.reference, widget);
    if (!producer) return null;
    const key = outputKey(producer);
    const outputs = Object.hasOwn(root.outputs, key) ? root.outputs[key] : null;
    return outputs && Object.hasOwn(outputs, declaration.output)
      ? outputs[declaration.output]
      : null;
  });
  const snapshot = (reading, input) =>
    source
      ? {
          source,
          ...reading,
          origin: {
            input,
            source,
            contract: declaration.contract,
            revision: reading.revision,
          },
        }
      : { ...reading, origin: { derived: [{ widget }] } };
  return { source, widget, selected, snapshot };
}

// The snapshot each delivered object value came from. An object is one delivery's copy,
// so the lookup is exact, and it lasts as long as something holds the value.
const supplied = new WeakMap();
/** The snapshot that supplied a delivered object `value`, or undefined. */
export const suppliedSnapshot = (value) => supplied.get(value);

// Whether the markup binds a declared input, to a source or to a widget's output.
export const bindsInput = (element, { source, reference }) =>
  Boolean(
    (source && element.getAttribute(source)) ||
    (reference && element.getAttribute(reference)),
  );

// Whether `element` binds a page data source while the page has read no data yet.
// Until the first state answer is accepted, a source has no reading because none has
// been read, not because it holds none, so an element drawing it then would draw "no
// data" and move its contents when the data came (leaf-element.js, `shouldUpdate`). An
// input bound to another widget's output, or a declared source the element doesn't
// name, waits for nothing. The acceptance draws the element with the accepted reading,
// as any element's first read takes it. A page whose first read brought no state
// settles offline, and its elements draw then, saying their sources hold nothing,
// since no answer is coming to fill them.
const dataRead = applicationState.select(
  (root) => root.data.version !== null || root.phase === "offline",
);
/** @param {Element} element */
export function awaitsData(element) {
  return (
    Object.values(registry[element.localName]?.["x-data"] ?? {}).some(
      (declaration) => declaration.source && element.getAttribute(declaration.source),
    ) && !dataRead.read()
  );
}

// A `LeafElement`'s reader of one bound input (leaf-element.js): the delivered source
// reading, read through a selection of that source, so a render that reads it is drawn
// again when the source moves. Markup owns the binding, captured at the first read, so
// module code cannot turn a live attribute mutation into an unvalidated rebind; a
// revision that rebinds mounts a new element.
export function dataReader(element, input, accepted) {
  const declaration = declaredInput(element, input);
  const { source, widget, selected, snapshot } = inputBinding(element, declaration);
  // What the element shows moves only as state application delivers, so a reading
  // accepted for a revision still being activated never draws into the document it
  // replaces. The first read takes the accepted reading.
  let stopAccepted;
  const delivered = computed(
    () => {
      deliveries.value;
      return untracked(selected.read);
    },
    {
      watched() {
        let seen = untracked(selected.read);
        stopAccepted = selected.subscribe((now) => {
          if (now === seen) return;
          seen = now;
          accepted();
        });
      },
      unwatched() {
        stopAccepted?.();
        stopAccepted = null;
      },
    },
  );
  let reported = null;
  let copied = { store: null, value: null };
  return () => {
    // The accepted reading claims the element's region inside the publication that
    // accepts it; the delivered one draws.
    const sourceStore = /** @type {{contract: string, revision?: string} | null} */ (
      widget ? selected.read() : delivered.value
    );
    const incompatible = sourceStore && sourceStore.contract !== declaration.contract;
    if (incompatible && reported !== sourceStore) {
      reported = sourceStore;
      reportPageError(
        `${source ? `data source ${source}` : `widget output ${widget}.${declaration.output}`} carries contract ${sourceStore.contract}; ` +
          `<${element.localName}> input ${input} requires ${declaration.contract}`,
      );
    }
    if (incompatible || !sourceStore || !Object.hasOwn(sourceStore, "value"))
      return null;
    // One copy a delivery: a render that reads it again gets the same value, so a widget
    // tells a new delivery by identity, and none can mutate the accepted snapshot.
    if (sourceStore !== copied.store) {
      copied = {
        store: sourceStore,
        value: structuredClone(snapshot(sourceStore, input)),
      };
      const { value } = copied.value;
      if (value !== null && typeof value === "object") {
        supplied.set(value, copied.value);
        if (source) attachDeferredLoader(value, readDeferred.bind(null, copied.value));
      }
    }
    return copied.value;
  };
}

// A renderer that draws data as it reads it holds the data version until its region
// presents; its readers hear the delivery itself.
const deliveries = signal(0);
export function joinDataDelivery(region) {
  joined.add(region);
  return () => joined.delete(region);
}

// A deferred value's identity belongs to the delivered manifest, which the widget names
// by the value it drew. A replacement can be accepted before its subscriber renders;
// loading through that older manifest must not fetch a same-key deferred value from the
// replacement.
async function readDeferred(manifest, key) {
  const { source, revision } = manifest;
  const current = () => {
    const reading = /** @type {{revision?: string, contract?: unknown} | undefined} */ (
      runtime.data.sources[source]
    );
    return (
      reading?.revision === revision &&
      reading.contract === manifest.contract &&
      Object.hasOwn(reading, "value")
    );
  };
  if (!current())
    throw new Error(
      `source ${source} revision ${revision} changed before loading deferred ${key}`,
    );
  if (offlineInteractive) {
    const records = registry.$data.contracts[manifest.contract].records;
    const item = offlineData().sources[source].value[records.items].find(
      (item) => item[records.key] === key,
    );
    if (!item)
      throw new Error(`unknown record key '${key}' in data source '${source}'`);
    if (!Object.hasOwn(item, records.deferred))
      throw new Error(
        `record '${key}' in data source '${source}' has no deferred field '${records.deferred}'`,
      );
    return structuredClone(item[records.deferred]);
  }
  const params = new URLSearchParams({ source, source_revision: revision, key });
  const answer = await requestJson(
    pageUrl(`api/deferred?${params}`),
    {},
    "deferred value",
  );
  if (!current())
    throw new Error(
      `source ${source} revision ${revision} changed while loading deferred ${key}`,
    );
  return structuredClone(answer.value);
}
