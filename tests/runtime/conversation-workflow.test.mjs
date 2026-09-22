import assert from "node:assert/strict";
import test from "node:test";
import {
  isPageWidgetWorkflow,
  projectThreadAttention,
  strongestWorkflow,
  threadAttention,
  workflowLabel,
} from "../../skills/leaf/assets/runtime/conversation/workflow.js";
import { readThreadRecords } from "../../skills/leaf/assets/runtime/conversation/model.js";

const workflow = (id, stage, extra = {}) => ({
  id,
  seq: 1,
  revision: 1,
  input: id,
  subject: { kind: "thread", id: "root" },
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

test("local workflows complete and override server attention without hiding an Ask", () => {
  const sending = workflow("pending:send", "sending");
  assert.deepEqual(projectThreadAttention(null, [sending]), {
    kind: "waiting",
    reason: "workflow",
    workflow: sending.id,
  });

  const failed = workflow("rejected:send", "sending", {
    condition: { kind: "failed", operation: "delivery" },
    next_actor: "reader",
  });
  assert.deepEqual(
    projectThreadAttention(
      { kind: "waiting", reason: "workflow", workflow: "server-work" },
      [workflow("server-work", "working"), failed],
    ),
    { kind: "needs_reader", reason: "workflow", workflow: failed.id },
  );
  assert.deepEqual(
    projectThreadAttention({ kind: "needs_reader", reason: "ask", workflow: "ask" }, [
      failed,
    ]),
    { kind: "needs_reader", reason: "ask", workflow: "ask" },
  );
  const recovery = {
    kind: "needs_reader",
    reason: "recovery",
    workflow: "accepted-recovery",
  };
  assert.equal(
    projectThreadAttention(recovery, [
      workflow("accepted-recovery", "answered", {
        condition: { kind: "failed", operation: "response" },
        next_actor: "reader",
      }),
    ]),
    recovery,
  );

  const accepted = workflow("accepted", "sent");
  assert.deepEqual(
    projectThreadAttention(
      { kind: "waiting", reason: "workflow", workflow: accepted.id },
      [accepted, sending],
    ),
    { kind: "waiting", reason: "workflow", workflow: accepted.id },
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

test("thread records project local sending attention", () => {
  const sending = workflow("pending:send", "sending");
  const thread = {
    root: { id: "root", author: "user", text: "Question", ts: "2026-09-22T10:00:00Z" },
    msgs: [
      { id: "root", author: "user", text: "Question", ts: "2026-09-22T10:00:00Z" },
    ],
    anchor: null,
    resolved: null,
    awaits_agent: true,
    awaits_reader: false,
    attention: null,
    bare_reaction: false,
    seat: null,
  };
  const [record] = readThreadRecords(
    [thread],
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
