/* A file's reading mode in a diff. Prose files usually keep a paragraph on one source
 * line, so a Markdown or plain-text file wraps its rows and any other file scrolls them
 * sideways, unless the page author chose one mode for the whole patch (`overflow`).
 */
/** @param {string} path @param {string | null | undefined} authored */
export const overflowFor = (path, authored) => {
  if (authored === "wrap" || authored === "scroll") return authored;
  if (authored != null) throw new Error(`Unsupported diff overflow: ${authored}`);
  return /\.(?:md|markdown|txt)$/i.test(path) ? "wrap" : "scroll";
};
