/* Native layout-shift evidence after presentation.
 *
 * Read Chrome's own painted-shift evidence while the gate leaves the presented page
 * alone, before its viewport sweeps and thread probes. A finite observation cannot
 * certify later timers or gesture paths, and a shifted node is an effect, not
 * necessarily the element whose size changed. Keep this as advice for the author to
 * judge. Unlike the suite's gesture-credit sensor this needs no model of Leaf's inputs.
 *
 * The check reads no shifts before presentation. A box that changes size as the page
 * loads, such as an image without width and height or a widget drawing, moves painted
 * content only where a frame came first, which differs between identical loads, and
 * many such boxes are Leaf's own widgets. A widget whose drawing differs from the
 * height it stated gets `drawn-height` advice, read from its boxes rather than from
 * paint timing.
 */
import { inPage } from "/runtime/check-api.js";
import { at } from "./locate.js";

/** @param {DOMRectReadOnly} rectangle */
const rect = ({ x, y, width, height }) => ({ x, y, width, height });

/** @typedef {{code: string, at: string, before: ReturnType<typeof rect>, after: ReturnType<typeof rect>}} PassiveShift */

// Each moved node is read as its entry is delivered, since it may leave the document
// before the observation ends. Chromium withholds a source inside a shadow tree, or
// one removed before delivery; hit testing would name whatever occupies its box now,
// which is neither necessarily the moved element nor the cause, so it is left out.
export function passiveLayoutShifts() {
  /** @type {Map<Element, PassiveShift>} */
  const moved = new Map();
  /** @param {PerformanceEntryList} entries */
  const read = (entries) => {
    for (const entry of /** @type {import("../../../browser/types/render-checks.js").NativeLayoutShift[]} */ (
      entries
    )) {
      if (entry.hadRecentInput) continue;
      for (const source of entry.sources) {
        const node =
          source.node instanceof Element
            ? source.node
            : (source.node?.parentElement ?? null);
        if (!node || !inPage(node)) continue;
        if (node.closest(".lf-chrome, .lf-ui")) continue;
        // One example per moved node; repeated autoplay ticks need no repeated
        // finding.
        if (!moved.has(node))
          moved.set(node, {
            code: "passive-layout-shift",
            at: at(node),
            before: rect(source.previousRect),
            after: rect(source.currentRect),
          });
      }
    }
  };
  const observer = new PerformanceObserver((list) => read(list.getEntries()));
  if (PerformanceObserver.supportedEntryTypes.includes("layout-shift"))
    observer.observe({ type: "layout-shift" });
  return () => {
    read(observer.takeRecords());
    observer.disconnect();
    return [...moved.values()];
  };
}
