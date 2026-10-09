import assert from "node:assert/strict";
import test from "node:test";

import {
  combineSemanticNews,
  currentSemanticNews,
  observeSemanticNews,
  semanticNewsNotice,
  semanticNewsReading,
} from "/runtime/semantic-news.js";
import { servedThread, servedWorkflow } from "../served.mjs";

// `unread: false` leaves a message out of its thread's server `unread` reading: read
// already, or not agent content at all (a reaction, a reply still streaming). `agent`
// is the name the server serves an agent's message under.
const message = (id, extra = {}) => ({
  id,
  seq: 1,
  author: "agent",
  agent: "Agent",
  kind: "reply",
  ...extra,
});
const thread = (id, msgs, attention = null, userPrompt = null) =>
  servedThread(
    msgs.map(({ unread: _unread, ...served }) => served),
    {
      id,
      attention,
      user_prompt: userPrompt,
      unread: msgs
        .filter((item) => item.unread !== false)
        .map((item) => ({ message: item.id, version: item.edited?.id ?? item.id })),
    },
  );
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
});
const kinds = (result) => result.news.map((item) => item.kind);
const responseFailure = (source, kind = "failed") =>
  servedWorkflow({
    id: "input",
    input: "input",
    subject: { kind: "thread", id: "t" },
    thread: "t",
    coordinate: ["thread", "t"],
    seq: 3,
    answer: null,
    stage: "answered",
    condition: { kind, operation: "response" },
    next_actor: "user",
    response: source,
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
    pageAsks: [ask("existing"), ask("new")],
  });
  const arrived = observeSemanticNews(baseline.observed, next);
  // A reply and both scopes of obligation may share a source id. Combining notices
  // must preserve all three facts while removing repeated observations of them.
  assert.deepEqual(
    arrived.news.map((item) => [item.kind, item.thread, item.source ?? item.version]),
    [
      ["agent_content", "t", "new"],
      ["user_obligation", null, "new"],
      ["user_obligation", "t", "new"],
    ],
  );
  assert.deepEqual(combineSemanticNews(arrived.news, arrived.news), arrived.news);
  assert.deepEqual(observeSemanticNews(arrived.observed, next).news, []);
});

test("structural asks own their thread obligation and reopening starts a new episode", () => {
  const baseline = observeSemanticNews(null, reading());
  const owed = reading({
    threads: [
      thread(
        "t",
        [message("question")],
        { kind: "needs_user", reason: "ask" },
        { message: "question", version: "question" },
      ),
    ],
    pageAsks: [ask("other")],
    threadAsks: [ask("choice", "t")],
  });
  const first = observeSemanticNews(baseline.observed, owed);
  assert.deepEqual(
    first.news.map((item) => [item.kind, item.thread, item.source ?? item.version]),
    [
      ["agent_content", "t", "question"],
      ["user_obligation", null, "other"],
      ["user_obligation", "t", "choice"],
    ],
  );
  const answered = observeSemanticNews(
    first.observed,
    reading({
      threads: [thread("t", [message("question", { unread: false })])],
      pageAsks: [ask("other")],
    }),
  );
  assert.deepEqual(answered.news, []);
  const reopenedReading = structuredClone(owed);
  reopenedReading.thread.threads[0].unread = [];
  const reopened = observeSemanticNews(answered.observed, reopenedReading);
  assert.deepEqual(
    reopened.news.map(({ kind, thread, source }) => [kind, thread, source]),
    [["user_obligation", "t", "choice"]],
  );
  assert.equal(semanticNewsNotice(reopened.news), "Input needed");
  const queued = combineSemanticNews(first.news, reopened.news);
  assert.equal(queued.length, 4);
  const current = currentSemanticNews(queued, reopenedReading, reopened.observed);
  assert.deepEqual(
    current.map(({ kind, thread, source }) => [kind, thread, source]),
    [
      ["user_obligation", null, "other"],
      ["user_obligation", "t", "choice"],
    ],
  );
  assert.equal(semanticNewsNotice(current), "2 items need your input");
  assert.deepEqual(combineSemanticNews(reopened.news, reopened.news), reopened.news);
  assert.deepEqual(observeSemanticNews(reopened.observed, owed).news, []);
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
    next.news.map((item) => [item.kind, item.thread, item.source ?? item.version]),
    [
      ["agent_content", "t", "second"],
      ["user_obligation", "t", "second"],
    ],
  );
});

test("current content versions and admitted messages determine arrivals", () => {
  const baseline = observeSemanticNews(
    null,
    reading({ threads: [thread("t", [message("original")])] }),
  );
  const next = reading({
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
  });
  const changed = observeSemanticNews(baseline.observed, next);
  assert.deepEqual(kinds(changed), ["agent_content", "response_failure"]);
  assert.equal(changed.news[0].version, "last-edit");
  assert.equal(changed.news[0].message.id, "original");
  assert.equal(
    semanticNewsNotice(currentSemanticNews(changed.news, next, changed.observed)),
    "Agent updated a reply; Response failed",
  );
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

test("a failed answer to a move in a thread's markup is news about that thread", () => {
  const baseline = observeSemanticNews(null, reading());
  // The server stamps the thread the widget was frozen into.
  const move = {
    ...responseFailure({ attempt: "attempt" }),
    subject: { kind: "widget", id: "pick" },
    coordinate: ["pick", "pick", "choose"],
  };
  const failed = observeSemanticNews(baseline.observed, reading({ workflows: [move] }));
  assert.deepEqual(
    failed.news.map(({ kind, thread }) => [kind, thread]),
    [["response_failure", "t"]],
  );
});

test("a response failure announces once per attempt and retrying is not recovery", () => {
  const baseline = observeSemanticNews(null, reading());
  const stale = observeSemanticNews(
    baseline.observed,
    reading({
      workflows: [responseFailure({ attempt: "attempt" }, "stale")],
    }),
  );
  assert.deepEqual(stale.news, []);
  const interruptedReading = reading({
    pageActivity: activity("working", {
      reply: { attempt: "attempt", state: "interrupted", responds: "input" },
    }),
    workflows: [responseFailure({ attempt: "attempt" }, "interrupted")],
  });
  const failed = observeSemanticNews(stale.observed, interruptedReading);
  assert.deepEqual(kinds(failed), ["response_failure", "agent_available"]);
  assert.deepEqual(
    failed.news
      .filter(({ kind }) => kind === "response_failure")
      .map(({ input, thread, condition }) => [input, thread, condition]),
    [["input", "t", "interrupted"]],
  );
  assert.deepEqual(observeSemanticNews(failed.observed, interruptedReading).news, []);
  const anotherAttempt = observeSemanticNews(
    failed.observed,
    reading({
      workflows: [responseFailure({ attempt: "another-attempt" }, "interrupted")],
      pageActivity: activity("working"),
    }),
  );
  assert.deepEqual(kinds(anotherAttempt), ["response_failure"]);
  assert.equal(combineSemanticNews(failed.news, anotherAttempt.news).length, 3);
  const retrying = observeSemanticNews(
    anotherAttempt.observed,
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
    settled.news.map(({ kind, thread, version }) => [kind, thread, version]),
    [["agent_content", "t", "answer"]],
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
  assert.deepEqual(kinds(restored), ["agent_available"]);
  const queued = combineSemanticNews(available.news, restored.news);
  assert.equal(queued.length, 2);
  assert.deepEqual(
    currentSemanticNews(
      queued,
      reading({ pageActivity: activity("working") }),
      restored.observed,
    ),
    restored.news,
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

test("deferred news drops superseded failures and edits", () => {
  const baseline = observeSemanticNews(null, reading());
  const failedReading = reading({
    threads: [thread("t", [message("answer", { edited: { id: "edit-a", seq: 2 } })])],
    workflows: [responseFailure({ attempt: "attempt" })],
  });
  const failed = observeSemanticNews(baseline.observed, failedReading);
  const answeredReading = reading({
    threads: [
      thread("t", [
        message("answer", { edited: { id: "edit-b", seq: 3 } }),
        message("recovered", { seq: 4 }),
      ]),
    ],
  });
  const answered = observeSemanticNews(failed.observed, answeredReading);
  const queued = combineSemanticNews(failed.news, answered.news);
  const current = currentSemanticNews(queued, answeredReading, answered.observed);
  assert.deepEqual(
    current.map(({ kind, thread, version }) => [kind, thread, version]),
    [
      ["agent_content", "t", "edit-b"],
      ["agent_content", "t", "recovered"],
    ],
  );
  assert.equal(semanticNewsNotice(current), "2 replies in 1 thread");
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
    opened.news.map(({ kind, thread, version }) => [kind, thread, version]),
    [["agent_content", "t", "away"]],
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
    result.news.map(({ thread, message, version }) => [thread, message.id, version]),
    [
      ["b", "plain", "plain"],
      ["a", "edited", "e"],
    ],
  );
});
