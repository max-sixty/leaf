/* Line correspondence across two versions of a text: which old line each new line
   stands for, which a long text document reads to keep its drawn rows. */

import assert from "node:assert/strict";
import test from "node:test";

import { keptLines } from "/runtime/text-alignment.js";

const lines = (count, word = "line") =>
  Array.from({ length: count }, (_, at) => `${word} ${at}`);

test("added lines stand for nothing and shift the lines after them", () => {
  assert.deepEqual(keptLines(["a", "b", "c"], ["new", "a", "b", "c"]), [-1, 0, 1, 2]);
  assert.deepEqual(keptLines(["a", "b", "c"], ["a", "c"]), [0, 2]);
});

test("a run of lines replaced by as many others stands for them one for one", () => {
  assert.deepEqual(keptLines(["a", "b", "c", "d"], ["a", "B", "C", "d"]), [0, 1, 2, 3]);
  assert.deepEqual(keptLines(["a", "b", "c"], ["new", "a", "B", "c"]), [-1, 0, 1, 2]);
  // Replaced by more or fewer lines, a run stands for none of them.
  assert.deepEqual(keptLines(["a", "b", "c"], ["a", "X", "Y", "c"]), [0, -1, -1, 2]);
});

test("a rewrite past the walk's cap gives up rather than walk every line", () => {
  const before = lines(20_000);
  assert.equal(keptLines(before, lines(20_000, "rewritten")), null);
  assert.equal(
    keptLines(
      before,
      before.map((line, at) => (at % 10 ? line : `${line} edited`)),
    ),
    null,
  );
  // A few edits across the same text are well within it.
  const edited = before.map((line, at) => (at % 4_000 ? line : `${line} edited`));
  assert.deepEqual(keptLines(before, edited), [...before.keys()]);
});
