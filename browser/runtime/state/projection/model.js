// @ts-check
/* Pure projection folding.

   Callers normalize server records and pending browser values at their boundaries.
   This module combines those values without consulting the DOM, registry, runtime
   state, or delivery state. Authored snapshots have the same shape captured by
   records/projection/authored.js: a map from widget id to `{state, specs}`. */

import { keptEach } from "../kept.js";
import { byRank } from "../../lib/rank.js";

/** @typedef {import("../../../types/domain.js").ProjectionEntry} ProjectionEntry */
/** @typedef {import("../../../types/domain.js").ClassifiedEntry} ClassifiedEntry */
/** @typedef {import("../../../types/domain.js").AuthoredMap} AuthoredMap */
/** @typedef {import("../../../types/domain.js").ActionValue} ActionValue */
/** @typedef {import("../../../types/domain.js").UnitValue} UnitValue */
/** @typedef {import("../../../types/domain.js").PositionValue} PositionValue */
/** @typedef {import("../../../types/domain.js").Projection} Projection */
// A state coordinate, `[owner, unit, verb]`, as the key the folds index it by. The
// server sends the tuple (`projection.py`); the browser keys and reads it back here.
/** @param {string} owner @param {string} unit @param {string} verb */
export const stateCoordinate = (owner, unit, verb) =>
  JSON.stringify([owner, unit, verb]);
/** @param {string} key @returns {[string, string, string]} */
export const coordinateOf = (key) => JSON.parse(key);

/** @param {{detail: Record<string, unknown>}} event @param {import("../../../types/domain.js").StateRecord} record */
export function foldedValue(event, record) {
  const value = event.detail.value;
  // An attribute record is a set, which the server's value lists sorted
  // (`projection.folded_value`); a pending action's value takes the same shape.
  // Unresolved detail has not passed admission, so a value that is no list is drawn
  // as it came until admission refuses it.
  if (record.kind === "attribute" && Array.isArray(value)) return value.toSorted();
  return value ?? null;
}

// Whether one value says the same as another: values are JSON, and an
// attribute record's is a sorted list.
/** @param {unknown} a @param {unknown} b */
const sameValue = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/** @param {ProjectionEntry} a @param {ProjectionEntry} b */
const compareProjected = (a, b) => {
  const aLogged = Number.isInteger(a.e.seq);
  const bLogged = Number.isInteger(b.e.seq);
  if (aLogged && bLogged) return (a.e.seq ?? 0) - (b.e.seq ?? 0);
  if (aLogged) return -1;
  if (bLogged) return 1;
  return (a.localOrder ?? 0) - (b.localOrder ?? 0);
};

/* Fold normalized durable entries and pending local gestures into the canonical
   projection views. Each entry carries `coordinate`, `e`, `unit`, `spec`, and `value`;
   it may also carry `restated`, `absorbed`, `stands`, `scope`, or `terminal`. Pending
   entries are already filtered for rejection and authoritative receipts by their
   delivery owner. A pending undo removes its target from the same coordinate fold,
   revealing the newest surviving local action, the newest durable action the server
   says `stands`, or authored state in that order. A verb has one writer, so a
   coordinate a local gesture reaches never holds an agent's report. */
/** @param {import("../../../types/domain.js").ProjectionInput} input @returns {Projection} */
export function foldProjection({
  entries = [],
  actionIds = [],
  reportIds = [],
  desiredIds = [],
  coverage = [],
  pendingEntries = [],
} = {}) {
  /** @type {Map<string, ProjectionEntry>} */
  const actions = new Map();
  /** @type {Map<string, ClassifiedEntry>} */
  const classified = new Map();
  /** @type {Map<string, ProjectionEntry>} */
  const desired = new Map();
  /** @type {Map<string, ProjectionEntry>} */
  const byId = new Map();
  /** @type {Map<string, ClassifiedEntry>} */
  const pendingWithdrawals = new Map();

  for (const entry of entries) {
    classified.set(entry.e.id, entry);
    byId.set(entry.e.id, entry);
  }

  for (const id of actionIds) {
    const entry = byId.get(id);
    if (entry && !entry.terminal) actions.set(entry.coordinate, entry);
  }
  const reports = Map.groupBy(
    reportIds.flatMap((id) => byId.get(id) ?? []).filter((entry) => !entry.terminal),
    (entry) => entry.coordinate,
  );
  for (const id of desiredIds) {
    const entry = byId.get(id);
    if (entry && !entry.terminal) desired.set(entry.coordinate, entry);
  }

  // Coverage can contain invalid, retired, or out-of-window records that have no
  // normalized entry. They remain classified so readiness accounts for them once.
  for (const record of coverage) {
    const e = record.event;
    if (e.kind === "undo" || classified.has(e.id)) continue;
    classified.set(e.id, { e, terminal: record.coordinate === null });
  }

  /** @type {ProjectionEntry[]} */
  const pendingActions = [];
  /** @type {Set<string>} */
  const withdrawn = new Set();
  /** @param {string} coordinate */
  const recompute = (coordinate) => {
    const local = pendingActions
      .filter((entry) => entry.coordinate === coordinate && !withdrawn.has(entry.e.id))
      .at(-1);
    const durable = [...classified.values()]
      .filter(
        /** @returns {entry is ProjectionEntry} */
        (entry) =>
          Boolean(
            entry.stands &&
            entry.coordinate === coordinate &&
            !withdrawn.has(entry.e.id),
          ),
      )
      .sort(compareProjected)
      .at(-1);
    const action = local ?? durable;
    for (const view of [actions, desired])
      if (action) view.set(coordinate, action);
      else view.delete(coordinate);
  };

  for (const entry of pendingEntries) {
    if (entry.kind === "undo") {
      const targetId = entry.targetId ?? entry.target.e.id;
      const target = classified.get(targetId) ?? entry.target;
      withdrawn.add(targetId);
      pendingWithdrawals.set(targetId, target);
      recompute(entry.coordinate);
      continue;
    }
    pendingActions.push(entry);
    recompute(entry.coordinate);
  }

  return { actions, reports, classified, desired, pendingWithdrawals };
}

/** @param {AuthoredMap} authoredSnapshots @param {ProjectionEntry} entry */
const authoredValue = (
  authoredSnapshots,
  { unit, e: { widget: owner, action: verb } },
) => {
  const authored = authoredSnapshots.get(owner);
  if (!authored) return undefined;
  const spec = authored.specs.get(verb);
  const state = authored.state[verb];
  if (!spec || !state) throw new Error(`Missing authored state for ${owner}/${verb}`);
  const record = spec.record;
  const value = state.value;
  if (record?.kind === "position" && "units" in state)
    return (
      Object.keys(state.value).find((container) =>
        state.value[container]?.includes(unit),
      ) ?? null
    );
  return value;
};

// Derive the durable provenance attached to each unit in force from the same values
// that render widget state. One unit has at most one reading for each origin.
/** @param {AuthoredMap} authoredSnapshots @param {Projection} projection */
export function projectionOrigins(authoredSnapshots, projection) {
  /** @type {Map<string, {origin: "restated" | "user" | "reported", unit: string}>} */
  const origins = new Map();
  /** @param {"restated" | "user" | "reported"} origin @param {string} unit */
  const add = (origin, unit) => {
    const key = `${origin}:${unit}`;
    if (!origins.has(key)) origins.set(key, { origin, unit });
  };

  for (const entry of projection.classified.values())
    for (const unit of entry.restated ?? []) add("restated", unit);

  for (const entry of projection.desired.values()) {
    const { unit, e, spec, value } = entry;
    const overridesSource = spec.record
      ? !sameValue(value, authoredValue(authoredSnapshots, entry))
      : true;
    if (!overridesSource) continue;
    add(e.kind === "action" ? "user" : "reported", unit);
  }
  return [...origins.values()];
}

// Compose complete verb values in memory. A position record the document has not
// absorbed places its unit at the rank it names, a coordinate of that unit's own
// (lib/rank.js), so each container lists its units by rank once every placement in force is
// in. `projection.py`'s `folded_positions` is the server's reading of the same rule.
//
// Each widget's folded state is kept (`state/kept.js`) by its authored state and the entries
// in force on it, so every widget nothing touched keeps the very state it had, and a
// reader of one, such as a thread holding a widget, can tell it unchanged by identity.
/** @typedef {{state: import("../../../types/domain.js").AuthoredWidget["state"], entries: ProjectionEntry[], specs: ReadonlyMap<string, import("../../../types/domain.js").ActionSpec>}} FoldedWidget */
/** @param {AuthoredMap} authoredSnapshots @param {Projection} projection */
export function foldWidgetStates(authoredSnapshots, projection) {
  /** @type {Map<string, ProjectionEntry[]>} */
  const inForce = new Map();
  for (const entry of [...projection.desired.values()].sort(compareProjected)) {
    const entries = inForce.get(entry.e.widget);
    if (entries) entries.push(entry);
    else inForce.set(entry.e.widget, [entry]);
  }
  /** @type {Map<string, FoldedWidget>} */
  const states = new Map();
  for (const [id, authored] of authoredSnapshots)
    states.set(id, foldedWidget(authored, inForce.get(id) ?? NO_ENTRIES));
  return states;
}
/** @type {readonly ProjectionEntry[]} */
const NO_ENTRIES = Object.freeze([]);

// One widget's state: its authored state with each entry in force on it applied, in
// the order the projection ranks them.
const foldedWidget = keptEach(
  /** @param {AuthoredMap extends ReadonlyMap<string, infer W> ? W : never} authored
   * @param {readonly ProjectionEntry[]} entries */
  (authored, entries) => foldWidget(authored, [...entries]),
);
/** @param {AuthoredMap extends ReadonlyMap<string, infer W> ? W : never} authored
 * @param {ProjectionEntry[]} entries @returns {FoldedWidget} */
function foldWidget(authored, entries) {
  // structuredClone creates a mutable owned graph. Its library type preserves the
  // source's readonly modifiers, so remove them only at this native-copy boundary.
  const state =
    /** @type {import("../../../types/domain.js").AuthoredWidget["state"]} */ (
      structuredClone(authored.state)
    );
  /** @param {PositionValue} state @param {string} unit @param {Record<string, unknown>} detail */
  const place = ({ value: containers, ranks }, unit, detail) => {
    const { value, rank } = /** @type {{value: string, rank: string}} */ (detail);
    const destination = containers[value];
    // A later revision may remove a moved unit or its destination.
    if (!destination || !Object.values(containers).some((ids) => ids.includes(unit)))
      return;
    for (const ids of Object.values(containers)) {
      const index = ids.indexOf(unit);
      if (index >= 0) ids.splice(index, 1);
    }
    destination.push(unit);
    ranks[unit] = rank;
  };
  for (const entry of entries) {
    const { spec, e, unit } = entry;
    const record = spec.record;
    const value = record ? structuredClone(e.detail.value) : e.action;
    const current = { action: e.action, value, detail: structuredClone(e.detail) };
    const target = state[e.action];
    if (target && "units" in target) {
      target.units[unit] = current;
      if ("ranks" in target && !entry.absorbed) place(target, unit, e.detail);
    } else {
      if (spec.unit !== "widget")
        throw new Error(`Missing authored units for ${e.widget}/${e.action}`);
      state[e.action] = current;
    }
  }
  for (const position of Object.values(state))
    if ("ranks" in position)
      for (const ids of Object.values(position.value)) ids.sort(byRank(position.ranks));
  return { state, entries, specs: authored.specs };
}

/* An obligation reads its value from the same complete fold as its widget. Completion
   can make an empty recorded value an answer, but cannot invent custom state after
   undo removes its action. Python's projection.obligation_value owns the same reading;
   the shared obligation-value cases exercise both runtimes. */
/** @param {import("../../base/snapshot.js").Immutable<Pick<import("../../../types/domain.js").AuthoredWidget, "state" | "specs">>} widget
 * @param {string} verb @param {boolean} answered */
export function obligationValue(widget, verb, answered) {
  const state = widget.state[verb];
  const spec = widget.specs.get(verb);
  if (!state || !spec)
    throw new Error(`Missing obligation value definition for ${verb}`);
  /** @param {unknown} value */
  const recorded = (value) =>
    spec.record?.kind === "attribute" && Array.isArray(value)
      ? value.toSorted()
      : value;
  const value =
    "units" in state
      ? spec.record?.kind === "position"
        ? state.value
        : Object.fromEntries(
            Object.entries(state.units)
              .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
              .map(([id, entry]) => [
                id,
                spec.record ? recorded(entry.value) : entry.detail,
              ]),
          )
      : spec.record
        ? recorded(state.value)
        : state.action
          ? state.detail
          : null;
  const hasInput =
    "units" in state ? Object.keys(state.units).length > 0 : Boolean(state.action);
  return {
    value,
    present: value !== null && (populated(value) || answered || hasInput),
  };
}

// Whether an obligation's value says something: neither absent, empty words nor an
// empty list or map.
/** @param {unknown} value */
const populated = (value) =>
  value !== null &&
  value !== "" &&
  (typeof value !== "object" || Object.keys(value).length > 0);

/* Whether the user's acts hold a state at `verb` on `widget`: an action in force there,
   one that records a non-empty value where the verb records one, or one at any of its
   members. What the markup holds counts for nothing, since only a gesture says a
   question is answered. It is what a widget that asks says of its obligation where its
   class says nothing of its own (`awaits`). */
/** @param {Parameters<typeof obligationValue>[0]} widget @param {string} verb */
export function holdsState(widget, verb) {
  const state = widget.state[verb];
  if (!state) return false;
  if ("units" in state) return Object.values(state.units).some((at) => at.action);
  if (!state.action) return false;
  return !widget.specs.get(verb)?.record || populated(state.value);
}

/** @param {ClassifiedEntry} entry @returns {entry is ProjectionEntry} */
export const isProjectionEntry = (entry) => entry.coordinate !== undefined;
