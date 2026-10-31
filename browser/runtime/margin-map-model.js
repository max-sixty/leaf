/* Immutable Page Map groups derived from the same target and contribution readings
 * that supply margin clusters. DOM placement, retained controls, activation, search
 * input and focus stay in the dialog adapter. */

import { spokenSubject, visibleContributionEntryLabel } from "./contribution-model.js";

import { contributionItemKey } from "./contribution-model.js";
import { annotationItems, entryControls } from "./margin-model.js";
import { wordsText } from "./voice.js";

const dialogItemKey = (entry, item) =>
  JSON.stringify(["item", entry.key, contributionItemKey(item)]);

function dialogControlKey(entry, offered, record) {
  return JSON.stringify(["control", entry.key, offered.key, record.key]);
}

const dialogControlId = (entry, offered, record) =>
  `lf-page-map-entry-${encodeURIComponent(dialogControlKey(entry, offered, record))}`;

export function marginMapGroups(entries, faceFor, searchTextByKey) {
  return Object.freeze(
    entries.map((entry) => {
      const controls = entryControls(entry);
      const items = annotationItems(entry);
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
            label: `Open ${face.label.toLowerCase()}: ${spokenSubject(visibleLabel)}`,
            visibleLabel,
            // The name as the row draws it, where someone says part of it (voice.js).
            visibleWords: item.words ?? visibleLabel,
            // Producers add context only when it carries another fact. Version
            // comparisons do: their pair is provenance, separate from the account.
            context: item.mapContext,
            receipt: item.workflowReceipt,
            awaitsUser: Boolean(item.userAttention),
          };
        }),
        ...controls.map(({ offered, record, receipt }) => ({
          kind: "control",
          key: dialogControlKey(entry, offered, record),
          id: dialogControlId(entry, offered, record),
          entry,
          offered,
          record,
          icon: record.icon,
          glyph: record.glyph,
          label: record.accessibleLabel,
          visibleLabel: visibleContributionEntryLabel(record),
          context: record.context,
          receipt,
          awaitsUser: false,
        })),
      ];
      const search = [
        entry.title,
        ...actions.flatMap(({ visibleLabel, context }) => [
          visibleLabel,
          wordsText(context ?? ""),
        ]),
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
