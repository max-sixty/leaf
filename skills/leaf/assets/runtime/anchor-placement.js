/* Current document targets for conversations and mechanical composition.

   Each read resolves durable anchors and pointed rows before selected presentation:
   initial admission and the final cohort move share this directory. Surface admission,
   inventory, standing and travel consume it;
   decoration consumes its resolved targets and never supplies their existence. These
   nodes and records are mechanical readings, outside the application snapshot. */
import { anchoringIsReady, resolveAnchor } from "./anchor-resolution.js";
import { pageText } from "./passages.js";
import { targetElement } from "./resolved-target.js";
import { placePoints } from "./pointed-place.js";
import { threadKey, threadNames } from "./thread/model.js";

export function createAnchorPlacement() {
  const placed = new Map();
  let pendingPlaced = null;
  let names = new Map();

  function read({ threads, draft, actionAnchor }) {
    if (!anchoringIsReady()) return null;
    placed.clear();
    names = threadNames(threads);
    const text = pageText();
    const readings = [];
    const pointable = [];
    for (const thread of threads) {
      if (!thread.anchor) continue;
      const resolved = resolveAnchor(thread.anchor, text);
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
    const pointed = placePoints(pointable, new Set(threads.map(threadKey)), text);
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
      draft.open && draft.anchor ? resolveAnchor(draft.anchor, text) : null;
    pendingPlaced = resolvedDraft;
    const active = draft.open ? null : actionAnchor;
    const action = active && !active.quote ? resolveAnchor(active, text) : null;
    return { readings, draft: { ...draft, resolved: resolvedDraft }, action };
  }
  return Object.freeze({
    read,
    placedAt: (id) => placed.get(names.get(id)?.id ?? id),
    pendingAt: () => pendingPlaced,
  });
}
