/* Whether the annotation layer shows.

   The annotation layer is everything Leaf draws over the page's content: the margin rows
   standing as pins, whatever they hold, the durable marks on commented and reacted
   passages with their element contours, an open card, and an unfolded cluster. The rail
   covers nothing, so it and everything standing in it stay. Hiding the layer changes no
   geometry, since nothing in it takes up room; it lets the user see what lies under it.

   The fact is this tab's view of the page, so it lives in the tab store and comes back
   with a reload, and a new page opens with the layer shown: a standing "never show
   markers" would hide every arrival on every page.

   `setAnnotationsHidden` is the one writer. It states the fact on the root for the
   stylesheets (theme.css, marks.css, chrome.css), keeps it for the tab, and tells each
   watcher, so the margin can take focus and its card off what it hides. Readers ask
   `annotationsHidden()` rather than the root attribute, which is a rendering. */
import { tabStore } from "./storage.js";
import { setRuntimeRootAttribute } from "./root-state.js";

export const ANNOTATIONS_KEY = "lf-annotations";

let hidden = false;
const watchers = new Set();

export const annotationsHidden = () => hidden;

export function watchAnnotations(watcher) {
  watchers.add(watcher);
}

export function setAnnotationsHidden(on) {
  if (on === hidden) return;
  hidden = on;
  setRuntimeRootAttribute(
    document.documentElement,
    "data-lf-annotations",
    on ? "hidden" : "shown",
  );
  tabStore.set(ANNOTATIONS_KEY, on ? "hidden" : null);
  for (const watcher of watchers) watcher(on);
}
