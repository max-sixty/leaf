/* A text document paints each token colour through a highlight named by the colour's
   variable (lf-text-document.js, `tokenHighlight`), and its stylesheet declares the
   rule for each: every colour the token theme gives must have one, or its tokens stand
   in plain ink. */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { foreground, leafTheme } from "../../build/entries/syntax/entry.mjs";

const css = readFileSync(
  new URL("../../packages/default/styles/text-document.css", import.meta.url),
  "utf8",
);

test("every token colour has the highlight rule that paints it", () => {
  const colours = new Set(
    leafTheme.tokenColors
      .map(({ settings }) => settings.foreground)
      .filter((colour) => colour && colour !== foreground),
  );
  assert.ok(colours.size > 0);
  for (const colour of colours) {
    const name = colour.match(/^var\(--([\w-]+)\)$/)?.[1];
    assert.ok(name, `${colour} is no colour variable`);
    assert.match(
      css,
      new RegExp(`::highlight\\(lf-token-${name}\\) \\{\\s*color: var\\(--${name}\\);`),
      `no rule paints lf-token-${name}`,
    );
  }
});
