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
// A framed task owns the whole main allocation. Put site context in its existing
// header so its content root and independently scrolling regions remain intact.
const header = main.querySelector(":scope > :only-child > header");
(header ?? main).prepend(note);
