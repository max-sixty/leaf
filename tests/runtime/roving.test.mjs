/* A group's one Tab stop: Tab reaches only the stop. */

import assert from "node:assert/strict";
import test from "node:test";

import { rove } from "/runtime/lib/roving.js";

test("a roving group offers one Tab stop", () => {
  const items = [0, 1, 2].map(() => document.createElement("button"));
  rove(items, items[1]);
  assert.deepEqual(
    items.map((item) => item.getAttribute("tabindex")),
    ["-1", "0", "-1"],
  );
});
