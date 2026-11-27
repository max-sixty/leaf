// Compiled from data-body.ts by build/typescript.mjs; edit that file.
/* A data widget's body: the `<pre>` its content model requires, as a module reads it.

   It is the `<pre>`'s text, never the element's own `textContent`. The two differ once
   the element holds a child: an HTML formatter is free to put the `<pre>` on its own
   line, and the newline and indent before it are the element's text too. Line one is
   load-bearing in every notation here, so that indent is not untidiness downstream: a
   diff's file header, a tree's root and a diagram's source type stop parsing, and a
   walkthrough's `hi` ranges and note anchors all point one line off. */

/** The body's text exactly, for a notation whose whitespace is content, such as a diff
 * or exact Markdown source. Throws where the element has no body. */
export const dataBody = (el) => {
  const body = el.querySelector(":scope > pre");
  if (!body) throw new Error(`<${el.localName}> has no data body`);
  return body.textContent;
};

/** The body's text as a module reads its lines: leading blank lines and trailing
 * whitespace are the `<pre>`'s layout, not lines. */
export const bodyText = (el) => dataBody(el).replace(/^\n+/, "").trimEnd();
