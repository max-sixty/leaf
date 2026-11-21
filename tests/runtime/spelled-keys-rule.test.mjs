/* What `architecture/spelled-keys` refuses (eslint.config.mjs).

   A notice's or an error's words name no key: the step they point to is a press the
   panel's field offers with its key. What a screen reader hears from `announce` may
   name one, since no press reaches it. */

import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { spelledKeysRule } from "../../eslint.config.mjs";
import { ruleReports } from "./lint-rule.mjs";

const filename = fileURLToPath(
  new URL("../../browser/runtime/probe.js", import.meta.url),
);

// How many times the rule reports on `code`.
const reports = (code) => ruleReports(spelledKeysRule, code, { filename }).length;

test("words that spell a key for a step are refused", () => {
  for (const code of [
    // The notices and the refusal's sentence before they offered presses.
    'notice("Annotations hidden — o shows them");',
    "notice(`${counted(n, 'change')} since v${since.version} — v shows them`);",
    'notice("Edit discarded; g D restores it");',
    'const said = [hidden.length && "Draft kept — g i resumes writing"];',
  ])
    assert.equal(reports(code), 1, code);
});

test("words that name no key, or that a screen reader hears, are admitted", () => {
  for (const code of [
    'notice("Draft kept", { press });',
    "raiseError(`Couldn't send — attempt ${attempt} is already in use`);",
    'notice("Its box is gone, so its words moved to a comment on the page");',
    "announce(`Draw mode: each stroke adds to one drawing, and z takes one back. ${'Escape leaves.'}`);",
    "announce(`${title} — g t opens it`);",
  ])
    assert.equal(reports(code), 0, code);
});
