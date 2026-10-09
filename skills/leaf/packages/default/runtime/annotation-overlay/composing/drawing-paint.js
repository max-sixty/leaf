/* Saved drawing annotations selected from the canonical Thread/target reading.
 *
 * This optional producer supplies generic ink descriptions. It owns no SVG nodes,
 * geometry, cache or scheduled work; native drawing-ink renders its records beside
 * active/draft ink. Page-owned annotation presentation omits this producer entirely.
 */
import { exactTarget } from "/runtime/resolved-target.js";

export function postedDrawings(threads, anchors) {
  const drawings = [];
  for (const thread of threads) {
    if (thread.resolved || !thread.root.drawing) continue;
    const place = anchors.placedAt(thread.id);
    const target = exactTarget(place);
    if (!target) continue;
    drawings.push({
      drawing: thread.root.drawing,
      target,
      className: "lf-drawing-posted",
      id: thread.id,
    });
  }
  return drawings;
}
