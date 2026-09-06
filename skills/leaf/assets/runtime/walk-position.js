/* The transient position of a category walk. `a`/`A` and `t`/`T` already own where
   they move; this owner says where that destination stands in the list the same next
   press will use. It stores only the walk and its stable destination, then derives the
   ordinal on every standing paint so an answered Ask, a resolved thread, or a narrowed
   panel cannot leave a stale denominator behind. The keyline owns its visual rendering;
   the existing live region announces each key arrival once. */
import { openAsks } from "./asks/model.js";
import { standingIn } from "./asks/view.js";
import { panelIsOpen } from "./chrome-layout.js";
import { openThreads } from "./conversation/reconcile.js";
import { narrowed } from "./conversation/narrowing.js";
import { activeInlineThread } from "./living-margin.js";
import { focused, paintHere } from "./keyboard/scopes.js";
import { closestAcross } from "./passages.js";

let walking = null; // {kind, targetId}; never a snapshot of the list it walks

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
    walking = null;
    return null;
  }
  const qualifier =
    kind === "ask" ? "open" : panelIsOpen() && narrowed() ? "shown" : "";
  return {
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
  walking = { kind, targetId };
  const arrived = walkPosition();
  paintHere();
  return arrived?.text ?? null;
}
