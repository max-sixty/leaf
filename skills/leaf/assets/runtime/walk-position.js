/* The transient position of a category walk. `a`/`A` and `t`/`T` already own where
   they move; this owner says where that destination stands in the list the same next
   press will use. It stores only the walk and its stable destination, then derives the
   ordinal on every standing paint so an answered Ask, a resolved thread, or a narrowed
   panel cannot leave a stale denominator behind. Reaching the same destination twice
   means the clamped walk met its boundary; that state briefly gives the unchanged
   ordinal an accent face. The existing live region announces each key arrival once. */
import { openAsks } from "./asks/model.js";
import { standingIn } from "./asks/view.js";
import { panelIsOpen } from "./chrome-layout.js";
import { openThreads } from "./conversation/reconcile.js";
import { narrowed } from "./conversation/narrowing.js";
import { activeInlineThread } from "./living-margin.js";
import { focused, paintHere } from "./keyboard/scopes.js";
import { closestAcross } from "./passages.js";

const BOUNDARY_MS = 900;

let walking = null; // {kind, targetId, boundary}; never a snapshot of the list it walks
let boundaryTimer = 0;

export function walkPositionLabel(kind, position, total, qualifier = "") {
  const noun = kind === "ask" ? "Ask" : kind === "thread" ? "Thread" : null;
  if (!noun) throw new Error(`leaf: unknown walk position kind ${kind}`);
  return `${noun} ${position} of ${total}${qualifier ? ` ${qualifier}` : ""}`;
}

function threadStanding() {
  if (!panelIsOpen()) return activeInlineThread()?.dataset.thread ?? null;
  return closestAcross(focused(), ".lf-thread[data-id]")?.dataset.id ?? null;
}

export function walkPosition() {
  if (!walking) return null;
  const { kind, targetId } = walking;
  const items =
    kind === "ask" ? openAsks() : openThreads({ visibleOnly: panelIsOpen() });
  const current = kind === "ask" ? (standingIn()?.id ?? null) : threadStanding();
  const index = items.findIndex((item) =>
    kind === "ask" ? item.id === targetId : item.dataset.id === targetId,
  );
  if (current !== targetId || index < 0) {
    clearTimeout(boundaryTimer);
    boundaryTimer = 0;
    walking = null;
    return null;
  }
  const qualifier =
    kind === "ask" ? "open" : panelIsOpen() && narrowed() ? "shown" : "";
  return {
    boundary: walking.boundary,
    kind,
    text: walkPositionLabel(kind, index + 1, items.length, qualifier),
  };
}

// A key walk has arrived. The caller still owns and announces the motion; this records
// only enough identity for the next standing paint to derive the status-line reading.
export function beginWalk(kind, targetId) {
  if (!targetId) throw new Error("leaf: a walk position needs a destination id");
  // Validate the kind now rather than letting the first later paint reinterpret it.
  walkPositionLabel(kind, 1, 1);
  const boundary = walking?.kind === kind && walking.targetId === targetId;
  clearTimeout(boundaryTimer);
  const arrived = { boundary, kind, targetId };
  walking = arrived;
  boundaryTimer = boundary
    ? setTimeout(() => {
        if (walking !== arrived) return;
        arrived.boundary = false;
        boundaryTimer = 0;
        paintHere();
      }, BOUNDARY_MS)
    : 0;
  const position = walkPosition();
  paintHere();
  return position?.text ?? null;
}
