/* Activity owns one Solid drawing; the live module calls its retained paint closure
 * so the initial template and its keyed rows survive upgrade unchanged. */
import { initialActivity } from "../widgets/activity-view.js";
document.documentElement.lfInitial.register("lf-activity", initialActivity);
