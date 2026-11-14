/* Accepted external values, mounted-widget outputs, and their typed readers.

   The browser orders data readings by when the server took them, independently of
   the log sequence, because overlapping poll and POST responses can order the authorities
   differently. A `LeafElement` reads a bound input through `dataReader`, which yields
   one copy a delivery of `{source, contract, revision, run, updated, value, origin}`,
   or `null` while the bound source has no readable value, and hands the widget only its
   `value` (element-data.js, "Bound values"). A widget-output binding yields
   `{contract, value, origin}` with derived-widget provenance, without a fabricated
   source revision or run. Each object value names the snapshot that supplied it
   (`suppliedSnapshot`), so whoever holds the value can name its revision.

   A widget output is a property its element holds under the output's declared name,
   as a form control holds `value`, and the element says it changed by dispatching
   `change` on itself. Nothing is published to Leaf: a reader's input names the
   producer (`reference`) and reads the one output of its contract off the element
   standing under that id, again whenever that element says `change`, and resolves
   the id again whenever a producer arrives or leaves, so it follows a replacement. A
   reader that arrives late, or before its producer's module has loaded, reads what the
   element holds then. Outputs stay outside the application state: no reading of the log
   depends on one, so a change runs no fold and no selection, and only the readers of
   that producer hear it. The proof that a reader has drawn is the one every
   `LeafElement` has: its region is claimed in the stack that moved its reading
   (`requestUpdate`, leaf-element.js), so the page reads as presented only after the draw.

   What a source shows moves only as state application delivers, and each element that
   draws data holds the data version until its region has drawn the delivery
   (`joinDataDelivery`). Modules draw the value into the authored seat; they do not
   fetch it, mutate the accepted copy, or keep a hidden current-value map of their own.*/

import { computed, share, signal, untracked } from "/runtime/framework.js";
import { runtime } from "./context.js";
import { applicationState, whenApplicationRegionsPresented } from "./semantic-state.js";
import { PAGE_PAINT_ATTRIBUTE } from "./page-paint.js";
import { setRuntimeRootAttribute } from "./root-state.js";
import { registry, tagsDeclaring } from "./registry.js";
import { watchArrivals } from "./arrivals.js";
import { referencedProjection, requireReference } from "./references.js";
import { reportPageError } from "./layer-client.js";
import { tick } from "./version-signal.js";

/** A publication as `leaf.data.read_source` serves it, before widget delivery.
 * @typedef {NonNullable<import("../types/contract.js").ServedReading["data"]["sources"]>[string]} SourceReading
 * @typedef {{contract: string, value: unknown}} OutputReading
 * @typedef {{input: string, source: string, contract: string, revision: string}
 *   | {derived: readonly {widget: string}[]}} DataOrigin
 * @typedef {(SourceReading & {source: string, origin: DataOrigin})
 *   | (OutputReading & {source?: never, revision?: never, origin: DataOrigin})} DataSnapshot
 */
/** @param {{version: string | null, sources: Record<string, SourceReading>}} candidate @param {number} taken */
export function acceptData(candidate, taken) {
  return applicationState.acceptData(candidate, taken);
}

// The regions that hold the data version until they have drawn a delivery.
/** @type {Set<string>} */
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

/** @param {Element} element @param {string} input */
const declaredInput = (element, input) => {
  const declaration = registry[element.localName]?.["x-data"]?.[input];
  if (!declaration)
    throw new Error(
      `<${element.localName}> input ${input} is not declared by this widget`,
    );
  return declaration;
};

// `standing` moves when an element that may hold an output arrives or leaves, so each
// reader resolves its bound id again; one watch covers every such tag, started by the
// first reader. Each producer a reader has resolved has a signal its `change` moves.
const standing = signal(0);
let producersWatched = "";
function watchProducers() {
  // A document adopts its registry once, so this starts one watch.
  const tags = tagsDeclaring((entry) => Boolean(entry["x-output"])).join(",");
  if (!tags || tags === producersWatched) return;
  producersWatched = tags;
  // An arrival is offered again when the nodes beside it change, which is no move.
  /** @type {WeakSet<Element>} */
  const stood = new WeakSet();
  watchArrivals(tags, [], {
    arrive(element) {
      if (stood.has(element)) return;
      stood.add(element);
      tick(standing);
    },
    leave(element) {
      stood.delete(element);
      tick(standing);
    },
  });
}
/** @type {WeakMap<Element, ReturnType<typeof signal<number>>>} */
const changes = new WeakMap();
/** @param {Element} producer */
function changeOf(producer) {
  let said = changes.get(producer);
  if (!said) {
    const moved = (said = signal(0));
    changes.set(producer, moved);
    // A control inside the producer says `change` too; only the producer's own counts.
    producer.addEventListener("change", (event) => {
      if (event.target === producer) tick(moved);
    });
  }
  return said;
}

/** @typedef {{contract: string, source?: string, reference?: string}} DataInput */

// The reading of one source, which moves only as state application delivers: the
// accepted one claims the element's region inside the publication that accepts it, and
// the delivered one draws, so a reading accepted for a revision still being activated
// never draws into the document it replaces. The first read takes the accepted reading.
/** @param {string} source @param {DataInput} declaration @param {string} input @param {() => void} accepted */
function deliveredSource(source, declaration, input, accepted) {
  const selected = applicationState.select(
    /** @returns {DataSnapshot | null} */ (root) => {
      const reading = Object.hasOwn(root.data.sources, source)
        ? root.data.sources[source]
        : null;
      return reading
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
        : null;
    },
  );
  /** @type {(() => void) | null} */
  let stopAccepted = null;
  return computed(
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
}

// The reading of a bound widget's output of `contract`: what the element under the bound
// id, resolved in the reader's authored scope, holds in the property its declaration
// names for that contract. `page check` holds that widget to one output of the contract.
// The value is copied as it is read, so a producer that changes its own object in place
// and says `change` is heard, and an equal value keeps the reading it replaced.
/** @param {Element} element @param {string} attribute @param {string} widget @param {string} contract */
function heldOutput(element, attribute, widget, contract) {
  watchProducers();
  /** @type {DataSnapshot | null} */
  let held = null;
  return computed(() => {
    standing.value;
    const producer = untracked(() => referencedProjection(element, attribute, widget));
    if (!producer) return (held = null);
    changeOf(producer).value;
    return untracked(() => {
      const outputs = registry[producer.localName]?.["x-output"] ?? {};
      const name = Object.keys(outputs).find((key) => outputs[key].contract === contract);
      const value = name
        ? /** @type {Record<string, unknown>} */ (/** @type {unknown} */ (producer))[name]
        : null;
      held =
        value === null || value === undefined
          ? null
          : share(held, {
              contract,
              value: structuredClone(value),
              origin: { derived: [{ widget }] },
            });
      return held;
    });
  });
}

// The snapshot each delivered object value came from. An object is one delivery's copy,
// so the lookup is exact, and it lasts as long as something holds the value.
/** @type {WeakMap<object, DataSnapshot>} */
const supplied = new WeakMap();
/** The snapshot that supplied a delivered object `value`, or undefined. @param {object} value */
export const suppliedSnapshot = (value) => supplied.get(value);

// Whether the markup binds a declared input, to a source or to a widget's output.
/** @param {Element} element @param {{source?: string, reference?: string}} declaration */
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

// An element's reader of one bound input (element-data.js), read through a signal, so a
// render that reads it is drawn again when its reading moves. Markup owns the binding,
// captured at the first read, so module code cannot turn a live attribute mutation into
// an unvalidated rebind; a revision that rebinds mounts a new element.
/** @param {Element} element @param {string} input @param {() => void} accepted @returns {() => DataSnapshot | null} */
export function dataReader(element, input, accepted) {
  const declaration = declaredInput(element, input);
  const source = declaration.source ? element.getAttribute(declaration.source) : null;
  const widget = declaration.reference
    ? element.getAttribute(declaration.reference)
    : null;
  if (source && widget)
    throw new Error(
      `<${element.localName}> input binds both an external source and widget output`,
    );
  if (declaration.reference) requireReference("data", element, declaration.reference);
  const bound = source
    ? deliveredSource(source, declaration, input, accepted)
    : widget && declaration.reference
      ? heldOutput(element, declaration.reference, widget, declaration.contract)
      : null;
  /** @type {DataSnapshot | null} */
  let reported = null;
  /** @type {{store: DataSnapshot, value: DataSnapshot} | null} */
  let copied = null;
  return () => {
    const sourceStore = bound?.value ?? null;
    const incompatible = sourceStore && sourceStore.contract !== declaration.contract;
    if (incompatible && reported !== sourceStore) {
      reported = sourceStore;
      reportPageError(
        `data source ${source} carries contract ${sourceStore.contract}; ` +
          `<${element.localName}> input ${input} requires ${declaration.contract}`,
      );
    }
    if (incompatible || !sourceStore || !Object.hasOwn(sourceStore, "value"))
      return null;
    // One copy a delivery: a render that reads it again gets the same value, so a widget
    // tells a new delivery by identity, and none can mutate the accepted snapshot.
    if (sourceStore !== copied?.store) {
      copied = {
        store: sourceStore,
        value: structuredClone(sourceStore),
      };
      const { value } = copied.value;
      if (value !== null && typeof value === "object")
        supplied.set(value, copied.value);
    }
    return copied.value;
  };
}

// A renderer that draws data as it reads it holds the data version until its region
// presents; its readers hear the delivery itself.
const deliveries = signal(0);
/** @param {string} region */
export function joinDataDelivery(region) {
  joined.add(region);
  return () => joined.delete(region);
}
