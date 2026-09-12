/* Pure projection folding.

   Callers normalize server records and pending browser values at their boundaries.
   This module combines those values without consulting the DOM, registry, runtime
   state, or delivery state. Authored snapshots have the same shape captured by
   projection/authored.js: a map from widget id to `{state, specs, positions}`. */

// Keep this spelling aligned with passages.js's cross-runtime whitespace reading.
const COLLAPSE =
  /[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+/g;

export function foldedFacet(event, record) {
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
   local action, durable action, standing report, or authored state in that order. */
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
    if (action) actions.set(coordinate, action);
    else actions.delete(coordinate);
    const report = reports.get(coordinate)?.at(-1);
    if (action) desired.set(coordinate, action);
    else if (report) desired.set(coordinate, report);
    else desired.delete(coordinate);
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

const authoredFacet = (authoredSnapshots, coordinate) => {
  const [owner, unit, facet] = JSON.parse(coordinate);
  const authored = authoredSnapshots.get(owner);
  if (!authored) return undefined;
  const spec = authored.specs.get(facet);
  const record = spec.record;
  const value = authored.state[facet].value;
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
      ? value !== authoredFacet(authoredSnapshots, coordinate)
      : true;
    if (!overridesSource) continue;
    add(e.kind === "action" ? "reader" : "reported", unit);
  }
  return [...origins.values()];
}

// Compose complete facet values in memory. Absolute placements for independent
// coordinates share their authored container ordering and are folded before rendering.
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
  const place = (containers, unit, record, detail) => {
    const destination = containers[detail[record.value]];
    if (!destination || !Object.values(containers).some((ids) => ids.includes(unit)))
      return;
    for (const ids of Object.values(containers)) {
      const index = ids.indexOf(unit);
      if (index >= 0) ids.splice(index, 1);
    }
    destination.splice(detail[record.order], 0, unit);
  };

  for (const entry of [...projection.desired.values()].sort(compareProjected)) {
    const owner = states.get(entry.e.widget);
    if (!owner) continue;
    const { spec, e, unit } = entry;
    const record = spec.record;
    const value = record ? structuredClone(e.detail[record.value]) : e.action;
    const facet = { action: e.action, value, detail: structuredClone(e.detail) };
    owner.entries.push(entry);
    if (spec.unit === "widget") {
      owner.state[spec.facet] = facet;
      if (record?.kind === "position") place(positions, unit, record, e.detail);
    } else {
      const target = owner.state[spec.facet];
      target.units[unit] = facet;
      if (record?.kind === "position") place(target.value, unit, record, e.detail);
    }
  }

  for (const [id, owner] of states) {
    const { state, specs } = owner;
    for (const [facet, spec] of specs) {
      if (spec.unit !== "widget" || spec.record?.kind !== "position") continue;
      const record = spec.record;
      const container = Object.keys(positions).find((key) =>
        positions[key].includes(id),
      );
      if (!container) continue;
      state[facet].value = container;
      state[facet].detail[record.value] = container;
      state[facet].detail[record.order] = positions[container].indexOf(id);
      owner.order = [container, positions[container].indexOf(id)];
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
