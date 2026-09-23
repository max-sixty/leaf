// One safe Markdown reading for every runtime and package surface. The parser stays
// lazy because most pages contain no Markdown supplied at runtime; callers can paint
// escaped source immediately and await this only when their own rendering needs it.
import { isCanonicalMediaUrl, scopedMediaUrl } from "./media.js";

const escapeHtml = (text) =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

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

// Read the attributes from Marked's inert output. Its renderer owns inline-text
// flattening, entity encoding and URL normalization; the document parser supplies
// the destination that the scheme guard must judge before this markup is published.
const probe = document.createElement("template");
function renderedElement(markup, tag) {
  probe.innerHTML = markup;
  const element = probe.content.firstElementChild;
  return element?.localName === tag ? element : null;
}

export function loadMarkdown(onError = null) {
  const attempt = (ready ??= import("/vendor/marked.esm.js").then((module) => {
    const markdown = new module.Marked({
      breaks: true,
      // Runtime-supplied Markdown may describe code containing angle brackets, but it
      // never gets an HTML execution door. Widgets enter through separately validated
      // markup fields. A line that opens with a tag starts an HTML block, which only
      // ever arrives here as someone showing markup, so it reads as the code block it
      // is: escaped inline, its lines and indentation would collapse into one run.
      renderer: {
        html(token) {
          if (!token.block) return escapeHtml(token.text);
          return this.code({ text: token.text, lang: "html", escaped: false });
        },
        link(token) {
          const markup = module.Renderer.prototype.link.call(this, token);
          const link = renderedElement(markup, "a");
          if (!link) return markup;
          const href = link.getAttribute("href");
          if (!safeUrl(href)) return this.parser.parseInline(token.tokens);
          if (isCanonicalMediaUrl(href))
            link.setAttribute("href", scopedMediaUrl(href));
          return link.outerHTML;
        },
        image(token) {
          const markup = module.Renderer.prototype.image.call(this, token);
          const image = renderedElement(markup, "img");
          if (!image) return markup;
          const href = image.getAttribute("src");
          if (!safeUrl(href)) return escapeHtml(image.alt);
          if (!isCanonicalMediaUrl(href)) return image.outerHTML;
          const source = scopedMediaUrl(href);
          image.setAttribute("src", source);
          const button = document.createElement("button");
          button.type = "button";
          button.className = "lf-media-open lf-message-media";
          button.setAttribute("data-lf-offer", "button");
          button.setAttribute("data-lf-said", "");
          button.setAttribute("data-lf-media-url", source);
          button.setAttribute("aria-label", `View ${image.alt || "Image"}`);
          button.append(image);
          return button.outerHTML;
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
