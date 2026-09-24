/* Immutable margin-entry grammar. This module normalizes contributor data and owns
   ordering and labels without browser dependencies. The browser registry keeps
   command-scope capabilities outside the normalized records. */

const entryRecords = new WeakSet();
export const isMarginEntry = (entry) => entryRecords.has(entry);

export const MARGIN_ENTRY_SCHEMA = Object.freeze({
  tones: Object.freeze(["neutral", "positive", "negative"]),
  behaviors: Object.freeze(["action", "disclosure", "status"]),
  states: Object.freeze(["idle", "engaged", "busy", "failed"]),
  ranks: Object.freeze([
    "complete",
    "escape",
    "primary",
    "secondary",
    "reading",
    "overflow",
  ]),
});

const TONES = new Set(MARGIN_ENTRY_SCHEMA.tones);
const BEHAVIORS = new Set(MARGIN_ENTRY_SCHEMA.behaviors);
const STATES = new Set(MARGIN_ENTRY_SCHEMA.states);
const RANKS = new Set(MARGIN_ENTRY_SCHEMA.ranks);
const STATE_PRIORITY = new Map([
  ["failed", 0],
  ["busy", 1],
  ["engaged", 2],
  ["idle", 3],
]);
const RANK_PRIORITY = new Map([
  ["complete", 0],
  ["escape", 1],
  ["primary", 2],
  ["secondary", 3],
  ["reading", 4],
  ["overflow", 5],
]);

const ENTRY_OPTIONS = new Set([
  "key",
  "glyph",
  "icon",
  "label",
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
  "className",
  "scope",
]);
const READING_OPTIONS = new Set([
  "subject",
  "state",
  "side",
  "claim",
  "reserve",
  "notice",
  "entries",
  "readings",
]);

const text = (value) => String(value ?? "").trim();
const unknownOptions = (offered, allowed, kind) => {
  const unknown = Object.keys(offered).filter((key) => !allowed.has(key));
  if (unknown.length)
    throw new TypeError(`Unknown margin ${kind} option: ${unknown.sort().join(", ")}`);
};
const freezeRelation = (relation) => {
  if (relation == null) return null;
  if (typeof relation !== "object")
    throw new TypeError("A margin entry relation must be an object");
  if (relation.kind === "entries") {
    const keys = relation.keys?.map(text).filter(Boolean) ?? [];
    if (!keys.length)
      throw new TypeError("A margin entry relation needs at least one entry key");
    return Object.freeze({
      kind: "entries",
      keys: Object.freeze(keys),
      expanded: Boolean(relation.expanded),
    });
  }
  if (relation.kind === "element") {
    const id = text(relation.id);
    if (!id) throw new TypeError("A margin element relation needs an id");
    return Object.freeze({
      kind: "element",
      id,
      expanded: Boolean(relation.expanded),
      popup: relation.popup == null ? null : text(relation.popup),
    });
  }
  throw new TypeError(`Unknown margin entry relation: ${String(relation.kind)}`);
};

export function marginEntry(offered) {
  if (!offered || typeof offered !== "object")
    throw new TypeError("A margin entry needs an options object");
  unknownOptions(offered, ENTRY_OPTIONS, "entry");
  const {
    key,
    glyph = null,
    icon = null,
    label,
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
    className = null,
    scope = null,
  } = offered;
  if (!text(key)) throw new TypeError("A margin entry needs a key");
  if (Boolean(text(glyph)) === Boolean(icon))
    throw new TypeError("A margin entry needs exactly one glyph or icon");
  if (!text(label)) throw new TypeError("A margin entry needs a label");
  if (!TONES.has(tone)) throw new TypeError(`Unknown margin entry tone: ${tone}`);
  if (!BEHAVIORS.has(behavior))
    throw new TypeError(`Unknown margin entry behavior: ${behavior}`);
  if (!RANKS.has(rank)) throw new TypeError(`Unknown margin entry rank: ${rank}`);
  if (!STATES.has(state)) throw new TypeError(`Unknown margin entry state: ${state}`);
  if (!Number.isSafeInteger(count) || count < 0)
    throw new TypeError("A margin entry count must be a non-negative integer");
  if (behavior !== "status" && !text(activation))
    throw new TypeError("An actionable margin entry needs an activation");
  if (behavior === "status" && scope != null)
    throw new TypeError("A status margin entry cannot have a command scope");
  const record = Object.freeze({
    key: text(key),
    glyph: glyph == null ? null : String(glyph),
    icon,
    label: text(label),
    accessibleLabel: text(accessibleLabel) || text(label),
    context: text(context) || null,
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
    activation: behavior === "status" ? null : text(activation),
    title: text(title) || null,
    className: text(className) || null,
  });
  entryRecords.add(record);
  return record;
}

export function normalizeMarginReading(reading, owner) {
  if (!reading || typeof reading !== "object")
    throw new TypeError("A margin contribution must read an object");
  unknownOptions(reading, READING_OPTIONS, "contribution");
  const {
    subject = null,
    state = "idle",
    side = "before",
    claim = true,
    reserve = 0,
    notice = null,
    entries = [],
    readings = [],
  } = reading;
  if (!STATES.has(state))
    throw new TypeError(`Unknown margin contribution state: ${state}`);
  if (side !== "before" && side !== "after")
    throw new TypeError(`Unknown margin contribution side: ${side}`);
  if (!Number.isFinite(reserve) || reserve < 0)
    throw new TypeError("A margin contribution reserve must be non-negative");
  if (!Array.isArray(entries))
    throw new TypeError("A margin contribution's entries must be an array");
  if (!Array.isArray(readings))
    throw new TypeError("A margin contribution's readings must be an array");
  const keys = new Set();
  const normalizedEntries = entries.map((entry) => {
    const normalized = entryRecords.has(entry) ? entry : marginEntry(entry);
    if (keys.has(normalized.key))
      throw new TypeError(
        `Duplicate margin entry key "${normalized.key}" in margin contribution "${owner}"`,
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
        `Margin reading IDs must be nonempty and unique in contribution "${owner}"`,
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
    subject: text(subject) || null,
    state,
    side,
    claim: Boolean(claim),
    reserve,
    notice: normalizedNotice,
    entries: Object.freeze(normalizedEntries),
    readings: Object.freeze(readings.map((item) => Object.freeze({ ...item }))),
  });
}

export const marginEntryStateRank = (state) => STATE_PRIORITY.get(state);
export const marginContributionState = (offered) => offered.reading.state;

export function compareMarginContributions(left, right) {
  const state =
    STATE_PRIORITY.get(left.reading.state) - STATE_PRIORITY.get(right.reading.state);
  return state || left.key.localeCompare(right.key);
}

export function compareMarginEntryRecords(left, right) {
  const state =
    STATE_PRIORITY.get(left.offered.reading.state) -
    STATE_PRIORITY.get(right.offered.reading.state);
  if (state) return state;
  const rank =
    RANK_PRIORITY.get(left.record.rank) - RANK_PRIORITY.get(right.record.rank);
  if (rank) return rank;
  const contribution = left.offered.key.localeCompare(right.offered.key);
  return contribution || left.record.key.localeCompare(right.record.key);
}

export const visibleMarginEntryLabel = ({ behavior, label }) =>
  behavior !== "disclosure" || label.endsWith("…") ? label : `${label}…`;

// A contribution owns its reading IDs; generated readings have no owner.
export const marginItemKey = (item) => JSON.stringify([item.owner ?? null, item.id]);

export const labelWords = (value) =>
  String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();

// Spoken names have a listening budget, independent of the space CSS gives the
// visible label. Only accessibility presentations use this excerpt; inventory and
// search retain the complete text. A long word or unspaced language keeps its prefix.
const SPOKEN_SUBJECT_CAP = 120;
export function spokenSubject(value) {
  const words = labelWords(value);
  const points = [...words];
  if (points.length <= SPOKEN_SUBJECT_CAP) return words;
  const excerpt = points.slice(0, SPOKEN_SUBJECT_CAP - 1);
  const boundary = excerpt.lastIndexOf(" ");
  const end = boundary >= SPOKEN_SUBJECT_CAP / 2 ? boundary : excerpt.length;
  return `${excerpt.slice(0, end).join("")}…`;
}
