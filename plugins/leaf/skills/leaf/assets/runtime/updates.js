/* Canonical action, work-claim, and report feeds exposed to widgets and chrome. */
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
    inChrome,
    projectionCommitted,
    stateProjection,
    threadList,
  } = dependencies;

  // Replace-in-place work claims, already normalized by the server out of status.json's
  // private store. Reports join them in updateSequence below. Keeping only source records
  // here means target and lifecycle are derived in one projection for every consumer.
  let claimUpdateSources = [];

  // The fold answers where reader state stands; this answers how it got there. A widget
  // receives its own absolute actions in log order, bounded by the version being viewed.
  // A reply widget lives in frozen chrome and therefore sees the whole sequence. Returning
  // fresh copies keeps the private event store private.
  function sequence(widget, verb, live) {
    return runtime.events
      .filter(
        (event) =>
          event.kind === "action" &&
          event.widget === widget.id &&
          (!verb || event.action === verb) &&
          (inChrome(widget) || event.revision <= runtime.currentRevision) &&
          live(event),
      )
      .map((event) => structuredClone(event));
  }

  const actionSequence = (widget, action) => {
    const projection = stateProjection(runtime.currentRevision);
    return sequence(widget, action, (e) => projectionCommitted(projection, e));
  };

  // Thread and widget ids may have the same spelling, so every target names its kind.
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
  const updateTargetKey = (target) =>
    target ? JSON.stringify([target.kind, target.id]) : null;
  const compareText = (left, right) => (left < right ? -1 : left > right ? 1 : 0);
  // A claim follows its log floor and precedes the next event.
  const updatePosition = (update) =>
    update.source === "report" ? [update.seq, 0] : [update.log_floor, 1];

  // Normalize both sources after stateProjection has classified the durable channel.
  function updatesFromProjection(target, projection) {
    const key = updateTargetKey(updateTarget(target));
    const reportStanding = new Set(
      [...projection.reports.values()].flat().map((entry) => entry.e.id),
    );
    const reportEffective = new Set(
      [...projection.desired.values()]
        .filter((entry) => entry.e.kind === "report")
        .map((entry) => entry.e.id),
    );
    const updates = [];
    for (const entry of projection.classified.values()) {
      const event = entry.e;
      if (event.kind !== "report" || entry.terminal) continue;
      const entryTarget = { kind: "widget", id: event.widget };
      if (key !== null && updateTargetKey(entryTarget) !== key) continue;
      const field = entry.spec.update;
      updates.push({
        id: event.id,
        target: entryTarget,
        source: "report",
        action: event.action,
        detail: event.detail,
        text: field ? event.detail[field] : null,
        ts: event.ts,
        revision: event.revision,
        seq: event.seq,
        agent: event.agent ?? null,
        session: event.session ?? null,
        disposition: reportEffective.has(event.id)
          ? "effective"
          : reportStanding.has(event.id)
            ? "standing"
            : "settled",
      });
    }
    const threads = new Map(threadList().map((thread) => [thread.root.id, thread]));
    for (const source of claimUpdateSources) {
      if (key !== null && updateTargetKey(source.target) !== key) continue;
      let effective = false;
      if (source.target.kind === "thread") {
        const thread = threads.get(source.target.id);
        effective = Boolean(
          thread &&
          !thread.resolved &&
          !thread.msgs.some(
            (message) =>
              message.kind === "reply" &&
              message.author === "claude" &&
              message.seq > source.log_floor,
          ),
        );
      } else if (source.target.kind === "widget") {
        effective = !runtime.events.some(
          (event) =>
            event.kind === "note" &&
            event.seq > source.log_floor &&
            (event.settles ?? []).some(
              (settlement) =>
                settlement.kind === "work" && settlement.id === source.target.id,
            ),
        );
      }
      updates.push({
        ...source,
        disposition: effective ? "effective" : "settled",
      });
    }
    return updates
      .sort((left, right) => {
        const leftPosition = updatePosition(left);
        const rightPosition = updatePosition(right);
        return (
          leftPosition[0] - rightPosition[0] ||
          leftPosition[1] - rightPosition[1] ||
          Date.parse(left.ts) - Date.parse(right.ts) ||
          compareText(left.source, right.source) ||
          compareText(updateTargetKey(left.target), updateTargetKey(right.target)) ||
          compareText(left.id, right.id)
        );
      })
      .map((update) => structuredClone(update));
  }

  const updateSequence = (target = null) =>
    updatesFromProjection(target, stateProjection(runtime.currentRevision));

  // Do not narrate a report while its coordinate still paints the prior winner.
  function reportUpdatesCommitted(projection, target) {
    const key = updateTargetKey(updateTarget(target));
    const coordinates = new Map();
    for (const entry of projection.classified.values()) {
      if (entry.terminal || entry.e.kind !== "report") continue;
      const entryKey = updateTargetKey({ kind: "widget", id: entry.e.widget });
      if (key === null || key === entryKey) coordinates.set(entry.coordinate, entry);
    }
    return [...coordinates.values()].every((entry) =>
      coordinateProjectionCommitted(projection, entry),
    );
  }

  // When the revision being read became active, or when its public stamp landed — the
  // floor under any statement about how fresh what the page says is. A row nobody has
  // reported on is not a row of unknown age: its words are exactly this old.
  //
  // Without the floor, silence renders as nothing at all, which is the one direction a
  // freshness line must never fail in. A fleet whose workers all died at six in the
  // evening, on a page updated at six, shows five rows claiming work and no elapsed
  // line anywhere at eight the next morning — a dead fleet reading healthy, which is the
  // claim-nobody-revises failure the banner's own judgment exists to answer, reintroduced
  // one section below the banner.
  const publishedAt = () => {
    let ts =
      runtime.active?.revision === runtime.currentRevision
        ? runtime.active.activated_at
        : null;
    for (const e of runtime.events)
      if (e.kind === "note" && e.revision === runtime.currentRevision) ts = e.ts;
    return ts;
  };

  // When the words around an element were said. A page's own content was said when its
  // revision became active; a widget an agent put in a message was said when the message
  // was, which is a later moment and often a much later one. Anything measuring "how long
  // since we heard anything" has to take the second where it stands in one, or a roster
  // carried in a reply certifies its workers against an activation from before the reply
  // existed — the freshness line answering for a page nobody was asking about.
  const saidAt = (el) =>
    closestAcross(el, ".lf-msg")?.querySelector(":scope > .lf-msg-head > time")
      ?.dateTime || publishedAt();

  // Run immediately and after every reconciliation, including polls with no new events.
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
      const projection = stateProjection(runtime.currentRevision);
      if (!reportUpdatesCommitted(projection, target)) return;
      callback(updatesFromProjection(target, projection));
    });

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
    claimUpdateSources: () => claimUpdateSources,
    publishedAt,
    saidAt,
    setClaimUpdateSources: (sources) => (claimUpdateSources = sources),
    updateSequence,
    watchActions,
    watchHistory,
    watchUpdates,
  };
}
