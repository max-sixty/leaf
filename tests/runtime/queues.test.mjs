import assert from "node:assert/strict";
import test from "node:test";
import { itemNoun } from "../../skills/leaf/assets/runtime/queues.js";

test("obligation and response rows keep their domain names", () => {
  assert.equal(itemNoun({ kind: "widget" }), "widget");
  assert.equal(itemNoun({ kind: "answer", answer: { kind: "reply" } }), "reply");
  assert.equal(itemNoun({ kind: "todo" }), "todo");
});
