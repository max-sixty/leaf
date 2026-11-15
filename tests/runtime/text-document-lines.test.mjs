/* What a new version of a long text document's text changes in its rows: which rows
   give way to which new ones, so the document patches the rows a change replaces and
   keeps every other row it drew. */

import assert from "node:assert/strict";
import test from "node:test";

import { changes } from "../../packages/default/widgets/lf-text-document.js";

/** Lines ending in a newline each, as a text ending in one is read. */
const lines = (/** @type {string[]} */ text) => ({
  text,
  endings: text.map(() => "\n"),
});
const numbered = (count, word = "line") =>
  Array.from({ length: count }, (_, at) => `${word} ${at}`);

test("added and removed rows give way where they stand", () => {
  assert.deepEqual(changes(lines(["a", "b", "c"]), lines(["new", "a", "b", "c"])), [
    { at: 0, removed: 0, to: 0, added: 1 },
  ]);
  assert.deepEqual(changes(lines(["a", "b", "c"]), lines(["a", "c"])), [
    { at: 1, removed: 1, to: 1, added: 0 },
  ]);
  assert.deepEqual(changes(lines(["a", "b"]), lines(["a", "b"])), []);
});

test("a run of rows replaced by others is one change, however many it adds", () => {
  assert.deepEqual(changes(lines(["a", "b", "c", "d"]), lines(["a", "B", "C", "d"])), [
    { at: 1, removed: 2, to: 1, added: 2 },
  ]);
  assert.deepEqual(changes(lines(["a", "b", "c"]), lines(["a", "X", "Y", "c"])), [
    { at: 1, removed: 1, to: 1, added: 2 },
  ]);
  // Changes apart stay apart, so each touches only its own rows.
  assert.deepEqual(changes(lines(["a", "b", "c"]), lines(["new", "a", "B", "c"])), [
    { at: 0, removed: 0, to: 0, added: 1 },
    { at: 1, removed: 1, to: 2, added: 1 },
  ]);
});

test("a row whose ending changes is a changed row", () => {
  const before = { text: ["a", "b", ""], endings: ["\n", "\n"] };
  const after = { text: ["a", "b", ""], endings: ["\r\n", "\n"] };
  assert.deepEqual(changes(before, after), [{ at: 0, removed: 1, to: 0, added: 1 }]);
});

test("a rewrite past the walk's cap is one change of every row", () => {
  const before = lines(numbered(2_000));
  assert.deepEqual(changes(before, lines(numbered(1_500, "rewritten"))), [
    { at: 0, removed: 2_000, to: 0, added: 1_500 },
  ]);
  // A few edits across the same text are well within it.
  const edited = before.text.map((line, at) => (at % 500 ? line : `${line} edited`));
  assert.deepEqual(
    changes(before, lines(edited)),
    [0, 500, 1_000, 1_500].map((at) => ({ at, removed: 1, to: at, added: 1 })),
  );
});
