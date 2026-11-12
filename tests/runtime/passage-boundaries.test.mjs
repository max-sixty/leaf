import "/runtime/stage-integration.js";
/* Which layer a node stands in, read across the boundaries a shadow root draws, and
   when the page's one reading of those layers may change.

   `closest` stops at the root it is called on, so a node inside a declared tree would
   read as standing outside the chrome its host sits in. Crossing back to the host is
   what makes one answer serve both trees, and it is the reading `inChrome` and
   `pageWords` are built on.

   `pageText()` is the whole of that reading. Every caller shares one answer for as long as
   the page holds still, and something the reading is built out of moving is what makes the
   next caller pay for a walk. The document reports most of that movement itself; the two
   inputs it reports nothing about have a door apiece, and the cases after those are why.
   The walk carries each layer down the tree rather than climbing to it from every word,
   and the last cases hold it to where a climb would have answered: at a shadow root, at
   a slot, and on the way back from a position in the reading to its node. */

import { programmaticSelection, selectEnds } from "/runtime/native-selection.js";
import assert from "node:assert/strict";
import test from "node:test";
import v8 from "node:v8";
import vm from "node:vm";

import { registry } from "/runtime/registry.js";
import {
  blockAt,
  closestAcross,
  contextAround,
  documentOutline,
  elementReading,
  fencePassageParts,
  findEach,
  findQuote,
  inChrome,
  neighbourhood,
  pageReadingVersion,
  pageText,
  pageBlocks,
  pageWords,
  pointAt,
  quoteFrom,
  quotesChanged,
  refuseBareText,
  runsIntoLine,
  says,
  segmentsIn,
  trackQuotes,
} from "/runtime/passages.js";
import { declaredRoot, upFrom } from "/runtime/shadow.js";
import { adoptShadowStage, shadowStage } from "/runtime/shadow-stage.js";

test("no node means no passage location, rather than a runtime error", () => {
  assert.equal(closestAcross(null, "main"), null);
  assert.equal(closestAcross(undefined, "main"), null);
});

test("a title's line and a quote across its end read one phrasing rule", () => {
  // Where a title meets the next words inside an element a line runs through, it runs
  // into that line (`runsIntoLine`), and a quote across the edge reads with a space or
  // without (`scan`); where the next words stand in an element outside phrasing, the
  // title ends its line and the edge is a gap a quote must keep.
  document.body.innerHTML =
    '<main><p id="inline"><strong>Title</strong><span>words follow</span></p>' +
    '<div id="block"><strong>Heading</strong><div>words below</div></div></main>';
  const inline = /** @type {Element} */ (document.getElementById("inline"));
  const block = /** @type {Element} */ (document.getElementById("block"));
  const title = (/** @type {Element} */ el) =>
    /** @type {Element} */ (el.querySelector("strong"));
  assert.equal(runsIntoLine(title(inline), inline), true);
  assert.equal(runsIntoLine(title(block), block), false);
  const reading = pageText();
  for (const quote of ["Title words", "Titlewords"])
    assert.equal(quoteFrom(findQuote(reading, quote, {}, inline)), "Titlewords", quote);
  assert.equal(
    quoteFrom(findQuote(reading, "Heading words", {}, block)),
    "Heading words",
  );
  assert.deepEqual(findQuote(reading, "Headingwords", {}, block), []);
});

test("a text node answers from the element holding it", () => {
  document.body.innerHTML = "<main><p>Words</p></main>";
  const words = document.querySelector("p").firstChild;
  assert.equal(closestAcross(words, "main"), document.querySelector("main"));
});

test("a document host value does not become a shadow-tree ancestor", () => {
  document.body.innerHTML = "<main><p>Words</p></main>";
  Object.defineProperty(document, "host", {
    configurable: true,
    value: "external.example",
  });
  try {
    assert.equal(says(document), "Words");
  } finally {
    delete document.host;
  }
});

// A detached subtree's root is an element, and an <a> or <area> has a `host` of its own:
// its URL's. All pages' other-page rows are such links, and the reading watcher
// climbs from the one a removal record names once it has left.
test("a detached link's URL host is not a shadow-tree ancestor", () => {
  document.body.innerHTML =
    '<main><a href="http://127.0.0.1:44276/other"><span>Row</span></a></main>';
  const link = document.querySelector("a");
  const inside = link.querySelector("span");
  link.remove();
  assert.equal(link.host, "127.0.0.1:44276", "the case needs a link with a host");
  assert.equal(upFrom(link), null);
  assert.equal(closestAcross(inside, "main"), null);
});

test("a link leaving the page after losing its words is a change the reading takes", () => {
  document.body.innerHTML =
    '<main><p>Kept</p><a href="http://127.0.0.1:44276/other"><span>Row</span></a></main>';
  assert.equal(pageText().raw.includes("Row"), true);
  // One step, as a re-render takes it: the row is emptied and removed before the
  // watcher reads either record, so the first names a link already detached.
  const link = document.querySelector("a");
  link.firstChild.remove();
  link.remove();
  assert.equal(pageText().raw, "Kept");
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

test("a root handed in reads as it would inside the walk: a slot its assignment", () => {
  document.body.innerHTML = '<main><div id="host"><p>Assigned words</p></div></main>';
  const host = document.querySelector("#host");
  host.attachShadow({ mode: "open" }).innerHTML =
    "<h2>Title</h2><slot>Fallback words</slot>";
  assert.equal(says(host.shadowRoot.querySelector("slot")), "Assigned words");
});

test("header and footer passages belong to the page while runtime surfaces do not", () => {
  document.body.innerHTML = `<header><p>Opening</p></header><main><p>Content</p></main>
    <footer><p>Closing</p></footer>
    <div class="lf-chrome"><p data-lf-said>Thread words</p></div>
    <div data-lf-runtime><p>Status words</p></div>`;
  const words = pageText().raw;
  for (const word of ["Opening", "Content", "Closing"]) assert.ok(words.includes(word));
  assert.ok(!words.includes("Thread words"));
  assert.ok(!words.includes("Status words"));
  assert.equal(says(document.body), "Opening Content Closing");
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

test("projected rows have separate passages inside one text block", () => {
  document.body.innerHTML =
    '<main><pre><span id="first">First <b>row</b></span>' +
    '<span id="second">Second row</span></pre></main>';
  const pre = document.querySelector("pre");
  const first = document.querySelector("#first");
  const second = document.querySelector("#second");
  assert.deepEqual(
    pageBlocks(() => true),
    [pre],
  );
  for (const row of [first, second]) {
    row.dataset.lfProjection = "source";
    row.dataset.lfDatum = row.id;
  }
  assert.deepEqual(
    pageBlocks(() => true),
    [first, second],
  );
  assert.equal(blockAt(first.querySelector("b").firstChild), first);
  assert.equal(says(pre), "First rowSecond row");
  first.removeAttribute("data-lf-datum");
  assert.deepEqual(
    pageBlocks(() => true),
    [pre, second],
  );
  second.removeAttribute("data-lf-projection");
  assert.deepEqual(
    pageBlocks(() => true),
    [pre],
  );
});

test("projecting an inline value preserves its typography and resolved quote", () => {
  document.body.innerHTML = "<main><p>The rate is <span><b>42</b>%</span>.</p></main>";
  const paragraph = document.querySelector("p");
  const value = document.querySelector("span");
  assert.equal(says(paragraph), "The rate is 42%.");
  value.dataset.lfGen = "1";
  value.dataset.lfProjection = "source";
  value.dataset.lfDatum = "rate";
  assert.deepEqual(
    pageBlocks(() => true),
    [paragraph, value],
  );
  assert.equal(says(paragraph), "The rate is 42%.");
  assert.equal(quoteFrom(findQuote(pageText(), "42%", {}, value)), "42%");
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
  assert.equal(pageText(), first, "a painted class leaves the reading unchanged");
});

test("the runtime's chrome repainting is not a change to what the page says", () => {
  document.body.innerHTML =
    '<main><p>Alpha beta</p></main><div class="lf-ui" id="panel"><p>Panel</p></div>';
  const first = pageText();
  assert.doesNotMatch(first.raw, /Panel/);
  // The floating panel re-renders on nearly every gesture — a drag on a large page
  // wrote dozens of records, all under `.lf-ui`. The reading skips those
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
  assert.equal(pageText(), first, "chrome-only changes leave the reading unchanged");
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
// door in passages.js, and a door that stopped forgetting would leave the reading unchanged
// over words the page no longer says — with nothing else to catch it.
test("a widget fenced after a reading was taken is in the next one", () => {
  document.body.innerHTML =
    "<main><p>Alpha</p><lf-fenced><p>Beta</p></lf-fenced></main>";
  const past = (reading) => neighbourhood(reading, "Alpha".length, 8, false);
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
  // Staging the root and filling it reaches no node the document observes.
  const root = shadowStage(document.querySelector("lf-staged"), [
    Object.assign(document.createElement("p"), { textContent: "Beta" }),
  ]);
  assert.match(pageText().raw, /Alpha.*Beta/s);
  // And the door leaves the tree watched, rather than forgetting the reading once.
  root.querySelector("p").textContent = "Gamma";
  assert.match(pageText().raw, /Alpha.*Gamma/s);
});

test("each document's reading is forgotten alone: the page's and a reply's", () => {
  Object.assign(registry, {
    "lf-staged": { "x-shadow": true },
    $layer: { generation: "passage-documents" },
  });
  document.body.innerHTML = "<main><p>Alpha</p></main>";
  const chrome = document.createElement("div");
  chrome.className = "lf-chrome";
  chrome.innerHTML = `<div class="lf-msg lf-ui" data-lf-gen="1"><div class="lf-msg-body">
    <lf-staged></lf-staged></div></div>`;
  document.documentElement.append(chrome);
  try {
    const root = shadowStage(chrome.querySelector("lf-staged"), [
      Object.assign(document.createElement("p"), { textContent: "Reply words." }),
    ]);
    const page = pageText();
    // A reply is a document of its own, so its widget redrawing is no change to the page.
    root.querySelector("p").textContent = "Reply changed.";
    assert.equal(pageText(), page);
    // A root the watcher already sees reports its own changes, as a reply's diff is
    // adopted again when its module loads.
    adoptShadowStage(root);
    assert.equal(pageText(), page);
    // And the page changing is no change to the reply, whose own change is.
    const body = chrome.querySelector(".lf-msg-body");
    const outline = documentOutline(body);
    document.querySelector("main p").textContent = "Beta";
    assert.equal(documentOutline(body), outline);
    root.querySelector("p").textContent = "Reply changed again.";
    assert.notEqual(documentOutline(body), outline);
  } finally {
    chrome.remove();
  }
});

// A key naming a reading, and what a reader kept about an element still on the page,
// outlive the reading they were taken under, so they hold nothing of it: a session that
// reads its page again and again would otherwise keep every reading it forgot.
test("a forgotten reading is held by no key or kept answer that outlives it", async () => {
  v8.setFlagsFromString("--expose-gc");
  const collect = vm.runInNewContext("gc");
  document.body.innerHTML = '<main><p id="kept">Alpha</p><p id="other">Beta</p></main>';
  const forgotten = new WeakRef(pageText());
  const version = pageReadingVersion();
  assert.equal(elementReading(document.getElementById("kept")), "Alpha");
  /** @type {HTMLElement} */ (document.getElementById("other")).textContent = "Gamma";
  assert.notEqual(pageReadingVersion(), version);
  await new Promise((done) => setTimeout(done));
  collect();
  assert.equal(forgotten.deref(), undefined);
});

// Startup refuses a module's bare text before anything reads the page, so it has to
// reach every root the reading would cross into, a stage inside another stage included.
test("startup refuses bare text staged inside another widget's root", () => {
  Object.assign(registry, {
    "lf-staged": { "x-shadow": true },
    $layer: { generation: "passage-nested-bare" },
  });
  document.body.innerHTML = "<main><lf-staged id=outer></lf-staged></main>";
  const inner = Object.assign(document.createElement("lf-staged"), { id: "inner" });
  const outer = shadowStage(document.getElementById("outer"), [inner]);
  shadowStage(inner, [document.createTextNode("Loose words")]);
  /** @type {string[]} */
  const reasons = [];
  /** @param {Event} event */
  const failed = (event) => reasons.push(event.detail.reason);
  window.addEventListener("lf-startup-failed", failed);
  try {
    refuseBareText();
  } finally {
    window.removeEventListener("lf-startup-failed", failed);
  }
  assert.equal(reasons.length, 1, String(reasons));
  assert.match(reasons[0], /<lf-staged id="inner"> staged bare text/);
  assert.equal(declaredRoot(outer.host), outer, "the outer stage holds an element");
  assert.equal(declaredRoot(inner), null, "the inner stage is refused for good");
});

// The sweep runs before every page upgrades, so it asks each stage once rather than
// filtering every stage for each root it admits, which grew with the square of a page of
// sibling widgets.
test("startup's refusal sweep asks each of many sibling stages once", () => {
  Object.assign(registry, {
    "lf-staged": { "x-shadow": true },
    $layer: { generation: "passage-flat-sweep" },
  });
  const count = 200;
  document.body.innerHTML = `<main>${"<lf-staged></lf-staged>".repeat(count)}</main>`;
  for (const host of document.querySelectorAll("lf-staged"))
    shadowStage(host, [document.createElement("p")]);
  const { contains } = Node.prototype;
  let checks = 0;
  /** @param {Node | null} other */
  Node.prototype.contains = function (other) {
    checks += 1;
    return contains.call(this, other);
  };
  try {
    refuseBareText();
  } finally {
    Node.prototype.contains = contains;
  }
  assert.ok(checks <= count, `${checks} containment checks for ${count} stages`);
});

// A page script's own custom element attaches a root no declaration vouches for. The
// file reading can't know a script will, so the page reading leaves the root's words out
// and reads the host by its light children, slotted or not, exactly as the file does.
test("an undeclared shadow tree is opaque, and its host reads by its children", () => {
  Object.assign(registry, { $layer: { generation: "passage-undeclared-root" } });
  document.body.innerHTML =
    '<main><p>Before</p><author-card><span slot="lead">Lead</span>Loose</author-card>' +
    "<p>After</p></main>";
  document.querySelector("author-card").attachShadow({ mode: "open" }).innerHTML =
    '<h3>Shadow</h3><slot name="lead"></slot>';
  assert.equal(pageText().raw.replace(/\0+/g, " "), "Before Lead Loose After");
});

// The walk carries what it knows down the tree rather than climbing from each word, so
// the places where a climb would have stopped are where a carried context has to start
// over: `closest` stops at a shadow root, and a slotted node reads where its host
// stands, not where its slot does.
test("chrome over a declared tree stops at its root, and not for what it slots", () => {
  Object.assign(registry, {
    "lf-staged": { "x-shadow": true },
    $layer: { generation: "passage-contexts" },
  });
  document.body.innerHTML =
    '<main><p>Page</p></main><div class="lf-ui"><lf-staged></lf-staged></div>';
  const host = document.querySelector("lf-staged");
  const staged = document.createElement("template");
  staged.innerHTML = "<p>Staged</p><p><slot></slot></p>";
  shadowStage(host, [...staged.content.childNodes]);
  // The stage clears light children, so what a slot takes arrives after it.
  host.innerHTML = "<b>Slotted</b> loose";
  assert.match(host.textContent, /Slotted loose/);
  const raw = pageText().raw;
  assert.match(raw, /Staged/, "the chrome above the host is not the tree's");
  assert.doesNotMatch(
    raw,
    /Slotted|loose/,
    "a slotted word stands in its host's chrome",
  );
});

test("a line break assigned to a shadow slot separates its words", () => {
  Object.assign(registry, {
    "lf-staged": { "x-shadow": true },
    $layer: { generation: "passage-slotted-break" },
  });
  document.body.innerHTML = "<main><lf-staged></lf-staged></main>";
  const host = document.querySelector("lf-staged");
  const staged = document.createElement("template");
  staged.innerHTML = "<p><slot></slot></p>";
  shadowStage(host, [...staged.content.childNodes]);
  // The stage clears light children, so what a slot takes arrives after it.
  host.innerHTML = "Alpha<br>Beta";
  assert.equal(says(host.shadowRoot), "Alpha Beta");
  assert.equal(pageText().raw, "Alpha Beta");
});

// What a slot takes is drawn among the words around the slot, so it runs into them as the
// words of a span would; a widget's own words stand apart from those beside it.
test("words a slot draws run into the words around the slot", () => {
  Object.assign(registry, {
    "lf-staged": { "x-shadow": true },
    $layer: { generation: "passage-slotted-words" },
  });
  document.body.innerHTML = "<main><p>Before<lf-staged></lf-staged>after</p></main>";
  const host = document.querySelector("lf-staged");
  const staged = document.createElement("template");
  staged.innerHTML = "<span>alpha<slot></slot>gamma</span>";
  shadowStage(host, [...staged.content.childNodes]);
  host.innerHTML = "<em>beta</em>";
  assert.equal(says(host.shadowRoot), "alphabetagamma");
  assert.equal(pageText().raw.replaceAll("\u0000", ""), "Before alphabetagamma after");
});

test("a selection in nested slots keeps exactly the rendered words it covers", () => {
  Object.assign(registry, {
    "lf-staged": { "x-shadow": true },
    $layer: { generation: "passage-nested-slots" },
  });
  document.body.innerHTML =
    '<main><p id="before">Before</p><lf-staged id="outer"></lf-staged>' +
    '<p id="after">After</p></main>';
  const stage = (host, label) => {
    const template = document.createElement("template");
    template.innerHTML = `<p>${label}</p><slot></slot><p>${label} tail</p>`;
    return shadowStage(host, [...template.content.childNodes]);
  };
  const outer = document.querySelector("#outer");
  const outerRoot = stage(outer, "Outer");
  const inner = document.createElement("lf-staged");
  outer.append(inner);
  const innerRoot = stage(inner, "Inner");
  inner.innerHTML = '<p id="words">Selected words</p>';
  const words = inner.querySelector("p");
  // happy-dom distributes assignedNodes but has no assignedSlot getter.
  // State the ancestry the native browser gives these same nodes.
  Object.defineProperty(inner, "assignedSlot", {
    value: outerRoot.querySelector("slot"),
  });
  Object.defineProperty(words, "assignedSlot", {
    value: innerRoot.querySelector("slot"),
  });
  assert.equal(
    quoteFrom(pageText().segments),
    "Before Outer Inner Selected words Inner tail Outer tail After",
  );
  const range = document.createRange();
  range.selectNodeContents(words);
  assert.equal(quoteFrom(segmentsIn(range)), "Selected words");
  range.setStart(words.firstChild, 3);
  range.setEnd(words.firstChild, 8);
  assert.equal(quoteFrom(segmentsIn(range)), "ected");
  range.setStart(document.querySelector("#before").firstChild, 0);
  range.setEnd(words.firstChild, words.textContent.length);
  assert.equal(quoteFrom(segmentsIn(range)), "Before Outer Inner Selected words");
  range.setStart(words.firstChild, 0);
  range.setEnd(document.querySelector("#after").firstChild, 5);
  assert.equal(
    quoteFrom(segmentsIn(range)),
    "Selected words Inner tail Outer tail After",
  );
  range.selectNode(outer);
  assert.equal(
    quoteFrom(segmentsIn(range)),
    "Outer Inner Selected words Inner tail Outer tail",
  );
  range.selectNodeContents(innerRoot.querySelector("p"));
  assert.equal(quoteFrom(segmentsIn(range)), "Inner");
  // Ends at the far edge of one text node and the near edge of another cover neither.
  range.setStart(document.querySelector("#before").firstChild, "Before".length);
  range.setEnd(document.querySelector("#after").firstChild, 0);
  assert.equal(
    quoteFrom(segmentsIn(range)),
    "Outer Inner Selected words Inner tail Outer tail",
  );
  // Select-all beside a declared tree composes a range over <html>.
  range.selectNodeContents(document.documentElement);
  assert.equal(
    quoteFrom(segmentsIn(range)),
    "Before Outer Inner Selected words Inner tail Outer tail After",
  );
});

// A page script's own element whose slots show its children out of light order, with
// words only its shadow root shows. The reading and a native Range both take its children
// in light order, so a selection is compared in that order rather than the one on screen.
test("a selection in an undeclared host that reorders its children keeps its words", () => {
  Object.assign(registry, { $layer: { generation: "passage-undeclared-order" } });
  document.body.innerHTML =
    '<main><p id="before">Before</p><u-card><p slot="body" id="body">Body</p>' +
    '<p slot="title" id="title">Title</p></u-card><p id="after">After</p></main>';
  const root = document.querySelector("u-card").attachShadow({ mode: "open" });
  root.innerHTML =
    '<h3 id="own">Own</h3><div id="holder"><slot name="title"></slot></div>' +
    '<slot name="body"></slot>';
  assert.equal(quoteFrom(pageText().segments), "Before Body Title After");
  const range = document.createRange();
  const text = (id) => document.querySelector(`#${id}`).firstChild;
  for (const id of ["before", "body", "title", "after"]) {
    range.selectNodeContents(text(id));
    assert.equal(quoteFrom(segmentsIn(range)), text(id).data, `text of ${id}`);
    range.selectNodeContents(document.querySelector(`#${id}`));
    assert.equal(quoteFrom(segmentsIn(range)), text(id).data, `contents of ${id}`);
  }
  range.setStart(text("body"), 0);
  range.setEnd(text("title"), 5);
  assert.equal(quoteFrom(segmentsIn(range)), "Body Title");
  range.setStart(text("title"), 0);
  range.setEnd(text("after"), 5);
  assert.equal(quoteFrom(segmentsIn(range)), "Title After");
  // Firefox keeps both ends of a selection of the root's own words inside the root, even
  // around a slot, and comments can't quote those words.
  range.selectNodeContents(root.querySelector("#own"));
  assert.deepEqual(segmentsIn(range), []);
  range.selectNodeContents(root.querySelector("#holder"));
  assert.deepEqual(segmentsIn(range), []);
});

// `segmentsIn` searches the reading, so every way the walk reaches a word has to agree
// with the comparison the search asks: a declared root's slots, nested and out of light
// order, an undeclared root's reordering slots, and a declared host's child no slot takes.
// A range from any word to any later one covers exactly the reading's words between them.
test("the reading's words stand in the order a selection is compared in", () => {
  Object.assign(registry, {
    "lf-staged": { "x-shadow": true },
    $layer: { generation: "passage-reading-order" },
  });
  const nodes = (html) => {
    const template = document.createElement("template");
    template.innerHTML = html;
    return [...template.content.childNodes];
  };
  document.body.innerHTML =
    "<main><p>Lead</p><lf-staged id=outer></lf-staged><lf-staged id=named></lf-staged>" +
    "<u-card><p slot=body>Card body</p><p slot=title>Card title</p></u-card>" +
    "<p>Last</p></main>";
  const outer = document.querySelector("#outer");
  shadowStage(outer, nodes("<p>Outer</p><slot></slot><p>Outer tail</p>"));
  const inner = document.createElement("lf-staged");
  outer.append(inner);
  shadowStage(inner, nodes("<p>Inner</p><div><slot></slot></div><p>Inner tail</p>"));
  inner.innerHTML = "<p>Deep <b>bold</b> words</p>";
  const named = document.querySelector("#named");
  shadowStage(
    named,
    nodes('<slot name="b"></slot><p>Named middle</p><slot name="a"></slot>'),
  );
  named.innerHTML = '<p slot="a">Slot a</p><p>Unslotted</p><p slot="b">Slot b</p>';
  document.querySelector("u-card").attachShadow({ mode: "open" }).innerHTML =
    '<slot name="title"></slot><slot name="body"></slot>';
  const { segments } = pageText();
  assert.equal(
    quoteFrom(segments),
    "Lead Outer Inner Deep bold words Inner tail Outer tail Slot b Named middle Slot a " +
      "Card body Card title Last",
  );
  segments.forEach(({ node: from }, start) => {
    for (let stop = start; stop < segments.length; stop++) {
      const to = segments[stop].node;
      // A live Range collapses when its ends are in two trees, and a StaticRange doesn't.
      const range = {
        startContainer: from,
        startOffset: 0,
        endContainer: to,
        endOffset: to.data.length,
      };
      assert.equal(
        quoteFrom(segmentsIn(range)),
        quoteFrom(segments.slice(start, stop + 1)),
        `from "${from.data}" to "${to.data}"`,
      );
    }
  });
});

// A selection covers one run of the page reading's segments, so it is found by searching
// for where its two ends fall rather than by testing every segment. Every comparison
// starts by asking a text node for its slot, so counting those asks counts the
// comparisons.
test("a selection's words are found from its ends, not by asking every word", () => {
  document.body.innerHTML = `<main>${Array.from(
    { length: 4096 },
    (_, i) => `<p id="row${i}">Row ${i}</p>`,
  ).join("")}</main>`;
  pageText();
  const row = document.querySelector("#row2000");
  const range = document.createRange();
  range.selectNodeContents(row);
  const slot = Object.getOwnPropertyDescriptor(Text.prototype, "assignedSlot");
  let asked = 0;
  Object.defineProperty(Text.prototype, "assignedSlot", {
    configurable: true,
    get() {
      asked += 1;
      return slot.get.call(this);
    },
  });
  try {
    assert.equal(quoteFrom(segmentsIn(range)), "Row 2000");
  } finally {
    Object.defineProperty(Text.prototype, "assignedSlot", slot);
  }
  assert.ok(asked < 200, `${asked} text nodes asked where they render`);
});

test("a declared label inside chrome is read down to its last word", () => {
  document.body.innerHTML =
    '<main><p>Page</p></main><div class="lf-ui"><span data-lf-said="tab"><b>Tab</b> label</span></div>';
  assert.match(pageText().raw, /Tab.*label/s);
});

// A reading rooted at a shadow tree starts where its host stands: the tree renders at
// the host's place, inside the host's block, so two spans in it are one run of words.
test("a reading rooted at a shadow tree reads in its host's block", () => {
  document.body.innerHTML =
    '<main><p>Rate <lf-rated id="rate"></lf-rated> today</p></main>';
  const root = document.querySelector("#rate").attachShadow({ mode: "open" });
  root.innerHTML = "<span>12</span><span>%</span>";
  assert.equal(says(root), "12%");
});

// Every position in the reading leads back to the character it came from, and what
// stands between text nodes, which holds none of theirs, leads nowhere: an edge between
// inline elements, or the space a block's end reads as.
test("a reading's positions lead back to their nodes", () => {
  document.body.innerHTML = "<main><p>Al<em></em><b>pha</b></p><p>beta</p></main>";
  document.querySelector("em").append(document.createTextNode(""));
  const reading = pageText();
  assert.equal(reading.raw, "Al\u0000\u0000pha beta");
  for (let i = 0; i < reading.raw.length; i++) {
    const at = pointAt(reading, i);
    const edge = reading.raw[i] === "\u0000" || i === "Al\u0000\u0000pha".length;
    assert.equal(at === null, edge, `${edge ? "edge" : "character"} at ${i}`);
    if (!edge)
      assert.equal(at.node.data[at.offset], reading.raw[i], `character at ${i}`);
  }
  assert.equal(pointAt(reading, -1) === null, true);
  assert.equal(pointAt(reading, reading.raw.length) === null, true);
});

// A quote's copies are told apart by the words beside each, and only those are read: a
// run of whitespace before them, however long, is not read again to learn whether the
// first of them follows a space.
test("telling a quote's copies apart reads only around them", () => {
  document.body.innerHTML = "<main><p></p></main>";
  const line = document.querySelector("p");
  line.textContent = `a${" ".repeat(1_000_000)}${"x".repeat(256)} MARK ${"y".repeat(256)} MARK ${"z".repeat(256)}`;
  const reading = pageText();
  const node = line.firstChild;
  const data = node.data;
  // A search reads a node's words as slices of its data, so the slices are what it read.
  let read = 0;
  Object.defineProperty(node, "data", {
    configurable: true,
    get: () => ({
      slice: (/** @type {number} */ start, /** @type {number} */ end) => {
        const part = data.slice(start, end);
        read += part.length;
        return part;
      },
    }),
  });
  try {
    const found = findQuote(reading, "MARK", {
      prefix: "y".repeat(24),
      suffix: "z".repeat(24),
    });
    assert.equal(found[0]?.start, data.lastIndexOf("MARK"), "the second copy");
  } finally {
    delete node.data;
  }
  assert.ok(read < 10_000, `${read} characters read to tell two copies apart`);
});

// The index of quotes carries each quote's copies from one reading to the next through
// the span the two differ in, and searches only there. Whatever a change does — writes
// words into a copy or puts them back, writes a second copy, makes or removes a fence
// inside one, replaces a node with the same words, or writes into a shadow stage a
// passage runs into — a carried quote answers as a pass over the page afresh does, which
// a quote the index doesn't keep is found by (a key with a space before it names the
// same words). And the quotes it says changed are those whose answer did, and only
// those a change came near.
test("a kept quote answers each change as a fresh pass over the page does", () => {
  Object.assign(registry, {
    "lf-staged": { "x-shadow": true },
    $layer: { generation: "quote-index" },
  });
  document.body.innerHTML =
    '<main><p id="a">Alpha beta gamma.</p><p id="b">Delta <span id="s">epsilon ' +
    'zeta</span> eta theta.</p><p id="c">Iota kappa.</p><div id="d"><p>Lambda mu' +
    "</p><lf-staged><p>nu xi omicron.</p></lf-staged></div><p>Pi rho.</p></main>";
  const stage = shadowStage(document.querySelector("lf-staged"), [
    ...document.querySelector("lf-staged").childNodes,
  ]);
  const [a, b, c, s] = ["#a", "#b", "#c", "#s"].map((at) => document.querySelector(at));
  const quotes = [
    "beta gamma",
    "epsilon zeta eta",
    "Delta epsilon",
    "kappa",
    "gamma. Delta",
    "mu nu xi",
    "Pi rho.",
  ];
  trackQuotes(quotes);
  let seen = quotesChanged(0).version;
  // Each answer as the text nodes it stands in, by name, and its offsets in them.
  const names = new Map();
  const answer = (/** @type {string} */ quote) =>
    findQuote(pageText(), quote, {})
      .map(({ node, start, end }) => {
        if (!names.has(node)) names.set(node, names.size);
        return `${names.get(node)}:${start}-${end}`;
      })
      .join(" ");
  /** @type {[string, () => void, string[]][]} */
  const steps = [
    [
      "words written into a copy",
      () => (a.firstChild.data = "Alpha beta"),
      ["beta gamma", "gamma. Delta"],
    ],
    [
      "the words put back",
      () => (a.firstChild.data = "Alpha beta gamma."),
      ["beta gamma", "gamma. Delta"],
    ],
    ["a second copy", () => c.append(" beta gamma"), ["beta gamma"]],
    ["the second copy taken out", () => c.lastChild.remove(), ["beta gamma"]],
    [
      "a fence inside a copy",
      () => (s.contentEditable = "true"),
      ["epsilon zeta eta", "Delta epsilon"],
    ],
    [
      "the fence taken out",
      () => s.removeAttribute("contenteditable"),
      ["epsilon zeta eta", "Delta epsilon"],
    ],
    [
      "a node replaced by the same words",
      () => b.replaceChild(document.createTextNode("Delta "), b.firstChild),
      ["Delta epsilon", "gamma. Delta"],
    ],
    [
      "a word inside a stage",
      () => stage.querySelector("p").prepend("Inserted "),
      ["mu nu xi"],
    ],
    [
      "the word taken out",
      () => stage.querySelector("p").firstChild.remove(),
      ["mu nu xi"],
    ],
  ];
  for (const [change, step, near] of steps) {
    const before = quotes.map(answer);
    step();
    const after = quotes.map(answer);
    assert.deepEqual(
      after,
      quotes.map((quote) => answer(` ${quote}`)),
      change,
    );
    const { version, quotes: changed } = quotesChanged(seen);
    seen = version;
    for (const [at, quote] of quotes.entries())
      if (before[at] !== after[at])
        assert.ok(changed.includes(quote), `${change}: ${quote} changed`);
    for (const quote of changed) assert.ok(near.includes(quote), `${change}: ${quote}`);
  }
  assert.ok(answer("beta gamma") && answer("mu nu xi"));
  trackQuotes([]);
});

// The margin keys each passage by how many copies of its words stand before it, and finds
// every copy of every passage's words in a block by one pass over it: overlapping copies
// included, and strings that start alike for longer than their first hash told apart.
test("one pass over a text finds every place each string starts", () => {
  const long = "Row of the table that starts alike: ";
  const text = `aaaa ab aab ${long}one; ${long}two; 😀a😀a`;
  const found = findEach(text, [
    "aa",
    "ab",
    `${long}two`,
    `${long}one`,
    "😀a",
    "zz",
    "",
  ]);
  const expected = (/** @type {string} */ string) => {
    const places = [];
    for (
      let at = string ? text.indexOf(string) : -1;
      at !== -1;
      at = text.indexOf(string, at + 1)
    )
      places.push(at);
    return places;
  };
  for (const [string, places] of found)
    assert.deepEqual(places, expected(string), string);
  assert.deepEqual(found.get("aa"), [0, 1, 2, 8]);
});

// Strings that share a long start, as quotes of a list's rows do, whether they share a
// length or come in as many lengths as there are strings, are found by one pass over the
// text whose work grows with the text and the strings' total length, not with how many
// strings start alike: each step of the pass is a lookup or two of the automaton's
// transitions, counted here.
test("strings sharing a long start cost the text and their own length", () => {
  const shared = "Row of a long list that every quote here starts with alike, ".repeat(
    5,
  );
  const shapes = {
    "one length": Array.from(
      { length: 400 },
      (_, n) => `${shared}${String(n).padStart(3, "0")}`,
    ),
    "a length each": Array.from(
      { length: 400 },
      (_, n) => `${"x".repeat(16 + n)}${String(n).padStart(4, "0")}!`,
    ),
  };
  const get = Map.prototype.get;
  for (const [shape, strings] of Object.entries(shapes)) {
    const text = strings.join(" ");
    let lookups = 0;
    Map.prototype.get = function (key) {
      lookups += 1;
      return get.call(this, key);
    };
    /** @type {Map<string, number[]>} */
    let found;
    try {
      found = findEach(text, strings);
    } finally {
      Map.prototype.get = get;
    }
    assert.deepEqual(
      strings.map((string) => found.get(string)),
      strings.map((string) => [text.indexOf(string)]),
      shape,
    );
    const letters = strings.reduce((sum, string) => sum + string.length, 0);
    assert.ok(lookups <= 4 * (text.length + letters), `${shape}: ${lookups} lookups`);
  }
});

// A repeated quote's copies are told apart by the words beside them, so a change there is
// a change to the quote even where no copy moved: the words its resolution read are kept
// with the copy, and a change among them says the quote changed.
test("a change beside a kept quote's copy, where it was told apart, changes the quote", () => {
  document.body.innerHTML =
    '<main><p id="x">one MARK two</p><p id="y">three MARK four</p></main>';
  const anchor = { prefix: "one", suffix: "two" };
  trackQuotes(["MARK"]);
  const { version } = quotesChanged(0);
  assert.equal(findQuote(pageText(), "MARK", anchor)[0]?.node.parentElement?.id, "x");
  document.querySelector("#x").firstChild.data = "uno MARK two";
  assert.ok(quotesChanged(version).quotes.includes("MARK"));
  assert.deepEqual(findQuote(pageText(), "MARK", anchor), []);
  trackQuotes([]);
});

// `says` and `wrote` are two answers for one element, and a kept reading must not hand
// back the other one's.
test("a message's body reads as its own document: the markup and the text alike", () => {
  // The panel draws a reply in generated chrome; the markup its author sent stands in
  // its body beside the text the runtime renders from its words, and both are its
  // writer's.
  document.body.innerHTML = `<main><div class="lf-msg lf-ui" data-lf-gen="1">
    <div class="lf-msg-body"><div class="lf-msg-text"><p id="text">Rendered words.</p></div>
    <section id="markup"><h2>Sent heading</h2><p>Sent words.</p></section>
    </div></div></main>`;
  const markup = document.getElementById("markup");
  assert.equal(elementReading(markup, "wrote"), "Sent heading Sent words.");
  assert.equal(elementReading(markup), "Sent heading Sent words.");
  assert.equal(
    elementReading(document.getElementById("text"), "wrote"),
    "Rendered words.",
  );
  assert.equal(elementReading(document.getElementById("text")), "Rendered words.");
});

test("one element's two readings are kept apart", () => {
  document.body.innerHTML =
    '<main><p id="line">Words <span data-lf-gen="">generated</span></p></main>';
  const line = document.querySelector("#line");
  assert.equal(elementReading(line, "says"), "Words generated");
  assert.equal(elementReading(line, "wrote"), "Words");
  assert.equal(elementReading(line), "Words generated");
});

// A part of the page's reading, read alone, holds what the whole holds under its element:
// chrome inside it is skipped, and an element under chrome or in a runtime surface holds
// none of the page's words, though a reading of its own frame (`says`) would find some.
test("a part of the page's reading says what the whole says there", () => {
  document.body.innerHTML =
    '<main><p>Before</p><lf-w id="w"><div id="row"><p>Row <b>words</b>' +
    '<button class="lf-ui">Chrome</button></p></div></lf-w>' +
    '<div class="lf-ui"><lf-w id="v"><div id="covered"><p>Covered row</p></div></lf-w>' +
    '</div></main><div class="lf-chrome"><lf-w id="m"><div id="message">' +
    "<p>Message row</p></div></lf-w></div>";
  const part = (id) => pageText(document.querySelector(`#${id}`));
  assert.equal(quoteFrom(part("row").segments), "Row words");
  assert.ok(pageText().raw.includes(part("row").raw));
  for (const [id, words] of [
    ["covered", "Covered row"],
    ["message", "Message row"],
  ]) {
    assert.equal(says(document.querySelector(`#${id}`)), words);
    assert.equal(part(id).raw, "", `#${id} holds none of the page's words`);
  }
});

// A display window may be shorter than a word, while stored quote context remains exact.
// Completing rather than dropping that word preserves what distinguishes nearby matches.
test("spoken context completes outer words in its local window", () => {
  document.body.innerHTML =
    "<main><p>Supercalifragilistic Primary <b>Notify me</b> for Backup release.</p></main>";
  const node = document.querySelector("b").firstChild;
  const segments = [{ node, start: 0, end: node.length }];
  assert.deepEqual(contextAround(pageText(), segments, { before: 24, after: 15 }), {
    before: "Supercalifragilistic Primary",
    after: "for Backup release",
  });
  assert.deepEqual(contextAround(pageText(), segments, { before: 0, after: 3 }), {
    before: "",
    after: "for",
  });
});

test("spoken context bounds unspaced languages and oversized tokens", () => {
  for (const context of [
    "这是一个很长的中文段落没有任何空格".repeat(40),
    "a".repeat(3000),
    "a".repeat(80) + " T",
    "a".repeat(90) + " " + "b".repeat(10),
  ]) {
    document.body.innerHTML = `<main><p>${context}<b>needle</b>${context}</p></main>`;
    const node = document.querySelector("b").firstChild;
    const around = contextAround(pageText(), [{ node, start: 0, end: node.length }]);
    assert.ok([...around.before].length <= 56);
    assert.ok([...around.after].length <= 56);
  }
});

// Endpoint equality keeps an asynchronous selectionchange on its writer, but a
// native divergence retires that provenance even when the endpoints return.
test("selection write provenance ends at native divergence", () => {
  document.body.innerHTML = "<main><p>The amber passage keeps its identity.</p></main>";
  const word = document.querySelector("p").firstChild;
  const selection = getSelection();
  selectEnds([word, 4], [word, 9]);
  assert.equal(programmaticSelection(selection), true);
  assert.equal(programmaticSelection(selection), true);
  selection.extend(word, 17);
  assert.equal(programmaticSelection(selection), false);
  selection.extend(word, 9);
  assert.equal(programmaticSelection(selection), false);
});
