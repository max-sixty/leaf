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

export function notifyDataSubscribers() {
  document.dispatchEvent(new Event("lf-data"));
  // The revision becomes a readiness fact only after synchronous subscribers have
  // rendered it. Render checks and export compare this stamp with the server snapshot,
  // so a data-only page cannot be read between acceptance and projection.
  if (runtime.data.revision >= 0)
    document.body.setAttribute(
      PAGE_PAINT_ATTRIBUTE.dataRevision,
      String(runtime.data.revision),
    );
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
  const update = () => {
    if (!source) {
      callback(null);
      return;
    }
    const present = Object.hasOwn(runtime.data.sources, source);
    if (present && runtime.data.sources[source].contract !== declaration.contract)
      throw new Error(
        `watchData(${element.localName}, ${input}) expected contract ${declaration.contract}, ` +
          `but source ${source} carries ${runtime.data.sources[source].contract}`,
      );
    if (!present) {
      callback(null);
      return;
    }
    const sourceStore = runtime.data.sources[source];
    if (selected) {
      const snapshot = sourceStore.snapshots?.[selected];
      if (!snapshot)
        throw new Error(
          `watchData(${element.localName}, ${input}) source ${source} has no snapshot ${selected}`,
        );
      callback(
        structuredClone({
          contract: sourceStore.contract,
          snapshot: selected,
          ...snapshot,
        }),
      );
      return;
    }
    if (!Object.hasOwn(sourceStore, "value")) {
      callback(null);
      return;
    }
    const snapshot = {
      contract: sourceStore.contract,
      updated: sourceStore.updated,
      value: sourceStore.value,
    };
    if (Object.hasOwn(sourceStore, "label")) snapshot.label = sourceStore.label;
    if (Object.hasOwn(sourceStore, "lines")) snapshot.lines = sourceStore.lines;
    callback(structuredClone(snapshot));
  };
  // Establish the subscription only after its first delivery succeeds. A package that
  // throws while mounting must not leave a listener behind to fail every later poll.
  update();
  document.addEventListener("lf-data", update);
  return () => document.removeEventListener("lf-data", update);
}
