/* Whether the annotation layer shows.

   The annotation layer is everything Leaf draws over the page's content: the margin rows
   shown as pins, whatever they hold, the durable marks on commented and reacted
   passages, an open card, and an unfolded cluster. The rail
   covers nothing, so it and everything standing in it stay. Hiding the layer changes no
   geometry, since nothing in it takes up room; it lets the user see what lies under it.

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
   every element: 2 to 3 s of Firefox's main thread on a page of 1.5 million. */
import { signal } from "/runtime/framework.js";
import { tabStore } from "./tab-store.js";
import { chromeRoot } from "./chrome.js";
import { pageCommand } from "./keyboard/register.js";
import { pressCommand } from "./keyboard/dispatch.js";
import { notice } from "./notifications.js";

import { ANNOTATIONS_KEY } from "./restore-state.js";

const hidden = signal(false);
// The press the notice of hidden annotations offers: `o` again, which brings them back.
/** @type {import("./notifications.js").Press} */
const SHOW_ANNOTATIONS = {
  action: "show-annotations",
  command: "annotations.toggle",
  run: () => pressCommand("annotations.toggle"),
  stands: () => hidden.value,
};
/** @type {Set<(hidden: boolean) => void>} */
const watchers = new Set();

export const annotationsHidden = () => hidden.value;

/** @param {(hidden: boolean) => void} watcher */
export function watchAnnotations(watcher) {
  watchers.add(watcher);
}

export function mountAnnotationControls() {
  pageCommand({
    id: "annotations.toggle",
    keys: ["o"],
    title: () => (hidden.value ? "show annotations" : "hide annotations"),
    touch: () => (hidden.value ? "Show annotations" : "Hide annotations"),
    menu: "annotate",
    // A notice while the press's result stands. Hiding offers Show annotations, the press
    // that brings them back, which the page field's standing "Annotations hidden"
    // doesn't (floating-panel.js, `standing`), so that notice shows in the field too.
    // Showing them says only that those words went, so it is about the annotations and
    // shows where those words don't, as on the folded leaf.
    run: () => {
      const on = !hidden.value;
      setAnnotationsHidden(on);
      notice(on ? "Annotations hidden" : "Annotations shown", {
        press: on ? SHOW_ANNOTATIONS : null,
        about: on ? null : "annotations",
        stands: () => hidden.value === on,
      });
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

// Restore before presentation, after the actual overlay has installed its readers.
export function restoreAnnotations() {
  if (tabStore.get(ANNOTATIONS_KEY) === "hidden") setAnnotationsHidden(true);
}
