/* User-supplied media from draft to full-image inspection.

   The draft and event log keep one representation: ordinary Markdown naming immutable
   page media. A composer projects appended generated image blocks as thumbnails beside
   its text field, then materializes the same Markdown again when its visible words
   change or Send reads the draft. Each appended block carries its own two-newline
   separator; removing that suffix preserves every newline the user wrote.
   Draft, sent-message, and authored links to their own image open one native modal
   viewer. A local drawing supplies its frozen canvas pixels at the press; its
   temporary image URL belongs only to that opening, never to the durable draft.
   PhotoSwipe supplies image zoom, pan, and touch gestures on demand; native
   modality, retained controls, and focus return remain Leaf's. An authored figure
   caption, an inspection link's explicit caption, or a table cell's column and row
   heads stay outside the image in a readable footer; alt text stays with the image.
   Links to other destinations and modified link presses keep their authored meaning. The document
   declares its public page root because a website module may live under an immutable
   release URL shared with a sample. All three resolve
   the same canonical `/media/…` text without rewriting durable content. The viewer's
   native dialog remains a retained chrome node. The image first appears in PhotoSwipe,
   once its module has loaded and the image has decoded, since PhotoSwipe needs the
   image's size up front; a second renderer shown meanwhile would have to agree with
   it on every box. An image opened from inside a popover, such as a draft's attachment
   in the page comment card, leaves that popover and its draft standing beneath the
   viewer (layer-stack.js, `showNativeLayer`). A queued close from an earlier opening leaves a reopened viewer's
   image and focus intact. */

import { describeFailure } from "./exception.js";
import { html, render } from "/runtime/framework.js";
import { offlineInteractive, pageUrl, runtimeResource } from "./context.js";
import { inBaseLayer } from "./base-layer.js";
import {
  handBack,
  focusDestination,
  closeLayer,
  openLayer,
  openerOf,
} from "./focus.js";
import { closeControl, offerAction, offered } from "./widget-elements.js";
import { keys, paintKeys } from "./keyboard/scopes.js";
import {
  nativeLayers,
  showNativeLayer,
  closeNativeLayer,
} from "./keyboard/layer-stack.js";
import { keeps, keepsHidden, keepsText } from "./keeps.js";
import { reducedMotion, foldDuration } from "./motion.js";
import { says } from "./passages.js";
import { plainPress } from "./pointer.js";

// Page media is whatever a reference names under this directory. The name a file there
// takes is the server's (Python's `schema.MEDIA_DIGEST`), which answers no other, so the
// browser reads a reference by its directory, as Python's own readings do, and leaves the
// name to the server.
const CANONICAL_MEDIA_ROOT = "/media/";
const ATTACHED_IMAGE = String.raw`!\[Attached image\]\((${CANONICAL_MEDIA_ROOT}[^\s)]+)\)`;
const ATTACHED_MEDIA = new RegExp(ATTACHED_IMAGE, "g");
const MEDIA_SUFFIX = new RegExp(
  `(?:^|\\n\\n)${ATTACHED_IMAGE}(?:\\n\\n${ATTACHED_IMAGE})*(?![\\s\\S])`,
);

/** @param {string} href */
export const isCanonicalMediaUrl = (href) => href.startsWith(CANONICAL_MEDIA_ROOT);

/** @param {string} href */
export const scopedMediaUrl = (href) =>
  offlineInteractive ? runtimeResource(href) : new URL(pageUrl(href.slice(1))).pathname;

/** @param {string} value */
export function readAttachedMedia(value) {
  const suffix = MEDIA_SUFFIX.exec(value);
  if (!suffix) return { text: value, paths: [] };
  return {
    text: value.slice(0, suffix.index),
    paths: [...suffix[0].matchAll(ATTACHED_MEDIA)].flatMap((image) => image.slice(1)),
  };
}

/** @param {string} text @param {readonly string[]} paths */
export function writeAttachedMedia(text, paths) {
  if (!paths.length) return text;
  const images = paths.map((path) => `![Attached image](${path})`).join("\n\n");
  if (!text) return images;
  return text + "\n\n" + images;
}

const viewerClose = closeControl({
  name: "Close image preview",
  title: "Close image preview (Esc)",
});

const viewerZoom = offerAction("word", "lf-media-viewer-zoom", "100%");

const stage = document.createElement("div");
stage.className = "lf-media-viewer-stage";
const caption = document.createElement("p");
caption.className = "lf-media-viewer-caption scroll";

/** @type {import("photoswipe").default | null} */
let inspector = null;
/** @type {Promise<typeof import("/vendor/photoswipe.esm.js").default> | null} */
let loading = null;
let opening = 0;
/** @type {string | null} */
let canvasUrl = null;

function imageTools() {
  if (!loading) {
    loading = import("/vendor/photoswipe.esm.js").then(
      ({ default: PhotoSwipe, styles }) => {
        const style = document.createElement("style");
        // Layered, as a dependency's defaults are, so the chrome's guard rolls back to
        // them rather than past them (styles/chrome-guard.css).
        style.textContent = inBaseLayer(styles);
        // The authored head is replaced on revision; the viewer owns these styles.
        mediaViewer.append(style);
        return PhotoSwipe;
      },
    );
  }
  return loading;
}

/** @param {{url: string, alt: string} | null} model */
function presentViewer(model) {
  render(
    html`
      <div class="lf-media-viewer-head">
        <strong id="lf-media-viewer-title" class="lf-dialog-title"
          >Image preview</strong
        >
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
      control: viewerClose,
      run: () => closeLayer(() => closeNativeLayer(mediaViewer)),
    },
    {
      id: "image.zoom",
      keys: ["z"],
      title: "zoom / fit",
      control: viewerZoom,
      when: () => {
        const slide = inspector?.currSlide;
        return Boolean(
          slide &&
          (slide.zoomLevels.initial < 1 ||
            Math.abs(slide.currZoomLevel - slide.zoomLevels.initial) > 0.01),
        );
      },
      run: () => inspector?.toggleZoom(),
    },
    {
      id: "image.pan",
      keys: ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"],
      title: "pan image",
      repeat: true,
      when: () => Boolean(inspector),
      // PhotoSwipe owns the native key's directional panning.
    },
  ],
  { when: () => mediaViewer.open },
);

// A capture in a table cell is named by the heads it stands under and beside, since a
// table of captures labels each axis once rather than each frame (authoring-evidence.md,
// "Source files and media"). Heads are read where they stand rather than where they
// come in the markup: a column head is a heading of the cell's own table across the
// cell's middle and above it, and a row head a `scope="row"` heading level with its
// middle and before it in the reading direction. So a spanning head names every cell
// under it, a two-row header names a cell twice, outer first, and a header row written
// without `<thead>` still counts. Each head reads as what it says, which leaves out a
// comment's mark the paint pass wrote into it.
const cellHeads = (/** @type {Element} */ from) => {
  const cell = from.closest("td");
  if (!cell) return "";
  const table = cell.closest("table");
  if (!table) return "";
  const box = cell.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const rtl = getComputedStyle(table).direction === "rtl";
  const columns = [];
  const rows = [];
  for (const head of table.querySelectorAll("th")) {
    if (head.closest("table") !== table) continue;
    const at = head.getBoundingClientRect();
    if (head.matches('[scope="row"]')) {
      const before = rtl ? at.left >= box.right - 1 : at.right <= box.left + 1;
      if (before && at.top <= y && y < at.bottom) rows.push(head);
    } else if (at.bottom <= box.top + 1 && at.left <= x && x < at.right)
      columns.push(head);
  }
  // A header row repeated before a later section stands above the capture twice.
  return [
    ...new Set([...columns, ...rows].map((head) => says(head)).filter(Boolean)),
  ].join(" · ");
};

// The viewer hands the user back to the image they opened it from (focus.js,
// `openLayer`) once the platform has closed it, by its button, Escape or a press outside.
/** @param {string | HTMLCanvasElement} source @param {string} alt @param {Element} from */
const open = async (source, alt, from) => {
  const attempt = ++opening;
  inspector?.destroy();
  inspector = null;
  if (canvasUrl) URL.revokeObjectURL(canvasUrl);
  canvasUrl = null;
  const canvas = source instanceof HTMLCanvasElement;
  openLayer(mediaViewer, from);
  presentViewer(canvas ? null : { url: source, alt });
  render(canvas ? html`<p>Preparing image…</p>` : null, stage);
  const figureCaption = from.closest("figure")?.querySelector("figcaption");
  const description =
    from.getAttribute("data-lf-media-caption") ||
    (figureCaption && says(figureCaption)) ||
    cellHeads(from);
  keepsText(caption, description);
  keepsHidden(caption, !description);
  keepsText(viewerZoom, "100%");
  if (!mediaViewer.open) showNativeLayer(mediaViewer, { source: from });
  focusDestination(viewerClose, "move");
  /** @type {string} */
  let url;
  if (canvas) {
    // Native encoding snapshots the pixels at this press. A late completion cannot
    // reopen a closed viewer or replace an image the reader opened since.
    let blob;
    try {
      /** @type {Promise<Blob | null>} */
      const encoded = new Promise((resolve) => source.toBlob(resolve));
      blob = await encoded;
      if (!blob) throw new Error("the drawing could not be encoded");
    } catch (error) {
      if (attempt !== opening || !mediaViewer.open) return;
      render(html`<p>Image preview unavailable: ${describeFailure(error)}.</p>`, stage);
      return;
    }
    if (attempt !== opening || !mediaViewer.open) return;
    canvasUrl = URL.createObjectURL(blob);
    url = canvasUrl;
    presentViewer({ url, alt });
  } else url = source;
  render(
    html`<span class="lf-media-viewer-probe"><img src=${url} alt="" /></span>`,
    stage,
  );
  const probe = stage.querySelector("img");
  if (!probe) throw new Error("Image inspection needs its rendered decode probe");
  Promise.all([imageTools(), probe.decode()]).then(
    ([PhotoSwipe]) => {
      // A delayed load belongs only to the image the reader still has open.
      if (attempt !== opening || !mediaViewer.open) return;
      // In a 1px column an image keeps a width its file states; one that states none
      // (an SVG with only a viewBox, or Mermaid's percentage width) narrows to the
      // column, and its natural size is a stand-in of its shape at 300px. Such an
      // image takes the size that covers the screen in either orientation, so it fits
      // below 100% in any window and zooms past its fit.
      const { naturalWidth: width, naturalHeight: height } = probe;
      const cover =
        Math.max(window.screen.width, window.screen.height) / Math.min(width, height);
      const size =
        probe.getBoundingClientRect().width > 1
          ? { width, height }
          : { width: width * cover, height: height * cover };
      render(null, stage);
      const current = new PhotoSwipe({
        dataSource: [{ src: url, alt, ...size }],
        appendToEl: mediaViewer,
        paddingFn: (viewport) => {
          const box = stage.getBoundingClientRect();
          const inset = getComputedStyle(stage);
          return {
            top: box.top + parseFloat(inset.paddingTop),
            right: viewport.x - box.right + parseFloat(inset.paddingRight),
            bottom: viewport.y - box.bottom + parseFloat(inset.paddingBottom),
            left: box.left + parseFloat(inset.paddingLeft),
          };
        },
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
        zoomAnimationDuration: reducedMotion() ? 0 : foldDuration(),
        clickToCloseNonZoomable: false,
        bgClickAction: "close",
        tapAction: "zoom",
      });
      inspector = current;
      current.on("keydown", (event) => {
        // PhotoSwipe owns only native panning in the active viewer. Leaf owns zoom,
        // cancellation and scopes, and Tab stays the browser's. Its document
        // listener must never act behind a newer layer or reinterpret text typed there.
        const key = event.originalEvent;
        if (
          key.defaultPrevented ||
          !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(key.key) ||
          nativeLayers().at(-1)?.root !== mediaViewer ||
          !(key.target instanceof Node && mediaViewer.contains(key.target))
        )
          event.preventDefault();
      });
      current.on("close", () => {
        if (mediaViewer.open) closeLayer(() => closeNativeLayer(mediaViewer));
      });
      current.on("zoomPanUpdate", ({ slide }) => {
        const enlarged = slide.currZoomLevel > slide.zoomLevels.initial + 0.01;
        keepsText(viewerZoom, enlarged ? "Fit" : "100%");
        keeps(viewerZoom, "aria-label", enlarged ? "Fit image" : "Zoom to actual size");
        paintKeys();
      });
      current.init();
      // Modality belongs to the containing native dialog, not a second ARIA dialog.
      const root = current.element;
      if (!root)
        throw new Error("PhotoSwipe did not create its image inspection surface");
      root.removeAttribute("role");
      root.removeAttribute("aria-modal");
      paintKeys();
    },
    (error) => {
      if (attempt !== opening || !mediaViewer.open) return;
      keepsText(
        caption,
        `Image preview unavailable: ${describeFailure(error)}. Open Original to see the file.`,
      );
      keepsHidden(caption, false);
    },
  );
};
mediaViewer.addEventListener("close", () => {
  if (mediaViewer.open) return;
  ++opening;
  inspector?.destroy();
  inspector = null;
  if (canvasUrl) URL.revokeObjectURL(canvasUrl);
  canvasUrl = null;
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
  if (event.defaultPrevented || !plainPress(event)) return;
  // The path ends at the document and the window, and an element whose id is
  // `matches` puts an object at `window.matches`, so only elements are asked.
  const path = event.composedPath();
  const trigger = path.find(
    /** @returns {node is Element} */ (node) =>
      node instanceof Element &&
      node.matches(
        ".lf-media-open[data-lf-media-url], .lf-media-open[data-lf-media-canvas]",
      ),
  );
  const link = path.find((node) => node instanceof HTMLAnchorElement);
  const image = link?.querySelector("img");
  // Only an image link to its own file opens inspection; other links keep their destination.
  const imageLink =
    link &&
    image &&
    !link.hasAttribute("download") &&
    (link.href === image.src || link.href === image.currentSrc);
  const origin = trigger ?? (link && imageLink ? link : null);
  if (!origin) return;
  const canvas = trigger?.hasAttribute("data-lf-media-canvas")
    ? trigger.querySelector("canvas")
    : null;
  const source =
    canvas ||
    trigger?.getAttribute("data-lf-media-url") ||
    (link && imageLink ? link.href : null);
  if (!source) throw new Error("Image inspection needs a canvas or image URL");
  event.preventDefault();
  void open(
    source,
    trigger?.getAttribute("data-lf-media-alt") ||
      (trigger?.querySelector("img") || image)?.alt ||
      "Image",
    origin,
  );
});
