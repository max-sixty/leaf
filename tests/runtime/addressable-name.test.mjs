/* What names an element: the one reading of the name the authoring contract gives it.

   A section is named by its heading, a disclosure by its summary, and a titled compound
   member or a widget by its leading <strong>. Anything else has no name, and the
   caller decides what stands in for one. The words come through the passage reader, so
   generated chrome inside an element names nothing.

   The chrome's label (`addressableLabel`) reads that name first and an element's words
   only where they are its own.

   The words are the ones the author wrote, so the server names an obligation's element
   by the same rule off the document; `tests/name_cases.json` holds both runtimes to
   one set of cases. Each case states its vocabulary rather than loading it, so a
   declared word is caused by that declaration and by nothing a page might have
   vendored. */

import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import {
  addressableLabel,
  addressableName,
  echoCopy,
  leadingTitle,
  titledElement,
} from "/runtime/addressable-names.js";
import { leadingTitle as portableLeadingTitle } from "/runtime/leading-title.js";
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

test("a name drawn elsewhere is a copy of the markup the author wrote", () => {
  declare();
  document.body.innerHTML = `<main><lf-part id="it"><header>
    <strong id="title"><code>README.md</code><span data-lf-gen="1">Δ</span></strong>
    <p><span class="added">+120</span> <span class="removed">−45</span> lines</p>
    </header><article><p>Body.</p></article></lf-part></main>`;
  const part = /** @type {Element} */ (document.getElementById("it"));
  const title = /** @type {Element} */ (leadingTitle(part));
  assert.equal(title, portableLeadingTitle(part));
  const copy = echoCopy(title);
  const shown = document.createElement("span");
  shown.append(...copy);
  // The code type stays, a widget's own words and every id go.
  assert.equal(shown.innerHTML, "<code>README.md</code>");
  assert.equal(addressableName(part), "README.md");
  // Asked again, the copy is the same nodes, so a drawing moves none of them.
  assert.deepEqual(echoCopy(title), copy);
  // After the title, the header's summary, its colours' classes included.
  const header = /** @type {Element} */ (part.querySelector("header"));
  const summary = document.createElement("span");
  summary.append(...echoCopy(header, title));
  assert.equal(summary.querySelector(".added")?.textContent, "+120");
  assert.equal(summary.textContent.replace(/\s+/g, " ").trim(), "+120 −45 lines");
  assert.equal(summary.querySelector("[id]"), null);
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
  // The page's title leads the column; it still names nothing the column holds.
  assert.equal(
    labelled(`<h1>Page title</h1><div id="it">${members}</div>`),
    "Card words",
  );
  // A picture's own name stands in for words it does not have.
  assert.equal(
    labelled('<figure id="it"><svg role="img" aria-label="Visual 0"></svg></figure>'),
    "Visual 0",
  );
  for (const tag of Object.keys(registry)) delete registry[tag];
});

test("a heading titles the outermost element it is the first heading of, short of a name", () => {
  declare();
  document.body.innerHTML = `<main><h1>Plan</h1>
    <lf-ask id="ask"><header><hgroup id="group"><p>Decision 1</p>
      <h2 id="question">Which store?</h2></hgroup></header><p>Two fit.</p></lf-ask>
    <lf-tab id="tab"><strong>First route</strong><h3 id="step">Prepare</h3><p>Words.</p></lf-tab>
    <section id="outer"><lf-ask id="inner"><h2 id="region">Which region?</h2></lf-ask>
    </section>
    <section id="notes-section"><lf-ask><h2 id="store">Which store?</h2></lf-ask>
      <h3 id="notes">Notes</h3><p>Words.</p></section>
    <div id="plan"><div><strong>Task one</strong> words</div>
      <div><strong>Task two</strong> words <lf-ask id="restart">
        <h3 id="restart-question">Restart it?</h3></lf-ask></div></div>
    <div id="more"><details id="details"><summary>More</summary>
      <h4 id="inside">Inside</h4></details></div>
    <section id="kick"><lf-ask><p>Review record</p><h2 id="ship">Ship it?</h2>
      </lf-ask></section>
    <section id="job"><div><span>01</span><h2 id="job-heading">Job</h2></div>
      <p>Its words.</p></section>
    <section id="tools"><p>Developer tools</p><h2 id="inspect">Inspect</h2></section>
    <section id="rollout"><h2 id="rollout-heading">Rollout</h2><p>Plan.</p>
      <lf-ask><h2>Include runners?</h2></lf-ask></section>
    <div id="body"><p>Lede.</p><section id="in"><h2 id="inputs">Inputs</h2></section>
      <section><h2>Outputs</h2></section></div>
    <div><h2>Before</h2><hgroup id="pair"><h2 id="first">First title</h2>
      <h3 id="second">Second</h3></hgroup></div>
  </main>`;
  const titled = (/** @type {string} */ id) =>
    titledElement(/** @type {Element} */ (document.getElementById(id))).id;
  assert.equal(titled("question"), "ask");
  // A tab is named by its leading <strong>, so a heading after it titles only itself.
  assert.equal(titled("step"), "step");
  // A section wrapping a question is titled by the question's heading, its first.
  assert.equal(titled("region"), "outer");
  // A heading after the question titles only itself.
  assert.equal(titled("store"), "notes-section");
  assert.equal(titled("notes"), "notes");
  // Words before a heading stop it titling anything but a section: a task's, a
  // disclosure's summary; a section's eyebrow doesn't, in a wrapper or not.
  assert.equal(titled("restart-question"), "restart");
  assert.equal(titled("inside"), "inside");
  assert.equal(titled("inspect"), "tools");
  assert.equal(titled("job-heading"), "job");
  assert.equal(titled("ship"), "kick");
  // A section takes its first heading past a question of the same rank inside it.
  assert.equal(titled("rollout-heading"), "rollout");
  // A wrapper holding sections of one rank is none's.
  assert.equal(titled("inputs"), "in");
  // Only an hgroup's leading heading titles it.
  assert.equal(titled("first"), "pair");
  assert.equal(titled("second"), "second");
  declare();
});

test("a heading titles what it opens as the page gains and loses headings", () => {
  declare();
  document.body.innerHTML = `<main><h1 id="title">Plan</h1>
    <section id="part"><h2 id="first">First</h2><p id="words">Words.</p></section>
  </main>`;
  const first = /** @type {Element} */ (document.getElementById("first"));
  assert.equal(titledElement(first).id, "part");
  // Words the page gains change no heading's reach.
  document.getElementById("words")?.append(" More words.");
  assert.equal(titledElement(first).id, "part");
  // A heading arriving before it in its section takes the section.
  const earlier = document.createElement("h2");
  earlier.textContent = "Earlier";
  first.before(earlier);
  assert.equal(titledElement(first), first);
  assert.equal(titledElement(earlier).id, "part");
  earlier.remove();
  assert.equal(titledElement(first).id, "part");
  // A second page title stops the first titling the page's column.
  const title = /** @type {Element} */ (document.getElementById("title"));
  const main = /** @type {Element} */ (document.querySelector("main"));
  assert.ok(titledElement(title).contains(main));
  const second = document.createElement("h1");
  second.textContent = "Appendix";
  main.append(second);
  assert.equal(titledElement(title), title);
  // A heading a widget's data draws loses its section to a heading the page puts
  // before it outside the data.
  document.body.innerHTML = `<main><section id="stages">
    <div data-lf-projection="stages" data-lf-datum="k1"><p>Data words.</p>
      <h3 id="drawn">Drawn</h3></div><p>Stage words.</p></section></main>`;
  const drawn = /** @type {Element} */ (document.getElementById("drawn"));
  const section = /** @type {Element} */ (document.getElementById("stages"));
  assert.ok(titledElement(drawn).contains(section));
  const stages = document.createElement("h2");
  stages.textContent = "Stages";
  section.prepend(stages);
  assert.equal(titledElement(drawn), drawn);
});
