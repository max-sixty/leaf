/* Which layer a node stands in, read across the boundaries a shadow root draws, and
   when the page's one reading of those layers may change.

   `closest` stops at the root it is called on, so a node inside a declared tree would
   read as standing outside the chrome its host sits in. Crossing back to the host is
   what makes one answer serve both trees, and it is the reading `inChrome` and
   `pageWords` are built on.

   `pageText` is the whole of that reading. Every caller shares one answer for as long as
   the page holds still, and something the reading is built out of moving is what makes the
   next caller pay for a walk. The document reports most of that movement itself; the two
   inputs it reports nothing about have a door apiece, and the last cases here are why. */

import assert from "node:assert/strict";
import test from "node:test";

import { registry } from "/runtime/registry.js";
import {
  closestAcross,
  fencePassageParts,
  inChrome,
  neighbourhood,
  pageText,
  pageWords,
  watchPassageRoot,
} from "/runtime/passages.js";

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

test("the runtime's chrome repainting is not a change to what the page says", () => {
  document.body.innerHTML =
    '<main><p>Alpha beta</p></main><div class="lf-ui" id="panel"><p>Panel</p></div>';
  const first = pageText();
  assert.doesNotMatch(first.raw, /Panel/);
  // The panel, the banner and the shortcut bar re-render on nearly every gesture — a drag
  // on a large page wrote dozens of records, all under `.lf-ui`. The reading skips those
  // words, so their churn is no reason to walk the page again.
  const panel = document.querySelector("#panel");
  panel.innerHTML = "<p>Panel again</p><button>Reply</button>";
  panel.querySelector("p").firstChild.data = "Panel once more";
  panel.querySelector("button").setAttribute("data-lf-gen", "");
  panel.querySelector("button").classList.add("lf-ui");
  // Chrome the runtime writes into the page's own blocks — a comment count — is chrome too.
  document
    .querySelector("main p")
    .insertAdjacentHTML("beforeend", '<span class="lf-ui">1 comment</span>');
  assert.equal(pageText(), first, "chrome-only changes leave the reading standing");
});

test("a label declared inside the chrome is the page's, arriving and leaving", () => {
  document.body.innerHTML =
    '<main><p>Alpha</p></main><div class="lf-ui" id="panel"></div>';
  pageText();
  const panel = document.querySelector("#panel");
  panel.insertAdjacentHTML("beforeend", '<span data-lf-said="label">Tab</span>');
  assert.match(pageText().raw, /Tab/, "a label is read wherever it stands");
  panel.querySelector("span").removeAttribute("data-lf-said");
  assert.doesNotMatch(
    pageText().raw,
    /Tab/,
    "and is chrome again once it stops being one",
  );
});

// The two inputs the document reports nothing about. An observer sees neither a set the
// runtime marks a widget's parts into nor a tree behind a shadow boundary, so each has a
// door in passages.js, and a door that stopped forgetting would leave the reading standing
// over words the page no longer says — with nothing else to catch it.
test("a widget fenced after a reading was taken is in the next one", () => {
  document.body.innerHTML =
    "<main><p>Alpha</p><lf-fenced><p>Beta</p></lf-fenced></main>";
  const past = (reading) =>
    neighbourhood(reading.origin, reading.fences, "Alpha".length, 8, false);
  assert.match(past(pageText()), /Beta/, "unfenced, the widget's words are page prose");
  // Marking the parts changes no node, so a reading taken before the marking would let a
  // quote from the paragraph above run straight into the widget's lines.
  fencePassageParts(document.querySelector("lf-fenced"));
  assert.equal(past(pageText()), "", "the fence ends the paragraph's neighbourhood");
});

test("a declared shadow tree's words are read, and its changes are seen", () => {
  Object.assign(registry, {
    "lf-staged": { "x-shadow": true },
    $layer: { generation: "passage-doors" },
  });
  document.body.innerHTML = "<main><p>Alpha</p><lf-staged></lf-staged></main>";
  const root = document.querySelector("lf-staged").attachShadow({ mode: "open" });
  root.append(Object.assign(document.createElement("p"), { textContent: "Beta" }));
  // Attaching the root and filling it reached no node the document observes.
  watchPassageRoot(root);
  assert.match(pageText().raw, /Alpha.*Beta/s);
  // And the door leaves the tree watched, rather than forgetting the reading once.
  root.firstElementChild.textContent = "Gamma";
  assert.match(pageText().raw, /Alpha.*Gamma/s);
});
