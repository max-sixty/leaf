/* Draw the transport before first paint; upgrade adopts these exact nodes. */
import { drawMotion } from "../widgets/motion-view.js";
document.documentElement.lfInitial.register("lf-motion", drawMotion);
