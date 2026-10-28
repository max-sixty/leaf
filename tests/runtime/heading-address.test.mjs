/* The address a heading's link copies: the outermost authored addressable the heading
   titles, by the rule that names an element after its leading title, else the
   heading's own id. A heading the page gave no address has no link. */

import assert from "node:assert/strict";
import test from "node:test";

import { headingAddress } from "/runtime/heading-links.js";

const addressOf = (markup) => {
  document.body.innerHTML = `<main>${markup}</main>`;
  return headingAddress(document.querySelector("[data-heading]"))?.id ?? null;
};

test("a heading that opens an identified section links to the section", () => {
  assert.equal(addressOf('<section id="s"><h2 data-heading>Title</h2></section>'), "s");
  assert.equal(
    addressOf('<section id="s"><h2 id="h" data-heading>Title</h2></section>'),
    "s",
  );
});

test("an eyebrow and title share the address of what they open", () => {
  assert.equal(
    addressOf(
      '<section id="s"><hgroup id="g"><p>Eyebrow</p><h2 data-heading>Title</h2></hgroup></section>',
    ),
    "s",
  );
  assert.equal(
    addressOf(
      '<div><hgroup id="g"><h2 data-heading>Title</h2></hgroup><p>Words</p></div>',
    ),
    "g",
  );
});

test("a heading inside a section it does not open links to itself", () => {
  assert.equal(
    addressOf(
      '<section id="s"><h2>Section</h2><p>Words</p><h3 id="h" data-heading>Part</h3></section>',
    ),
    "h",
  );
  assert.equal(
    addressOf('<section id="s"><h2>Section</h2><h3 data-heading>Part</h3></section>'),
    null,
  );
});

test("a nested section's heading links to the nested section", () => {
  assert.equal(
    addressOf(
      '<section id="outer"><h2>Outer</h2><section id="inner"><h3 data-heading>Inner</h3></section></section>',
    ),
    "inner",
  );
});

test("a heading with no authored address has no link", () => {
  assert.equal(addressOf("<section><h2 data-heading>Title</h2></section>"), null);
  assert.equal(addressOf('<h2 id="lf-toc-section-1" data-heading>Title</h2>'), null);
});
