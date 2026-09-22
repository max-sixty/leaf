// One safe Markdown reading for every runtime and package surface. The parser stays
// lazy because most pages contain no Markdown supplied at runtime; callers can paint
// escaped source immediately and await this only when their own rendering needs it.
import { isCanonicalMediaUrl, scopedMediaUrl } from "./media.js";

const escapeHtml = (text) =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const escapeAttribute = (text) => escapeHtml(text).replace(/"/g, "&quot;");

const escapedSource = (text) => escapeHtml(text);
let render = escapedSource;
let ready;

export const renderMarkdown = (text) => render(text);
// Whether a rendering taken now is the parser's or the escaped source standing in for
// it. A caller that keeps what it painted needs to know which it kept, so the words can
// be given their Markdown once the import lands.
export const markdownReady = () => render !== escapedSource;

const WEB_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

function safeUrl(href) {
  if (href.startsWith("#")) return true;
  try {
    return WEB_PROTOCOLS.has(new URL(href, location.href).protocol);
  } catch {
    return false;
  }
}

// Page media keeps its canonical text in the log, and an MCP capability route needs
// that href scoped to reach the same bytes. Scope only those; every other destination
// stands as the reader wrote it.
const destination = (href) => (isCanonicalMediaUrl(href) ? scopedMediaUrl(href) : href);

export function loadMarkdown(onError = null) {
  const attempt = (ready ??= import("/vendor/marked.esm.js").then((module) => {
    const markdown = new module.Marked({
      breaks: true,
      // Runtime-supplied Markdown may describe code containing angle brackets, but it
      // never gets an HTML execution door. Widgets enter through separately validated
      // markup fields.
      renderer: {
        html: (token) => escapeHtml(token.text),
        // One reading of a destination, shared by the protocol check and the
        // attribute it lands in. Marked hands a renderer the authored text, and an
        // href attribute decodes character references when that markup lands, so
        // handing the destination back to Marked's own renderer would write
        // `javascript&#58;` unescaped and let the document resolve as a script URL
        // what this guard read as a relative path. Every link and image is therefore
        // written here, with the destination escaped into the attribute it was
        // checked as; image inspection has its own button renderer below.
        link(token) {
          if (!safeUrl(token.href)) return this.parser.parseInline(token.tokens);
          let link = `<a href="${escapeAttribute(destination(token.href))}"`;
          if (token.title) link += ` title="${escapeAttribute(token.title)}"`;
          return link + `>${this.parser.parseInline(token.tokens)}</a>`;
        },
        image(token) {
          if (!safeUrl(token.href)) return escapeHtml(token.text);
          const source = destination(token.href);
          if (!isCanonicalMediaUrl(token.href)) {
            let image = `<img src="${escapeAttribute(source)}"`;
            image += ` alt="${escapeAttribute(token.text)}"`;
            if (token.title) image += ` title="${escapeAttribute(token.title)}"`;
            return image + ">";
          }
          const label = token.text || "Image";
          let image = `<button type="button" class="lf-media-open lf-message-media" data-lf-offer="button" data-lf-said data-lf-media-url="${escapeAttribute(source)}" aria-label="View ${escapeAttribute(label)}"><img src="${escapeAttribute(source)}" alt="${escapeAttribute(token.text)}"`;
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
