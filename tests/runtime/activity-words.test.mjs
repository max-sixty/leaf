/* What the status and All pages say for each served activity reading
   (`activity-words.js`).

   Every case starts from the activity the server sends for a page a live session holds
   (`served.mjs`), changing only the fields the case is about, and reads it at the moment
   that reading was taken. Which activity a log and a claim come to is the server's
   fold, held by `tests/model/test_activity.py`. */

import assert from "node:assert/strict";
import test from "node:test";

import {
  activityFacts,
  leafRow,
  pageStatus,
  statusModel,
} from "/runtime/activity-words.js";
import { servedActivity, servedReading } from "../served.mjs";

const NOW = Date.parse(servedActivity().ts);
const minutesAgo = (minutes) => new Date(NOW - minutes * 60_000).toISOString();
const NO_QUEUES = { on_user: [], on_agent: [], done: [] };

// The page's served state with `activity`, as the status reads it.
const state = (activity) => ({
  activity: servedActivity(activity),
  agent: "Claude",
  publication: null,
});
// The row's words and the disclosure's, for one activity reading.
const said = (activity) => {
  const { summary, explanation } = pageStatus(state(activity));
  return [summary, explanation];
};

test.beforeEach((t) => t.mock.timers.enable({ apis: ["Date"], now: NOW }));

test("working says the agent's own sentence, dated on the row once it is old", () => {
  const work = { kind: "working", detail: "revising the plan", ts: minutesAgo(0) };
  assert.deepEqual(said({ ...work, counts: { pending: 1 } }), [
    "Claude working — revising the plan",
    "Claude is working — revising the plan (just now). 1 response owed on updates awaiting delivery.",
  ]);
  assert.deepEqual(said({ ...work, ts: minutesAgo(5) }), [
    "Claude working · 5m ago — revising the plan",
    "Claude is working — revising the plan (5m ago)",
  ]);
});

test("authored activity detail retains its exact source only in the words that show it", () => {
  const source = { event_id: "progress-1", item: "question-1" };
  const activity = {
    kind: "working",
    detail: "checking the roof",
    detail_source: source,
  };
  const reading = pageStatus(state(activity));
  const model = statusModel(reading, NO_QUEUES, "Claude");
  assert.equal(model.summary, "Claude working — checking the roof");
  assert.deepEqual(
    model.summaryParts.filter((part) => part.source),
    [{ text: "checking the roof", source }],
  );
  const stalled = statusModel(
    pageStatus(state({ ...activity, kind: "stalled" })),
    NO_QUEUES,
    "Claude",
  );
  assert.equal(
    stalled.summaryParts.some((part) => part.source),
    false,
  );
  assert.deepEqual(
    stalled.explanationParts.filter((part) => part.source),
    [{ text: "checking the roof", source }],
  );
  assert.deepEqual(
    stalled.addsParts.filter((part) => part.source),
    [{ text: "checking the roof", source }],
  );
  const generic = statusModel(
    pageStatus(state({ ...activity, detail_source: null })),
    NO_QUEUES,
    "Claude",
  );
  assert.equal(
    generic.summaryParts.some((part) => part.source),
    false,
  );
});

test("working with no sentence of the agent's names what its turn picked up", () => {
  const picked = (handling, handling_comments) =>
    said({
      kind: "working",
      detail: "",
      ts: minutesAgo(0),
      counts: { handling, handling_comments },
    });
  assert.deepEqual(picked(1, 1), [
    "Claude working — has the comment",
    "Claude has the comment and hasn't said what it's doing yet (just now)",
  ]);
  assert.equal(picked(1, 0)[0], "Claude working — has the answer");
  assert.equal(picked(3, 2)[0], "Claude working — has 2 comments and 1 answer");
  // Nothing picked up and nothing said is plain work.
  assert.deepEqual(picked(0, 0), ["Claude working", "Claude is working (just now)"]);
});

test("a step the transport watched names the work and stands beside the agent's sentence", () => {
  const work = { kind: "working", detail: "revising the plan", ts: minutesAgo(0) };
  assert.deepEqual(
    said({
      ...work,
      observed_kind: "tool",
      observed: "Running the tests",
      counts: { pending: 1 },
    }),
    [
      "Claude using a tool — revising the plan",
      "Claude is using a tool — revising the plan (just now) · Running the tests. 1 response owed on updates awaiting delivery.",
    ],
  );
});

test("work waiting in the agent's own session says where it is answered, and is announced by it", () => {
  const status = pageStatus(
    state({
      kind: "working",
      detail: "",
      ts: minutesAgo(0),
      observed_kind: "awaiting_approval",
      awaiting: true,
    }),
  );
  assert.equal(
    status.explanation,
    "Claude is waiting for approval in the terminal (just now)",
  );
  assert.equal(status.actionableWork, "awaiting_approval");
  assert.equal(pageStatus(state({ kind: "working" })).actionableWork, null);
});

test("listening says where a comment starts, with input on its way counted after", () => {
  assert.equal(
    said({ kind: "listening", detail: "" })[0],
    "Claude awaits — select text to comment",
  );
  assert.deepEqual(said({ kind: "listening", detail: "", counts: { pending: 1 } }), [
    "Claude awaits — select text to comment",
    "Claude awaits — select text to comment. 1 response owed on updates awaiting delivery.",
  ]);
});

test("a quiet claim is dated by its last word, and a dropped one by the turn's ending", () => {
  const quiet = {
    kind: "stalled",
    detail: "revising the plan",
    counts: { pending: 1 },
  };
  assert.deepEqual(said({ ...quiet, ts: minutesAgo(20) }), [
    "Claude last checked in 20m ago",
    "Claude last checked in 20m ago: revising the plan. Updates are saved.",
  ]);
  assert.deepEqual(said({ ...quiet, ts: minutesAgo(5), dropped: true }), [
    "Claude’s turn ended 5m ago",
    "Claude’s turn ended 5m ago: revising the plan. Updates are saved.",
  ]);
  assert.deepEqual(said({ kind: "stalled", detail: "", ts: null }), [
    "Claude hasn't checked in",
    "Claude hasn't checked in. Updates are saved.",
  ]);
});

test("away asks for a nudge only once input is overdue", () => {
  assert.deepEqual(said({ kind: "away", detail: "" }), [
    "Claude away",
    "Claude isn't watching right now. Updates are saved. It picks them up next turn.",
  ]);
  assert.deepEqual(
    said({ kind: "away", dropped: true, ts: minutesAgo(5), counts: { overdue: 1 } }),
    [
      "Nudge Claude in the terminal",
      "Claude’s turn ended 5m ago. Updates are saved. Nothing is answering them, so nudge it in the terminal.",
    ],
  );
});

test("a page nobody holds, and a closed one, say so without the agent", () => {
  assert.deepEqual(said({ kind: "unheld", detail: "running the migration" }), [
    "No session",
    "No session holds this page. Updates are saved. It picks up again when a session does.",
  ]);
  assert.deepEqual(said({ kind: "closed" }), ["Page closed", "Page closed"]);
});

test("an unreachable server reports itself in the blocked tone; a refused key and an unappliable state ask", () => {
  assert.deepEqual(pageStatus(null, { reach: "unreachable" }), {
    kind: "unreachable",
    tone: "blocked",
    summary: "Server offline — reconnecting",
    explanation:
      "Server offline — reconnecting. Keep this page open so pending changes can send.",
    adds: "",
  });
  assert.deepEqual(pageStatus(null, { reach: "refused" }), {
    kind: "refused",
    tone: "blocked",
    summary: "Key refused — open Leaf's link in a new tab",
    explanation:
      "The server no longer accepts this tab's key. Open the link Leaf printed in a new tab, and keep this one open so pending changes can send.",
    adds: "Keep this tab open so pending changes can send.",
    asks: true,
  });
  assert.deepEqual(pageStatus(null, { reach: "faulted", fault: "KeyError: 'x'." }), {
    kind: "faulted",
    tone: "blocked",
    summary: "Server error — retrying",
    explanation: "The server answered with an error: KeyError: 'x'. Retrying.",
    adds: "It answered: KeyError: 'x'. Retrying.",
  });
  assert.deepEqual(pageStatus(null, { reach: "broken" }), {
    kind: "broken",
    tone: "blocked",
    summary: "Page couldn't apply current state — reload",
    explanation: "Page couldn't apply current state — reload",
    adds: "",
    asks: true,
  });
});

test("a status asks the user to act only where its words do", () => {
  const asks = (activity) =>
    statusModel(pageStatus(state(activity)), NO_QUEUES, "Claude").asks;
  // A nudge and work waiting in its own session ask.
  assert.equal(asks({ kind: "away", dropped: true, counts: { overdue: 1 } }), true);
  assert.equal(
    asks({ kind: "working", observed_kind: "awaiting_approval", awaiting: true }),
    true,
  );
  // Work, waiting the agent's turn, and the stock words that say where a comment
  // starts only report.
  assert.equal(asks({ kind: "working", detail: "revising the plan" }), false);
  assert.equal(asks({ kind: "away", detail: "" }), false);
  assert.equal(asks({ kind: "listening", detail: "" }), false);
  assert.equal(asks({ kind: "listening", detail: "", counts: { pending: 1 } }), false);
  assert.equal(asks({ kind: "stalled", ts: minutesAgo(20) }), false);
  assert.equal(asks({ kind: "unheld" }), false);
  // A server that went away reconnects by itself; a refused key waits on the user.
  const reached = (reach) =>
    statusModel(pageStatus(null, { reach }), NO_QUEUES, "Claude").asks;
  assert.equal(reached("unreachable"), false);
  assert.equal(reached("refused"), true);
});

// The served lists as `readQueues` publishes them, each to-do row joined to its record.
function publishedQueues(reading) {
  const todos = new Map(reading.browser.todos.map((todo) => [todo.id, todo]));
  const join = (rows) =>
    rows.map((row) =>
      row.kind === "todo" ? { ...row, todo: todos.get(row.id) } : row,
    );
  const { on_user: onUser, on_agent: onAgent } = reading.browser.views["1"].queues;
  return { on_user: join(onUser), on_agent: join(onAgent) };
}

test("the explanation names what waits on each side", () => {
  const reading = servedReading("queues on both sides");
  const queues = publishedQueues(reading);
  const status = pageStatus({
    ...reading,
    activity: servedActivity({ kind: "listening" }),
  });
  const model = statusModel(status, queues, reading.agent);
  const long = statusModel(status, queues, "Codex Research Agent");
  assert.match(long.explanation, /Waiting on Codex Research Agent: 1 reply/);
  assert.equal(
    model.explanation,
    "Agent awaits — select text to comment. Waiting on me: 2 to answer, 1 to-do (Try the build on a phone), 2 updates to send again. Waiting on Agent: 1 reply, 1 to-do (Rebuild the chart).",
  );
  // A page with nothing waiting adds nothing, and an offline page counts nothing.
  assert.equal(statusModel(status, NO_QUEUES, "Agent").explanation, status.explanation);
  const offline = statusModel(
    pageStatus(reading, { reach: "unreachable" }),
    queues,
    reading.agent,
  );
  assert.equal(
    offline.explanation,
    "Server offline — reconnecting. Keep this page open so pending changes can send.",
  );
});

test("what the disclosure adds to the row says only what the row does not", () => {
  const reading = servedReading("queues on both sides");
  const queues = publishedQueues(reading);
  const adds = (activity, onBoth = NO_QUEUES) =>
    statusModel(pageStatus(state(activity)), onBoth, "Claude").adds;
  const work = { kind: "working", detail: "revising the plan", ts: minutesAgo(0) };
  // Working restates the row; what follows the sentence is all it adds.
  assert.equal(adds(work), "");
  assert.equal(
    adds({ ...work, observed_kind: "tool", observed: "Running the tests" }, queues),
    "Running the tests. Waiting on me: 2 to answer, 1 to-do (Try the build on a phone), 2 updates to send again. Waiting on Claude: 1 reply, 1 to-do (Rebuild the chart).",
  );
  assert.equal(adds({ kind: "listening", detail: "" }), "");
  // What the sentence says past the row, without the state the row already says.
  assert.equal(
    adds({
      kind: "working",
      detail: "",
      ts: minutesAgo(0),
      counts: { handling: 1, handling_comments: 1 },
    }),
    "It hasn't said what it's doing yet.",
  );
  assert.equal(
    adds({ kind: "listening", detail: "", counts: { pending: 1 } }),
    "1 response owed on updates awaiting delivery.",
  );
  assert.equal(
    adds({ kind: "away", detail: "" }),
    "Updates are saved. It picks them up next turn.",
  );
  assert.equal(pageStatus(null, { reach: "unreachable" }).adds, "");
});

test("a published page's agent is on call, and its explanation introduces the page", () => {
  const publication = { agent: "Agent", install_url: "/#install" };
  // The server names a hosted copy's agent after its publication.
  const published = (activity, extra = {}) =>
    pageStatus({
      ...state(activity),
      agent: "Agent",
      publication: { ...publication, ...extra },
    });
  // A comment starts the agent, so whenever it isn't working it reads as listening,
  // inviting that comment, whether no session holds the copy yet or one went quiet
  // with a line of work it never finished.
  for (const kind of ["closed", "unheld", "listening", "away", "stalled"]) {
    const detail = kind === "listening" ? "" : "revising the plan";
    const status = published({ kind, detail });
    assert.equal(status.kind, "listening");
    assert.equal(status.tone, "listening");
    assert.equal(status.summary, "Agent awaits — comment to revise this copy");
    assert.equal(status.asks, false);
  }
  // Its work reads as on any page.
  const working = published({ kind: "working", detail: "revising the plan" });
  assert.equal(working.tone, "working");
  assert.equal(working.summary, "Agent working — revising the plan");
  const model = statusModel(published({ kind: "closed" }), NO_QUEUES, "Agent");
  assert.equal(
    model.explanation,
    "Agent awaits — comment to revise this copy. This website is a Leaf page, and this copy is private to this browser. Install Leaf",
  );
  assert.equal(model.adds, "");
  assert.deepEqual(model.publication, {
    copy: "This website is a Leaf page, and this copy is private to this browser. ",
    examples: null,
    install: "Install Leaf",
    installUrl: "/#install",
    examplesUrl: null,
  });
  const example = statusModel(
    published({ kind: "closed" }, { kind: "example" }),
    NO_QUEUES,
    "Agent",
  );
  assert.equal(
    example.explanation,
    "Agent awaits — comment to revise this copy. This is an example on the Leaf website, and this copy is private to this browser. Other examples Install Leaf",
  );
  assert.equal(example.publication.examplesUrl, "/examples/");
});

test("a leaves row says each kind in a row's words, with the updates still waiting", () => {
  const row = (activity) => leafRow(state(activity)).line;
  assert.equal(
    row({ kind: "working", detail: "recording the demo" }),
    "Working — recording the demo",
  );
  assert.equal(
    row({
      kind: "working",
      detail: "",
      observed_kind: "tool",
      counts: { pending: 1, queued: 2 },
    }),
    "Using a tool · 2 responses owed on queued updates · 1 response owed on updates awaiting delivery",
  );
  assert.equal(row({ kind: "listening", detail: "" }), "Awaits");
  assert.equal(
    row({ kind: "listening", detail: "", counts: { pending: 1 } }),
    "Awaits · 1 response owed on updates awaiting delivery",
  );
  assert.equal(
    row({ kind: "stalled", detail: "revising", ts: minutesAgo(20) }),
    "Last checked in 20m ago — revising",
  );
  assert.equal(
    row({ kind: "stalled", detail: "", ts: minutesAgo(5), dropped: true }),
    "Turn ended 5m ago",
  );
  assert.equal(row({ kind: "away" }), "Away");
  assert.equal(
    row({ kind: "away", dropped: true, ts: minutesAgo(5), counts: { overdue: 1 } }),
    "Turn ended 5m ago",
  );
  assert.equal(row({ kind: "unheld" }), "No session");
  assert.equal(row({ kind: "closed" }), "Closed");
  assert.equal(leafRow(state({ kind: "stalled" })).tone, "away");
});

test("the facts both seats share count what the agent owes apart from what waits", () => {
  const facts = activityFacts(
    state({ counts: { active: 1, handling: 2, picked_up: 1, queued: 1, pending: 3 } }),
  );
  assert.deepEqual(facts.waiting, [
    "1 response owed on queued updates",
    "3 responses owed on updates awaiting delivery",
  ]);
  assert.deepEqual(facts.owed, [
    "1 response being worked on",
    "2 responses owed on delivered updates",
    "1 response owed on delivered updates; no current turn observed",
  ]);
});
