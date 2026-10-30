/* A file's reading mode in a diff. Prose files usually keep a paragraph on one source
 * line, so a Markdown or plain-text file wraps its rows and any other file scrolls them
 * sideways, unless the page author chose one mode for the whole patch (`overflow`).
 */
export const overflowFor = (path, authored) =>
  authored ?? (/\.(?:md|markdown|txt)$/i.test(path) ? "wrap" : "scroll");
