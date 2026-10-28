/* Current document targets for conversations and mechanical composition.

   Each read resolves durable anchors and pointed rows before selected presentation:
   initial admission and the final cohort move share this directory. Surface admission,
   inventory, current location and travel consume it;
   decoration consumes its resolved targets and never supplies their existence. These
   nodes and records are mechanical readings, outside the application snapshot.

   An anchor on an element an agent sent in a message, which the page itself doesn't
   hold, stands in that message, and its placement names it (`message`). While no reader
   draws the message, that is all it has (`resolvedInMessage`); while the floating panel
   draws it in its view of the message's thread, it keeps the element's reading too, so
   the element is marked there. `placedAt` tracks changes to resolved placements for
   views that read them while drawing; a source replacement can change a quote's
   status without changing its thread. */
import { anchoringIsReady, resolveAnchor } from "./anchor-resolution.js";
import { resolvedInMessage, targetElement } from "./resolved-target.js";
import { inChrome } from "./passages.js";
import { placePoints } from "./pointed-place.js";
import { threadKey, threadNames } from "./thread/model.js";
import { messageHolding } from "./thread/messages.js";
import { signal } from "/runtime/framework.js";
import { tick } from "./version-signal.js";

const samePlacement = (a, b) =>
  a?.kind === b?.kind &&
  a?.status === b?.status &&
  a?.exact === b?.exact &&
  a?.datumElement === b?.datumElement &&
  a?.element === b?.element &&
  a?.place === b?.place &&
  a?.surface === b?.surface &&
  a?.message === b?.message &&
  a?.point === b?.point &&
  a?.pointRow === b?.pointRow &&
  a?.pointWords === b?.pointWords;

// The message of these threads that keeps the element an anchor names, if any. An anchor
// captured detached names no passage the user selected, so finding its element's message
// identifies nothing and it stays detached.
function heldIn(anchor, threads) {
  const held =
    anchor.section && !anchor.detached ? messageHolding(anchor.section) : null;
  return held &&
    threads.some((thread) => thread.msgs.some(({ id }) => id === held.message))
    ? held
    : null;
}

export function createAnchorPlacement() {
  const placed = new Map();
  const version = signal(0);
  let pendingPlaced = null;
  let names = new Map();

  function read({ threads, draft, actionAnchor }) {
    if (!anchoringIsReady()) return null;
    const before = new Map(placed);
    placed.clear();
    // Names for the threads this read placed, so `placedAt` answers from the same
    // reading as `placed` until the next read, not from a later publication.
    names = threadNames(threads);
    const readings = [];
    const pointable = [];
    for (const thread of threads) {
      if (!thread.anchor) continue;
      const found = resolveAnchor(thread.anchor);
      const held =
        found && !inChrome(found.place) ? null : heldIn(thread.anchor, threads);
      const resolved = !held
        ? found
        : found
          ? Object.assign(found, { message: held.message })
          : resolvedInMessage(held);
      if (!resolved) continue;
      const target = targetElement(resolved) ?? resolved.place;
      const placement = Object.assign(resolved, {
        point: null,
        pointRow: null,
        pointWords: null,
      });
      placed.set(thread.id, placement);
      readings.push({ thread, placement });
      if (!thread.resolved && !thread.anchor.quote && !thread.anchor.visual && target)
        pointable.push({ id: thread.id, key: threadKey(thread), target });
    }
    const pointed = placePoints(pointable, new Set(threads.map(threadKey)));
    for (const { id, key } of pointable) {
      const point = pointed.get(key);
      if (point)
        Object.assign(placed.get(id), {
          point: point.element,
          pointRow: point.row,
          pointWords: point.words,
        });
    }
    const resolvedDraft =
      draft.open && draft.anchor ? resolveAnchor(draft.anchor) : null;
    pendingPlaced = resolvedDraft;
    const active = draft.open ? null : actionAnchor;
    const action = active && !active.quote ? resolveAnchor(active) : null;
    if (
      before.size !== placed.size ||
      [...placed].some(([id, placement]) => !samePlacement(before.get(id), placement))
    )
      tick(version);
    return { readings, draft: { ...draft, resolved: resolvedDraft }, action };
  }
  return Object.freeze({
    read,
    placedAt: (id) => {
      version.value;
      return placed.get(names.get(id)?.id ?? id);
    },
    pendingAt: () => pendingPlaced,
  });
}
