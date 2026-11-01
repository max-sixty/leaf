/* The page's own code blocks, coloured by syntax-tokens.js, and the language a file path
   means: the parts of highlighting that read Leaf's registry and report to the page. */
import { runtime } from "./context.js";
import { reportPageError } from "./layer-client.js";
import { syntaxLanguageNames } from "./syntax-languages.js";
import { synNodes, syntax } from "./syntax-tokens.js";

const registry = runtime.registry;

// What a filename says it holds, or undefined where the registry's table has no answer
// and the block stays the colour of its own ink. The only place a language is derived
// rather than declared: a unified diff spans files and a file editor names one, so neither
// has a `language` to read, and a file's path is its own statement about what it is.
// lf-diff colours by this, and the file editor chooses its Markdown mode by it, so a
// filename means the same language in both. Still a declaration —
// the rule that nothing is inferred is about source *text*, which no path is. The table
// is the registry's ($languages), beside the enum it has to agree with, rather than a
// second list here.
/** @param {string} path */
export const langForPath = (path) => {
  const filename = path.slice(path.lastIndexOf("/") + 1);
  const dot = filename.lastIndexOf(".");
  return dot < 0
    ? undefined
    : registry.$languages.paths[filename.slice(dot + 1).toLowerCase()];
};

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
// A block's declared language where the registry colours it.
/** @param {Element} code */
const languageOf = (code) => {
  const lang = code.getAttribute("class")?.match(LANGUAGE_CLASS)?.[1];
  if (!lang) return undefined;
  return Object.hasOwn(syntaxLanguageNames, lang)
    ? syntaxLanguageNames[lang]
    : undefined;
};
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
    const lang = languageOf(code);
    if (lang && code.getAttribute("data-lf-syntax") !== lang && !tokenizing.has(code)) {
      tokenizing.add(code);
      blocks.push(code);
    }
  }
  if (!blocks.length) return;
  for (const code of blocks) {
    let lang = languageOf(code);
    try {
      while (lang) {
        const source = code.textContent;
        const tokens = await syntax(source, lang);
        if (code.textContent !== source || languageOf(code) !== lang) {
          lang = languageOf(code);
          continue;
        }
        // Tokens that colour nothing are the text the block already holds.
        if (tokens.some(({ style }) => Object.keys(style).length))
          code.replaceChildren(...synNodes(tokens));
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
