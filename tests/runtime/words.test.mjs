/* Words as a label reads them (lib/words.js): an excerpt is cut at a word boundary in
   its second half, from words collapsed as a label collapses them, however much of a
   long value it reads to find them; and a label collapses the whitespace a passage
   does. */

import assert from "node:assert/strict";
import test from "node:test";

import { COLLAPSE } from "/runtime/kernel-facts.js";
import { excerptWords, labelWords } from "/runtime/lib/words.js";

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

test("a label collapses the whitespace a passage collapses", () => {
  // The library reads JavaScript's own whitespace class, and a passage the kernel
  // registry's list (`$passages.collapse`), which spells that class out for Python. A
  // label cut from a quote would otherwise keep a space the quote folded.
  const passage = new RegExp(`^(?:${COLLAPSE.source})$`);
  const differing = [];
  for (let point = 0; point <= 0x10ffff; point += 1) {
    const character = String.fromCodePoint(point);
    if (/^\s$/u.test(character) !== passage.test(character))
      differing.push(`U+${point.toString(16).toUpperCase().padStart(4, "0")}`);
  }
  assert.deepEqual(differing, []);
  assert.equal(labelWords(" a \n﻿ b　"), "a b");
});
