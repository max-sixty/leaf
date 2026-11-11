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
  quotesChanged,
  readingParts,
  says,
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
// them a heading.
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
    datum("t", "<p><slot></slot></p>");
  shadowStage(host, [...staged.content.childNodes]);
  // The stage clears light children, so what its slots take arrives after it.
  host.innerHTML =
    '<b id="slotted" slot="x">Slotted words</b><h4 slot="h">Slotted heading</h4>' +
    '<i id="other">Other</i>';
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
// with a fence where each part stands, and each part its words under it.
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
  for (const root of parts) {
    const own = pageText(root);
    assert.deepEqual(
      facts(own.segments),
      facts(whole.segments.filter(({ node }) => standsUnder(node, root))),
      `${what}: the words of part ${root.id}`,
    );
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
};

// Every element the outline can be asked about, in the light tree and in declared ones.
const elements = () => [
  ...document.body.querySelectorAll("*"),
  ...[...document.querySelectorAll("lf-staged")].flatMap((host) => [
    ...host.shadowRoot.querySelectorAll("*"),
  ]),
];
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
};

// Each kind of change, in turn on one page.
/** @param {HTMLElement} host */
const changes = (host) => {
  const by = (id) => document.getElementById(id);
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

// Hearing a change costs the kept parts it may have moved, however many nodes it put in
// or took out: each kept part is climbed once a batch, not once for each node.
test("hearing rows replaced at once costs the kept parts, not rows times parts", () => {
  /** @param {number} n */
  const climbs = (n) => {
    freshVocabulary();
    document.body.innerHTML = "<main><section></section></main>";
    const box = document.querySelector("section");
    const rows = (tag) =>
      Array.from({ length: n }, (_, i) => {
        const row = document.createElement("div");
        row.setAttribute("data-lf-projection", "w");
        row.setAttribute("data-lf-datum", `l${i}`);
        row.textContent = `line ${i} ${tag}`;
        return row;
      });
    box.append(...rows("first"));
    for (const root of readingParts()) pageText(root);
    let read = 0;
    const slot = Object.getOwnPropertyDescriptor(Element.prototype, "assignedSlot");
    Object.defineProperty(Element.prototype, "assignedSlot", {
      ...slot,
      get() {
        read += 1;
        return slot.get.call(this);
      },
    });
    try {
      box.replaceChildren(...rows("again"));
      pageReadingVersion();
    } finally {
      Object.defineProperty(Element.prototype, "assignedSlot", slot);
    }
    return read;
  };
  const [small, large] = [climbs(100), climbs(200)];
  assert.ok(large < small * 3, `${small} climbs for 100 rows, ${large} for 200`);
});
