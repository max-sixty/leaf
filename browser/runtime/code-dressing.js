/* The page's own code, drawn by the language each `<code>` names
   (syntax-tokens.js, `codeLanguage`): a block coloured by its grammar (syntax.js), a
   formula typeset (formulas.js). One pass, which whatever places markup runs over what
   it placed: the document's dressing (declared-words.js), a message's draw, a Markdown
   body's repaint (markdown.js, `paintMarkdown`) and a widget's own draw
   (module-state.md). */
import { highlightBlocks } from "./syntax.js";
import { typesetFormulas } from "./formulas.js";

/** @param {Document | DocumentFragment | Element} root */
export const dressCode = (root) =>
  Promise.all([highlightBlocks(root), typesetFormulas(root)]).then(() => {});
