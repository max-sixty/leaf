/* A file's reading mode in a diff. Prose files usually keep a paragraph on one source
 * line, so a file the page's language table calls Markdown (`langForPath`), or a
 * plain-text file, wraps its rows and any other file scrolls them sideways, unless the
 * page author chose one mode for the whole patch (`overflow`).
 */
import { langForPath } from "/runtime/portable-api.js";

/** @param {string} path @param {string | null | undefined} authored */
export const overflowFor = (path, authored) => {
  if (authored === "wrap" || authored === "scroll") return authored;
  if (authored != null) throw new Error(`Unsupported diff overflow: ${authored}`);
  return langForPath(path) === "markdown" || /\.txt$/i.test(path) ? "wrap" : "scroll";
};
