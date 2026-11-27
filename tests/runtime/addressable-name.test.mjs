/* What names an element: the one reading of the name the authoring contract gives it.

   A section or article is named by the heading it opens with, a disclosure by its
   summary, and a registered widget that takes a `label` by that attribute. Anything else, a bold line
   in prose included, has no name, and the caller decides what stands in for one. The
   words come through the passage reader, so generated chrome inside an element names
   nothing.

   The chrome's label (`addressableLabel`) reads that name first and an element's words
   only where they are its own.

   The words are the ones the author wrote, so the server names an obligation's element
   by the same rule off the document; `tests/name_cases.json` holds both runtimes to
   one set of cases. Each case states its vocabulary rather than loading it, so the
   attribute route is caused by that declaration and by nothing a page might have
   vendored. */

import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import {
  addressableLabel,
  addressableName,
  sectionLabel,
  titledElement,
  titlingHeading,
} from "/runtime/readings/addressable-names.js";
import { registry } from "/runtime/state/registry.js";

// The cases the server's `passages.element_name` answers too.
const CASES = JSON.parse(
  readFileSync(new URL("../name_cases.json", import.meta.url), "utf8"),
);

const declare = (vocabulary = {}) => {
  for (const tag of Object.keys(registry)) delete registry[tag];
  Object.assign(registry, vocabulary);
};

const named = (markup) => {
  document.body.innerHTML = `<main>${markup}</main>`;
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
    named(
      '<section id="it"><h2>Title<span class="lf-ui"> · 3 open</span></h2></section>',
    ),
    "Title",
  );
  assert.equal(
    named(
      '<section id="it"><strong class="lf-ui">6 · 🎯</strong><h2>Real title</h2></section>',
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
      '<section id="it"><h4>How should it page?</h4><lf-options><lf-option label="Require three"><small class="lf-tag">last week: 0</small>probes.</lf-option></lf-options></section>',
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

test("a caption or label names its element without a gloss's explanation", () => {
  // A popover's words stand apart until shown, so they name nothing.
  const gloss = '<lf-gloss>p99<span popover="hint">the slowest 1%</span></lf-gloss>';
  const figure = `<figure id="it"><img alt=""><figcaption>${gloss} by hour</figcaption></figure>`;
  assert.equal(labelled(figure), "p99 by hour");
  assert.equal(
    labelled(`<label for="it">${gloss} budget</label><input id="it">`),
    "p99 budget",
  );
});

test("a drawing's part is a figure, named by its aria-label", () => {
  // SVG's element names, such as `g`, mean nothing to the reader.
  document.body.innerHTML =
    '<main><figure id="fig"><svg viewBox="0 0 10 10"><g id="it" aria-label="Bar for K"><path d="M0 0L5 0"/></g></svg><figcaption>Sensitivity</figcaption></figure></main>';
  assert.equal(sectionLabel(document.querySelector("#it")), "figure · Bar for K");
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
      '<section><h4>Which rollout?</h4><lf-options id="it"><lf-option label="Now"></lf-option></lf-options></section>',
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
  const members = "<lf-column><lf-card>Card words</lf-card></lf-column>";
  assert.equal(labelled(`<lf-board id="it">${members}</lf-board>`), "");
  assert.equal(labelled(`<div id="it">${members}</div>`), "Card words");
  // The page's title leads the column; it still names nothing the column holds.
  assert.equal(
    labelled(`<h1>Page title</h1><div id="it">${members}</div>`),
    "Card words",
  );
  for (const tag of Object.keys(registry)) delete registry[tag];
});

test("a heading titles the section or article it opens, and otherwise itself", () => {
  declare({ "lf-tab": {} });
  document.body.innerHTML = `<main><h1 id="title">Plan</h1>
    <section id="costs"><h2 id="costs-heading">Costs</h2><p>Words.</p>
      <h3 id="sub">Sub-heading</h3></section>
    <article id="notes"><hgroup><p>Stage 2</p><h2 id="notes-heading">Notes</h2></hgroup>
      </article>
    <section id="tools"><p>Developer tools</p><h2 id="inspect">Inspect</h2></section>
    <div id="wrapper"><h2 id="wrapped">Wrapped</h2></div>
    <aside id="aside"><h2 id="aside-heading">Aside</h2></aside>
    <lf-tab id="tab" label="First route"><h3 id="step">Prepare</h3></lf-tab>
    <details id="more"><summary>More</summary><h4 id="inside">Inside</h4></details>
    <div><hgroup id="pair"><h2 id="first">First title</h2><p>Subtitle</p></hgroup></div>
    <section id="outer"><section id="inner"><h2 id="inner-heading">Inner</h2></section>
      </section>
    <section id="chrome"><hgroup><h2 class="lf-ui" id="drawn">Drawn</h2>
      <h2 id="authored">Authored</h2></hgroup></section>
  </main>`;
  const titled = (/** @type {string} */ id) =>
    titledElement(/** @type {Element} */ (document.getElementById(id))).id;
  assert.equal(titled("costs-heading"), "costs");
  assert.equal(titled("notes-heading"), "notes");
  // A heading after other content titles only itself, in a section or anywhere else.
  assert.equal(titled("sub"), "sub");
  assert.equal(titled("inspect"), "inspect");
  assert.equal(titled("wrapped"), "wrapped");
  assert.equal(titled("aside-heading"), "aside-heading");
  assert.equal(titled("step"), "step");
  assert.equal(titled("inside"), "inside");
  assert.equal(titled("title"), "title");
  // An hgroup is its heading's, and a section only the one it opens.
  assert.equal(titled("first"), "pair");
  assert.equal(titled("inner-heading"), "inner");
  // Chrome in an hgroup titles nothing, and leaves the authored heading its section.
  assert.equal(titled("authored"), "chrome");
  declare();
});

test("a heading inside a widget titles only itself", () => {
  // A widget's name is its `label`, so no heading it leads with titles it.
  declare({ "lf-card": {} });
  document.body.innerHTML = `<main><h2>Earlier</h2>
    <lf-card id="card"><header><h3 id="ship">Ship</h3></header><p>Words.</p></lf-card>
  </main>`;
  const ship = /** @type {Element} */ (document.getElementById("ship"));
  const card = /** @type {Element} */ (document.getElementById("card"));
  assert.equal(titledElement(ship), ship);
  assert.equal(titlingHeading(card), null);
  declare();
});

test("a heading put first in a section takes it from the one it displaces", () => {
  declare();
  document.body.innerHTML = `<main><section id="part"><h2 id="first">First</h2>
    <p>Words.</p></section></main>`;
  const first = /** @type {Element} */ (document.getElementById("first"));
  assert.equal(titledElement(first).id, "part");
  const earlier = document.createElement("h2");
  earlier.textContent = "Earlier";
  first.before(earlier);
  assert.equal(titledElement(first), first);
  assert.equal(titledElement(earlier).id, "part");
  earlier.remove();
  assert.equal(titledElement(first).id, "part");
});
