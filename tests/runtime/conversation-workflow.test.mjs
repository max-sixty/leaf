import assert from "node:assert/strict";
import test from "node:test";
import {
  isPageWidgetWorkflow,
  strongestWorkflow,
  threadAttention,
  workflowLabel,
} from "../../skills/leaf/assets/runtime/conversation/workflow.js";
import {
  awaitsReader,
  foldThreads,
  readThreadRecords,
} from "../../skills/leaf/assets/runtime/conversation/model.js";

const workflow = (id, stage, extra = {}) => ({
  id,
  seq: 1,
  revision: 1,
  input: id,
  subject: { kind: "conversation", id: "root" },
  stage,
  activity: [],
  condition: null,
  next_actor: "agent",
  ...extra,
});

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

test("thread attention gives a standing reader Ask precedence over agent work", () => {
  const work = workflow("a", "working");
  const recovery = workflow("recovery", "sent", {
    condition: { kind: "failed" },
    next_actor: "reader",
  });
  const thread = {
    resolved: null,
    workflows: [recovery, work],
    attention: { kind: "needs_reader", reason: "ask", workflow: "recovery" },
  };
  assert.deepEqual(threadAttention(thread), {
    kind: "needs_reader",
    label: "On you",
    workflow: recovery,
    secondary: "Working",
  });
  assert.equal(
    strongestWorkflow([
      workflow("older", "picked_up", { condition: { kind: "stale" } }),
      work,
    ]),
    work,
  );
  assert.equal(strongestWorkflow([work, recovery]), recovery);
  assert.equal(
    strongestWorkflow([
      workflow("older", "working", { seq: 1 }),
      workflow("newer", "working", { seq: 2 }),
    ]).id,
    "newer",
  );
  assert.equal(
    strongestWorkflow([
      workflow("fresh", "working", { seq: 1 }),
      workflow("stale", "working", {
        seq: 2,
        condition: { kind: "stale", operation: "work" },
      }),
    ]).id,
    "fresh",
  );
});

test("page widget workflows are revision-bounded independently of frozen widgets", () => {
  const widget = workflow("widget", "working", {
    revision: 2,
    subject: { kind: "widget", id: "frozen-choice" },
    coordinate: '["frozen-choice","choice","selection"]',
  });
  assert.equal(isPageWidgetWorkflow(widget, 1), false);
  assert.equal(isPageWidgetWorkflow(widget, 2), true);
});

test("a thread the reader is still sending waits on that send", () => {
  const sending = workflow("pending:send", "sending");
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

test("a local prose answer clears accepted reader attention until refusal", () => {
  const thread = {
    root: { id: "root", author: "agent", text: "Which one?", ts: "now" },
    msgs: [{ id: "root", author: "agent", text: "Which one?", ts: "now" }],
    anchor: null,
    resolved: null,
    awaits_agent: false,
    awaits_reader: false,
    attention: { kind: "needs_reader", reason: "recovery", workflow: "failed" },
    bare_reaction: false,
    unread: [],
    seat: null,
  };
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
        next_actor: "reader",
      }),
      workflow("pending:retry", "sending"),
    ],
  );
  assert.deepEqual(record.attention, {
    kind: "waiting",
    reason: "workflow",
    workflow: "pending:retry",
  });
  assert.equal(awaitsReader(record), false);
  assert.equal(awaitsReader({ ...record, attention: thread.attention }), true);
});

test("a frozen message widget keeps its exact workflow in the message and thread", () => {
  const widgetWork = workflow("action-1", "working", {
    revision: 2,
    input: "action-1",
    subject: { kind: "widget", id: "frozen-choice" },
  });
  const thread = {
    root: { id: "root", author: "user", text: "Question", ts: "2026-09-22T10:00:00Z" },
    msgs: [
      { id: "root", author: "user", text: "Question", ts: "2026-09-22T10:00:00Z" },
      {
        id: "agent-reply",
        parent: "root",
        author: "agent",
        markup: "<lf-choice id='frozen-choice'></lf-choice>",
        ts: "2026-09-22T10:01:00Z",
      },
    ],
    anchor: null,
    resolved: null,
    awaits_agent: false,
    awaits_reader: false,
    bare_reaction: false,
    unread: [],
    seat: null,
  };
  const document = {
    revision: 1,
    descriptors: new Map([
      [
        "frozen-choice",
        {
          id: "frozen-choice",
          tag: "lf-choice",
          document: { kind: "thread", thread: "root", message: "agent-reply" },
        },
      ],
    ]),
    messageBodies: new Map([
      [
        "agent-reply",
        { text: "Choose", document: { thread: "root", message: "agent-reply" } },
      ],
    ]),
  };
  const [record] = readThreadRecords([thread], document, new Map(), [widgetWork]);
  assert.deepEqual(record.msgs[1].workflows, [widgetWork]);
  assert.deepEqual(record.workflows, [widgetWork]);
});
