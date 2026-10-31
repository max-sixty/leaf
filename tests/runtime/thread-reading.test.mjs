import assert from "node:assert/strict";
import test from "node:test";
import { servedReading, servedThread, servedWorkflow } from "../served.mjs";

const { lastMovedAt, moved, readThreadRecords } =
  await import("/runtime/thread/model.js");
const { threadAttention } = await import("/runtime/thread/workflow.js");
const { threadName, threadSummary } = await import("/runtime/thread/messages.js");
const { loadMarkdown } = await import("/runtime/markdown.js");
const { createThreadDestinations } = await import("/runtime/thread/destination.js");

test("Thread destinations without a page preview retain canonical targets and shadow-held identity", async () => {
  const owner = document.createElement("div");
  const shadow = owner.attachShadow({ mode: "open" });
  const thread = document.createElement("section");
  thread.className = "lf-page-thread";
  thread.dataset.thread = "thread-without-preview";
  const control = document.createElement("button");
  thread.append(control);
  shadow.append(thread);
  document.body.append(owner);
  const destinations = createThreadDestinations({
    threadIdsAt: () => [],
    placedAt: (id) => (id === thread.dataset.thread ? { place: owner } : null),
  });
  control.focus();
  assert.equal(destinations.threadHere(), thread);
  assert.equal(destinations.threadAtCurrentLocation(), thread.dataset.thread);
  assert.equal(destinations.threadTarget(thread.dataset.thread), owner);
  assert.equal(destinations.threadTarget("detached"), null);
  assert.equal(destinations.threadFocusTarget(thread.dataset.thread), null);
  owner.remove();
});

const NO_DOCUMENT = { registry: {}, descriptors: new Map(), messageBodies: new Map() };

const agent = (id, extra = {}) => ({
  id,
  kind: "reply",
  author: "agent",
  text: id,
  seq: 1,
  ts: "2026-03-01T12:00:00Z",
  ...extra,
});
test("a thread's unread is the server reading less what this tab is acknowledging", () => {
  const root = agent("root", { kind: "comment" });
  const reply = agent("reply", { seq: 2, edited: { id: "edit", seq: 4, ts: "x" } });
  const threads = [
    servedThread([root, reply], {
      unread: [
        { message: "root", version: "root" },
        { message: "reply", version: "edit" },
      ],
    }),
  ];
  const read = (acknowledging) =>
    readThreadRecords(threads, NO_DOCUMENT, new Map(), [], [], [], acknowledging)[0];

  const unread = read([]);
  assert.deepEqual(
    unread.msgs.map((message) => message.unread),
    [true, true],
  );
  assert.equal(unread.unread.length, 2);

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
  assert.equal(lastMovedAt(thread), "2026-03-02T09:00:00Z");
});

test("an untitled thread goes by the words its opening renders, everywhere it is named", async () => {
  // Reached whenever a thread has no title yet, as after a failed title request. The
  // floating panel's row, the margin, Page Map, Questions and the activity feed all name it by
  // this one reading, so none shows the opening's Markdown source and another its words.
  assert.ok(await loadMarkdown());
  const named = (root, changes = {}) =>
    readThreadRecords([servedThread([root], changes)], NO_DOCUMENT, new Map(), [])[0];
  const user = (extra) =>
    agent("opening", { kind: "comment", author: "user", ...extra });
  const prose = named(user({ text: "Is **this** the\n\n`retry` path?" }));
  assert.equal(threadName(prose), "Is this the retry path?");
  assert.equal(threadSummary(prose).topic, threadName(prose));
  // A drawing with no words still has a name to stand under.
  assert.equal(
    threadName(named(user({ text: "", drawing: { strokes: [] } }))),
    "Drawing",
  );
  // The agent's title, once it has one, is the name.
  assert.equal(
    threadName(named(user({ text: "Is **this** it?" }), { title: "Retry path" })),
    "Retry path",
  );
});

test("attention names the outstanding question rather than the latest message", () => {
  const question = agent("question", {
    kind: "comment",
    text: "Does this crop show enough of the room?",
  });
  const followup = agent("followup", {
    text: "I also added the room number.",
    seq: 2,
  });
  const source = servedThread([question, followup], {
    attention: { kind: "needs_user", reason: "obligation", workflow: null },
  });
  const [thread] = readThreadRecords([source], NO_DOCUMENT, new Map(), []);
  const attention = threadAttention(thread, "Claude");
  assert.equal(attention.word.text, "Your turn");
  assert.equal(
    threadAttention(
      {
        ...thread,
        attention: { kind: "needs_user", reason: "resend", workflow: "send" },
        workflows: [
          servedWorkflow({
            id: "send",
            subject: { kind: "thread", id: "question" },
            thread: "question",
          }),
        ],
      },
      "Claude",
    ).word.text,
    "Send it again",
  );
  assert.equal(
    threadAttention(
      {
        ...thread,
        attention: { kind: "needs_user", reason: "resend", workflow: "move" },
        workflows: [
          servedWorkflow({
            id: "move",
            subject: { kind: "widget", id: "choice" },
            thread: "question",
          }),
        ],
      },
      "Claude",
    ).word.text,
    "Try it again",
  );
  assert.equal(
    threadAttention(
      {
        ...thread,
        attention: { kind: "waiting", reason: "uncertain", workflow: null },
      },
      "Claude",
    ).word.text,
    "Uncertain",
  );
  assert.equal(
    threadAttention(
      {
        ...thread,
        attention: { kind: "waiting", reason: "workflow", workflow: null },
      },
      "Claude",
    ).word.text,
    "Waiting",
  );
  assert.equal(threadAttention({ ...thread, attention: null }, "Claude"), null);
});

test("superseding a blocked primary destination completes its prior navigation", async () => {
  const { applicationState } = await import("/runtime/semantic-state.js");
  const { readThreads } = await import("/runtime/thread/state.js");
  applicationState.identify(1);
  applicationState.captureDocument({
    ...applicationState.read().document,
    registry: {},
    authored: new Map(),
    descriptors: new Map(),
  });
  applicationState.adopt(servedReading("suggestion closes a thread"));
  const id = readThreads().threads[0].id;
  assert.equal(
    await (async () => {
      const workspace = document.createElement("section");
      document.body.append(workspace);
      const reached = Promise.withResolvers();
      const blocked = Promise.withResolvers();
      const router = createThreadDestinations({});
      let calls = 0;
      const unregister = router.register(workspace, () => {}, {
        update: () =>
          ++calls === 1 ? (reached.resolve(), blocked.promise) : Promise.resolve(),
        destination: () => null,
      });
      const firstNavigation = router.openPageThread(id, { focus: false });
      await reached.promise;
      await router.openPageThread(id, { focus: false });
      const result = await firstNavigation;
      blocked.resolve();
      unregister();
      workspace.remove();
      return result === null;
    })(),
    true,
  );
});

test("a thread the primary declines and nothing on the page shows is asked of it again, last", async () => {
  // The page the test before admitted, whose reading holds one thread.
  const { readThreads } = await import("/runtime/thread/state.js");
  const id = readThreads().threads[0].id;
  const workspace = document.createElement("section");
  const view = document.createElement("div");
  workspace.append(view);
  document.body.append(workspace);
  const router = createThreadDestinations({
    threadIdsAt: () => [],
    placedAt: () => null,
  });
  // Declines until asked as the last resort, as the floating panel declines a thread
  // about a passage.
  const asked = [];
  const unregister = router.register(
    workspace,
    (_key, request) => {
      asked.push(request.last);
      return request.last ? undefined : false;
    },
    {
      update: () => Promise.resolve(),
      destination: () => view,
      ownsDestination: (node) => node === view,
    },
  );
  const landed = await router.openPageThread(id, { focus: false });
  unregister();
  workspace.remove();
  assert.deepEqual(asked, [false, true]);
  assert.equal(landed, view);
});

test("prepared thread readings consume only their own held-news release", async () => {
  const { HeldNews } = await import("/runtime/thread/held-news.js");
  for (const earlier of [false, true])
    assert.equal(
      await (async (earlier) => {
        const base = servedThread([
          {
            id: "opening",
            seq: 1,
            kind: "comment",
            author: "user",
            text: "old",
            body: { text: "old" },
          },
        ]);
        const reading = (text) => {
          const source = {
            ...base,
            msgs: base.msgs.map((message) => ({
              ...message,
              text,
              body: { ...message.body, text },
            })),
          };
          source.root = source.msgs[0];
          const descriptor = (source) => ({
            id: source.id,
            key: source.key,
            source,
            messages: source.msgs,
            resolved: source.resolved,
            summaries: source.summaries,
            reread: descriptor,
          });
          return { threads: [descriptor(source)] };
        };
        const owner = document.createElement("section");
        document.body.append(owner);
        const held = new HeldNews(
          owner,
          () => ({ node: owner, newsMoves: () => true }),
          () => {},
        );
        const options = { row: false };
        held.hold(reading("old"), options);
        if (earlier) held.release();
        const pending = held.prepare(reading("new"), options);
        held.release();
        pending.commit();
        const replacement = held.prepare(reading("new"), options);
        const opened = replacement.reading.threads[0].source.msgs[0].text === "new";
        replacement.commit();
        const next = held.prepare(reading("later"), options);
        const holdingAgain =
          next.reading.threads[0].source.msgs[0].text === "new" &&
          Boolean(next.reading.threads[0].news);
        held.dispose();
        owner.remove();
        return opened && holdingAgain;
      })(earlier),
      true,
    );
});

test("a transcript commits when drawn, and abandoned renders call nothing", async (t) => {
  const { createPrimaryReader } = await import("/runtime/thread/primary-reader.js");
  const { applicationState } = await import("/runtime/semantic-state.js");
  applicationState.identify(1);
  applicationState.adopt(servedReading("suggestion closes a thread"));
  await loadMarkdown();
  const owner = document.createElement("section");
  const outlet = document.createElement("div");
  owner.append(outlet);
  document.body.append(owner);
  const root = agent("commit-question", { kind: "comment", author: "user" });
  const collection = (text = null) => ({
    phase: "ready",
    threads: readThreadRecords(
      [
        servedThread([
          root,
          ...(text ? [agent("commit-answer", { seq: 2, text })] : []),
        ]),
      ],
      NO_DOCUMENT,
      new Map(),
      [],
      [],
      [],
      [],
    ),
  });
  let intent = "opening";
  let deferred = null;
  const drawn = [];
  const reader = createPrimaryReader(
    owner,
    (reading, parts) => {
      const captured = intent;
      parts.transcript(reading.threads[0].key, outlet, {
        drawn: (answer) => drawn.push({ captured, answer, text: outlet.textContent }),
      });
      return deferred?.promise;
    },
    {
      reply: {},
      reaction: {},
      read: { observeMessage: () => () => {}, observeFeedback: () => () => {} },
    },
    () => Promise.resolve(),
    { answersAtOnce: true },
  );
  t.after(() => {
    reader.unregister();
    owner.remove();
  });
  const never = new Promise(() => {});
  await reader.prepare(collection(), never).paint();
  assert.equal(drawn.length, 1);
  assert.equal(drawn[0].answer, null);

  for (const abandoned of ["superseded", "cancelled"]) {
    intent = abandoned;
    const cancellation = Promise.withResolvers();
    deferred = Promise.withResolvers();
    const pending = reader.prepare(collection("Never drawn"), cancellation.promise);
    deferred = null;
    intent = "later navigation";
    const count = drawn.length;
    let accepted;
    if (abandoned === "superseded")
      accepted = reader.prepare(collection("Drawn answer"), never);
    else cancellation.resolve();
    assert.equal(await pending, null);
    assert.equal(drawn.length, count);
    accepted ??= reader.prepare(collection("Drawn answer"), never);
    const painted = accepted.paint();
    // The callback follows synchronous placement, before asynchronous preparation.
    assert.equal(drawn.at(-1).captured, "later navigation");
    assert.match(drawn.at(-1).text, /Drawn answer/);
    assert.deepEqual(drawn.at(-1).answer, {
      turn: collection().threads[0].msgs[0].key,
      reply: collection("Drawn answer").threads[0].msgs[1].key,
    });
    assert.equal(Object.isFrozen(drawn.at(-1).answer), true);
    await painted;
    await reader.prepare(collection(), never).paint();
  }
});

test("news answers only a user turn that still stands", async () => {
  const { threadChange } = await import("/runtime/thread/held-news.js");
  const root = { id: "question", key: "question", author: "user", body: "Question" };
  const turn = { id: "followup", key: "followup", author: "user", body: "And this?" };
  const reading = (messages, words) => ({
    messages,
    source: { msgs: messages },
    summaries: [],
    working: { words },
  });
  const before = reading([root, turn], "Working");
  assert.deepEqual(threadChange(before, reading([root, turn], "More work")).answers, {
    turn: "followup",
    reply: null,
  });
  // Undo removes the interjection while work on the original question continues.
  assert.equal(threadChange(before, reading([root], "More work")).answers, null);
});
