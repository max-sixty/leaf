/* Reader-supplied media from draft to full-image inspection.

   The draft and event log keep one representation: ordinary Markdown naming immutable
   page media. A composer projects the generated image blocks as thumbnails beside its
   textarea, then materializes the same Markdown again when its visible words change or
   Send reads the draft. Sent-message images open one native modal viewer. Its URL is
   derived from this module's served route, so a normal page and an MCP capability page
   resolve the same canonical `/media/…` text without rewriting durable content. */

const CANONICAL_MEDIA_ROOT = "/" + "media/";
const MODULE_PAGE_ROOT = new URL("../", import.meta.url);
const MEDIA_NAME = /^[a-f0-9]{16}\.(?:png|jpe?g|gif|webp|svg)$/;
const MEDIA_PATH = String.raw`\/media\/[a-f0-9]{16}\.(?:png|jpe?g|gif|webp|svg)`;
const PASTED_MEDIA = new RegExp(
  String.raw`\[!\[Pasted image\]\((${MEDIA_PATH})\)\]\(\1\)|!\[Pasted image\]\((${MEDIA_PATH})\)`,
  "g",
);

export const isCanonicalMediaUrl = (href) => {
  if (!href.startsWith(CANONICAL_MEDIA_ROOT)) return false;
  return MEDIA_NAME.test(href.slice(CANONICAL_MEDIA_ROOT.length));
};

export const scopedMediaUrl = (href) =>
  new URL(href.slice(CANONICAL_MEDIA_ROOT.length), new URL("media/", MODULE_PAGE_ROOT))
    .pathname;

export function readPastedMedia(value) {
  const paths = [];
  const text = value
    .replace(PASTED_MEDIA, (_match, linked, plain) => {
      paths.push(linked ?? plain);
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

export const mediaViewer = document.createElement("dialog");
mediaViewer.className = "lf-ui lf-media-viewer";
mediaViewer.setAttribute("aria-modal", "true");
mediaViewer.setAttribute("aria-labelledby", "lf-media-viewer-title");
const head = document.createElement("div");
head.className = "lf-media-viewer-head";
const title = document.createElement("strong");
title.textContent = "Image preview";
title.id = "lf-media-viewer-title";
const close = document.createElement("button");
close.className = "lf-btn";
close.textContent = "Close";
close.type = "button";
close.onclick = () => mediaViewer.close();
head.append(title, close);
const stage = document.createElement("div");
stage.className = "lf-media-viewer-stage";
const image = document.createElement("img");
stage.append(image);
mediaViewer.append(head, stage);

let origin = null;
const open = (url, alt, from) => {
  origin = from;
  image.src = url;
  image.alt = alt;
  if (!mediaViewer.open) mediaViewer.showModal();
  close.focus({ preventScroll: true });
};
mediaViewer.addEventListener("close", () => {
  image.removeAttribute("src");
  if (origin?.isConnected) origin.focus({ preventScroll: true });
  origin = null;
});
mediaViewer.addEventListener("mousedown", (event) => {
  if (event.target !== mediaViewer) return;
  const box = mediaViewer.getBoundingClientRect();
  if (
    event.clientX < box.left ||
    event.clientX > box.right ||
    event.clientY < box.top ||
    event.clientY > box.bottom
  ) {
    event.preventDefault();
    mediaViewer.close();
  }
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
