/* The accepted external data and its watchers.

   The browser keeps the accepted data revision independently from `lastEventSeq`,
   because overlapping poll and POST responses can order the authorities differently.
   `watchData(widget, input, callback)` delivers a clone of `{source, contract,
   revision, updated, value, origin}` for current, a clone with `snapshot`, `label`, and
   optional `lines` for a selected capture, or `null` before a bound current value
   exists. It redelivers only when that source revision changes; overlapping reads await
   the same in-flight rendering before stamping readiness. Its synchronous time readings
   refresh independently of data delivery. Modules project the result into the authored
   seat; they do not fetch it, mutate the accepted copy, or keep a hidden current-value
   map of their own.*/

import { runtime } from "./context.js";
import {
  applicationState,
  attachApplicationPresentation,
  whenApplicationRegionsPresented,
} from "./semantic-state.js";
import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";
import { registry } from "./registry.js";
import { clocked } from "./presence.js";
import { reportPageError, sameDelivery } from "./layer-client.js";

export function acceptData(candidate) {
  if (
    !candidate ||
    typeof candidate !== "object" ||
    Array.isArray(candidate) ||
    !Number.isInteger(candidate.revision) ||
    candidate.revision < 0 ||
    !candidate.sources ||
    typeof candidate.sources !== "object" ||
    Array.isArray(candidate.sources)
  )
    throw new TypeError(
      "state data must carry a non-negative integer revision and sources",
    );
  return applicationState.acceptData(candidate);
}

const subscriptions = new Set();
let subscriptionSequence = 0;

export async function notifyDataSubscribers() {
  const revision = runtime.data.revision;
  const current = [...subscriptions];
  for (const subscription of current) subscription.notify();
  const regions = current.map((subscription) => subscription.region);
  await whenApplicationRegionsPresented(
    regions,
    () => runtime.data.revision === revision,
  );
  // The revision becomes a readiness fact only after every subscriber has settled. A
  // rejected package render is reported at its own boundary rather than turning every
  // later state read into the same page-wide failure. Render checks and export compare
  // this stamp with the server snapshot, so a data-only page cannot be read while an
  // asynchronous projection is still pending.
  if (revision >= 0 && runtime.data.revision === revision)
    document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.dataRevision, String(revision));
}

// A source value remains the server snapshot's to own. Subscribers name one input on
// their own widget; the declaration supplies its contract and the attribute where this
// page bound a concrete source. They receive a fresh JSON clone immediately, then
// when that source revision changes. Synchronous time readings also refresh the paint
// when their displayed value changes. A module cannot mutate the accepted snapshot,
// and a newly activated seat need not wait for a later state read.
// `projectData` remains the rendering boundary: this helper delivers records but writes no
// DOM and keeps no widget-specific cache.
export function watchData(element, input, callback) {
  if (!(element instanceof Element))
    throw new TypeError("watchData element must be a widget element");
  if (typeof input !== "string" || !input)
    throw new TypeError("watchData input must be a non-empty string");
  if (typeof callback !== "function")
    throw new TypeError(
      `watchData(${element.localName}, ${input}) callback must be a function`,
    );
  const declaration = registry[element.localName]?.["x-data"]?.[input];
  if (!declaration)
    throw new Error(
      `watchData(${element.localName}, ${input}) input is not declared by this widget`,
    );
  // Markup owns the binding and optional immutable selection. Capture both at mount so
  // module code cannot turn a live attribute mutation into an unvalidated rebind.
  // Version activation mounts a new element and therefore establishes a new
  // subscription when authored markup changes.
  const source = element.getAttribute(declaration.source);
  const selected = declaration.snapshot
    ? element.getAttribute(declaration.snapshot)
    : null;
  const paint = clocked(element, callback);
  const selectedSource = applicationState.select((root) =>
    source && Object.hasOwn(root.data.sources, source)
      ? root.data.sources[source]
      : null,
  );
  let delivered = false;
  let deliveredRevision;
  let completion = Promise.resolve();
  const region = `data:${element.id}:${input}:${++subscriptionSequence}`;
  const presentation = attachApplicationPresentation(region, element);
  const subscription = { region, notify: () => notifySelected() };
  let stopSelection;
  let pendingDelivery = null;
  let stopped = false;
  function stop() {
    if (stopped) return;
    stopped = true;
    subscriptions.delete(subscription);
    stopSelection?.();
    pendingDelivery?.settle();
    pendingDelivery = null;
    paint.stop();
    presentation.disconnect();
  }
  const deliver = (snapshot, mounting = false) => {
    const revision = snapshot?.revision ?? null;
    if (!delivered || deliveredRevision !== revision) {
      if (snapshot)
        snapshot.origin = {
          input,
          source,
          contract: declaration.contract,
          revision: snapshot.revision,
          data_revision: runtime.data.revision,
          ...(selected ? { snapshot: selected } : {}),
        };
      // Claim this source revision before invoking package code so a synchronous
      // failure or re-entrant notification cannot redeliver the same failed value.
      delivered = true;
      deliveredRevision = revision;
      const rendering = paint(structuredClone(snapshot));
      completion = Promise.resolve(rendering).catch((error) => {
        reportPageError(`data subscriber failed: ${error?.message ?? error}`);
        if (mounting) stop();
      });
    }
    return completion;
  };
  const update = (sourceStore, mounting = false) => {
    if (!source) {
      return deliver(null, mounting);
    }
    if (sourceStore && sourceStore.contract !== declaration.contract)
      throw new Error(
        `watchData(${element.localName}, ${input}) expected contract ${declaration.contract}, ` +
          `but source ${source} carries ${sourceStore.contract}`,
      );
    if (!sourceStore) {
      return deliver(null, mounting);
    }
    if (selected) {
      const snapshot = sourceStore.snapshots?.[selected];
      if (!snapshot)
        throw new Error(
          `watchData(${element.localName}, ${input}) source ${source} has no snapshot ${selected}`,
        );
      return deliver(
        {
          source,
          contract: sourceStore.contract,
          revision: Number(selected),
          snapshot: selected,
          ...snapshot,
        },
        mounting,
      );
    }
    if (!Object.hasOwn(sourceStore, "value")) {
      return deliver(null, mounting);
    }
    const snapshot = {
      source,
      contract: sourceStore.contract,
      revision: sourceStore.revision,
      updated: sourceStore.updated,
      value: sourceStore.value,
    };
    if (Object.hasOwn(sourceStore, "label")) snapshot.label = sourceStore.label;
    if (Object.hasOwn(sourceStore, "lines")) snapshot.lines = sourceStore.lines;
    return deliver(snapshot, mounting);
  };
  const updateSafely = (sourceStore) => {
    try {
      return update(sourceStore);
    } catch (error) {
      reportPageError(`data subscriber failed: ${error?.message ?? error}`);
    }
  };
  const selectedRevision = (sourceStore) =>
    sourceStore ? (selected ? Number(selected) : sourceStore.revision) : null;
  const stage = (sourceStore) => {
    const revision = selectedRevision(sourceStore);
    if (delivered && deliveredRevision === revision) return;
    pendingDelivery?.settle();
    let settle;
    const pending = {
      sourceStore,
      completion: new Promise((resolve) => {
        settle = resolve;
      }),
      settle: (rendering) => settle(rendering),
    };
    pendingDelivery = pending;
    void presentation.present(revision, pending.completion);
  };
  function notifySelected() {
    const pending = pendingDelivery;
    if (!pending) return completion;
    pendingDelivery = null;
    pending.settle(updateSafely(pending.sourceStore));
    return pending.completion;
  }
  // A publisher selection captures this mount's source. Its initial subscription call
  // is the mount delivery; later accepted publications stage the selected value and its
  // presentation ticket synchronously, before that semantic epoch seals. Notification
  // starts the staged paint only after activation has retained this document. A package
  // that throws while mounting must not leave a subscription behind to fail every later
  // publication.
  try {
    let mounting = true;
    stopSelection = selectedSource.subscribe((sourceStore) => {
      if (mounting) {
        const rendering = update(sourceStore, true);
        void presentation.present(deliveredRevision, rendering);
        return rendering;
      }
      stage(sourceStore);
    });
    mounting = false;
  } catch (error) {
    stop();
    throw error;
  }
  subscriptions.add(subscription);
  return stop;
}

// Fragment identity belongs to the delivered manifest. A replacement can be accepted
// before its subscriber renders; loading through that older manifest must not fetch a
// same-key fragment from the replacement.
export async function loadDataFragment(manifest, key) {
  if (
    !manifest ||
    typeof manifest.source !== "string" ||
    !manifest.source ||
    !Number.isInteger(manifest.revision) ||
    manifest.revision < 1
  )
    throw new TypeError("loadDataFragment needs a source snapshot");
  if (typeof key !== "string" || !key)
    throw new TypeError("loadDataFragment key must be a non-empty string");
  const contract = registry.$data?.contracts?.[manifest.contract];
  if (!contract?.fragments)
    throw new Error(
      `loadDataFragment contract ${manifest.contract} does not declare fragments`,
    );
  const { source, snapshot } = manifest;
  if (!snapshot && runtime.data.sources[source]?.revision !== manifest.revision)
    throw new Error(
      `source ${source} revision ${manifest.revision} changed before loading fragment ${key}`,
    );
  const revision = runtime.data.revision;
  const params = new URLSearchParams({
    data_revision: String(revision),
    source,
    key,
  });
  if (snapshot) params.set("snapshot", snapshot);
  const { offlineInteractive } = await import("./context.js");
  if (offlineInteractive)
    throw new Error(
      "data fragments need a Leaf server and are unavailable in this copy",
    );
  const response = await fetch(`/api/data?${params}`);
  if (response.ok && !sameDelivery(response)) {
    throw new Error("Leaf's data vocabulary changed while loading a fragment");
  }
  const answer = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      answer.error || `data fragment failed to load (${response.status})`,
    );
  if (
    answer.revision !== revision ||
    answer.source !== source ||
    answer.contract !== manifest.contract ||
    answer.key !== key ||
    (snapshot ? answer.snapshot !== snapshot : Object.hasOwn(answer, "snapshot"))
  )
    throw new Error("data fragment response does not match its request");
  if (runtime.data.revision !== revision)
    throw new Error(`data revision ${revision} changed while loading fragment ${key}`);
  return structuredClone(answer.value);
}
