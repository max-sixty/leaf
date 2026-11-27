/* What travel asks a widget before it reads what a key addresses under it
   (`revealAddressed`): a visual draws the state holding a declared part, and a lazy
   widget hands back its hydration. A thread anchored to a part, a module's
   `navigateToDatum` and a URL fragment naming a widget's key all ask this, so a part
   one of them reaches the others reach too.

   A visual with too many parts to list answers both directions itself: the part an id
   names, which a comment's anchor resolves to, and the part a node of it stands for,
   which aim and focus take.

   A visual whose parts are no places to stand takes focus for them itself, settling on
   the part as focus is placed there and at no other time.

   The vocabulary is stated here: a film admitting frame ids by prefix and drawing one
   frame at a time, a lazy list answering `lfRevealDatum`, and a plot drawing a mark for
   each point it is asked for. */

import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { fragmentKey, fragmentUrl } from "/runtime/base/anchor-coordinate.js";
import {
  addressedElements,
  addressedFocus,
  aimTargetAt,
  elementNamed,
  focusTargetAt,
  fragmentAddress,
  fragmentTarget,
  resolveAnchor,
  revealAddressed,
  visualPartLabel,
  visualParts,
} from "/runtime/readings/anchor-resolution.js";
import { targetElement } from "/runtime/readings/resolved-target.js";
import { registry } from "/runtime/state/registry.js";
import { visualPartProblems } from "/runtime/state/visual-parts.js";
import { layoutChanged } from "/runtime/lib/widget-events.js";
import { kept } from "/runtime/state/kept.js";
import { focusDestination, handBack } from "/runtime/dom/focus.js";

beforeEach(() => {
  for (const tag of Object.keys(registry)) delete registry[tag];
  Object.assign(registry, {
    "lf-film": {
      visual: { prefixes: ["frame:"] },
    },
    "lf-lazy": {},
    "lf-plot": {
      visual: { prefixes: ["point:"] },
    },
  });
});

// A film that draws one admitted frame at a time.
const film = () => {
  const element = document.createElement("lf-film");
  element.id = "film";
  const draw = (id) => {
    element.replaceChildren(document.createElement("span"));
    element.firstChild.dataset.frame = id.replace("frame:", "");
  };
  draw("one");
  element.lfParts = {
    read: () => [
      {
        id: `frame:${element.firstChild.dataset.frame}`,
        element: element.firstChild,
        label: "a frame",
      },
    ],
    reveal: draw,
  };
  return element;
};

const frame = (element, key) =>
  addressedElements(element, `frame:${key}`).map((part) => part.dataset.frame);

test("a part a visual draws in another state is drawn before travel reads it", () => {
  document.body.innerHTML = "<main></main>";
  const source = film();
  document.querySelector("main").append(source);

  assert.deepEqual(frame(source, "two"), [], "the film opens on its first frame");
  assert.equal(
    revealAddressed(source, "frame:two"),
    null,
    "a visual draws synchronously",
  );
  assert.deepEqual(frame(source, "two"), ["two"]);
  assert.equal(
    revealAddressed(source, "three"),
    null,
    "an unadmitted part is not drawn",
  );
  assert.deepEqual(frame(source, "two"), ["two"]);
});

test("a lazy widget answers with its hydration", () => {
  document.body.innerHTML = "<main></main>";
  const source = document.createElement("lf-lazy");
  const asked = [];
  const hydrated = Promise.resolve();
  source.lfRevealDatum = (key) => {
    asked.push(key);
    return hydrated;
  };
  document.querySelector("main").append(source);

  assert.equal(revealAddressed(source, "row-7"), hydrated);
  assert.deepEqual(asked, ["row-7"]);
});

test("travel settles a visible part before a pending replacement can retire it", async () => {
  document.body.innerHTML = "<main></main>";
  const source = document.createElement("lf-film");
  let shown = "one";
  let replacing = true;
  const surface = document.createElement("span");
  source.append(surface);
  document.querySelector("main").append(source);
  source.lfParts = {
    read: () => [{ id: `frame:${shown}`, element: surface, label: "a frame" }],
    reveal: (id) => {
      replacing = false;
      shown = id.replace("frame:", "");
    },
  };
  const replacement = Promise.resolve().then(() => {
    if (replacing) shown = "two";
  });

  revealAddressed(source, "frame:one");
  await replacement;
  assert.equal(shown, "one", "the requested destination remains the drawn part");
});

test("a package inventory rejects bad ids instead of recovering or rewriting them", () => {
  document.body.innerHTML = "<main></main>";
  const source = document.createElement("lf-film");
  let id = "frame:one";
  const element = document.createElement("span");
  source.append(element);
  document.querySelector("main").append(source);
  source.lfParts = { read: () => [{ id, element, label: "a frame" }] };

  assert.equal(visualParts(source)[0].id, id);
  for (id of [" frame:one", "frame:one ", "frame:two parts", "", 7, null])
    assert.throws(() => visualParts(source), /has no single-token id/);
});

test("a fragment names a widget's key, and the URL built for one reads back as it", () => {
  const widget = document.createElement("lf-film");
  for (const [id, key] of [
    ["items", "b/3"],
    ["diff", '["src/a b.py","new",12]'],
    ["flow", "node:Line%20Item"],
    ["a:b", "c"],
  ]) {
    widget.id = id;
    const url = new URL(fragmentUrl(widget, key));
    assert.deepEqual(fragmentKey(url.hash), { id, key }, url.hash);
  }
  widget.id = "items";
  assert.equal(new URL(fragmentUrl(widget)).hash, "#items");
  assert.equal(new URL(fragmentUrl(widget, "b/3")).hash, "#items:b/3");
  for (const hash of ["#items", "#:b/3", "#items:"])
    assert.equal(fragmentKey(hash), null, hash);
});

test("a fragment names an element by its id first, else a widget's key", () => {
  document.body.innerHTML = '<main><section id="a:b">Authored</section></main>';
  const source = film();
  document.querySelector("main").append(source);

  // An authored id holding a colon keeps its link.
  assert.equal(fragmentTarget("#a:b"), document.getElementById("a:b"));
  // A key the widget has not drawn names the widget until travel draws it.
  assert.deepEqual(fragmentAddress("#film:frame:two"), {
    element: source,
    key: "frame:two",
    place: null,
  });
  assert.equal(fragmentTarget("#film:frame:two"), source);
  revealAddressed(source, "frame:two");
  assert.equal(fragmentTarget("#film:frame:two")?.dataset.frame, "two");
  assert.equal(fragmentTarget("#missing:frame:two"), null);
});

test("an address in an agent's message names its message's element before the page's", () => {
  // A thread Leaf seats in the page's flow stands before the page's own element.
  document.body.innerHTML =
    '<div data-lf-runtime><div class="lf-msg-body"><section id="twice">Message</section>' +
    '<b id="only-said">From</b></div></div>' +
    '<main><section id="twice">Page</section><p id="100%">Full</p></main>';
  const source = film();
  document.querySelector("main").append(source);
  const [message, page] = document.querySelectorAll("section");
  const from = document.querySelector("b");

  assert.equal(elementNamed("twice"), page);
  assert.equal(elementNamed("twice", page), page);
  assert.equal(elementNamed("#twice", from), message);
  assert.equal(elementNamed("twice", from), message);
  // An id the page lacks names what a reply Leaf draws holds.
  assert.equal(elementNamed("only-said"), from);
  // What the message doesn't hold, the page does, a widget's key included.
  assert.equal(elementNamed("film:frame:two", from), source);
  // A bare address keeps each `%` it spells; a fragment spells one encoded.
  assert.equal(elementNamed("100%")?.localName, "p");
  assert.equal(elementNamed("#100%25")?.localName, "p");
});

// A plot of three points, drawn as one line, that draws a mark for a point when asked
// for it by id, whose own aim stands on one point or none, and which stands on a point
// Leaf puts focus on it for.
const SVG = "http://www.w3.org/2000/svg";
const plot = () => {
  const element = document.createElement("lf-plot");
  element.id = "plot";
  const svg = document.createElementNS(SVG, "svg");
  const line = document.createElementNS(SVG, "path");
  const ring = document.createElementNS(SVG, "circle");
  svg.append(line, ring);
  element.append(svg);
  const points = new Set(["a", "b", "c"]);
  /** @type {Map<string, any>} */
  const marks = new Map();
  const state = { aimed: null, asked: [], settled: [] };
  element.lfParts = {
    read: () => [...marks.values()],
    find: (id) => {
      state.asked.push(id);
      const point = id.replace("point:", "");
      if (!points.has(point)) return null;
      if (!marks.has(id)) {
        const mark = document.createElementNS(SVG, "circle");
        svg.append(mark);
        marks.set(id, { id, element: mark, label: `point ${point}` });
      }
      return marks.get(id);
    },
    at: (node) =>
      state.aimed && (node === element || svg.contains(node))
        ? { id: state.aimed, element: ring, label: "the point aimed at" }
        : null,
    label: (id) => `point ${id.replace("point:", "")}, no longer drawn`,
    focus: (id) => {
      state.settled.push(id);
      state.aimed = id;
    },
  };
  return { element, line, ring, marks, state };
};

test("a part a visual is too large to list is found by its id, and only it is listed", () => {
  document.body.innerHTML = "<main></main>";
  const { element, marks, state } = plot();
  document.querySelector("main").append(element);

  assert.deepEqual(visualParts(element), [], "the plot lists no point nobody named");
  const found = resolveAnchor({ section: "plot", visual: "point:b" });
  assert.equal(targetElement(found), marks.get("point:b")?.element);
  assert.deepEqual(state.asked, ["point:b"], "the plot is asked, not searched");
  assert.deepEqual(
    visualParts(element).map((part) => part.id),
    ["point:b"],
  );
  assert.equal(visualPartLabel(element, "point:b"), "point b");
  // A point the plot doesn't draw stands on the whole plot, which may draw it once it
  // can, and is named by the plot's label reader.
  const absent = resolveAnchor({ section: "plot", visual: "point:z" });
  assert.equal(targetElement(absent), element);
  assert.equal(absent?.status, "fallback");
  assert.equal(visualPartLabel(element, "point:z"), "point z, no longer drawn");
  assert.equal(resolveAnchor({ section: "plot", visual: "frame:b" }), null);
});

test("a node of a visual stands for the part the visual names for it", () => {
  document.body.innerHTML = "<main></main>";
  const { element, line, ring, state } = plot();
  document.querySelector("main").append(element);

  // A hit on the line takes the whole plot while the plot's aim stands nowhere, and
  // the point it stands on once it does, though no element of that point was hit.
  assert.deepEqual(aimTargetAt(line)?.anchor, { section: "plot" });
  state.aimed = "point:a";
  const aimed = aimTargetAt(line);
  assert.deepEqual(aimed?.anchor, { section: "plot", visual: "point:a" });
  assert.equal(aimed?.element, ring);
  // Focus on the plot takes the point the plot stands on, while the plot read as one
  // element, as the target picker reads it, stays whole.
  assert.deepEqual(focusTargetAt(element)?.anchor, {
    section: "plot",
    visual: "point:a",
  });
  assert.deepEqual(aimTargetAt(element)?.anchor, { section: "plot" });
  state.aimed = null;
  assert.deepEqual(focusTargetAt(element)?.anchor, { section: "plot" });
  // A part outside the declared prefixes is not taken.
  state.aimed = "frame:a";
  assert.deepEqual(aimTargetAt(line)?.anchor, { section: "plot" });
});

test("a visual settles on its part as focus is placed there, and at no other time", () => {
  document.body.innerHTML = "<main><button>Elsewhere</button></main>";
  const { element, state } = plot();
  element.tabIndex = 0;
  document.querySelector("main").append(element);
  const elsewhere = document.querySelector("button");

  // Naming where focus goes for a point, as travel does each time it reads its
  // destination, changes nothing the plot shows.
  const destination = addressedFocus(element, "point:b");
  assert.ok(destination);
  assert.deepEqual(state.settled, []);
  // A hand-back that passes the plot by, which can't take focus now, leaves it as it was.
  element.inert = true;
  handBack(destination, elsewhere);
  assert.equal(document.activeElement, elsewhere);
  assert.deepEqual(state.settled, []);
  // Nor does placing focus on it while it can't take focus, as travel to a chart inside
  // an inert region does.
  focusDestination(destination, "move");
  assert.deepEqual(state.settled, []);
  // Placing focus there settles the plot on the point, once, and the plot takes it.
  element.inert = false;
  focusDestination(destination, "move");
  assert.equal(document.activeElement, element);
  assert.deepEqual(state.settled, ["point:b"]);
  assert.deepEqual(focusTargetAt(element)?.anchor, {
    section: "plot",
    visual: "point:b",
  });
});

test("a visual whose lfParts reads nothing is read by the parts it marks", () => {
  document.body.innerHTML = "<main></main>";
  const source = document.createElement("lf-film");
  source.id = "marked";
  // The plot standing inside the film is a visual of its own, and what it marks is its
  // own, whatever the ids: one the film would admit, and one that is no id at all.
  source.innerHTML =
    '<span data-lf-part="frame:one">The  first <b>frame</b></span>' +
    '<svg><circle data-lf-part="frame:two" aria-label="The second frame"/></svg>' +
    '<lf-plot><i data-lf-part="frame:nine">A point</i>' +
    '<i data-lf-part="x-axis tick label">A tick</i></lf-plot>';
  document.querySelector("main").append(source);
  const [one, two] = source.querySelectorAll('[data-lf-part^="frame:"]');

  // In document order, each named by its `aria-label` or else by its words.
  const inventory = () =>
    visualParts(source).map(({ id, element, label }) => [id, element, label]);
  assert.deepEqual(inventory(), [
    ["frame:one", one, "The first frame"],
    ["frame:two", two, "The second frame"],
  ]);
  const found = resolveAnchor({ section: "marked", visual: "frame:two" });
  assert.equal(targetElement(found), two);
  // A hit inside a marked node is a hit on its part.
  assert.deepEqual(aimTargetAt(one.querySelector("b"))?.anchor, {
    section: "marked",
    visual: "frame:one",
  });
  // A mark of the film's own that its prefixes don't admit is no part, and is what the
  // render check names.
  const declaration = registry["lf-film"].visual;
  assert.deepEqual(visualPartProblems(source, declaration), []);
  const mistyped = source.appendChild(document.createElement("span"));
  mistyped.dataset.lfPart = "frme:three";
  mistyped.textContent = "A third frame";
  assert.equal(inventory().length, 2);
  assert.deepEqual(visualPartProblems(source, declaration), [
    { kind: "unadmitted-parts", parts: ["frme:three"] },
  ]);
  mistyped.remove();
  // The marks are read as they stand. A reading kept from them is made again once the
  // widget's layout is said to have changed, as Leaf says after it sets the element's
  // properties.
  const ids = kept(() => inventory().map(([id]) => id));
  assert.deepEqual(ids(), ["frame:one", "frame:two"]);
  one.remove();
  assert.deepEqual(inventory(), [["frame:two", two, "The second frame"]]);
  assert.deepEqual(ids(), ["frame:one", "frame:two"]);
  layoutChanged(source);
  assert.deepEqual(ids(), ["frame:two"]);
});
