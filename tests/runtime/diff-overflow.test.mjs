import assert from "node:assert/strict";
import test from "node:test";
import { installLanguagePaths } from "../../browser/runtime/base/language-paths.js";
import { syntaxLanguagePaths } from "../../browser/runtime/lib/syntax-languages.js";
import { overflowFor } from "../../packages/diff/widgets/overflow.js";

test("a diff wraps the files the page's language table calls Markdown, and plain text", (t) => {
  t.after(() => installLanguagePaths(syntaxLanguagePaths));
  // A page whose packages call another extension Markdown, and take `md` away.
  installLanguagePaths({ ...syntaxLanguagePaths, mdx: "markdown", md: "text" });
  assert.equal(overflowFor("docs/a.mdx", null), "wrap");
  assert.equal(overflowFor("docs/A.MARKDOWN", null), "wrap");
  assert.equal(overflowFor("docs/a.md", null), "scroll");
  assert.equal(overflowFor("notes.txt", null), "wrap");
  assert.equal(overflowFor("Makefile", null), "scroll");
  assert.equal(overflowFor("docs/a.mdx", "scroll"), "scroll");
});
