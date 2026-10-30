/* A press that shows a symbol names its action, so one action shows one symbol on
 * every surface (browser/AGENTS.md, "Visual grammar"). */
import assert from "node:assert/strict";
import test from "node:test";
import {
  offerAction,
  offerActionElement,
  offeredAction,
} from "/runtime/widget-elements.js";
import { html, render } from "/runtime/framework.js";

const symbolOf = (control) =>
  [...control.querySelectorAll(":scope > svg")].map((svg) => svg.dataset.lfIcon);

test("a symbol shows its action's symbol and says its name unless its label says more", () => {
  const retry = offerAction("symbol", "", undefined, { action: "retry" });
  assert.deepEqual(symbolOf(retry), ["retry"]);
  assert.equal(retry.getAttribute("aria-label"), "Retry");
  assert.equal(retry.title, "Retry");
  const named = offerAction("symbol", "", "Retry loading the file", {
    action: "retry",
  });
  assert.equal(named.getAttribute("aria-label"), "Retry loading the file");
  assert.deepEqual(symbolOf(named), ["retry"]);
  // Close and Discard share ✕; the action, not the icon, is what a press names.
  assert.deepEqual(
    symbolOf(offerAction("mark", "", undefined, { action: "discard" })),
    ["cross"],
  );
});

test("a press can't show a symbol without naming one of Leaf's actions", () => {
  assert.throws(() => offerAction("symbol", "", "Retry"), /names the action/);
  assert.throws(
    () => offerAction("symbol", "", undefined, { action: "spin" }),
    /Unknown Leaf action/,
  );
  assert.throws(
    () => offerAction("word", "", "Go", { action: "next" }),
    /shows no action's symbol/,
  );
  // Words stay the author's: a page's own Done is a word, as Leaf's to-do's is.
  assert.equal(offerAction("word", "", "Done").textContent, "Done");
});

test("a template's symbol is drawn once and swaps only when its action's symbol changes", () => {
  const box = document.createElement("div");
  const draw = (action) =>
    render(
      html`<button ${offeredAction("symbol", "", undefined, { action })}></button>`,
      box,
    );
  draw("resolve");
  const button = box.querySelector("button");
  const check = button.firstElementChild;
  assert.deepEqual(symbolOf(button), ["check"]);
  // Resolve and Reopen are one toggle drawn as one check: nothing is rewritten.
  draw("reopen");
  assert.equal(button.firstElementChild, check);
  assert.equal(button.getAttribute("aria-label"), "Reopen");
  draw("play");
  assert.deepEqual(symbolOf(button), ["play"]);
});

test("an existing control owns its icon while a template action supplies its symbol", () => {
  const copy = document.createElement("wa-copy-button");
  const ownedIcon = document.createElement("span");
  ownedIcon.slot = "copy-icon";
  ownedIcon.textContent = "Own copy glyph";
  copy.append(ownedIcon);
  assert.equal(offerActionElement(copy, "mark", "copy-control", "Copy code"), copy);
  assert.equal(copy.firstElementChild, ownedIcon);
  assert.equal(copy.children.length, 1);
  assert.equal(copy.classList.contains("lf-mark-action"), true);
  assert.equal(copy.getAttribute("aria-label"), "Copy code");

  const root = document.createElement("div");
  render(
    html`<button ${offeredAction("mark", "", undefined, { action: "copy" })}></button>`,
    root,
  );
  const action = root.querySelector("button");
  assert.deepEqual(symbolOf(action), ["copy"]);
  assert.equal(action.getAttribute("aria-label"), "Copy");
});
