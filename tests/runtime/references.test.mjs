/* Where a `refers` attribute resolves, for `navigateToDatum` and a widget's data input
   alike: in the referrer's own message before the page, never in another message. And
   `navigateToDatum` handed an attribute its entry doesn't declare is the caller's
   error. */

import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import {
  referencedProjection,
  requireReference,
} from "/runtime/readings/references.js";
import { registry } from "/runtime/state/registry.js";

beforeEach(() => {
  for (const tag of Object.keys(registry)) delete registry[tag];
  Object.assign(registry, {
    "lf-driver": {
      refers: { for: {} },
    },
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
    "<div class='lf-chrome'></div><header data-home='header'></header>" +
    "<main data-home='page'></main><footer data-home='footer'></footer>";
  const main = document.querySelector("main");
  const chrome = document.querySelector(".lf-chrome");
  main.append(target("code", ["a"]), target("page-only", ["a"]));
  document.querySelector("header").append(target("header-only", ["a"]));
  document.querySelector("footer").append(target("footer-only", ["a"]));
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
  for (const name of ["header", "footer"]) {
    onPage.setAttribute("for", `${name}-only`);
    assert.equal(home(onPage), name);
    inMessage.setAttribute("for", `${name}-only`);
    assert.equal(home(inMessage), name);
  }
  onPage.setAttribute("for", "elsewhere");
  assert.equal(home(onPage), "nothing");
});

test("an attribute the referrer's entry does not declare is the caller's error", () => {
  document.body.innerHTML = "<main></main>";
  const film = driver("film", "code");
  document.querySelector("main").append(film);
  assert.throws(() => requireReference(film, "about"), TypeError);
  assert.doesNotThrow(() => requireReference(film, "for"));
});
