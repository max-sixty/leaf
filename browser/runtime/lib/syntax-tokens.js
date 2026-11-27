// Compiled from syntax-tokens.ts by build/typescript.mjs; edit that file.
/* Code as tokens: the one tokenizing engine, its grammars, the language a block names,
   and the nodes and lines a caller builds from what it returns. It reads nothing Leaf
   composes into a page, and a failure is the caller's to report, as a widget reports
   one through `failSoft` (failure.js). Leaf colours the page's own blocks itself
   (`dressCode` in the package API), and `langForPath` there names the language a file
   path means, by the page's composed `$languages` table. */
import { syntaxLanguageNames, syntaxLanguages } from "./syntax-languages.js";

// The language a block of code names, by HTML's own convention for it: a class prefixed
// `language-` on the `<code>` (WHATWG, "The code element"), which every Markdown
// renderer writes, so a block written anywhere else needs no translation here. A widget
// whose body is data reads the `<code>` in its `<pre>`, and the class on the widget
// itself where it has none, as a document bound to a source has no `<pre>`. A grammar
// answers to its name and to each alias Shiki gives it (`syntaxLanguageNames`), and the
// grammar's name is returned. Any other name is null: it colours nothing, and the
// block stays the colour of its ink, as it would on a page that colours nothing, where
// a block naming no language (undefined) may take a default, such as a Markdown
// preview's source; `page check` names such a class (`markup_checks/markup.py`,
// `language_advice`), unless it is `math`, a formula's LaTeX, which readings/formulas.js
// typesets.
const LANGUAGE_CLASS = /(?:^|\s)language-(\S+)/;
const classLanguage = (element) => {
  const name = element?.getAttribute("class")?.match(LANGUAGE_CLASS)?.[1];
  if (!name) return undefined;
  return Object.hasOwn(syntaxLanguageNames, name) ? syntaxLanguageNames[name] : null;
};
/** @param block a `<code>`, or a widget whose body is a `<pre>` */
export const codeLanguage = (block) => {
  const named = classLanguage(block.querySelector(":scope > pre > code"));
  return named === undefined ? classLanguage(block) : named;
};

// Ordinary code and Pierre's diffs share one Shiki engine and theme. Colors
// follow the page's scheme; generated spans never enter the authored source.
// The engine loads only for code, and each grammar only when it is requested.
let tokenizerReady;
const tokenizer = () => (tokenizerReady ??= import("/vendor/syntax.esm.js"));
const languagesReady = new Map();

// Loads the engine and `lang`'s grammar, once, so a caller can load one ahead of the
// call that colours in it. The registry generates the literal import map. A missing
// language is a bundle mismatch, not a reason to silently color a declared language as
// plain text. An absent language prepares only the theme, for a diff of an unknown file
// type.
export function ensureSyntaxLanguage(lang) {
  if (!lang) return tokenizer();
  let ready = languagesReady.get(lang);
  if (!ready) {
    const load = syntaxLanguages[lang];
    if (!load)
      throw new Error(`no ${lang} grammar — rebuild syntax from registry.json`);
    ready = Promise.all([tokenizer(), load()]).then(async ([shared, grammar]) => {
      await shared.registerLanguage(lang, grammar.default);
      return shared;
    });
    languagesReady.set(lang, ready);
  }
  return ready;
}

// Code as `{tokens, state}`: `tokens` is [{text, style}], a flat run in source order
// carrying Shiki's themed CSS declarations directly, whose CSS variables inherit the
// page's palette. A list rather than markup because callers build different DOM from
// it: plain code emits one span per token, while lf-code interleaves the line spans it
// numbers. `lang` is a grammar's name, as `codeLanguage` and `langForPath` return one.
//
// `state` is the grammar state the source's last line ends in, and passed back as
// `state` it continues another source from there, so a long text coloured a part at a
// time, each part from the state the part before it ended in, is coloured as the whole
// text would be. Begun afresh, a part starting inside a docstring read its rest as code.
export async function syntax(source, lang, state) {
  return (await syntaxNow(lang)).tokenize(source, state);
}

// `syntax` for `lang` as a synchronous call, once its grammar has loaded, beside each
// declaration a token's style can hold (`declarations`, `[property, value]` pairs), for
// a caller that colours text as it lays it out and names each declaration once, as the
// file editor's highlighter does a line at a time.
export async function syntaxNow(lang) {
  const shared = await ensureSyntaxLanguage(lang);
  const tokenize = await shared.tokenizer(lang);
  return {
    declarations: shared.tokenDeclarations(),
    tokenize(source, state) {
      const tokenized = tokenize(source, state);
      // The vendored tokenizer's output is data entering, so it is checked once, here,
      // and indexed everywhere after: that the tokens partition the source exactly.
      // Three things rest on it — lf-code numbers its lines by counting newlines in
      // them, `hi` and each note's `at` address those numbers, and the anchor pass reads
      // the spans as the text the file holds — and a dropped character slides all three
      // with nothing on screen saying so. Failing here fails the block soft to its plain
      // source, and the console error fails the render gate, which is what puts it in
      // front of whoever can drop the language declaration.
      if (tokenized.tokens.map((t) => t.text).join("") !== source)
        throw new Error(`the ${lang} tokenizer did not return the source unchanged`);
      return tokenized;
    },
  };
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
  let line = [];
  const lines = [line];
  for (const { text, style } of tokens) {
    const parts = text.split("\n");
    parts.forEach((part, i) => {
      if (i) {
        line = [];
        lines.push(line);
      }
      if (part) line.push({ text: part, style });
    });
  }
  return lines;
}
