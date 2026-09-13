/* Canonical action and update feeds exposed to widgets and chrome.

   Projection answers where state stands. Some modules also need to narrate how the state
   arrived or when it was last reported. They read that through the exported sequence
   helpers, not through raw `events`.

   `updateSequence(target)` is the one reading of news about an item. Its target is
   either a widget element or an explicit `{kind, id}` pair; a bare id is not an identity
   and is rejected because a thread and a widget may spell theirs alike. With no target
   it returns the whole ordered feed. Reports from the append-only log and ephemeral
   thread work claims from status storage share a common envelope: `id`, typed `target`,
   `source`, `action`, structured `detail`, declared human-readable `text`, `ts`,
   attribution, and `disposition`. Report envelopes also retain their version and
   sequence; a claim carries `log_floor`, the log sequence it followed.

   The source discriminator is semantic, not an implementation leak. A report stands
   until a stamped revision's note absorbs or overrules it; a claim stands until the
   thread receives an agent reply after that sequence or is resolved. The closed
   disposition is `effective` when an update contributes to current state on its semantic
   coordinate, `standing` when it still needs source-specific settlement but is presently
   outranked, and `settled` when that authority answers it. An older unabsorbed report
   can therefore be standing, and a reader action can mask a report that a version still
   owes an answer. Settled entries remain in the feed when their source retains history.
   A module showing freshness therefore still sees when the log last heard from a worker
   after a stamp absorbs the worker's report.

   An x-report verb may name one required non-empty string detail field with `update`.
   That is the envelope's `text`; consumers never infer prose from a field, verb, or
   widget name. Claims use their required detail as `detail.text` and `text`. The state
   boundary performs this normalization once, before downstream code sees private status
   storage.

   `updateSequence` filters the server-normalized update feed. `watchUpdates` and
   `watchAsks` subscribe their public semantic readings to the application publisher
   and invoke the callback immediately. The same rendering function
   therefore handles a module connected before the first state and one constructed by a
   later thread reconcile.

   Accepted and local attempts publish one complete snapshot, including reads whose
   event list did not grow and definitive refusals that restore authoritative truth.
   Time-dependent paints are separate:
   `presence.js` records synchronous `ago` and `clockValue` readings inside a `clocked`
   callback. The shared tick reruns only callbacks whose reading changed and drops
   disconnected owners. Subscription callbacks use this same mechanism, so a new widget
   owes no entry in a kernel list of clock consumers. A held state does not reset the
   measured server clock offset. Callbacks must render from the sequence they receive and
   return their cleanup function from `watchUpdates` when their element
   disconnects.

   `active.revision` identifies the immutable document currently shown; `active.version`
   is its public stamp when it has one, otherwise null, and `active.label` is `vN`,
   `Draft after vN`, or `Draft`. The timestamp of the latest note for that revision is
   the freshness floor for authored state when no report exists. A page that reports no
   worker update is not timeless; its authored assertion is as old as its revision.

   createProjectionUpdates binds semantic subscriptions to one presentation owner's
   commit proof. Raw update, claim, and history readings do not depend on that proof and
   remain direct exports. */
import { watchProjection } from "./projection-watch.js";
import { currentProjection } from "./projection/state.js";

import { runtime } from "./context.js";
import { closestAcross } from "./passages.js";

// The canonical receipt supplies one reader-facing workflow stage. Transport evidence
// remains in `phase`; consumers use this projection instead of independently deciding
// whether the move is sent, waiting, queued, picked up, working, or awaiting continuation.
export function agentWorkflowStage(receipt) {
  if (!receipt) return null;
  if (receipt.phase === "active")
    return receipt.quiet || receipt.dropped ? "was_working" : "working";
  if (receipt.phase === "picked_up")
    return receipt.dropped ? "picked_up_ended" : "picked_up";
  if (receipt.phase === "queued") return "queued";
  if (receipt.phase === "waiting") return "waiting";
  return "sent";
}

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
export const updateSequence = (target = null) => {
  const key = targetKey(updateTarget(target));
  return (runtime.view?.updates ?? [])
    .filter((update) => key === null || targetKey(update.target) === key)
    .map((update) => structuredClone(update));
};

const publishedAt = () => runtime.view?.published_at ?? null;
export const saidAt = (el) =>
  closestAcross(el, ".lf-msg")?.querySelector(":scope > .lf-msg-head > time")
    ?.dateTime || publishedAt();

// Full history is intentionally raw: it is the one public escape hatch whose contract
// is the append-only log itself rather than a semantic reading of that log.
export const watchHistory = (owner, callback) =>
  watchProjection(owner, () =>
    callback(runtime.events.map((event) => structuredClone(event))),
  );

export function createProjectionUpdates({ coordinateProjectionCommitted }) {
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
  const watchUpdates = (target, callback) =>
    watchProjection(target instanceof Element ? target : document.body, () => {
      const projection = currentProjection();
      if (reportsCommitted(projection, target)) callback(updateSequence(target));
    });
  return { watchUpdates };
}
