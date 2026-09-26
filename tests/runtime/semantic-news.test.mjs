import assert from "node:assert/strict";
import test from "node:test";

import {
  combineSemanticNews,
  currentSemanticNews,
  observeSemanticNews,
  semanticNewsNotice,
  semanticNewsReading,
} from "/runtime/semantic-news.js";

// `unread: false` leaves a message out of its thread's server `unread` reading: read
// already, or not agent content at all (a reaction, a reply still streaming).
const message = (id, extra = {}) => ({
  id,
  seq: 1,
  author: "agent",
  kind: "reply",
  ...extra,
});
const thread = (id, msgs, attention = null, userPrompt = null) => ({
  root: { id },
  msgs,
  attention,
  user_prompt: userPrompt,
  unread: msgs
    .filter((item) => item.unread !== false)
    .map((item) => ({ message: item.id, version: item.edited?.id ?? item.id })),
});
const ask = (id, thread = null) => ({ id, thread });
const activity = (kind = "away", extra = {}) => ({
  kind,
  held: true,
  reply: null,
  ...extra,
});
const reading = ({
  threads = [],
  pageAsks = [],
  threadAsks = [],
  requestOutcomes = [],
  workflows = [],
  pageActivity = activity(),
} = {}) => ({
  page: { asks: { user: pageAsks } },
  thread: {
    threads,
    asks: { user: threadAsks },
  },
  workflows,
  activity: pageActivity,
  requestOutcomes,
});
const kinds = (result) => result.news.map((item) => item.kind);
const responseFailure = (source, kind = "failed") => ({
  condition: { kind, operation: "response" },
  response: source,
  input: "input",
  subject: { kind: "thread", id: "t" },
  seq: 3,
});

test("accepted messages and user obligations arrive together after a quiet baseline", () => {
  const old = reading({
    threads: [thread("t", [message("old", { unread: false })])],
    pageAsks: [ask("existing")],
  });
  const baseline = observeSemanticNews(null, old);
  assert.deepEqual(baseline.news, []);
  assert.deepEqual(observeSemanticNews(baseline.observed, old).news, []);

  const next = reading({
    threads: [
      thread(
        "t",
        [message("old", { unread: false }), message("new", { seq: 2, awaits: true })],
        { kind: "needs_user", reason: "ask" },
        { message: "new", version: "new" },
      ),
    ],
    pageAsks: [ask("existing"), ask("new-page")],
  });
  const arrived = observeSemanticNews(baseline.observed, next);
  assert.deepEqual(kinds(arrived), [
    "agent_content",
    "user_obligation",
    "user_obligation",
  ]);
  assert.deepEqual(
    arrived.news.map((item) => item.key),
    [
      "content:new",
      'obligation:["page","new-page"]:1',
      'obligation:["thread-turn","t","new"]:1',
    ],
  );
  assert.deepEqual(observeSemanticNews(arrived.observed, next).news, []);
});

test("structural asks own their thread obligation and reopening starts a new episode", () => {
  const baseline = observeSemanticNews(null, reading());
  const owed = reading({
    threads: [
      thread("t", [message("question")], {
        kind: "needs_user",
        reason: "ask",
      }),
    ],
    threadAsks: [ask("choice", "t")],
  });
  const first = observeSemanticNews(baseline.observed, owed);
  assert.deepEqual(
    first.news.map((item) => item.key),
    ["content:question", 'obligation:["thread","t","choice"]:1'],
  );
  const answered = observeSemanticNews(
    first.observed,
    reading({
      threads: [thread("t", [message("question")])],
    }),
  );
  assert.deepEqual(answered.news, []);
  const reopened = observeSemanticNews(answered.observed, owed);
  assert.deepEqual(
    reopened.news.map((item) => item.key),
    ['obligation:["thread","t","choice"]:2'],
  );
});

test("a second question in the same waiting thread has its own source version", () => {
  const firstQuestion = reading({
    threads: [
      thread(
        "t",
        [message("first", { awaits: true })],
        { kind: "needs_user", reason: "ask" },
        { message: "first", version: "first" },
      ),
    ],
  });
  const baseline = observeSemanticNews(null, firstQuestion);
  const next = observeSemanticNews(
    baseline.observed,
    reading({
      threads: [
        thread(
          "t",
          [
            message("first", { awaits: true }),
            message("second", { seq: 2, awaits: true }),
          ],
          { kind: "needs_user", reason: "ask" },
          { message: "second", version: "second" },
        ),
      ],
    }),
  );
  assert.deepEqual(
    next.news.map((item) => item.key),
    ["content:second", 'obligation:["thread-turn","t","second"]:1'],
  );
});

test("current content versions and admitted messages determine arrivals", () => {
  const baseline = observeSemanticNews(
    null,
    reading({ threads: [thread("t", [message("original")])] }),
  );
  const changed = observeSemanticNews(
    baseline.observed,
    reading({
      threads: [
        thread("t", [
          message("original", { edited: { id: "last-edit", seq: 5 } }),
          message("stream", {
            addressable: false,
            attempt: "pending",
            unread: false,
          }),
          message("reaction", { token: "agree", unread: false }),
          message("failed-reply", { failure: "turn_failed" }),
        ]),
      ],
      workflows: [responseFailure({ id: "failed-reply" })],
    }),
  );
  assert.deepEqual(kinds(changed), ["agent_content", "response_failure"]);
  assert.equal(changed.news[0].key, "content:last-edit");
  assert.equal(changed.news[1].key, "response:failed-reply");
  const same = observeSemanticNews(
    changed.observed,
    reading({
      threads: [
        thread("t", [message("original", { edited: { id: "last-edit", seq: 5 } })]),
      ],
    }),
  );
  assert.deepEqual(same.news, []);
});

test("every canonical receipt survives one read and failed requests reopen asks", () => {
  const baseline = observeSemanticNews(null, reading());
  const receipt = (id, requestId, seq, status) => ({
    id,
    request: requestId,
    seq,
    status,
  });
  const outcome = (request, result) => ({
    request,
    widget: "approval",
    receipt: result,
  });
  const first = outcome("first", receipt("failed", "first", 3, "failed"));
  const second = outcome("second", receipt("succeeded", "second", 5, "succeeded"));
  const complete = observeSemanticNews(
    baseline.observed,
    reading({ requestOutcomes: [first, second] }),
  );
  assert.deepEqual(
    complete.news.map((item) => item.key),
    ["request:failed", "request:succeeded"],
  );
  const reopened = observeSemanticNews(
    complete.observed,
    reading({
      requestOutcomes: [
        first,
        second,
        outcome("third", receipt("failed-again", "third", 7, "failed")),
      ],
      pageAsks: [ask("approval")],
    }),
  );
  assert.deepEqual(kinds(reopened), ["request_outcome", "user_obligation"]);
  assert.equal(reopened.news[0].receipt.id, "failed-again");
});

test("response failures have exact episodes and recovery needs an accepted answer", () => {
  const baseline = observeSemanticNews(null, reading());
  const stale = observeSemanticNews(
    baseline.observed,
    reading({
      workflows: [responseFailure({ attempt: "attempt" }, "stale")],
    }),
  );
  assert.deepEqual(stale.news, []);
  const failed = observeSemanticNews(
    stale.observed,
    reading({
      pageActivity: activity("working", {
        reply: { attempt: "attempt", state: "interrupted", responds: "input" },
      }),
      workflows: [responseFailure({ attempt: "attempt" }, "interrupted")],
    }),
  );
  assert.deepEqual(kinds(failed), ["response_failure", "agent_available"]);
  assert.equal(failed.news[0].key, "response:attempt");
  const retrying = observeSemanticNews(
    failed.observed,
    reading({
      pageActivity: activity("working", {
        reply: { attempt: "attempt", state: "active", responds: "input" },
      }),
      workflows: [],
    }),
  );
  assert.deepEqual(retrying.news, []);
  const recovered = observeSemanticNews(
    retrying.observed,
    reading({
      threads: [thread("t", [message("answered", { responds: "input", seq: 4 })])],
      pageActivity: activity("working"),
    }),
  );
  assert.deepEqual(kinds(recovered), ["agent_content"]);
});

test("a settled failure before one read cannot announce a stale failure", () => {
  const baseline = observeSemanticNews(null, reading());
  const settled = observeSemanticNews(
    baseline.observed,
    reading({
      threads: [
        thread("t", [
          message("failed", { responds: "input", seq: 2, failure: "turn_failed" }),
          message("answer", { responds: "input", seq: 4 }),
        ]),
      ],
      workflows: [],
    }),
  );
  assert.deepEqual(
    settled.news.map((item) => item.key),
    ["content:answer"],
  );
});

test("agent availability is an episode, not a work-stage notice", () => {
  const baseline = observeSemanticNews(null, reading());
  const available = observeSemanticNews(
    baseline.observed,
    reading({
      pageActivity: activity("listening"),
    }),
  );
  assert.deepEqual(kinds(available), ["agent_available"]);
  assert.deepEqual(
    observeSemanticNews(
      available.observed,
      reading({
        pageActivity: activity("working"),
      }),
    ).news,
    [],
  );
  const stalled = observeSemanticNews(
    available.observed,
    reading({
      pageActivity: activity("stalled"),
    }),
  );
  assert.deepEqual(stalled.news, []);
  const restored = observeSemanticNews(
    stalled.observed,
    reading({
      pageActivity: activity("working"),
    }),
  );
  assert.deepEqual(
    restored.news.map((item) => item.key),
    ["agent-available:2"],
  );
});

test("page obligations come from the shown revision, not a waiting activation", () => {
  const shown = reading({ pageAsks: [ask("shown")] });
  const waiting = reading({ pageAsks: [ask("waiting")] });
  const selected = semanticNewsReading({
    effective: { view: { document: shown.page } },
    authoritative: {
      active: { revision: 2 },
      browser: {
        views: { 1: { document: shown.page }, 2: { document: waiting.page } },
        thread: shown.thread,
        request_outcomes: [],
      },
      workflows: [],
      activity: shown.activity,
    },
  });
  assert.deepEqual([...selected.page.asks.user], [ask("shown")]);
});

test("one producer notice states a reply and new obligation as separate facts", () => {
  const baseline = observeSemanticNews(null, reading());
  const current = reading({
    threads: [
      thread(
        "t",
        [message("answer", { agent: "Sam", awaits: true })],
        { kind: "needs_user", reason: "ask" },
        { message: "answer", version: "answer" },
      ),
    ],
  });
  const result = observeSemanticNews(baseline.observed, current);
  assert.equal(
    semanticNewsNotice(currentSemanticNews(result.news, current, result.observed)),
    "Sam replied; Input needed",
  );
  assert.deepEqual(combineSemanticNews(result.news, result.news), result.news);
});

test("deferred news drops superseded failures and edits but keeps historical receipts", () => {
  const baseline = observeSemanticNews(null, reading());
  const failedReading = reading({
    threads: [thread("t", [message("answer", { edited: { id: "edit-a", seq: 2 } })])],
    workflows: [responseFailure({ attempt: "attempt" })],
    requestOutcomes: [
      {
        request: "req",
        widget: "control",
        receipt: { id: "receipt", status: "failed" },
      },
    ],
  });
  const failed = observeSemanticNews(baseline.observed, failedReading);
  const answeredReading = reading({
    threads: [
      thread("t", [
        message("answer", { edited: { id: "edit-b", seq: 3 } }),
        message("recovered", { seq: 4 }),
      ]),
    ],
    requestOutcomes: failedReading.requestOutcomes,
  });
  const answered = observeSemanticNews(failed.observed, answeredReading);
  const queued = combineSemanticNews(failed.news, answered.news);
  const current = currentSemanticNews(queued, answeredReading, answered.observed);
  assert.deepEqual(
    current.map((item) => item.key),
    ["request:receipt", "content:edit-b", "content:recovered"],
  );
  assert.equal(semanticNewsNotice(current), "2 replies in 1 thread; Request failed");
});

test("deferred failure wording follows its current condition and stale availability disappears", () => {
  const baseline = observeSemanticNews(null, reading());
  const interrupted = observeSemanticNews(
    baseline.observed,
    reading({
      workflows: [responseFailure({ attempt: "attempt" }, "interrupted")],
      pageActivity: activity("working"),
    }),
  );
  const latest = reading({
    workflows: [responseFailure({ attempt: "attempt" }, "failed")],
    pageActivity: activity("away"),
  });
  assert.equal(
    semanticNewsNotice(
      currentSemanticNews(interrupted.news, latest, interrupted.observed),
    ),
    "Response failed",
  );
  assert.deepEqual(
    currentSemanticNews(interrupted.news, reading(), interrupted.observed),
    [],
  );
});

test("agent content is news while it is unread, including on the first reading", () => {
  const waiting = reading({
    threads: [
      thread("t", [
        message("away", { seq: 1 }),
        message("seen", { seq: 2, unread: false }),
      ]),
    ],
  });
  const opened = observeSemanticNews(null, waiting);
  assert.deepEqual(
    opened.news.map((item) => item.key),
    ["content:away"],
  );
  assert.equal(
    semanticNewsNotice(currentSemanticNews(opened.news, waiting, opened.observed)),
    "Agent replied",
  );
  // Taken in before the notice could show — here, or in another tab — it drops out.
  const taken = reading({
    threads: [
      thread("t", [
        message("away", { seq: 1, unread: false }),
        message("seen", { seq: 2, unread: false }),
      ]),
    ],
  });
  assert.deepEqual(currentSemanticNews(opened.news, taken, opened.observed), []);
  // A reply another tab already read arrives read, and is no news here.
  const later = observeSemanticNews(
    opened.observed,
    reading({
      threads: [
        thread("t", [
          message("away", { seq: 1, unread: false }),
          message("elsewhere", { seq: 3, unread: false }),
        ]),
      ],
    }),
  );
  assert.deepEqual(later.news, []);
});

test("news is ordered by when each message last moved", () => {
  const result = observeSemanticNews(
    null,
    reading({
      threads: [
        thread("a", [message("edited", { seq: 1, edited: { id: "e", seq: 9 } })]),
        thread("b", [message("plain", { seq: 5 })]),
      ],
    }),
  );
  assert.deepEqual(
    result.news.map((item) => item.key),
    ["content:plain", "content:e"],
  );
});
