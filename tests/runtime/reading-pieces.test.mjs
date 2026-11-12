import "/runtime/stage-integration.js";
/* The page's reading kept in pieces (passages.js, `Piece`): the frame, which is the
   page's words outside its parts with a fence where each part stands, and each datum
   that is a part, read alone. Each kept piece must say what a fresh walk of the page says
   of its words, so each kind of change drops every piece whose words or context it moved,
   and only those: a change inside one part leaves every other part unread. */

import assert from "node:assert/strict";
import test from "node:test";

import { registry } from "/runtime/registry.js";
import {
  documentOutline,
  elementReading,
  fencePassageParts,
  findQuote,
  pageReadingVersion,
  pageText,
  quoteFrom,
  quotesChanged,
  readingElements,
  readingParts,
  says,
  segmentsIn,
  trackQuotes,
} from "/runtime/passages.js";
import { shadowStage } from "/runtime/shadow-stage.js";

let generation = 0;
// A vocabulary no reading has been read against, which forgets every kept piece.
const freshVocabulary = () =>
  Object.assign(registry, {
    "lf-staged": { "x-shadow": true },
    $layer: { generation: `reading-pieces-${(generation += 1)}` },
  });

const datum = (id, inner) =>
  `<div id="${id}" data-lf-projection="w" data-lf-datum="${id}">${inner}</div>`;

// Prose, three parts, a datum standing inside a line (which reads with the line), and a
// declared tree holding two parts whose slots show the host's light children, one of
// them a heading, and a slot outside them that shows a part among those children.
const page = () => {
  freshVocabulary();
  document.body.innerHTML =
    '<main><h1>Title</h1><p id="intro">Intro words before the data</p>' +
    '<section id="s1"><h2>First section</h2>' +
    datum("a", '<p>Alpha one</p><p id="a2">Alpha two</p><br>') +
    '<p id="between" data-lf-projection="w">Between<br></p>' +
    datum(
      "b",
      '<h3>Inside heading</h3><p>Beta one</p><figure aria-label="Figure">' +
        '<figcaption>Caption</figcaption><p id="b2">Beta two</p></figure>',
    ) +
    '<p>Words <span data-lf-projection="w" data-lf-datum="i">inline datum</span> after</p>' +
    datum("c", "<ul><li>Gamma one</li><li>Gamma two</li></ul>") +
    '</section><lf-staged id="host"></lf-staged><p id="outro">Outro</p></main>';
  const host = document.querySelector("#host");
  const staged = document.createElement("template");
  staged.innerHTML =
    datum("s", '<p>Staged <slot name="x"></slot></p><slot name="h"></slot>') +
    datum("t", "<p><slot></slot></p>") +
    '<section id="w"><slot name="p"></slot></section>';
  shadowStage(host, [...staged.content.childNodes]);
  // The stage clears light children, so what its slots take arrives after it.
  host.innerHTML =
    '<b id="slotted" slot="x">Slotted words</b><h4 slot="h">Slotted heading</h4>' +
    '<i id="other">Other</i>' +
    datum("u", '<p id="u1">Shown words</p>').replace("<div ", '<div slot="p" ');
  return host;
};

const FACTS = ["node", "start", "end", "block", "textBlock", "words", "gen"];
// Whether a node stands under a root as the page's words do: a node a slot shows stands
// where the slot does.
const standsUnder = (node, root) => {
  for (let at = node; at; at = at.assignedSlot ?? at.parentNode ?? at.host ?? null)
    if (at === root) return true;
  return false;
};
/** @param {{segments: object[]}} reading */
const facts = (segments) => segments.map((segment) => FACTS.map((key) => segment[key]));
// The kept pieces must say what a fresh walk of the whole page says: the body is no
// part, so its own reading is that walk. The frame holds its words outside the parts,
// with a fence where each part stands, and each datum its words under it.
const assertPieces = (what) => {
  const whole = pageText(document.body);
  const parts = readingParts();
  const inPart = ({ node }) => parts.some((root) => standsUnder(node, root));
  const frame = pageText();
  assert.deepEqual(
    facts(frame.segments),
    facts(whole.segments.filter((segment) => !inPart(segment))),
    `${what}: the frame's words`,
  );
  for (const root of elements().filter((element) => element.matches("[data-lf-datum]")))
    assert.deepEqual(
      facts(pageText(root).segments),
      facts(whole.segments.filter(({ node }) => standsUnder(node, root))),
      `${what}: the words of datum ${root.id}`,
    );
  for (const root of parts) {
    const before = frame.segments.findIndex(
      ({ node }) => root.compareDocumentPosition(node) & 4,
    );
    const at = before < 0 ? frame.raw.length : frame.segments[before].rawStart - 1;
    if (before !== 0)
      assert.ok(
        frame.fences.includes(at),
        `${what}: a fence where part ${root.id} stands`,
      );
  }
  for (const element of document.querySelectorAll("[id]"))
    assert.equal(
      elementReading(element),
      says(element),
      `${what}: #${element.id}'s words`,
    );
  // Every element of the page that matches, each once, the parts' among them. By
  // identity: two elements alike are deeply equal.
  const all = elements();
  const found = readingElements(MATCHED);
  assert.equal(new Set(found).size, found.length, `${what}: each element once`);
  assert.ok(
    found.every((element) => all.includes(element)),
    `${what}: no element outside the page`,
  );
  assert.deepEqual(
    all.map((element) => found.includes(element)),
    all.map((element) => element.matches(MATCHED)),
    `${what}: the elements that match`,
  );
};
// What `readingElements` is asked for: elements in the frame and in parts, those a
// slot shows, and the parts' own roots.
const MATCHED = "p, b, em, figure, h1, h2, h3, h4, [data-lf-datum]";

// Every element the outline can be asked about, in the light tree and in declared ones,
// those declared inside another included.
const elements = (root = document.body) =>
  [...root.querySelectorAll("*")].flatMap((element) =>
    element.localName === "lf-staged"
      ? [element, ...elements(element.shadowRoot)]
      : [element],
  );
// What the outline says of each element, the chain of what stands over it included.
const outlineOf = () => {
  const { outline, at, over, above } = documentOutline(document.body);
  const chain = (state) =>
    state ? [state.container, state.heading, ...chain(state.up)] : [];
  return {
    outline: [...outline],
    at: outline.map((heading) => at.get(heading)),
    over: elements().map((element) => chain(over.get(element))),
    above: outline.map((heading) => [above.has(heading), above.get(heading)]),
  };
};
// The outline put together from kept pieces must say what one read afresh says. Reading
// afresh forgets every kept piece, so the next change finds none of this one's left.
const assertOutline = (what) => {
  const kept = outlineOf();
  freshVocabulary();
  assert.deepEqual(kept, outlineOf(), `${what}: the outline`);
};
// Every piece read and kept, so a change has something to drop.
const readEverything = () => {
  for (const root of readingParts()) pageText(root);
  for (const element of document.querySelectorAll("[id]")) elementReading(element);
  outlineOf();
  readingElements(MATCHED);
};

const by = (id) => document.getElementById(id);

// Each kind of change, in turn on one page.
/** @param {HTMLElement} host */
const changes = (host) => {
  const fresh = (markup) => {
    const template = document.createElement("template");
    template.innerHTML = markup;
    return template.content;
  };
  return [
    ["words edited inside a part", () => (by("a2").firstChild.data = "Alpha edited")],
    ["a break put at a part's end", () => by("c").append(document.createElement("br"))],
    [
      "a heading put in a part",
      () =>
        by("c").prepend(
          Object.assign(document.createElement("h3"), { textContent: "New" }),
        ),
    ],
    [
      "a part replaced",
      () => by("b").replaceWith(fresh(datum("b", "<p>Beta again</p>"))),
    ],
    ["a part added", () => by("s1").append(fresh(datum("d", "<p>Delta</p>")))],
    ["a part removed", () => by("a").remove()],
    ["prose edited", () => (by("intro").firstChild.data = "Intro rewritten")],
    ["a part's own marker taken off", () => by("c").removeAttribute("data-lf-datum")],
    ["prose made a part", () => by("between").setAttribute("data-lf-datum", "between")],
    [
      "words edited in the part it became",
      () => (by("between").firstChild.data = "Edited"),
    ],
    [
      "a part comes to stand inside a new part",
      () => {
        by("s1").setAttribute("data-lf-projection", "w");
        by("s1").setAttribute("data-lf-datum", "s1");
      },
    ],
    [
      "words edited in the part that stands inside it",
      () => (by("b").firstChild.firstChild.data = "Beta inside"),
    ],
    [
      "the outer part's marker taken off",
      () => by("s1").removeAttribute("data-lf-datum"),
    ],
    [
      "words a part's slot shows edited",
      () => (by("slotted").firstChild.data = "Slotted"),
    ],
    [
      "a child given to the host whose part's slot shows it",
      () =>
        host.append(
          Object.assign(document.createElement("em"), { textContent: "Late" }),
        ),
    ],
    [
      "a child moved to a slot in another part",
      () => by("other").setAttribute("slot", "x"),
    ],
    [
      "a part moved under chrome",
      () => {
        const chrome = Object.assign(document.createElement("div"), {
          className: "lf-ui",
        });
        by("s1").append(chrome);
        chrome.append(by("b"));
      },
    ],
    [
      "a slot that shows a part made a part",
      () => {
        const shows = host.shadowRoot.querySelector("#w");
        shows.setAttribute("data-lf-projection", "w");
        shows.setAttribute("data-lf-datum", "w");
      },
    ],
    ["words edited in the part it shows", () => (by("u1").firstChild.data = "Shown")],
    ["chrome put over parts", () => by("s1").classList.add("lf-ui")],
    ["chrome taken off them", () => by("s1").classList.remove("lf-ui")],
    ["a fence put around parts", () => fencePassageParts(by("s1"))],
  ];
};

test("the frame holds the page's words outside its parts, and each part its own", () => {
  page();
  assertPieces("as first read");
  // The outline one walk of `main` records, past which the page's goes on to the body.
  const main = document.querySelector("main");
  const walked = documentOutline(main);
  const { outline, over } = documentOutline(document.body);
  assert.deepEqual([...outline], [...walked.outline]);
  assert.ok(outline.some((heading) => heading.textContent === "Slotted heading"));
  const chain = (state) =>
    state && state.container !== main
      ? [state.container, state.heading, ...chain(state.up)]
      : [];
  for (const element of main.querySelectorAll("*"))
    assert.deepEqual(chain(over.get(element)), chain(walked.over.get(element)));
  // The elements that match, in the order the page reads them, as its outline is.
  const headings = readingElements("h1, h2, h3, h4");
  assert.equal(headings.length, outline.length);
  assert.ok(headings.every((heading, at) => heading === outline[at]));
});

test("a part's headings join the outline where no heading comes before them", () => {
  freshVocabulary();
  document.body.innerHTML =
    "<main>" + datum("a", "<h2>Only heading</h2><p>Alpha</p>") + "<p>After</p></main>";
  const { outline, at } = documentOutline(document.body);
  const heading = document.querySelector("h2");
  assert.deepEqual([...outline], [heading]);
  assert.equal(at.get(heading), 0);
});

test("each change drops the pieces whose words or context it moved", () => {
  for (const [what, change] of changes(page())) {
    readEverything();
    change();
    assertPieces(what);
  }
});

test("each change drops the pieces whose outline it moved", () => {
  for (const [what, change] of changes(page())) {
    readEverything();
    change();
    assertOutline(what);
  }
});

// A slot shows what another slot passes on to it, so a change to what holds the first
// reaches the parts among the children of the second's host.
test("a change over a slot reaches the parts another slot passes on to it", () => {
  freshVocabulary();
  document.body.innerHTML =
    '<main><p>Prose</p><lf-staged id="outer"></lf-staged></main>';
  const nodes = (markup) => {
    const template = document.createElement("template");
    template.innerHTML = markup;
    return [...template.content.childNodes];
  };
  const outer = document.getElementById("outer");
  shadowStage(outer, nodes('<lf-staged id="inner"></lf-staged>'));
  const inner = outer.shadowRoot.getElementById("inner");
  shadowStage(inner, nodes('<div id="holder"><slot></slot></div>'));
  inner.append(document.createElement("slot"));
  outer.innerHTML = datum("x", '<p id="x1">Passed on</p>');
  assert.deepEqual(readingParts(), [by("x")]);
  const holder = inner.shadowRoot.getElementById("holder");
  const steps = [
    [
      "what holds the slot made a part",
      () => holder.setAttribute("data-lf-datum", "h"),
    ],
    ["words edited in the part passed on", () => (by("x1").firstChild.data = "Edited")],
  ];
  holder.setAttribute("data-lf-projection", "w");
  for (const [what, change] of steps) {
    readEverything();
    change();
    assertPieces(what);
  }
});

// Reading a part means asking each of its elements where it stands; a part kept from
// before is asked nothing.
test("a change inside one part leaves the other parts unread", () => {
  page();
  readEverything();
  const other = document.getElementById("b");
  const { matches } = Element.prototype;
  let asked = 0;
  Element.prototype.matches = function (selector) {
    if (other.contains(this)) asked += 1;
    return matches.call(this, selector);
  };
  try {
    document.getElementById("a2").firstChild.data = "Alpha edited";
    assert.match(pageText(document.getElementById("a")).raw, /Alpha edited/);
    pageText();
    documentOutline(document.body);
    readingElements(MATCHED);
  } finally {
    Element.prototype.matches = matches;
  }
  assert.equal(asked, 0, `${asked} questions asked of the other part's elements`);
});

// Each piece keeps the copies of every quote the threads name, so a line rewritten in a
// document changes the quotes on that line alone, and none in prose or in another part.
test("a line rewritten in a part changes only the quotes standing on it", () => {
  freshVocabulary();
  const lines = Array.from({ length: 40 }, (_, i) => `<p>Line ${i} of the notes</p>`);
  document.body.innerHTML =
    "<main><p>The prose before the notes</p>" +
    datum("n", lines.join("")) +
    datum("m", "<p>Other notes here</p>") +
    "</main>";
  const notes = document.getElementById("n");
  const quotes = [
    ...lines.map((_, i) => `Line ${i} of`),
    "Other notes",
    "prose before",
  ];
  trackQuotes(quotes);
  for (const quote of quotes.slice(0, 40))
    assert.ok(findQuote(pageText(notes), quote, {}).length);
  findQuote(pageText(document.getElementById("m")), "Other notes", {});
  findQuote(pageText(), "prose before", {});
  const { version } = quotesChanged(0);
  notes.children[7].firstChild.data = "Line 7 rewritten";
  assert.deepEqual(quotesChanged(version).quotes, ["Line 7 of"]);
});

// Anchor placement finds a datum's quote in that datum's own words, whether the datum is
// a part or stands in one or in a line, so a change to those words changes the quote.
for (const [what, markup] of [
  [
    "inside a part",
    datum("outer", "<p>Outer words</p>" + datum("d", "alpha beta gamma")),
  ],
  [
    "standing in a line",
    '<p>Words <span id="d" data-lf-projection="w" data-lf-datum="d">alpha beta gamma</span></p>',
  ],
  [
    "that is a heading",
    '<h2 id="d" data-lf-projection="w" data-lf-datum="d">alpha beta gamma</h2>',
  ],
])
  test(`a quote in a datum ${what} changes when its words move`, () => {
    freshVocabulary();
    document.body.innerHTML = `<main><p>Prose before</p>${markup}</main>`;
    const own = document.getElementById("d");
    trackQuotes(["beta gamma"]);
    assert.ok(findQuote(pageText(own), "beta gamma", {}).length);
    const { version } = quotesChanged(0);
    own.firstChild.data = "words first alpha beta gamma";
    assert.deepEqual(quotesChanged(version).quotes, ["beta gamma"]);
  });

// A page of `n` datum rows between two paragraphs, every piece read.
/** @param {number} n */
const rowsPage = (n) => {
  freshVocabulary();
  const rows = Array.from({ length: n }, (_, i) =>
    datum(`r${i}`, `line ${i} of the rows`),
  );
  document.body.innerHTML =
    '<main><p id="intro">Intro words before the rows</p><section>' +
    rows.join("") +
    '</section><p id="outro">Outro words</p></main>';
  for (const root of readingParts()) pageText(root);
  return document.querySelector("section").children;
};
// How many times the walk asks a node which slot shows it, as each step up the reading's
// tree does, while `run` runs.
/** @param {() => void} run */
const stepsUp = (run) => {
  let steps = 0;
  const kinds = [Element, Text].map(({ prototype }) => [
    prototype,
    Object.getOwnPropertyDescriptor(prototype, "assignedSlot"),
  ]);
  for (const [prototype, slot] of kinds)
    Object.defineProperty(prototype, "assignedSlot", {
      ...slot,
      get() {
        steps += 1;
        return slot.get.call(this);
      },
    });
  try {
    run();
  } finally {
    for (const [prototype, slot] of kinds)
      Object.defineProperty(prototype, "assignedSlot", slot);
  }
  return steps;
};

// The frame's marks are in reading order, so where a selection stands among the parts is
// a binary search: one in prose, or across the edge between two parts, compares about as
// many places on a page of a thousand parts as on one of a hundred.
test("a selection compares a few parts' places however many the page holds", () => {
  /** @param {number} n */
  const steps = (n) => {
    const rows = rowsPage(n);
    const range = (from, start, to, end) => {
      const made = document.createRange();
      made.setStart(from, start);
      made.setEnd(to, end);
      return made;
    };
    const intro = document.getElementById("intro").firstChild;
    const inProse = range(intro, 4, intro, 20);
    const next = rows[n / 2 + 1].firstChild;
    const across = range(rows[n / 2].firstChild, 5, next, next.data.indexOf(" of"));
    assert.equal(quoteFrom(segmentsIn(inProse)), "o words before t");
    assert.equal(
      quoteFrom(segmentsIn(across)),
      `${n / 2} of the rows line ${n / 2 + 1}`,
    );
    return [stepsUp(() => segmentsIn(inProse)), stepsUp(() => segmentsIn(across))];
  };
  const [small, large] = [steps(100), steps(1000)];
  for (const [k, what] of ["in prose", "across two parts"].entries())
    assert.ok(
      large[k] < small[k] * 2,
      `${what}: ${small[k]} steps beside 100 parts, ${large[k]} beside 1000`,
    );
});

// A selection across parts holds the frame's words and each part's in reading order.
test("a selection across parts reads the frame's words and theirs in order", () => {
  const rows = rowsPage(3);
  const range = document.createRange();
  range.setStart(document.getElementById("intro").firstChild, 6);
  range.setEnd(document.getElementById("outro").firstChild, 3);
  assert.equal(
    quoteFrom(segmentsIn(range)),
    "words before the rows line 0 of the rows line 1 of the rows line 2 of the rows Out",
  );
  range.setStart(rows[1].firstChild, 7);
  assert.equal(quoteFrom(segmentsIn(range)), "of the rows line 2 of the rows Out");
});

// Hearing a change finds the kept parts it moved from the nodes it changed down, so a
// paragraph put in the frame costs as much beside a thousand kept parts as beside a
// hundred.
test("hearing a paragraph put in the frame costs the same however many parts are kept", () => {
  /** @param {number} n */
  const steps = (n) => {
    rowsPage(n);
    return stepsUp(() => {
      const added = Object.assign(document.createElement("p"), { textContent: "More" });
      document.getElementById("outro").before(added);
      pageReadingVersion();
    });
  };
  const [small, large] = [steps(100), steps(1000)];
  assert.equal(large, small, `${small} steps beside 100 parts, ${large} beside 1000`);
});
