/* What a place on the page previews (place-preview.js): its name over its first parts,
   each read from the place's words rather than copied from its nodes, and which links
   preview one at all. The state a question's obligation and the conversations about a
   place add come from the served reading, and the browser test that hovers a link
   holds them (`tests/browser/controls/test_previews.py`). */

import assert from "node:assert/strict";
import test from "node:test";
import { render } from "/runtime/framework.js";
import { linkedPlace, placePreview } from "/runtime/place-preview.js";

// The preview's name and parts, each as [its class without the prefix, its words].
/** @param {string} markup */
function previewed(markup) {
  document.body.innerHTML = `<main>${markup}</main>`;
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

test("a heading previews the part of the page it heads, as the page's outline reads it", () => {
  // Up to its container's next heading, which heads a part of its own.
  assert.deepEqual(
    previewed(`<h2 id="it">Support</h2><p>It covers the spinner.</p>
      <p>And queued edits.</p><h3>Detail</h3><p>Not this.</p>`).parts,
    [
      ["name", "Support"],
      ["text", "It covers the spinner."],
      ["text", "And queued edits."],
    ],
  );
  // A heading in a header heads what holds the header.
  assert.deepEqual(
    previewed(`<section><header><h2 id="it">Risk</h2></header>
      <p>First lines.</p></section>`).parts,
    [
      ["name", "Risk"],
      ["text", "First lines."],
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

test("a closed disclosure shows only its summary, linked to or held", () => {
  assert.deepEqual(
    previewed(`<details id="it"><summary>The method</summary>
      <p>Hidden while closed.</p></details>`).parts,
    [["name", "The method"]],
  );
  assert.deepEqual(
    previewed(`<details id="it" open><summary>The method</summary>
      <p>Shown while open.</p></details>`).parts,
    [
      ["name", "The method"],
      ["text", "Shown while open."],
    ],
  );
  assert.deepEqual(
    previewed(
      `<div id="it"><details><summary>The method</summary><p>Hidden.</p></details></div>`,
    ).parts,
    [["text", "The method"]],
  );
});

test("a native block in a message's markup previews its words", () => {
  // As the floating panel draws a reply: generated chrome around the body that holds
  // the markup the agent sent.
  assert.deepEqual(
    previewed(`<div class="lf-msg lf-ui" data-lf-gen="1"><div class="lf-msg-body">
      <div class="lf-msg-text"><p>The reply's words.</p></div>
      <section id="it"><h2>Message heading</h2><p>Message first lines.</p></section>
      </div></div>`).parts,
    [
      ["name", "Message heading"],
      ["text", "Message first lines."],
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
