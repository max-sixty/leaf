/* What a stable reference to an authored target keeps, and what it refuses to guess.

   Resolution is three-valued and only `resolved` carries an element, so each case
   here reads the status rather than the node: a reference that cannot prove which
   candidate owns it must say `ambiguous`, not hand back whichever node now occupies
   an ordinal. */

import assert from "node:assert/strict";
import test from "node:test";

import {
  captureTargetReference,
  resolveTargetReference,
} from "/runtime/target-references.js";

const scope = (markup) => {
  document.body.innerHTML = `<section id="scope">${markup}</section>`;
  return document.querySelector("#scope");
};

test("an authored id is the target's exact identity", () => {
  const root = scope('<article id="exact">Exact target</article>');
  const target = root.querySelector("#exact");
  const reference = captureTargetReference(root, target);

  assert.deepEqual(reference, { kind: "id", id: "exact" });
  const reading = resolveTargetReference(root, reference);
  assert.equal(reading.status, "resolved");
  assert.equal(reading.element, target);
});

test("an id differing only in case names nothing", () => {
  const root = scope('<article id="exact">Exact target</article>');
  assert.equal(
    resolveTargetReference(root, { kind: "id", id: "EXACT" }).status,
    "detached",
  );
});

test("a repeated id is ambiguous and carries no element", () => {
  const root = scope('<article id="exact">Exact target</article>');
  const reference = captureTargetReference(root, root.querySelector("#exact"));
  const duplicate = document.createElement("div");
  duplicate.id = "exact";
  root.append(duplicate);

  const repeated = resolveTargetReference(root, reference);
  assert.equal(repeated.status, "ambiguous");
  assert.ok(!Object.hasOwn(repeated, "element"));
});

test("a step through a declared shadow tree says which tree it crossed", () => {
  const root = scope('<article id="host"></article>');
  const host = root.querySelector("#host");
  host.attachShadow({ mode: "open" }).innerHTML = "<div><b>Inside</b></div>";
  const target = host.shadowRoot.querySelector("b");

  const reference = captureTargetReference(root, target);
  assert.deepEqual(reference, {
    kind: "structure",
    anchor: "host",
    path: [
      { tree: "shadow", tag: "div" },
      { tree: "light", tag: "b" },
    ],
  });
  assert.equal(resolveTargetReference(root, reference).element, target);
});
