import assert from "node:assert/strict";
import test from "node:test";
import {
  isPageWidgetWorkflow,
  strongestWorkflow,
  threadAttention,
  workflowLabel,
} from "../../skills/leaf/assets/runtime/thread/workflow.js";
import {
  awaitsAgent,
  awaitsUser,
  foldThreads,
  readThreadRecords,
} from "../../skills/leaf/assets/runtime/thread/model.js";
import { servedReading, servedThread, servedWorkflow } from "../served.mjs";

// A workflow for an input in the thread `root` opened, which the agent owes a reply
// and which holds the thread.
const workflow = (id, stage, changes = {}) =>
  servedWorkflow({
    id,
    seq: 1,
    input: id,
    subject: { kind: "thread", id: "root" },
    thread: "root",
    coordinate: ["thread", "root"],
    answer: { kind: "reply", to: id, for: id },
    stage,
    ...changes,
  });

// The document a thread's frozen board is captured into: the reply `e2` in thread
// `e1` holds the board `feeder-board`.
const FROZEN_BOARD = {
  revision: 1,
  descriptors: new Map([
    [
      "feeder-board",
      {
        id: "feeder-board",
        tag: "lf-board",
        document: { kind: "thread", thread: "e1", message: "e2" },
      },
    ],
  ]),
  messageBodies: new Map([
    ["e2", { text: "Here is the board.", document: { thread: "e1", message: "e2" } }],
  ]),
};

test("workflow labels retain exact input progress and positive conditions", () => {
  const older = workflow("a", "replying");
  const newer = workflow("b", "queued");
  assert.equal(workflowLabel(older), "Replying");
  assert.equal(workflowLabel(newer), "Queued");
  assert.equal(
    workflowLabel(workflow("ended", "picked_up", { condition: { kind: "ended" } })),
    "Turn ended",
  );
  assert.equal(
    workflowLabel(workflow("stale", "working", { condition: { kind: "stale" } })),
    "Update stale",
  );
  assert.equal(
    workflowLabel(
      workflow("failed-response", "answered", {
        condition: { kind: "failed", operation: "response" },
      }),
    ),
    "Not answered",
  );
});

test("thread attention gives a standing user Ask precedence over agent work", () => {
  const work = workflow("a", "working");
  const recovery = workflow("recovery", "sent", {
    condition: { kind: "failed" },
    next_actor: "user",
  });
  const thread = {
    resolved: null,
    workflows: [recovery, work],
    attention: { kind: "needs_user", reason: "ask", workflow: "recovery" },
  };
  assert.deepEqual(threadAttention(thread), {
    kind: "needs_user",
    label: "On you to answer",
    workflow: recovery,
    secondary: "Working",
  });
});

test("a frozen move that owes nothing leaves an owed thread on the user alone", () => {
  // The server's reading: the agent asked over a board it sent, and the user moved a
  // card without answering. The move stands in the thread but does not hold it.
  const { threads, workflows } = servedReading("frozen move owes nothing");
  const [record] = readThreadRecords(threads, FROZEN_BOARD, new Map(), workflows);
  assert.deepEqual(threadAttention(record), {
    kind: "needs_user",
    label: "On you to answer",
    workflow: null,
    secondary: "",
  });
});

test("a send this tab has not delivered ranks below the served workflows of its next actor", () => {
  // Served strongest first; the server's order is taken as given.
  const recovery = workflow("recovery", "answered", {
    condition: { kind: "failed", operation: "response" },
    next_actor: "user",
  });
  const older = workflow("older", "sent", { seq: 1 });
  const newer = workflow("newer", "sent", { seq: 2 });
  const pending = workflow("pending:reply", "sending", { seq: 3 });
  const refused = workflow("rejected:retry", "sending", {
    seq: 4,
    condition: { kind: "failed", operation: "delivery" },
    next_actor: "user",
  });
  assert.equal(strongestWorkflow([recovery, older, pending, refused]), recovery);
  assert.equal(strongestWorkflow([newer, older, pending, refused]), refused);
  assert.equal(strongestWorkflow([newer, older, pending]), newer);
  assert.equal(strongestWorkflow([older, newer, pending]), older);
  assert.equal(strongestWorkflow([pending]), pending);
  assert.equal(strongestWorkflow([]), null);
});

test("page widget workflows are revision-bounded independently of frozen widgets", () => {
  const widget = workflow("widget", "working", {
    revision: 2,
    subject: { kind: "widget", id: "choice" },
    thread: null,
    coordinate: ["choice", "choice", "selection"],
  });
  assert.equal(isPageWidgetWorkflow(widget, 1), false);
  assert.equal(isPageWidgetWorkflow(widget, 2), true);
  const frozen = { ...widget, subject: { kind: "widget", id: "frozen" } };
  assert.equal(isPageWidgetWorkflow({ ...frozen, thread: "root" }, 2), false);
});

test("a thread the user is still sending waits on that send", () => {
  const sending = workflow("pending:send", "sending", {
    subject: { kind: "thread", id: "pending:send" },
    thread: "pending:send",
  });
  const root = {
    id: "pending:send",
    kind: "comment",
    author: "user",
    text: "Question",
    ts: "2026-09-22T10:00:00Z",
  };
  const [thread] = foldThreads([], [root], [], []);
  const [record] = readThreadRecords(
    [{ ...thread, unread: [] }],
    { revision: 1, descriptors: new Map(), messageBodies: new Map() },
    new Map(),
    [sending],
  );
  assert.deepEqual(record.attention, {
    kind: "waiting",
    reason: "workflow",
    workflow: sending.id,
  });
});

test("a local prose answer clears accepted user attention until refusal", () => {
  const thread = servedThread(
    [{ id: "root", kind: "comment", author: "agent", text: "Which one?", ts: "now" }],
    { attention: { kind: "needs_user", reason: "recovery", workflow: "failed" } },
  );
  const reply = {
    id: "pending:retry",
    kind: "reply",
    parent: "root",
    author: "user",
    text: "Try again",
    ts: "now",
    pending: true,
  };
  const [folded] = foldThreads([thread], [reply], [], []);

  const [record] = readThreadRecords(
    [folded],
    { revision: 1, descriptors: new Map(), messageBodies: new Map() },
    new Map(),
    [
      workflow("failed", "answered", {
        condition: { kind: "failed", operation: "response" },
        next_actor: "user",
      }),
      workflow("pending:retry", "sending"),
    ],
  );
  assert.deepEqual(record.attention, {
    kind: "waiting",
    reason: "workflow",
    workflow: "pending:retry",
  });
  assert.equal(awaitsUser(record), false);
  assert.equal(awaitsAgent(record), true);
  assert.equal(awaitsUser({ ...record, attention: thread.attention }), true);
  assert.equal(awaitsAgent({ ...record, attention: thread.attention }), false);
});

test("a frozen message widget keeps its exact workflow in the message and thread", () => {
  // The server's reading of a card the user moved on a board the agent sent.
  const { threads, workflows } = servedReading("frozen move owes nothing");
  const [record] = readThreadRecords(threads, FROZEN_BOARD, new Map(), workflows);
  assert.deepEqual(
    record.msgs.map((message) => message.workflows.map(({ id }) => id)),
    [[], ["e3"]],
  );
  assert.deepEqual(
    record.workflows.map(({ id }) => id),
    ["e3"],
  );
});

test("a thread this tab opened carries every field a served thread does", () => {
  const root = {
    id: "pending:ask",
    kind: "comment",
    author: "user",
    text: "Question",
    ts: "2026-09-22T10:00:00Z",
  };
  const [opened] = foldThreads([], [root], [], []);
  assert.deepEqual(
    Object.keys(opened).sort(),
    Object.keys(servedThread([root])).sort(),
  );
});
