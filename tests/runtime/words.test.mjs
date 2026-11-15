/* Words as a label reads them (words.js): an excerpt is cut at a word boundary in its
   second half, from words collapsed as a label collapses them, however much of a long
   value it reads to find them. */

import assert from "node:assert/strict";
import test from "node:test";

import { excerptWords } from "/runtime/words.js";

test("an excerpt of a long value says what one of all of it would", () => {
  const eleven = "word word word word word word word word word word word…";
  assert.equal(excerptWords("word ".repeat(1000), 60), eleven);
  // Whitespace that collapses to nothing leaves the start of the value too few letters
  // to cut, so more of it is read.
  assert.equal(excerptWords(`${" \n".repeat(400)}${"word ".repeat(1000)}`, 60), eleven);
  assert.equal(
    excerptWords(`${"word ".repeat(11)}${" ".repeat(400)}`, 60),
    eleven.slice(0, -1).trim(),
  );
  // A pair split where the start ends counts once, as the whole value counts it.
  assert.equal(excerptWords(`a${"😀".repeat(100)}`, 60), `a${"😀".repeat(58)}…`);
});
