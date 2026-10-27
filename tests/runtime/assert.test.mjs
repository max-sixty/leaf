/* The comparisons a runtime test makes go through tests/runtime/assert.mjs, which writes
   each node as a reference. Asked here: a failure writes each node as its opening tag,
   wherever in the values a node hangs. */

import assert from "node:assert/strict";
import test from "node:test";

const filled = () => {
  const root = document.createElement("main");
  for (let index = 0; index < 150; index += 1)
    root.append(Object.assign(document.createElement("p"), { id: `p${index}` }));
  document.body.append(root);
  return root;
};

const failure = (compare) => {
  try {
    compare();
  } catch (error) {
    return error;
  }
  assert.fail("the comparison passed");
};

test("a failed comparison writes a node reached only through a cycle as its tag", () => {
  const root = filled();
  try {
    // The cycle closes through `loop` before the walk reaches the node beside it.
    const value = (id) => {
      const holder = { loop: {} };
      holder.loop.back = holder;
      holder.node = document.getElementById(id);
      return holder;
    };
    const error = failure(() => assert.deepStrictEqual(value("p1"), value("p2")));
    assert.ok(error instanceof assert.AssertionError, String(error));
    assert.match(error.message, /<p id="p1"> #\d+/);
  } finally {
    root.remove();
  }
});
