import assert from "node:assert/strict";
import test from "node:test";
import { selectDone, selectQueues } from "../../skills/leaf/assets/runtime/queues.js";
import { foldThreads } from "../../skills/leaf/assets/runtime/thread/model.js";
import { servedReading, servedWorkflow } from "../served.mjs";

const reading = () => servedReading("queues on both sides");
const kinds = (items) => items.map(({ kind, id }) => [kind, id]);

test("the browser selects the same two queues page state prints", () => {
  const { queues, ...served } = reading();
  assert.deepEqual(selectQueues(served), {
    onYou: queues.on_you,
    onAgent: queues.on_agent,
  });
});

// A send this tab has not delivered, in the shape the publisher gives it.
const sending = (id, subject, thread) =>
  servedWorkflow({
    id: `pending:${id}`,
    subject,
    thread,
    holds_thread: subject.kind === "thread",
    answer: null,
    stage: "sending",
    condition: null,
    next_actor: "agent",
  });

test("a reply the user is sending moves its thread to the agent's queue at once", () => {
  const served = reading();
  // The publisher folds the pending reply into its thread, which then waits on the
  // agent, and lists the reply's own workflow after the served ones.
  const [thread] = served.threads.filter((candidate) => candidate.id === "e1");
  const threads = foldThreads(
    served.threads,
    [
      {
        id: "pending:a1",
        attempt: "a1",
        kind: "reply",
        parent: thread.msgs.at(-1).id,
        author: "user",
        text: "Weekly.",
        pending: true,
      },
    ],
    [],
    [],
    new Set(),
  );
  const workflows = [
    ...served.workflows,
    sending("a1", { kind: "thread", id: "e1" }, "e1"),
  ];
  const { onYou, onAgent } = selectQueues({ ...served, threads, workflows });
  assert.deepEqual(kinds(onYou), [
    ["ask", "pick-ask"],
    ["recovery", "e7"],
    ["recovery", "e9"],
  ]);
  assert.deepEqual(onAgent.at(-2), {
    kind: "answer",
    id: "pending:a1",
    subject: { kind: "thread", id: "e1" },
    thread: "e1",
    answer: null,
    stage: "sending",
  });
});

test("a follow-up sent in a thread the agent owes takes the place of its answer", () => {
  // The server owes a thread one answer, to its latest move, so the reply in flight
  // stands for the thread's answer rather than counting a second one.
  const served = reading();
  const workflows = [
    ...served.workflows,
    sending("a3", { kind: "thread", id: "e3" }, "e3"),
  ];
  const { onAgent } = selectQueues({ ...served, workflows });
  assert.deepEqual(kinds(onAgent), [
    ["answer", "pending:a3"],
    ["task", "e6"],
  ]);
});

test("a pick the user is sending owes nothing yet and leaves its Ask open", () => {
  const served = reading();
  const workflows = [
    ...served.workflows,
    sending("a2", { kind: "widget", id: "pick" }, null),
  ];
  const queues = selectQueues({ ...served, workflows });
  assert.deepEqual(queues, selectQueues(served));
});

test("a thread holding an open Ask is on the user once, as that Ask", () => {
  const served = reading();
  const asks = [...served.asks, { ...served.asks[0], id: "seated", thread: "e1" }];
  assert.deepEqual(kinds(selectQueues({ ...served, asks }).onYou), [
    ["ask", "pick-ask"],
    ["ask", "seated"],
    ["recovery", "e7"],
    ["recovery", "e9"],
  ]);
});

test("what is done is each answered Ask and each task the agent ended", () => {
  const served = servedReading("done");
  assert.deepEqual(selectDone(served), [
    {
      kind: "ask",
      id: "ship-ask",
      subject: { kind: "widget", id: "ship-ask" },
      thread: null,
    },
    {
      kind: "task",
      id: "e4",
      subject: { kind: "thread", id: "e2" },
      thread: "e2",
      title: "Check the colours",
      state: "done",
      ended: "2026-09-19T12:00:00+00:00",
      detail: "Matched the theme",
    },
  ]);
});
