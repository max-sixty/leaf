/* Immutable Page Map groups derived from the same target and contribution readings
 * that supply margin clusters. DOM placement, retained controls, activation, search
 * input and focus stay in the dialog adapter. */

import {
  contributionItemKey,
  spokenSubject,
  visibleContributionEntryLabel,
} from "../base/contribution-model.js";
import { annotationItems, entryControls } from "./margin-model.js";
import { wordsText } from "../base/voice.js";
import type { AnnotationItem, MarginEntry, Offer } from "./margin-model.js";
import type { Words } from "../base/voice.js";
import type { KindFace, OwnedEntry } from "../base/contribution-model.js";
import type { Workflow } from "../../types/domain.js";

type Item = AnnotationItem;
type EntryRecord = OwnedEntry;
type ActionBase = {
  key: string;
  icon: string | null;
  label: string;
  visibleLabel: string;
  context: Words | null | undefined;
  receipt: Workflow | null | undefined;
  awaitsUser: boolean;
};
type ItemAction<O extends Offer> = ActionBase & {
  kind: "item";
  entry: MarginEntry<O>;
  item: Item;
  visibleWords: Words;
  glyph?: never;
  id?: never;
};
type ControlAction<O extends Offer> = ActionBase & {
  kind: "control";
  id: string;
  entry: MarginEntry<O>;
  offered: O;
  record: EntryRecord;
  glyph: string | null;
  item?: never;
  visibleWords?: never;
};
const dialogItemKey = (entry: { key: string }, item: Item) =>
  JSON.stringify(["item", entry.key, contributionItemKey(item)]);

function dialogControlKey(
  entry: { key: string },
  offered: { key: string },
  record: EntryRecord,
) {
  return JSON.stringify(["control", entry.key, offered.key, record.key]);
}

const dialogControlId = (
  entry: { key: string },
  offered: { key: string },
  record: EntryRecord,
) =>
  `lf-page-map-entry-${encodeURIComponent(dialogControlKey(entry, offered, record))}`;

/** @param saidOf An item's words as the map opens, where the inventory's copy would
 *   be stale, as a draft's is. */
export function marginMapGroups<O extends Offer>(
  entries: readonly MarginEntry<O>[],
  faceFor: (item: Item) => KindFace,
  searchTextByKey: ReadonlyMap<string, string>,
  saidOf: (item: Item) => string | null = () => null,
) {
  return Object.freeze(
    entries.map((entry) => {
      const controls = entryControls(entry);
      const items = annotationItems(entry);
      const actions: (ItemAction<O> | ControlAction<O>)[] = [
        ...items.map((item): ItemAction<O> => {
          const face = faceFor(item);
          const visibleLabel = saidOf(item) || item.text || entry.title;
          return {
            kind: "item",
            key: dialogItemKey(entry, item),
            entry,
            item,
            icon: face.icon,
            label: `Open ${face.label.toLowerCase()}: ${spokenSubject(visibleLabel)}`,
            visibleLabel,
            // The name as the row draws it, where someone says part of it (base/voice.js).
            visibleWords: item.words ?? visibleLabel,
            // Producers add context only when it carries another fact. Version
            // comparisons do: their pair is provenance, separate from the account.
            context: item.mapContext,
            receipt: item.workflowReceipt,
            awaitsUser: Boolean(item.userAttention),
          };
        }),
        ...controls.map(({ offered, record, receipt }): ControlAction<O> => ({
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
        actions: Object.freeze(actions.map((action) => Object.freeze(action))),
        search,
      });
    }),
  );
}
