import assert from "node:assert/strict";
import test from "node:test";
import { endsByDone, selectDone, selectQueues, taskNoun } from "../../skills/leaf/assets/runtime/queues.js";
import { servedReading, servedWorkflow } from "../served.mjs";

const reading = () => servedReading("queues on both sides");
const kinds = (items) => items.map(({ kind, id }) => [kind, id]);
const collection = (all) => ({
  all,
  user: all.filter((question) => question.next_actor === "user"),
  unanswered: all.filter((question) => question.status === "open"),
});

test("the browser selects the same two queues page state prints", () => {
  const { queues, ...served } = reading();
  assert.deepEqual(selectQueues(served), { onYou: queues.on_you, onAgent: queues.on_agent });
});

const sending = (id, subject, thread) => servedWorkflow({
  id: `pending:${id}`, subject, thread, holds_thread: subject.kind === "thread",
  answer: null, stage: "sending", condition: null, next_actor: "agent",
});

test("a follow-up sent in a thread replaces its accepted response obligation", () => {
  const served = reading();
  const workflows = [...served.workflows, sending("a3", { kind: "thread", id: "e3" }, "e3")];
  assert.deepEqual(kinds(selectQueues({ ...served, workflows }).onAgent), [
    ["answer", "pending:a3"], ["task", "e6"],
  ]);
});

test("a pending widget gesture changes no admitted Question membership", () => {
  const served = reading();
  const workflows = [...served.workflows, sending("a2", { kind: "widget", id: "pick" }, null)];
  assert.deepEqual(selectQueues({ ...served, workflows }), selectQueues(served));
});

test("Question rows select the canonical next actor without becoming Tasks", () => {
  const served = reading();
  const all = served.questions.all.map((question) => question.source.kind === "widget"
    ? { ...question, next_actor: "agent" } : question);
  const queues = selectQueues({ ...served, questions: collection(all) });
  assert.ok(queues.onYou.every((item) => item.kind !== "question" || item.question.source.kind !== "widget"));
  assert.ok(queues.onYou.some((item) => item.kind === "task"));
  assert.ok(served.questions.all.some((question) => question.source.kind === "widget"));
});

test("Question and response rows keep their domain names", () => {
  assert.equal(taskNoun({ kind: "question", ends: "widget" }), "question");
  assert.equal(taskNoun({ kind: "question", ends: "reply" }), "question");
  assert.equal(taskNoun({ kind: "answer", answer: { kind: "reply" } }), "reply");
  assert.equal(taskNoun({ kind: "task", ends: "done" }), "task");
});

test("Done lists completed Questions and explicit Tasks through their own records", () => {
  const served = servedReading("done");
  const done = selectDone(served);
  const answered = done.find((item) => item.kind === "question");
  assert.equal(answered.question.status, "answered");
  assert.equal(answered.id, answered.question.id);
  assert.equal(answered.state, "done");
  assert.ok(done.some((item) => item.kind === "task" && item.title === "Check the colours"));
});

test("only an explicit user Task offers Done", () => {
  const { onYou, onAgent } = selectQueues(reading());
  const question = onYou.find((item) => item.kind === "question");
  const task = onYou.find((item) => item.kind === "task");
  const agentTask = onAgent.find((item) => item.kind === "task");
  assert.deepEqual([question, task, agentTask].map(endsByDone), [false, true, false]);
});
