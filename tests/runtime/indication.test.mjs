/* What an indication marks: the elements a driver's declared reference and key
   address, where the server would resolve that reference, as the union of every
   driver's standing indication.

   The vocabulary is stated here: a driver declaring `x-refers` on `for`, and a target
   whose `lfElementsFor` maps a key to its own children, which is the hook's whole
   contract. Nothing about a real widget's rendering is needed to ask these. */

import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { indicate } from "/runtime/indication.js";
import { referencedProjection } from "/runtime/anchor-resolution.js";
import { registry } from "/runtime/registry.js";
import { LAYOUT } from "/runtime/widget-elements.js";

beforeEach(() => {
  for (const tag of Object.keys(registry)) delete registry[tag];
  Object.assign(registry, {
    "lf-driver": { "x-refers": { for: {} } },
    "lf-target": {},
  });
});

// A target whose key is a comma list of its children's `data-part` names.
const target = (id, parts) => {
  const element = document.createElement("lf-target");
  element.id = id;
  for (const part of parts) {
    const child = document.createElement("span");
    child.dataset.part = part;
    element.append(child);
  }
  element.lfElementsFor = (key) =>
    key
      .split(",")
      .map((part) => element.querySelector(`[data-part="${part}"]`))
      .filter(Boolean);
  return element;
};

const driver = (id, refers) => {
  const element = document.createElement("lf-driver");
  element.id = id;
  element.setAttribute("for", refers);
  return element;
};

const marked = () =>
  [...document.querySelectorAll("[data-lf-indicated]")].map(
    (element) => `${element.parentElement.id}:${element.dataset.part}`,
  );

// Which document a reference landed in, named rather than compared as elements: an
// element in a failing assertion's diff is inspected down its whole tree.
const home = (owner) =>
  referencedProjection(owner, "for")?.parentElement.dataset.home ?? "nothing";

test("a reference resolves in its own message before the page, and never in another message", () => {
  document.body.innerHTML =
    "<main data-home='page'></main><div class='lf-chrome'></div>";
  const main = document.querySelector("main");
  const chrome = document.querySelector(".lf-chrome");
  main.append(target("code", ["a"]), target("page-only", ["a"]));
  const [mine, theirs] = ["mine", "theirs"].map((name) => {
    const body = document.createElement("div");
    body.className = "lf-msg-body";
    body.dataset.home = name;
    chrome.append(body);
    return body;
  });
  mine.append(target("code", ["b"]));
  theirs.append(target("elsewhere", ["c"]));

  const inMessage = driver("d", "code");
  mine.append(inMessage);
  assert.equal(home(inMessage), "mine");
  inMessage.setAttribute("for", "page-only");
  assert.equal(home(inMessage), "page");
  inMessage.setAttribute("for", "elsewhere");
  assert.equal(home(inMessage), "nothing");

  const onPage = driver("p", "code");
  main.append(onPage);
  assert.equal(home(onPage), "page");
});

test("each driver holds one key per attribute, and the page wears the union", () => {
  document.body.innerHTML = "<main></main>";
  const main = document.querySelector("main");
  const code = target("code", ["1", "2", "3", "4"]);
  const film = driver("film", "code");
  const other = driver("other", "code");
  main.append(code, film, other);

  assert.equal(indicate(film, "for", "1,2"), true);
  assert.deepEqual(marked(), ["code:1", "code:2"]);
  // The target's own ARIA state is its own: a mark neither writes nor clears it.
  const line = code.querySelector('[data-part="1"]');
  line.setAttribute("aria-current", "location");

  indicate(film, "for", "3");
  assert.deepEqual(marked(), ["code:3"], "a new key replaces the driver's last one");
  indicate(film, "for", "1");
  indicate(film, "for", "3");
  assert.equal(line.getAttribute("aria-current"), "location");

  indicate(other, "for", "3,4");
  indicate(film, "for", null);
  assert.deepEqual(marked(), ["code:3", "code:4"], "one driver never clears another's");

  assert.equal(
    indicate(film, "for", "9"),
    false,
    "a key addressing nothing marks nothing",
  );
  indicate(other, "for", null);
  indicate(film, "for", null);
  assert.deepEqual(marked(), []);
});

test("a re-render the target states is resolved again", () => {
  document.body.innerHTML = "<main></main>";
  const main = document.querySelector("main");
  const code = target("code", []);
  const film = driver("film", "code");
  main.append(code, film);

  assert.equal(indicate(film, "for", "2"), false);
  for (const part of ["1", "2"]) {
    const child = document.createElement("span");
    child.dataset.part = part;
    code.append(child);
  }
  code.dispatchEvent(new CustomEvent(LAYOUT, { bubbles: true, composed: true }));
  assert.deepEqual(marked(), ["code:2"]);
  indicate(film, "for", null);
});

test("an attribute the driver's entry does not declare is the caller's error", () => {
  document.body.innerHTML = "<main></main>";
  const film = driver("film", "code");
  document.querySelector("main").append(film);
  assert.throws(() => indicate(film, "about", "1"), TypeError);
  assert.throws(() => indicate(film, "for", ""), TypeError);
  assert.throws(() => indicate(null, "for", "1"), TypeError);
});
