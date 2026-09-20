/* Which layer a node stands in, read across the boundaries a shadow root draws.

   `closest` stops at the root it is called on, so a node inside a declared tree would
   read as standing outside the chrome its host sits in. Crossing back to the host is
   what makes one answer serve both trees, and it is the reading `inChrome` and
   `pageWords` are built on. */

import assert from "node:assert/strict";
import test from "node:test";

import { closestAcross, inChrome, pageWords } from "/runtime/passages.js";

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
