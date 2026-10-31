/* Passive layout shifts after the page's first presentation.
 *
 * Read Chrome's own painted-shift evidence while the gate leaves the page alone,
 * before its viewport sweeps and thread probes. A finite observation cannot certify
 * later timers or gesture paths, and a shifted node is an effect, not necessarily
 * the element whose size changed. Keep this as advice for the author to judge.
 * Unlike the suite's gesture-credit sensor this needs no model of Leaf's inputs.
 */
import { at } from "./locate.js";

let observation = null;

export function startPassiveLayoutShifts() {
  observation?.observer.disconnect();
  const started = performance.now();
  const moved = new Map();
  const rect = ({ x, y, width, height }) => ({ x, y, width, height });
  const collect = (entries) => {
    for (const entry of entries) {
      if (entry.startTime < started || entry.hadRecentInput) continue;
      for (const source of entry.sources) {
        const node = source.node;
        const element = node instanceof Element ? node : node?.parentElement;
        if (!element?.closest("body > main")) continue;
        if (element.closest(".lf-chrome, .lf-ui")) continue;
        // One example per moved node; repeated autoplay ticks need no repeated
        // finding. The native rectangles retain the evidence at that paint.
        if (!moved.has(node)) {
          moved.set(node, {
            code: "passive-layout-shift",
            at: at(element),
            before: rect(source.previousRect),
            after: rect(source.currentRect),
          });
        }
      }
    }
  };
  const observer = new PerformanceObserver((list) => collect(list.getEntries()));
  observer.observe({ type: "layout-shift" });
  observation = { observer, collect, moved };
}

export function finishPassiveLayoutShifts() {
  const { observer, collect, moved } = observation;
  collect(observer.takeRecords());
  observer.disconnect();
  observation = null;
  return [...moved.values()];
}
