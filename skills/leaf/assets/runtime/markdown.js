// One safe Markdown reading for every runtime and package surface. The parser stays
// lazy because most pages contain no Markdown supplied at runtime; callers can paint
// escaped source immediately and await this only when their own rendering needs it.
import { isCanonicalMediaUrl, scopedMediaUrl } from "./media.js";

export const escapeHtml = (text) =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const escapeAttribute = (text) => escapeHtml(text).replace(/"/g, "&quot;");

let render = (text) => escapeHtml(text);
let ready;

export const renderMarkdown = (text) => render(text);

const WEB_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

function safeUrl(href) {
  if (href.startsWith("#")) return true;
  try {
    return WEB_PROTOCOLS.has(new URL(href, location.href).protocol);
  } catch {
    return false;
  }
}

export function loadMarkdown(onError = null) {
  const attempt = (ready ??= import("/vendor/marked.esm.js").then((module) => {
    const markdown = new module.Marked({
      breaks: true,
      // Runtime-supplied Markdown may describe code containing angle brackets, but it
      // never gets an HTML execution door. Widgets enter through separately validated
      // markup fields.
      renderer: {
        html: (token) => escapeHtml(token.text),
        link(token) {
          if (!safeUrl(token.href)) return this.parser.parseInline(token.tokens);
          if (!isCanonicalMediaUrl(token.href)) return false;
          // Marked can preserve an ordinary page-media link on a normal page, but its
          // root would escape an MCP capability route. Scope only this href and retain
          // the link's authored meaning; image inspection has its own button renderer.
          let link = `<a href="${escapeAttribute(scopedMediaUrl(token.href))}"`;
          if (token.title) link += ` title="${escapeAttribute(token.title)}"`;
          return link + `>${this.parser.parseInline(token.tokens)}</a>`;
        },
        image(token) {
          if (!safeUrl(token.href)) return escapeHtml(token.text);
          if (!isCanonicalMediaUrl(token.href)) return false;
          const source = scopedMediaUrl(token.href);
          const label = token.text || "Image";
          let image = `<button type="button" class="lf-media-open lf-message-media" data-lf-media-url="${escapeAttribute(source)}" aria-label="View ${escapeAttribute(label)}"><img src="${escapeAttribute(source)}" alt="${escapeAttribute(token.text)}"`;
          if (token.title) image += ` title="${escapeAttribute(token.title)}"`;
          return image + "></button>";
        },
      },
    });
    render = (text) => markdown.parse(text);
  }));
  return attempt
    .then(() => true)
    .catch((error) => {
      // A transient resource failure can recover on a later state read. Until then the
      // renderer remains the escaped source, which preserves every supplied word.
      if (ready === attempt) ready = undefined;
      onError?.(error);
      return false;
    });
}
