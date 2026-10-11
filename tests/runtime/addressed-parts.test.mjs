/* What travel asks a widget before it reads what a key addresses under it
   (`revealAddressed`): a visual draws the state holding a declared part, and a lazy
   widget hands back its hydration. A thread anchored to a part and a module's
   `navigateToDatum` both ask this, so a part one of them reaches the other reaches too.

   The vocabulary is stated here: a film declaring its parts in `parts` and drawing one
   frame at a time, and a lazy list answering `lfRevealDatum`. */

import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { addressedElements, revealAddressed } from "/runtime/anchor-resolution.js";
import { registry } from "/runtime/registry.js";
import { registerVisualParts } from "/runtime/visual-parts.js";

beforeEach(() => {
  for (const tag of Object.keys(registry)) delete registry[tag];
  Object.assign(registry, {
    "lf-film": { "x-visual": { parts: "parts" } },
    "lf-lazy": {},
  });
});

// A film that draws one of its declared frames at a time.
const film = () => {
  const element = document.createElement("lf-film");
  element.id = "film";
  element.setAttribute("parts", "one two");
  const draw = (id) => {
    element.replaceChildren(document.createElement("span"));
    element.firstChild.dataset.frame = id;
  };
  draw("one");
  registerVisualParts(
    element,
    () => [
      {
        id: element.firstChild.dataset.frame,
        element: element.firstChild,
        label: "a frame",
      },
    ],
    { reveal: draw },
  );
  return element;
};

const frame = (element, key) =>
  addressedElements(element, key).map((part) => part.dataset.frame);

test("a part a visual draws in another state is drawn before travel reads it", () => {
  document.body.innerHTML = "<main></main>";
  const source = film();
  document.querySelector("main").append(source);

  assert.deepEqual(frame(source, "two"), [], "the film opens on its first frame");
  assert.equal(revealAddressed(source, "two"), null, "a visual draws synchronously");
  assert.deepEqual(frame(source, "two"), ["two"]);
  assert.equal(
    revealAddressed(source, "three"),
    null,
    "an undeclared part is not drawn",
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
  registry["lf-film"]["x-visual"].all = "all";
  const source = film();
  source.setAttribute("parts", "all");
  document.querySelector("main").append(source);
  assert.deepEqual(frame(source, "one"), ["one"]);
  revealAddressed(source, "two");
  assert.deepEqual(frame(source, "two"), ["two"]);
  source.removeAttribute("parts");
  assert.deepEqual(frame(source, "two"), []);
});

test("visual ownership and authored IDs follow each publication's own declaration", async () => {
  const { visualAt, isAddressable, addressableAt } =
    await import("/runtime/anchor-resolution.js");
  const { bindVocabulary, rememberVocabulary } =
    await import("/runtime/widget-contexts.js");
  const root = document.createElement("main");
  root.innerHTML =
    '<lf-publication-visual id="frozen-visual"><p id="generated-id">Frozen drawing.</p></lf-publication-visual><lf-publication-visual id="current-prose"><p id="authored-id">Current prose.</p><img id="ordinary-picture"></lf-publication-visual>';
  document.body.append(root);
  const [visual, prose] = root.children;
  for (const [index, host] of [visual, prose].entries()) {
    const context = {
      revision: 401 + index,
      declarations: {
        $layer: { generation: `visual-ownership-${index}` },
        "lf-publication-visual": index === 0 ? { "x-visual": "whole" } : {},
      },
    };
    rememberVocabulary(context);
    bindVocabulary(host, context);
  }
  try {
    assert.ok(visualAt(prose.firstElementChild) === null);
    assert.ok(visualAt(prose.lastElementChild)?.element === prose.lastElementChild);
    assert.equal(isAddressable(prose.firstElementChild), true);
    assert.ok(
      addressableAt(prose.firstElementChild.firstChild) === prose.firstElementChild,
    );
    assert.ok(visualAt(visual.firstElementChild)?.element === visual);
    assert.equal(isAddressable(visual.firstElementChild), false);
    assert.ok(addressableAt(visual.firstElementChild.firstChild) === visual);
    // The outermost provider reading skips a same-tag ancestor whose publication
    // declares prose, rather than letting it take the nested drawing's identity.
    prose.append(visual);
    assert.ok(visualAt(visual.firstElementChild)?.element === visual);
  } finally {
    root.remove();
  }
});
