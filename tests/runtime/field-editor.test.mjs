/* The field's own Enter binding preserves code indentation and native editability,
   whether its Markdown reads as a draft or joins lines like the displayed file. */
import assert from "node:assert/strict";
import test from "node:test";

import { loadFieldEditor } from "/runtime/composing/field-editor.js";
import { keymap } from "/vendor/codemirror.esm.js";

for (const joined of [false, true]) {
  for (const readOnly of [false, true]) {
    test(`Enter ${readOnly ? "refuses a read-only" : "keeps indentation in an editable"} ${joined ? "file" : "draft"} code fence`, async () => {
      const { fieldState } = await loadFieldEditor();
      const source = "```\n    code\n```";
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
      assert.equal(enter.run(view), !readOnly);
      assert.equal(dispatched, readOnly ? 0 : 1);
      assert.equal(
        view.state.doc.toString(),
        readOnly ? source : "```\n    code\n    \n```",
      );
    });
  }
}
