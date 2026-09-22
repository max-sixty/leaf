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

// A Markdown destination is attribute source text: Marked hands it over with its
// character references undecoded, because its own emission writes them where the HTML
// parser decodes them. Leaf writes the attribute itself, so it takes that decoding
// here, in the one place a destination is read. `escapeAttribute` puts this reading
// back unchanged, so `javascript&#58;` is refused rather than resolved and an ordinary
// `&amp;` still reaches the query it names.
const probe = document.createElement("template");
const readHref = (href) => {
  probe.innerHTML = `<i data-href="${href.replace(/"/g, "&quot;")}"></i>`;
  return probe.content.firstElementChild.dataset.href;
};

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
        // attribute it lands in. Handing the destination back to Marked's own
        // renderer would write `javascript&#58;` unescaped and let the document
        // resolve as a script URL what this guard read as a relative path. Every link
        // and image is therefore written here, from the one reading `readHref` takes
        // and escaped back into the attribute it was checked as; image inspection has
        // its own button renderer below.
        link(token) {
          const href = readHref(token.href);
          if (!safeUrl(href)) return this.parser.parseInline(token.tokens);
          let link = `<a href="${escapeAttribute(destination(href))}"`;
          if (token.title) link += ` title="${escapeAttribute(token.title)}"`;
          return link + `>${this.parser.parseInline(token.tokens)}</a>`;
        },
        image(token) {
          const href = readHref(token.href);
          if (!safeUrl(href)) return escapeHtml(token.text);
          const source = escapeAttribute(destination(href));
          const title = token.title ? ` title="${escapeAttribute(token.title)}"` : "";
          const image = `<img src="${source}" alt="${escapeAttribute(token.text)}"${title}>`;
          if (!isCanonicalMediaUrl(href)) return image;
          const label = escapeAttribute(token.text || "Image");
          return (
            `<button type="button" class="lf-media-open lf-message-media"` +
            ` data-lf-offer="button" data-lf-said data-lf-media-url="${source}"` +
            ` aria-label="View ${label}">${image}</button>`
          );
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
