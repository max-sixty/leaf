/* A data body's text, the lines a module draws and numbers.

   `page check` counts the same lines to hold an lf-code `lines` numbering to its
   body, and `test_interact_document.py` reads these cases against that gate. The
   whitespace at the edges is where the two runtimes' own `\s` differ, so a body ending
   in one of those characters is numbered here exactly as the gate counts it. */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { bodyText } from "/runtime/widget-upgrade.js";

const { cases } = JSON.parse(
  readFileSync(new URL("../body_text_cases.json", import.meta.url)),
);

test("a data body's text drops its <pre>'s layout and the browser's whitespace alone", () => {
  for (const [body, text] of cases) {
    const widget = document.createElement("lf-code");
    const pre = document.createElement("pre");
    pre.textContent = body;
    widget.append(pre);
    assert.equal(bodyText(widget), text, JSON.stringify(body));
  }
});
