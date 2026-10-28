/* Code as tokens: the one tokenizing engine, its grammars, and the nodes and lines a
   caller builds from what it returns. It loads in any document (portable-api.js): it
   reads nothing Leaf composes into a page, and a failure is the caller's to report, as a
   widget reports one through `failSoft`. The page's own code blocks and the language a
   path means are syntax.js's, since both read Leaf's registry. */
import { syntaxLanguages } from "./syntax-languages.js";

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
