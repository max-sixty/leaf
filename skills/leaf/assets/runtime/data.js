/* The accepted external data and its readers.

   The browser orders data readings by when the server took them, independently of
   the log sequence, because overlapping poll and POST responses can order the authorities
   differently. A `LeafElement` reads a bound input through `dataReader` (`this.data`),
   which yields one copy a delivery of `{source, contract, revision, run, updated, value,
   origin}`, or `null` while the bound source has no readable value. What it shows moves
   only as state application delivers, and each element that draws data holds the data
   version until its region has drawn the delivery (`joinDataDelivery`). Modules project
   the result into the authored seat; they do not fetch it, mutate the accepted copy, or
   keep a hidden current-value map of their own.*/

import { outsideReading, untracked } from "/vendor/browser-runtime.js";
import { offlineData, offlineInteractive, pageUrl, runtime } from "./context.js";
import { applicationState, whenApplicationRegionsPresented } from "./semantic-state.js";
import { PAGE_PAINT_ATTRIBUTE } from "./page-paint.js";
import { setRuntimeRootAttribute } from "./root-state.js";
import { registry } from "./registry.js";
import { reportPageError, requestJson } from "./layer-client.js";

export function acceptData(candidate, taken) {
  return applicationState.acceptData(candidate, taken);
}

// The regions that hold the data version until they have drawn a delivery.
const joined = new Set();

export async function notifyDataSubscribers() {
  const version = runtime.data.version;
  deliveries += 1;
  const round = {};
  for (const delivered of [...deliveryListeners]) delivered(round);
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

// A `LeafElement`'s reader of one bound input (leaf-element.js): the delivered source
// reading, read through a selection of that source, so a render that reads it is drawn
// again when the source moves. Markup owns the binding, captured at the first read, so
// module code cannot turn a live attribute mutation into an unvalidated rebind; a
// revision that rebinds mounts a new element.
export function dataReader(element, input) {
  const declaration = declaredInput(element, input);
  const source = element.getAttribute(declaration.source);
  const selected = applicationState.select((root) =>
    source && Object.hasOwn(root.data.sources, source)
      ? root.data.sources[source]
      : null,
  );
  // What the element shows moves only as state application delivers, so a reading
  // accepted for a revision still being activated never draws into the document it
  // replaces. The first read takes the accepted reading.
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
  stagedReadings.add(selected);
  let reported = null;
  let copied = { store: null, value: null };
  return () => {
    // The accepted reading claims the element's region inside the publication that
    // accepts it; the delivered one draws.
    selected.read();
    const sourceStore = /** @type {{contract: string, revision?: string} | null} */ (
      delivered.read()
    );
    const incompatible = sourceStore && sourceStore.contract !== declaration.contract;
    if (incompatible && reported !== sourceStore) {
      reported = sourceStore;
      reportPageError(
        `data source ${source} carries contract ${sourceStore.contract}; ` +
          `<${element.localName}> input ${input} requires ${declaration.contract}`,
      );
    }
    if (incompatible || !source || !sourceStore || !Object.hasOwn(sourceStore, "value"))
      return null;
    // One copy a delivery: a render that reads it again gets the same value, so a widget
    // tells a new delivery by identity, and none can mutate the accepted snapshot.
    if (sourceStore !== copied.store)
      copied = {
        store: sourceStore,
        value: structuredClone({
          source,
          ...sourceStore,
          origin: {
            input,
            source,
            contract: declaration.contract,
            revision: sourceStore.revision,
          },
        }),
      };
    return copied.value;
  };
}

// A renderer that draws data as it reads it holds the data version until its region
// presents; its readers hear the delivery itself.
let deliveries = 0;
const deliveryListeners = new Set();
// The accepted readings a `LeafElement` follows to claim its region, not to draw.
const stagedReadings = new WeakSet();
export const stagesOnly = (reading) => stagedReadings.has(reading);
export function joinDataDelivery(region) {
  joined.add(region);
  return () => joined.delete(region);
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
