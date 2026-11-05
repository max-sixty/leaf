/* Tab and Shift+Tab in a draft nest a list item and take it out a level
   (composing/field-editor.js, `nestItems`), by the renderer's reading of the draft, so
   the message reads the item where the source now stands it. */

import assert from "node:assert/strict";
import test from "node:test";

import { nestItems } from "/runtime/composing/field-editor.js";
import { loadMarkdown, placedMarkdownTokens } from "/runtime/markdown.js";

// Each draft marks the caret `|`, or a selection `«…»`, with the draft the press leaves:
// unchanged where the item has nowhere to go, and null where the press is no list's.
const TAB = {
  "an empty new item": ["- one\n- |", "- one\n  - "],
  "a numbered item, starting a list from 1": ["1. one\n2. |two", "1. one\n   1. two"],
  "a numbered item, joining the list there": [
    "1. one\n   1. a\n2. |two",
    "1. one\n   1. a\n   2. two",
  ],
  "a wider number": ["10. a\n11. |b", "10. a\n    1. b"],
  "a task": ["- [ ] one\n- [ ] |two", "- [ ] one\n  - [ ] two"],
  "an item in a quote": ["> - one\n> - |two", "> - one\n>   - two"],
  "an item with its lines and items": [
    "- a\n- |b\n  more\n  - c",
    "- a\n  - b\n    more\n    - c",
  ],
  "selected items, together": ["- a\n- «b\n  - c\n- d»", "- a\n  - b\n    - c\n  - d"],
  "the first item": ["- |one\n- two", "- one\n- two"],
  "words outside a list": ["plain|", null],
};
const SHIFT_TAB = {
  "a nested item": ["- one\n  - |two", "- one\n- two"],
  "a middle item, the next nesting in it": [
    "- a\n  - x\n  - |y\n  - z",
    "- a\n  - x\n- y\n  - z",
  ],
  "an item into a numbered list": ["1. a\n   - |b", "1. a\n2. b"],
  "an item in a quote": ["> - one\n>   - |two", "> - one\n> - two"],
  "a top-level item": ["- |one", "- one"],
};

function press(marked, deeper) {
  const caret = marked.indexOf("|");
  const source = marked.replace(/[|«»]/g, "");
  const from = caret === -1 ? marked.indexOf("«") : caret;
  const to = caret === -1 ? marked.indexOf("»") - 1 : caret;
  const changes = nestItems(source, placedMarkdownTokens(source), from, to, deeper);
  if (!changes) return null;
  let out = source;
  for (const { from: a, to: b, insert } of changes.toSorted((x, y) => y.from - x.from))
    out = out.slice(0, a) + insert + out.slice(b);
  return out;
}

test("Tab nests the item the caret or selection is in under the item above it", async () => {
  await loadMarkdown();
  for (const [name, [marked, left]] of Object.entries(TAB))
    assert.equal(press(marked, true), left, name);
});

test("Shift+Tab takes a nested item out into its parent's list", async () => {
  await loadMarkdown();
  for (const [name, [marked, left]] of Object.entries(SHIFT_TAB))
    assert.equal(press(marked, false), left, name);
});

test("a nested item reads as nested in the list the message renders", async () => {
  await loadMarkdown();
  const nested = press("- one\n- |two", true);
  const levels = placedMarkdownTokens(nested)
    .filter(({ token }) => token.type === "list_item_open")
    .map(({ token }) => token.level);
  assert.deepEqual(levels, [1, 3]);
});
