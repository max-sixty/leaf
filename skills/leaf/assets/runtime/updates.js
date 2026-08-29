/* Canonical action and update feeds exposed to widgets and chrome. */
let publishedActionSequence;
let publishedPublishedAt;
let publishedSaidAt;
let publishedUpdateSequence;
let publishedWatchActions;
let publishedWatchHistory;
let publishedWatchUpdates;
export {
  publishedActionSequence as actionSequence,
  publishedPublishedAt as publishedAt,
  publishedSaidAt as saidAt,
  publishedUpdateSequence as updateSequence,
  publishedWatchActions as watchActions,
  publishedWatchHistory as watchHistory,
  publishedWatchUpdates as watchUpdates,
};

export function createUpdates(runtime, dependencies) {
  const {
    closestAcross,
    coordinateProjectionCommitted,
    projectionCommitted,
    stateProjection,
  } = dependencies;

  let claimState = Object.freeze({
    sources: Object.freeze([]),
    claimsHeld: false,
    agentTurnClosed: null,
    claimingSession: null,
  });
  function replaceClaimState(next) {
    const prior = claimState;
    claimState = Object.freeze({
      sources: Object.freeze(structuredClone(next.sources)),
      claimsHeld: next.claimsHeld,
      agentTurnClosed: next.agentTurnClosed,
      claimingSession: next.claimingSession,
    });
    return () => (claimState = prior);
  }
  const workClaimState = () => ({
    claimsHeld: claimState.claimsHeld,
    agentTurnClosed: claimState.agentTurnClosed,
    claimingSession: claimState.claimingSession,
  });

  const actionSequence = (widget, action) => {
    const projection = stateProjection();
    return [...projection.classified.values()]
      .filter(
        (entry) =>
          !entry.terminal &&
          entry.e.kind === "action" &&
          entry.e.widget === widget.id &&
          (!action || entry.e.action === action) &&
          projectionCommitted(projection, entry.e),
      )
      .sort((left, right) => left.e.seq - right.e.seq)
      .map((entry) => structuredClone(entry.e));
  };

  function updateTarget(target) {
    if (target === null) return null;
    if (target instanceof Element) {
      if (target.id) return { kind: "widget", id: target.id };
    } else if (
      ["widget", "thread"].includes(target?.kind) &&
      typeof target.id === "string" &&
      target.id
    ) {
      return { kind: target.kind, id: target.id };
    }
    throw new TypeError(
      "update target must be a widget element or {kind: 'widget' | 'thread', id}",
    );
  }
  const targetKey = (target) =>
    target ? JSON.stringify([target.kind, target.id]) : null;
  const updateSequence = (target = null) => {
    const key = targetKey(updateTarget(target));
    return (runtime.view?.updates ?? [])
      .filter((update) => key === null || targetKey(update.target) === key)
      .map((update) => structuredClone(update));
  };

  function reportsCommitted(projection, target) {
    const key = targetKey(updateTarget(target));
    const coordinates = new Map();
    for (const entry of projection.classified.values()) {
      if (entry.terminal || entry.e.kind !== "report") continue;
      const entryKey = targetKey({ kind: "widget", id: entry.e.widget });
      if (key === null || key === entryKey) coordinates.set(entry.coordinate, entry);
    }
    return [...coordinates.values()].every((entry) =>
      coordinateProjectionCommitted(projection, entry),
    );
  }

  const publishedAt = () => runtime.view?.published_at ?? null;
  const saidAt = (el) =>
    closestAcross(el, ".lf-msg")?.querySelector(":scope > .lf-msg-head > time")
      ?.dateTime || publishedAt();

  const watch = (owner, callback) => {
    const update = () => {
      if (!owner.isConnected) {
        document.removeEventListener("lf-actions", update);
        return;
      }
      callback();
    };
    document.addEventListener("lf-actions", update);
    update();
    return () => document.removeEventListener("lf-actions", update);
  };

  const watchActions = (widget, action, callback) =>
    watch(widget, () => callback(actionSequence(widget, action)));
  const watchUpdates = (target, callback) =>
    watch(target instanceof Element ? target : document.body, () => {
      const projection = stateProjection();
      if (reportsCommitted(projection, target)) callback(updateSequence(target));
    });
  // Full history is intentionally raw: it is the one public escape hatch whose contract
  // is the append-only log itself rather than a semantic reading of that log.
  const watchHistory = (owner, callback) =>
    watch(owner, () => callback(runtime.events.map((event) => structuredClone(event))));

  publishedActionSequence = actionSequence;
  publishedPublishedAt = publishedAt;
  publishedSaidAt = saidAt;
  publishedUpdateSequence = updateSequence;
  publishedWatchActions = watchActions;
  publishedWatchHistory = watchHistory;
  publishedWatchUpdates = watchUpdates;

  return {
    actionSequence,
    publishedAt,
    replaceClaimState,
    saidAt,
    updateSequence,
    watchActions,
    watchHistory,
    watchUpdates,
    workClaimState,
  };
}
