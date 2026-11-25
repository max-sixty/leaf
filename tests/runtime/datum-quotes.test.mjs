import "/runtime/stage-integration.js";
/* Which words a quote anchored in a widget's data is captured against and found again
   in: its datum's own (`pageText(datum)`), read alone with the datum's edges as the
   reading's ends. A page grows large through its widgets' data, so finding such a quote
   costs what its datum holds, and the edge of the datum is the edge of its context on
   both sides of the round trip.

   The datum is a block of a widget's projection (`data-lf-projection`, `data-lf-datum`)
   standing between prose paragraphs, which share no fence with it. */

import assert from "node:assert/strict";
import test from "node:test";

import { anchorForRange, resolveAnchor } from "/runtime/readings/anchor-resolution.js";
import { findQuote, pageText, readingPart } from "/runtime/readings/passages.js";
import { registry } from "/runtime/state/registry.js";
import { shadowStage } from "/runtime/dom/shadow-stage.js";

/** @param {string} lines the datum's rows, as markup */
const page = (lines, prose = "<p>Words before the data</p>") => {
  document.body.innerHTML =
    `<main>${prose}<div id="w"><div id="doc" data-lf-projection="w" ` +
    `data-lf-datum="doc">${lines}</div></div><p>Words after the data</p></main>`;
  return document.querySelector("#doc");
};

const selecting = (node) => {
  const range = document.createRange();
  range.selectNodeContents(node);
  return range;
};

// A line a document holds twice, at its top and at its foot, has nothing beside it on
// one side within the document. Read against the page's whole reading, that empty side
// met the prose around the document, so no copy confirmed it and the comment detached.
test("a line a datum holds twice is found at the copy the user selected", () => {
  Object.assign(registry, { $layer: { generation: "datum-quote-edges" } });
  const datum = page("<p>Repeated line</p><p>Middle line</p><p>Repeated line</p>");
  const [top, , foot] = [...datum.querySelectorAll("p")].map((p) => p.firstChild);
  for (const [copy, line] of [
    ["top", top],
    ["foot", foot],
  ]) {
    const anchor = anchorForRange(selecting(line));
    assert.equal(anchor?.detached, undefined, `the ${copy} copy keeps its place`);
    assert.equal(anchor?.datum, "doc");
    const resolved = resolveAnchor(anchor);
    assert.equal(resolved?.kind, "passage");
    assert.equal(resolved.exact, true);
    assert.deepEqual(
      resolved.segments.map(({ node, start, end }) => [node, start, end]),
      [[line, 0, line.data.length]],
      `the ${copy} copy is the one found`,
    );
  }
});

// The same line in the prose beside the datum, with the same neighbours, is no
// candidate: a datum's quote stands in its datum.
test("a datum's quote is never found outside its datum", () => {
  Object.assign(registry, { $layer: { generation: "datum-quote-within" } });
  const datum = page("<p>Shared line</p>", "<p>Shared line</p>");
  const resolved = resolveAnchor({
    section: "w",
    datum: "doc",
    quote: "Shared line",
  });
  assert.equal(resolved?.kind, "passage");
  assert.equal(resolved.segments[0]?.node, datum.querySelector("p").firstChild);
});

// How many times `read` asks a text node outside `datum` for its words.
/** @param {Element} datum @param {() => void} read */
const readsOutside = (datum, read) => {
  let owner = Text.prototype;
  while (!Object.getOwnPropertyDescriptor(owner, "data"))
    owner = Object.getPrototypeOf(owner);
  const data = Object.getOwnPropertyDescriptor(owner, "data");
  let outside = 0;
  Object.defineProperty(owner, "data", {
    ...data,
    get() {
      if (!datum.contains(this)) outside += 1;
      return data.get.call(this);
    },
  });
  try {
    read();
  } finally {
    Object.defineProperty(owner, "data", data);
  }
  return outside;
};

// Resolution reads the datum's words and none of the page's others: four thousand
// paragraphs beside the datum leave their text unread.
test("finding a datum's quote reads no words outside the datum", () => {
  Object.assign(registry, { $layer: { generation: "datum-quote-reads" } });
  const prose = Array.from({ length: 4096 }, (_, i) => `<p>Paragraph ${i}</p>`);
  const datum = page("<p>Alpha</p><p>Beta</p>", prose.join(""));
  const outside = readsOutside(datum, () => {
    const resolved = resolveAnchor({
      section: "w",
      datum: "doc",
      quote: "Beta",
    });
    assert.equal(resolved?.kind, "passage");
  });
  assert.equal(outside, 0, `${outside} text nodes outside the datum read`);
});

// Capturing a selection inside the datum, as a triple click on one of its lines makes,
// reads the datum's words alone too.
test("capturing a selection inside a datum reads no words outside the datum", () => {
  Object.assign(registry, { $layer: { generation: "datum-capture-reads" } });
  const prose = Array.from({ length: 4096 }, (_, i) => `<p>Paragraph ${i}</p>`);
  const datum = page("<p>Alpha</p><p>Beta</p>", prose.join(""));
  const line = datum.querySelectorAll("p")[1].firstChild;
  const outside = readsOutside(datum, () => {
    assert.equal(anchorForRange(selecting(line))?.quote, "Beta");
  });
  assert.equal(outside, 0, `${outside} text nodes outside the datum read`);
});

// A drag from the end of the paragraph before a datum into its first line also holds the
// newline between them, which is neither's word: the passage is the line, on the datum.
test("a selection from the space before a datum into its line is captured on the datum", () => {
  Object.assign(registry, { $layer: { generation: "datum-capture-space" } });
  const datum = page(
    "<p>Alpha line</p><p>Beta line</p>",
    "<p>Words before the data</p>\n",
  );
  const space = datum.parentElement.previousSibling;
  assert.equal(space.data, "\n");
  const range = document.createRange();
  range.setStart(space, 0);
  range.setEnd(datum.querySelector("p").firstChild, 5);
  const anchor = anchorForRange(range);
  assert.equal(anchor?.datum, "doc");
  assert.equal(anchor?.quote, "Alpha");
  assert.equal(resolveAnchor(anchor)?.exact, true);
});

// A widget's data drawn as lines, each a datum of its own, as a diff draws its lines.
/** @param {string[]} lines */
const linesPage = (lines) => {
  document.body.innerHTML =
    '<main><p>Words before the data</p><div id="w">' +
    lines
      .map(
        (line, at) =>
          `<div data-lf-projection="w" data-lf-datum="${at + 1}">${line}</div>`,
      )
      .join("") +
    "</div><p>Words after the data</p></main>";
  return lines.map(
    (_, at) =>
      /** @type {Text} */ (
        document.querySelector(`[data-lf-datum="${at + 1}"]`)?.firstChild
      ),
  );
};
/** @param {Text} from @param {number} start @param {Text} to @param {number} end */
const spanning = (from, start, to, end) => {
  const range = document.createRange();
  range.setStart(from, start);
  range.setEnd(to, end);
  return range;
};
/** @param {import("/runtime/readings/passages.js").Segment[] | undefined} segments */
const words = (segments) =>
  segments?.map(({ node, start, end }) => node.data.slice(start, end));

// A sentence a diff wraps across two lines is one passage: the comment names the line it
// starts on and the line it ends on, which the thread stands beside, and is found again
// over the words between.
test("a selection across two of a widget's data names both and is found again", () => {
  Object.assign(registry, { $layer: { generation: "datum-run" } });
  const [first, second] = linesPage([
    "Text must reach a reader who has only",
    "that text and the files it points to.",
  ]);
  const range = spanning(
    first,
    first.data.indexOf("reach"),
    second,
    "that text".length,
  );
  const anchor = anchorForRange(range);
  assert.equal(anchor?.detached, undefined);
  assert.equal(anchor?.datum, "2");
  assert.equal(anchor?.from, "1");
  assert.equal(anchor?.quote, "reach a reader who has only that text");
  const resolved = resolveAnchor(anchor);
  assert.equal(resolved?.kind, "passage");
  assert.equal(resolved.exact, true);
  assert.deepEqual(words(resolved.segments), [
    "reach a reader who has only",
    "that text",
  ]);
});

// Words a line says once more after a copy of them that ends on the next line are told
// apart by the words around each copy, read across both lines.
test("a passage across data whose words repeat is found where it was selected", () => {
  Object.assign(registry, { $layer: { generation: "datum-run-repeats" } });
  const [first, second] = linesPage(["one two. one", "two. end"]);
  const anchor = anchorForRange(spanning(first, 9, second, 4));
  assert.equal(anchor?.detached, undefined);
  assert.equal(anchor?.quote, "one two.");
  const resolved = resolveAnchor(anchor);
  assert.equal(resolved?.kind, "passage");
  assert.deepEqual(
    resolved.segments.map(({ node, start, end }) => [node, start, end]),
    [
      [first, 9, 12],
      [second, 0, 4],
    ],
  );
});

// Words on both sides of a datum's edge name no one passage anything finds again.
test("a selection across a datum's edge is captured detached", () => {
  Object.assign(registry, { $layer: { generation: "datum-capture-across" } });
  const datum = page("<p>Alpha line</p>");
  const range = document.createRange();
  range.setStart(document.querySelector("main > p").firstChild, 6);
  range.setEnd(datum.querySelector("p").firstChild, 5);
  const anchor = anchorForRange(range);
  assert.equal(anchor?.datum, undefined);
  assert.equal(anchor?.detached, true);
  assert.match(anchor?.quote ?? "", /before the data.*Alpha/);
});

// A word a datum holds on every line is captured by the words beside the copy the user
// selected, and the other copies are told apart by the letter beside each, read from the
// datum's reading: no copy's neighbouring words are read unless its letters match, and
// the selected copy's read the lines in the 4,096 characters around it. Read word by
// word, the 2,000 copies read every line of the datum.
test("capturing a word a datum repeats reads the words beside only the copies that could match", () => {
  Object.assign(registry, { $layer: { generation: "datum-capture-copies" } });
  const lines = Array.from({ length: 2000 }, (_, i) => `<p>x${i} needle y${i}</p>`);
  const datum = page(lines.join(""));
  pageText(datum);
  const line = datum.querySelectorAll("p")[1000].firstChild;
  const range = document.createRange();
  range.setStart(line, line.data.indexOf("needle"));
  range.setEnd(line, line.data.indexOf("needle") + "needle".length);
  const read = readsOutside(document.createElement("div"), () => {
    const anchor = anchorForRange(range);
    assert.equal(anchor?.detached, undefined);
    assert.equal(anchor?.quote, "needle");
  });
  assert.equal(resolveAnchor(anchorForRange(range))?.segments[0]?.node, line);
  assert.ok(read < lines.length / 4, `${read} text nodes read for 2,000 copies`);
});

// A datum inside a widget's shadow tree reads the words its slot shows, which stand
// outside it, the host's own children. A copy of its quote there is no copy in the datum,
// so the datum's one copy is still the quote's.
test("a datum's quote counts no copy among the words its slot shows from outside it", () => {
  Object.assign(registry, {
    "lf-slotted-datum": {
      shadow: true,
    },
    $layer: { generation: "datum-quote-slot" },
  });
  document.body.innerHTML =
    '<main><div id="w"><lf-slotted-datum><p>MARK two</p></lf-slotted-datum></div></main>';
  const host = /** @type {HTMLElement} */ (document.querySelector("lf-slotted-datum"));
  const tree = document.createElement("template");
  tree.innerHTML =
    '<div data-lf-projection="w" data-lf-datum="doc"><p>MARK one</p><slot></slot></div>';
  const light = host.innerHTML;
  shadowStage(host, [...tree.content.childNodes]);
  host.innerHTML = light;
  const datum = /** @type {Element} */ (
    host.shadowRoot?.querySelector("[data-lf-datum]")
  );
  assert.equal(readingPart(datum), datum);
  assert.match(pageText(datum).raw, /MARK one.*MARK two/s);
  const [first] = findQuote(pageText(datum), "MARK", {}, datum);
  assert.equal(first?.node, datum.querySelector("p")?.firstChild);
});
