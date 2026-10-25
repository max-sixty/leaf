/* Draw the whole timeline before first paint; upgrade adopts these exact nodes. */
import { drawTimeline } from "./timeline-view.js";
document.documentElement.lfInitial.register("lf-timeline", drawTimeline);
