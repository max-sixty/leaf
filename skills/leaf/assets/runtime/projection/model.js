/* Pure projection folding.

   Callers normalize server records and pending browser values at their boundaries.
   This module combines those values without consulting the DOM, registry, runtime
   state, or delivery state. Authored snapshots have the same shape captured by
   projection/authored.js: a map from widget id to `{state, specs, positions}`. */

// Keep this spelling aligned with passages.js's cross-runtime whitespace reading.
const COLLAPSE =
  /[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+/g;

export function foldedValue(event, record) {
  const value = event.detail[record.value];
  if (record.kind === "body")
    return String(value ?? "")
      .replace(COLLAPSE, " ")
      .trim();
  if (record.kind === "attribute") return [...value].sort().join(" ");
  return value ?? null;
}

const compareProjected = (a, b) => {
  const aLogged = Number.isInteger(a.e.seq);
  const bLogged = Number.isInteger(b.e.seq);
  if (aLogged && bLogged) return a.e.seq - b.e.seq;
  if (aLogged) return -1;
  if (bLogged) return 1;
  return a.localOrder - b.localOrder;
};

/* Fold normalized durable entries and pending local gestures into the canonical
   projection views. Each entry carries `coordinate`, `e`, `unit`, `spec`, and `value`;
   it may also carry `restated`, `scope`, or `terminal`. Pending entries are already
   filtered for rejection and authoritative receipts by their delivery owner. A pending
   undo removes its target from the same coordinate fold, revealing the newest surviving
   local action, durable action, or authored state in that order. A verb has one writer,
   so a coordinate a local gesture reaches never holds an agent's report. */
/** @param {{entries?: object[], actionIds?: string[], reportIds?: string[], desiredIds?: string[], coverage?: object[], pendingEntries?: object[]}} input */
export function foldProjection({
  entries = [],
  actionIds = [],
  reportIds = [],
  desiredIds = [],
  coverage = [],
  pendingEntries = [],
} = {}) {
  const actions = new Map();
  const reports = new Map();
  const classified = new Map();
  const desired = new Map();
  const byId = new Map();
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

  const durableWithdrawn = new Set(
    coverage
      .map(({ event }) => event)
      .filter((event) => event.kind === "undo")
      .map((event) => event.undoes),
  );
  const pendingActions = [];
  const withdrawn = new Set();
  const recompute = (coordinate) => {
    const local = pendingActions
      .filter((entry) => entry.coordinate === coordinate && !withdrawn.has(entry.e.id))
      .at(-1);
    const durable = [...classified.values()]
      .filter(
        (entry) =>
          !entry.terminal &&
          entry.coordinate === coordinate &&
          entry.e.kind === "action" &&
          !entry.restated?.length &&
          !durableWithdrawn.has(entry.e.id) &&
          !withdrawn.has(entry.e.id),
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
      const targetId =
        entry.targetEntry?.acceptedId ??
        entry.targetEntry?.readEvent?.id ??
        entry.target.e.id;
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

const authoredValue = (authoredSnapshots, coordinate) => {
  const [owner, unit, verb] = JSON.parse(coordinate);
  const authored = authoredSnapshots.get(owner);
  if (!authored) return undefined;
  const spec = authored.specs.get(verb);
  const record = spec.record;
  const value = authored.state[verb].value;
  if (record?.kind === "attribute") return value.join(" ");
  if (record?.kind === "body") return value.replace(COLLAPSE, " ").trim();
  if (record?.kind === "position" && spec.unit !== "widget")
    return (
      Object.keys(value).find((container) => value[container].includes(unit)) ?? null
    );
  return value;
};

// Derive the durable provenance attached to each standing unit from the same values
// that render widget state. One unit has at most one reading for each origin.
export function projectionOrigins(authoredSnapshots, projection) {
  const origins = new Map();
  const add = (origin, unit) => {
    const key = `${origin}:${unit}`;
    if (!origins.has(key)) origins.set(key, { origin, unit });
  };

  for (const entry of projection.classified.values())
    for (const unit of entry.restated ?? []) add("restated", unit);

  for (const [coordinate, { unit, e, spec, value }] of projection.desired) {
    const overridesSource = spec.record
      ? value !== authoredValue(authoredSnapshots, coordinate)
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
   state the same two rules for the Python fold and the append door; keep them aligned. */

const DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz";

export const authoredRank = (index) =>
  "z".repeat(Math.floor(index / 35)) + DIGITS[(index % 35) + 1];

const byRank = (ranks) => (a, b) =>
  ranks[a] < ranks[b] ? -1 : ranks[a] > ranks[b] ? 1 : a < b ? -1 : a > b ? 1 : 0;

// The shortest key strictly between `before` ("" is the start) and `after` (null is the
// end). Equal bounds have nothing between them, so the key ties and ids decide.
function rankBetween(before, after) {
  if (after !== null && before >= after) return before;
  if (after !== null) {
    let n = 0;
    while ((before[n] ?? "0") === after[n]) n += 1;
    if (n > 0) return after.slice(0, n) + rankBetween(before.slice(n), after.slice(n));
  }
  const low = before ? DIGITS.indexOf(before[0]) : 0;
  const high = after !== null ? DIGITS.indexOf(after[0]) : DIGITS.length;
  if (high - low > 1) return DIGITS[Math.round((low + high) / 2)];
  if (after !== null && after.length > 1) return after[0];
  return DIGITS[low] + rankBetween(before.slice(1), null);
}

// The rank that puts `unit` at `index` among the other units a position verb's state
// lists in `container`: the widget's own reading of where a gesture dropped it.
export function rankAt({ value, ranks }, container, index, unit) {
  const others = value[container].filter((id) => id !== unit);
  return rankBetween(ranks[others[index - 1]] ?? "", ranks[others[index]] ?? null);
}

// Compose complete verb values in memory. A position record places its unit at the
// rank it names, a coordinate of that unit's own (rank keys above), so each
// container lists its units by rank once every standing placement is in.
export function foldWidgetStates(authoredSnapshots, projection) {
  const states = new Map(
    [...authoredSnapshots].map(([id, authored]) => [
      id,
      {
        state: structuredClone(authored.state),
        entries: [],
        specs: authored.specs,
      },
    ]),
  );
  const positions = Object.assign(
    {},
    ...[
      ...new Set([...authoredSnapshots.values()].map(({ positions }) => positions)),
    ].map((value) => structuredClone(value)),
  );
  const positionRanks = Object.fromEntries(
    Object.values(positions).flatMap((ids) =>
      ids.map((id, index) => [id, authoredRank(index)]),
    ),
  );
  const place = (containers, ranks, unit, record, detail) => {
    const destination = containers[detail[record.value]];
    if (!destination || !Object.values(containers).some((ids) => ids.includes(unit)))
      return;
    for (const ids of Object.values(containers)) {
      const index = ids.indexOf(unit);
      if (index >= 0) ids.splice(index, 1);
    }
    destination.push(unit);
    ranks[unit] = detail[record.rank];
  };
  const list = (containers, ranks) => {
    for (const ids of Object.values(containers)) ids.sort(byRank(ranks));
  };

  for (const entry of [...projection.desired.values()].sort(compareProjected)) {
    const owner = states.get(entry.e.widget);
    if (!owner) continue;
    const { spec, e, unit } = entry;
    const record = spec.record;
    const value = record ? structuredClone(e.detail[record.value]) : e.action;
    const standing = { action: e.action, value, detail: structuredClone(e.detail) };
    owner.entries.push(entry);
    if (spec.unit === "widget") {
      owner.state[e.action] = standing;
      if (record?.kind === "position")
        place(positions, positionRanks, unit, record, e.detail);
    } else {
      const target = owner.state[e.action];
      target.units[unit] = standing;
      if (record?.kind === "position")
        place(target.value, target.ranks, unit, record, e.detail);
    }
  }
  list(positions, positionRanks);

  for (const [id, owner] of states) {
    const { state, specs } = owner;
    for (const [verb, spec] of specs) {
      if (spec.record?.kind !== "position") continue;
      if (spec.unit !== "widget") {
        list(state[verb].value, state[verb].ranks);
        continue;
      }
      const record = spec.record;
      const container = Object.keys(positions).find((key) =>
        positions[key].includes(id),
      );
      if (!container) continue;
      state[verb].value = container;
      state[verb].detail[record.value] = container;
      state[verb].detail[record.rank] = positionRanks[id];
      state[verb].index = positions[container].indexOf(id);
      owner.order = [container, state[verb].index];
    }
  }

  return new Map(
    [...states].sort(([, a], [, b]) => {
      const left = a.order ?? ["", -1];
      const right = b.order ?? ["", -1];
      return left[0].localeCompare(right[0]) || left[1] - right[1];
    }),
  );
}
