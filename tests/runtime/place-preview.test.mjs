/* What a place on the page previews (place-preview.js): its name over its first parts,
   each read from the place's words rather than copied from its nodes, a heading's
   section as the page's reading walks it, and which links preview one at all. What the
   platform draws, a code block's lines as its whitespace draws them, the state a
   question's obligation and the conversations about a place add are the browser's to
   show, and the browser test that hovers a link holds them
   (`tests/browser/controls/test_previews.py`). */

import assert from "node:assert/strict";
import test from "node:test";
import { render } from "/runtime/framework.js";
import { linkedPlace, placePreview } from "/runtime/place-preview.js";
import { partOver } from "/runtime/thread/placement.js";
import { registry } from "/runtime/registry.js";
import { shadowStage } from "/runtime/shadow-stage.js";

// The preview's name and parts, each as [its class without the prefix, its words], of
// `#it` in `markup`: the page's, or with `message` the markup of a reply as the floating
// panel draws it, in the chrome after the page's body, inside generated chrome around
// the message's body.
/** @param {string} markup @param {{message?: boolean}} [where] */
function previewed(markup, { message = false } = {}) {
  document.querySelector(".lf-chrome")?.remove();
  document.body.innerHTML = message
    ? "<main><p>The page.</p></main>"
    : `<main>${markup}</main>`;
  if (message) {
    const chrome = document.createElement("div");
    chrome.className = "lf-chrome";
    chrome.innerHTML = `<div class="lf-msg lf-ui" data-lf-gen="1"><div class="lf-msg-body">
      <div class="lf-msg-text"><p>The reply's words.</p></div>${markup}</div></div>`;
    document.documentElement.append(chrome);
  }
  const preview = placePreview(document.getElementById("it"));
  if (!preview) return null;
  assert.equal(preview.excerpt, true);
  const tip = document.createElement("div");
  render(preview.detail, tip);
  const place = tip.querySelector(".lf-place");
  return {
    parts: [
      ...(preview.name ? [["name", preview.name]] : []),
      ...[...(place?.children ?? [])].map((part) => [
        part.className.replace("lf-place-", ""),
        part.textContent.replace(/\s+/g, " ").trim(),
      ]),
    ],
    copied: tip.querySelectorAll("[id], a, button, input, [tabindex]").length,
  };
}

test("a section previews its heading and first lines, past what stands above the heading", () => {
  assert.deepEqual(
    previewed(`<section id="it"><p class="eyebrow">mobile</p><h2>The stall</h2>
      <p id="p1">One in <a href="#x">forty</a> stalls.</p><p>It recovers.</p>
      <p>Third.</p><p>Fourth.</p></section>`),
    {
      parts: [
        ["name", "The stall"],
        ["text", "One in forty stalls."],
        ["text", "It recovers."],
      ],
      copied: 0,
    },
  );
});

test("a heading previews the part it heads itself, up to the outline's next heading", () => {
  assert.deepEqual(
    previewed(`<h2 id="it">Support</h2><p>It covers the spinner.</p>
      <h3>Detail</h3><p>Detail's own.</p>`).parts,
    [
      ["name", "Support"],
      ["text", "It covers the spinner."],
    ],
  );
  // A block holding the next heading gives what stands before it, however deep.
  assert.deepEqual(
    previewed(`<h2 id="it">Support</h2><section><p>Inside.</p><h2>Next</h2>
      <p>Not this.</p></section>`).parts,
    [
      ["name", "Support"],
      ["text", "Inside."],
    ],
  );
  assert.deepEqual(
    previewed(`<h2 id="it">First</h2><div>Prefix <h2>Next section</h2>
      <p>Other section words</p></div>`).parts,
    [
      ["name", "First"],
      ["text", "Prefix"],
    ],
  );
  // A heading in a header heads what holds the header, from the words after it there.
  assert.deepEqual(
    previewed(`<section><header><h2 id="it">Risk</h2></header>
      <p>First lines.</p></section>`).parts,
    [
      ["name", "Risk"],
      ["text", "First lines."],
    ],
  );
  assert.deepEqual(
    previewed(`<section><header><h2 id="it">Risk</h2><p>Important standfirst.</p>
      </header><p>Later body.</p></section>`).parts,
    [
      ["name", "Risk"],
      ["text", "Important standfirst."],
      ["text", "Later body."],
    ],
  );
});

test("a list shows its first items and how many more it holds", () => {
  assert.deepEqual(
    previewed(
      `<ol id="it"><li>One.</li><li>Two.</li><li>Three.</li><li>Four.</li></ol>`,
    ).parts,
    [["list", "One.Two.Three.1 more"]],
  );
  assert.deepEqual(
    previewed(
      `<dl id="it"><dt>Observed</dt><dd>1 in 40</dd><dt>Lost</dt><dd>none</dd></dl>`,
    ).parts,
    [["list", "Observed: 1 in 40Lost: none"]],
  );
});

test("a table shows its caption over its first rows, cell by cell", () => {
  const { parts } = previewed(`<table id="it"><caption>Budget</caption>
    <tr><th>Quarter</th><th>Spent</th></tr><tr><td>Q1</td><td>$38k</td></tr>
    <tr><td>Q2</td><td>$45k</td></tr><tr><td>Q3</td><td>$12k</td></tr></table>`);
  assert.deepEqual(parts, [
    ["name", "Budget"],
    ["table", "QuarterSpentQ1$38kQ2$45k1 more row"],
  ]);
});

test("a message's markup previews by its own document: its words, names and outline", () => {
  assert.deepEqual(
    previewed(
      `<section id="it"><h2>Message heading</h2><p>Message first lines.</p></section>`,
      { message: true },
    ).parts,
    [
      ["name", "Message heading"],
      ["text", "Message first lines."],
    ],
  );
  // A paragraph is named by the heading over it in the message.
  assert.deepEqual(
    previewed(`<h2>Risk</h2><p id="it">It may fail.</p>`, { message: true }).parts,
    [
      ["name", "Risk"],
      ["text", "It may fail."],
    ],
  );
  // Leaf's controls in a message's markup are no part of its outline.
  assert.deepEqual(
    previewed(
      `<h2>Actual subject</h2><h3 class="lf-ui" data-lf-gen="x">Generated</h3>
      <p id="it">It may fail.</p>`,
      { message: true },
    ).parts,
    [
      ["name", "Actual subject"],
      ["text", "It may fail."],
    ],
  );
  // A heading heads the message's part it opens, up to the message's next heading.
  assert.deepEqual(
    previewed(`<h2 id="it">Risk</h2><h2>Other section</h2><p>Other text</p>`, {
      message: true,
    }).parts,
    [["name", "Risk"]],
  );
});

test("a heading's section is walked through declared shadow trees and their slots", () => {
  Object.assign(registry, {
    "lf-staged": { "x-shadow": true },
    $layer: { generation: "place-preview-shadow" },
  });
  // Two sections a widget draws in its declared tree, in a reply's markup.
  document.querySelector(".lf-chrome")?.remove();
  document.body.innerHTML = "<main><p>The page.</p></main>";
  const chrome = document.createElement("div");
  chrome.className = "lf-chrome";
  chrome.innerHTML = `<div class="lf-msg lf-ui" data-lf-gen="1"><div class="lf-msg-body">
    <lf-staged id="widget"></lf-staged></div></div>`;
  document.documentElement.append(chrome);
  const sections = document.createElement("template");
  sections.innerHTML = `<section><h2 id="it">First section</h2><p>First paragraph.</p>
    </section><section><h2>Second section</h2><p>Second paragraph.</p></section>`;
  shadowStage(document.getElementById("widget"), [...sections.content.childNodes]);
  const staged = document.getElementById("widget").shadowRoot.getElementById("it");
  const read = placePreview(staged);
  const tip = document.createElement("div");
  render(read.detail, tip);
  assert.equal(read.name, "First section");
  assert.equal(tip.textContent.replace(/\s+/g, " ").trim(), "First paragraph.");
  // Slots order what they take as the tree draws them, whatever the light order.
  document.body.innerHTML = `<main><h2 id="it">Lead</h2><lf-staged id="slotted">
    </lf-staged><h2>Next</h2></main>`;
  const slots = document.createElement("template");
  slots.innerHTML = `<div><slot name="a"></slot><slot name="b"></slot></div>`;
  const host = document.getElementById("slotted");
  shadowStage(host, [...slots.content.childNodes]);
  // The stage clears light children, so what the slots take arrives after it.
  host.innerHTML = `<p slot="b">Drawn second.</p><p slot="a">Drawn first.</p>`;
  const lead = placePreview(document.getElementById("it"));
  const lines = document.createElement("div");
  render(lead.detail, lines);
  assert.deepEqual(
    [...lines.querySelectorAll(".lf-place-text")].map((part) => part.textContent),
    ["Drawn first.", "Drawn second."],
  );
  // A slot's fallback, replaced by what is assigned to it, is no part of the outline,
  // so its heading ends nothing.
  document.body.innerHTML = `<main><lf-staged id="fallback"></lf-staged></main>`;
  const fallback = document.createElement("template");
  fallback.innerHTML = `<h2 id="it">First</h2><slot><h3>Fallback heading</h3></slot>
    <h2>Next</h2><p>Next words.</p>`;
  const holder = document.getElementById("fallback");
  shadowStage(holder, [...fallback.content.childNodes]);
  holder.innerHTML = "<p>Assigned body.</p>";
  const first = placePreview(holder.shadowRoot.getElementById("it"));
  const body = document.createElement("div");
  render(first.detail, body);
  assert.equal(body.textContent.replace(/\s+/g, " ").trim(), "Assigned body.");
});

test("a place with no name of its own is named by the part it stands in, as On me groups it", () => {
  // The name of each place below is the card's, and the part `partOver` gives, which On
  // me's "By place" bands are titled by, is the element that name comes from.
  /** @param {string} markup @param {string} name @param {string} part */
  const named = (markup, name, part) => {
    assert.equal(previewed(markup).parts[0]?.join(":"), `name:${name}`);
    const over = partOver(document.getElementById("it"));
    assert.equal(
      over?.matches("h1, h2, h3, h4, h5, h6") ? "heading" : over?.localName,
      part,
    );
  };
  // A region its author labelled.
  named(
    `<section aria-label="Deployment"><p id="it">It may fail.</p></section>`,
    "Deployment",
    "section",
  );
  // A section the author wrote names what stands in it before its heading.
  named(
    `<h2>Earlier</h2><section><p id="it">Context first.</p><h2>Later</h2>
    <p>After.</p></section>`,
    "Later",
    "heading",
  );
  // A sub-heading inside a titled section heads what follows it.
  named(
    `<section><h2>Section title</h2><p>Intro.</p><h3>Sub-heading</h3>
    <p id="it">Words under the sub-heading.</p></section>`,
    "Sub-heading",
    "heading",
  );
  // A figure's caption names what it holds.
  named(
    `<figure><figcaption>Stalls by week</figcaption><div><p id="it">A note on
    the chart.</p></div></figure>`,
    "Stalls by week",
    "figure",
  );
  // An aside's heading heads the aside alone.
  named(
    `<h2>Deployment</h2><aside><h3>Optional note</h3><p>Aside words.</p>
    </aside><p id="it">It ships on Monday.</p>`,
    "Deployment",
    "heading",
  );
  // A line's leading <strong> names the line itself, and makes no part.
  named(
    `<h2>Suggestions</h2><p><span><strong>Replace.</strong> The meeting starts
    at <em id="it">ten</em>.</span></p>`,
    "Suggestions",
    "heading",
  );
  assert.equal(
    previewed(`<p><span id="it"><strong>Replace.</strong> The meeting starts
    at ten.</span></p>`).parts[0]?.join(":"),
    "name:Replace.",
  );
  // What Leaf generates in the page names nothing, whatever it is labelled.
  named(
    `<h2>Real part</h2><div data-lf-gen="1" aria-label="Leaf's own"><p id="it">Words
    in it.</p></div>`,
    "Real part",
    "heading",
  );
});

test("a slotted section reads its slot's run once, and only as far as its preview shows", () => {
  Object.assign(registry, {
    "lf-staged": { "x-shadow": true },
    $layer: { generation: "place-preview-run" },
  });
  document.querySelector(".lf-chrome")?.remove();
  document.body.innerHTML = `<main><lf-staged id="host"></lf-staged></main>`;
  const slot = document.createElement("template");
  slot.innerHTML = "<div><slot></slot></div>";
  const host = document.getElementById("host");
  shadowStage(host, [...slot.content.childNodes]);
  host.innerHTML = `<h2 id="it">Long</h2>${Array.from(
    { length: 400 },
    (_, at) => `<p>Paragraph ${at}.</p>`,
  ).join("")}`;
  const counted = { assignedElements: 0, checkVisibility: 0 };
  const originals = Object.keys(counted).map((name) => {
    const owner =
      name === "assignedElements"
        ? document.createElement("slot").constructor
        : Element;
    const original = owner.prototype[name];
    owner.prototype[name] = function (...args) {
      counted[name] += 1;
      return original.apply(this, args);
    };
    return () => (owner.prototype[name] = original);
  });
  try {
    const read = placePreview(document.getElementById("it"));
    const tip = document.createElement("div");
    render(read.detail, tip);
    assert.deepEqual(
      [...tip.querySelectorAll(".lf-place-text")].map((part) => part.textContent),
      ["Paragraph 0.", "Paragraph 1."],
    );
  } finally {
    for (const restore of originals) restore();
  }
  assert.ok(
    counted.assignedElements <= 1,
    `slot read ${counted.assignedElements} times`,
  );
  assert.ok(counted.checkVisibility < 10, `${counted.checkVisibility} elements asked`);
});

test("a figure shows its picture under its caption, and a drawing its title", () => {
  const { parts } = previewed(`<figure id="it"><img src="/media/a.png" alt="A chart">
    <figcaption>Stalls by week</figcaption></figure>`);
  assert.deepEqual(parts, [
    ["name", "Stalls by week"],
    ["figure", ""],
  ]);
  assert.deepEqual(
    previewed(`<figure id="it"><svg role="img"><title>Three batches</title></svg>
      <figcaption>The queue</figcaption></figure>`).parts,
    [
      ["name", "The queue"],
      ["text", "Three batches"],
    ],
  );
});

test("only a link an author wrote into the page names a place", () => {
  document.body.innerHTML = `<main><p id="target">Here.</p>
    <a id="in" href="#target">in</a><a id="out" href="https://example.com/#target">out</a>
    <a id="gone" href="#missing">gone</a>
    <nav class="lf-ui"><a id="drawn" href="#target">drawn</a></nav></main>`;
  const place = (id) => linkedPlace(document.getElementById(id))?.id ?? null;
  assert.equal(place("in"), "target");
  assert.equal(place("out"), null);
  assert.equal(place("gone"), null);
  assert.equal(place("drawn"), null);
});
