/* Markdown on a Leaf page: how the page writes the links and pictures the library's
   dialect renders (lib/markdown.js), and the passes that render the words the composed
   registry declares Markdown. The dialect itself reads nothing of the page's. */
import { opensElsewhere } from "./declared-words.js";
import { offerContentElement } from "../base/element-markers.js";
import { describeFailure } from "../lib/exception.js";
import {
  loadMarkdown,
  markdownReady,
  paintMarkdown,
  renderMarkdown,
} from "../lib/markdown.js";
import { isCanonicalMediaUrl, scopedMediaUrl } from "./media.js";
import { declaredElements } from "../state/registry.js";
import { dataBody } from "../lib/data-body.js";
import type { MarkdownLinks } from "../lib/markdown.js";
import type { WidgetDeclaration } from "../../types/contract.js";

/** The page's links and pictures (`MarkdownLinks` in lib/markdown.js), which every
 * rendering on a Leaf page passes. The page's own media answers at the page's address
 * (media.js, `scopedMediaUrl`), and its picture is a press that opens the media viewer.
 * Markdown can't say where a link opens, so a link that leaves the page opens in a new
 * tab, and the page, and the thread the reader followed the link from, stay open where
 * they were. */
export const pageLinks: MarkdownLinks = {
  link: (href) =>
    isCanonicalMediaUrl(href)
      ? { href: scopedMediaUrl(href) }
      : opensElsewhere(href)
        ? { target: "_blank" }
        : undefined,
  picture: (image) => {
    const href = image.getAttribute("src");
    if (href === null || !isCanonicalMediaUrl(href)) return image;
    const source = scopedMediaUrl(href);
    image.setAttribute("src", source);
    const button = offerContentElement(
      image.ownerDocument.createElement("button"),
      "picture",
      "lf-media-open lf-message-media",
    );
    button.setAttribute("data-lf-said", "");
    button.setAttribute("data-lf-media-url", source);
    button.setAttribute("aria-label", `View ${image.alt || "Image"}`);
    button.append(image);
    return button;
  },
};

// A declaration whose data body is Markdown words (`content: markdown`).
const wordsAreMarkdown = (entry: WidgetDeclaration) => entry.content === "markdown";

// A Markdown body (`content: markdown`) is the layer's to render, so a package
// declaration cannot make file-side passages read words the browser leaves as raw
// Markdown.
export async function loadDeclaredMarkdown(
  scope: Element | Document | DocumentFragment,
) {
  if (!declaredElements(scope, wordsAreMarkdown).length) return;
  let failure: unknown;
  if (!(await loadMarkdown((error) => (failure = error))))
    throw new Error(
      `leaf: Markdown renderer failed to load: ${describeFailure(failure)}`,
    );
}

// Each element declaring `content: markdown` shows its data body's rendering in place
// of its `<pre>`. Only presentation nodes are formatted. Source documents stay intact
// for typed state, revision patching and provenance; arrivals call this after capture,
// before connection. Their import preparation has already made the parser ready, so
// this step is synchronous. The server's first paint of a body (`data-lf-prepaint`)
// stamps the source it rendered, as `paintMarkdown` does, but its rendering writes none
// of the page's links, so the stamp doesn't spare that body its paint.
export function formatDeclaredMarkdown(scope: Element | Document | DocumentFragment) {
  const elements = declaredElements(scope, wordsAreMarkdown);
  if (!elements.length) return;
  if (!markdownReady())
    throw new Error("leaf: Markdown formatting requires its loaded renderer");
  for (const element of elements) {
    const pre = element.querySelector(":scope > pre");
    if (!pre) continue;
    const body =
      element.querySelector(":scope > .lf-markdown-body") ??
      document.createElement("div");
    if (body.className !== "lf-markdown-body") body.className = "lf-markdown-body";
    const source = dataBody(element);
    if (
      body.hasAttribute("data-lf-prepaint") &&
      body.getAttribute("data-lf-source-words") === source
    ) {
      const markup = renderMarkdown(source, pageLinks, false);
      if (body.innerHTML !== markup) body.innerHTML = markup;
    } else paintMarkdown(body, source, pageLinks);
    body.removeAttribute("data-lf-prepaint");
    body.removeAttribute("data-lf-gen");
    pre.replaceWith(body);
  }
}
