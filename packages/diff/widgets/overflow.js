/* A file's reading mode in a diff. Prose files usually keep a paragraph on one source
 * line, so a Markdown or plain-text file wraps its rows and any other file scrolls them
 * sideways, unless the page author chose one mode for the whole patch (`overflow`).
 * The widget draws by it and its first paint (initial/lf-diff.js) counts the rows it
 * wraps, so both import this one rule. The Markdown extensions are those the layer's
 * language table maps to `markdown` (`$languages`), which a runtime test holds this
 * rule to: the classic first-paint script runs before the registry has loaded. */
export const overflowFor = (path, authored) =>
  authored ?? (/\.(?:md|markdown|txt)$/i.test(path) ? "wrap" : "scroll");
