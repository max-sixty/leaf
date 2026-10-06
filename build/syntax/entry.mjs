/** Shared Shiki engine, Leaf token theme, and source-preserving token reading.
 *
 * The runtime loads registry-selected grammar modules before asking either this
 * tokenizer or Pierre to render. Both use this singleton and the same theme;
 * grammar loaders are registered here so Pierre consumes those same modules.
 */
import {
  createHighlighterCore,
  createCssVariablesTheme,
  getTokenStyleObject,
  normalizeTheme,
  stringifyTokenStyle,
} from "@shikijs/core";
import { createJavaScriptRegexEngine } from "@shikijs/engine-javascript";

export const themeName = "leaf";

export const leafTheme = {
  name: themeName,
  type: "light",
  colors: {
    "editor.foreground": "var(--code-ink)",
    "editor.background": "var(--pre-bg)",
  },
  tokenColors: [
    {
      scope: ["comment", "string.quoted.docstring"],
      settings: { foreground: "var(--syn-comment)", fontStyle: "italic" },
    },
    {
      scope: ["keyword", "storage", "constant.language", "constant.other.option"],
      settings: { foreground: "var(--syn-keyword)" },
    },
    {
      scope: [
        "string",
        "constant.character",
        "markup.inline",
        "markup.fenced_code",
        "markup.underline.link",
      ],
      settings: { foreground: "var(--syn-string)" },
    },
    { scope: ["constant.numeric"], settings: { foreground: "var(--syn-number)" } },
    {
      scope: [
        "entity.name.command",
        "entity.name.function",
        "support.function",
        "entity.name.section",
        "markup.heading",
      ],
      settings: { foreground: "var(--syn-name)" },
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
      settings: { foreground: "var(--syn-type)" },
    },
    { scope: ["markup.inserted"], settings: { foreground: "var(--ok-ink)" } },
    { scope: ["markup.deleted"], settings: { foreground: "var(--danger-ink)" } },
    { scope: ["keyword.operator"], settings: { foreground: "var(--code-ink)" } },
  ],
};

export const foreground = leafTheme.colors["editor.foreground"];

export const bundledLanguages = {};
let highlighter;

/** Pierre's public factory shares the engine already used by ordinary code. */
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

export async function registerLanguage(lang, grammar) {
  bundledLanguages[lang] = async () => ({ default: grammar });
  const instance = await createHighlighter();
  await instance.loadLanguage(grammar);
}

/** Offsets preserve original line endings even when Shiki normalizes its lines. */
export async function tokenize(source, lang) {
  const instance = await createHighlighter({ langs: [lang] });
  const lines = instance.codeToTokensBase(source, { lang, theme: themeName });
  const tokens = [];
  const append = (text, style) => {
    if (!text) return;
    if (tokens.length && JSON.stringify(tokens.at(-1).style) === JSON.stringify(style))
      tokens.at(-1).text += text;
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
  return tokens;
}

export async function codeToHtml(source, options) {
  const instance = await createHighlighter({ langs: [options.lang] });
  return instance.codeToHtml(source, options);
}

export const createOnigurumaEngine = () => {
  throw new Error("Leaf uses the JavaScript regex engine");
};

export {
  createCssVariablesTheme,
  createJavaScriptRegexEngine,
  getTokenStyleObject,
  normalizeTheme,
  stringifyTokenStyle,
};
