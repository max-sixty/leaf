/* A write from elsewhere into a file the editor holds, open or kept while another is
   open: what Undo does after it, and which lines it marks. */
import assert from "node:assert/strict";
import test from "node:test";

import { EditorView, historyKeymap } from "/vendor/file-editor.esm.js";
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

/** Each line `state` marks as written elsewhere, as its mark and line number. */
function marked(state) {
  const marks = [];
  for (const set of state.facet(EditorView.decorations)) {
    if (typeof set === "function") continue;
    for (const at = set.iter(); at.value; at.next())
      if (at.value.spec.class?.startsWith("lf-written"))
        marks.push(`${at.value.spec.class} ${state.doc.lineAt(at.from).number}`);
  }
  return marks;
}

test("A write from elsewhere marks the lines it changed and no line beside them", () => {
  for (const [before, after, marks] of [
    // A line put in above one it left alone, as a list item or config key is.
    ["key: 1\nother: 2\n", "key: 1\nkey: 3\nother: 2\n", ["lf-written 2"]],
    ["one\ntwo\nthree\n", "new\none\ntwo\nthree\n", ["lf-written 1"]],
    // The diff inserts "wo\nt" after the "t" of "three".
    ["one\nthree\n", "one\ntwo\nthree\n", ["lf-written 2"]],
    // A line added at the end, after a final line break and without one.
    ["one\n", "one\ntwo\n", ["lf-written 2"]],
    ["one", "one\ntwo", ["lf-written 2"]],
    ["", "a\n", ["lf-written 1"]],
    // A change that ends at a line break, and one within a line.
    ["one\ntwo\n", "ONE\ntwo\n", ["lf-written 1"]],
    ["alpha\nbeta\ngamma\n", "alpha\nbeta2\ngamma\n", ["lf-written 2"]],
    // Lines taken away mark the gap, not the line after it; the diff takes "wo\nt".
    ["one\ntwo\nthree\n", "one\nthree\n", ["lf-written-gap 2"]],
    ["one\ntwo\n", "one\n", ["lf-written-gap 2"]],
    ["one\ntwo", "one", ["lf-written-gap-below 1"]],
    // A rewrapped paragraph keeps its count of lines, so it leaves no gap, though its
    // diff joins one line to the next and splits another.
    ["aaa\nbbb ccc\n", "aaa bbb\nccc\n", ["lf-written 1", "lf-written 2"]],
  ]) {
    const { editor, view } = editorOf(before);
    editor.follow(after);
    assert.equal(view.state.doc.toString(), after);
    assert.deepEqual(marked(view.state), marks, JSON.stringify([before, after]));
  }
});
