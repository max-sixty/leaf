/* Whether the annotation layer shows.

   The annotation layer is everything drawn over the page's content for its
   annotations. Under Leaf's own margin that is the margin rows shown as pins, whatever
   they hold, the durable marks on commented and reacted passages, an open card, and an
   unfolded cluster. The rail covers nothing, so it and everything standing in it stay.
   A package that draws over the page's content, as a page presenting its own
   annotations does (`data-annotations="page"`), joins the layer through the same door
   Leaf's margin and passage paint use (`watchAnnotationLayer`). Hiding the layer
   changes no geometry, since nothing in it takes up room; it lets the user see what
   lies under it.

   The fact is this tab's view of the page, so it lives in the tab store and comes back
   with a reload, and a new page opens with the layer shown: a lasting "never show
   markers" would hide every arrival on every page.

   `setAnnotationsHidden` is the one writer. It states the fact on the chrome's root
   (`data-lf-annotations-hidden`) for the stylesheets, keeps it for the tab, and tells
   each watcher, so the margin can take focus and its card off what it hides and the
   passage paint can empty the durable marks (anchor-paint.js, `paintDurable`). Readers
   ask `annotationsHidden()` rather than the attribute, which is a rendering; a renderer
   that reads it repaints when it changes. The margin's pins and change bars stand in
   the chrome and read the attribute through its root; the contents map's changed
   stretch, in the page, reads it through `:root:has()` (toc.css). On `html`, a custom
   property the attribute set restyled every element of the page each time the layer
   changed, and a rule reading it through a descendant combinator made Firefox visit
   every element: 2 to 3 s of Firefox's main thread on a page of 1.5 million.

   The command stands on every page, and takes a press while something watches or the
   layer is hidden, so a page with nothing over its content offers no press that hides
   nothing, and a layer hidden when its last watcher left, as a page's own margin leaves
   with a revision, can still be shown. */
import { signal } from "/runtime/framework.js";
import { tabStore } from "./tab-store.js";
import { chromeRoot } from "./chrome.js";
import { pageCommand } from "./keyboard/register.js";
import { repaint } from "./repaint.js";
import { notice } from "./notifications.js";
import { coarsePointer } from "./pointer.js";

import { ANNOTATIONS_KEY } from "./restore-state.js";

const hidden = signal(false);
/** @type {Set<(hidden: boolean) => void>} */
const watchers = new Set();

export const annotationsHidden = () => hidden.value;

// Join the layer: `watcher(hidden)` hears each change, and hears at once a layer that
// stands hidden as it joins, as one restored for the tab before a widget upgraded
// does. A watcher joining a shown layer hears nothing, since it draws shown already.
// Its coming and going change whether the command takes a press, so each repaints the
// row that offers it. The returned function leaves the layer.
/** @param {(hidden: boolean) => void} watcher */
export function watchAnnotationLayer(watcher) {
  watchers.add(watcher);
  repaint();
  if (hidden.value) watcher(true);
  return () => {
    if (watchers.delete(watcher)) repaint();
  };
}

export function mountAnnotationControls() {
  pageCommand({
    id: "annotations.toggle",
    keys: ["o"],
    title: () => (hidden.value ? "show annotations" : "hide annotations"),
    touch: () => (hidden.value ? "Show annotations" : "Hide annotations"),
    menu: "annotate",
    when: () => watchers.size > 0 || hidden.value,
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
  chromeRoot.toggleAttribute("data-lf-annotations-hidden", on);
  tabStore.set(ANNOTATIONS_KEY, on ? "hidden" : null);
  for (const watcher of watchers) watcher(on);
}

// Restore before presentation, after Leaf's own margin has joined the layer; what a
// package draws joins as its widget upgrades, and hears the restored state then.
export function restoreAnnotations() {
  if (tabStore.get(ANNOTATIONS_KEY) === "hidden") setAnnotationsHidden(true);
}
