/* Delivery reserves the real screenshot inspection drawing before behavior loads. */
import { drawShot } from "../widgets/shot-view.js";
document.documentElement.lfInitial.register("lf-shot", drawShot);
