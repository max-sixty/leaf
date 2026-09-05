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
 * and how every other page of this site wears its bar (`nav.sitenav` in the site package, and
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
 * page rather than a page of this site — the same line the site package draws about its
 * own rules.
 */

const NOTE = `
  <p>
    <strong>An example of a leaf page.</strong> No agent is behind it: nothing you do
    here leaves your own browser.
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
document.querySelector("main").prepend(note);
