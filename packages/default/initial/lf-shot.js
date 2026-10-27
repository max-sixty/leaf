/* Delivery reserves the real screenshot inspection drawing before behavior loads. */
import { ShotView } from "../widgets/shot-view.js";
document.documentElement.lfInitial.register(
  "lf-shot",
  (host, tools) => new ShotView(host, tools),
);
