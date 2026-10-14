/* What the banner and the leaves drawer say for each served activity reading
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

// The page's served state with `activity`, as the banner reads it.
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

test("working with no sentence of the agent's names what its turn picked up", () => {
  const picked = (handling, handling_comments) =>
    said({
      kind: "working",
      detail: "",
      ts: minutesAgo(0),
      counts: { handling, handling_comments },
    });
  assert.deepEqual(picked(1, 1), [
    "Claude working — picked up the comment",
    "Claude picked up the comment and hasn't said what it's doing yet (just now)",
  ]);
  assert.equal(picked(1, 0)[0], "Claude working — picked up the answer");
  assert.equal(picked(3, 2)[0], "Claude working — picked up 2 comments and 1 answer");
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
    "Claude is waiting for approval (just now). It waits in its own session, not on this page.",
  );
  assert.equal(status.actionableWork, "awaiting_approval");
  assert.equal(pageStatus(state({ kind: "working" })).actionableWork, null);
});

test("listening keeps the agent's request on the row until input supersedes it", () => {
  assert.deepEqual(said({ kind: "listening", detail: "pick a storage engine" }), [
    "Claude awaits — pick a storage engine",
    "Claude awaits — pick a storage engine",
  ]);
  assert.equal(
    said({ kind: "listening", detail: "" })[0],
    "Claude awaits — select text to comment",
  );
  assert.deepEqual(
    said({
      kind: "listening",
      detail: "pick a storage engine",
      counts: { pending: 1 },
    }),
    [
      "Claude listening",
      "Claude is listening — pick a storage engine. 1 response owed on updates awaiting delivery.",
    ],
  );
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
    "No check-in from Claude is recorded",
    "No check-in from Claude is recorded. Updates are saved.",
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
      "Nudge Claude in terminal",
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

test("an unreachable server, a refused key and an unappliable state each say what to do", () => {
  assert.deepEqual(pageStatus(null), {
    kind: "unreachable",
    tone: "offline",
    summary: "Server offline — reconnecting; keep page open",
    explanation:
      "Server offline — reconnecting. Keep this page open so pending changes can send.",
  });
  assert.deepEqual(pageStatus(null, { keyRefused: true }), {
    kind: "unreachable",
    tone: "offline",
    summary: "Key refused — open Leaf's link in a new tab",
    explanation:
      "The server no longer accepts this tab's key. Open the link Leaf printed in a new tab, and keep this one open so pending changes can send.",
  });
  assert.deepEqual(pageStatus(new Error("bad state")), {
    kind: "broken",
    tone: "offline",
    summary: "Page couldn't apply current state — reload",
    explanation: "Page couldn't apply current state — reload",
  });
});

test("the disclosure names what waits on each side, and the row counts the agent's", () => {
  const reading = servedReading("queues on both sides");
  const { queues } = reading.browser.views["1"];
  const status = pageStatus({
    ...reading,
    activity: servedActivity({ kind: "listening" }),
  });
  const model = statusModel(status, queues, reading.agent);
  assert.equal(model.queues, "On Agent: 2");
  // The row cuts a long name to the room its box keeps; the disclosure keeps it whole.
  const long = statusModel(status, queues, "Codex Research Agent");
  assert.deepEqual(
    [long.queues, long.queuesWidest],
    ["On Codex Resea…: 2", "On Codex Resea…: 9"],
  );
  assert.match(long.explanation, /Waiting on Codex Research Agent: 1 reply/);
  assert.equal(
    model.explanation,
    "Agent awaits — select text to comment. Waiting on me: 2 asks, 1 to-do (Try the build on a phone), 2 updates to send again. Waiting on Agent: 1 reply, 1 to-do (Rebuild the chart).",
  );
  // A page with nothing waiting adds nothing, and an offline page counts nothing.
  assert.equal(statusModel(status, NO_QUEUES, "Agent").explanation, status.explanation);
  const offline = statusModel(pageStatus(null), queues, reading.agent);
  assert.deepEqual(
    [offline.queues, offline.explanation],
    [
      "",
      "Server offline — reconnecting. Keep this page open so pending changes can send.",
    ],
  );
});

test("a published page introduces itself and its links in place of the status", () => {
  const publication = { agent: "Agent", install_url: "/#install" };
  const status = pageStatus({ ...state({ kind: "working" }), publication });
  assert.deepEqual(status, { kind: "publication", tone: "", publication });
  const model = statusModel(status, NO_QUEUES, "Agent");
  assert.equal(
    model.explanation,
    "This website is a Leaf page. Agent replies and revises this private copy. Install Leaf",
  );
  assert.deepEqual(model.publication, {
    copy: "This website is a Leaf page. Agent replies and revises this private copy. ",
    examples: null,
    install: "Install Leaf",
    installUrl: "/#install",
    examplesUrl: null,
  });
  const example = statusModel(
    pageStatus({ ...state({}), publication: { ...publication, kind: "example" } }),
    NO_QUEUES,
    "Agent",
  );
  assert.equal(
    example.explanation,
    "This is an example on the Leaf website. Agent replies and revises this private copy. Other examples Install Leaf",
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
  assert.equal(
    row({ kind: "listening", detail: "pick a storage engine" }),
    "Awaits — pick a storage engine",
  );
  assert.equal(
    row({ kind: "listening", detail: "", counts: { pending: 1 } }),
    "Listening · 1 response owed on updates awaiting delivery",
  );
  assert.equal(
    row({ kind: "stalled", detail: "revising", ts: minutesAgo(20) }),
    "Quiet (20m ago) — revising",
  );
  assert.equal(
    row({ kind: "stalled", detail: "", ts: minutesAgo(5), dropped: true }),
    "Left (5m ago)",
  );
  assert.equal(row({ kind: "away" }), "Away");
  assert.equal(
    row({ kind: "away", dropped: true, ts: minutesAgo(5), counts: { overdue: 1 } }),
    "Left (5m ago)",
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
    "2 responses owed on picked-up updates",
    "1 response owed on picked-up updates; no current turn observed",
  ]);
  assert.equal(facts.listening, true);
  assert.equal(activityFacts(state({})).listening, false);
});
