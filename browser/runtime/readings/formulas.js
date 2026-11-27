// Compiled from formulas.ts by build/typescript.mjs; edit that file.
/* The page's own formulas: LaTeX in a `<code class="language-math">`, typeset by Temml
   as the MathML the browser draws itself. A `<code>` among words is an inline formula,
   which wraps where TeX would break it, and the `<code>` alone in a `<pre>` a display
   one, as Markdown's math writes them (GitHub's ```math fence, remark-math's `$…$`), so
   a page writes a formula the way Markdown renders one, and a ```math fence in a
   Markdown body or message is a display formula. Without Leaf the source shows as code.

   The source stays the formula's words. The typeset `<math>` stands in a shadow root on
   a span holding the source, and a root no registry entry declares is opaque to the
   page's reading, whose host reads by its light children (passages.js), so the browser
   reads a formula as its LaTeX exactly as the file does, with no fence: a quote may run
   across a formula in a sentence, and it names the formula by its source, which is
   what its author can find. A selection inside one takes all of it
   (dom/native-selection.js, `pageRange`), and its range stands at the host's edges, so it
   is drawn where the formula is (passages.js, `rangeOf`). The shadow root also keeps
   Temml's rules for `<math>` off any MathML the page writes itself.

   Temml loads only on a page that shows a formula. Its sheet stands in each formula's
   root, but its font face in the document, where Chromium reads a face from, beside the
   rules that keep a formula's `<code>`, which wears `data-lf-formula`, and a display
   formula's `<pre>` from drawing code's face round it, in lf-base as a dependency's
   defaults are (base/base-layer.js), so the page's own CSS outranks them. A display
   formula keeps a code block's Copy, which copies its LaTeX. A source Temml refuses keeps
   showing as written, and the refusal goes to the page's log, where its agent reads it
   (`reportPageError`). */
import { reportPageError } from "../transport/layer-client.js";
import { inBaseLayer } from "../base/base-layer.js";
import { keeps } from "../lib/keeps.js";
import { PAGE_PAINT_ATTRIBUTE } from "../base/page-paint.js";
import { DATA_BODY } from "./syntax.js";

const FORMULA = "code.language-math";
const PAINT = PAGE_PAINT_ATTRIBUTE.formula;

// A typeset formula's `<code>`, and a display formula's `<pre>`, only wrap its source, so
// they draw nothing of their own: a formula takes the size and ink of the words around
// it rather than code's face, and a display formula stands in no code block's frame,
// keeping the block's room and scrolling in it where it is too wide for the column. A
// formula can't wrap, so the block is contained: it asks what holds it for no width,
// and a wide formula scrolls rather than widening a flex item or a grid track.
const WRAPPING = `
code[${PAINT}] {
  font: inherit;
  color: inherit;
  background: none;
  border: 0;
  padding: 0;
}
pre:has(> code[${PAINT}="display"]) {
  font: inherit;
  color: inherit;
  background: none;
  border-color: transparent;
  white-space: normal;
  overflow-x: auto;
  contain: inline-size;
}
code[${PAINT}="display"],
code[${PAINT}="display"] > * {
  display: block;
}`;

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

// The source each host was typeset from. A formula is current while its host is all
// it holds, holds that source still, and was set in the mode its place asks for: a live
// revision that rewrites the source replaces the host or its words, one that adds words
// beside a display formula makes it inline, and the pass typesets it again.
const typeset = new WeakMap();
const current = (code) =>
  code.childNodes.length === 1 &&
  typeset.get(code.firstChild) === code.textContent &&
  code.getAttribute(PAINT) === (displayed(code) ? "display" : "inline");

// A formula's words, out of the host an earlier pass typeset them into.
const words = (code) =>
  [...code.childNodes].flatMap((node) =>
    typeset.has(node) ? [...node.childNodes] : [node],
  );

// A display formula is the whole of its `<pre>`; a `<code>` among other words in one
// is a formula in a line of them.
const displayed = (code) =>
  code.parentElement?.localName === "pre" &&
  [...code.parentElement.childNodes].every(
    (node) => node === code || (node instanceof Text && !node.data.trim()),
  );

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
  let loaded;
  try {
    loaded = await temml();
  } catch (err) {
    reportPageError(err, "Temml failed to load, so formulas show their LaTeX");
    return;
  }
  const { renderer, sheet } = loaded;
  for (const code of formulas) {
    if (current(code)) continue;
    const display = displayed(code);
    // Temml renders into an element, which a shadow root isn't.
    const into = document.createElement("span");
    try {
      renderer.render(code.textContent, into, {
        displayMode: display,
        wrap: "tex",
        throwOnError: true,
      });
    } catch (err) {
      // A refusal of the source is the author's to fix, and its message, which quotes
      // the source, is the whole of what they need.
      reportPageError(
        err instanceof Error && err.name === "ParseError" ? err.message.trim() : err,
        "A formula failed to typeset",
      );
      if (code.hasAttribute(PAINT)) {
        code.replaceChildren(...words(code));
        keeps(code, PAINT, null);
      }
      continue;
    }
    const host = document.createElement("span");
    const stage = host.attachShadow({ mode: "open" });
    stage.adoptedStyleSheets = [sheet];
    stage.append(...into.childNodes);
    host.append(...words(code));
    code.replaceChildren(host);
    typeset.set(host, host.textContent);
    keeps(code, PAINT, display ? "display" : "inline");
  }
}
