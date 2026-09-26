import assert from "node:assert/strict";
import { mock } from "node:test";
import test from "node:test";
import process from "node:process";

// Recent's day names are formatted in the zone the page loads in, so the zone — one with
// a daylight-saving change — is fixed before the modules load rather than by a static
// import that would load them first.
process.env.TZ = "America/New_York";
const { moved, readThreadRecords, threadSummary } =
  await import("/runtime/thread/model.js");
const { inRecentOrder, recentGroup } = await import("/runtime/thread/placement.js");
const { unreadBoundaries } = await import("/runtime/thread/summary-ranges.js");
const { threadAttention } = await import("/runtime/thread/workflow.js");
const { DEFAULT_INTENT, narrowingReading, transition } =
  await import("/runtime/thread/narrowing.js");

const NO_DOCUMENT = { descriptors: new Map(), messageBodies: new Map() };

const agent = (id, extra = {}) => ({
  id,
  kind: "reply",
  author: "agent",
  text: id,
  seq: 1,
  ts: "2026-03-01T12:00:00Z",
  ...extra,
});
const serverThread = (msgs, extra = {}) => ({
  root: msgs[0],
  msgs,
  anchor: null,
  resolved: null,
  bare_reaction: false,
  seat: null,
  summaries: [],
  attention: null,
  unread: [],
  ...extra,
});

test("a thread's unread is the server reading less what this tab is acknowledging", () => {
  const root = agent("root", { kind: "comment" });
  const reply = agent("reply", { seq: 2, edited: { id: "edit", seq: 4, ts: "x" } });
  const threads = [
    serverThread([root, reply], {
      unread: [
        { message: "root", version: "root" },
        { message: "reply", version: "edit" },
      ],
    }),
  ];
  const read = (acknowledging) =>
    readThreadRecords(threads, NO_DOCUMENT, new Map(), [], acknowledging)[0];

  const standing = read([]);
  assert.deepEqual(
    standing.msgs.map((message) => message.unread),
    [true, true],
  );
  assert.equal(standing.unread.length, 2);

  // Acknowledging the reply's earlier version leaves its current one unread.
  const stale = read([{ message: "reply", version: "reply" }]);
  assert.deepEqual(
    stale.msgs.map((message) => message.unread),
    [true, true],
  );

  const current = read([{ message: "reply", version: "edit" }]);
  assert.deepEqual(
    current.msgs.map((message) => message.unread),
    [true, false],
  );
  assert.deepEqual(current.unread, [{ message: "root", version: "root" }]);
});

test("a message moves when it is edited, and a thread when any turn moves", () => {
  const plain = agent("plain", { seq: 3, ts: "2026-03-01T09:00:00Z" });
  const edited = agent("edited", {
    seq: 1,
    ts: "2026-02-20T09:00:00Z",
    edited: { id: "e", seq: 7, ts: "2026-03-02T09:00:00Z" },
  });
  assert.deepEqual(moved(plain), { seq: 3, ts: "2026-03-01T09:00:00Z" });
  assert.deepEqual(moved(edited), { seq: 7, ts: "2026-03-02T09:00:00Z" });
  const thread = {
    root: { ...edited, body: { text: "Topic" } },
    msgs: [
      { ...edited, body: { text: "Topic" } },
      agent("later", { seq: 4, ts: "2026-02-25T09:00:00Z" }),
    ],
  };
  assert.equal(threadSummary(thread).latest, "2026-03-02T09:00:00Z");
});

test("attention names the outstanding question rather than the latest message", () => {
  const question = agent("question", {
    kind: "comment",
    text: "Does this crop show enough of the room?",
  });
  const update = agent("update", {
    text: "I also added the room number.",
    seq: 2,
  });
  const source = serverThread([question, update], {
    attention: { kind: "needs_user", reason: "ask", workflow: null },
    user_prompt: { message: "question", version: "question" },
  });
  const [thread] = readThreadRecords([source], NO_DOCUMENT, new Map(), []);
  const attention = threadAttention(thread);
  assert.equal(attention.label, "On you");
  assert.equal(attention.action, "answer question");
  assert.equal(threadAttention({ ...thread, user_prompt: null }).action, "answer Ask");
  assert.equal(
    threadAttention({
      ...thread,
      attention: { kind: "needs_user", reason: "recovery", workflow: "send" },
      workflows: [{ id: "send", subject: { kind: "thread" } }],
    }).action,
    "resend",
  );
  assert.equal(
    threadAttention({
      ...thread,
      attention: { kind: "needs_user", reason: "recovery", workflow: "move" },
      workflows: [{ id: "move", subject: { kind: "widget" } }],
    }).action,
    "retry",
  );
  assert.equal(
    threadAttention({
      ...thread,
      attention: { kind: "waiting", reason: "uncertain", workflow: null },
    }).action,
    undefined,
  );
  assert.equal(
    threadAttention({
      ...thread,
      attention: { kind: "waiting", reason: "workflow", workflow: null },
    }).action,
    undefined,
  );
  assert.equal(threadAttention({ ...thread, attention: null }), null);
});

const recentThread = (id, ts, edited = null) => {
  const root = { ...agent(id, { ts, ...(edited && { edited }) }), body: { text: id } };
  return { root, msgs: [root] };
};

test("Recent orders by last move and groups by the user's calendar day", () => {
  // 2026-03-09 00:30 local, the day after the spring-forward Sunday (a 23-hour day).
  mock.timers.enable({ apis: ["Date"], now: Date.parse("2026-03-09T04:30:00Z") });
  try {
    const old = recentThread("old", "2026-03-04T15:00:00Z", {
      id: "e",
      seq: 9,
      ts: "2026-03-09T04:10:00Z",
    });
    const beforeMidnight = recentThread("late", "2026-03-09T03:50:00Z");
    const acrossDst = recentThread("sunday", "2026-03-08T06:00:00Z");
    const saturday = recentThread("saturday", "2026-03-07T20:00:00Z");
    const order = inRecentOrder([saturday, acrossDst, beforeMidnight, old]);
    assert.deepEqual(
      order.map((thread) => thread.root.id),
      ["old", "late", "sunday", "saturday"],
    );
    assert.deepEqual(
      order.map((thread) => recentGroup(thread).label),
      ["Today", "Yesterday", "Yesterday", "Mar 7"],
    );
  } finally {
    mock.timers.reset();
  }
});

test("an unread run is marked where it starts and where the next read message stands", () => {
  const m = (key, unread) => ({ key, unread });
  const ranges = [
    { kind: "message", message: m("a", false) },
    { kind: "message", message: m("b", true) },
    { kind: "summary", expanded: true, messages: [m("c", true), m("d", false)] },
    { kind: "summary", expanded: false, messages: [m("e", true)] },
    { kind: "message", message: m("f", true) },
  ];
  assert.deepEqual(
    [...unreadBoundaries(ranges)],
    [
      ["b", "new"],
      ["d", "end"],
      ["f", "new"],
    ],
  );
});

test("narrowing transitions reset what they contradict and counts name each subset", () => {
  const resolved = transition(DEFAULT_INTENT, "status", "resolved");
  assert.equal(resolved.status, "resolved");
  assert.equal(
    transition({ ...DEFAULT_INTENT, waiting: "user" }, "status", "resolved").waiting,
    "all",
  );
  assert.equal(transition(resolved, "waiting", "user").status, "open");
  assert.equal(transition(DEFAULT_INTENT, "status", "open"), DEFAULT_INTENT);

  const onUser = { kind: "needs_user", reason: "ask" };
  // Work the agent claimed on a thread it had already answered: the card says
  // Working, so the agent filter lists it.
  const claimed = { kind: "waiting", reason: "workflow", workflow: "claim:working" };
  const threads = [
    { ...recentThread("asks", "2026-03-01T00:00:00Z"), attention: onUser },
    { ...recentThread("working", "2026-03-01T00:00:00Z"), attention: claimed },
    {
      ...recentThread("closed", "2026-03-01T00:00:00Z"),
      resolved: { author: "user" },
    },
  ];
  const groups = new Map(threads.map((thread) => [thread, { key: "section" }]));
  const model = narrowingReading(DEFAULT_INTENT, threads, groups);
  assert.deepEqual(
    model.shown.map((thread) => thread.root.id),
    ["asks", "working"],
  );
  const amounts = Object.fromEntries(
    model.presentation.groups.flatMap((group) =>
      group.choices.map((choice) => [`${group.kind}:${choice.value}`, choice.amount]),
    ),
  );
  assert.equal(amounts["status:open"], 2);
  assert.equal(amounts["status:resolved"], 1);
  assert.equal(amounts["waiting:user"], 1);
  assert.equal(amounts["waiting:agent"], 1);
  assert.equal(model.presentation.userAvailable, true);
});
