/* Accepted external values, mounted-widget outputs, and their typed watchers.

   The browser orders data readings by when the server took them, independently of
   the log sequence, because overlapping poll and POST responses can order the authorities
   differently. `watchData(widget, input, callback)` delivers a clone of `{source,
   contract, revision, run, updated, value, origin}`, or `null` while the bound source has no
   readable value. A widget-output binding receives `{contract, value, origin}` with
   derived widget provenance, without a server source, revision or run. Outputs join
   the same immutable application publication and presentation barrier as sources.
   Subscriptions pause while their owner is absent, and a return
   delivers by the rule every returning paint follows (`readingPaint` in
   `presence.js`), which also reports a failing callback once and keeps its
   subscription. Contract, publication, or validity changes redeliver; overlapping
   reads await the same in-flight rendering before stamping the version presented. Its
   synchronous time readings refresh independently of data delivery. The returned
   cleanup's `refresh()` repaints the last delivered reading through the same clock
   tracking, without admitting or delivering a newer source. Modules project the
   result into the authored seat; they do not fetch it, mutate the accepted copy, or keep a
   hidden current-value map of their own.*/

import { outsideReading, untracked } from "/vendor/browser-runtime.js";
import { offlineData, offlineInteractive, pageUrl, runtime } from "./context.js";
import {
  applicationState,
  attachApplicationPresentation,
  whenApplicationRegionsPresented,
} from "./semantic-state.js";
import { PAGE_PAINT_ATTRIBUTE } from "./page-paint.js";
import { setRuntimeRootAttribute } from "./root-state.js";
import { registry } from "./registry.js";
import { reportPageError, requestJson } from "./layer-client.js";
import { watchOwner } from "./arrivals.js";
import { readingPaint } from "./presence.js";
import { referencedProjection, requireReference } from "./references.js";

export function acceptData(candidate, taken) {
  return applicationState.acceptData(candidate, taken);
}

const subscriptions = new Set();
let subscriptionSequence = 0;

// Equality of the accepted publication, including a same-value rerun. Content
// revision remains the coordinate for origins and deferred requests; a changed
// contract or validation result also changes what this subscriber can receive.
function readingIdentity(reading) {
  return reading
    ? JSON.stringify([
        reading.contract,
        reading.revision === undefined ? reading.value : null,
        reading.revision ?? null,
        reading.run ?? null,
        reading.error ?? null,
        Object.hasOwn(reading, "value"),
      ])
    : null;
}

export async function notifyDataSubscribers() {
  const version = runtime.data.version;
  deliveries += 1;
  const round = {};
  for (const delivered of [...deliveryListeners]) delivered(round);
  const current = [...subscriptions];
  for (const subscription of current) subscription.notify();
  const regions = current.flatMap((subscription) => subscription.regions);
  await whenApplicationRegionsPresented(
    regions,
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
      `watchData(${element.localName}, ${input}) input is not declared by this widget`,
    );
  return declaration;
};

// Mounted widgets own their derived values. The publication holds the immutable
// reading, while this weak lifetime record only lets a retained node return with it.
const outputOwners = new WeakMap();
const outputKeys = new WeakMap();
let outputSequence = 0;
function outputKey(element) {
  if (!outputKeys.has(element)) outputKeys.set(element, `output:${++outputSequence}`);
  return outputKeys.get(element);
}
export function publishOutput(element, output, value) {
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
  if (declaration.reference)
    requireReference("watchData", element, declaration.reference);
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

// A `LeafElement`'s reader of one bound input (leaf-element.js): the value `watchData`
// would deliver for the accepted source reading, read through a selection of that
// source, so a render that reads it is drawn again when the source moves. The binding
// is captured at the first read, as `watchData` captures it at mount.
export function dataReader(element, input) {
  const declaration = declaredInput(element, input);
  const { source, widget, selected, snapshot } = inputBinding(element, declaration);
  // What the element shows moves only as state application delivers, as a `watchData`
  // subscription's staged paint does, so a reading accepted for a revision still being
  // activated never draws into the document it replaces. The first read takes the
  // accepted reading, as a subscription's mount delivery does.
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
    (moved) => {
      deliveryListeners.add(moved);
      return () => deliveryListeners.delete(moved);
    },
  );
  if (!widget) stagedReadings.add(selected);
  let reported = null;
  return () => {
    // The accepted reading claims the element's region inside the publication that
    // accepts it; the delivered one draws.
    selected.read();
    const sourceStore = /** @type {{contract: string, revision?: string} | null} */ (
      widget ? selected.read() : delivered.read()
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
    return structuredClone(snapshot(sourceStore, input));
  };
}

// A renderer that draws data as it reads it holds the data version until its regions
// present, as a `watchData` subscription does: a widget's render and the preparation
// its draw starts (`present()`). Its readers hear the delivery itself.
let deliveries = 0;
const deliveryListeners = new Set();
// The accepted readings a `LeafElement` follows to claim its region, not to draw.
const stagedReadings = new WeakSet();
export const stagesOnly = (reading) => stagedReadings.has(reading);
export function joinDataDelivery(regions) {
  const subscription = { regions, notify() {} };
  subscriptions.add(subscription);
  return () => subscriptions.delete(subscription);
}

// A source value remains the server snapshot's to own. Subscribers name one input on
// their own widget; the declaration supplies its contract and the attribute where this
// page bound a concrete source. They receive a fresh JSON clone immediately, then
// when that source reading changes. Synchronous time readings also refresh the paint
// when their displayed value changes. A module cannot mutate the accepted snapshot,
// and a newly activated seat need not wait for a later state read.
// `projectData` remains the rendering boundary: this helper delivers records but writes no
// DOM and keeps no widget-specific cache.
export function watchData(element, input, callback) {
  const declaration = declaredInput(element, input);
  // Markup owns the binding. Capture it at mount so module code cannot turn a live
  // attribute mutation into an unvalidated rebind. Version activation mounts a new
  // element and therefore establishes a new subscription when authored markup changes.
  const {
    source,
    widget,
    selected: selectedSource,
    snapshot,
  } = inputBinding(element, declaration);
  const paint = readingPaint(element, callback);
  let completion = Promise.resolve();
  const region = `data:${element.id}:${input}:${++subscriptionSequence}`;
  let presentation = null;
  const subscription = { regions: [region], notify: () => notifySelected() };
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
  // A null delivery stands until the accepted source reading changes, including
  // recovery from an incompatible contract without a new content revision.
  const deliver = (snapshot, identity) => {
    if (paint.owes(identity)) {
      const rendering = paint(identity, structuredClone(snapshot));
      // The paint reported a failed callback; it does not hold the data version back.
      completion = Promise.resolve(rendering).catch(() => {});
    }
    return completion;
  };
  const update = (sourceStore) => {
    const identity = readingIdentity(sourceStore);
    const incompatible = sourceStore && sourceStore.contract !== declaration.contract;
    if (incompatible && paint.owes(identity))
      reportPageError(
        `${source ? `data source ${source}` : `widget output ${widget}.${declaration.output}`} carries contract ${sourceStore.contract}; ` +
          `watchData(${element.localName}, ${input}) requires ${declaration.contract}`,
      );
    // The server validates values once. An incompatible named contract or an
    // invalid/missing value clears this seat, keeping its subscription for recovery.
    if (incompatible || !sourceStore || !Object.hasOwn(sourceStore, "value"))
      return deliver(null, identity);
    return deliver(snapshot(sourceStore, input), identity);
  };
  const stage = (sourceStore) => {
    const identity = readingIdentity(sourceStore);
    // A source can return to the reading already on screen while a later one is
    // staged; that staged reading must be replaced rather than left to paint.
    if (!pendingDelivery && !paint.owes(identity)) return;
    // The new ticket releases a staged one that never painted.
    pendingDelivery = { sourceStore, ticket: presentation.present(identity) };
  };
  function notifySelected() {
    const pending = pendingDelivery;
    if (!pending) return;
    pendingDelivery = null;
    pending.ticket.resolve(update(pending.sourceStore));
  }
  // A publisher selection captures this mount's source. Its initial subscription call
  // is the mount delivery; later accepted publications stage the selected value and its
  // presentation ticket synchronously, before that semantic epoch seals. Notification
  // starts the staged paint only after activation has retained this document. A
  // callback that fails, on its first reading or any later one, is reported by its paint
  // (`readingPaint`) and keeps its subscription, so the next changed reading draws again.
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
      // Derived values are produced while painting the retained document, rather
      // than by a server answer awaiting activation. Their claimed region starts
      // after this publication, and joins the same data presentation barrier.
      if (widget) queueMicrotask(notifySelected);
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

// A deferred value's identity belongs to the delivered manifest. A replacement can be
// accepted before its subscriber renders; loading through that older manifest must not
// fetch a same-key deferred value from the replacement.
export async function loadDeferred(manifest, key) {
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
