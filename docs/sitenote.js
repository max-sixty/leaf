/* The website's navigation label, injected ahead of Leaf's runtime on examples.
 *
 * The document remains the authored example, while this `.lf-ui` subtree stays outside
 * its anchorable reading. The status banner owns the no-agent warning; this label gives
 * a visitor context and a route back without repeating it. Paper drops the label because
 * a printout is the example itself, not a page of the product site.
 */

const NOTE = `
  <p>
    <strong>An example of a Leaf page.</strong> Try its controls in a private,
    temporary copy for this browser.
  </p>
  <p class="sitenote-nav">
    <a href="/">What leaf is</a> ·
    <a href="/examples/">The other examples</a> ·
    <a href="/#install">Install leaf</a>
  </p>
`;

const note = Object.assign(document.createElement("div"), {
  className: "lf-ui sitenote",
  innerHTML: NOTE,
});
const main = document.querySelector("main");
// A framed task owns the whole main allocation. Put site context in its header so its
// content root and independently scrolling regions remain intact — and give one to a
// framed task that authored none rather than leaving the note beside it. A second
// element under `main` is precisely what tells the runtime the workspace is not the
// page's root, so the note dropped there costs the example the allocation it is being
// shown for: the page arrives in ordinary document flow with no bounded regions at all.
const framed = main.querySelector(":scope > lf-workspace:only-child");
let header = framed?.querySelector(":scope > header") ?? null;
if (framed && !header) {
  // Marked as the layer's own, like the note it carries: this header is the site
  // speaking, and the example's anchorable reading is unchanged by it.
  header = Object.assign(document.createElement("header"), { className: "lf-ui" });
  framed.prepend(header);
}
(header ?? main).prepend(note);
