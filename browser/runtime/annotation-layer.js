/* Whether the annotation layer shows.

   The annotation layer is everything drawn over the page's content for its
   annotations. Under Leaf's own margin that is the margin rows shown as pins, whatever
   they hold, the durable marks on commented and reacted passages, an open card, and an
   unfolded cluster. The rail covers nothing, so it and everything standing in it stay.
   A package that draws over the page's content joins the layer by watching it
   (`watchAnnotationLayer`), as a page presenting its own annotations does
   (`data-annotations="page"`). Hiding the layer changes no geometry, since nothing in
   it takes up room; it lets the user see what lies under it.

   The fact is this tab's view of the page, so it lives in the tab store and comes back
   with a reload, and a new page opens with the layer shown: a lasting "never show
   markers" would hide every arrival on every page.

   `setAnnotationsHidden` is the one writer. It states the fact on the root for the
   stylesheets, keeps it for the tab, and tells each watcher, so the margin can take
   focus and its card off what it hides and the passage paint can empty the durable
   marks (anchor-paint.js, `paintDurable`). Readers ask
   `annotationsHidden()` rather than the root attribute, which is a rendering; a
   renderer that reads it repaints when it changes.

   The command is live while something watches, so a page with nothing over its content
   offers no press that hides nothing. Boot declares it where Leaf's own margin draws
   the layer; on a page that draws its own, the first package to watch declares it, so
   a page whose presentation covers nothing, such as a rail of threads, shows no row for
   it. */
import { signal } from "/runtime/framework.js";
import { tabStore } from "./tab-store.js";
import { setRuntimeRootAttribute } from "./root-state.js";
import { pageCommand } from "./keyboard/register.js";
import { repaint } from "./repaint.js";
import { notice } from "./notifications.js";
import { coarsePointer } from "./pointer.js";

import { ANNOTATIONS_KEY } from "./restore-state.js";

const hidden = signal(false);
/** @type {Set<(hidden: boolean) => void>} */
const watchers = new Set();

export const annotationsHidden = () => hidden.value;

/** @param {(hidden: boolean) => void} watcher */
export function watchAnnotations(watcher) {
  watchers.add(watcher);
}

// A package's part of the layer (module-annotations.md, "Hiding what a widget draws
// over the page"). Its watcher hears the state as it registers, which may follow the
// tab's restored state by any time, and each change after; its registration is what
// makes the command live, so it repaints the row that offers it.
/** @param {(hidden: boolean) => void} watcher */
export function watchAnnotationLayer(watcher) {
  if (typeof watcher !== "function")
    throw new TypeError("watchAnnotationLayer needs a function to tell");
  mountAnnotationControls();
  restoreAnnotations();
  watchers.add(watcher);
  repaint();
  watcher(hidden.value);
  return () => {
    if (watchers.delete(watcher)) repaint();
  };
}

let mounted = false;
export function mountAnnotationControls() {
  if (mounted) return;
  mounted = true;
  pageCommand({
    id: "annotations.toggle",
    keys: ["o"],
    title: () => (hidden.value ? "show annotations" : "hide annotations"),
    touch: () => (hidden.value ? "Show annotations" : "Hide annotations"),
    menu: "annotate",
    when: () => watchers.size > 0,
    run: () => {
      setAnnotationsHidden(!hidden.value);
      notice(
        !hidden.value
          ? "Annotations shown"
          : coarsePointer.matches
            ? "Annotations hidden"
            : "Annotations hidden — o shows them",
      );
    },
  });
}

/** @param {boolean} on */
function setAnnotationsHidden(on) {
  if (on === hidden.value) return;
  hidden.value = on;
  setRuntimeRootAttribute(
    document.documentElement,
    "data-lf-annotations",
    on ? "hidden" : null,
  );
  tabStore.set(ANNOTATIONS_KEY, on ? "hidden" : null);
  for (const watcher of watchers) watcher(on);
}

// Restore before presentation, after the actual overlay has installed its readers.
export function restoreAnnotations() {
  if (tabStore.get(ANNOTATIONS_KEY) === "hidden") setAnnotationsHidden(true);
}
