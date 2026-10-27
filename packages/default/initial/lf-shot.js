/* Delivery reserves the real screenshot inspection drawing before behavior loads.
 * The view draws its symbols from the layer's icon table, which only this build-time
 * entry can import: shot-view.js also loads at run time beside the widget. */
import { iconMarkup } from "../../../browser/runtime/icon-paths.js";
import { ShotView } from "../widgets/shot-view.js";
document.documentElement.lfInitial.register(
  "lf-shot",
  (host, tools) => new ShotView(host, { ...tools, iconMarkup }),
);
