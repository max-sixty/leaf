/* What else the user could aim at, at any point of the page (widget-elements.js,
 * `aimableAt`): the answer the preview's rule for a thread's words reads, at any point,
 * marked words or not. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { adoptRegistry } from "/runtime/registry.js";
import { aimableAt } from "/runtime/widget-elements.js";

const entries = (path) =>
  JSON.parse(readFileSync(new URL(`../../${path}`, import.meta.url), "utf8"));
const bundled = entries("packages/default/registry.json");
const kernel = entries("browser/registry.json");
adoptRegistry({
  ...Object.fromEntries(
    [
      "lf-code",
      "lf-draft",
      "lf-options",
      "lf-option",
      "lf-pane",
      "lf-tabs",
      "lf-tab",
    ].map((tag) => [tag, bundled[tag]]),
  ),
  ...Object.fromEntries(
    ["lf-suggestion", "lf-old", "lf-new"].map((tag) => [tag, kernel[tag]]),
  ),
});

// The id of what takes the pointer at the first text in the element `id` names.
const takerAt = (id) => {
  const text = document
    .createTreeWalker(document.getElementById(id), NodeFilter.SHOW_TEXT)
    .nextNode();
  return aimableAt(text)?.id ?? null;
};

test("a control, a title, a preview of its own or a widget's drawn content takes the pointer", () => {
  document.body.innerHTML = `
    <p id="prose">Plain words.</p>
    <a id="link" href="#prose"><span id="in-link">Linked words.</span></a>
    <button id="button" type="button">Press</button>
    <div id="listbox" role="listbox"><span id="in-listbox">An item.</span></div>
    <div id="edit" contenteditable>Editable words.</div>
    <span id="titled" title="Said by the browser">Titled words.</span>
    <div id="card" tabindex="0"><p id="in-card">What the card holds.</p></div>
    <lf-code id="code"><pre id="in-code">x = 1</pre></lf-code>
    <lf-draft id="draft"><pre id="in-draft">A draft.</pre></lf-draft>`;
  document.getElementById("card").lfPreview = () => ({ name: "The card" });
  assert.deepEqual(
    Object.fromEntries(
      [
        "prose",
        "in-link",
        "button",
        "in-listbox",
        "edit",
        "titled",
        "in-card",
        "in-code",
        "in-draft",
      ].map((id) => [id, takerAt(id)]),
    ),
    {
      prose: null,
      "in-link": "link",
      button: "button",
      "in-listbox": "listbox",
      edit: "edit",
      titled: "titled",
      "in-card": "card",
      "in-code": "code",
      "in-draft": "draft",
    },
  );
});

test("a tab stop, a scrolling box, a frame's title or the author's words in a widget take nothing", () => {
  document.body.innerHTML = `
    <div id="stop" tabindex="0">Words a tab stop holds.</div>
    <div id="scroller" style="overflow: auto; height: 1em">Words that scroll.<br>More.</div>
    <lf-tabs id="tabs"><lf-tab id="tab"><lf-pane id="pane">Pane words.</lf-pane></lf-tab></lf-tabs>
    <lf-options id="options" choose><lf-option id="option"><span id="mark"
      role="checkbox">Open</span><span id="chip">An option.</span></lf-option></lf-options>
    <lf-suggestion id="suggestion"><lf-old><p id="old">Old words.</p></lf-old><lf-new><p
      id="new">New words.</p></lf-new></lf-suggestion>`;
  // A widget's verbs say what it records, not that a press on its content acts: what
  // takes the pointer in an option is its mark.
  assert.deepEqual(
    ["stop", "scroller", "pane", "chip", "old", "new", "mark"].map(takerAt),
    [null, null, null, null, null, null, "mark"],
  );
  // A frame's title is its accessible name, which no tooltip shows (the frame is left
  // unattached, since the test's document loads none).
  const frame = document.createElement("iframe");
  frame.title = "A frame's name";
  assert.equal(aimableAt(frame), null);
  // An element is asked as a text node is, from itself outward.
  assert.equal(aimableAt(document.getElementById("pane")), null);
});

test("what a shadow tree holds is asked from its host outward, and slotted words from their slot", () => {
  document.body.innerHTML = `<a id="host" href="#"></a><p id="bare"></p>
    <span id="slotting"><span id="slotted">Slotted words.</span></span>`;
  for (const id of ["host", "bare"])
    document.getElementById(id).attachShadow({ mode: "open" }).innerHTML =
      "<span>Shadow words.</span>";
  document.getElementById("slotting").attachShadow({ mode: "open" }).innerHTML =
    '<button id="slot-control" title="Slot control"><slot></slot></button>';
  const inside = (id) =>
    document.getElementById(id).shadowRoot.querySelector("span").firstChild;
  assert.equal(aimableAt(inside("host"))?.id, "host");
  assert.equal(aimableAt(inside("bare")), null);
  assert.equal(takerAt("slotted"), "slot-control");
});
