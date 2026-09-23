// One safe Markdown reading for every runtime and package surface. The parser stays
// lazy because most pages contain no Markdown supplied at runtime; callers can paint
// escaped source immediately and await this only when their own rendering needs it.
import { isCanonicalMediaUrl, scopedMediaUrl } from "./media.js";
import { elementsDeclaring, declarationFor } from "./registry.js";

const escapeHtml = (text) =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const escapedSource = (text) => escapeHtml(text);
let render = escapedSource;
let renderInline = escapedSource;
let ready;

export const renderMarkdown = (text) => render(text);
export const renderInlineMarkdown = (text, breaks = true) => renderInline(text, breaks);
// A hard break is visible separation in passage readings, too. Text-node based
// capture cannot otherwise see a <br> between two words.
export function inlineMarkdownFragment(text, breaks = true) {
  const parsed = document.createElement("template");
  parsed.innerHTML = renderInlineMarkdown(text, breaks);
  for (const br of parsed.content.querySelectorAll("br"))
    br.after(document.createTextNode("\n"));
  return parsed.content;
}

// Registry text formatting belongs to the layer, so a package declaration cannot
// make file-side passages read words the browser leaves as raw Markdown.
export async function prepareDeclaredInlineMarkdown(scope) {
  const elements = elementsDeclaring(scope, "x-text-format");
  if (declarationFor(scope, "x-text-format")) elements.unshift(scope);
  if (!elements.length) return;
  let failure;
  if (!(await loadMarkdown((error) => (failure = error))))
    throw new Error(
      `leaf: inline Markdown renderer failed to load: ${failure?.message ?? failure}`,
    );
  for (const element of elements) {
    for (const node of [...element.childNodes]) {
      if (node.nodeType !== Node.TEXT_NODE || !node.data.trim()) continue;
      const parsed = inlineMarkdownFragment(node.data, false);
      if (!parsed.firstElementChild && parsed.textContent === node.data) continue;
      const words = document.createElement("span");
      words.className = "lf-markdown-words";
      words.dataset.lfMarkdownWords = "";
      words.dataset.lfSourceWords = node.data;
      words.append(parsed);
      node.replaceWith(words);
    }
  }
}
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
      // This dialect has no HTML: a tag is text wherever it appears. Runtime-
      // supplied Markdown may describe code containing angle brackets, but it never gets
      // an HTML execution door; widgets enter through separately validated markup fields.
      // Declining the tokens, rather than escaping what they matched, keeps a block of
      // tags as text with its lines. Marked's paragraph rule still starts a new
      // paragraph at an unindented block tag, which splits the block without losing a
      // line; a fence is what keeps markup whole.
      tokenizer: { html: () => undefined, tag: () => undefined },
      renderer: {
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
    renderInline = (text, breaks) => markdown.parseInline(text, { breaks });
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
