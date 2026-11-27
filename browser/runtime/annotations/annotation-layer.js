// Compiled from annotation-layer.ts by build/typescript.mjs; edit that file.
/* Whether the annotation layer shows.

   The annotation layer is everything Leaf draws over the page's content: the margin rows
   shown as pins, whatever they hold, the durable marks on commented and reacted
   passages, an open card, and an unfolded cluster. The rail
   covers nothing, so it and everything standing in it stay. Hiding the layer changes no
   geometry, since nothing in it takes up room; it lets the user see what lies under it.

   The fact is this tab's view of the page, so it lives in the tab store and comes back
   with a reload, and a new page opens with the layer shown: a lasting "never show
   markers" would hide every arrival on every page.

   `g H` (Hidden) hides or shows it, one of Go-to's named rows (go-to-sequence.js),
   rather than a key of its own: the user hides it rarely, so it spends none of the few
   single letters the page has free. The user chose H for Hidden over leaving H to the
   changes `h` walks, as `g T` and `g M` open the lists `t` and `m` walk. Hiding it is
   no mode, though it lasts until the user shows it again: it changes what the page
   shows, not what a key or the panel's field does. So the field keeps taking words, and
   its standing words say the layer is hidden ("Annotations hidden", panel/floating-panel.js,
   `STANDING_PARTS`); a mode's chip would take the field's place.

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
import { signal } from "/vendor/signals-core.js";
import { tabStore } from "../state/tab-store.js";
import { chromeRoot } from "../base/chrome.js";
import { notice } from "../transport/notifications.js";

import { ANNOTATIONS_KEY } from "../state/restore-state.js";

const hidden = signal(false);
const watchers = new Set();

export const annotationsHidden = () => hidden.value;

export function watchAnnotations(watcher) {
  watchers.add(watcher);
}

// Go-to's row for the layer, which Go-to also declares to the page (leaf.js,
// `directDestinations`), so the leaf's menu and a finger reach it as `g H` does.
export const ANNOTATIONS_TOGGLE = {
  id: "annotations.toggle",
  keys: ["Shift+h"],
  title: () => (hidden.value ? "show annotations" : "hide annotations"),
  touch: () => (hidden.value ? "Show annotations" : "Hide annotations"),
  menu: "annotate",
  // A notice while the press's result stands, about the annotations (transport/notifications.js,
  // `about`); hiding them offers Show annotations as its press.
  run: () => {
    const on = !hidden.value;
    setAnnotationsHidden(on);
    const stands = () => hidden.value === on;
    notice(on ? "Annotations hidden" : "Annotations shown", {
      about: "annotations",
      stands,
      press: on
        ? {
            action: "show-annotations",
            command: "annotations.toggle",
            stands,
          }
        : null,
    });
  },
};

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
