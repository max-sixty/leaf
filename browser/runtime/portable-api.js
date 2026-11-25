/* The part of the helper surface that loads in any document. A widget importing only
   from here runs on a plain HTML page as well as a Leaf page: the host maps Leaf's
   rooted module paths with an import map of its own, as a Leaf page does
   (`layer_import_map` in revision_delivery.py), and runs none of Leaf's runtime. On a
   Leaf page the same widget gets Leaf's features through what Leaf reads from outside
   it, rather than through calls into Leaf: the events it dispatches
   (lib/widget-events.js), the keys it declares as `lfCommands`, what pointing at an
   element reads (`lfPreview`, annotations/preview.js, `lf-preview` as that changes, and
   `lf-preview-ended` as the preview goes), the words it asks a listener to hear
   (`lf-announce`), where a step of its own walk landed (`lf-walk`, records/walk-position.js),
   the inventory of Comment targets it states (`data-lf-part` marks or `lfParts`,
   state/visual-parts.js), and the parts it marks for Leaf to dress, a block's Copy control
   (`data-lf-copy`, records/code-copy.js) and a quiet word (`data-lf-quiet`,
   records/declared-words.js).
   A page without Leaf reads none of them, so there the widget binds no key, shows no
   preview, says nothing aloud, offers no Comment target and shows no Leaf control.

   widget-api.js re-exports all of it, so these are the same helpers by either path.
   Each home re-exported here must load, and work, in a document Leaf did not compose:
   it reads nothing at import that Leaf's delivery or prepaint puts in a page.
   tests/smoke/test_plain_page.py holds the portable widgets to that. A portable widget
   also imports the library's modules (lib/), each of which loads in any document. */
export { whileConnected, frameFor } from "./dom/arrivals.js";
export { tabStore } from "./state/tab-store.js";

export { shadowStage } from "./dom/shadow-stage.js";

export { threadSurface } from "./records/thread/surface-handles.js";

export { searchField } from "./dom/control-labels.js";

export { focusDestination, holdFocus, onUserInput } from "./dom/focus.js";
export { retainUserIntent } from "./dom/user-intent.js";
export { scrollIntoView } from "./readings/landing-scroll.js";
export { scrollersOf } from "./readings/scroll-containers.js";
export { move } from "./dom/dom-move.js";
export { setChildLists, setChildren, setRenderedChildren } from "./dom/dom-children.js";
export { langForPath } from "./base/language-paths.js";
