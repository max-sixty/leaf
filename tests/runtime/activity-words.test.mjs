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

test("working says the agent's own sentence, dated only in the disclosure", () => {
  const work = { kind: "working", detail: "revising the plan", ts: minutesAgo(0) };
  assert.deepEqual(said({ ...work, counts: { pending: 1 } }), [
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
    kind: "working",
    detail: "checking the roof",
    detail_source: source,
  };
  const reading = pageStatus(state(activity));
  const model = statusModel(reading, NO_QUEUES, "Claude");
  assert.equal(model.summary, "checking the roof");
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

test("working with no sentence of the agent's leaves the row's words to it", () => {
  const picked = (handling) =>
    said({ kind: "working", detail: "", ts: minutesAgo(0), counts: { handling } });
  // The leaf's tone says it works; only the disclosure says so in words, Leaf's.
  for (const handling of [1, 3, 0])
    assert.deepEqual(picked(handling), ["", "Working (just now)"]);
  const status = pageStatus(state({ kind: "working", detail: "" }));
  assert.equal(status.voice, "leaf");
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
      "revising the plan",
      "revising the plan (just now) · Running the tests. 1 response owed on updates awaiting delivery.",
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
  assert.equal(status.explanation, "Approval needed in the terminal (just now)");
  assert.equal(status.actionableWork, "awaiting_approval");
  // The wait leads the sentence it interrupts.
  assert.equal(
    pageStatus(
      state({
        kind: "working",
        detail: "Writing the page",
        observed_kind: "awaiting_input",
        awaiting: true,
      }),
    ).summary,
    "Input needed in the terminal — Writing the page",
  );
  assert.equal(pageStatus(state({ kind: "working" })).actionableWork, null);
});

test("listening says where a comment starts, with input on its way counted after", () => {
  assert.equal(
    said({ kind: "listening", detail: "" })[0],
    "Ready — select text to comment",
  );
  assert.deepEqual(said({ kind: "listening", detail: "", counts: { pending: 1 } }), [
    "Ready — select text to comment",
    "Ready — select text to comment. 1 response owed on updates awaiting delivery.",
  ]);
});

test("a quiet claim is dated by its last word, and a dropped one by the turn's ending", () => {
  const quiet = {
    kind: "stalled",
    detail: "revising the plan",
    counts: { pending: 1 },
  };
  assert.deepEqual(said({ ...quiet, ts: minutesAgo(20) }), [
    "Last checked in 20m ago",
    "Last checked in 20m ago: revising the plan. Updates are saved.",
  ]);
  assert.deepEqual(said({ ...quiet, ts: minutesAgo(5), dropped: true }), [
    "Stopped 5m ago",
    "Stopped 5m ago: revising the plan. Updates are saved.",
  ]);
  assert.deepEqual(said({ kind: "stalled", detail: "", ts: null }), [
    "Haven't checked in yet",
    "Haven't checked in yet. Updates are saved.",
  ]);
});

test("away asks for a nudge only once input is overdue", () => {
  assert.deepEqual(said({ kind: "away", detail: "" }), [
    "Away",
    "Away right now. Updates are saved. They're picked up next turn.",
  ]);
  assert.deepEqual(
    said({ kind: "away", dropped: true, ts: minutesAgo(5), counts: { overdue: 1 } }),
    [
      "Not answering — nudge the terminal",
      "Stopped 5m ago. Updates are saved. Nothing is answering them, so nudge the terminal.",
    ],
  );
});

test("a page nobody holds, and a closed one, say so without the agent", () => {
  assert.deepEqual(said({ kind: "unheld", detail: "running the migration" }), [
    "Not on this page right now",
    "Not on this page right now. Updates are saved. They're picked up next time.",
  ]);
  assert.deepEqual(said({ kind: "closed" }), [
    "Done with this page",
    "Done with this page.",
  ]);
});

test("only words the agent wrote are in its voice", () => {
  const source = { event_id: "progress-1", item: "question-1" };
  const status = (activity) => pageStatus(state(activity));
  const line = { detail: "revising the plan", detail_source: source };
  assert.equal(status({ kind: "working", ...line }).voice, "agent");
  // Everything Leaf composes is Leaf's, the agent's last line beside it or not.
  for (const kind of ["working", "listening", "stalled", "away", "unheld", "closed"])
    assert.equal(status({ kind, detail: "" }).voice, "leaf", kind);
  assert.equal(status({ kind: "stalled", ts: minutesAgo(5), ...line }).voice, "leaf");
  assert.equal(status({ kind: "away", counts: { overdue: 1 } }).voice, "leaf");
  assert.equal(pageStatus(null, { reach: "unreachable" }).voice, "leaf");
  // A wait in the terminal leads the agent's line in Leaf's words: only the line's
  // part carries its source, which the seats draw in the agent's voice.
  const waiting = status({
    kind: "working",
    ...line,
    observed_kind: "awaiting_approval",
    awaiting: true,
  });
  assert.deepEqual(
    waiting.summaryParts.map((part) => [part.text, Boolean(part.source)]),
    [
      ["Approval needed in the terminal", false],
      [" — ", false],
      ["revising the plan", true],
    ],
  );
});

test("an unreachable server reports itself in the blocked tone; a refused key and an unappliable state ask", () => {
  assert.deepEqual(pageStatus(null, { reach: "unreachable" }), {
    kind: "unreachable",
    tone: "blocked",
    summary: "Lost the connection — reconnecting",
    voice: "leaf",
    explanation:
      "Lost the connection — reconnecting. Keep this page open so changes made here go through.",
    adds: "",
  });
  assert.deepEqual(pageStatus(null, { reach: "refused" }), {
    kind: "refused",
    tone: "blocked",
    summary: "This tab lost access — open the link again",
    voice: "leaf",
    explanation:
      "This tab lost access. Open the page's link again in a new tab, and keep this one open so changes made here go through.",
    adds: "Keep this tab open so changes made here go through.",
    asks: true,
  });
  assert.deepEqual(pageStatus(null, { reach: "faulted", fault: "KeyError: 'x'." }), {
    kind: "faulted",
    tone: "blocked",
    summary: "Hit a problem — trying again",
    voice: "leaf",
    explanation: "Hit a problem: KeyError: 'x'. Trying again.",
    adds: "KeyError: 'x'. Trying again.",
  });
  assert.deepEqual(pageStatus(null, { reach: "broken" }), {
    kind: "broken",
    tone: "blocked",
    summary: "Couldn't show the latest — reload",
    voice: "leaf",
    explanation: "Couldn't show the latest — reload",
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
    "Ready — select text to comment. Waiting on me: 2 to answer, 1 to-do (Try the build on a phone), 2 updates to send again. Waiting on Agent: 1 reply, 1 to-do (Rebuild the chart).",
  );
  // A to-do's title is the agent's words; the count around it is Leaf's.
  assert.deepEqual(
    model.explanationParts
      .filter((part) => part.voice === "agent")
      .map((part) => part.text),
    ["Try the build on a phone", "Rebuild the chart"],
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
  const work = { kind: "working", detail: "revising the plan", ts: minutesAgo(0) };
  // Working restates the row; what follows the sentence is all it adds. What waits on
  // each side stands on the tabs beside the menu, so the menu's status leaves it out.
  assert.equal(adds(work), "");
  assert.equal(
    adds({ ...work, observed_kind: "tool", observed: "Running the tests" }, queues),
    "Running the tests",
  );
  assert.equal(adds({ kind: "listening", detail: "" }), "");
  // What the sentence says past the row, without the state the row already says.
  assert.equal(
    adds({
      kind: "working",
      detail: "",
      ts: minutesAgo(0),
      counts: { handling: 1 },
    }),
    "Working",
  );
  assert.equal(
    adds({ kind: "listening", detail: "", counts: { pending: 1 } }),
    "1 response owed on updates awaiting delivery.",
  );
  assert.equal(
    adds({ kind: "away", detail: "" }),
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
  for (const kind of ["closed", "unheld", "listening", "away", "stalled"]) {
    const detail = kind === "listening" ? "" : "revising the plan";
    const status = published({ kind, detail });
    assert.equal(status.kind, "listening");
    assert.equal(status.tone, "listening");
    assert.equal(status.summary, "Ready — comment to revise this copy");
    assert.equal(status.asks, false);
  }
  // Its work reads as on any page.
  const working = published({ kind: "working", detail: "revising the plan" });
  assert.equal(working.tone, "working");
  assert.equal(working.summary, "revising the plan");
  const model = statusModel(published({ kind: "closed" }), NO_QUEUES, "Agent");
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
    published({ kind: "closed" }, { kind: "example" }),
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
  assert.equal(
    row({ kind: "working", detail: "recording the demo" }),
    "recording the demo",
  );
  assert.equal(
    row({
      kind: "working",
      detail: "",
      observed_kind: "tool",
      counts: { pending: 1, queued: 2 },
    }),
    "2 responses owed on queued updates · 1 response owed on updates awaiting delivery",
  );
  assert.equal(
    row({
      kind: "working",
      detail: "Writing the page",
      observed_kind: "awaiting_approval",
      awaiting: true,
    }),
    "Approval needed in the terminal — Writing the page",
  );
  // Each part is in the voice of whoever said it.
  const voices = (activity) =>
    leafRow(state(activity)).parts.map((part) => [part.text, part.voice]);
  assert.deepEqual(voices({ kind: "working", detail: "recording the demo" }), [
    ["recording the demo", "agent"],
  ]);
  assert.deepEqual(
    voices({ kind: "stalled", detail: "revising", ts: minutesAgo(20) }),
    [
      ["Last checked in 20m ago", "leaf"],
      [" — ", "leaf"],
      ["revising", "agent"],
    ],
  );
  assert.equal(row({ kind: "listening", detail: "" }), "Ready");
  assert.equal(
    row({ kind: "listening", detail: "", counts: { pending: 1 } }),
    "Ready · 1 response owed on updates awaiting delivery",
  );
  assert.equal(
    row({ kind: "stalled", detail: "revising", ts: minutesAgo(20) }),
    "Last checked in 20m ago — revising",
  );
  assert.equal(
    row({ kind: "stalled", detail: "", ts: minutesAgo(5), dropped: true }),
    "Stopped 5m ago",
  );
  assert.equal(row({ kind: "away" }), "Away");
  assert.equal(
    row({ kind: "away", dropped: true, ts: minutesAgo(5), counts: { overdue: 1 } }),
    "Stopped 5m ago",
  );
  assert.equal(row({ kind: "unheld" }), "Not on this page right now");
  assert.equal(row({ kind: "closed" }), "Done with this page");
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
