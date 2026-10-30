import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  isPageWidgetWorkflow,
  strongestWorkflow,
  threadAttention,
  workflowLabel,
  workflowVoice,
} from "../../browser/runtime/thread/workflow.js";
import { foldThreads, readThreadRecords } from "../../browser/runtime/thread/model.js";
import { isTurnEvent, turnMessage } from "../../browser/runtime/pending/model.js";
import { servedReading, servedThread, servedWorkflow } from "../served.mjs";

// The user's turns, which `events.exchange` and `events.turn_message` read off the log
// by the same cases (`tests/turn_cases.json`).
const TURN_CASES = JSON.parse(
  readFileSync(new URL("../turn_cases.json", import.meta.url), "utf8"),
);

for (const { id, events, turns } of TURN_CASES)
  test(`a gesture this tab sends hands over the turn the server reads: ${id}`, () => {
    assert.deepEqual(
      events.filter(isTurnEvent).map((event) => [event.id, turnMessage(event)]),
      turns,
    );
  });

// A workflow for an input in the thread `root` opened, which serves the record of the
// reply the agent owes it.
const workflow = (id, stage, changes = {}) =>
  servedWorkflow({
    id,
    seq: 1,
    input: id,
    message: id,
    subject: { kind: "thread", id: "root" },
    thread: "root",
    coordinate: ["thread", "root"],
    obligation: `update:${id}`,
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
  assert.equal(workflowLabel(older, "Claude"), "Replying");
  assert.equal(workflowLabel(newer, "Claude"), "Up next");
  assert.equal(
    workflowLabel(
      workflow("ended", "picked_up", { condition: { kind: "ended" } }),
      "Claude",
    ),
    "Stopped",
  );
  assert.equal(
    workflowLabel(
      workflow("stale", "working", { condition: { kind: "stale" } }),
      "Claude",
    ),
    "Gone quiet",
  );
  assert.equal(
    workflowLabel(
      workflow("failed-response", "answered", {
        condition: { kind: "failed", operation: "response" },
      }),
      "Claude",
    ),
    "Not answered",
  );
});

// Until the agent has an update it can say nothing of it, so Leaf says the update waits
// for the agent, sent or still sending, and again once it is late. Leaf says everything
// it observes of the update's way, in its own voice; the agent's voice relays only its
// own acts, starting the update and answering it.
test("Leaf says what it observes of an update, and the agent only what it did", () => {
  for (const stage of ["sending", "sent"])
    assert.equal(workflowLabel(workflow(stage, stage), "Claude"), "Queued for Claude");
  const late = workflow("late", "sent", {
    condition: { kind: "stale", operation: "delivery" },
  });
  assert.equal(workflowLabel(late, "Claude"), "Still queued for Claude");
  const voices = Object.fromEntries(
    ["sending", "sent", "queued", "picked_up", "working", "replying", "answered"].map(
      (stage) => [stage, workflowVoice(workflow(stage, stage))],
    ),
  );
  assert.deepEqual(voices, {
    sending: "leaf",
    sent: "leaf",
    queued: "leaf",
    picked_up: "leaf",
    working: "agent",
    replying: "leaf",
    answered: "agent",
  });
  assert.equal(workflowVoice(late), "leaf");
  const ended = workflow("ended", "working", { condition: { kind: "ended" } });
  assert.equal(workflowVoice(ended), "leaf");
});

test("thread attention gives an open user obligation precedence over agent work", () => {
  const work = workflow("a", "working");
  const recovery = workflow("recovery", "sent", {
    condition: { kind: "failed" },
  });
  const thread = {
    resolved: null,
    workflows: [recovery, work],
    // The record the agent's work serves, which it still owes.
    obligations: [{ id: "update:a", source: { kind: "update" }, next_actor: "agent" }],
    attention: { kind: "needs_user", reason: "obligation", workflow: "recovery" },
  };
  assert.deepEqual(threadAttention(thread, "Claude"), {
    kind: "needs_user",
    label: "Your turn",
    voice: "agent",
    workflow: recovery,
  });
});

test("a thread an open to-do holds waits on the agent under the to-do's title", () => {
  // The server's reading once the reply settled the comment and the to-do stood.
  const thread = {
    resolved: null,
    workflows: [],
    attention: { kind: "waiting", reason: "todo", workflow: null },
    todos: [{ id: "t1", title: "Rebuild the banner quieter", running: null }],
  };
  assert.deepEqual(threadAttention(thread, "Claude"), {
    kind: "waiting",
    label: "Still to do",
    voice: "agent",
    workflow: null,
  });
});

test("a frozen move that owes nothing leaves an owed thread on the user alone", () => {
  // The server's reading: the agent asked over a board it sent, and the user moved a
  // card without answering. The move stands in the thread but does not hold it.
  const { threads, workflows } = servedReading("frozen move owes nothing");
  const [record] = readThreadRecords(threads, FROZEN_BOARD, new Map(), workflows);
  assert.deepEqual(threadAttention(record, "Claude"), {
    kind: "needs_user",
    label: "Your turn",
    voice: "agent",
    workflow: null,
  });
});

test("a send this tab has not delivered ranks below the served workflows of its next actor", () => {
  // Served strongest first; the server's order is taken as given.
  const recovery = workflow("recovery", "answered", {
    condition: { kind: "failed", operation: "response" },
  });
  const older = workflow("older", "sent", { seq: 1 });
  const newer = workflow("newer", "sent", { seq: 2 });
  const pending = workflow("pending:reply", "sending", { seq: 3 });
  const refused = workflow("rejected:retry", "sending", {
    seq: 4,
    condition: { kind: "failed", operation: "delivery" },
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

test("a pending reply shows on its message and leaves whose turn it is to the log", () => {
  const thread = servedThread(
    [{ id: "root", kind: "comment", author: "agent", text: "Which one?", ts: "now" }],
    { attention: { kind: "needs_user", reason: "resend", workflow: "failed" } },
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
      }),
      workflow("pending:retry", "sending"),
    ],
  );
  assert.deepEqual(
    record.msgs.map((message) => [message.id, message.workflows.map(({ id }) => id)]),
    [
      ["root", []],
      ["pending:retry", ["pending:retry"]],
    ],
  );
  assert.deepEqual(record.attention, thread.attention);
});

test("a local rewrite shows on its message and reopens a closed thread", () => {
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
  assert.equal(thread.msgs[0].text, "Chart 2024.", "the served thread stays as served");
});

test("pending thread gestures fold in the order the user made them, as the log will", () => {
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
  const rewrite = {
    id: "pending:rewrite",
    kind: "edit",
    author: "user",
    message: "root",
    text: "B",
    ts: "now",
  };
  const reply = { ...rewrite, id: "pending:reply", kind: "reply", parent: "question" };
  const keep = { ...reply, id: "pending:keep", text: undefined, token: "keep" };
  const undo = { id: "pending:undo", kind: "undo", author: "user", undoes: "kept" };
  const resolve = { kind: "resolve", parent: "root", author: "user" };
  const unresolve = { ...resolve, kind: "unresolve" };
  const owed = { kind: "needs_user", reason: "obligation", workflow: null };
  const fold = (changes, ...gestures) =>
    foldThreads([servedThread([asked, question], changes)], gestures)[0];

  // Whose turn the thread is stays as the server read it, whatever the user sends,
  // until the log answers.
  for (const gesture of [reply, rewrite, keep, undo, resolve, unresolve])
    assert.deepEqual(fold({ attention: owed }, gesture).attention, owed, gesture.id);
  // A resolve after a turn closes the thread the turn reopened, and a turn after a
  // resolve reopens it; a reaction is no turn, so it leaves a resolve in force.
  const closed = { author: "user", pending: true };
  const resolved = { resolved: { id: "closed", kind: "resolve", author: "user" } };
  assert.deepEqual(fold({}, rewrite, resolve).resolved, closed);
  assert.equal(fold(resolved, resolve, reply).resolved, null);
  assert.deepEqual(fold({}, resolve, keep).resolved, closed);
  assert.equal(fold(resolved, unresolve).resolved, null);
  // Taking back the resolve that closed the thread reopens it; taking back anything
  // else leaves it closed.
  assert.equal(fold(resolved, { ...undo, undoes: "closed" }).resolved, null);
  assert.deepEqual(fold(resolved, undo).resolved, resolved.resolved);
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
    id: "pending:question",
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
