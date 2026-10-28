/* Delivery and behavior use one retained screenshot template and root. */
import { render } from "/vendor/lit.js";
import { ShotView } from "../widgets/shot-view.js";
document.documentElement.lfInitial.register("lf-shot", (host, tools) => {
  const view = new ShotView(host, tools);
  // Fitting needs the connected stage and frame labels. Draw their canonical
  // template once to measure; the coordinator draws its resulting geometry.
  render(view.render(), host, { host });
  view.fit();
  return view;
});
