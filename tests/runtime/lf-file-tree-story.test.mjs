/* The file tree's update as stories (`Story`, @effect/ui/testing): what the reader's
   acts in the search and the rows do to the query, and what opening a file asks of
   Leaf, with no page or Trees behind it. Trees' rows on a page are the browser
   suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { Story } from "@effect/ui/testing";
import { Component, Effect, HtmlCommand } from "/vendor/effect-ui.js";
import { NavigateToDatum } from "/runtime/widget-services.js";
import {
  FileTree,
  FileTreeMessage,
} from "../../packages/file-tree/widgets/lf-file-tree.js";

const files = [{ path: "README.md" }, { path: "src/main.py", key: "main" }];
const props = { value: { files }, label: "Files", linked: true };

/** @param {Record<string, unknown>} given @param {(s: any) => void} body */
const story = (given, body) =>
  Effect.gen(function* () {
    body(yield* Story.make(FileTree, { ...props, ...given }));
  }).pipe(Effect.scoped, Effect.runSync);

test("opening a keyed file in a linked tree empties the search and reveals its datum", () => {
  story({}, (s) => {
    s.send(FileTreeMessage.UpdatedQuery({ value: "main" }))
      .send(FileTreeMessage.OpenedFile({ path: "src/main.py" }))
      .expectExact(
        NavigateToDatum.make({
          reference: "for",
          key: "main",
          success: "Opened src/main.py.",
          missing: "src/main.py is no longer available.",
        }),
      )
      .resolve(NavigateToDatum, Component.noop);
    assert.equal(s.model.query, "");
  });
});

test("opening a file asks nothing of Leaf without a key or a reference", () => {
  story({}, (s) => s.send(FileTreeMessage.OpenedFile({ path: "README.md" })));
  story({ linked: false }, (s) =>
    s.send(FileTreeMessage.OpenedFile({ path: "src/main.py" })),
  );
});

test("a letter typed on a row types into the search and puts the reader there", () => {
  story({}, (s) => {
    s.send(FileTreeMessage.UpdatedQuery({ value: "ma" }))
      .send(FileTreeMessage.TypedOnRow({ key: "i" }))
      .resolve(HtmlCommand.Focus, { found: true });
    assert.equal(s.model.query, "mai");
  });
});

test("Escape, a chosen match and Trees closing its search each empty the search", () => {
  for (const message of [
    FileTreeMessage.PressedEscape(),
    FileTreeMessage.ChoseMatch(),
    FileTreeMessage.ClosedTreeSearch(),
  ])
    story({}, (s) => {
      s.send(FileTreeMessage.UpdatedQuery({ value: "main" })).send(message);
      assert.equal(s.model.query, "");
    });
});
