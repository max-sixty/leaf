/* The file tree's rows and update as stories (`Story`, @effect/ui/testing): which rows
   the reader sees, where a key takes them and what a press asks of Leaf, with no page
   behind it. The drawing and focus on a page are the browser suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { Story } from "@effect/ui/testing";
import { Component, Effect, HtmlCommand } from "/vendor/effect-ui.js";
import { NavigateToDatum } from "/runtime/widget-services.js";
import {
  FileTree,
  FileTreeMessage,
  visibleRows,
} from "../../packages/file-tree/widgets/lf-file-tree.js";

const files = [
  { path: "README.md" },
  { path: "src/main.py", key: "main", status: /** @type {const} */ ("added") },
  { path: "src/lib/util.py" },
  { path: "docs/guide/intro/start.md" },
];
const props = { value: { files }, label: "Files", linked: true };
const all = { query: "", closed: [] };
/** @param {ReturnType<typeof visibleRows>} rows */
const names = (rows) => rows.map((row) => `${"  ".repeat(row.level - 1)}${row.name}`);
const found = { found: true };

/** @param {(s: any) => void} body */
const story = (body) =>
  Effect.gen(function* () {
    body(yield* Story.make(FileTree, props));
  }).pipe(Effect.scoped, Effect.runSync);

test("folders come first and open, and a folder holding one folder is one row", () => {
  assert.deepEqual(names(visibleRows(files, all)), [
    "docs/guide/intro",
    "  start.md",
    "src",
    "  lib",
    "    util.py",
    "  main.py",
    "README.md",
  ]);
});

test("search keeps the matching files and their folders, under the reader's expansion", () => {
  assert.deepEqual(names(visibleRows(files, { query: "PY", closed: [] })), [
    "src",
    "  lib",
    "    util.py",
    "  main.py",
  ]);
  assert.deepEqual(names(visibleRows(files, { query: "py", closed: ["src/lib"] })), [
    "src",
    "  lib",
    "  main.py",
  ]);
  assert.deepEqual(visibleRows(files, { query: "nothing", closed: [] }), []);
});

test("a folder the reader closed stays closed as the list changes, and a new one opens", () => {
  const closed = { query: "", closed: ["src"] };
  const grown = [...files, { path: "tests/test_main.py" }];
  assert.deepEqual(names(visibleRows(grown, closed)), [
    "docs/guide/intro",
    "  start.md",
    "src",
    "tests",
    "  test_main.py",
    "README.md",
  ]);
});

test("pressing a keyed file in a linked tree selects it and reveals its datum", () => {
  story((s) => {
    s.send(FileTreeMessage.UpdatedQuery({ value: "main" }))
      .send(FileTreeMessage.ClickedRow({ id: "file:src/main.py" }))
      .expectExact(
        NavigateToDatum.make({
          reference: "for",
          key: "main",
          success: "Opened src/main.py.",
          missing: "src/main.py is no longer available.",
        }),
      )
      .resolve(NavigateToDatum, Component.noop);
    assert.deepEqual(s.model, {
      query: "",
      closed: [],
      active: "file:src/main.py",
      picked: "src/main.py",
    });
  });
});

test("pressing a folder toggles it, and the arrows walk the rows", () => {
  story((s) => {
    s.send(FileTreeMessage.ClickedRow({ id: "folder:src" }));
    assert.deepEqual(s.model.closed, ["src"]);
    s.send(FileTreeMessage.PressedRowKey({ id: "folder:src", key: "ArrowRight" }));
    assert.deepEqual(s.model.closed, []);
    s.send(FileTreeMessage.PressedRowKey({ id: "folder:src", key: "ArrowRight" }))
      .resolve(HtmlCommand.Focus, found)
      .send(FileTreeMessage.PressedRowKey({ id: "folder:src/lib", key: "ArrowLeft" }));
    assert.equal(s.model.active, "folder:src/lib");
    assert.deepEqual(s.model.closed, ["src/lib"]);
    s.send(FileTreeMessage.PressedRowKey({ id: "folder:src/lib", key: "ArrowLeft" }))
      .resolve(HtmlCommand.Focus, found)
      .send(FileTreeMessage.PressedRowKey({ id: "folder:src", key: "End" }))
      .resolve(HtmlCommand.Focus, found);
    assert.equal(s.model.active, "file:README.md");
  });
});

test("a letter on a row types into the search, and Enter there chooses the first match", () => {
  story((s) => {
    s.send(FileTreeMessage.PressedRowKey({ id: "file:README.md", key: "y" }))
      .resolve(HtmlCommand.Focus, found)
      .send(FileTreeMessage.PressedSearchKey({ key: "Enter" }))
      .resolve(HtmlCommand.Focus, found);
    assert.equal(s.model.query, "");
    assert.equal(s.model.active, "file:src/lib/util.py");
  });
});

test("Escape empties the search", () => {
  story((s) => {
    s.send(FileTreeMessage.UpdatedQuery({ value: "main" })).send(
      FileTreeMessage.PressedSearchKey({ key: "Escape" }),
    );
    assert.equal(s.model.query, "");
  });
});

test("an unlinked tree keeps its selection local", () => {
  Effect.gen(function* () {
    const s = yield* Story.make(FileTree, { ...props, linked: false });
    s.send(FileTreeMessage.ClickedRow({ id: "file:src/main.py" }));
    assert.equal(s.model.picked, "src/main.py");
  }).pipe(Effect.scoped, Effect.runSync);
});
