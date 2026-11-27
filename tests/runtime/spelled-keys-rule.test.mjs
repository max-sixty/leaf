/* What `architecture/spelled-keys` refuses (eslint.config.mjs): the form a notice's
   or an error's words took to name a key for their step, which a press the panel's
   field offers says now (panel/field-readings.js, `press`). */

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
    'notice("Draft kept; g i resumes it");',
    'const said = [hidden.length && "Draft kept — g i resumes writing"];',
    // An announcement says its keys through the register (`saying`), not in its words.
    "announce(`${title} — g t opens it`);",
  ])
    assert.equal(reports(code), 1, code);
});

test("words that name no key are admitted", () => {
  for (const code of [
    'notice("Draft kept", { press });',
    "raiseError(`Couldn't send — attempt ${attempt} is already in use`);",
    // A count or the article after a dash is no key.
    'notice("Saved — 3 changes since v2");',
    'raiseError("Couldn\'t start — a process exited");',
    'notice("Its box is gone, so its words moved to a comment on the page");',
    "announce(`Go to — 3 visible targets. ${saying(rows)}`);",
  ])
    assert.equal(reports(code), 0, code);
});
