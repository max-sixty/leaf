/* What names an element: the one reading of the name the authoring contract gives it.

   A section is named by its heading, a disclosure by its summary, a titled compound
   member by its leading <strong>, and an element whose registry entry declares
   `x-name` by that attribute. Anything else has no name, and the caller decides what
   stands in for one. The words come through the passage reader, so
   generated chrome inside an element names nothing.

   The vocabulary is stated here rather than loaded, so the attribute route is caused
   by this declaration and by nothing a page might have vendored. */

import assert from "node:assert/strict";
import test from "node:test";

import { addressableName } from "/runtime/anchor-resolution.js";
import { registry } from "/runtime/registry.js";

const named = (markup) => {
  document.body.innerHTML = `<main>${markup}</main>`;
  return addressableName(document.querySelector("#it"));
};

test("the contract's titles name their elements", () => {
  assert.equal(
    named('<section id="it"><h2>Plan</h2><p>Body words.</p></section>'),
    "Plan",
  );
  assert.equal(
    named('<details id="it"><summary>Method</summary><p>Steps.</p></details>'),
    "Method",
  );
  // A titled member's comparison chips stand before its title and are not its name.
  assert.equal(
    named(
      '<lf-option id="it"><lf-chip>effort: low</lf-chip><strong>Flag first</strong> Ship dark.</lf-option>',
    ),
    "Flag first",
  );
});

test("an element the contract gives no title has no name", () => {
  assert.equal(named('<p id="it">Some <em>plain</em> words.</p>'), "");
  assert.equal(named('<lf-card id="it">Untitled card words.</lf-card>'), "");
  assert.equal(addressableName(null), "");
});

test("a leading header holds the title, past an eyebrow above it", () => {
  assert.equal(
    named(
      '<lf-workspace id="it"><header><h1>Review</h1></header><p>Body.</p></lf-workspace>',
    ),
    "Review",
  );
  assert.equal(
    named(
      '<section id="it"><header><p class="eyebrow">Stage 2</p><strong>Migration rehearsal</strong></header></section>',
    ),
    "Migration rehearsal",
  );
});

test("words before a title mean it is not one", () => {
  // Inline emphasis in prose is not the paragraph's name.
  assert.equal(named('<p id="it">This is <strong>important</strong> text.</p>'), "");
});

test("the attribute a tag declares with x-name names its element", () => {
  for (const tag of Object.keys(registry)) delete registry[tag];
  Object.assign(registry, {
    "lf-column": { "x-name": "label" },
    // An attribute shown first is not a title unless it is declared as one.
    "lf-metric": { "x-says": { value: "before" } },
  });
  assert.equal(
    named(
      '<lf-column id="it" label="Ready"><lf-card><strong>A</strong></lf-card></lf-column>',
    ),
    "Ready",
  );
  assert.equal(named('<lf-metric id="it" value="312">daily visits</lf-metric>'), "");
  // Without its attribute the element falls back to the contract's other titles.
  assert.equal(named('<lf-column id="it"><h3>Later</h3></lf-column>'), "Later");
  for (const tag of Object.keys(registry)) delete registry[tag];
});

test("generated chrome names nothing, and does not hide the title behind it", () => {
  assert.equal(
    named('<lf-card id="it"><strong class="lf-ui">6 · 🎯</strong>Words.</lf-card>'),
    "",
  );
  assert.equal(
    named(
      '<lf-card id="it"><strong class="lf-ui">6 · 🎯</strong><strong>Real title</strong> Words.</lf-card>',
    ),
    "Real title",
  );
});
