import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { overflowFor } from "../../packages/diff/widgets/overflow.js";

const { paths } = JSON.parse(
  readFileSync(new URL("../../browser/registry.json", import.meta.url), "utf8"),
).$languages;

test("a diff wraps the files the language table calls Markdown, and plain text", () => {
  // The classic first-paint script can't read the registry, so the rule spells the
  // Markdown extensions out; a new one in the table must reach it too.
  const modes = Object.fromEntries(
    Object.keys(paths).map((extension) => [
      extension,
      overflowFor(`docs/a.${extension.toUpperCase()}`, null),
    ]),
  );
  const expected = Object.fromEntries(
    Object.entries(paths).map(([extension, language]) => [
      extension,
      language === "markdown" ? "wrap" : "scroll",
    ]),
  );
  assert.deepEqual(modes, expected);
  assert.equal(overflowFor("notes.txt", null), "wrap");
  assert.equal(overflowFor("Makefile", null), "scroll");
  assert.equal(overflowFor("docs/a.md", "scroll"), "scroll");
});
