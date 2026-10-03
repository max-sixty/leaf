/* Saved drawing annotations selected from the canonical Thread/target reading.
 *
 * This optional producer supplies generic ink descriptions. It owns no SVG nodes,
 * geometry, cache or scheduled work; native drawing-ink renders its records beside
 * active/draft ink. Page-owned annotation presentation omits this producer entirely.
 */
import { targetElement, targetPlace } from "/runtime/resolved-target.js";

export function postedDrawings(threads, anchors) {
  const drawings = [];
  for (const thread of threads) {
    if (thread.resolved || !thread.root.drawing) continue;
    const place = thread.root.anchor ? anchors.placedAt(thread.id) : null;
    if (thread.root.anchor && (!place || place.status === "outdated")) continue;
    drawings.push({
      drawing: thread.root.drawing,
      target: targetElement(place) ?? targetPlace(place),
      className: "lf-drawing-posted",
      id: thread.id,
    });
  }
  return drawings;
}
