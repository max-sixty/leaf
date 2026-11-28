/* The page's own code, drawn by the language each `<code>` names
   (syntax-tokens.js, `codeLanguage`): a block coloured by its grammar (syntax.js), a
   formula typeset (formulas.js), and every block's lines boxed so their wrapped rows
   hang from each line's indent (code-lines.js). One pass, which whatever places markup
   runs over what it placed: the document's dressing (records/declared-words.js), a message's
   draw and a widget's own draw (module-widgets.md, "Drawing"), such as a draft's repaint of its
   body. The lines are boxed first, so the tokens land in their lines. */
import { boxLines } from "./code-lines.js";
import { highlightBlocks } from "./syntax.js";
import { typesetFormulas } from "./formulas.js";

export const dressCode = (root: Document | DocumentFragment | Element) => {
  boxLines(root);
  return Promise.all([highlightBlocks(root), typesetFormulas(root)]).then(() => {});
};
