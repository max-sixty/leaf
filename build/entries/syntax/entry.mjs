/** Leaf's syntax module, token theme, and source-preserving token reading.
 *
 * The runtime loads registry-selected grammar modules before asking either this
 * tokenizer or Pierre to render. Grammar loaders are registered here so Pierre
 * consumes those same modules and Leaf's token theme.
 */
import {
  createHighlighterCore,
  createCssVariablesTheme,
  getTokenStyleObject,
  normalizeTheme,
  stringifyTokenStyle,
  tokenizeWithTheme,
} from "@shikijs/core";
import { createJavaScriptRegexEngine } from "@shikijs/engine-javascript";

export const themeName = "leaf";

/** @satisfies {import("@shikijs/core").ThemeRegistration} */
export const leafTheme = {
  name: themeName,
  type: "light",
  colors: {
    "editor.foreground": "var(--lf-code-ink)",
    "editor.background": "var(--lf-pre-bg)",
  },
  tokenColors: [
    {
      scope: ["comment", "string.quoted.docstring"],
      settings: { foreground: "var(--lf-syn-comment)", fontStyle: "italic" },
    },
    {
      scope: ["keyword", "storage", "constant.language", "constant.other.option"],
      settings: { foreground: "var(--lf-syn-keyword)" },
    },
    {
      scope: [
        "string",
        "constant.character",
        "markup.inline",
        "markup.fenced_code",
        "markup.underline.link",
      ],
      settings: { foreground: "var(--lf-syn-string)" },
    },
    { scope: ["constant.numeric"], settings: { foreground: "var(--lf-syn-number)" } },
    {
      scope: [
        "entity.name.command",
        "entity.name.function",
        "support.function",
        "entity.name.section",
        "markup.heading",
      ],
      settings: { foreground: "var(--lf-syn-name)" },
    },
    {
      scope: [
        "variable",
        "entity.name.type",
        "entity.name.class",
        "support.type",
        "entity.name.tag",
        "entity.other.attribute-name",
        "entity.other.inherited-class",
        "entity.name.selector",
      ],
      settings: { foreground: "var(--lf-syn-type)" },
    },
    { scope: ["markup.inserted"], settings: { foreground: "var(--lf-ok-ink)" } },
    { scope: ["markup.deleted"], settings: { foreground: "var(--lf-danger-ink)" } },
    { scope: ["keyword.operator"], settings: { foreground: "var(--lf-code-ink)" } },
    // A heading and strong words are bold, emphasis italic and a link's address
    // underlined, as the rendered text would show them.
    { scope: ["markup.heading", "markup.bold"], settings: { fontStyle: "bold" } },
    { scope: ["markup.italic"], settings: { fontStyle: "italic" } },
    { scope: ["markup.underline.link"], settings: { fontStyle: "underline" } },
  ],
};

export const foreground = leafTheme.colors["editor.foreground"];

/** @type {Record<string, () => Promise<{default: import("@shikijs/core").LanguageRegistration[]}>>} */
export const bundledLanguages = {};
/** @type {ReturnType<typeof createHighlighterCore> | undefined} */
let highlighter;

/** Ordinary code blocks share one highlighter and its loaded grammars. */
/** @param {{langs?: (string | import("@shikijs/core").LanguageInput)[], themes?: (string | import("@shikijs/core").ThemeInput)[]}} [options] */
export async function createHighlighter({ langs = [], themes = [] } = {}) {
  const instance = await (highlighter ??= createHighlighterCore({
    engine: createJavaScriptRegexEngine(),
    langs: [],
    themes: [leafTheme],
  }));
  for (const lang of langs) {
    if (typeof lang !== "string") await instance.loadLanguage(lang);
    else if (
      !["text", "plain", "plaintext", "ansi"].includes(lang) &&
      !instance.getLoadedLanguages().includes(lang)
    ) {
      const loader = bundledLanguages[lang];
      if (!loader) throw new Error(`Leaf has not loaded the ${lang} grammar`);
      await instance.loadLanguage((await loader()).default);
    }
  }
  for (const theme of themes) {
    if (typeof theme !== "string") await instance.loadTheme(theme);
    else if (theme !== themeName) throw new Error(`Leaf has no ${theme} token theme`);
  }
  return instance;
}

/** @param {string} lang @param {import("@shikijs/core").LanguageRegistration[]} grammar */
export async function registerLanguage(lang, grammar) {
  bundledLanguages[lang] = async () => ({ default: grammar });
  const instance = await createHighlighter();
  await instance.loadLanguage(grammar);
}

const maxLineLength = 20000;

/** Offsets preserve original line endings even when Shiki normalizes its lines. Returns
 * the tokens and the grammar state their last line ends in, which a later call takes as
 * `state` to continue from it: a text tokenized a part at a time, each part from the
 * state the one before it ended in, is coloured as the whole text would be.
 *
 * A line shorter than `maxLineLength` is coloured to its end however long it takes, and
 * a longer one, such as minified code, stays in plain ink. The main thread's time is
 * bounded by length rather than by Shiki's default of 500 ms a line, because a time
 * limit depends on the machine's load: a grammar's first line pays for compiling the
 * rules it reaches, which on a loaded machine runs past 500 ms and leaves the tail of a
 * short line uncoloured. The maintainer chose the length bound over tokenizing in a
 * worker. The cap is VS Code's; a line just under it takes nearly a second unloaded. */
/** @param {string} source @param {string} lang @param {import("@shikijs/core").GrammarState} [state] */
export async function tokenize(source, lang, state) {
  return (await tokenizer(lang))(source, state);
}

/** `tokenize` for `lang` as a synchronous call, once its grammar and the theme have
 * loaded, for a caller that colours text as it lays it out, a line at a time. */
/** @param {string} lang */
export async function tokenizer(lang) {
  const instance = await createHighlighter({ langs: [lang] });
  /** @param {string} source @param {import("@shikijs/core").GrammarState} [state] */
  return (source, state) => tokenized(instance, source, lang, state);
}

/** Each declaration a token's style can hold, as `tokenize` writes it, once: each colour
 * Leaf's theme names, and each font style. A token's style holds one colour and the
 * font styles of every rule that matches it, as a comment's italic joins the colour
 * of a keyword inside it, so a caller that styles tokens by name, as an editor's
 * highlighter does, names these and gives a token the names its style holds. */
/** @returns {[string, string][]} */
export const tokenDeclarations = () => {
  /** @type {Map<string, [string, string]>} */
  const declarations = new Map();
  /** @param {Record<string, string>} style */
  const add = (style) => {
    for (const [property, value] of Object.entries(style))
      declarations.set(`${property}: ${value}`, [property, value]);
  };
  for (const { settings } of leafTheme.tokenColors)
    if ("foreground" in settings && settings.foreground !== foreground)
      add({ color: settings.foreground });
  // Shiki's font styles are bits: italic, bold, underline and strikethrough.
  for (let fontStyle = 1; fontStyle < 16; fontStyle++)
    add(
      getTokenStyleObject(
        /** @type {Parameters<typeof getTokenStyleObject>[0]} */ ({ fontStyle }),
      ),
    );
  return [...declarations.values()];
};

/** The grammar each state was read in. Shiki compiles a grammar that embeds others
 * lazily, as Markdown does each fence's language, again whenever one of them loads, and
 * a state read in the old grammar fails in the new one ("Not supported!"). So a text
 * continued from a state stays in the grammar it began in, and a text begun afresh takes
 * the language's current grammar, with every language loaded by then.
 * @type {WeakMap<import("@shikijs/core").GrammarState, import("@shikijs/core").Grammar>} */
const grammarOf = new WeakMap();

/** @param {Awaited<ReturnType<typeof createHighlighter>>} instance @param {string} source
 * @param {string} lang @param {import("@shikijs/core").GrammarState} [state] */
function tokenized(instance, source, lang, state) {
  const grammar = (state && grammarOf.get(state)) ?? instance.getLanguage(lang);
  const { theme, colorMap } = instance.setTheme(themeName);
  const lines = tokenizeWithTheme(source, grammar, theme, colorMap, {
    tokenizeTimeLimit: 0,
    tokenizeMaxLineLength: maxLineLength,
    ...(state && { grammarState: state }),
  });
  /** @type {{text: string, style: import("@shikijs/core").TokenStyles}[]} */
  const tokens = [];
  /** @param {string} text @param {import("@shikijs/core").TokenStyles} style */
  const append = (text, style) => {
    if (!text) return;
    const previous = tokens.at(-1);
    if (previous && JSON.stringify(previous.style) === JSON.stringify(style))
      previous.text += text;
    else tokens.push({ text, style });
  };
  let cursor = 0;
  for (const line of lines)
    for (const token of line) {
      if (token.offset > cursor) append(source.slice(cursor, token.offset), {});
      const style = getTokenStyleObject(token);
      if (style.color === foreground) delete style.color;
      append(token.content, style);
      cursor = token.offset + token.content.length;
    }
  if (cursor < source.length) append(source.slice(cursor), {});
  const next = instance.getLastGrammarState(lines);
  if (next) grammarOf.set(next, grammar);
  return { tokens, state: next };
}

/** @param {string} source @param {import("@shikijs/core").CodeToHastOptions<string, string>} options */
export async function codeToHtml(source, options) {
  const instance = await createHighlighter({ langs: [options.lang] });
  return instance.codeToHtml(source, options);
}

export const createOnigurumaEngine = () => {
  throw new Error("Leaf uses the JavaScript regex engine");
};

export {
  createCssVariablesTheme,
  createHighlighterCore,
  createJavaScriptRegexEngine,
  getTokenStyleObject,
  normalizeTheme,
  stringifyTokenStyle,
};
