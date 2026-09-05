/* This module owns external-data acceptance, readiness, and source-contract
 * subscriptions. */
import { runtime } from "./context.js";
import { PAGE_PAINT_ATTRIBUTE } from "./presentation.js";
import { registry } from "./registry.js";

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
  if (candidate.revision <= runtime.data.revision) return false;
  runtime.data = structuredClone(candidate);
  return true;
}

// A watcher can mount after its source snapshot has already been accepted (most notably
// while a newer document is activating). Keep that first render in the same readiness
// boundary as the next data notification instead of letting the notification stamp the
// revision while the mount is still painting it.
const initialRenders = [];
let reportDataError = (text) => console.error(`leaf: ${text}`);

export function configureDataReporting(report) {
  if (typeof report !== "function")
    throw new TypeError("data error reporter must be a function");
  reportDataError = report;
}

async function settleDataRenders(renderings) {
  const settled = await Promise.allSettled(renderings);
  for (const result of settled)
    if (result.status === "rejected")
      reportDataError(
        `data subscriber failed: ${result.reason?.message ?? result.reason}`,
      );
}

export async function notifyDataSubscribers() {
  const revision = runtime.data.revision;
  const mounting = initialRenders.splice(0);
  await settleDataRenders(mounting);
  const pending = [];
  document.dispatchEvent(new CustomEvent("lf-data", { detail: { pending } }));
  await settleDataRenders(pending);
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
// whenever state asks subscribers to restate their reading, so a module cannot mutate
// the private accepted snapshot and a newly activated seat need not wait for the next
// poll.
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
  const deliver = (snapshot, event) => {
    if (snapshot)
      snapshot.origin = {
        input,
        source,
        contract: declaration.contract,
        revision: snapshot.revision,
        data_revision: runtime.data.revision,
        ...(selected ? { snapshot: selected } : {}),
      };
    const rendering = callback(snapshot);
    if (rendering?.then && Array.isArray(event?.detail?.pending))
      event.detail.pending.push(rendering);
    return rendering;
  };
  const update = (event) => {
    if (!source) {
      return deliver(null, event);
    }
    const present = Object.hasOwn(runtime.data.sources, source);
    if (present && runtime.data.sources[source].contract !== declaration.contract)
      throw new Error(
        `watchData(${element.localName}, ${input}) expected contract ${declaration.contract}, ` +
          `but source ${source} carries ${runtime.data.sources[source].contract}`,
      );
    if (!present) {
      return deliver(null, event);
    }
    const sourceStore = runtime.data.sources[source];
    if (selected) {
      const snapshot = sourceStore.snapshots?.[selected];
      if (!snapshot)
        throw new Error(
          `watchData(${element.localName}, ${input}) source ${source} has no snapshot ${selected}`,
        );
      return deliver(
        structuredClone({
          source,
          contract: sourceStore.contract,
          revision: Number(selected),
          snapshot: selected,
          ...snapshot,
        }),
        event,
      );
    }
    if (!Object.hasOwn(sourceStore, "value")) {
      return deliver(null, event);
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
    return deliver(structuredClone(snapshot), event);
  };
  // Establish the subscription only after its first delivery succeeds. A package that
  // throws while mounting must not leave a listener behind to fail every later poll.
  const initial = update();
  document.addEventListener("lf-data", update);
  if (initial?.then)
    initialRenders.push(
      Promise.resolve(initial).catch((error) => {
        document.removeEventListener("lf-data", update);
        throw error;
      }),
    );
  return () => document.removeEventListener("lf-data", update);
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
  const response = await fetch(`/api/data?${params}`);
  const responseLayer = response.headers.get("Leaf-Layer");
  if (response.ok && responseLayer && responseLayer !== registry.$layer?.generation) {
    location.reload();
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
