/* The part of the helper surface that loads in any document. A widget importing only
   from here runs on a plain HTML page as well as a Leaf page: the host maps Leaf's
   rooted module paths with an import map of its own, as a Leaf page does
   (`layer_import_map` in revision_delivery.py), and runs none of Leaf's runtime. On a
   Leaf page the same widget gets Leaf's features through what Leaf reads from outside
   it, the standard events `failSoft` and `PendingTaskEvent` dispatch (widget-upgrade.js),
   rather than through calls into Leaf.

   widget-api.js re-exports all of it, so these are the same helpers by either path.
   Each home re-exported here must load, and work, in a document Leaf did not compose:
   it reads nothing at import that Leaf's delivery or prepaint puts in a page.
   tests/smoke/test_plain_page.py holds the portable widgets to that. */
export { whileConnected, frameFor } from "./arrivals.js";
export {
  afterScript,
  cancelRender,
  cancelAnimation,
  nextAnimation,
  nextFrame,
  nextRender,
  sizeObserver,
} from "./rendering.js";
export {
  PendingTaskEvent,
  bodyText,
  dataBody,
  failSoft,
  once,
  placesFailure,
  reportFailure,
} from "./widget-upgrade.js";
export { measure } from "./shown-box.js";
export { inBaseLayer } from "./base-layer.js";
