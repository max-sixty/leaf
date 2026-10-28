/* A page-owned view of the canonical annotation inventory.
 *
 * This registration consumes the directory after the Thread cohort commits. Its
 * synchronous paint joins that existing presentation proof and immediate contribution
 * updates. Source-linked rows use their existing owner; native contribution
 * controls use the one shared cache, activation and focus directory. No view collects
 * annotations, resolves their anchors, folds events or publishes an application root.
 * The owner retains its rows and layout, and unregisters when its document leaves.
 */
import { contributionSource } from "./contributions.js";
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

export function createAnnotationView(owner, render, inventory, invalidate, retire) {
  if (!(owner instanceof Element))
    throw new TypeError("consumeAnnotations needs an Element owner");
  if (!owner.isConnected)
    throw new TypeError("An annotation view needs a connected owner");
  if (typeof render !== "function")
    throw new TypeError("consumeAnnotations needs a synchronous render callback");
  let active = true;
  let places = new Map();
  let offers = new Set();
  const stopSide = declareSide((node) => {
    for (const [row, entry] of places)
      if (under(node, row)) return inventory.entryPlace(entry);
    return null;
  });

  function paint(entries) {
    if (!active) return;
    if (!owner.isConnected) return unregister();
    const nextPlaces = new Map();
    const nextOffers = new Set();
    const allowed = new Set(entries);
    let painting = true;
    const admit = (entry) => {
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
            const offered = contributionSource(model);
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
          const retained = new Map(
            entry.offers.map((model) => {
              const offered = contributionSource(model);
              nextOffers.add(offered);
              return [
                model,
                materializeContributionControls(
                  offered,
                  "page",
                  activateContributionControl,
                ),
              ];
            }),
          );
          return entryControls(entry).map(({ offered, record, receipt }) => {
            const control = retained.get(offered).get(record.key);
            presentContributionReceipts(control, receipt, false);
            return control;
          });
        },
      });
      if (result?.then)
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
