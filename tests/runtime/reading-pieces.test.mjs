import "/runtime/stage-integration.js";
/* The page's reading put together from pieces kept apart: the frame, and each datum that
   is a part (passages.js, `Piece`). Whatever kept pieces a reader puts together must say
   what one fresh walk of the page says, so each kind of change drops every piece whose
   words or context it moved, and only those. A change inside one part leaves every
   other part unread. */

import assert from "node:assert/strict";
import test from "node:test";

import { registry } from "/runtime/registry.js";
import { documentOutline, fencePassageParts, pageText } from "/runtime/passages.js";
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
// declared tree holding two parts whose slots show the host's light children. Breaks
// stand at a part's end and just before another, where one walk carries them past the
// edge.
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
    datum("s", '<p>Staged <slot name="x"></slot></p>') +
    datum("t", "<p><slot></slot></p>");
  shadowStage(host, [...staged.content.childNodes]);
  // The stage clears light children, so what its slots take arrives after it.
  host.innerHTML = '<b id="slotted" slot="x">Slotted words</b><i id="other">Other</i>';
  return host;
};

const SEGMENT = ["start", "end", "rawStart", "block", "textBlock", "words", "gen"];
// Each segment's node and the facts it carries, with whether a break stands before it.
const segments = (reading) =>
  reading.segments.map((segment) => [
    segment.node,
    ...SEGMENT.map((key) => segment[key]),
    Boolean(segment.breakBefore),
  ]);
// The pieces put together must read as one fresh walk of the page does: the body is no
// part, so its own reading is a walk of the whole page.
const assertWhole = (what) => {
  const kept = pageText();
  const fresh = pageText(document.body);
  assert.notEqual(kept, fresh);
  assert.equal(kept.raw, fresh.raw, `${what}: the words`);
  assert.deepEqual(kept.fences, fresh.fences, `${what}: the fences`);
  assert.deepEqual(segments(kept), segments(fresh), `${what}: the segments`);
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

// Each kind of change, in turn on one page, each after every piece has been read and
// kept, so it has something to drop.
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

test("the page's reading put together from its parts says what one walk says", () => {
  page();
  assertWhole("as first read");
  // The outline one walk of `main` records, past which the page's goes on to the body.
  const main = document.querySelector("main");
  const walked = documentOutline(main);
  const { outline, over } = documentOutline(document.body);
  assert.deepEqual([...outline], [...walked.outline]);
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
    pageText();
    outlineOf();
    change();
    assertWhole(what);
  }
});

test("each change drops the pieces whose outline it moved", () => {
  for (const [what, change] of changes(page())) {
    pageText();
    outlineOf();
    change();
    assertOutline(what);
  }
});
test("a change inside one part leaves the other parts unread", () => {
  page();
  pageText();
  outlineOf();
  const other = document.getElementById("b");
  const { matches } = Element.prototype;
  let asked = 0;
  Element.prototype.matches = function (selector) {
    if (other.contains(this)) asked += 1;
    return matches.call(this, selector);
  };
  try {
    document.getElementById("a2").firstChild.data = "Alpha edited";
    assert.match(pageText().raw, /Alpha edited/);
    documentOutline(document.body);
  } finally {
    Element.prototype.matches = matches;
  }
  assert.equal(asked, 0, `${asked} questions asked of the other part's elements`);
});
