/* File-language declarations. A plain host uses the shipped vocabulary; a Leaf
   page installs its composed table, including extension overrides and removals. */
import { syntaxLanguagePaths } from "./syntax-languages.js";

let paths = syntaxLanguagePaths;
/** @param {Record<string, string>} declarations */
export const installLanguagePaths = (declarations) => {
  paths = declarations;
};

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
  return dot < 0 ? undefined : paths[filename.slice(dot + 1).toLowerCase()];
};
