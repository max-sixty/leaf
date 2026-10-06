/* This module owns code tokenization and highlighting. */
import { runtime } from "./context.js";
import { syntaxLanguages } from "./syntax-languages.js";

const registry = runtime.registry;

// Ordinary code and Pierre's diffs share one Shiki engine and theme. Colors
// follow the page's scheme; generated spans never enter the authored source.
// The engine loads only for code, and each grammar only when it is requested.
let tokenizerReady;
const tokenizer = () => (tokenizerReady ??= import("/vendor/syntax.esm.js"));
const languagesReady = new Map();

// The registry generates the literal import map. A missing language is a bundle
// mismatch, not a reason to silently color a declared language as plain text.
// An absent language prepares only the theme, for a diff of an unknown file type.
export function ensureSyntaxLanguage(lang) {
  if (!lang) return tokenizer();
  if (!languagesReady.has(lang)) {
    const load = syntaxLanguages[lang];
    if (!load)
      throw new Error(`no ${lang} grammar — rebuild syntax from registry.json`);
    languagesReady.set(
      lang,
      Promise.all([tokenizer(), load()]).then(async ([shared, grammar]) => {
        await shared.registerLanguage(lang, grammar.default);
        return shared;
      }),
    );
  }
  return languagesReady.get(lang);
}

// Code as [{text, style}] — a flat run in source order, carrying Shiki's
// themed CSS declarations directly. CSS variables inherit the page's palette.
// A list rather than markup because callers build different DOM from it: plain code
// emits one span per token, while lf-code interleaves the line spans it numbers.
// A declared language is validated by page check
// against the registry's $languages.names.
export async function syntax(source, lang) {
  const shared = await ensureSyntaxLanguage(lang);
  const tokens = await shared.tokenize(source, lang);
  // The vendored tokenizer's output is data entering, so it is checked once, here, and
  // indexed everywhere after: that the tokens partition the source exactly. Three things
  // rest on it — lf-code numbers its lines by counting newlines in them, `hi` and each
  // note's `at` address those numbers, and the anchor pass reads the spans as the text
  // the file holds — and a dropped character slides all three with nothing on screen
  // saying so. Failing here fails the block soft to its plain source, and the console
  // error fails the render gate, which is what puts it in front of whoever can drop the
  // language declaration.
  if (tokens.map((t) => t.text).join("") !== source)
    throw new Error(`the ${lang} tokenizer did not return the source unchanged`);
  return tokens;
}

// Tokens as nodes: one span per style, and the bare text where none applies, so nothing
// lands in the DOM that says nothing. Callers build from here — plain code replacing its
// own children, lf-code appending into the line it is numbering — because a second place
// writing the same span is a second place to forget the attribute.
export const synNodes = (tokens) =>
  tokens.map(({ text, style }) => {
    if (!Object.keys(style).length) return document.createTextNode(text);
    const span = document.createElement("span");
    span.dataset.lfSyn = "";
    for (const [property, value] of Object.entries(style))
      span.style.setProperty(property, value);
    span.textContent = text;
    return span;
  });

// Tokens re-cut so none crosses a newline: one array of {text, style} per line, in source
// order. The tokenizer's runs and a line are two different spans of the same characters,
// and this is where they are reconciled for lf-code, whose lines are what it numbers.
// It tokenizes a whole run and cuts it afterwards rather than colouring a line at a time,
// because a token can span a newline:
// a docstring coloured line by line restarts the tokenizer inside itself and reads its
// second line as code.
export function tokenLines(tokens) {
  const lines = [[]];
  for (const { text, style } of tokens) {
    const parts = text.split("\n");
    parts.forEach((part, i) => {
      if (i) lines.push([]);
      if (part) lines.at(-1).push({ text: part, style });
    });
  }
  return lines;
}

// What a filename says it holds, or undefined where the registry's table has no answer
// and the block stays the colour of its own ink. The only place a language is derived
// rather than declared: a unified diff spans files, so lf-diff has no `language` to read and
// each file's path is the diff's own statement about what it is. Still a declaration —
// the rule that nothing is inferred is about source *text*, which no path is. The table
// is the registry's ($languages), beside the enum it has to agree with, rather than a
// second list here.
export const langForPath = (path) =>
  registry.$languages.paths[
    path.split("/").pop().split(".").slice(1).pop()?.toLowerCase()
  ];

// The page's own code blocks: <pre><code class="language-python">. The class is the
// universal one — what every Markdown renderer emits — so a block Claude wrote anywhere
// else needs no translation to land here. A language outside $languages stays the
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
const languageOf = (code) => {
  const lang = code.className.match(LANGUAGE_CLASS)?.[1];
  return registry.$languages.names.includes(lang) ? lang : undefined;
};
// Blocks whose tokens are on their way. A pass that reaches one again before they land,
// as a message that renders twice in a turn does, would tokenize the same text and
// write the same spans over the ones the first pass wrote. So the pass in flight
// answers for the block as it stands when its tokens land, not as it stood when it
// asked: text or a language that changed meanwhile is tokenized again.
const tokenizing = new WeakSet();
export async function highlightBlocks(root) {
  const blocks = [];
  // The root counts, like every other dressing pass: a revision that rewrote a block's
  // code replaces the one element, and what arrives is the `<code>` itself.
  const found = [...root.querySelectorAll(BLOCK)];
  if (root.matches?.(BLOCK)) found.unshift(root);
  for (const code of found) {
    // A block already tokenized for this language keeps its spans: a live revision
    // that rewrote an ancestor's attribute dresses the ancestor again, and the user
    // may be holding a selection in the block beneath it.
    const lang = languageOf(code);
    if (lang && code.dataset.lfSyntax !== lang && !tokenizing.has(code)) {
      tokenizing.add(code);
      blocks.push(code);
    }
  }
  if (!blocks.length) return;
  for (const code of blocks) {
    let lang = languageOf(code);
    try {
      let tokens;
      while (lang) {
        const source = code.textContent;
        tokens = await syntax(source, lang);
        if (code.textContent === source && languageOf(code) === lang) break;
        lang = languageOf(code);
      }
      if (!lang) continue;
      // Tokens that colour nothing are the text the block already holds.
      if (tokens.some(({ style }) => Object.keys(style).length))
        code.replaceChildren(...synNodes(tokens));
      code.dataset.lfSyntax = lang;
    } catch (err) {
      console.error(
        `leaf: <pre><code class="language-${lang}"> failed to highlight`,
        err,
      );
    } finally {
      tokenizing.delete(code);
    }
  }
}
