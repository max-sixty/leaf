/* The accepted external data and its watchers.

   The browser orders data readings by when the server took them, independently of
   `lastEventSeq`, because overlapping poll and POST responses can order the authorities
   differently. `watchData(widget, input, callback)` delivers a clone of `{source,
   contract, revision, updated, value, origin}`, or `null` while the bound source has no
   readable value. It redelivers only when that source revision changes; overlapping
   reads await the same in-flight rendering before stamping readiness. Its synchronous
   time readings refresh independently of data delivery. Modules project the result
   into the authored seat; they do not fetch it, mutate the accepted copy, or keep a
   hidden current-value map of their own.*/

import { offlineData, offlineInteractive, pageUrl, runtime } from "./context.js";
import {
  applicationState,
  attachApplicationPresentation,
  whenApplicationRegionsPresented,
} from "./semantic-state.js";
import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";
import { registry } from "./registry.js";
import { clocked } from "./presence.js";
import { layerHeaders, reportPageError, sameDelivery } from "./layer-client.js";

export function acceptData(candidate, taken) {
  if (
    !candidate ||
    typeof candidate !== "object" ||
    Array.isArray(candidate) ||
    typeof candidate.version !== "string" ||
    !candidate.sources ||
    typeof candidate.sources !== "object" ||
    Array.isArray(candidate.sources)
  )
    throw new TypeError("state data must carry a version and sources");
  const changed = applicationState.acceptData(candidate, taken);
  // A reading that finds the data already presented is presented as it arrives.
  if (!changed && document.body.dataset.lfDataVersion === runtime.data.version)
    stampData(runtime.data.version);
  return changed;
}

// The readiness stamp: the data version presented, and when the server took the
// newest reading the page accepted. Render checks and export compare it with their own
// state read. Any process may rewrite a source, so the page can move past the reader's
// version, and a page that has presented a reading taken no earlier has caught up.
function stampData(version) {
  document.body.setAttribute(PAGE_PAINT_ATTRIBUTE.dataVersion, version);
  document.body.setAttribute(
    PAGE_PAINT_ATTRIBUTE.dataTaken,
    String(applicationState.dataTaken()),
  );
}

const subscriptions = new Set();
let subscriptionSequence = 0;

export async function notifyDataSubscribers() {
  const version = runtime.data.version;
  const current = [...subscriptions];
  for (const subscription of current) subscription.notify();
  const regions = current.map((subscription) => subscription.region);
  await whenApplicationRegionsPresented(
    regions,
    () => runtime.data.version === version,
  );
  // The version becomes a readiness fact only after every subscriber has settled. A
  // rejected package render is reported at its own boundary rather than turning every
  // later state read into the same page-wide failure. A data-only page therefore
  // cannot be read while an asynchronous projection is still pending.
  if (version !== null && runtime.data.version === version) stampData(version);
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
  // Markup owns the binding. Capture it at mount so module code cannot turn a live
  // attribute mutation into an unvalidated rebind. Version activation mounts a new
  // element and therefore establishes a new subscription when authored markup changes.
  const source = element.getAttribute(declaration.source);
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
  // `revision` is the source's, which a source whose value fails its contract also
  // has: its `null` delivery stands until the file changes again.
  const deliver = (snapshot, revision, mounting = false) => {
    if (!delivered || deliveredRevision !== revision) {
      if (snapshot)
        snapshot.origin = {
          input,
          source,
          contract: declaration.contract,
          revision: snapshot.revision,
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
    if (sourceStore && sourceStore.contract !== declaration.contract)
      throw new Error(
        `watchData(${element.localName}, ${input}) expected contract ${declaration.contract}, ` +
          `but source ${source} carries ${sourceStore.contract}`,
      );
    const revision = source ? (sourceStore?.revision ?? null) : null;
    // A value that fails its contract is the server's reading to report, in `page
    // state` and `version check`; the page shows the source as holding nothing.
    if (!source || !sourceStore || !Object.hasOwn(sourceStore, "value"))
      return deliver(null, revision, mounting);
    return deliver(
      {
        source,
        contract: sourceStore.contract,
        revision,
        updated: sourceStore.updated,
        value: sourceStore.value,
      },
      revision,
      mounting,
    );
  };
  const updateSafely = (sourceStore) => {
    try {
      return update(sourceStore);
    } catch (error) {
      reportPageError(`data subscriber failed: ${error?.message ?? error}`);
    }
  };
  const stage = (sourceStore) => {
    const revision = sourceStore?.revision ?? null;
    // What this subscriber will next paint is the staged delivery while one stands, and
    // the delivered revision otherwise. A revision is a digest of the source's bytes, so
    // a source can return to the revision already on screen while a later one is still
    // staged, and that staging is what has to go.
    if (!pendingDelivery && delivered && deliveredRevision === revision) return;
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
    typeof manifest.revision !== "string" ||
    !manifest.revision
  )
    throw new TypeError("loadDataFragment needs a source delivery");
  if (typeof key !== "string" || !key)
    throw new TypeError("loadDataFragment key must be a non-empty string");
  const contract = registry.$data?.contracts?.[manifest.contract];
  if (!contract?.fragments)
    throw new Error(
      `loadDataFragment contract ${manifest.contract} does not declare fragments`,
    );
  const { source, revision } = manifest;
  const current = () => runtime.data.sources[source]?.revision === revision;
  if (!current())
    throw new Error(
      `source ${source} revision ${revision} changed before loading fragment ${key}`,
    );
  if (offlineInteractive) {
    const reading = offlineData()?.sources?.[source];
    if (
      !reading ||
      reading.contract !== manifest.contract ||
      reading.revision !== revision
    )
      throw new Error("interactive export fragment does not match its source");
    const items = reading.value?.[contract.fragments.items];
    const matches = Array.isArray(items)
      ? items.filter((item) => item?.[contract.fragments.key] === key)
      : [];
    if (matches.length !== 1 || !(contract.fragments.value in matches[0]))
      throw new Error("interactive export fragment does not match its key");
    return structuredClone(matches[0][contract.fragments.value]);
  }
  const params = new URLSearchParams({ source, source_revision: revision, key });
  const response = await fetch(pageUrl(`api/data?${params}`), {
    headers: layerHeaders(),
  });
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
    answer.key !== key
  )
    throw new Error("data fragment response does not match its request");
  if (!current())
    throw new Error(
      `source ${source} revision ${revision} changed while loading fragment ${key}`,
    );
  return structuredClone(answer.value);
}
