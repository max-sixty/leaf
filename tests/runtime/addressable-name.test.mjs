/* What names an element: the one reading of the name the authoring contract gives it.

   A section is named by its heading, a disclosure by its summary, a titled compound
   member by its leading <strong>, and an element whose registry entry declares
   `x-name` by that attribute. Anything else has no name, and the caller decides what
   stands in for one. The words come through the passage reader, so
   generated chrome inside an element names nothing.

   The chrome's label (`addressableLabel`) reads that name first and an element's words
   only where they are its own.

   The vocabulary is stated here rather than loaded, so the attribute route is caused
   by this declaration and by nothing a page might have vendored. */

import assert from "node:assert/strict";
import test from "node:test";

import { addressableLabel, addressableName } from "/runtime/anchor-resolution.js";
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
    named('<div id="it"><header><h1>Review</h1></header><p>Body.</p></div>'),
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

test("a title group names itself and its owner by the heading alone", () => {
  assert.equal(
    named(
      '<hgroup id="it"><p class="eyebrow">Stage 2</p><h1>Review</h1><p>Subtitle.</p></hgroup>',
    ),
    "Review",
  );
  assert.equal(
    named(
      '<section id="it"><hgroup><p class="eyebrow">Stage 2</p><h2>Migration</h2></hgroup><p>Body.</p></section>',
    ),
    "Migration",
  );
  assert.equal(
    named(
      '<section id="it"><header><hgroup><p class="eyebrow">Stage 2</p><h2>Migration</h2></hgroup></header></section>',
    ),
    "Migration",
  );
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

const labelled = (markup) => {
  document.body.innerHTML = `<main>${markup}</main>`;
  return addressableLabel(document.querySelector("#it"));
};

test("the chrome names an element by its name before its words", () => {
  // A question is its heading, not its heading run into its options and their chips.
  assert.equal(
    labelled(
      '<lf-ask id="it"><h4>How should it page?</h4><lf-options><lf-option><lf-chip>last week: 0</lf-chip><strong>Require three</strong> probes.</lf-option></lf-options></lf-ask>',
    ),
    "How should it page?",
  );
  assert.equal(
    labelled(
      '<figure id="it"><img alt=""><figcaption>Pages by hour</figcaption></figure>',
    ),
    "Pages by hour",
  );
  assert.equal(
    labelled('<div id="it" aria-label="Latency"><p>12 ms</p></div>'),
    "Latency",
  );
});

test("an element whose words are its own is named by them, cut short", () => {
  assert.equal(
    labelled('<p id="it">Some <em>plain</em> words.</p>'),
    "Some plain words.",
  );
  const label = labelled(`<li id="it">${"word ".repeat(40)}</li>`);
  assert.ok(label.length <= 60 && label.endsWith("…"), label);
});

test("an element whose words are its members' takes the nearest enclosing name", () => {
  // Options have no title of their own; the question holding them names them.
  assert.equal(
    labelled(
      '<lf-ask><h4>Which rollout?</h4><lf-options id="it"><lf-option><strong>Now</strong></lf-option></lf-options></lf-ask>',
    ),
    "Which rollout?",
  );
  assert.equal(
    labelled('<section><h3>Export lag</h3><div id="it"><svg></svg></div></section>'),
    "Export lag",
  );
  assert.equal(addressableLabel(null), "");
});

test("past every name, plain markup is its words and a widget is its word", () => {
  // The column is not a name for what it holds. A registered widget then says its
  // word, which the caller has; plain markup has none worth saying, so its words.
  for (const tag of Object.keys(registry)) delete registry[tag];
  Object.assign(registry, { "lf-board": {} });
  const members =
    "<lf-column><lf-card><strong>Card</strong> words</lf-card></lf-column>";
  assert.equal(labelled(`<lf-board id="it">${members}</lf-board>`), "");
  assert.equal(labelled(`<div id="it">${members}</div>`), "Card words");
  // A picture's own name stands in for words it does not have.
  assert.equal(
    labelled('<figure id="it"><svg role="img" aria-label="Visual 0"></svg></figure>'),
    "Visual 0",
  );
  for (const tag of Object.keys(registry)) delete registry[tag];
});
