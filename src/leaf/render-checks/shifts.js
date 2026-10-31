/* Native layout-shift evidence during startup and after presentation.
 *
 * Read Chrome's own painted-shift evidence while the gate leaves the page alone,
 * before its viewport sweeps and thread probes. A finite observation cannot certify
 * later timers or gesture paths, and a shifted node is an effect, not necessarily
 * the element whose size changed. Keep this as advice for the author to judge.
 * Unlike the suite's gesture-credit sensor this needs no model of Leaf's inputs.
 */
import { inPage } from "/runtime/check-api.js";
import { at } from "./locate.js";

// Chromium withholds a source inside a shadow tree, or one removed before delivery.
// Its rectangles still prove movement. Hit testing would name whatever occupies the
// box now, which is neither necessarily the moved element nor the cause.
const sourceReading = (source) => ({
  node: source.node ? at(source.node) : "a source node the browser did not expose",
  before: source.before,
  after: source.after,
});

let observation = null;

export function startPassiveLayoutShifts() {
  observation?.stop();
  const moved = new Map();
  const stop = globalThis.__leafRenderDriver.observeLayoutShifts((entries) => {
    for (const entry of entries) {
      for (const source of entry.sources) {
        const node = source.node;
        if (!inPage(node)) continue;
        if (node.closest(".lf-chrome, .lf-ui")) continue;
        // One example per moved node; repeated autoplay ticks need no repeated
        // finding. Anonymous sources remain in startup evidence, not per-node advice.
        if (!moved.has(node)) {
          const reading = sourceReading(source);
          moved.set(node, {
            code: "passive-layout-shift",
            at: reading.node,
            before: reading.before,
            after: reading.after,
          });
        }
      }
    }
  });
  observation = { stop, moved };
}

export function finishPassiveLayoutShifts() {
  const { stop, moved } = observation;
  stop();
  observation = null;
  return [...moved.values()];
}

// Native layout shifts are evidence for the page's author, not a refusal budget.
// CLS uses the platform metric's session windows: gaps below 1s, at most 5s long.
export function startupLayoutShifts() {
  const entries = globalThis.__leafRenderDriver.startupLayoutShifts();
  if (!entries.length) return [];
  let cls = 0,
    score = 0,
    first = -Infinity,
    previous = -Infinity;
  for (const entry of entries) {
    if (entry.startTime - previous >= 1000 || entry.startTime - first >= 5000) {
      first = entry.startTime;
      score = 0;
    }
    score += entry.value;
    cls = Math.max(cls, score);
    previous = entry.startTime;
  }
  return [
    {
      code: "startup-layout-shift",
      cls,
      entries: entries.map((entry) => ({
        at: entry.startTime,
        value: entry.value,
        sources: entry.sources.map(sourceReading),
      })),
    },
  ];
}
