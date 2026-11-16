/* The page's own formulas: LaTeX in a `<code class="language-math">`, typeset by Temml
   as the MathML the browser draws itself. A `<code>` among words is an inline formula
   and the `<code>` of a `<pre>` a display one, as Markdown's math writes them (GitHub's
   ```math fence, remark-math's `$…$`), so a page, a Markdown body and a thread message
   write a formula the same way, with the class syntax-tokens.js reads a block's
   language from. Without Leaf the source shows as code.

   The source stays the formula's words. The typeset `<math>` stands in a shadow root on
   a span holding the source, and a root no registry entry declares is opaque to the
   page's reading, whose host reads by its light children (passages.js), so the browser
   reads a formula as its LaTeX exactly as the file does, with no fence: a quote may run
   across a formula in a sentence, and it names the formula by its source, which is
   what its author can find. The shadow root is also what keeps Temml's rules for
   `<math>` off any MathML the page writes itself. A comment on a formula alone points at
   it whole, by the id of its `<pre>` or of the block holding it.

   Temml loads only on a page that shows a formula. Its sheet stands in each formula's
   root, but its font face in the document, where Chromium reads a face from, beside the
   rules that keep a formula's `<code>` and `<pre>` from drawing code's face round it, in
   lf-base as a dependency's defaults are (base-layer.js), so the page's own CSS
   outranks them. A source Temml refuses keeps showing as written, and the refusal goes
   to the page's log, where its agent reads it (`reportPageError`). */
import { reportPageError } from "./layer-client.js";
import { inBaseLayer } from "./base-layer.js";
import { DATA_BODY } from "./syntax.js";

const FORMULA = "code.language-math";
const HOST = "data-lf-formula";

// A typeset formula's `<code>`, and a display formula's `<pre>`, only wrap its source, so
// they draw nothing of their own: a formula takes the size and ink of the words around
// it rather than code's face, a display formula stands in no code block's box, and one
// too wide for the column scrolls in its own box.
const WRAPPING = `
code:has(> [${HOST}]) {
  font: inherit;
  color: inherit;
  background: none;
  border: 0;
  padding: 0;
}
pre:has(> code > [${HOST}]) {
  font: inherit;
  color: inherit;
  background: none;
  border: 0;
  padding: 0;
  white-space: normal;
  overflow-x: auto;
}
pre > code > [${HOST}] {
  display: block;
}`;

/** @type {Promise<{renderer: typeof import("/vendor/temml.esm.js").default, sheet: CSSStyleSheet}> | undefined} */
let temmlReady;
const temml = () =>
  (temmlReady ??= import("/vendor/temml.esm.js").then(
    ({ default: renderer, styles }) => {
      const sheet = new CSSStyleSheet();
      sheet.replaceSync(styles);
      const faces = [...sheet.cssRules]
        .filter((rule) => rule instanceof window.CSSFontFaceRule)
        .map((rule) => rule.cssText);
      const page = new CSSStyleSheet();
      page.replaceSync(inBaseLayer([...faces, WRAPPING].join("\n")));
      document.adoptedStyleSheets = [...document.adoptedStyleSheets, page];
      return { renderer, sheet };
    },
  ));

/** @type {WeakSet<Element>} */
const typeset = new WeakSet();
// A formula is current while the host it was typeset into is all it holds: a live
// revision that rewrites its source replaces that, and the pass typesets it again.
/** @param {Element} code */
const current = (code) =>
  code.childNodes.length === 1 && typeset.has(/** @type {Element} */ (code.firstChild));

/** @param {Document | DocumentFragment | Element} root */
export async function typesetFormulas(root) {
  // The root counts, as in every dressing pass: a revision that rewrote one formula
  // brings the `<code>` itself.
  const found = [...root.querySelectorAll(FORMULA)];
  if (root instanceof Element && root.matches(FORMULA)) found.unshift(root);
  // A widget whose body is data draws its own `<pre>` (syntax.js, `DATA_BODY`).
  const formulas = found.filter(
    (code) => !current(code) && !code.matches(`${DATA_BODY} > code`),
  );
  if (!formulas.length) return;
  const { renderer, sheet } = await temml();
  for (const code of formulas) {
    if (current(code)) continue;
    // Temml renders into an element, which a shadow root isn't.
    const into = document.createElement("span");
    try {
      renderer.render(code.textContent ?? "", into, {
        displayMode: code.parentElement?.localName === "pre",
        throwOnError: true,
      });
    } catch (err) {
      // A refusal of the source is the author's to fix, and its message, which quotes
      // the source, is the whole of what they need.
      reportPageError(
        err instanceof Error && err.name === "ParseError" ? err.message.trim() : err,
        `<code class="language-math"> failed to typeset`,
      );
      continue;
    }
    const host = document.createElement("span");
    host.setAttribute(HOST, "");
    const stage = host.attachShadow({ mode: "open" });
    stage.adoptedStyleSheets = [sheet];
    stage.append(...into.childNodes);
    host.append(...code.childNodes);
    code.append(host);
    typeset.add(host);
  }
}
