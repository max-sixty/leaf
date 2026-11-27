/* Leaf's focus accounting around the portable DOM mover. Install before any runtime
   render; off Leaf the browser owns focus and native state-preserving moves. */
import { installMoveFocus } from "./dom-move.js";
import { holdFocus, watchCurrentLocationIn } from "./focus.js";

installMoveFocus({ hold: holdFocus, watch: watchCurrentLocationIn });
