/* User-supplied media from draft to full-image inspection.

   The draft and event log keep one representation: ordinary Markdown naming immutable
   page media. A composer projects appended generated image blocks as thumbnails beside
   its text field, then materializes the same Markdown again when its visible words
   change or Send reads the draft. Each appended block carries its own two-newline
   separator; removing that suffix preserves every newline the user wrote.
   Sent-message images open one native modal viewer. The document
   declares its public page root because a website module may live under an immutable
   release URL shared with a sample. All three resolve
   the same canonical `/media/…` text without rewriting durable content. The viewer's
   native dialog remains a retained chrome node, with its title, retained Close control,
   and image rendered synchronously by Lit. A queued close from an earlier opening
   leaves a reopened viewer's image and focus intact. */

import { html, render } from "../vendor/browser-runtime.js";
import { offlineInteractive, pageUrl, runtimeResource } from "./context.js";
import { handBack, focusDestination } from "./focus.js";
import { closeControl } from "./widget-elements.js";

// Page media is whatever a reference names under this directory. The name a file there
// takes is the server's (Python's `schema.MEDIA_DIGEST`), which answers no other, so the
// browser reads a reference by its directory, as Python's own readings do, and leaves the
// name to the server.
const CANONICAL_MEDIA_ROOT = "/media/";
const PASTED_IMAGE = String.raw`!\[Pasted image\]\((${CANONICAL_MEDIA_ROOT}[^\s)]+)\)`;
const PASTED_MEDIA = new RegExp(PASTED_IMAGE, "g");
const MEDIA_SUFFIX = new RegExp(
  `(?:^|\\n\\n)${PASTED_IMAGE}(?:\\n\\n${PASTED_IMAGE})*(?![\\s\\S])`,
);

export const isCanonicalMediaUrl = (href) => href.startsWith(CANONICAL_MEDIA_ROOT);

export const scopedMediaUrl = (href) =>
  offlineInteractive ? runtimeResource(href) : new URL(pageUrl(href.slice(1))).pathname;

export function readPastedMedia(value) {
  const suffix = MEDIA_SUFFIX.exec(value);
  if (!suffix) return { text: value, paths: [] };
  return {
    text: value.slice(0, suffix.index),
    paths: Array.from(suffix[0].matchAll(PASTED_MEDIA), (image) => image[1]),
  };
}

export function writePastedMedia(text, paths) {
  if (!paths.length) return text;
  const images = paths.map((path) => `![Pasted image](${path})`).join("\n\n");
  if (!text) return images;
  return text + "\n\n" + images;
}

const viewerClose = closeControl({
  name: "Close image preview",
  title: "Close image preview (Esc)",
});
viewerClose.onclick = () => mediaViewer.close();

function presentViewer(model) {
  render(
    html`
      <div class="lf-media-viewer-head">
        <strong id="lf-media-viewer-title">Image preview</strong>
        ${viewerClose}
      </div>
      <div class="lf-media-viewer-stage">
        ${model ? html`<img src=${model.url} alt=${model.alt} />` : null}
      </div>
    `,
    mediaViewer,
  );
}

export const mediaViewer = document.createElement("dialog");
mediaViewer.id = "lf-media-viewer";
mediaViewer.className = "lf-ui lf-media-viewer";
mediaViewer.setAttribute("closedby", "any");
mediaViewer.setAttribute("aria-modal", "true");
mediaViewer.setAttribute("aria-labelledby", "lf-media-viewer-title");
presentViewer(null);

let origin = null;
const open = (url, alt, from) => {
  origin = from;
  presentViewer({ url, alt });
  if (!mediaViewer.open) mediaViewer.showModal();
  focusDestination(viewerClose, "move");
};
mediaViewer.addEventListener("close", () => {
  if (mediaViewer.open) return;
  presentViewer(null);
  if (origin) handBack(origin);
  origin = null;
});
document.addEventListener("click", (event) => {
  // The path ends at the document and the window, and an element whose id is
  // `matches` puts an object at `window.matches`, so only elements are asked.
  const trigger = event
    .composedPath()
    .find(
      (node) =>
        node instanceof Element && node.matches(".lf-media-open[data-lf-media-url]"),
    );
  if (trigger)
    open(
      trigger.dataset.lfMediaUrl,
      trigger.querySelector("img")?.alt || "Pasted image",
      trigger,
    );
});
