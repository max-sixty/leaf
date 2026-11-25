/* The one helper surface behavior modules import. Capabilities come from their
   domain owners; optional hosts load when requested. Owners import one another,
   and leaf.js only boots.

   The runtime tree is not the set of importers: package widget modules reach this file
   over HTTP from the served page, as `/runtime/widget-api.js`. What only the render
   gate's probes read belongs in check-api.js instead.

   Every export is supported for independent and bundled packages alike; the
   references/module-*.md files document each one. Kernel widgets import private
   capabilities from their owners rather than lending them through this surface.

   The helpers that load in any document are portable-api.js's, re-exported here whole,
   so a widget that must also run off a Leaf page imports from there and every other
   widget keeps importing from here.

   Shared web code that reaches none of Leaf's is no part of this surface: it is the
   library's (lib/; browser/AGENTS.md, "The library of shared web code").

   Each export is a name every package author learns, so one joins this file only
   after the questions in packages/AGENTS.md, "A widget's need of Leaf". */
import "./element-integration.js";
import { deferredArrival } from "./presentation.js";
import { growthIsSeen } from "./geometry.js";
import { PendingTaskEvent } from "./lib/pending-task.js";
import { threadsReading } from "./readings.js";
import { threadActions } from "./application.js";
export * from "./portable-api.js";

// `nameOf(thing)`: the name Leaf gives an element, the page, a thread or an On list
// row, in words.
export { nameOf } from "./names.js";
// The page readings, each a value to `read()` and a `change` to hear: the obligations,
// or those a region holds, the On lists, the threads, which it also writes, and the
// page's history (readings.js).
export { history, obligations, queues } from "./readings.js";
export const threads = Object.assign(threadsReading, threadActions);
export { comparisonChanges } from "./version.js";
export { go, placePageThreads, registerThreadPresentation } from "./application.js";
export { registerContribution } from "./contributions.js";
export { pageLinks } from "./page-markdown.js";
export { scopedMediaUrl } from "./media.js";
export { named, says } from "./passages.js";
export { boundFile } from "./file-api.js";
export { generate } from "./llm-api.js";
export { connection } from "./http-api.js";
export { draft } from "./drafts.js";
export { layerFact } from "./registry.js";
export { backgroundFlash, motion } from "./motion.js";
// `whenNear` waits for the reader to near a node and declares the wait as an arrival,
// so a widget cannot defer without the page knowing.
export { whenNear } from "./presentation.js";
export { aimedAt } from "./widget-elements.js";

// Render a declared template or a generated document as an isolated live Leaf page,
// which only Leaf's server can allocate (SOUL.md, "Make the work concrete and
// playable"). The returned host owns readiness, the frame's height, Reset and disposal
// (live-samples.md). A block's frame the reader sees as it mounts is drawing under way
// (lib/pending-task.js), read here in the caller's stack: the page's presentation
// waits for it, or the gesture whose rendering showed the frame owns its fit. The host
// says when that drawing is in (sample.js, `landed`).
/** @param {Parameters<typeof import("./sample.js").mountSample>[0]} frame
 * @param {Parameters<typeof import("./sample.js").mountSample>[1]} options
 * @returns {Promise<ReturnType<typeof import("./sample.js").mountSample>>} */
export async function mountSample(frame, options) {
  /** @type {PromiseWithResolvers<void> | null} */
  const landing =
    !options.window && growthIsSeen(frame) ? Promise.withResolvers() : null;
  if (landing) frame.dispatchEvent(new PendingTaskEvent(landing.promise));
  try {
    // The page counts the sample's arrival from here; the host counts it once it starts.
    const owner = await deferredArrival(import("./sample.js"));
    return owner.mountSample(frame, options, landing && landing.resolve);
  } catch (error) {
    landing?.resolve();
    throw error;
  }
}
export { wear } from "./dress.js";
