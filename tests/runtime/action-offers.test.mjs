/* A press that shows a symbol names its action, so one action shows one symbol on
 * every surface (browser/AGENTS.md, "Controls are few and quiet"). */
import assert from "node:assert/strict";
import test from "node:test";
import { nameAction } from "/runtime/control-labels.js";
import { offerAction, offeredAction } from "/runtime/widget-elements.js";
import { html, render } from "/runtime/framework.js";

const symbolOf = (control) =>
  [...control.querySelectorAll(":scope > svg")].map((svg) => svg.dataset.lfIcon);
// What `make` makes in a document the runtime doesn't upgrade, which prepaint marks
// (`data-lf-interactive`).
const offLeaf = (make) => {
  const root = document.documentElement;
  root.toggleAttribute("data-lf-interactive", false);
  try {
    return make();
  } finally {
    root.toggleAttribute("data-lf-interactive", true);
  }
};

test("a symbol shows its action's symbol and says its name unless its label says more", () => {
  const retry = offerAction("symbol", "", undefined, { action: "retry" });
  assert.deepEqual(symbolOf(retry), ["retry"]);
  assert.equal(retry.getAttribute("aria-label"), "Retry");
  // On Leaf the preview says its word on every route, so it writes no title, which the
  // browser would show to a pointer instead (preview.js); off Leaf the title is the
  // only reading a pointer gets.
  assert.equal(retry.getAttribute("title"), null);
  const plain = offLeaf(() =>
    offerAction("symbol", "", undefined, { action: "retry" }),
  );
  assert.equal(plain.getAttribute("title"), "Retry");
  const named = offerAction("symbol", "", "Retry loading the file", {
    action: "retry",
  });
  assert.equal(named.getAttribute("aria-label"), "Retry loading the file");
  assert.deepEqual(symbolOf(named), ["retry"]);
  // Undo and Discard share the U-turn; the action, not the icon, is what a press names.
  assert.deepEqual(
    symbolOf(offerAction("mark", "", undefined, { action: "discard" })),
    ["undo"],
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
  // Words stay the author's: a page's own Done may be a word.
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

test("a symbol whose action follows its state takes the new action's symbol and name", () => {
  const button = offerAction("symbol", "lf-x", undefined, { action: "expand-all" });
  const face = button.className;
  nameAction(button, "collapse-all");
  assert.deepEqual(symbolOf(button), ["fold"]);
  assert.equal(button.getAttribute("aria-label"), "Collapse all");
  // A label says more, and the role's face stays as it was.
  nameAction(button, "expand-all", { label: "Expand all files" });
  assert.deepEqual(symbolOf(button), ["unfold"]);
  assert.equal(button.getAttribute("aria-label"), "Expand all files");
  assert.equal(button.getAttribute("title"), null);
  offLeaf(() => nameAction(button, "collapse-all"));
  assert.equal(button.getAttribute("title"), "Collapse all");
  assert.equal(button.className, face);
});
