/* Immutable Page Map groups derived from the same target and contribution readings
 * that supply margin clusters. DOM placement, retained controls, activation, search
 * input and focus stay in the dialog adapter. */

import { spokenSubject, visibleContributionEntryLabel } from "./contribution-model.js";

import { contributionItemKey } from "./contribution-model.js";
import { annotationItems, entryControls } from "./margin-model.js";
import { wordsText } from "./voice.js";

/** @typedef {import("./margin-model.js").Offer} Offer
 * @typedef {import("./margin-model.js").AnnotationItem} Item
 * @typedef {import("./contribution-model.js").OwnedEntry} EntryRecord
 * @typedef {import("./voice.js").Words} Words
 * @typedef {{key: string, icon: string | null, label: string, visibleLabel: string, context: Words | null | undefined,
 * receipt: import("./framework/application.js").Workflow | null | undefined, awaitsUser: boolean}} ActionBase
 */
/** @template {Offer} O @typedef {ActionBase & {kind: "item", entry: import("./margin-model.js").MarginEntry<O>, item: Item, visibleWords: Words, glyph?: never, id?: never}} ItemAction */
/** @template {Offer} O @typedef {ActionBase & {kind: "control", id: string, entry: import("./margin-model.js").MarginEntry<O>, offered: O, record: EntryRecord, glyph: string | null, item?: never, visibleWords?: never}} ControlAction */
/** @param {{key: string}} entry @param {Item} item */
const dialogItemKey = (entry, item) =>
  JSON.stringify(["item", entry.key, contributionItemKey(item)]);

/** @param {{key: string}} entry @param {{key: string}} offered @param {EntryRecord} record */
function dialogControlKey(entry, offered, record) {
  return JSON.stringify(["control", entry.key, offered.key, record.key]);
}

/** @param {{key: string}} entry @param {{key: string}} offered @param {EntryRecord} record */
const dialogControlId = (entry, offered, record) =>
  `lf-page-map-entry-${encodeURIComponent(dialogControlKey(entry, offered, record))}`;

/** @template {Offer} O
 * @param {readonly import("./margin-model.js").MarginEntry<O>[]} entries
 * @param {(item: Item) => import("./contribution-model.js").KindFace} faceFor
 * @param {ReadonlyMap<string, string>} searchTextByKey */
export function marginMapGroups(entries, faceFor, searchTextByKey) {
  return Object.freeze(
    entries.map((entry) => {
      const controls = entryControls(entry);
      const items = annotationItems(entry);
      /** @type {(ItemAction<O> | ControlAction<O>)[]} */
      const actions = [
        ...items.map(
          /** @returns {ItemAction<O>} */ (item) => {
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
          },
        ),
        ...controls.map(
          /** @returns {ControlAction<O>} */ ({ offered, record, receipt }) => ({
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
          }),
        ),
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
        actions: Object.freeze(actions.map((action) => Object.freeze(action))),
        search,
      });
    }),
  );
}
