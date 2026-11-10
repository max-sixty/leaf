import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  isPageWidgetWorkflow,
  progressFace,
  strongestWorkflow,
  threadAttention,
  workflowWord,
} from "../../browser/runtime/thread/workflow.js";
import {
  deleted,
  foldThreads,
  readThreadRecords,
} from "../../browser/runtime/thread/model.js";
import { isTurnEvent, turnMessage } from "../../browser/runtime/pending/model.js";
import { threadReading } from "../../browser/runtime/thread/thread-card.js";
import { servedReading, servedThread, servedWorkflow } from "../served.mjs";

// No thread has a to-do attached.

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

const said = (workflowAt) => {
  const word = workflowWord(workflowAt, "Claude");
  return word && [word.text, word.voice];
};

test("workflow words retain exact input progress and positive conditions", () => {
  assert.deepEqual(said(workflow("a", "replying")), ["Replying", "agent"]);
  assert.deepEqual(said(workflow("b", "queued")), ["Up next", "leaf"]);
  assert.deepEqual(
    said(workflow("ended", "picked_up", { condition: { kind: "ended" } })),
    ["Stopped", "leaf"],
  );
  assert.deepEqual(
    said(workflow("stale", "working", { condition: { kind: "stale" } })),
    ["Gone quiet", "leaf"],
  );
  assert.deepEqual(
    said(
      workflow("failed-response", "answered", {
        condition: { kind: "failed", operation: "response" },
      }),
    ),
    ["Not answered", "leaf"],
  );
});

// Until the agent has an update it can say nothing of it, so Leaf says the update waits
// for the agent, sent or still sending, and again once it is late. Leaf says everything
// it observes of the update's way, in its own voice; the agent's voice relays what it
// reliably did: starting the update, streaming its reply and answering it.
test("Leaf says what it observes of an update, and the agent only what it did", () => {
  const late = workflow("late", "sent", {
    condition: { kind: "stale", operation: "delivery" },
  });
  const words = Object.fromEntries(
    ["sending", "sent", "queued", "picked_up", "working", "replying"].map((stage) => [
      stage,
      said(workflow(stage, stage)),
    ]),
  );
  assert.deepEqual(words, {
    sending: ["Queued for Claude", "leaf"],
    sent: ["Queued for Claude", "leaf"],
    queued: ["Up next", "leaf"],
    picked_up: ["Delivered", "leaf"],
    working: ["On it", "agent"],
    replying: ["Replying", "agent"],
  });
  // An answer says nothing on its message, which already shows it, but names its word
  // where it is asked for, as a title does.
  assert.equal(said(workflow("answered", "answered")), null);
  assert.deepEqual(
    workflowWord(workflow("answered", "answered"), "Claude", { answered: true }),
    { text: "Answered", voice: "agent" },
  );
  assert.deepEqual(said(late), ["Still queued for Claude", "leaf"]);
});

// On leaf.page a send to a page whose agent isn't running waits while its container
// starts, and says so until the server has the update.
test("a send that launches the agent says so until the server has it", () => {
  assert.deepEqual(said({ ...workflow("first", "sending"), launching: true }), [
    "Launching agent container",
    "leaf",
  ]);
  assert.deepEqual(said({ ...workflow("next", "sending"), launching: false }), [
    "Queued for Claude",
    "leaf",
  ]);
});

// A fork of the agent's conversation taking an update on is the agent's act, so the
// update reads On it on its way to the session, with the working face; the session's
// own stages and every condition still say what they say.
test("an update a fork has taken on reads On it until the session's own stage", () => {
  const forked = (stage, changes = {}) =>
    workflow(stage, stage, { at_work: true, ...changes });
  for (const stage of ["sent", "queued", "picked_up"]) {
    assert.deepEqual(said(forked(stage)), ["On it", "agent"], stage);
    assert.equal(progressFace(forked(stage)), "working", stage);
  }
  assert.deepEqual(said(forked("replying")), ["Replying", "agent"]);
  assert.deepEqual(
    said(forked("sent", { condition: { kind: "stale", operation: "delivery" } })),
    ["Still queued for Claude", "leaf"],
  );
  assert.equal(
    progressFace(
      forked("sent", { condition: { kind: "stale", operation: "delivery" } }),
    ),
    null,
  );
});

// The fork's line is the agent's step under that word, live as the session's own
// working line is.
test("a fork's working line is the thread's live step while its update reads On it", () => {
  const root = {
    id: "root",
    kind: "comment",
    author: "user",
    text: "Fix the build",
    ts: "2026-11-05T10:00:00Z",
  };
  const line = {
    id: "line",
    kind: "reply",
    parent: "root",
    author: "agent",
    text: "Looking at the build",
    ts: "2026-11-05T10:00:03Z",
    ephemeral: true,
  };
  const [record] = readThreadRecords(
    [
      servedThread([root, line], {
        attention: { kind: "waiting", reason: "workflow", workflow: "root" },
      }),
    ],
    FROZEN_BOARD,
    new Map(),
    [workflow("root", "sent", { at_work: true })],
  );
  const { working } = threadReading(record, "margin", {});
  assert.equal(working?.words, "Looking at the build");
  assert.equal(working?.live, true);
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
    word: { text: "Your turn", voice: "agent" },
    workflow: recovery,
  });
});

test("a thread an open to-do holds waits on the agent under the to-do's title", () => {
  // The server's reading once the reply settled the comment and the to-do stood.
  const thread = {
    resolved: null,
    workflows: [],
    attention: { kind: "waiting", reason: "todo", workflow: null, todo: "t1" },
    todos: [{ id: "t1", title: "Rebuild the banner quieter", running: null }],
  };
  assert.deepEqual(threadAttention(thread, "Claude"), {
    kind: "waiting",
    word: { text: "Still to do", voice: "agent" },
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
    word: { text: "Your turn", voice: "agent" },
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
    [{ ...thread, unread: {} }],
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

test("taking back a rewrite draws its message as the log's answer will", () => {
  const [rewritten] = servedReading("rewritten twice").threads;
  const [answered] = servedReading("rewritten twice, the last taken back").threads;
  /** @param {{text?: string, edited?: object, content_version: string}} message */
  const words = ({ text, edited, content_version }) => ({
    text,
    edited,
    content_version,
  });
  const [folded] = foldThreads([rewritten], [{ kind: "undo", undoes: "e3" }]);
  assert.equal(folded.root.text, "Chart 2025.");
  assert.deepEqual(folded.msgs.map(words), answered.msgs.map(words));
  assert.deepEqual(words(folded.root), words(answered.root));
});

test("taking back an answered reaction keeps its place as the log's answer will", () => {
  const [answered] = servedReading("a reaction answered").threads;
  const [taken] = servedReading(
    "a reaction answered, both reactions taken back",
  ).threads;
  /** @param {import("../../browser/types/domain.js").Message} message */
  const place = (message) => ({
    id: message.id,
    text: message.text,
    token: message.token,
    was: message.withdrawn?.was,
    deleted: deleted(message),
  });
  const [folded] = foldThreads(
    [answered],
    [
      { kind: "undo", undoes: "e3" },
      { kind: "undo", undoes: "e1" },
    ],
  );
  assert.deepEqual(folded.msgs.map(place), [
    { id: "e1", text: "", token: undefined, was: "change", deleted: true },
    { id: "e2", text: "Which part?", token: undefined, was: undefined, deleted: false },
  ]);
  assert.deepEqual(folded.msgs.map(place), taken.msgs.map(place));
  assert.deepEqual(place(folded.root), place(taken.root));
  assert.equal(folded.bare_reaction, taken.bare_reaction);
});

test("the press leaves a sent message's place Deleted, as the log's answer does where answered", () => {
  const [answered] = servedReading("a reply answered").threads;
  const [taken] = servedReading("a reply answered, taken back").threads;
  /** @param {import("../../browser/types/domain.js").Message} message */
  const place = (message) => ({
    id: message.id,
    text: message.text,
    was: message.withdrawn?.was,
    deleted: deleted(message),
  });
  const [folded] = foldThreads([answered], [{ kind: "undo", undoes: "e3" }]);
  assert.deepEqual(folded.msgs.map(place)[2], {
    id: "e3",
    text: "",
    was: "The rollout section.",
    deleted: true,
  });
  assert.deepEqual(folded.msgs.map(place), taken.msgs.map(place));
  // Whether anything stands on a message is the log's to say, so the press leaves the
  // place of one nothing answers, or one a reply still streams to, and of a comment
  // alone in its thread, which the server's reading then takes away.
  const loose = { ...answered.msgs[2], id: "loose", parent: "e4", text: "And this?" };
  const stream = {
    ...answered.msgs[3],
    id: "stream:t1",
    parent: "loose",
    provisional: true,
  };
  const alone = { ...answered, msgs: [answered.root] };
  for (const [thread, undoes] of [
    [{ ...answered, msgs: [...answered.msgs, loose] }, "loose"],
    [{ ...answered, msgs: [...answered.msgs, loose, stream] }, "loose"],
    [alone, "e1"],
  ]) {
    const [pressed] = foldThreads([thread], [{ kind: "undo", undoes }]);
    const left = pressed.msgs.find(({ id }) => id === undoes);
    assert.deepEqual(
      [pressed.msgs.length, left && place(left).deleted],
      [thread.msgs.length, true],
    );
  }
});

test("a mark alone on the page comes off in the press, and a place the log kept stays", () => {
  const [holding] = servedReading("a reaction holding a to-do").threads;
  const [held] = servedReading("a reaction holding a to-do taken back").threads;
  assert.equal(held.root.withdrawn?.was, "change");
  // The press takes the mark off; the log's answer brings back the place a to-do keeps.
  assert.deepEqual(foldThreads([holding], [{ kind: "undo", undoes: "e1" }]), []);
  // The log's place stays through the next gesture, whatever else stood on it.
  assert.deepEqual(foldThreads([held], [{ kind: "undo", undoes: "elsewhere" }]), [
    held,
  ]);
  // A chip taken back comes off, and leaves the place it stood on.
  const { withdrawn: _, ...said } = held.root;
  const marked = {
    ...held,
    msgs: [...held.msgs, { ...said, id: "mark", parent: "e1", token: "keep" }],
  };
  assert.deepEqual(
    foldThreads([marked], [{ kind: "undo", undoes: "mark" }]).map(({ msgs }) =>
      msgs.map(({ id }) => id),
    ),
    [["e1"]],
  );
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
