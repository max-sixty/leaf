/* Activity owns its initial drawing; the live module adopts the same nodes and
 * retains tab-local reading through executable replacement. */
import { initialActivity } from "./widgets/activity-view.js";
document.documentElement.lfInitial.register("lf-activity", initialActivity);
