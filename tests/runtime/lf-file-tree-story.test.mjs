/* The file tree's update as stories (`Story`, @effect/ui/testing): what opening a file
   asks of Leaf, with no page or Trees behind it. Trees' rows and search on a page are
   the browser suite's. */
import test from "node:test";
import { Story } from "@effect/ui/testing";
import { Component, Effect } from "/vendor/effect-ui.js";
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

test("opening a keyed file in a linked tree reveals its datum", () => {
  story({}, (s) => {
    s.send(FileTreeMessage.OpenedFile({ path: "src/main.py" }))
      .expectExact(
        NavigateToDatum.make({
          reference: "for",
          key: "main",
          success: "Opened src/main.py.",
          missing: "src/main.py is no longer available.",
        }),
      )
      .resolve(NavigateToDatum, Component.noop);
  });
});

test("opening a file asks nothing of Leaf without a key or a reference", () => {
  story({}, (s) => s.send(FileTreeMessage.OpenedFile({ path: "README.md" })));
  story({ linked: false }, (s) =>
    s.send(FileTreeMessage.OpenedFile({ path: "src/main.py" })),
  );
});
