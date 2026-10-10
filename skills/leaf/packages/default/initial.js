/* Package-owned initial drawings paint before modules; live modules adopt the
 * same nodes, retaining tab-local reading and stable sample allocations. */
import { initialActivity } from "./widgets/activity-view.js";
import { initialSample } from "./widgets/sample-view.js";
document.documentElement.lfInitial.register("lf-activity", initialActivity);
document.documentElement.lfInitial.register("lf-sample", initialSample);
