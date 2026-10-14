/* The page walks' one step (`stepFrom`, standing-target.js) over the page's rendered
   order (`renderedOrder`, shadow-tree.js): `t` and `m` step from the same place the same
   way, a place holding the user's is where they already are, and words a widget renders
   in a shadow tree keep their order among the places beside them. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { renderedOrder } from "/runtime/shadow.js";
import { stepFrom } from "/runtime/standing-target.js";

// <main><p first/><section><p held/></section><x-widget>#shadow<p inner-a/><p inner-b/></x-widget><p last/></main>
function page() {
  const main = document.createElement("main");
  const first = document.createElement("p");
  const section = document.createElement("section");
  const held = document.createElement("p");
  section.append(held);
  const widget = document.createElement("x-widget");
  const innerA = document.createElement("p");
  const innerB = document.createElement("p");
  widget.attachShadow({ mode: "open" }).append(innerA, innerB);
  const last = document.createElement("p");
  main.append(first, section, widget, last);
  document.body.append(main);
  return { main, first, section, held, widget, innerA, innerB, last };
}

test("rendered order reads into a shadow tree rather than stopping at its host", () => {
  const { main, first, widget, innerA, innerB, last } = page();
  assert.ok(renderedOrder(first, innerA) < 0);
  assert.ok(renderedOrder(innerA, innerB) < 0);
  assert.ok(renderedOrder(innerB, last) < 0);
  assert.ok(renderedOrder(last, innerA) > 0);
  // A node comes before what it holds, its shadow tree included.
  assert.ok(renderedOrder(widget, innerA) < 0);
  assert.equal(renderedOrder(innerA, innerA), 0);
  main.remove();
});

test("a place holding the user's is the nearest step either way", () => {
  const { main, first, section, held, last } = page();
  const items = [first, section, last];
  const at = (item) => item;
  assert.equal(stepFrom(items, held, 1, at).row, section);
  assert.equal(stepFrom(items, held, -1, at).row, section);
  // A place the user's holds is ahead of it, as its words follow where they stand.
  assert.equal(stepFrom(items, main, 1, at).row, first);
  assert.deepEqual(stepFrom(items, main, -1, at), { row: last, wrapped: true });
  main.remove();
});

test("a step from inside a shadow tree goes to its neighbour there", () => {
  const { main, first, innerA, innerB, last } = page();
  const at = (item) => item;
  assert.equal(stepFrom([first, innerB, last], innerA, 1, at).row, innerB);
  assert.equal(stepFrom([first, innerA, last], innerB, -1, at).row, innerA);
  main.remove();
});

test("an unplaced item stands after every place, and a step past the end comes round", () => {
  const { main, first, last } = page();
  const loose = { name: "general" };
  const at = (item) => (item === loose ? null : item);
  assert.equal(stepFrom([first, loose], last, 1, at).row, loose);
  assert.deepEqual(stepFrom([first, loose], last, -1, at), {
    row: first,
    wrapped: false,
  });
  assert.deepEqual(stepFrom([first], last, 1, at), { row: first, wrapped: true });
  assert.deepEqual(stepFrom([first], null, -1, at), { row: first, wrapped: false });
  main.remove();
});
