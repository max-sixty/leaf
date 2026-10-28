/* Delivery and behavior use one retained screenshot template and root. The build
 * entry supplies the icon table because shot-view.js also loads at run time. */
import { render } from "/vendor/lit.js";
import { iconMarkup } from "../../../browser/runtime/icon-paths.js";
import { ShotView } from "../widgets/shot-view.js";
document.documentElement.lfInitial.register("lf-shot", (host, tools) => {
  const view = new ShotView(host, { ...tools, iconMarkup });
  // Fitting needs the connected stage and frame labels. Draw their canonical
  // template once to measure; the coordinator draws its resulting geometry.
  render(view.render(), host, { host });
  view.fit();
  return view;
});
