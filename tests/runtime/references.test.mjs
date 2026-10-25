/* Where an `x-refers` attribute resolves: in the referrer's own message before the
   page, never in another message, and for a keyed contract in the referrer's own
   scope. And a verb handed an attribute its entry doesn't declare is the caller's
   error. `navigateToDatum` and widget data inputs both read references this way. */

import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { referencedProjection, requireReference } from "/runtime/references.js";
import { registry } from "/runtime/registry.js";

beforeEach(() => {
  for (const tag of Object.keys(registry)) delete registry[tag];
  Object.assign(registry, {
    "lf-driver": { "x-refers": { for: {} } },
    "lf-target": {},
  });
});

const target = (id, parts) => {
  const element = document.createElement("lf-target");
  element.id = id;
  for (const part of parts) {
    const child = document.createElement("span");
    child.dataset.part = part;
    element.append(child);
  }
  return element;
};

const driver = (id, refers) => {
  const element = document.createElement("lf-driver");
  element.id = id;
  element.setAttribute("for", refers);
  return element;
};

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

test("a keyed reference names the member its own scope holds, never an id", () => {
  Object.assign(registry, {
    "lf-scope": {},
    "lf-member": { "x-unique": { name: "lf-scope" } },
    "lf-keyed": { "x-refers": { for: { tag: "lf-member", key: "name" } } },
  });
  document.body.innerHTML = `<main>
    <lf-scope data-home="mine"><lf-member name="tone"></lf-member>
      <lf-scope data-home="nested"><lf-member name="size"></lf-member></lf-scope>
      <p><lf-keyed for="tone"></lf-keyed></p></lf-scope>
    <lf-scope data-home="theirs"><lf-member name="size" id="tone"></lf-member></lf-scope>
  </main>`;
  const keyed = document.querySelector("lf-keyed");
  assert.equal(home(keyed), "mine");
  keyed.setAttribute("for", "size");
  assert.equal(home(keyed), "nothing", "a nested scope's member is not this scope's");
});

test("an attribute the referrer's entry does not declare is the caller's error", () => {
  document.body.innerHTML = "<main></main>";
  const film = driver("film", "code");
  document.querySelector("main").append(film);
  assert.throws(() => requireReference("navigateToDatum", film, "about"), TypeError);
  assert.doesNotThrow(() => requireReference("navigateToDatum", film, "for"));
});
