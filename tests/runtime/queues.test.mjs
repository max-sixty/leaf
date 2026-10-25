import assert from "node:assert/strict";
import test from "node:test";
import { itemNoun } from "../../browser/runtime/queues.js";

test("obligation and response rows keep their domain names", () => {
  assert.equal(itemNoun({ kind: "widget" }), "widget");
  assert.equal(itemNoun({ kind: "update", owner: "agent", thread: "t1" }), "reply");
  assert.equal(itemNoun({ kind: "update", owner: "agent", thread: null }), "answer");
  assert.equal(itemNoun({ kind: "update", owner: "user", thread: "t1" }), "resend");
  assert.equal(itemNoun({ kind: "todo" }), "todo");
});
