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
    message: id,
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
  registry: {},
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

test("thread attention gives a standing user Question precedence over agent work", () => {
  const work = workflow("a", "working");
  const recovery = workflow("recovery", "sent", {
    condition: { kind: "failed" },
    next_actor: "user",
  });
  const thread = {
    resolved: null,
    workflows: [recovery, work],
    attention: { kind: "needs_user", reason: "question", workflow: "recovery" },
  };
  assert.deepEqual(threadAttention(thread), {
    kind: "needs_user",
    label: "On you to answer",
    workflow: recovery,
    secondary: "Working",
  });
});

test("a thread an open task holds waits on the agent under the task's title", () => {
  // The server's reading once the reply settled the comment and the task stood.
  const thread = {
    resolved: null,
    workflows: [],
    attention: {
      kind: "waiting",
      reason: "task",
      workflow: null,
      task: { id: "t1", title: "Rebuild the banner quieter" },
    },
  };
  assert.deepEqual(threadAttention(thread), {
    kind: "waiting",
    label: "Task open",
    workflow: null,
    secondary: "Rebuild the banner quieter",
  });
  assert.ok(awaitsAgent(thread));
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
  const [thread] = foldThreads([], [root]);
  const [record] = readThreadRecords(
    [{ ...thread, unread: [] }],
    { revision: 1, registry: {}, descriptors: new Map(), messageBodies: new Map() },
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
  const [folded] = foldThreads([thread], [reply]);

  const [record] = readThreadRecords(
    [folded],
    { revision: 1, registry: {}, descriptors: new Map(), messageBodies: new Map() },
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

test("a local rewrite shows on its message and hands a closed thread to the agent", () => {
  const asked = {
    id: "root",
    kind: "comment",
    author: "user",
    text: "Chart 2024.",
    ts: "then",
  };
  const answer = {
    id: "answer",
    kind: "reply",
    parent: "root",
    author: "agent",
    agent: "Indexer",
    text: "Charted.",
    ts: "then",
  };
  const thread = servedThread([asked, answer], {
    resolved: { id: "closed", kind: "resolve", author: "user" },
  });
  const rewrite = {
    id: "pending:rewrite",
    kind: "edit",
    author: "user",
    message: "root",
    text: "Chart 2025.",
    ts: "now",
  };
  const [folded] = foldThreads([thread], [rewrite]);

  const [record] = readThreadRecords(
    [folded],
    { revision: 1, registry: {}, descriptors: new Map(), messageBodies: new Map() },
    new Map(),
    [workflow("pending:rewrite", "sending", { message: "root" })],
  );
  assert.deepEqual(
    record.msgs.map((message) => [message.body.text, Boolean(message.edited)]),
    [
      ["Chart 2025.", true],
      ["Charted.", false],
    ],
  );
  assert.equal(record.root.body.text, "Chart 2025.");
  assert.deepEqual(
    record.msgs.map((message) => message.workflows.map(({ id }) => id)),
    [["pending:rewrite"], []],
  );
  assert.equal(record.resolved, null);
  assert.equal(awaitsAgent(record), true);
  assert.equal(thread.msgs[0].text, "Chart 2024.", "the served thread stays as served");
});

test("a pending gesture leaves its thread as the server read that gesture leaving it", () => {
  const asked = { id: "root", kind: "comment", author: "user", text: "A", ts: "then" };
  const question = {
    id: "question",
    kind: "reply",
    parent: "root",
    author: "agent",
    agent: "Indexer",
    text: "Which year?",
    ts: "then",
  };
  const owed = { kind: "needs_user", reason: "question", workflow: null };
  const rewrite = {
    id: "pending:rewrite",
    kind: "edit",
    author: "user",
    message: "root",
    text: "B",
    ts: "now",
  };
  const reply = { ...rewrite, id: "pending:reply", kind: "reply", parent: "question" };
  const resolve = {
    id: "pending:resolve",
    kind: "resolve",
    author: "user",
    parent: "root",
  };
  const unresolve = { ...resolve, id: "pending:unresolve", kind: "unresolve" };
  const waiting = {
    attention: { kind: "waiting", reason: "workflow", workflow: null },
    owed: [],
  };
  const closed = { attention: null, owed: [] };
  const fold = (changes, ...gestures) => {
    const [thread] = foldThreads(
      [servedThread([asked, question], changes)],
      gestures,
      (token) => token === "keep",
    );
    return { attention: thread.attention, owed: thread.owed };
  };

  // A question left in prose: a reply answers it and hands the thread over, on the
  // reply's own send; new words for an older message answer nothing; a reply's reading
  // covers a rewrite beside it.
  const settled = {
    attention: { kind: "waiting", reason: "workflow", workflow: "root" },
    owed: [],
  };
  const prose = {
    attention: owed,
    user_prompt: { message: "question", version: "question" },
    after: {
      reply: waiting,
      edit: { attention: owed, owed: ["reply:question"] },
      resolve: closed,
      unresolve: null,
      react: settled,
    },
  };
  assert.deepEqual(fold(prose, reply), {
    attention: { kind: "waiting", reason: "workflow", workflow: "pending:reply" },
    owed: [],
  });
  assert.deepEqual(fold(prose, rewrite), prose.after.edit);
  assert.equal(fold(prose, reply, rewrite).attention.workflow, "pending:rewrite");
  // A reaction that settles the question answers it, as the server read it doing; one
  // that settles nothing leaves the thread as served.
  const keep = { ...reply, id: "pending:keep", text: undefined, token: "keep" };
  assert.deepEqual(fold(prose, keep), settled);
  assert.deepEqual(fold(prose, { ...keep, token: "clarify" }), {
    attention: owed,
    owed: undefined,
  });
  // Settlement goes the way the last gesture takes it: a resolve closes the thread, a
  // turn after it reopens it, and a reopen undoing a resolve still pending leaves the
  // thread as served.
  assert.deepEqual(fold(prose, reply, resolve), closed);
  assert.equal(fold(prose, resolve, reply).attention.workflow, "pending:reply");
  assert.deepEqual(fold(prose, resolve, unresolve), {
    attention: owed,
    owed: undefined,
  });
  // A resolved thread over an Ask: a reopening, by itself or by a turn, gives the Ask
  // back to the user, and a pick whose answer failed stays theirs to send again.
  const ask = { attention: owed, owed: ["widget:years"] };
  const resend = {
    attention: { kind: "needs_user", reason: "recovery", workflow: "pick" },
    owed: [],
  };
  const resolved = {
    attention: null,
    resolved: { id: "closed", kind: "resolve", author: "user" },
    after: { reply: resend, edit: resend, resolve: null, unresolve: ask, react: null },
  };
  assert.deepEqual(fold(resolved, unresolve), ask);
  assert.deepEqual(fold(resolved, reply), resend);
  assert.deepEqual(fold(resolved, rewrite), resend);
});

test("pending thread gestures fold in the order the user made them, as the log will", () => {
  const asked = { id: "root", kind: "comment", author: "user", text: "A", ts: "then" };
  const answer = {
    id: "answer",
    kind: "reply",
    parent: "root",
    author: "agent",
    agent: "Indexer",
    text: "Done.",
    ts: "then",
  };
  const rewrite = {
    id: "pending:rewrite",
    kind: "edit",
    author: "user",
    message: "root",
    text: "B",
    ts: "now",
  };
  const reply = {
    id: "pending:reply",
    kind: "reply",
    parent: "root",
    author: "user",
    text: "C",
    ts: "now",
  };
  const resolve = { kind: "resolve", parent: "root", author: "user" };
  const fold = (...gestures) =>
    foldThreads([servedThread([asked, answer])], gestures)[0];

  // The newest turn is the one the agent answers, whichever kind it is.
  assert.equal(fold(rewrite, reply).attention.workflow, "pending:reply");
  assert.equal(fold(reply, rewrite).attention.workflow, "pending:rewrite");
  // A resolve after a rewrite closes the thread the rewrite reopened.
  assert.deepEqual(fold(rewrite, resolve).resolved, { author: "user", pending: true });
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
  const [opened] = foldThreads([], [root]);
  assert.deepEqual(
    Object.keys(opened).sort(),
    Object.keys(servedThread([root])).sort(),
  );
});
