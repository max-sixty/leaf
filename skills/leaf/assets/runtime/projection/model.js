// @ts-check
/* Pure projection folding.

   Callers normalize server records and pending browser values at their boundaries.
   This module combines those values without consulting the DOM, registry, runtime
   state, or delivery state. Authored snapshots have the same shape captured by
   projection/authored.js: a map from widget id to `{state, specs}`. */

/** @typedef {import("../../../../../build/browser/domain.ts").ProjectionEntry} ProjectionEntry */
/** @typedef {import("../../../../../build/browser/domain.ts").ClassifiedEntry} ClassifiedEntry */
/** @typedef {import("../../../../../build/browser/domain.ts").AuthoredMap} AuthoredMap */
/** @typedef {import("../../../../../build/browser/domain.ts").StandingValue} StandingValue */
/** @typedef {import("../../../../../build/browser/domain.ts").UnitValue} UnitValue */
/** @typedef {import("../../../../../build/browser/domain.ts").PositionValue} PositionValue */
/** @typedef {import("../../../../../build/browser/domain.ts").Projection} Projection */
/** @param {{detail: Record<string, unknown>}} event @param {import("../../../../../build/browser/domain.ts").StateRecord} record */
export function foldedValue(event, record) {
  const value = event.detail.value;
  if (record.kind === "attribute") {
    // Unresolved detail has not passed admission. Only iterable attribute values
    // can be drawn; the server remains the owner of the declared detail schema.
    if (typeof value === "string" || Array.isArray(value))
      return [...value].sort().join(" ");
  }
  return value ?? null;
}

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
/** @param {import("../../../../../build/browser/domain.ts").ProjectionInput} input @returns {Projection} */
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
  /** @type {Map<string, ProjectionEntry[]>} */
  const reports = new Map();
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
  for (const id of reportIds) {
    const entry = byId.get(id);
    if (!entry || entry.terminal) continue;
    const standing = reports.get(entry.coordinate) ?? [];
    standing.push(entry);
    reports.set(entry.coordinate, standing);
  }
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
  if (record?.kind === "attribute" && Array.isArray(value)) return value.join(" ");
  if (record?.kind === "position" && "units" in state)
    return (
      Object.keys(state.value).find((container) =>
        state.value[container]?.includes(unit),
      ) ?? null
    );
  return value;
};

// Derive the durable provenance attached to each standing unit from the same values
// that render widget state. One unit has at most one reading for each origin.
/** @param {AuthoredMap} authoredSnapshots @param {Projection} projection */
export function projectionOrigins(authoredSnapshots, projection) {
  /** @type {Map<string, {origin: string, unit: string}>} */
  const origins = new Map();
  /** @param {string} origin @param {string} unit */
  const add = (origin, unit) => {
    const key = `${origin}:${unit}`;
    if (!origins.has(key)) origins.set(key, { origin, unit });
  };

  for (const entry of projection.classified.values())
    for (const unit of entry.restated ?? []) add("restated", unit);

  for (const entry of projection.desired.values()) {
    const { unit, e, spec, value } = entry;
    const overridesSource = spec.record
      ? value !== authoredValue(authoredSnapshots, entry)
      : true;
    if (!overridesSource) continue;
    add(e.kind === "action" ? "user" : "reported", unit);
  }
  return [...origins.values()];
}

/* Rank keys: where a unit stands among its container's siblings, as a coordinate of its
   own.

   A position record carries a rank rather than an index. A rank is a base-36 fraction
   written as its digits after the point, `0-9a-z`, never ending in `0`, so ordinary
   string order is numeric order and there is always a key strictly between two others.
   A container lists its units by rank, ties by id. An index counts siblings, so it means
   something only against the order the other moves left; a rank means the same thing
   whichever of the other moves stand, so undoing or superseding one card's move never
   shifts another card.

   Authored units rank by their authored index, `authoredRank(i)`, a key that does not
   depend on how many siblings follow. `projection.py`'s `authored_rank` and `RANK`
   state the same two rules for the Python fold and the append door, and
   `tests/rank_cases.json` holds both runtimes to the same cases.

   A rank lies among the container's authored units on the revision the user moved on,
   so it holds while a revision authors them the same way. A revision that authors them
   differently absorbs the move: it writes the unit where the move left it, and its
   markup places the unit. The server marks such an entry `absorbed` for the document
   it reads, and it no longer places its unit. */

const DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz";

/** @param {number} index */
export const authoredRank = (index) =>
  "z".repeat(Math.floor(index / 35)) + DIGITS.charAt((index % 35) + 1);

/** @param {Record<string, string>} ranks */
const byRank = (ranks) => /** @param {string} a @param {string} b */ (a, b) => {
  const left = ranks[a];
  const right = ranks[b];
  if (left !== undefined && right !== undefined && left !== right)
    return left < right ? -1 : 1;
  return a < b ? -1 : a > b ? 1 : 0;
};

// A key strictly between `before` ("" is the start) and `after` (null is the end).
// Equal bounds have nothing between them, so the key ties and ids decide. An open end
// steps one digit past its neighbour rather than halving the gap, so a column that only
// ever grows at one end gains a character per 35 drops rather than per 5; an empty
// container starts in the middle.
/** @param {string} before @param {string | null} after @returns {string} */
function rankBetween(before, after) {
  if (after === null) return before ? rankAfter(before) : "i";
  if (!before) return rankBefore(after);
  if (before >= after) return before;
  return midpoint(before, after);
}

/** @param {string} key @returns {string} */
function rankAfter(key) {
  const digit = DIGITS.indexOf(key.charAt(0));
  if (digit < DIGITS.length - 1) return DIGITS.charAt(digit + 1);
  return "z" + (key.length > 1 ? rankAfter(key.slice(1)) : "1");
}

/** @param {string} key @returns {string} */
function rankBefore(key) {
  if (key.length > 1 && key.charAt(0) !== "0") return key.charAt(0);
  const digit = DIGITS.indexOf(key.charAt(0));
  if (digit > 1) return DIGITS.charAt(digit - 1);
  return "0" + (key.length > 1 ? rankBefore(key.slice(1)) : "z");
}

/** @param {string} before @param {string | null} after @returns {string} */
function midpoint(before, after) {
  if (after !== null) {
    let n = 0;
    while ((before[n] ?? "0") === after[n]) n += 1;
    if (n > 0) return after.slice(0, n) + midpoint(before.slice(n), after.slice(n));
  }
  const low = before ? DIGITS.indexOf(before.charAt(0)) : 0;
  const high = after !== null ? DIGITS.indexOf(after.charAt(0)) : DIGITS.length;
  if (high - low > 1) return DIGITS.charAt(Math.round((low + high) / 2));
  if (after !== null && after.length > 1) return after.charAt(0);
  return DIGITS.charAt(low) + midpoint(before.slice(1), null);
}

// The rank that puts `unit` at `index` among the other units a position verb's state
// lists in `container`: the widget's own reading of where a gesture dropped it.
/** @param {PositionValue} state @param {string} container @param {number} index @param {string} unit */
export function rankAt({ value, ranks }, container, index, unit) {
  const members = value[container];
  if (!members) throw new Error(`Unknown position container ${container}`);
  const others = members.filter((id) => id !== unit);
  const before = others[index - 1];
  const after = others[index];
  return rankBetween(
    before ? (ranks[before] ?? "") : "",
    after ? (ranks[after] ?? null) : null,
  );
}

// Compose complete verb values in memory. A position record the document has not
// absorbed places its unit at the rank it names, a coordinate of that unit's own (rank keys
// above), so each container lists its units by rank once every standing placement is
// in. `projection.py`'s `folded_positions` is the server's reading of the same rule.
/** @param {AuthoredMap} authoredSnapshots @param {Projection} projection */
export function foldWidgetStates(authoredSnapshots, projection) {
  // structuredClone creates a mutable owned graph. Its library type preserves the
  // source's readonly modifiers, so remove them only at this native-copy boundary.
  /** @param {import("../../../../../build/browser/snapshot.ts").Immutable<import("../../../../../build/browser/domain.ts").AuthoredWidget["state"]>} state */
  const copyState = (state) =>
    /** @type {import("../../../../../build/browser/domain.ts").AuthoredWidget["state"]} */ (
      structuredClone(state)
    );
  /** @type {Map<string, {state: import("../../../../../build/browser/domain.ts").AuthoredWidget["state"], entries: ProjectionEntry[], specs: ReadonlyMap<string, import("../../../../../build/browser/domain.ts").ActionSpec>}>} */
  const states = new Map(
    [...authoredSnapshots].map(([id, authored]) => [
      id,
      {
        state: copyState(authored.state),
        entries: [],
        specs: authored.specs,
      },
    ]),
  );
  /** @param {PositionValue} state @param {string} unit @param {Record<string, unknown>} detail */
  const place = ({ value: containers, ranks }, unit, detail) => {
    // A malformed unresolved move has no drawable position. Leave the authored
    // position until admission refuses it rather than failing the publication.
    if (typeof detail.value !== "string" || typeof detail.rank !== "string") return;
    const destination = containers[detail.value];
    if (!destination || !Object.values(containers).some((ids) => ids.includes(unit)))
      return;
    for (const ids of Object.values(containers)) {
      const index = ids.indexOf(unit);
      if (index >= 0) ids.splice(index, 1);
    }
    destination.push(unit);
    ranks[unit] = detail.rank;
  };

  for (const entry of [...projection.desired.values()].sort(compareProjected)) {
    const owner = states.get(entry.e.widget);
    if (!owner) continue;
    const { spec, e, unit } = entry;
    const record = spec.record;
    const value = record ? structuredClone(e.detail.value) : e.action;
    const standing = { action: e.action, value, detail: structuredClone(e.detail) };
    owner.entries.push(entry);
    const target = owner.state[e.action];
    if (target && "units" in target) {
      target.units[unit] = standing;
      if ("ranks" in target && !entry.absorbed) place(target, unit, e.detail);
    } else {
      if (spec.unit !== "widget")
        throw new Error(`Missing authored units for ${e.widget}/${e.action}`);
      owner.state[e.action] = standing;
    }
  }

  for (const { state } of states.values())
    for (const position of Object.values(state))
      if ("ranks" in position)
        for (const ids of Object.values(position.value))
          ids.sort(byRank(position.ranks));
  return states;
}

/** @param {ClassifiedEntry} entry @returns {entry is ProjectionEntry} */
export const isProjectionEntry = (entry) => entry.coordinate !== undefined;
