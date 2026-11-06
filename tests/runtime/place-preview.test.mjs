/* What a place on the page previews (place-preview.js): its name over its first parts,
   each read from the place's words rather than copied from its nodes, a heading's
   section as the page's reading walks it, and which links preview one at all. What the
   platform draws, the state a question's obligation and the conversations about a place
   add are the browser's to show, and the browser test that hovers a link holds them
   (`tests/browser/controls/test_previews.py`). */

import assert from "node:assert/strict";
import test from "node:test";
import { render } from "/runtime/framework.js";
import { linkedPlace, placePreview } from "/runtime/place-preview.js";
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

test("a heading previews its section, up to the next heading at its level or above", () => {
  assert.deepEqual(
    previewed(`<h2 id="it">Support</h2><p>It covers the spinner.</p>
      <h3>Detail</h3><h2>Next</h2><p>Not this.</p>`).parts,
    [
      ["name", "Support"],
      ["text", "It covers the spinner."],
      ["heading", "Detail"],
    ],
  );
  // A block holding the next heading gives what stands before it.
  assert.deepEqual(
    previewed(`<h2 id="it">Support</h2><section><p>Inside.</p><h2>Next</h2>
      <p>Not this.</p></section>`).parts,
    [
      ["name", "Support"],
      ["text", "Inside."],
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
});

test("a place with no name of its own takes the nearest name holding it", () => {
  assert.deepEqual(
    previewed(`<section aria-label="Deployment"><p id="it">It may fail.</p></section>`)
      .parts,
    [
      ["name", "Deployment"],
      ["text", "It may fail."],
    ],
  );
});

test("code shows its first lines", () => {
  assert.deepEqual(
    previewed(`<pre id="it"><code>a()\nb()\nc()\nd()\ne()</code></pre>`).parts,
    [["code", "a() b() c() d()"]],
  );
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
