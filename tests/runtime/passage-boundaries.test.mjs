/* Which layer a node stands in, read across the boundaries a shadow root draws, and
   when the page's one reading of those layers may change.

   `closest` stops at the root it is called on, so a node inside a declared tree would
   read as standing outside the chrome its host sits in. Crossing back to the host is
   what makes one answer serve both trees, and it is the reading `inChrome` and
   `pageWords` are built on.

   `pageText` is the whole of that reading, and it is a function of the document alone.
   Every caller shares one answer for as long as the document holds still, and the page
   changing under it is what makes the next caller pay for a walk. */

import assert from "node:assert/strict";
import test from "node:test";

import { closestAcross, inChrome, pageText, pageWords } from "/runtime/passages.js";

test("no node means no passage location, rather than a runtime error", () => {
  assert.equal(closestAcross(null, "main"), null);
  assert.equal(closestAcross(undefined, "main"), null);
});

test("a text node answers from the element holding it", () => {
  document.body.innerHTML = "<main><p>Words</p></main>";
  const words = document.querySelector("p").firstChild;
  assert.equal(closestAcross(words, "main"), document.querySelector("main"));
});

test("a node in a declared tree stands where its host stands", () => {
  document.body.innerHTML =
    '<div class="lf-chrome"><article id="host"></article></div><main><p>Page</p></main>';
  const host = document.querySelector("#host");
  host.attachShadow({ mode: "open" }).innerHTML = "<span>Inside</span>";
  const inside = host.shadowRoot.querySelector("span");

  assert.equal(inside.closest(".lf-chrome"), null, "closest stops at the shadow root");
  assert.equal(
    closestAcross(inside, ".lf-chrome"),
    document.querySelector(".lf-chrome"),
  );
  assert.equal(inChrome(inside), true);
  assert.equal(pageWords(inside), false);
  assert.equal(pageWords(document.querySelector("main p")), true);
});

test("the page's reading is taken once while the document holds still", () => {
  document.body.innerHTML = "<main><p>Alpha beta</p></main>";
  const first = pageText();
  assert.equal(first.raw, "Alpha beta");
  // Every anchor pass, selection change and pointer move asks for this reading. A walk
  // apiece is what makes a large page stutter, so the second ask is the same answer.
  assert.equal(pageText(), first, "a document that did not change has one reading");
});

test("a word the page changes is in the next reading", () => {
  document.body.innerHTML = "<main><p>Alpha beta</p></main>";
  pageText();
  document.querySelector("p").firstChild.data = "Alpha gamma";
  assert.equal(pageText().raw, "Alpha gamma");
});

test("words the page gains or loses are in the next reading", () => {
  document.body.innerHTML = "<main><p>Alpha</p></main>";
  pageText();
  document.querySelector("main").insertAdjacentHTML("beforeend", "<p>Beta</p>");
  assert.match(pageText().raw, /Alpha.*Beta/s);
  document.querySelector("main p").remove();
  assert.doesNotMatch(pageText().raw, /Alpha/);
});

test("words that become the runtime's own leave the next reading", () => {
  document.body.innerHTML = '<main><p>Alpha</p><p id="later">Beta</p></main>';
  pageText();
  document.querySelector("#later").classList.add("lf-ui");
  assert.doesNotMatch(pageText().raw, /Beta/);
});

test("a mark the runtime paints is not a change to what the page says", () => {
  document.body.innerHTML = "<main><p>Alpha beta</p></main>";
  const first = pageText();
  // The painter toggles its own classes on the page's own elements between passes. The
  // reading does not read them, and re-walking the document for one is the cost this
  // page could not afford.
  document.querySelector("p").classList.add("lf-mark-el");
  assert.equal(pageText(), first, "a painted class leaves the reading standing");
});
