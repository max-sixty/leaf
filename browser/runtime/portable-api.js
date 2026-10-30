/* The part of the helper surface that loads in any document. A widget importing only
   from here runs on a plain HTML page as well as a Leaf page: the host maps Leaf's
   rooted module paths with an import map of its own, as a Leaf page does
   (`layer_import_map` in revision_delivery.py), and runs none of Leaf's runtime. On a
   Leaf page the same widget gets Leaf's features through what Leaf reads from outside
   it, rather than through calls into Leaf: the events it dispatches (widget-upgrade.js),
   the keys it declares as `lfCommands`, the words it asks a listener to hear
   (`announce`), the inventory of Comment targets it registers (`registerVisualParts`,
   visual-parts.js), and the parts it marks for Leaf to dress, a block's Copy control
   (`data-lf-copy`, code-copy.js) and a quiet word (`data-lf-quiet`, declared-words.js).
   A page without Leaf reads none of them, so there the widget binds no key, says
   nothing aloud, offers no Comment target and shows no Leaf control.

   widget-api.js re-exports all of it, so these are the same helpers by either path.
   Each home re-exported here must load, and work, in a document Leaf did not compose:
   it reads nothing at import that Leaf's delivery or prepaint puts in a page.
   tests/smoke/test_plain_page.py holds the portable widgets to that. */
export {
  html,
  noChange,
  nothing,
  render,
  classMap,
  createRef,
  guard,
  keyed,
  live,
  ref,
  repeat,
  styleMap,
  unsafeHTML,
} from "/vendor/lit.js";
export { whileConnected, frameFor, setScroll } from "./arrivals.js";
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
  LAYOUT,
  PendingTaskEvent,
  announce,
  bodyText,
  commandsChanged,
  dataBody,
  failSoft,
  layoutChanged,
  once,
  placesFailure,
  reportFailure,
} from "./widget-upgrade.js";
export { measure } from "./shown-box.js";
export { registerVisualParts } from "./visual-parts.js";
export { inBaseLayer } from "./base-layer.js";
export { tabStore } from "./tab-store.js";
export { ensureSyntaxLanguage, synNodes, syntax, tokenLines } from "./syntax-tokens.js";
export { actionName } from "./icon-paths.js";
export { onMotionPreferenceChange, reducedMotion } from "./motion.js";
// The time axis the Playwright timeline and lf-timeline both draw on.
export { assignRows, axisTicks, textWidth } from "./time-axis.js";

export { actionClass } from "./control-faces.js";
export { actionTemplate } from "./icons.js";

export {
  offerElement,
  generatedElement,
  offer,
  offerAction,
  offerActionElement,
  selectableOffer,
  offered,
  offeredAction,
  selectableOffered,
  generated,
} from "./element-markers.js";
