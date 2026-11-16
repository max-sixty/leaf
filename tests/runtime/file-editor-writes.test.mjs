/* A write from elsewhere into a file the editor holds, open or kept while another is
   open: what Undo does after it. */
import assert from "node:assert/strict";
import test from "node:test";

import { EditorView, historyKeymap } from "/vendor/codemirror.esm.js";
import { createEditor, followKept, mergeKept } from "/widgets/editor.js";

/** An editor showing `text`, with its view for typing as the reader would. */
function editorOf(text) {
  const parent = document.body.appendChild(document.createElement("div"));
  const editor = createEditor(parent, { text });
  const view = EditorView.findFromDOM(parent.querySelector(".cm-editor"));
  assert.ok(view);
  return { editor, view };
}

/** Replace `from`..`to` with `insert` as the reader's own keystrokes do. */
const type = (view, from, to, insert) =>
  view.dispatch({ changes: { from, to, insert }, userEvent: "input.type" });

/** Undo once on `state`, as Mod-z does; the state after it, or null where nothing is
 * left to undo. */
function undo(state) {
  const binding = historyKeymap.find(({ key }) => key === "Mod-z");
  assert.ok(binding?.run);
  let next = null;
  binding.run({
    state,
    dispatch(transaction) {
      next = transaction.state;
    },
  });
  return next;
}

/** Every text Undo walks `state` back through, from `state` itself. */
function undone(state) {
  const texts = [];
  for (let at = state; at; at = undo(at)) texts.push(at.doc.toString());
  return texts;
}

test("Undo after a write followed into a kept file never corrupts its text", () => {
  const { editor, view } = editorOf("one\n");
  type(view, 0, 3, "user");
  const kept = followKept(editor.suspend(), "agent\n");
  assert.deepEqual(undone(kept.state), ["agent\n"]);
});

// The reader changed line one and saved it, then typed on line three; the agent then
// rewrites line one, which the draft doesn't touch relative to what is on disk.
const saved = "user\n\nthree\n";
const draft = (view) => {
  type(view, 0, 3, "user");
  type(view, saved.length - 1, saved.length - 1, "!");
};

test("Undo after a write merged into a kept file never corrupts a line the reader saved", () => {
  const { editor, view } = editorOf("one\n\nthree\n");
  draft(view);
  const kept = mergeKept(editor.suspend(), saved, "agent\n\nthree\n");
  assert.ok(kept);
  assert.deepEqual(undone(kept.state), ["agent\n\nthree!\n"]);
});

test("Undo after a write merged into the open file never corrupts a line the reader saved", () => {
  const { editor, view } = editorOf("one\n\nthree\n");
  draft(view);
  assert.ok(editor.merge(saved, "agent\n\nthree\n"));
  assert.deepEqual(undone(view.state), ["agent\n\nthree!\n"]);
});
