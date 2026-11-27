/* The word for an element's kind, as a reader would call it: a paragraph, a table, a
   figure, or the word a widget gives its own kind. It reads the element alone, so
   every surface that names a kind of element says the same word for it. */

const HTML_WORDS: Record<string, string> = {
  input: "control",
  select: "control",
  button: "control",
  p: "paragraph",
  li: "item",
  tr: "row",
  td: "cell",
  th: "cell",
  figure: "figure",
  blockquote: "quote",
  pre: "block",
  section: "section",
  article: "section",
  aside: "aside",
  ul: "list",
  ol: "list",
  dl: "list",
  table: "table",
  details: "note",
  h1: "heading",
  h2: "heading",
  h3: "heading",
  h4: "heading",
  h5: "heading",
  h6: "heading",
};

// A drawing the page holds inline, and each part of it an author gave an id, is a
// figure to the reader, as a diagram's box is its diagram: SVG's element names, `g`,
// `path` and `text`, name nothing the reader sees.
const SVG = "http://www.w3.org/2000/svg";

/** The word for `addressable`'s kind: a widget's own word (`widgetWord`), else the
 * word for its HTML element, a `<pre>` holding a `<code>` being code, else its tag;
 * "" for no element. */
export function addressableWord(addressable: Element | null | undefined) {
  if (!addressable) return "";
  if (addressable.namespaceURI === SVG) return "figure";
  const tag = addressable.tagName.toLowerCase();
  const word = widgetWord(tag, addressable);
  if (word) return word;
  if (tag === "pre")
    return addressable.querySelector(":scope > code") ? "code" : "block";
  return HTML_WORDS[tag] ?? tag;
}

// A widget's word for its kind: the `aria-roledescription` its element carries, which
// its author writes in markup or the widget that owns it writes as it builds, as a
// playground does on each preset; else what its module answers from `lfWord()` where
// `element` is drawn and has the method; else its tag without the `lf-` prefix.
export function widgetWord(tag: string, element: Element | null = null) {
  return (
    element?.getAttribute("aria-roledescription")?.trim() ||
    element?.lfWord?.() ||
    (tag.startsWith("lf-") ? tag.slice(3) : "")
  );
}
