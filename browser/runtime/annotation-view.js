/* A page-owned view of the canonical annotation inventory.
 *
 * This registration consumes the directory after the Thread cohort commits. Its
 * synchronous paint joins that existing presentation proof and immediate contribution
 * updates. Source-linked rows use their existing owner; native contribution
 * controls use the one shared cache, activation and focus directory. No view collects
 * annotations, resolves their anchors, folds events or publishes an application root.
 * The owner retains its rows and layout, and unregisters when its document leaves.
 */
import {
  activateContributionControl,
  clearContributionControls,
  contributionControlKey,
  contributionEntryRecord,
  materializeContributionControls,
  presentContributionReceipts,
} from "./contribution-controls.js";
import { declareSide } from "./current-target.js";
import { under } from "./shadow.js";
import { annotationItems, entryControls } from "./margin-model.js";

/** @typedef {import("./annotation-inventory.js").InventoryEntry} Entry
 * @typedef {import("./contributions.js").ContributionSource} Source
 * @typedef {import("./contributions.js").ContributionOffer} Offer
 * @typedef {ReturnType<typeof import("./annotation-inventory.js").createAnnotationInventory>} Inventory
 * @typedef {{target: Inventory["targetFor"], activate: Inventory["activate"], items: typeof annotationItems,
 * controlKey: typeof contributionControlKey, controlRecord: typeof contributionEntryRecord,
 * arriving: boolean, place: (entry: Entry, row: Element) => void,
 * controls: (entry: Entry) => Element[]}} Capabilities
 * @typedef {(entries: readonly Entry[], capabilities: Capabilities) => unknown} Paint
 */
/** @param {Element} owner @param {Paint} render @param {Inventory} inventory
 * @param {() => void} invalidate @param {() => void} retire */
export function createAnnotationView(owner, render, inventory, invalidate, retire) {
  if (!(owner instanceof Element))
    throw new TypeError("consumeAnnotations needs an Element owner");
  if (!owner.isConnected)
    throw new TypeError("An annotation view needs a connected owner");
  if (typeof render !== "function")
    throw new TypeError("consumeAnnotations needs a synchronous render callback");
  let active = true;
  /** @type {Map<Element, Entry>} */
  let places = new Map();
  /** @type {Set<Source>} */
  let offers = new Set();
  const stopSide = declareSide((node) => {
    for (const [row, entry] of places)
      if (under(node, row)) return inventory.entryPlace(entry);
    return null;
  });

  /** @param {readonly Entry[]} entries */
  function paint(entries) {
    if (!active) return;
    if (!owner.isConnected) return unregister();
    /** @type {Map<Element, Entry>} */
    const nextPlaces = new Map();
    /** @type {Set<Source>} */
    const nextOffers = new Set();
    const allowed = new Set(entries);
    let painting = true;
    const admit = (/** @type {Entry} */ entry) => {
      if (!painting || !allowed.has(entry))
        throw new TypeError("Annotation capabilities belong to their current reading");
    };
    try {
      const result = render(entries, {
        target: inventory.targetFor,
        activate: inventory.activate,
        items: annotationItems,
        controlKey: contributionControlKey,
        controlRecord: contributionEntryRecord,
        arriving: entries.some((entry) =>
          entry.offers.some((model) => {
            const offered = model.source();
            const request = offered.focusRequest;
            return (
              request &&
              (request.surface == null || request.surface === "page") &&
              offered.reading.entries.some(
                (item) => item.key === request.key && item.visible,
              )
            );
          }),
        ),
        place(entry, row) {
          admit(entry);
          if (!(row instanceof Element) || !under(row, owner))
            throw new TypeError("An annotation row must stay inside its owner");
          nextPlaces.set(row, entry);
        },
        controls(entry) {
          admit(entry);
          /** @type {Map<Offer, ReturnType<typeof materializeContributionControls>>} */
          const retained = new Map();
          /** @param {Offer} offer */
          const materialize = (offer) => {
            let controls = retained.get(offer);
            if (!controls) {
              controls = materializeContributionControls(
                offer,
                "page",
                activateContributionControl,
              );
              retained.set(offer, controls);
              nextOffers.add(offer.source());
            }
            return controls;
          };
          for (const offer of entry.offers) materialize(offer);
          return entryControls(entry).map(({ offered, record, receipt }) => {
            const control = materialize(offered)(record);
            presentContributionReceipts(control, receipt, false);
            return control;
          });
        },
      });
      if (
        result &&
        (typeof result === "object" || typeof result === "function") &&
        "then" in result &&
        result.then
      )
        throw new TypeError(
          "Annotation paint must finish inside its inventory reading",
        );
      for (const offered of offers)
        if (!nextOffers.has(offered))
          clearContributionControls(offered, "page", new Set());
      offers = nextOffers;
      places = nextPlaces;
    } catch (error) {
      for (const offered of nextOffers)
        if (!offers.has(offered)) clearContributionControls(offered, "page", new Set());
      throw error;
    } finally {
      painting = false;
    }
  }

  let stopReading = () => {};
  function unregister() {
    if (!active) return;
    active = false;
    stopReading();
    stopSide();
    for (const offered of offers) clearContributionControls(offered, "page", new Set());
    offers.clear();
    places.clear();
    retire();
  }
  try {
    stopReading = inventory.watch(paint);
  } catch (error) {
    unregister();
    throw error;
  }
  return Object.freeze({ read: inventory.read, update: invalidate, unregister });
}
