/* User-supplied media from draft to full-image inspection.

   The draft and event log keep one representation: ordinary Markdown naming immutable
   page media. A composer projects the generated image blocks as thumbnails beside its
   text field, then materializes the same Markdown again when its visible words change or
   Send reads the draft. Sent-message images open one native modal viewer. The document
   declares its public page root because a website module may live under an immutable
   release URL shared with a sample. All three resolve
   the same canonical `/media/…` text without rewriting durable content. The viewer's
   native dialog remains a direct chrome child while its light-DOM Lit face owns the
   generated title, control, and image. */

import { LitElement, html } from "../vendor/browser-runtime.js";
import { offlineInteractive, pageUrl, runtimeResource } from "./context.js";
import { handBack } from "./focus.js";
import { closeControl } from "./widget-elements.js";

// Page media is whatever a reference names under this directory. The name a file there
// takes is the server's (Python's `schema.MEDIA_DIGEST`), which answers no other, so the
// browser reads a reference by its directory, as Python's own readings do, and leaves the
// name to the server.
const CANONICAL_MEDIA_ROOT = "/media/";
const PASTED_MEDIA = new RegExp(
  String.raw`!\[Pasted image\]\((${CANONICAL_MEDIA_ROOT}[^\s)]+)\)`,
  "g",
);

export const isCanonicalMediaUrl = (href) => href.startsWith(CANONICAL_MEDIA_ROOT);

export const scopedMediaUrl = (href) =>
  offlineInteractive ? runtimeResource(href) : new URL(pageUrl(href.slice(1))).pathname;

export function readPastedMedia(value) {
  const paths = [];
  const text = value
    .replace(PASTED_MEDIA, (_match, path) => {
      paths.push(path);
      return "";
    })
    .replace(/\n{3,}/g, "\n\n")
    .replace(/^\n+|\n+$/g, "");
  return { text, paths };
}

export function writePastedMedia(text, paths) {
  if (!paths.length) return text;
  const images = paths.map((path) => `![Pasted image](${path})`).join("\n\n");
  if (!text) return images;
  const separator = text.endsWith("\n\n") ? "" : text.endsWith("\n") ? "\n" : "\n\n";
  return text + separator + images;
}

const VIEWER_FACE_TAG = "leaf-media-viewer-face";

class MediaViewerFace extends LitElement {
  static properties = {
    model: { attribute: false },
  };

  #close = closeControl({
    name: "Close image preview",
    title: "Close image preview (Esc)",
  });

  constructor() {
    super();
    this.model = null;
    this.#close.onclick = () => this.closeViewer();
  }

  createRenderRoot() {
    return this;
  }

  present(model) {
    this.model = model;
    if (this.isConnected) this.performUpdate();
  }

  focusClose() {
    this.#close.focus({ preventScroll: true });
  }

  render() {
    return html`
      <div class="lf-media-viewer-head">
        <strong id="lf-media-viewer-title">Image preview</strong>
        ${this.#close}
      </div>
      <div class="lf-media-viewer-stage">
        ${this.model ? html`<img src=${this.model.url} alt=${this.model.alt} />` : null}
      </div>
    `;
  }
}

if (!customElements.get(VIEWER_FACE_TAG))
  customElements.define(VIEWER_FACE_TAG, MediaViewerFace);

export const mediaViewer = document.createElement("dialog");
mediaViewer.id = "lf-media-viewer";
mediaViewer.className = "lf-ui lf-media-viewer";
mediaViewer.setAttribute("closedby", "any");
mediaViewer.setAttribute("aria-modal", "true");
mediaViewer.setAttribute("aria-labelledby", "lf-media-viewer-title");
const viewerFace = document.createElement(VIEWER_FACE_TAG);
viewerFace.style.display = "contents";
viewerFace.closeViewer = () => mediaViewer.close();
mediaViewer.append(viewerFace);

let origin = null;
const open = (url, alt, from) => {
  origin = from;
  viewerFace.present(Object.freeze({ url, alt }));
  if (!mediaViewer.open) mediaViewer.showModal();
  viewerFace.focusClose();
};
mediaViewer.addEventListener("close", () => {
  viewerFace.present(null);
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
