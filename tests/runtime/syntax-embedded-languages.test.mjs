/* A Markdown text coloured a line at a time, as the file editor colours one, keeps
   colouring after a language its fences name loads elsewhere on the page, as a
   preview's code block loads one, and a text begun afterwards colours fences in it. */

import assert from "node:assert/strict";
import test from "node:test";
import { ensureSyntaxLanguage, syntaxNow } from "/runtime/lib/syntax-tokens.js";

test("a Markdown text begun before a fence's language loads keeps colouring", async () => {
  const { tokenize } = await syntaxNow("markdown");
  let { state } = tokenize("Settings look like this:");
  await ensureSyntaxLanguage("json");
  for (const line of ["- **`floor`** is a number:", "```json", '{"floor": 1}', "```"])
    ({ state } = tokenize(line, state));
  const { tokens } = tokenize("# Next", state);
  assert.equal(tokens[0]?.style.color, "var(--lf-syn-name)");
  const fresh = tokenize('```json\n{"floor": 300000}\n```').tokens;
  assert.equal(
    fresh.find((token) => token.text === "300000")?.style.color,
    "var(--lf-syn-number)",
  );
});
