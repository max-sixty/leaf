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

// The fields of each reading the status tells apart (`activity.py`): the agent at
// work, or held by a dialog in its own window; there and taking input; there with the
// work it had in hand gone quiet, or stopped with its turn; away between turns, or away
// with an update only the user's nudge moves; and no session holding the page, or the
// agent done with it.
const WORKING = { state: "running" };
const TERMINAL = { state: "blocked", reason: "terminal", next_actor: "user" };
const LISTENING = { presence: "here", state: "waiting", next_actor: "agent" };
const QUIET = {
  presence: "here",
  state: "blocked",
  reason: "quiet",
  next_actor: "agent",
};
const STOPPED = { ...QUIET, reason: "stopped" };
const AWAY = { presence: "away", state: "waiting", next_actor: "agent" };
const STRANDED = { ...AWAY, state: "blocked", reason: "stopped", next_actor: "user" };
const GONE = { presence: "gone" };
const CLOSED = { presence: "closed" };
const READINGS = { WORKING, LISTENING, QUIET, AWAY, GONE, CLOSED };

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

test("working says the agent's own sentence, dated only in the disclosure", () => {
  const work = { ...WORKING, detail: "revising the plan", ts: minutesAgo(0) };
  assert.deepEqual(said({ ...work, counts: { unseen: 1 } }), [
    "revising the plan",
    "revising the plan (just now). 1 response owed on updates awaiting delivery.",
  ]);
  assert.deepEqual(said({ ...work, ts: minutesAgo(5) }), [
    "revising the plan",
    "revising the plan (5m ago)",
  ]);
});

test("authored activity detail retains its exact source only in the words that show it", () => {
  const source = { event_id: "progress-1", item: "question-1" };
  const activity = {
    ...WORKING,
    detail: "checking the roof",
    detail_source: source,
  };
  const reading = pageStatus(state(activity));
  const model = statusModel(reading, NO_QUEUES, "Claude");
  assert.equal(model.summary, "checking the roof");
  assert.deepEqual(
    model.summaryParts.filter((part) => part.source),
    [{ text: "checking the roof", voice: "agent", source }],
  );
  const stalled = statusModel(
    pageStatus(state({ ...activity, ...QUIET })),
    NO_QUEUES,
    "Claude",
  );
  assert.equal(
    stalled.summaryParts.some((part) => part.source),
    false,
  );
  assert.deepEqual(
    stalled.explanationParts.filter((part) => part.source),
    [{ text: "checking the roof", voice: "agent", source }],
  );
  assert.deepEqual(
    stalled.addsParts.filter((part) => part.source),
    [{ text: "checking the roof", voice: "agent", source }],
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

test("working with no sentence of the agent's leaves the row's words to it", () => {
  const picked = (waiting) =>
    said({ ...WORKING, detail: "", ts: minutesAgo(0), counts: { waiting } });
  // The leaf's tone says it works; only the disclosure says so in words, Leaf's.
  for (const waiting of [1, 3, 0])
    assert.deepEqual(picked(waiting), ["", "Working (just now)"]);
  const status = pageStatus(state({ ...WORKING, detail: "" }));
  assert.ok(status.explanationParts.every((part) => part.voice === "leaf"));
});

test("a step the transport watched names the work and stands beside the agent's sentence", () => {
  const work = { ...WORKING, detail: "revising the plan", ts: minutesAgo(0) };
  assert.deepEqual(
    said({
      ...work,
      observed_kind: "tool",
      observed: "Running the tests",
      counts: { unseen: 1 },
    }),
    [
      "revising the plan",
      "revising the plan (just now) · Running the tests. 1 response owed on updates awaiting delivery.",
    ],
  );
});

test("work waiting in the agent's own session says where it is answered, and is announced by it", () => {
  const status = pageStatus(
    state({
      ...TERMINAL,
      detail: "",
      ts: minutesAgo(0),
      observed_kind: "awaiting_approval",
    }),
  );
  assert.equal(status.explanation, "Approval needed in the terminal (just now)");
  assert.equal(status.actionableWork, "awaiting_approval");
  // The wait leads the sentence it interrupts.
  assert.equal(
    pageStatus(
      state({
        ...TERMINAL,
        detail: "Writing the page",
        observed_kind: "awaiting_input",
      }),
    ).summary,
    "Input needed in the terminal — Writing the page",
  );
  assert.equal(
    pageStatus(state({ ...WORKING, observed_kind: "tool" })).actionableWork,
    null,
  );
});

test("listening says where a comment starts, with input on its way counted after", () => {
  assert.equal(said({ ...LISTENING, detail: "" })[0], "Ready — select text to comment");
  assert.deepEqual(said({ ...LISTENING, detail: "", counts: { unseen: 1 } }), [
    "Ready — select text to comment",
    "Ready — select text to comment. 1 response owed on updates awaiting delivery.",
  ]);
});

test("a quiet claim is dated by its last word, and a dropped one by the turn's ending", () => {
  const quiet = {
    ...QUIET,
    detail: "revising the plan",
    counts: { unseen: 1 },
  };
  assert.deepEqual(said({ ...quiet, ts: minutesAgo(20) }), [
    "Last checked in 20m ago",
    "Last checked in 20m ago: revising the plan. Updates are saved.",
  ]);
  assert.deepEqual(said({ ...quiet, ts: minutesAgo(5), reason: "stopped" }), [
    "Stopped 5m ago",
    "Stopped 5m ago: revising the plan. Updates are saved.",
  ]);
  assert.deepEqual(said({ ...QUIET, detail: "", ts: null }), [
    "Haven't checked in yet",
    "Haven't checked in yet. Updates are saved.",
  ]);
});

test("away asks for a nudge only once an update is stranded", () => {
  assert.deepEqual(said({ ...AWAY, detail: "" }), [
    "Away",
    "Away right now. Updates are saved. They're picked up next turn.",
  ]);
  assert.deepEqual(said({ ...STRANDED, ts: minutesAgo(5), counts: { blocked: 1 } }), [
    "Not answering — nudge the terminal",
    "Stopped 5m ago. Updates are saved. Nothing is answering them, so nudge the terminal.",
  ]);
  // A turn interrupted mid-answer left its update as one that ended did.
  assert.equal(
    said({ ...STRANDED, reason: "interrupted", ts: minutesAgo(5) })[1],
    "Stopped 5m ago. Updates are saved. Nothing is answering them, so nudge the terminal.",
  );
});

test("each reading the user acts on differently has a kind of its own", () => {
  const kinds = [
    WORKING,
    TERMINAL,
    LISTENING,
    QUIET,
    STOPPED,
    AWAY,
    STRANDED,
    GONE,
    CLOSED,
  ].map((reading) => pageStatus(state(reading)).kind);
  assert.deepEqual(kinds, [
    "working",
    "working",
    "listening",
    "stalled",
    "stalled",
    "away",
    "away",
    "unheld",
    "closed",
  ]);
});

test("a page nobody holds, and a closed one, say so without the agent", () => {
  assert.deepEqual(said({ ...GONE, detail: "running the migration" }), [
    "Not on this page right now",
    "Not on this page right now. Updates are saved. They're picked up next time.",
  ]);
  assert.deepEqual(said(CLOSED), ["Done with this page", "Done with this page."]);
});

test("only words the agent wrote are in its voice", () => {
  const source = { event_id: "progress-1", item: "question-1" };
  const status = (activity) => pageStatus(state(activity));
  const line = { detail: "revising the plan", detail_source: source };
  // Who says each part of each wording.
  const voices = (reading) =>
    [reading.summaryParts, reading.explanationParts, reading.addsParts].map((parts) =>
      parts.map((part) => [part.text, part.voice]),
    );
  assert.deepEqual(voices(status({ ...WORKING, ...line, ts: minutesAgo(0) })), [
    [["revising the plan", "agent"]],
    [
      ["revising the plan", "agent"],
      [" (just now)", "leaf"],
    ],
    [],
  ]);
  // Everything Leaf composes is Leaf's, the agent's last line beside it or not.
  for (const [name, reading] of Object.entries(READINGS))
    assert.ok(
      voices(status({ ...reading, detail: "" }))
        .flat()
        .every(([, voice]) => voice === "leaf"),
      name,
    );
  assert.deepEqual(voices(status({ ...QUIET, ts: minutesAgo(5), ...line })), [
    [["Last checked in 5m ago", "leaf"]],
    [
      ["Last checked in 5m ago", "leaf"],
      [": ", "leaf"],
      ["revising the plan", "agent"],
      [". Updates are saved.", "leaf"],
    ],
    [
      ["Last said: ", "leaf"],
      ["revising the plan", "agent"],
      [". ", "leaf"],
      ["Updates are saved.", "leaf"],
    ],
  ]);
  // A wait in the terminal leads the agent's line in Leaf's words: only the line's
  // part carries its source, which the seats draw in the agent's voice.
  const waiting = status({
    ...TERMINAL,
    ...line,
    observed_kind: "awaiting_approval",
  });
  assert.deepEqual(
    waiting.summaryParts.map((part) => [part.text, part.voice, Boolean(part.source)]),
    [
      ["Approval needed in the terminal", "leaf", false],
      [" — ", "leaf", false],
      ["revising the plan", "agent", true],
    ],
  );
});

test("an unreachable server reports itself in the blocked tone; a refused key and an unappliable state ask", () => {
  assert.deepEqual(pageStatus(null, { reach: "unreachable" }), {
    kind: "unreachable",
    tone: "blocked",
    summary: "Lost the connection — reconnecting",
    explanation:
      "Lost the connection — reconnecting. Keep this page open so changes made here go through.",
    adds: "",
  });
  assert.deepEqual(pageStatus(null, { reach: "refused" }), {
    kind: "refused",
    tone: "blocked",
    summary: "This tab lost access — open the link again",
    explanation:
      "This tab lost access. Open the page's link again in a new tab, and keep this one open so changes made here go through.",
    adds: "Keep this tab open so changes made here go through.",
    asks: true,
  });
  assert.deepEqual(pageStatus(null, { reach: "faulted", fault: "KeyError: 'x'." }), {
    kind: "faulted",
    tone: "blocked",
    summary: "Hit a problem — trying again",
    explanation: "Hit a problem: KeyError: 'x'. Trying again.",
    adds: "KeyError: 'x'. Trying again.",
  });
  assert.deepEqual(pageStatus(null, { reach: "broken" }), {
    kind: "broken",
    tone: "blocked",
    summary: "Couldn't show the latest — reload",
    explanation: "Couldn't show the latest — reload",
    adds: "",
    asks: true,
  });
});

test("a status asks the user to act only where its words do", () => {
  const asks = (activity) =>
    statusModel(pageStatus(state(activity)), NO_QUEUES, "Claude").asks;
  // A nudge and work waiting in its own session ask.
  assert.equal(asks({ ...STRANDED, counts: { blocked: 1 } }), true);
  assert.equal(asks({ ...TERMINAL, observed_kind: "awaiting_approval" }), true);
  // Work, waiting the agent's turn, and the stock words that say where a comment
  // starts only report.
  assert.equal(asks({ ...WORKING, detail: "revising the plan" }), false);
  assert.equal(asks({ ...AWAY, detail: "" }), false);
  assert.equal(asks({ ...LISTENING, detail: "" }), false);
  assert.equal(asks({ ...LISTENING, detail: "", counts: { unseen: 1 } }), false);
  assert.equal(asks({ ...QUIET, ts: minutesAgo(20) }), false);
  assert.equal(asks(GONE), false);
  // A server that went away reconnects by itself; a refused key waits on the user.
  const reached = (reach) =>
    statusModel(pageStatus(null, { reach }), NO_QUEUES, "Claude").asks;
  assert.equal(reached("unreachable"), false);
  assert.equal(reached("refused"), true);
});

// The served lists as `readQueues` publishes them, each row joined to its record.
function publishedQueues(reading) {
  const { obligations, queues } = reading.browser.views["1"];
  const records = new Map(obligations.map((record) => [record.id, record]));
  const join = (rows) =>
    rows.map((row) => ({ ...row, obligation: records.get(row.id) }));
  return { on_user: join(queues.on_user), on_agent: join(queues.on_agent) };
}

test("the explanation names what waits on each side", () => {
  const reading = servedReading("queues on both sides");
  const queues = publishedQueues(reading);
  const status = pageStatus({
    ...reading,
    activity: servedActivity(LISTENING),
  });
  const model = statusModel(status, queues, reading.agent);
  const long = statusModel(status, queues, "Codex Research Agent");
  assert.match(long.explanation, /Waiting on Codex Research Agent: 1 reply/);
  assert.equal(
    model.explanation,
    "Ready — select text to comment. Waiting on me: 2 to answer, 2 updates to send again. Waiting on Agent: 1 reply, 1 to-do (Rebuild the chart).",
  );
  // A to-do's title is the agent's words; the count around it is Leaf's.
  assert.deepEqual(
    model.explanationParts
      .filter((part) => part.voice === "agent")
      .map((part) => part.text),
    ["Rebuild the chart"],
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
    "Lost the connection — reconnecting. Keep this page open so changes made here go through.",
  );
});

test("what the disclosure adds to the row says only what the row does not", () => {
  const reading = servedReading("queues on both sides");
  const queues = publishedQueues(reading);
  const adds = (activity, onBoth = NO_QUEUES) =>
    statusModel(pageStatus(state(activity)), onBoth, "Claude").adds;
  const work = { ...WORKING, detail: "revising the plan", ts: minutesAgo(0) };
  // Working restates the row; what follows the sentence is all it adds. What waits on
  // each side stands on the tabs beside the menu, so the menu's status leaves it out.
  assert.equal(adds(work), "");
  assert.equal(
    adds({ ...work, observed_kind: "tool", observed: "Running the tests" }, queues),
    "Running the tests",
  );
  assert.equal(adds({ ...LISTENING, detail: "" }), "");
  // What the sentence says past the row, without the state the row already says.
  assert.equal(
    adds({
      ...WORKING,
      detail: "",
      ts: minutesAgo(0),
      counts: { waiting: 1 },
    }),
    "Working",
  );
  assert.equal(
    adds({ ...LISTENING, detail: "", counts: { unseen: 1 } }),
    "1 response owed on updates awaiting delivery.",
  );
  assert.equal(
    adds({ ...AWAY, detail: "" }),
    "Updates are saved. They're picked up next turn.",
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
  for (const reading of [CLOSED, GONE, LISTENING, AWAY, QUIET]) {
    const detail = reading === LISTENING ? "" : "revising the plan";
    const status = published({ ...reading, detail });
    assert.equal(status.kind, "listening");
    assert.equal(status.tone, "listening");
    assert.equal(status.summary, "Ready — comment to revise this copy");
    assert.equal(status.asks, false);
  }
  // Its work reads as on any page.
  const working = published({ ...WORKING, detail: "revising the plan" });
  assert.equal(working.tone, "working");
  assert.equal(working.summary, "revising the plan");
  const model = statusModel(published(CLOSED), NO_QUEUES, "Agent");
  assert.equal(
    model.explanation,
    "Ready — comment to revise this copy. This website is a Leaf page, and this copy is private to this browser. Install Leaf",
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
    published(CLOSED, { kind: "example" }),
    NO_QUEUES,
    "Agent",
  );
  assert.equal(
    example.explanation,
    "Ready — comment to revise this copy. This is an example on the Leaf website, and this copy is private to this browser. Other examples Install Leaf",
  );
  assert.equal(example.publication.examplesUrl, "/examples/");
});

test("a leaves row says each kind in a row's words, with the updates still waiting", () => {
  const row = (activity) => leafRow(state(activity)).line;
  assert.equal(row({ ...WORKING, detail: "recording the demo" }), "recording the demo");
  assert.equal(
    row({
      ...WORKING,
      detail: "",
      observed_kind: "tool",
      counts: { unseen: 3 },
    }),
    "3 responses owed on updates awaiting delivery",
  );
  assert.equal(
    row({
      ...TERMINAL,
      detail: "Writing the page",
      observed_kind: "awaiting_approval",
    }),
    "Approval needed in the terminal — Writing the page",
  );
  // Each part is in the voice of whoever said it.
  const voices = (activity) =>
    leafRow(state(activity)).parts.map((part) => [part.text, part.voice]);
  assert.deepEqual(voices({ ...WORKING, detail: "recording the demo" }), [
    ["recording the demo", "agent"],
  ]);
  assert.deepEqual(voices({ ...QUIET, detail: "revising", ts: minutesAgo(20) }), [
    ["Last checked in 20m ago", "leaf"],
    [" — ", "leaf"],
    ["revising", "agent"],
  ]);
  assert.equal(row({ ...LISTENING, detail: "" }), "Ready");
  assert.equal(
    row({ ...LISTENING, detail: "", counts: { unseen: 1 } }),
    "Ready · 1 response owed on updates awaiting delivery",
  );
  assert.equal(
    row({ ...QUIET, detail: "revising", ts: minutesAgo(20) }),
    "Last checked in 20m ago — revising",
  );
  assert.equal(row({ ...STOPPED, detail: "", ts: minutesAgo(5) }), "Stopped 5m ago");
  assert.equal(row(AWAY), "Away");
  assert.equal(
    row({ ...STRANDED, ts: minutesAgo(5), counts: { blocked: 1 } }),
    "Stopped 5m ago",
  );
  assert.equal(row(GONE), "Not on this page right now");
  assert.equal(row(CLOSED), "Done with this page");
  assert.equal(leafRow(state(QUIET)).tone, "away");
});

test("the facts both seats share count what the agent owes apart from what waits", () => {
  const facts = activityFacts(
    state({ counts: { running: 1, waiting: 2, blocked: 1, unseen: 3 } }),
  );
  assert.deepEqual(facts.waiting, ["3 responses owed on updates awaiting delivery"]);
  assert.deepEqual(facts.owed, [
    "1 response being worked on",
    "2 responses owed",
    "1 response owed on updates that stopped",
  ]);
});
