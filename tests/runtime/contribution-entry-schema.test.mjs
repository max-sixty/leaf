/* The `shared-contribution-actions` eval fails an answer that uses an entry option or
   enum value the runtime refuses, so its rubric spells out the accepted ones. This
   holds that prose to `CONTRIBUTION_ENTRY_SCHEMA`, so a change to the grammar fails
   here until the rubric scores answers against the same lists. */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { parse } from "yaml";
import { CONTRIBUTION_ENTRY_SCHEMA } from "../../browser/runtime/contribution-model.js";

const rubric = () => {
  const path = new URL(
    "../../evals/shared-contribution-actions/case.yaml",
    import.meta.url,
  );
  const [assertion] = parse(readFileSync(path, "utf8")).assert;
  return assertion.value.replace(/\s+/g, " ");
};
/** @param {string} text */
const names = (text) => text.split(/, | and /).map((name) => name.trim());
/** @param {string} text @param {RegExp} pattern */
const listed = (text, pattern) => {
  const match = text.match(pattern);
  assert.ok(match, `the rubric no longer matches ${pattern}`);
  return names(match[1]);
};

test("the contribution eval's rubric lists exactly the entry grammar", () => {
  const text = rubric();
  const lists = {
    options: listed(text, /The accepted entry options are ([^.]+)\./),
    behaviors: listed(text, /The accepted entry behaviors are ([^;]+);/),
    tones: listed(text, /; tones ([^;]+);/),
    ranks: listed(text, /; ranks ([^;]+);/),
    states: listed(text, /; states ([^.]+)\./),
  };
  for (const [field, words] of Object.entries(lists))
    assert.deepEqual(
      [...words].sort(),
      [...CONTRIBUTION_ENTRY_SCHEMA[field]].sort(),
      field,
    );
});
