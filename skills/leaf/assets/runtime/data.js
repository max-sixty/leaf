/* The accepted external data and its watchers.

   The browser orders data readings by when the server took them, independently of
   the log sequence, because overlapping poll and POST responses can order the authorities
   differently. `watchData(widget, input, callback)` delivers a clone of `{source,
   contract, revision, run, updated, value, origin}`, or `null` while the bound source has no
   readable value. Subscriptions pause while their owner is absent, and a return
   delivers by the rule every returning paint follows (`readingPaint` in
   `presence.js`), which also reports a failing callback once and keeps its
   subscription. Contract, publication, or validity changes redeliver; overlapping
   reads await the same in-flight rendering before stamping the version presented. Its
   synchronous time readings refresh independently of data delivery. The returned
   cleanup's `refresh()` repaints the last delivered reading through the same clock
   tracking, without admitting or delivering a newer source. Modules project the
   result into the authored seat; they do not fetch it, mutate the accepted copy, or keep a
   hidden current-value map of their own.*/

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
        reading.revision ?? null,
        reading.run ?? null,
        reading.error ?? null,
        Object.hasOwn(reading, "value"),
      ])
    : null;
}

export async function notifyDataSubscribers() {
  const version = runtime.data.version;
  const current = [...subscriptions];
  for (const subscription of current) subscription.notify();
  const regions = current.map((subscription) => subscription.region);
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

// A source value remains the server snapshot's to own. Subscribers name one input on
// their own widget; the declaration supplies its contract and the attribute where this
// page bound a concrete source. They receive a fresh JSON clone immediately, then
// when that source reading changes. Synchronous time readings also refresh the paint
// when their displayed value changes. A module cannot mutate the accepted snapshot,
// and a newly activated seat need not wait for a later state read.
// `projectData` remains the rendering boundary: this helper delivers records but writes no
// DOM and keeps no widget-specific cache.
export function watchData(element, input, callback) {
  const declaration = registry[element.localName]?.["x-data"]?.[input];
  if (!declaration)
    throw new Error(
      `watchData(${element.localName}, ${input}) input is not declared by this widget`,
    );
  // Markup owns the binding. Capture it at mount so module code cannot turn a live
  // attribute mutation into an unvalidated rebind. Version activation mounts a new
  // element and therefore establishes a new subscription when authored markup changes.
  const source = element.getAttribute(declaration.source);
  const paint = readingPaint(element, callback);
  const selectedSource = applicationState.select((root) =>
    source && Object.hasOwn(root.data.sources, source)
      ? root.data.sources[source]
      : null,
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
  // A null delivery stands until the accepted source reading changes, including
  // recovery from an incompatible contract without a new content revision.
  const deliver = (snapshot, identity) => {
    if (paint.owes(identity)) {
      if (snapshot)
        snapshot.origin = {
          input,
          source,
          contract: declaration.contract,
          revision: snapshot.revision,
        };
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
        `data source ${source} carries contract ${sourceStore.contract}; ` +
          `watchData(${element.localName}, ${input}) requires ${declaration.contract}`,
      );
    // The server validates values once. An incompatible named contract or an
    // invalid/missing value clears this seat, keeping its subscription for recovery.
    if (incompatible || !source || !sourceStore || !Object.hasOwn(sourceStore, "value"))
      return deliver(null, identity);
    return deliver({ source, ...sourceStore }, identity);
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
