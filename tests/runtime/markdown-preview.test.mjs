/* A draft's preview (composing/field-editor.js) draws what its sent message will, from
   the reading of the renderer that sends it. A rule the renderer enables whose tokens
   the preview doesn't draw leaves its construct as source in the draft while the
   message renders it. This holds every rule the renderer's parser enables
   (markdown.js, `makeMarkdown`) to the token types the preview draws (`DRAWN`), or to
   an exception that says why its source stays as typed. */

import assert from "node:assert/strict";
import test from "node:test";

import { DRAWN } from "/runtime/composing/field-editor.js";
import { makeMarkdown } from "/runtime/markdown.js";

// What each rule emits that a reader sees, by the token type the preview reads it as:
// markdown-it's own rules, the task-list plugin's and Leaf's. [] is a rule that emits
// nothing seen: it drives, joins or annotates other rules' tokens.
const EMITS = {
  // core
  normalize: [],
  block: [],
  strip_references: [],
  inline: [],
  "github-task-lists": ["html_inline"],
  linkify: ["link_open"],
  text_join: [],
  blank_lines: [],
  safe_links: [],
  // block
  fence: ["fence"],
  blockquote: ["blockquote_open"],
  hr: ["hr"],
  list: ["bullet_list_open", "ordered_list_open", "list_item_open"],
  heading: ["heading_open"],
  paragraph: ["paragraph_open"],
  // inline, both passes
  text: ["text"],
  // A soft break is the source's own line break.
  newline: ["hardbreak"],
  // An escape's text_special is joined into the text around it.
  escape: ["text", "hardbreak"],
  backticks: ["code_inline"],
  strikethrough: ["s_open"],
  emphasis: ["em_open", "strong_open"],
  link: ["link_open"],
  image: ["image"],
  autolink: ["link_open"],
  entity: ["text"],
  balance_pairs: [],
  fragments_join: [],
};

// The rules whose constructs stay as typed in the draft, and why.
const AS_TYPED = {
  table: "a table's grid is more than the editor's lines can draw",
  reference: "a reference definition shows as typed, though the message drops its line",
  html_block: "html is off, so the rule matches nothing and its markup reads as text",
  html_inline: "html is off, so the rule matches nothing and its markup reads as text",
  replacements: "the typographer is off, so the rule changes nothing",
  smartquotes: "the typographer is off, so the rule changes nothing",
};

test("the draft draws each construct its message renders, or keeps one listed as typed", async () => {
  const markdown = makeMarkdown(await import("/vendor/markdown-it.esm.js"), true);
  // The exceptions for markup and typography rest on these.
  assert.equal(markdown.options.html, false);
  assert.equal(markdown.options.typographer, false);
  const enabled = new Set(
    [
      markdown.core.ruler,
      markdown.block.ruler,
      markdown.inline.ruler,
      markdown.inline.ruler2,
    ].flatMap((ruler) =>
      ruler.__rules__.filter((rule) => rule.enabled).map((rule) => rule.name),
    ),
  );
  const gaps = [];
  for (const name of enabled) {
    if (name in AS_TYPED) continue;
    if (!(name in EMITS)) gaps.push(`${name}: enabled, but neither drawn nor listed`);
    else
      for (const type of EMITS[name])
        if (!DRAWN.has(type))
          gaps.push(`${name}: the draft leaves its ${type} as source`);
  }
  // A rule turned off leaves its entry claiming what nothing emits.
  for (const name of [...Object.keys(EMITS), ...Object.keys(AS_TYPED)])
    if (!enabled.has(name)) gaps.push(`${name}: listed, but not enabled`);
  assert.deepEqual(gaps, []);
});
