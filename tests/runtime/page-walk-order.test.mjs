/* The page walks' one step (`stepFrom`, current-target.js) over the page's rendered
   order (`renderedOrder`, shadow-tree.js): `t` and `m` step from the same place the same
   way, a place holding the user's is where they already are, and words a widget renders
   in a shadow tree keep their order among the places beside them. The threads `t` walks
   keep one order (`inPageOrder`, thread/placement.js) whatever surface draws them. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { renderedOrder } from "/runtime/shadow.js";
import { stepFrom } from "/runtime/current-target.js";
import { inPageOrder } from "/runtime/thread/placement.js";

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
  assert.equal(
    stepFrom(items, { place: held, kind: "current-location" }, 1, at),
    section,
  );
  assert.equal(
    stepFrom(items, { place: held, kind: "current-location" }, -1, at),
    section,
  );
  // A place the user's holds is ahead of it, as its words follow where they stand.
  assert.equal(
    stepFrom(items, { place: main, kind: "current-location" }, 1, at),
    first,
  );
  assert.equal(
    stepFrom(items, { place: main, kind: "current-location" }, -1, at),
    last,
  );
  main.remove();
});

test("a step from inside a shadow tree goes to its neighbour there", () => {
  const { main, first, innerA, innerB, last } = page();
  const at = (item) => item;
  assert.equal(
    stepFrom([first, innerB, last], { place: innerA, kind: "current-location" }, 1, at),
    innerB,
  );
  assert.equal(
    stepFrom(
      [first, innerA, last],
      { place: innerB, kind: "current-location" },
      -1,
      at,
    ),
    innerA,
  );
  main.remove();
});

test("an unplaced item stands after every place, and a step past the end comes round", () => {
  const { main, first, last } = page();
  const loose = { name: "general" };
  const at = (item) => (item === loose ? null : item);
  assert.equal(
    stepFrom([first, loose], { place: last, kind: "current-location" }, 1, at),
    loose,
  );
  assert.equal(
    stepFrom([first, loose], { place: last, kind: "current-location" }, -1, at),
    first,
  );
  assert.equal(
    stepFrom([first], { place: last, kind: "current-location" }, 1, at),
    first,
  );
  assert.equal(
    stepFrom([first], { place: null, kind: "current-location" }, -1, at),
    first,
  );
  main.remove();
});

test("entering a region reaches its first or last stop before leaving it", () => {
  const { main, first, innerA, innerB, widget, last } = page();
  const items = [first, innerA, innerB, last];
  const at = (item) => item;
  const origin = { place: widget, kind: "enter" };
  assert.equal(stepFrom(items, origin, 1, at), innerA);
  assert.equal(stepFrom(items, origin, -1, at), innerB);
  // A visible obligation is a point to arrive at, even when it contains another obligation.
  assert.equal(
    stepFrom(
      [first, widget, innerA, innerB, last],
      { place: widget, kind: "at" },
      -1,
      at,
    ),
    widget,
  );
  main.remove();
});

test("a thread on another thread's message keeps its order whether or not it is drawn", () => {
  // A reply carrying a widget is drawn in a Leaf surface only while a view shows it, and
  // the thread walk opens and closes those views, so the order must not move with them.
  document.body.innerHTML =
    '<main><p id="on-page">Page</p></main><div class="lf-chrome"><section id="in-reply">Reply widget</section></div>';
  const threads = [
    { id: "on-page", anchor: { section: "on-page" } },
    { id: "general", anchor: null },
    { id: "on-reply", anchor: { section: "in-reply" } },
  ];
  const order = () => inPageOrder(threads, () => null).map((thread) => thread.id);
  try {
    assert.deepEqual(order(), ["on-page", "general", "on-reply"]);
    document.querySelector(".lf-chrome").remove();
    assert.deepEqual(order(), ["on-page", "general", "on-reply"]);
  } finally {
    document.body.replaceChildren();
  }
});
