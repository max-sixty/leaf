/* The server's durable projection, adapted to live DOM nodes plus the local outbox.

   The DOM is a projection of three ordered inputs:

   1. the authored state captured from this version;
   2. standing actions and reports in the server's transaction-consistent browser view;
   3. surviving optimistic recorded actions in the outbox.

   The semantic coordinate is `JSON.stringify([ownerWidgetId, unitId, facet])`. `x-state`
   and `x-report` declare the fold unit, facet, detail schema, and optional record form
   for every verb. `unitOf` finds the unit from the declaration. No core consumer
   branches on a widget tag or verb to determine state identity.

   The browser's `stateProjection` is a DOM adapter. It resolves those declared
   coordinates back to current widget modules and overlays unresolved local records. It
   does not derive retractions, settlements, thread structure, decisions, updates, or
   undo eligibility from raw events. Winners on independent coordinates still compose in
   event order through `compareProjected`.

   The two durable channels share the coordinate model but retain their meaning:

   - `x-state` records the reader's actions. The latest surviving action wins its
     coordinate.
   - `x-report` records provisional agent or worker state. Reports remain live until a
     version note answers their event ids.
   - A reader action wins over a live report on the same coordinate. Different facets on
     the same unit remain independent.

   `stateProjection` is uncached because registry declarations resolve through the live
   DOM. Thread construction and revision activation can introduce new nodes. Its result
   has four views: `actions`, `reports`, `classified`, and `desired`. Add a browser
   consumer to one of these views or extend the Python wire view instead of building
   another fold over raw `events`. */
import { runtime } from "../context.js";
import { COLLAPSE, elementById } from "../passages.js";
import { outbox } from "../outbox.js";
import { authoredStates, domFacet } from "./authored.js";
const { registry } = runtime;

export function foldedFacet(e, record) {
  const value = e.detail[record.value];
  if (record.kind === "body")
    return String(value ?? "")
      .replace(COLLAPSE, " ")
      .trim();
  if (record.kind === "attribute") return [...value].sort().join(" ");
  return value ?? null;
}

function compareProjected(a, b) {
  const aLogged = Number.isInteger(a.e.seq);
  const bLogged = Number.isInteger(b.e.seq);
  if (aLogged && bLogged) return a.e.seq - b.e.seq;
  if (aLogged) return -1;
  if (bLogged) return 1;
  return a.localOrder - b.localOrder;
}

const coordinateKey = (coordinate) => JSON.stringify(coordinate);
const domValue = (value, record) =>
  record?.kind === "attribute" ? value.join(" ") : value;

export function projectionFromView(view, conversation = runtime.browser?.conversation) {
  const actions = new Map();
  const reports = new Map();
  const classified = new Map();
  const desired = new Map();
  const byId = new Map();
  const projections = [view?.document?.projection, conversation?.projection].filter(
    Boolean,
  );

  for (const projection of projections) {
    for (const wire of projection.entries ?? []) {
      const e = wire.event;
      const coordinate = coordinateKey(wire.coordinate);
      const widget = elementById(e.widget);
      const channel = e.kind === "action" ? "x-state" : "x-report";
      const spec = widget && registry[widget.localName]?.[channel]?.[e.action];
      const entry = spec
        ? {
            coordinate,
            e,
            restated: wire.restated ?? [],
            scope: wire.scope,
            spec,
            unit: wire.coordinate[1],
            value: domValue(wire.value, spec.record),
          }
        : { coordinate, e, scope: wire.scope, terminal: true };
      classified.set(e.id, entry);
      byId.set(e.id, entry);
    }
  }

  for (const projection of projections) {
    for (const id of projection.actions ?? []) {
      const entry = byId.get(id);
      if (entry && !entry.terminal) actions.set(entry.coordinate, entry);
    }
    for (const id of projection.reports ?? []) {
      const entry = byId.get(id);
      if (!entry || entry.terminal) continue;
      const standing = reports.get(entry.coordinate) ?? [];
      standing.push(entry);
      reports.set(entry.coordinate, standing);
    }
    for (const id of projection.desired ?? []) {
      const entry = byId.get(id);
      if (entry && !entry.terminal) desired.set(entry.coordinate, entry);
    }
  }

  // Invalid, retired, and out-of-window records are still complete readings. They do
  // not name a DOM coordinate, but readiness must account for them once rather than
  // waiting forever for a node the canonical projector says cannot receive them.
  for (const record of view?.coverage ?? []) {
    const e = record.event;
    if (e.kind === "undo" || classified.has(e.id)) continue;
    classified.set(e.id, { e, terminal: record.coordinate === null });
  }

  return { actions, reports, classified, desired };
}

export function stateProjection() {
  const projection = projectionFromView(runtime.view);
  const loggedAttempts = new Set(
    (runtime.browser?.receipts ?? []).map((e) => e.attempt).filter(Boolean),
  );
  // A gesture already painted by its widget remains the newest local statement until
  // one complete server snapshot both contains its receipt and has been reconciled.
  for (const out of outbox) {
    const entry = out.projection;
    if (!entry || out.rejected || loggedAttempts.has(out.event.attempt)) continue;
    projection.actions.set(entry.coordinate, entry);
    projection.desired.set(entry.coordinate, entry);
  }
  return projection;
}

// Compose final values in memory. A placement action is absolute for its unit,
// but several placements share one ordered container; fold their winners once
// before any renderer moves a node.
export function widgetStates(projection = stateProjection()) {
  const states = new Map(
    [...authoredStates].map(([id, authored]) => [
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
    ...[...new Set([...authoredStates.values()].map(({ positions }) => positions))].map(
      (positions) => structuredClone(positions),
    ),
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
    for (const [facet, spec] of specs)
      if (spec.unit === "widget" && spec.record?.kind === "position") {
        const record = spec.record;
        const container = Object.keys(positions).find((key) =>
          positions[key].includes(id),
        );
        if (container) {
          state[facet].value = container;
          state[facet].detail[record.value] = container;
          state[facet].detail[record.order] = positions[container].indexOf(id);
          owner.order = [container, positions[container].indexOf(id)];
        }
      }
  }
  // Widget-absolute placements share a physical ordering boundary despite having
  // independent state owners. Place them in final order, exactly as a container
  // renderer consumes its complete ordered list.
  return new Map(
    [...states].sort(([, a], [, b]) => {
      const left = a.order ?? ["", -1];
      const right = b.order ?? ["", -1];
      return left[0].localeCompare(right[0]) || left[1] - right[1];
    }),
  );
}

// Restricting the desired winners lets the render gate observe what carried
// decisions alone paint. It never revives a superseded event or changes the log.
export function standingState(eventIds = null) {
  const projection = stateProjection();
  if (eventIds !== null) {
    const included = new Set(eventIds);
    projection.desired = new Map(
      [...projection.desired].filter(([, entry]) => included.has(entry.e.id)),
    );
  }
  return [...widgetStates(projection)].map(([id, { state, specs }]) => ({
    get widget() {
      return elementById(id);
    },
    state,
    read: () =>
      [...specs]
        .filter(([, spec]) => spec.record?.kind === "body")
        .map(([facet, spec]) => [facet, domFacet(elementById(id), spec.record)]),
  }));
}
