import assert from "node:assert/strict";
import test from "node:test";
import { selectQueues } from "../../skills/leaf/assets/runtime/queues.js";
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

test("a reply the user is sending takes its thread off their queue at once", () => {
  const served = reading();
  // The publisher folds the pending reply into its thread, which then waits on the
  // agent; the reply's own workflow is still the tab's, owing nothing it can name.
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
  const { onYou } = selectQueues({ ...served, threads });
  assert.deepEqual(kinds(onYou), [
    ["ask", "pick-ask"],
    ["recovery", "e7"],
  ]);
});

test("a thread holding an open Ask is on the user once, as that Ask", () => {
  const served = reading();
  const asks = [...served.asks, { ...served.asks[0], id: "seated", thread: "e1" }];
  assert.deepEqual(kinds(selectQueues({ ...served, asks }).onYou), [
    ["ask", "pick-ask"],
    ["ask", "seated"],
    ["recovery", "e7"],
  ]);
});

test("a page move handed back to the user is on their queue by its widget", () => {
  const served = reading();
  const refused = servedWorkflow({
    id: "rejected:a2",
    subject: { kind: "widget", id: "pick" },
    thread: null,
    holds_thread: false,
    answer: null,
    condition: { kind: "failed", operation: "delivery" },
    next_actor: "user",
  });
  const { onYou } = selectQueues({
    ...served,
    workflows: [...served.workflows, refused],
  });
  assert.deepEqual(onYou.at(-1), {
    kind: "recovery",
    id: "rejected:a2",
    subject: { kind: "widget", id: "pick" },
    thread: null,
  });
});
