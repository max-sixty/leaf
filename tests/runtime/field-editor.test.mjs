/* The field's own Enter binding preserves code indentation and native editability,
   whether its Markdown reads as a draft or joins lines like the displayed file. */
import assert from "node:assert/strict";
import test from "node:test";

import { loadMarkdown } from "/runtime/markdown.js";
import { loadFieldEditor } from "/runtime/composing/field-editor.js";
import { keymap } from "/vendor/codemirror.esm.js";

/** Press Enter with the caret after `code` in `source`, returning the press's result
 * and the words after it. */
async function enterAfterCode(source, { joined, readOnly = false }) {
  const { fieldState } = await loadFieldEditor();
  const caret = source.indexOf("code") + "code".length;
  const state = fieldState(
    { base: source, text: source, anchor: caret, head: caret, steps: [] },
    {
      typed: (_native, insert) => insert(),
      returned: () => true,
      oneLine: () => false,
      joined: () => joined,
      revealed: () => {},
      focused: () => {},
      readOnly,
      attributes: {},
    },
  );
  const enter = state
    .facet(keymap)
    .flat()
    .find(({ key }) => key === "Enter");
  assert.ok(enter?.run);
  let dispatched = 0;
  const view = {
    state,
    dispatch(transaction) {
      dispatched++;
      view.state = transaction.state;
    },
  };
  const handled = enter.run(view);
  assert.equal(dispatched, handled ? 1 : 0);
  return { handled, words: view.state.doc.toString() };
}

for (const joined of [false, true]) {
  for (const readOnly of [false, true]) {
    test(`Enter ${readOnly ? "refuses a read-only" : "keeps indentation in an editable"} ${joined ? "file" : "draft"} code fence`, async () => {
      const source = "```\n    code\n```";
      const { handled, words } = await enterAfterCode(source, { joined, readOnly });
      assert.equal(handled, !readOnly);
      assert.equal(words, readOnly ? source : "```\n    code\n    \n```");
    });
  }
}

test("Enter continues the indented code a Markdown body reads, as a file does", async () => {
  // The field reads its words as the body it edits does, where four spaces after a
  // blank line open code, so Return writes the code's next line rather than a break.
  assert.equal(await loadMarkdown(), true);
  const source = "Run:\n\n    code";
  assert.deepEqual(await enterAfterCode(source, { joined: true }), {
    handled: true,
    words: "Run:\n\n    code\n    ",
  });
});
