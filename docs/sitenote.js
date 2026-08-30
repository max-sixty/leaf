/* What a published example is, said on the example itself.
 *
 * A page here is the file in the tree, whole: the reader is looking at what an agent
 * would hand them, so nothing on it introduces it. That is right for the page and wrong
 * for the visitor, who arrives on a URL somebody sent them and meets a document with
 * live chrome around it and no statement of what either one is. The banner has the one
 * seat that speaks for whoever is behind the page, and it is a single line that gives up
 * width first (`docs/session.js`) — enough to say where a comment goes, not enough to say
 * what this whole thing is or how to get one.
 *
 * So the site puts its own label at the head of the page: what this is, where the words
 * go, and the way back to the site that published it — which an example otherwise hasn't
 * got at all, being a directory of its own with no link out of it.
 *
 * It stands inside <main>, at the document's own column and under a rule, which is where
 * and how every other page of this site wears its bar (`nav.sitenav` in docs/site.css, and
 * the reasoning there: a band spanning wider than the words under it is a second column to
 * read). Inside the column it also needs no width of its own, so a theme that moves the
 * measure moves the label with it.
 *
 * It is the site's voice and not the page's, so it wears `.lf-ui`: the anchor pass reads
 * that class as "not the document" and skips the subtree, which is what keeps this out of
 * a captured quote, and the chrome's sans face says the same thing to the eye. The file
 * the build published holds none of it, and the page's own reading skips it, so the two
 * readings agree about what the page says — the standing requirement on anything a module
 * adds to a version (the repo's "the file's reading never claims more than the page's").
 *
 * Paper drops it. A printout is a copy of the page, and a copy of a leaf page is that
 * page rather than a page of this site — the same line `docs/site.css` draws about its
 * own rules.
 */

const NOTE = `
  <p>
    <strong>An example of a leaf page.</strong> No agent is behind it: nothing you do
    here leaves your own browser.
  </p>
  <p class="sitenote-nav">
    <a href="/index.html">What leaf is</a> ·
    <a href="/examples.html">The other examples</a> ·
    <a href="/examples.html#run">Run one for real</a>
  </p>
`;

// Every colour is a token, so the label follows both palettes and every later change to
// them — `docs/site.css`'s claim about the theme, made again here because a page under
// /examples links the theme and not that file.
//
// The page's own top padding comes down by about what the label takes, so the title sits
// where it sat rather than a screenful lower.
//
// Colour is stated on the children, since `.lf-ui` states one too and the label wears
// that class: a declaration on the root is the chrome's own rule restated at its weight,
// where one on a child outranks it however the two stylesheets land.
const CSS = `
  body > main { padding-top: 32px; }
  .sitenote { margin: 0 0 36px; padding-bottom: 12px;
              border-bottom: 1px solid var(--rule); }
  .sitenote p { margin: 0; color: var(--ink-2); }
  .sitenote strong { color: var(--ink); font-weight: 600; }
  .sitenote p.sitenote-nav { margin-top: 4px; color: var(--muted-2); }
  .sitenote a { color: var(--accent); text-decoration: none; }
  .sitenote a:hover { text-decoration: underline; }
  @media print { .sitenote { display: none; } }
`;

document.head.append(
  Object.assign(document.createElement("style"), { textContent: CSS }),
);

const note = Object.assign(document.createElement("div"), {
  className: "lf-ui sitenote",
  innerHTML: NOTE,
});
document.querySelector("main").prepend(note);
