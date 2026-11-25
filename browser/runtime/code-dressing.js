/* The page's code, drawn by the language each `<code>` names
   (syntax-tokens.js, `codeLanguage`): a block coloured by its grammar (syntax.js), a
   formula typeset (formulas.js), and every block's lines boxed so their wrapped rows
   hang from each line's indent (code-lines.js). The lines are boxed first, so the
   tokens land in their lines.

   Code is dressed wherever it arrives, whoever drew it: the served document, a
   revision, a message, a widget's own drawing (`watchCode`). A widget writes
   `<pre><code class="language-…">` and calls nothing, and the dressing it starts is
   drawing under way on the `<code>` (lib/pending-task.js), which the page's readiness
   counts. The pass is idempotent, so the passes that wait on their own dressing, the
   document's (declared-words.js) and a message's draw, run it over what they placed as
   well. */
import { watchArrivals } from "./arrivals.js";
import { boxLines } from "./code-lines.js";
import { highlightBlocks } from "./syntax.js";
import { typesetFormulas } from "./formulas.js";
import { PendingTaskEvent } from "./lib/pending-task.js";

/** @param {Document | DocumentFragment | Element} root */
export const dressCode = (root) => {
  boxLines(root);
  return Promise.all([highlightBlocks(root), typesetFormulas(root)]).then(() => {});
};

// A block, its `<code>` or a formula, dressed as it arrives and again as its language
// changes. A block already coloured for its language keeps its colouring (syntax.js),
// so a widget that rewrites a block's words draws a new `<code>`.
export function watchCode() {
  watchArrivals("pre, pre > code, code.language-math", ["class"], {
    arriveBatch: (codes) => {
      for (const code of codes)
        code.dispatchEvent(new PendingTaskEvent(dressCode(code)));
    },
    leave: () => {},
  });
}
