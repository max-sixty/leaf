/*
 * Shiki's public entry, cut to Leaf's declared languages and the JavaScript regex
 * engine. The Oniguruma engine loads WebAssembly, which the page CSP will not fetch.
 */
import {
  createBundledHighlighter,
  createCssVariablesTheme,
  createSingletonShorthands,
  getTokenStyleObject,
  stringifyTokenStyle,
} from "@shikijs/core";
import { createJavaScriptRegexEngine } from "@shikijs/engine-javascript";

export const bundledLanguages = {/* LEAF_PIERRE_LANGUAGES */};

export const createHighlighter = createBundledHighlighter({
  langs: bundledLanguages,
  themes: {},
  engine: createJavaScriptRegexEngine,
});
export const { codeToHtml } = createSingletonShorthands(createHighlighter);
export {
  createCssVariablesTheme,
  createJavaScriptRegexEngine,
  getTokenStyleObject,
  stringifyTokenStyle,
};
export const createOnigurumaEngine = () => {
  throw new Error("Leaf's Pierre bundle includes the JavaScript regex engine only");
};
