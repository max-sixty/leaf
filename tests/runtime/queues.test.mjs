import assert from "node:assert/strict";
import test from "node:test";
import { taskNoun } from "../../skills/leaf/assets/runtime/queues.js";

test("ask and response rows keep their domain names", () => {
  assert.equal(taskNoun({ kind: "ask" }), "ask");
  assert.equal(taskNoun({ kind: "answer", answer: { kind: "reply" } }), "reply");
  assert.equal(taskNoun({ kind: "todo" }), "todo");
});
