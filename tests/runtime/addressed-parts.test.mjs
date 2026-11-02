/* What travel asks a widget before it reads what a key addresses under it
   (`revealAddressed`): a visual draws the state holding a declared part, and a lazy
   widget hands back its hydration. A thread anchored to a part, a module's
   `navigateToDatum` and a URL fragment naming a widget's key all ask this, so a part
   one of them reaches the others reach too.

   The vocabulary is stated here: a film admitting frame ids by prefix and drawing one
   frame at a time, and a lazy list answering `lfRevealDatum`. */

import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { fragmentKey, fragmentUrl } from "/runtime/anchor-coordinate.js";
import {
  addressedElements,
  fragmentAddress,
  fragmentTarget,
  revealAddressed,
  visualParts,
} from "/runtime/anchor-resolution.js";
import { registry } from "/runtime/registry.js";
import { registerVisualParts } from "/runtime/visual-parts.js";

beforeEach(() => {
  for (const tag of Object.keys(registry)) delete registry[tag];
  Object.assign(registry, {
    "lf-film": { "x-visual": { prefixes: ["frame:"] } },
    "lf-lazy": {},
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
  registerVisualParts(
    element,
    () => [
      {
        id: `frame:${element.firstChild.dataset.frame}`,
        element: element.firstChild,
        label: "a frame",
      },
    ],
    { reveal: draw },
  );
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

test("an opted-in complete inventory derives targets while omission keeps the whole visual", () => {
  document.body.innerHTML = "<main></main>";
  registry["lf-film"]["x-visual"] = { parts: "parts" };
  const source = film();
  source.setAttribute("parts", "all");
  document.querySelector("main").append(source);
  assert.deepEqual(frame(source, "one"), ["one"]);
  revealAddressed(source, "frame:two");
  assert.deepEqual(frame(source, "two"), ["two"]);
  source.removeAttribute("parts");
  assert.deepEqual(frame(source, "two"), []);
});

test("travel settles a visible part before a pending replacement can retire it", async () => {
  document.body.innerHTML = "<main></main>";
  const source = document.createElement("lf-film");
  let shown = "one";
  let replacing = true;
  const surface = document.createElement("span");
  source.append(surface);
  document.querySelector("main").append(source);
  registerVisualParts(
    source,
    () => [{ id: `frame:${shown}`, element: surface, label: "a frame" }],
    {
      reveal: (id) => {
        replacing = false;
        shown = id.replace("frame:", "");
      },
    },
  );
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
  registerVisualParts(source, () => [{ id, element, label: "a frame" }]);

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
