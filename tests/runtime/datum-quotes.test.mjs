import "/runtime/stage-integration.js";
/* Which words a quote anchored in a widget's data is captured against and found again
   in: its datum's own (`pageText(datum)`), read alone with the datum's edges as the
   reading's ends. A page grows large through its widgets' data, so finding such a quote
   costs what its datum holds, and the edge of the datum is the edge of its context on
   both sides of the round trip.

   The datum is a block of a widget's projection (`data-lf-projection`, `data-lf-datum`)
   standing between prose paragraphs, which share no fence with it. */

import assert from "node:assert/strict";
import test from "node:test";

import { anchorForRange, resolveAnchor } from "/runtime/anchor-resolution.js";
import { registry } from "/runtime/registry.js";

/** @param {string} lines the datum's rows, as markup */
const page = (lines, prose = "<p>Words before the data</p>") => {
  document.body.innerHTML =
    `<main>${prose}<div id="w"><div id="doc" data-lf-projection="w" ` +
    `data-lf-datum="doc">${lines}</div></div><p>Words after the data</p></main>`;
  return document.querySelector("#doc");
};

const selecting = (node) => {
  const range = document.createRange();
  range.selectNodeContents(node);
  return range;
};

// A line a document holds twice, at its top and at its foot, has nothing beside it on
// one side within the document. Read against the page's whole reading, that empty side
// met the prose around the document, so no copy confirmed it and the comment detached.
test("a line a datum holds twice is found at the copy the user selected", () => {
  Object.assign(registry, { $layer: { generation: "datum-quote-edges" } });
  const datum = page("<p>Repeated line</p><p>Middle line</p><p>Repeated line</p>");
  const [top, , foot] = [...datum.querySelectorAll("p")].map((p) => p.firstChild);
  for (const [copy, line] of [
    ["top", top],
    ["foot", foot],
  ]) {
    const anchor = anchorForRange(selecting(line));
    assert.equal(anchor?.detached, undefined, `the ${copy} copy keeps its place`);
    assert.equal(anchor?.datum, "doc");
    const resolved = resolveAnchor(anchor);
    assert.equal(resolved?.kind, "passage");
    assert.equal(resolved.exact, true);
    assert.deepEqual(
      resolved.segments.map(({ node, start, end }) => [node, start, end]),
      [[line, 0, line.data.length]],
      `the ${copy} copy is the one found`,
    );
  }
});

// The same line in the prose beside the datum, with the same neighbours, is no
// candidate: a datum's quote stands in its datum.
test("a datum's quote is never found outside its datum", () => {
  Object.assign(registry, { $layer: { generation: "datum-quote-within" } });
  const datum = page("<p>Shared line</p>", "<p>Shared line</p>");
  const resolved = resolveAnchor({ section: "w", datum: "doc", quote: "Shared line" });
  assert.equal(resolved?.kind, "passage");
  assert.equal(resolved.segments[0]?.node, datum.querySelector("p").firstChild);
});

// Resolution reads the datum's words and none of the page's others: four thousand
// paragraphs beside the datum leave their text unread.
test("finding a datum's quote reads no words outside the datum", () => {
  Object.assign(registry, { $layer: { generation: "datum-quote-reads" } });
  const prose = Array.from({ length: 4096 }, (_, i) => `<p>Paragraph ${i}</p>`);
  const datum = page("<p>Alpha</p><p>Beta</p>", prose.join(""));
  let owner = Text.prototype;
  while (!Object.getOwnPropertyDescriptor(owner, "data"))
    owner = Object.getPrototypeOf(owner);
  const data = Object.getOwnPropertyDescriptor(owner, "data");
  let outside = 0;
  Object.defineProperty(owner, "data", {
    ...data,
    get() {
      if (!datum.contains(this)) outside += 1;
      return data.get.call(this);
    },
  });
  try {
    const resolved = resolveAnchor({ section: "w", datum: "doc", quote: "Beta" });
    assert.equal(resolved?.kind, "passage");
  } finally {
    Object.defineProperty(owner, "data", data);
  }
  assert.equal(outside, 0, `${outside} text nodes outside the datum read`);
});
