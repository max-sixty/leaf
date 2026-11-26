import "/runtime/stage-integration.js";
/* Where a stored quote stands when the page doesn't show its words once
   (`resolveAnchor`): on its section, as a fallback, or nowhere where the anchor names
   none. An agent's quote carries no context, so words its section shows twice stand
   on the section too, even where one copy fills a passage cell, which an empty side
   would confirm. */

import assert from "node:assert/strict";
import test from "node:test";

import { resolveAnchor } from "/runtime/readings/anchor-resolution.js";
import { registry } from "/runtime/state/registry.js";

/** @param {string} markup @param {string} generation */
const page = (markup, generation) => {
  Object.assign(registry, { $layer: { generation } });
  document.body.innerHTML = `<main>${markup}</main>`;
};

test("words their section no longer shows stand on the section", () => {
  page('<p id="s">The cutoff moved.</p>', "quote-fallback-gone");
  const section = document.getElementById("s");
  const placed = resolveAnchor({ section: "s", quote: "The retry budget" });
  assert.equal(placed?.kind, "element");
  assert.equal(placed.element, section);
  assert.equal(placed.exact, false);
  assert.equal(placed.status, "fallback");
  assert.equal(resolveAnchor({ section: null, quote: "The retry budget" }), null);
  assert.equal(resolveAnchor({ section: "gone", quote: "The retry budget" }), null);
});

test("words a section shows once stand on them, whatever the anchor left out", () => {
  page('<p id="s">The cutoff moved.</p>', "quote-fallback-once");
  const placed = resolveAnchor({ section: "s", quote: "cutoff" });
  assert.equal(placed?.kind, "passage");
  assert.equal(placed.exact, true);
});

test("an agent's quote of words its section shows twice names neither copy", () => {
  page(
    '<div id="s"><span contenteditable="true">MARK</span> then MARK again</div>',
    "quote-fallback-twice",
  );
  const agents = resolveAnchor({ section: "s", quote: "MARK" });
  assert.equal(agents?.kind, "element");
  assert.equal(agents.status, "fallback");
  // A selection's empty sides say the copy fills its cell, which only the first does.
  const selected = resolveAnchor({
    section: "s",
    quote: "MARK",
    prefix: "",
    suffix: "",
  });
  assert.equal(selected?.kind, "passage");
  assert.equal(selected.segments[0]?.node.parentElement?.localName, "span");
});
