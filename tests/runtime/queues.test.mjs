import assert from "node:assert/strict";
import test from "node:test";
import { taskNoun } from "../../skills/leaf/assets/runtime/queues.js";

test("Question and response rows keep their domain names", () => {
  assert.equal(taskNoun({ kind: "question", ends: "widget" }), "question");
  assert.equal(taskNoun({ kind: "question", ends: "reply" }), "question");
  assert.equal(taskNoun({ kind: "answer", answer: { kind: "reply" } }), "reply");
  assert.equal(taskNoun({ kind: "task", ends: "done" }), "task");
});
