/* What names an element: the one reading of the name the authoring contract gives it.

   A section is named by its heading, a disclosure by its summary, a titled compound
   member by its leading <strong>, and an element whose registry entry declares
   `x-name` by that attribute. Anything else has no name, and the caller decides what
   stands in for one. The words come through the passage reader, so
   generated chrome inside an element names nothing.

   The chrome's label (`addressableLabel`) reads that name first and an element's words
   only where they are its own.

   The words are the ones the author wrote, so the server names a Question's element
   by the same rule off the document; `tests/name_cases.json` holds both runtimes to
   one set of cases. Each case states its vocabulary rather than loading it, so the
   attribute route is caused by that declaration and by nothing a page might have
   vendored. */

import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import { addressableLabel, addressableName } from "/runtime/addressable-names.js";
import { renderSaid } from "/runtime/declared-words.js";
import { registry } from "/runtime/registry.js";

// The cases the server's `gesture_words.element_name` answers too.
const CASES = JSON.parse(
  readFileSync(new URL("../name_cases.json", import.meta.url), "utf8"),
);

const declare = (vocabulary = {}) => {
  for (const tag of Object.keys(registry)) delete registry[tag];
  Object.assign(registry, vocabulary);
};

const named = (markup) => {
  document.body.innerHTML = `<main>${markup}</main>`;
  renderSaid(document.body);
  return addressableName(document.querySelector("#it"));
};

for (const { id, registry: vocabulary, markup, name } of CASES)
  test(`name: ${id}`, () => {
    declare(vocabulary);
    assert.equal(named(markup), name);
    declare();
  });

test("no element has no name", () => {
  assert.equal(addressableName(null), "");
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
      '<lf-ask id="it"><h4>How should it page?</h4><lf-options><lf-option><small class="tag">last week: 0</small><strong>Require three</strong> probes.</lf-option></lf-options></lf-ask>',
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
