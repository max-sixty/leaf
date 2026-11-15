/* The page's own code blocks, coloured by syntax-tokens.js, with failures reported
   to the page. Portable language-paths.js owns a filename's language reading. */
import { reportPageError } from "./layer-client.js";
import { syntaxLanguageNames } from "./syntax-languages.js";
import { synNodes, syntax } from "./syntax-tokens.js";

// The page's own code blocks: <pre><code class="language-python">. The class is the
// universal one — what every Markdown renderer emits — so a block Claude wrote anywhere
// else needs no translation to land here. Shiki's names and aliases resolve to the
// registry's grammar names at build time. A language outside that set stays the
// colour of its ink, as the same block would in any page that colours nothing: plain
// HTML claims no vocabulary. lf-code declares `language` instead, because a custom
// element's vocabulary is the registry's to state, and `page check` holds it there.
//
// The spans change no text: a <span> is no text block, so the anchor pass reads exactly
// the run of characters it read before. That is what lets this run over the document
// without the file's reading of the same page needing to know it happened.
const LANGUAGE_CLASS = /(?:^|\s)language-([\w+.#-]+)(?=\s|$)/;
const BLOCK = "pre > code[class]";
// The language a block declares that Leaf can colour, or none: one the registry
// colours, in a block that holds text and inline annotations.
//
// Tokens are cut at the text nodes' boundaries, so authored elements keep their
// identity, attributes and listeners. A <br> supplies a line break absent from
// textContent; leave those blocks alone rather than tokenize a different source.
/** @param {Element} code */
export const colourableAs = (code) => {
  const lang = code.getAttribute("class")?.match(LANGUAGE_CLASS)?.[1];
  if (!lang || !Object.hasOwn(syntaxLanguageNames, lang)) return undefined;
  if (code.querySelector("br")) return undefined;
  return syntaxLanguageNames[lang];
};
// The language Leaf colours a block in, or none, read again when its tokens land: the
// one it can colour, where the block wears the reading face. The render gate reads the
// two together to name a block that declares a language and goes uncoloured.
//
// The token palette is the face's, drawn for the face's code ground (reading.css), so a
// block that doesn't wear it, as on a page that takes no theme, keeps the colours its
// page gives it. A page that supplies its own token palette turns off the reading face,
// as for its other personally themed content. Only a block in the document has a face
// to read: one not yet placed is a surface Leaf is building, such as a message, and
// all of those wear the face.
/** @param {Element} code */
export const colouredAs = (code) => {
  if (
    code.isConnected &&
    getComputedStyle(code).getPropertyValue("--lf-reading-face").trim() !== "1"
  )
    return undefined;
  return colourableAs(code);
};
// Partition the whole-source token stream over text nodes and our earlier token
// spans. Authored elements are traversed, never replaced; a token crossing one is
// cut into pieces with the same style. Equal pieces keep their nodes on a repaint.
/** @param {Element} code
 * @param {Parameters<typeof synNodes>[0]} tokens */
function colourText(code, tokens) {
  /** @type {(Text | Element)[]} */
  const nodes = [];
  /** @param {Node} parent */
  const collect = (parent) => {
    for (const node of parent.childNodes) {
      if (
        node instanceof Text ||
        (node instanceof Element && node.matches("[data-lf-syn]"))
      )
        nodes.push(node);
      else collect(node);
    }
  };
  collect(code);
  let index = 0;
  let offset = 0;
  for (const node of nodes) {
    let remaining = node.textContent.length;
    /** @type {Parameters<typeof synNodes>[0][number][]} */
    const pieces = [];
    while (remaining) {
      const token = /** @type {Parameters<typeof synNodes>[0][number]} */ (
        tokens[index]
      );
      const length = Math.min(remaining, token.text.length - offset);
      if (length)
        pieces.push({
          text: token.text.slice(offset, offset + length),
          style: token.style,
        });
      remaining -= length;
      offset += length;
      if (offset === token.text.length) {
        index++;
        offset = 0;
      }
    }
    const painted = synNodes(pieces);
    if (painted.length === 1 && painted.every((piece) => node.isEqualNode(piece)))
      continue;
    if (painted.length) node.replaceWith(...painted);
  }
}
// Blocks whose tokens are on their way. A pass that reaches one again before they land,
// as a message that renders twice in a turn does, would tokenize the same text and
// write the same spans over the ones the first pass wrote. So the pass in flight
// answers for the block as it stands when its tokens land, not as it stood when it
// asked: text or a language that changed meanwhile is tokenized again.
/** @type {WeakSet<Element>} */
const tokenizing = new WeakSet();
/** @param {Document | DocumentFragment | Element} root */
export async function highlightBlocks(root) {
  const blocks = [];
  // The root counts, like every other dressing pass: a revision that rewrote a block's
  // code replaces the one element, and what arrives is the `<code>` itself.
  const found = [...root.querySelectorAll(BLOCK)];
  if (root instanceof Element && root.matches(BLOCK)) found.unshift(root);
  for (const code of found) {
    // A block already tokenized for this language keeps its spans: a live revision
    // that rewrote an ancestor's attribute dresses the ancestor again, and the user
    // may be holding a selection in the block beneath it.
    const lang = colouredAs(code);
    if (lang && code.getAttribute("data-lf-syntax") !== lang && !tokenizing.has(code)) {
      tokenizing.add(code);
      blocks.push(code);
    }
  }
  if (!blocks.length) return;
  for (const code of blocks) {
    let lang = colouredAs(code);
    try {
      while (lang) {
        const source = code.textContent;
        const { tokens } = await syntax(source, lang);
        if (code.textContent !== source || colouredAs(code) !== lang) {
          lang = colouredAs(code);
          continue;
        }
        colourText(code, tokens);
        code.setAttribute("data-lf-syntax", lang);
        break;
      }
    } catch (err) {
      reportPageError(err, `<pre><code class="language-${lang}"> failed to highlight`);
    } finally {
      tokenizing.delete(code);
    }
  }
}
