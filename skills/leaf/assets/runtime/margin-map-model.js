/* Immutable Page Map groups derived from the same target and contribution readings
 * that supply margin clusters. DOM placement, retained controls, activation, search
 * input and focus stay in the dialog adapter. */

import {
  compareMarginEntryRecords,
  visibleMarginEntryLabel,
} from "./margin-entry-model.js";

function dialogControls(entry) {
  const records = entry.offers
    .flatMap((offered) =>
      offered.reading.entries
        .filter((record) => record.visible)
        .map((record) => Object.freeze({ record, offered })),
    )
    .sort(compareMarginEntryRecords);
  return records;
}

const dialogItemKey = (entry, item) => JSON.stringify(["item", entry.key, item.id]);

function dialogControlKey(entry, offered, record) {
  return JSON.stringify(["control", entry.key, offered.key, record.key]);
}

const dialogControlId = (entry, offered, record) =>
  `lf-page-map-entry-${encodeURIComponent(dialogControlKey(entry, offered, record))}`;

export function marginMapGroups(entries, faceFor, searchTextByKey) {
  return Object.freeze(
    entries.map((entry) => {
      const controls = dialogControls(entry);
      const controlOwners = new Set(controls.map(({ record }) => record.owner));
      const items = entry.items.filter(
        (item) => !item.owner || !controlOwners.has(item.owner),
      );
      const actions = [
        ...items.map((item) => {
          const face = faceFor(item);
          const visibleLabel = item.text || entry.title;
          return {
            kind: "item",
            key: dialogItemKey(entry, item),
            entry,
            item,
            icon: face.icon,
            label: `Open ${face.label.toLowerCase()}: ${visibleLabel}`,
            visibleLabel,
            // Map rows stay one line unless their producer explicitly owes a second.
            // Version comparisons do: their pair is provenance rather than part of the
            // account.
            context: item.mapContext,
          };
        }),
        ...controls.map(({ offered, record }) => ({
          kind: "control",
          key: dialogControlKey(entry, offered, record),
          id: dialogControlId(entry, offered, record),
          entry,
          offered,
          record,
          icon: record.icon,
          glyph: record.glyph,
          label: record.accessibleLabel,
          visibleLabel: visibleMarginEntryLabel(record),
          context: record.context,
        })),
      ];
      const search = [
        entry.title,
        ...actions.flatMap(({ visibleLabel, context }) => [visibleLabel, context]),
        searchTextByKey.get(entry.key),
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase();
      return Object.freeze({
        key: entry.key,
        entry,
        controls: Object.freeze(controls),
        actions: Object.freeze(actions.map(Object.freeze)),
        search,
      });
    }),
  );
}
