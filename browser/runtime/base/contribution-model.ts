/* Immutable contribution grammar. This module normalizes contributor data and owns
   ordering and labels without browser dependencies. The browser registry keeps
   command-scope capabilities outside the normalized records. */

import { actionIcon } from "../lib/icon-paths.js";
import { excerptWords } from "../lib/words.js";
import type { Voice, Words } from "./voice.js";
import type { Workflow } from "../../types/domain.js";
import type { ScopeCapability, ScopeDeclaration } from "./command-declaration.js";
import type { CompleteUnion } from "../../types/contract.js";

const TONES = Object.freeze({ neutral: true, positive: true, negative: true });
const BEHAVIORS = Object.freeze({ action: true, disclosure: true, status: true });
const RANK_PRIORITY = Object.freeze({
  complete: 0,
  escape: 1,
  primary: 2,
  secondary: 3,
  reading: 4,
  overflow: 5,
});
const STATE_PRIORITY = Object.freeze({ idle: 3, engaged: 2, busy: 1, failed: 0 });
export type Tone = keyof typeof TONES;
export type Behavior = keyof typeof BEHAVIORS;
export type Rank = keyof typeof RANK_PRIORITY;
export type ContributionState = keyof typeof STATE_PRIORITY;
export type ContributionKind = keyof typeof kinds;
type EntryRelationInput =
  | { kind: "entries"; keys: readonly string[]; expanded?: boolean }
  | { kind: "element"; id: string; expanded?: boolean; popup?: string | null };
export type EntryInput = {
  key: string;
  label: string;
  glyph?: string | null;
  action?: string | null;
  icon?: string | null;
  voice?: Voice | null;
  accessibleLabel?: string | null;
  context?: Words | null;
  description?: string | null;
  behavior?: Behavior;
  tone?: Tone;
  rank?: Rank;
  state?: ContributionState;
  visible?: boolean;
  disabled?: boolean;
  count?: number;
  pressed?: boolean | null;
  workflowReceipt?: Workflow | null | undefined;
  relation?: EntryRelationInput | null;
  activation?: string | null;
  title?: string | null;
  scope?: ScopeDeclaration | ScopeCapability | null | undefined;
};
export type ContributionEntry = ReturnType<typeof contributionEntry>;
type BrandedEntry = ContributionEntry & { owner?: string };
export type OwnedEntry = ContributionEntry & { owner: string };
type ReadingInput = {
  id: string;
  text: string;
  kind?: ContributionKind;
  represents?: boolean;
  activate?: () => unknown;
};
export type ReadingOptions = {
  kind?: ContributionKind | null;
  subject?: string | null;
  state?: ContributionState;
  side?: "before" | "after";
  notice?: { text: string; tone?: string | null } | null;
  entries?: readonly EntryInput[];
  readings?: readonly ReadingInput[];
};
export type ContributionReading = ReturnType<typeof normalizeContributionReading>;
export type ContributionModel = {
  key: string;
  reading: Omit<ContributionReading, "readings"> & { hasReadings: boolean };
};
const entryRecords: WeakSet<object> = new WeakSet();
export const isContributionEntry = (
  entry: EntryInput | ContributionEntry | undefined,
): entry is BrandedEntry => entry !== undefined && entryRecords.has(entry);

const ENTRY_OPTION_NAMES = Object.freeze([
  "key",
  "glyph",
  "action",
  "icon",
  "label",
  "voice",
  "accessibleLabel",
  "context",
  "description",
  "behavior",
  "tone",
  "rank",
  "state",
  "visible",
  "disabled",
  "count",
  "pressed",
  "workflowReceipt",
  "relation",
  "activation",
  "title",
  "scope",
]);
const ENTRY_OPTIONS = new Set(ENTRY_OPTION_NAMES);

export const CONTRIBUTION_ENTRY_SCHEMA = Object.freeze({
  tones: Object.freeze(Object.keys(TONES)),
  behaviors: Object.freeze(Object.keys(BEHAVIORS)),
  states: Object.freeze(Object.keys(STATE_PRIORITY)),
  ranks: Object.freeze(Object.keys(RANK_PRIORITY)),
  options: ENTRY_OPTION_NAMES,
});
// What a contribution reading or contribution is, and the face and word it wears. A
// kind whose word is Leaf's account of an update on its way to the agent says so in
// its `voice`, as each of its receipts does alone (`workflowWord`).
const kinds = {
  action: { label: "Action", icon: "dot", priority: -1 },
  change: { label: "Change", icon: "change", priority: 0 },
  restated: {
    label: "Rewritten",
    icon: "change",
    priority: 0,
    indication: true,
  },
  comment: { label: "Thread", icon: "comment", priority: 1 },
  // Words the user wrote about a place and hasn't sent (records/drafts.js, the drafts list),
  // in a draft's grey (controls.css). It follows a thread on the same place, which
  // stays the entry's face.
  draft: { label: "Draft", icon: "comment", priority: 1.5 },
  "on-me": { label: "On Me", icon: "question", priority: 2 },
  sent: {
    label: "Queued",
    icon: "sent",
    priority: 3,
    indication: true,
    voice: "leaf",
  },
  pickup: {
    label: "Delivered",
    icon: "pickup",
    priority: 3,
    indication: true,
    voice: "leaf",
  },
  // Every receipt whose progress stopped short: one past the pickup grace, one
  // whose turn ended or went quiet, one the harness failed. A single receipt reads
  // under its own label; this names a group of them.
  waiting: {
    label: "Stalled update",
    icon: "waiting",
    priority: 3,
    indication: true,
    voice: "leaf",
  },
  user: {
    label: "My change",
    icon: "change",
    priority: 4,
    indication: true,
  },
  reported: {
    label: "Reported state",
    icon: "activity",
    priority: 4,
    indication: true,
  },
  activity: { label: "Working", icon: "activity", priority: 4 },
} satisfies Record<string, KindFace>;
for (const face of Object.values(kinds)) Object.freeze(face);
export type KindFace = {
  label: string;
  icon: string;
  priority: number;
  indication?: boolean;
  voice?: Voice;
};
export const KINDS: { readonly [K in keyof typeof kinds]: Readonly<KindFace> } =
  Object.freeze(kinds);
const READING_OPTIONS = new Set([
  "kind",
  "subject",
  "state",
  "side",
  "notice",
  "entries",
  "readings",
]);

const text = (value: unknown) => String(value ?? "").trim();
const unknownOptions = (
  offered: object,
  allowed: ReadonlySet<string>,
  kind: string,
) => {
  const unknown = Object.keys(offered).filter((key) => !allowed.has(key));
  if (unknown.length)
    throw new TypeError(
      `Unknown contribution ${kind} option: ${unknown.sort().join(", ")}`,
    );
};
type EntryRelation = CompleteUnion<
  | { kind: "entries"; keys: readonly string[]; expanded: boolean }
  | { kind: "element"; id: string; expanded: boolean; popup: string | null }
>;
const freezeRelation = (relation: EntryRelationInput | null): EntryRelation | null => {
  if (relation == null) return null;
  const kind = relation.kind;
  if (kind === "entries") {
    const keys = relation.keys?.map(text).filter(Boolean) ?? [];
    if (!keys.length)
      throw new TypeError("A contribution entry relation needs at least one entry key");
    return Object.freeze({
      kind: "entries",
      keys: Object.freeze(keys),
      expanded: Boolean(relation.expanded),
    });
  }
  if (kind === "element") {
    const id = text(relation.id);
    if (!id) throw new TypeError("A margin element relation needs an id");
    return Object.freeze({
      kind: "element",
      id,
      expanded: Boolean(relation.expanded),
      popup: relation.popup == null ? null : text(relation.popup),
    });
  }
  throw new TypeError(`Unknown contribution entry relation: ${String(kind)}`);
};

export function contributionEntry(offered: EntryInput) {
  unknownOptions(offered, ENTRY_OPTIONS, "entry");
  const {
    key,
    glyph = null,
    action = null,
    icon: mark = null,
    label,
    voice = null,
    accessibleLabel = null,
    context = null,
    description = null,
    behavior = "action",
    tone = "neutral",
    rank = "primary",
    state = "idle",
    visible = true,
    disabled = false,
    count = 1,
    pressed = null,
    workflowReceipt = undefined,
    relation = null,
    activation = key,
    title = null,
    scope = null,
  } = offered;
  if (!text(key)) throw new TypeError("A contribution entry needs a key");
  // An entry that does something shows its action's symbol (icon-paths.js, `ACTIONS`);
  // `icon` is for one that shows what it holds, such as a margin entry's kind.
  if ([text(glyph), action, mark].filter(Boolean).length !== 1)
    throw new TypeError("A contribution entry needs exactly one glyph, action or icon");
  const icon = action ? actionIcon(action) : mark;
  if (!text(label)) throw new TypeError("A contribution entry needs a label");
  if (!Object.hasOwn(TONES, tone))
    throw new TypeError(`Unknown contribution entry tone: ${tone}`);
  if (!Object.hasOwn(BEHAVIORS, behavior))
    throw new TypeError(`Unknown contribution entry behavior: ${behavior}`);
  if (!Object.hasOwn(RANK_PRIORITY, rank))
    throw new TypeError(`Unknown contribution entry rank: ${rank}`);
  if (!Object.hasOwn(STATE_PRIORITY, state))
    throw new TypeError(`Unknown contribution entry state: ${state}`);
  if (!Number.isSafeInteger(count) || count < 0)
    throw new TypeError("A contribution entry count must be a non-negative integer");
  if (behavior !== "status" && !text(activation))
    throw new TypeError("An actionable contribution entry needs an activation");
  if (behavior === "status" && scope != null)
    throw new TypeError("A status contribution entry cannot have a command scope");
  const fields = {
    key: text(key),
    glyph: glyph == null ? null : String(glyph),
    icon,
    label: text(label),
    // Who says the label, where a speaker says it, as a lone receipt says its word
    // (`workflowWord`); null where it is a name. Its line may be said too (voice.js).
    voice,
    accessibleLabel: text(accessibleLabel) || text(label),
    context:
      typeof context === "string" || context == null ? text(context) || null : context,
    description: text(description) || null,
    behavior,
    tone,
    rank,
    state,
    visible: Boolean(visible),
    disabled: Boolean(disabled),
    count,
    pressed: pressed == null ? null : Boolean(pressed),
    workflowReceipt,
    relation: freezeRelation(relation),
    title: text(title) || null,
  };
  const record =
    behavior === "status"
      ? Object.freeze({ ...fields, behavior, activation: null })
      : Object.freeze({ ...fields, behavior, activation: text(activation) });
  entryRecords.add(record);
  return record;
}

export function normalizeContributionReading(reading: ReadingOptions, owner: string) {
  unknownOptions(reading, READING_OPTIONS, "contribution");
  const {
    kind = null,
    subject = null,
    state = "idle",
    side = "before",
    notice = null,
    entries = [],
    readings = [],
  } = reading;
  if (!Object.hasOwn(STATE_PRIORITY, state))
    throw new TypeError(`Unknown contribution state: ${state}`);
  if (kind != null && !Object.hasOwn(KINDS, kind))
    throw new TypeError(
      `Unknown contribution kind "${kind}" in contribution "${owner}"`,
    );
  if (side !== "before" && side !== "after")
    throw new TypeError(`Unknown contribution side: ${side}`);
  const keys = new Set();
  const normalizedEntries = entries.map((entry) => {
    const normalized = isContributionEntry(entry) ? entry : contributionEntry(entry);
    if (keys.has(normalized.key))
      throw new TypeError(
        `Duplicate contribution entry key "${normalized.key}" in contribution "${owner}"`,
      );
    keys.add(normalized.key);
    const owned = Object.freeze({ ...normalized, owner });
    entryRecords.add(owned);
    return owned;
  });
  const ids = new Set();
  for (const item of readings) {
    if (typeof item.id !== "string" || !item.id.trim() || ids.has(item.id))
      throw new TypeError(
        `Contribution reading IDs must be nonempty and unique in contribution "${owner}"`,
      );
    ids.add(item.id);
  }
  const normalizedNotice =
    notice == null
      ? null
      : Object.freeze({
          text: text(notice.text),
          tone: text(notice.tone) || "negative",
        });
  return Object.freeze({
    kind,
    subject: text(subject) || null,
    state,
    side,
    notice: normalizedNotice,
    entries: Object.freeze(normalizedEntries),
    // A reading carries only the fields a reading declares. The margin item made from
    // it (features/annotation-inventory.js) also holds what only Leaf's own readings
    // say, such as a thread's `unread` and `userAttention`, so a package's field of
    // that name would paint Leaf's marks.
    readings: Object.freeze(
      readings.map(({ id, text, kind, represents }) =>
        Object.freeze({
          id,
          text,
          ...(kind !== undefined && { kind }),
          ...(represents && { represents }),
        }),
      ),
    ),
  });
}

export const contributionEntryStateRank = (state: ContributionState) =>
  STATE_PRIORITY[state];
export const contributionState = (offered: ContributionModel) => offered.reading.state;

export function compareContributions(
  left: ContributionModel,
  right: ContributionModel,
) {
  const state =
    STATE_PRIORITY[left.reading.state] - STATE_PRIORITY[right.reading.state];
  return state || left.key.localeCompare(right.key);
}

export function compareContributionEntryRecords(
  left: { offered: ContributionModel; record: OwnedEntry },
  right: { offered: ContributionModel; record: OwnedEntry },
) {
  const state =
    STATE_PRIORITY[left.offered.reading.state] -
    STATE_PRIORITY[right.offered.reading.state];
  if (state) return state;
  const rank = RANK_PRIORITY[left.record.rank] - RANK_PRIORITY[right.record.rank];
  if (rank) return rank;
  const contribution = left.offered.key.localeCompare(right.offered.key);
  return contribution || left.record.key.localeCompare(right.record.key);
}

// A disclosure's label says it opens with a trailing ellipsis, unless the label already
// ends in a stop of its own: an ellipsis, or a question's mark, which would read as
// "?…".
export const visibleContributionEntryLabel = ({
  behavior,
  label,
}: Pick<ContributionEntry, "behavior" | "label">) =>
  behavior !== "disclosure" || /[…?]$/.test(label) ? label : `${label}…`;

// A contribution owns its reading IDs; generated readings have no owner.
export const contributionItemKey = (item: { owner?: string; id: string }) =>
  JSON.stringify([item.owner ?? null, item.id]);

// Spoken names have a listening budget, independent of the space CSS gives the
// visible label. Only accessibility presentations use this excerpt; inventory and
// search retain the complete text.
const SPOKEN_SUBJECT_CAP = 120;
export const spokenSubject = (value: string) => excerptWords(value, SPOKEN_SUBJECT_CAP);
