/* How long one line may hold the main thread while it is coloured (`syntax`): a line
   up to Leaf's cap is coloured to its end however long its tokenizing takes, and a
   longer one, such as minified code, stays in plain ink without being tokenized, so
   the line after it is still coloured. */

import assert from "node:assert/strict";
import test from "node:test";
import { syntax } from "/runtime/lib/syntax-tokens.js";

const after = "\nconst kept = 1; // keep the source\n";

test("a line past the cap stays plain, and the next line is still coloured", async () => {
  const long = "let a = 1; ".repeat(2000);
  const { tokens } = await syntax(long + after, "javascript");
  assert.equal(tokens.map((token) => token.text).join(""), long + after);
  assert.deepEqual(tokens[0], { text: long + "\n", style: {} });
  assert.equal(
    tokens.find((token) => token.text === "// keep the source")?.style.color,
    "var(--lf-syn-comment)",
  );
});

test("a line under the cap is coloured to its end", async () => {
  const short = "let a = 1; ".repeat(100);
  const { tokens } = await syntax(short + after, "javascript");
  assert.ok(tokens.length > 300);
  assert.ok(tokens[0].style.color);
});
