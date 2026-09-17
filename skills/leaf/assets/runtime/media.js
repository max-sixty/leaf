/* Reader-supplied media from draft to full-image inspection.

   The draft and event log keep one representation: ordinary Markdown naming immutable
   page media. A composer projects the generated image blocks as thumbnails beside its
   textarea, then materializes the same Markdown again when its visible words change or
   Send reads the draft. Sent-message images open one native modal viewer. The document
   declares its public page root because a website module may live under an immutable
   release URL; ordinary and MCP pages fall back to the module route. All three resolve
   the same canonical `/media/…` text without rewriting durable content. The viewer's
   native dialog remains a direct chrome child while its light-DOM Lit face owns the
   generated title, control, and image. */

// Joined rather than written whole: the MCP boundary's route scoper rewrites a quoted
// media root in served JS (http.py's _ROOTED_PAGE_ROUTE), and this constant has to keep
// speaking the canonical text that drafts and events carry. MEDIA_PATH's escaped form
// below dodges the same rewrite; neither may be spelled the obvious way.
import { LitElement, html } from "../vendor/browser-runtime.js";
import { offlineInteractive, runtimeResource } from "./context.js";

const CANONICAL_MEDIA_ROOT = "/" + "media/";
const runtimeMarker = document.querySelector(
  "script[data-lf-server], script[data-lf-runtime][data-lf-offline]",
);
const declaredPageRoot = runtimeMarker?.dataset.lfPageRoot;
const MODULE_PAGE_ROOT = offlineInteractive
  ? null
  : declaredPageRoot === undefined
    ? new URL("../", import.meta.url)
    : new URL(`${declaredPageRoot || ""}/`, location.origin);
const MEDIA_NAME = /^[a-f0-9]{16}\.(?:png|jpe?g|gif|webp|svg)$/;
const MEDIA_PATH = String.raw`\/media\/[a-f0-9]{16}\.(?:png|jpe?g|gif|webp|svg)`;
const PASTED_MEDIA = new RegExp(String.raw`!\[Pasted image\]\((${MEDIA_PATH})\)`, "g");

export const isCanonicalMediaUrl = (href) => {
  if (!href.startsWith(CANONICAL_MEDIA_ROOT)) return false;
  return MEDIA_NAME.test(href.slice(CANONICAL_MEDIA_ROOT.length));
};

export const scopedMediaUrl = (href) =>
  offlineInteractive
    ? runtimeResource(href)
    : new URL(
        href.slice(CANONICAL_MEDIA_ROOT.length),
        new URL("media/", MODULE_PAGE_ROOT),
      ).pathname;

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

  constructor() {
    super();
    this.model = null;
    this.closeViewer = null;
  }

  createRenderRoot() {
    return this;
  }

  present(model) {
    this.model = model;
    if (this.isConnected) this.performUpdate();
  }

  focusClose() {
    this.querySelector(".lf-media-viewer-head > button").focus({
      preventScroll: true,
    });
  }

  render() {
    return html`
      <div class="lf-media-viewer-head">
        <strong id="lf-media-viewer-title">Image preview</strong>
        <button class="lf-btn" type="button" @click=${this.closeViewer}>Close</button>
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
// The viewer covers the page to show one image, so every ordinary way out of it is a
// way out: the close control, a close request, and the backdrop the image sits on. The
// platform runs all three off this declaration, including the backdrop press whose
// target a modal dialog reports as the dialog itself.
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
  if (origin?.isConnected) origin.focus({ preventScroll: true });
  origin = null;
});
document.addEventListener("click", (event) => {
  const trigger = event
    .composedPath()
    .find((node) => node?.matches?.(".lf-media-open[data-lf-media-url]"));
  if (trigger)
    open(
      trigger.dataset.lfMediaUrl,
      trigger.querySelector("img")?.alt || "Pasted image",
      trigger,
    );
});
