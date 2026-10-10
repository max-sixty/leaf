/* User-supplied media from draft to full-image inspection.

   The draft and event log keep one representation: ordinary Markdown naming immutable
   page media. A composer projects appended generated image blocks as thumbnails beside
   its text field, then materializes the same Markdown again when its visible words
   change or Send reads the draft. Each appended block carries its own two-newline
   separator; removing that suffix preserves every newline the user wrote.
   Draft, sent-message, and authored links to their own image open one native modal
   viewer. PhotoSwipe supplies image zoom, pan, and touch gestures on demand; native
   modality, retained controls, and focus return remain Leaf's. Links to other
   destinations and modified link presses keep their authored meaning. The document
   declares its public page root because a website module may live under an immutable
   release URL shared with a sample. All three resolve
   the same canonical `/media/…` text without rewriting durable content. The viewer's
   native dialog remains a retained chrome node. Its fitted image appears synchronously
   while the manipulation module loads. A queued close from an earlier opening
   leaves a reopened viewer's image and focus intact. */

import { html, render } from "../vendor/browser-runtime.js";
import { offlineInteractive, pageUrl, runtimeResource } from "./context.js";
import {
  handBack,
  focusDestination,
  closeLayer,
  openLayer,
  openerOf,
} from "./focus.js";
import { closeControl, offered } from "./widget-elements.js";
import { keys, paintKeys } from "./keyboard/scopes.js";
import {
  nativeLayers,
  showNativeLayer,
  closeNativeLayer,
} from "./keyboard/layer-stack.js";
import { keeps, keepsText } from "./keeps.js";
import { reducedMotion, FOLD_MS } from "./motion.js";

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

const viewerZoom = document.createElement("button");
viewerZoom.type = "button";
viewerZoom.className = "lf-btn lf-media-viewer-zoom";
viewerZoom.textContent = "100%";

const stage = document.createElement("div");
stage.className = "lf-media-viewer-stage";
const caption = document.createElement("p");
caption.className = "lf-media-viewer-caption";

let inspector = null;
let loading = null;
let opening = 0;

function imageTools() {
  if (!loading) {
    loading = import("../vendor/photoswipe.esm.js").then(
      ({ default: PhotoSwipe, styles }) => {
        const style = document.createElement("style");
        style.textContent = styles;
        // The authored head is replaced on revision; the viewer owns these styles.
        mediaViewer.append(style);
        return PhotoSwipe;
      },
    );
  }
  return loading;
}

function presentViewer(model) {
  render(
    html`
      <div class="lf-media-viewer-head">
        <strong id="lf-media-viewer-title">Image preview</strong>
        <div class="lf-media-viewer-actions">
          ${
            model
              ? html`<a
                  ${offered("lf-media-viewer-original", true)}
                  href=${model.url}
                  target="_blank"
                  rel="noopener"
                  >Original</a
                >`
              : null
          }
          ${viewerZoom}${viewerClose}
        </div>
      </div>
      ${stage}${caption}
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

keys(
  mediaViewer,
  "Image preview",
  [
    {
      id: "image.close",
      keys: ["Escape"],
      title: "close image",
      description: "Close image preview",
      control: viewerClose,
      run: () => closeLayer(() => closeNativeLayer(mediaViewer)),
    },
    {
      id: "image.zoom",
      keys: ["z"],
      title: "zoom / fit",
      description: "Toggle actual size and fitted image",
      control: viewerZoom,
      when: () => {
        const slide = inspector?.currSlide;
        return Boolean(
          slide &&
          (slide.zoomLevels.initial < 1 ||
            Math.abs(slide.currZoomLevel - slide.zoomLevels.initial) > 0.01),
        );
      },
      run: () => inspector.toggleZoom(),
    },
    {
      id: "image.pan",
      keys: ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"],
      title: "pan image",
      description: "Pan the enlarged image",
      repeat: true,
      when: () => Boolean(inspector),
      // PhotoSwipe owns the native key's directional panning.
    },
  ],
  { when: () => mediaViewer.open },
);

// The viewer hands the user back to the image they opened it from (focus.js,
// `openLayer`) once the platform has closed it, by its button, Escape or a press outside.
const open = (url, alt, from) => {
  const attempt = ++opening;
  inspector?.destroy();
  inspector = null;
  openLayer(mediaViewer, from);
  presentViewer({ url, alt });
  render(html`<img src=${url} alt=${alt} />`, stage);
  keepsText(
    caption,
    from.closest("figure")?.querySelector("figcaption")?.textContent || alt,
  );
  keepsText(viewerZoom, "100%");
  if (!mediaViewer.open) showNativeLayer(mediaViewer);
  focusDestination(viewerClose, "move");
  const image = stage.querySelector("img");
  Promise.all([imageTools(), image.decode()]).then(
    ([PhotoSwipe]) => {
      // A delayed load belongs only to the image the reader still has open.
      if (attempt !== opening || !mediaViewer.open) return;
      render(null, stage);
      const current = new PhotoSwipe({
        dataSource: [
          { src: url, width: image.naturalWidth, height: image.naturalHeight, alt },
        ],
        appendToEl: mediaViewer,
        paddingFn: () => ({
          top: mediaViewer.querySelector(".lf-media-viewer-head").offsetHeight + 16,
          right: 16,
          bottom: caption.offsetHeight + 16,
          left: 16,
        }),
        secondaryZoomLevel: 1,
        close: false,
        zoom: false,
        counter: false,
        arrowPrev: false,
        arrowNext: false,
        trapFocus: false,
        returnFocus: false,
        escKey: false,
        // The native dialog owns its opening and closing. Zoom alone animates.
        showHideAnimationType: "none",
        zoomAnimationDuration: reducedMotion() ? 0 : FOLD_MS,
        clickToCloseNonZoomable: false,
        bgClickAction: "close",
        tapAction: "zoom",
      });
      inspector = current;
      current.on("keydown", (event) => {
        // PhotoSwipe owns only native panning in the active viewer. Leaf owns zoom,
        // cancellation and scopes; the browser owns Tab. Its document listener must
        // never act behind a newer layer or reinterpret text typed there.
        const key = event.originalEvent;
        if (
          key.defaultPrevented ||
          !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(key.key) ||
          nativeLayers().at(-1)?.root !== mediaViewer ||
          !mediaViewer.contains(key.target)
        )
          event.preventDefault();
      });
      current.on("close", () => {
        if (mediaViewer.open) closeLayer(() => closeNativeLayer(mediaViewer));
      });
      current.on("zoomPanUpdate", () => {
        const slide = current.currSlide;
        const enlarged = slide.currZoomLevel > slide.zoomLevels.initial + 0.01;
        keepsText(viewerZoom, enlarged ? "Fit" : "100%");
        keeps(viewerZoom, "aria-label", enlarged ? "Fit image" : "Zoom to actual size");
        paintKeys();
      });
      current.init();
      // Modality belongs to the containing native dialog, not a second ARIA dialog.
      current.element.removeAttribute("role");
      current.element.removeAttribute("aria-modal");
      paintKeys();
    },
    (error) => {
      if (attempt !== opening || !mediaViewer.open) return;
      keepsText(
        caption,
        `Image controls unavailable: ${error.message}. Open Original to inspect the file.`,
      );
    },
  );
};
mediaViewer.addEventListener("close", () => {
  if (mediaViewer.open) return;
  ++opening;
  inspector?.destroy();
  inspector = null;
  const origin = openerOf(mediaViewer);
  openLayer(mediaViewer, null);
  closeLayer(
    () => {
      render(null, stage);
      presentViewer(null);
    },
    origin && (() => handBack(origin)),
  );
});
document.addEventListener("click", (event) => {
  if (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  )
    return;
  // The path ends at the document and the window, and an element whose id is
  // `matches` puts an object at `window.matches`, so only elements are asked.
  const trigger = event
    .composedPath()
    .find(
      (node) =>
        node instanceof Element && node.matches(".lf-media-open[data-lf-media-url]"),
    );
  const link = event.composedPath().find((node) => node instanceof HTMLAnchorElement);
  const image = link?.querySelector("img");
  // A linked image explicitly names its inspection destination; other image links
  // retain their author's destination.
  const imageLink =
    image &&
    !link.hasAttribute("download") &&
    (link.href === image.src || link.href === image.currentSrc);
  if (trigger || imageLink) {
    event.preventDefault();
    open(
      trigger?.dataset.lfMediaUrl || link.href,
      (trigger?.querySelector("img") || image)?.alt || "Image",
      trigger || link,
    );
  }
});
