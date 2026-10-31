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
  text: `Words of ${id}.`,
  // The served content version: its latest rewrite's id, else its own.
  content_version: extra.edited?.id ?? id,
  ...extra,
});
// A notice's parts as the live region hears them.
const words = (parts) => parts.map((part) => part.text).join("");
const said = (news) => words(semanticNewsNotice(news));
const thread = (id, msgs, attention = null) =>
  servedThread(
    msgs.map(({ unread: _unread, ...served }) => served),
    {
      id,
      attention,
      unread: msgs
        .filter((item) => item.unread !== false)
        .map((item) => ({ message: item.id, version: item.content_version })),
    },
  );
const item = (id, thread = null) => ({
  id,
  thread,
  message: thread,
  source: { kind: "widget", id },
  next_actor: "user",
});
// A question asked in words: the agent's message `id` carrying `obligation`.
const replyObligation = (id) => ({
  id,
  thread: "t",
  message: id,
  source: { kind: "message", id },
  next_actor: "user",
});
const reading = ({
  threads = [],
  pageObligations = [],
  threadObligations = [],
  workflows = [],
} = {}) => ({
  obligations: [...pageObligations, ...threadObligations],
  thread: { threads },
  workflows,
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
    obligation: "update:input",
    stage: "answered",
    condition: { kind, operation: "response" },
    response: source,
  });

test("accepted messages and user obligations arrive together after a quiet baseline", () => {
  const old = reading({
    threads: [thread("t", [message("old", { unread: false })])],
    pageObligations: [item("existing")],
  });
  const baseline = observeSemanticNews(null, old);
  assert.deepEqual(baseline.news, []);
  assert.deepEqual(observeSemanticNews(baseline.observed, old).news, []);

  const next = reading({
    threads: [
      thread("t", [message("old", { unread: false }), message("new", { seq: 2 })], {
        kind: "needs_user",
        reason: "obligation",
      }),
    ],
    pageObligations: [item("existing"), item("new")],
    threadObligations: [replyObligation("new")],
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

test("structural questions own their thread obligation and reopening starts a new episode", () => {
  const baseline = observeSemanticNews(null, reading());
  const owed = reading({
    threads: [
      thread("t", [message("question")], { kind: "needs_user", reason: "obligation" }),
    ],
    pageObligations: [item("other")],
    threadObligations: [item("choice", "t")],
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
      pageObligations: [item("other")],
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
  assert.equal(said(reopened.news), "New on me");
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
  assert.equal(said(current), "2 new on me");
  assert.deepEqual(combineSemanticNews(reopened.news, reopened.news), reopened.news);
  assert.deepEqual(observeSemanticNews(reopened.observed, owed).news, []);
});

test("a second question in the same waiting thread has its own source version", () => {
  const firstQuestion = reading({
    threadObligations: [replyObligation("first")],
    threads: [
      thread("t", [message("first")], { kind: "needs_user", reason: "obligation" }),
    ],
  });
  const baseline = observeSemanticNews(null, firstQuestion);
  const next = observeSemanticNews(
    baseline.observed,
    reading({
      threadObligations: [replyObligation("second")],
      threads: [
        thread("t", [message("first"), message("second", { seq: 2 })], {
          kind: "needs_user",
          reason: "obligation",
        }),
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
    said(currentSemanticNews(changed.news, next, changed.observed)),
    "Edited: Words of original. · Not answered",
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

test("an update handed back to the user is news once, as its failed response", () => {
  const baseline = observeSemanticNews(null, reading());
  const handedBack = observeSemanticNews(
    baseline.observed,
    reading({
      threadObligations: [
        {
          id: "update:input",
          thread: "t",
          message: "input",
          source: { kind: "update", id: "input" },
          next_actor: "user",
        },
      ],
      workflows: [responseFailure({ id: "failure" })],
    }),
  );
  assert.deepEqual(kinds(handedBack), ["response_failure"]);
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
    workflows: [responseFailure({ attempt: "attempt" }, "interrupted")],
  });
  const failed = observeSemanticNews(stale.observed, interruptedReading);
  assert.deepEqual(kinds(failed), ["response_failure"]);
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
    }),
  );
  assert.deepEqual(kinds(anotherAttempt), ["response_failure"]);
  assert.equal(combineSemanticNews(failed.news, anotherAttempt.news).length, 2);
  const retrying = observeSemanticNews(
    anotherAttempt.observed,
    reading({
      workflows: [],
    }),
  );
  assert.deepEqual(retrying.news, []);
  const recovered = observeSemanticNews(
    retrying.observed,
    reading({
      threads: [thread("t", [message("answered", { responds: "input", seq: 4 })])],
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

test("page obligations come from the shown revision, not a waiting activation", () => {
  const shown = reading({ pageObligations: [item("shown")] });
  const waiting = reading({ pageObligations: [item("waiting")] });
  const selected = semanticNewsReading({
    effective: { view: { obligations: shown.obligations, thread: shown.thread } },
    authoritative: {
      active: { revision: 2 },
      browser: {
        views: {
          1: { obligations: shown.obligations, thread: shown.thread },
          2: { obligations: waiting.obligations, thread: waiting.thread },
        },
      },
      workflows: [],
    },
  });
  assert.deepEqual(selected.obligations, [item("shown")]);
});

test("a new message speaks for itself, with what it asks of the user", () => {
  const baseline = observeSemanticNews(null, reading());
  const current = reading({
    threadObligations: [replyObligation("answer")],
    threads: [
      thread(
        "t",
        [message("answer", { agent: "Sam", text: "Does this answer your question?" })],
        {
          kind: "needs_user",
          reason: "obligation",
        },
      ),
    ],
  });
  const result = observeSemanticNews(baseline.observed, current);
  assert.equal(
    said(currentSemanticNews(result.news, current, result.observed)),
    "Does this answer your question?",
  );
  assert.deepEqual(combineSemanticNews(result.news, result.news), result.news);
  // Something else new on the user's list is its own fact, counted by the list's name.
  const more = reading({
    pageObligations: [item("elsewhere")],
    threadObligations: [replyObligation("answer")],
    threads: current.thread.threads,
  });
  const both = observeSemanticNews(baseline.observed, more);
  assert.equal(
    said(currentSemanticNews(both.news, more, both.observed)),
    "Does this answer your question? · New on me",
  );
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
  assert.equal(said(current), "2 replies in 1 thread");
});

test("a notice sets apart only what Leaf read of the answer", () => {
  // The agent's words stand as it wrote them; what became of an answer is Leaf's
  // reading, in italic where the seat draws it; the list's name is the interface's.
  const parts = semanticNewsNotice([
    { kind: "agent_content", key: "content:m1", thread: "a", message: message("m1") },
    { kind: "response_failure", key: "failure:f1", condition: "failed" },
    { kind: "user_obligation", key: "obligation:o1", message: "another" },
  ]);
  assert.deepEqual(
    parts.map((part) => [part.text, part.voice]),
    [
      ["Words of m1.", "agent"],
      [" · ", null],
      ["Not answered", "leaf"],
      [" · ", null],
      ["New on me", null],
    ],
  );
  assert.deepEqual(semanticNewsNotice([]), []);
});

test("deferred failure wording follows its current condition and a cleared failure disappears", () => {
  const baseline = observeSemanticNews(null, reading());
  const interrupted = observeSemanticNews(
    baseline.observed,
    reading({
      workflows: [responseFailure({ attempt: "attempt" }, "interrupted")],
    }),
  );
  const latest = reading({
    workflows: [responseFailure({ attempt: "attempt" }, "failed")],
  });
  assert.equal(
    said(currentSemanticNews(interrupted.news, latest, interrupted.observed)),
    "Not answered",
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
    said(currentSemanticNews(opened.news, waiting, opened.observed)),
    "Words of away.",
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

test("held producer batches preserve interrupted news and merge later arrivals", async (t) => {
  const { notice, noticeReading, holdStatus, liveEl } =
    await import("/runtime/notifications.js");
  t.mock.timers.enable({ apis: ["setTimeout"] });
  t.after(() => window.happyDOM.cancelAsync());
  const announcements = [];
  let delivered;
  const observer = new MutationObserver(() => {
    const words = liveEl.textContent;
    if (!words) return;
    announcements.push(words);
    delivered?.resolve();
  });
  observer.observe(liveEl, { childList: true, subtree: true });
  t.after(() => observer.disconnect());
  const news = ["a", "b", "a", "b"].map((thread, index) => ({
    kind: "agent_content",
    key: `content:queued-${index}`,
    thread,
    version: `queued-${index}`,
    message: message(`queued-${index}`, { agent: "Codex" }),
  }));
  const announce = async (value) => {
    delivered = Promise.withResolvers();
    notice(semanticNewsNotice(value), {
      background: true,
      group: {
        key: "semantic-news",
        value,
        combine: combineSemanticNews,
        format: semanticNewsNotice,
      },
    });
    t.mock.timers.tick(30);
    await delivered.promise;
  };
  await announce(news.slice(0, 2));
  assert.equal(words(noticeReading().message), "2 replies in 2 threads");
  assert.equal(noticeReading().visible, true);
  holdStatus(10000);
  assert.equal(noticeReading().visible, false);
  for (const item of news.slice(2)) await announce([item]);
  assert.equal(noticeReading().visible, false);
  assert.deepEqual(announcements, [
    "2 replies in 2 threads",
    "Words of queued-2.",
    "Words of queued-3.",
  ]);
  const before = [...announcements];
  holdStatus(1);
  t.mock.timers.tick(1);
  assert.equal(words(noticeReading().message), "4 replies in 2 threads");
  assert.equal(noticeReading().visible, true);
  t.mock.timers.tick(30);
  await window.happyDOM.whenAsyncComplete();
  assert.deepEqual(
    announcements,
    before,
    "showing deferred news must not announce it again",
  );
});
