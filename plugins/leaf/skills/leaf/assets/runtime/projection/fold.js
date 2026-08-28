/* The server's durable projection, adapted to live DOM nodes plus the local outbox. */
export function createProjectionFold(runtime, dependencies) {
  const { COLLAPSE, domFacet, elementById, outbox } = dependencies;
  const { registry } = runtime;

  function foldedFacet(e, record) {
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

  function projectionFromView(view, conversation = runtime.browser?.conversation) {
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

  function stateProjection() {
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

  const standingState = () => {
    const projection = stateProjection();
    return [...projection.desired]
      .sort(([, a], [, b]) => compareProjected(a, b))
      .map(([_coordinate, { unit, e, spec }]) => ({
        get widget() {
          return elementById(e.widget);
        },
        unit,
        facet: spec.facet,
        record: spec.record?.kind ?? null,
        action: e.action,
        detail: e.detail,
        read: () => {
          const el = spec.record && elementById(unit);
          return el ? domFacet(el, spec.record) : null;
        },
      }));
  };

  return {
    compareProjected,
    foldedFacet,
    projectionFromView,
    standingState,
    stateProjection,
  };
}
