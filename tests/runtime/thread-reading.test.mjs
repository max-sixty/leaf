import assert from "node:assert/strict";
import { mock } from "node:test";
import test from "node:test";
import process from "node:process";
import { servedReading, servedThread, servedWorkflow } from "../served.mjs";

// Recent's day names are formatted in the zone the page loads in, so the zone — one with
// a daylight-saving change — is fixed before the modules load rather than by a static
// import that would load them first.
process.env.TZ = "America/New_York";
const { moved, readThreadRecords, threadSummary } =
  await import("/runtime/thread/model.js");
const { inRecentOrder } = await import("/runtime/thread/placement.js");
const { unreadBoundaries } = await import("/runtime/thread/summary-ranges.js");
const { threadAttention } = await import("/runtime/thread/workflow.js");
const {
  DEFAULT_INTENT,
  createThreadNarrowing,
  narrowingReading,
  threadSearchReading,
  transition,
} = await import("/runtime/thread/narrowing.js");
const { createThreadPanelElements } = await import("/runtime/thread/panel-elements.js");
const { createThreadListController } = await import("/runtime/thread/thread-list.js");
const { createThreadDestinations } = await import("/runtime/thread/destination.js");
const { retainUserIntent } = await import("/runtime/user-intent.js");
const { createThreadPanelController } = await import("/runtime/thread-panel.js");

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
  const arrivals = [];
  const destinations = createThreadDestinations({
    threadIdsAt: () => [],
    placedAt: (id) => (id === thread.dataset.thread ? { place: owner } : null),
    panelIsOpen: () => false,
    showThread: async (id, options) => {
      arrivals.push({ id, options });
      return control;
    },
  });
  control.focus();
  assert.equal(destinations.threadHere(), thread);
  assert.equal(destinations.threadAtStanding(), thread.dataset.thread);
  assert.equal(destinations.threadTarget(thread.dataset.thread), owner);
  assert.equal(destinations.threadTarget("detached"), null);
  assert.equal(destinations.threadFocusTarget(thread.dataset.thread), null);
  const intent = retainUserIntent();
  assert.equal(await destinations.openPageThread("detached", { intent }), control);
  assert.equal(arrivals[0].id, "detached");
  assert.equal(arrivals[0].options.intent, intent);
  assert.equal(arrivals[0].options.part, "reply");
  assert.equal(arrivals[0].options.focus, true);
  window.dispatchEvent(new Event("input"));
  assert.equal(await destinations.openPageThread("detached", { intent }), null);
  assert.equal(arrivals.length, 1);
  owner.remove();
});

test("two Thread panels own separate controls and list state", () => {
  const first = createThreadPanelElements({ id: "test-threads-first" });
  const second = createThreadPanelElements({ id: "test-threads-second" });
  const firstList = createThreadListController(first);
  const secondList = createThreadListController(second);
  const card = document.createElement("div");
  card.className = "lf-thread";
  card.dataset.id = "thread-a";
  first.threadsBox.append(card);
  first.findInput.value = "different filter";
  first.threadsBox.scrollTop = 72;

  assert.deepEqual(firstList.openThreadsInPageOrder(), [card]);
  assert.deepEqual(secondList.openThreadsInPageOrder(), []);
  assert.notEqual(second.findInput.value, first.findInput.value);
  assert.equal(second.threadsBox.scrollTop, 0);
  assert.notEqual(first.panel, second.panel);
  first.dispose();
  second.dispose();
});

test("two mounted panel controllers keep independent visibility and keyboard rungs", () => {
  const first = createThreadPanelElements({ id: "test-panel-first" });
  const second = createThreadPanelElements({ id: "test-panel-second" });
  const registered = new Map();
  let selected = null;
  const auxiliarySurfaces = {
    registerAuxiliarySurface: ({ key, ...surface }) => {
      registered.set(key, surface);
      return () => registered.delete(key);
    },
    selectedSurface: () => registered.get(selected)?.surface ?? null,
    select: (key) => {
      registered.get(selected)?.hide();
      selected = key;
      registered.get(key)?.show({ phase: "gesture" });
    },
  };
  const make = (elements, key) =>
    createThreadPanelController({
      key,
      auxiliarySurfaces,
      elements: { ...elements, toggleBtn: document.createElement("button") },
      narrowing: { narrowed: () => false, threadSearchActive: () => false },
      threadAtStanding: () => null,
      showThread: () => {},
      refreshThread: () => {},
      closeReactionMode: () => {},
      closePreview: () => {},
    });
  const firstController = make(first, "test-first");
  const secondController = make(second, "test-second");
  firstController.setPanel(true);
  assert.equal(firstController.panelIsOpen(), true);
  assert.equal(secondController.panelIsOpen(), false);
  secondController.setPanel(true);
  assert.equal(firstController.panelIsOpen(), false);
  assert.equal(secondController.panelIsOpen(), true);
  firstController.dispose();
  secondController.dispose();
  first.dispose();
  second.dispose();
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
    readThreadRecords(threads, NO_DOCUMENT, new Map(), [], acknowledging)[0];

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
  assert.equal(threadSummary(thread).latest, "2026-03-02T09:00:00Z");
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
    attention: { kind: "needs_user", reason: "ask", workflow: null },
    user_prompt: { message: "question", version: "question" },
  });
  const [thread] = readThreadRecords([source], NO_DOCUMENT, new Map(), []);
  const attention = threadAttention(thread);
  assert.equal(attention.label, "My turn to answer");
  assert.equal(
    threadAttention({ ...thread, user_prompt: null }).label,
    "My turn to answer",
  );
  assert.equal(
    threadAttention({
      ...thread,
      attention: { kind: "needs_user", reason: "resend", workflow: "send" },
      workflows: [
        servedWorkflow({
          id: "send",
          subject: { kind: "thread", id: "question" },
          thread: "question",
        }),
      ],
    }).label,
    "My turn to resend",
  );
  assert.equal(
    threadAttention({
      ...thread,
      attention: { kind: "needs_user", reason: "resend", workflow: "move" },
      workflows: [
        servedWorkflow({
          id: "move",
          subject: { kind: "widget", id: "choice" },
          thread: "question",
        }),
      ],
    }).label,
    "My turn to retry",
  );
  assert.equal(
    threadAttention({
      ...thread,
      attention: { kind: "waiting", reason: "uncertain", workflow: null },
    }).label,
    "Uncertain",
  );
  assert.equal(
    threadAttention({
      ...thread,
      attention: { kind: "waiting", reason: "workflow", workflow: null },
    }).label,
    "Waiting",
  );
  assert.equal(threadAttention({ ...thread, attention: null }), null);
});

const recentThread = (id, ts, edited = null) => {
  const root = { ...agent(id, { ts, ...(edited && { edited }) }), body: { text: id } };
  return { id, root, msgs: [root] };
};

test("Recent orders threads by their last move, an edit counting as one", () => {
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
      order.map((thread) => thread.id),
      ["old", "late", "sunday", "saturday"],
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
  // A thread the agent has started a move in: the card says Working, so the agent
  // filter lists it.
  const claimed = { kind: "waiting", reason: "workflow", workflow: "working" };
  const threads = [
    { ...recentThread("asks", "2026-03-01T00:00:00Z"), attention: onUser },
    { ...recentThread("working", "2026-03-01T00:00:00Z"), attention: claimed },
    {
      ...recentThread("closed", "2026-03-01T00:00:00Z"),
      resolved: { author: "user" },
    },
  ];
  const places = new Map(
    threads.map((thread) => [thread, { gone: false, section: "" }]),
  );
  const model = narrowingReading(DEFAULT_INTENT, threads, places);
  assert.deepEqual(
    model.shown.map((thread) => thread.id),
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
  const incomplete = narrowingReading(DEFAULT_INTENT, threads, places, false);
  assert.deepEqual(incomplete.shown, model.shown);
  assert.equal(incomplete.presentation.summary, "");
  assert.equal(incomplete.presentation.userAvailable, false);
  for (const group of incomplete.presentation.groups)
    for (const choice of group.choices) assert.equal(choice.amount, null);
});

test("a fold without prose is searchable by its visible label", () => {
  const thread = {
    ...recentThread("progress", "2026-03-01T00:00:00Z"),
    summaries: [{ id: "fold", label: "Previous progress messages", text: "" }],
  };
  const places = new Map([[thread, { gone: false, section: "" }]]);
  const reading = narrowingReading(
    { ...DEFAULT_INTENT, finding: "previous progress messages" },
    [thread],
    places,
  );
  assert.deepEqual(
    reading.shown.map(({ id }) => id),
    ["progress"],
  );
  assert.deepEqual(
    threadSearchReading(thread, "previous progress messages").messages,
    [],
  );
});

test("a pending narrowing reset gives way to a newer reading gesture", async () => {
  const view = {
    configure(controls) {
      this.controls = controls;
    },
  };
  const listRoot = document.createElement("div");
  document.body.append(listRoot);
  let finish;
  const presented = new Promise((resolve) => (finish = resolve));
  const narrowing = createThreadNarrowing({
    view,
    listRoot,
    readThreads: () => [],
    ready: () => true,
    repaint: () => presented,
  });
  narrowing.mount();
  const pending = view.controls.chooseFacet("status", "resolved");

  globalThis.dispatchEvent(new Event("wheel"));
  listRoot.scrollTop = 230;
  finish();
  await pending;

  assert.equal(listRoot.scrollTop, 230);
  listRoot.remove();
});

test("panel narrowing controllers keep independent intent over shared threads", async () => {
  const open = { ...recentThread("open", "2026-03-01T00:00:00Z"), resolved: null };
  const resolved = {
    ...recentThread("resolved", "2026-03-01T00:00:00Z"),
    resolved: { author: "user" },
  };
  const threads = [open, resolved];
  const places = new Map(
    threads.map((thread) => [thread, { gone: false, section: "Section" }]),
  );
  const makePanel = () => {
    const view = {
      configure(controls) {
        this.controls = controls;
      },
      setSearchWords(words) {
        this.words = words;
      },
    };
    const listRoot = { scrollTop: 10 };
    const narrowing = createThreadNarrowing({
      view,
      listRoot,
      readThreads: () => threads,
      ready: () => true,
      repaint: () => Promise.resolve(),
    });
    narrowing.mount();
    return { narrowing, view, listRoot };
  };
  const first = makePanel();
  const second = makePanel();

  await first.view.controls.chooseFacet("status", "resolved");
  assert.deepEqual(first.narrowing.model(threads, places).shown, [resolved]);
  assert.deepEqual(second.narrowing.model(threads, places).shown, [open]);
  assert.equal(first.listRoot.scrollTop, 0);
  assert.equal(second.listRoot.scrollTop, 10);

  // Revealing a destination already in this view keeps the intent that retained
  // arrivals use to distinguish repainting from a deliberate change of view.
  const kept = second.narrowing.model(threads, places).intent;
  await second.narrowing.revealThread("open");
  assert.equal(second.narrowing.model(threads, places).intent, kept);
  assert.equal(second.narrowing.widen(), false);
  assert.equal(second.narrowing.model(threads, places).intent, kept);

  await second.narrowing.revealThread("resolved");
  assert.notEqual(second.narrowing.model(threads, places).intent, kept);
  assert.deepEqual(second.narrowing.model(threads, places).shown, [resolved]);
  first.narrowing.widen();
  assert.deepEqual(first.narrowing.model(threads, places).shown, [open]);
  assert.deepEqual(second.narrowing.model(threads, places).shown, [resolved]);
  // An empty normalized search can still carry raw editing to clear on Reset.
  first.view.controls.changeWords(" ");
  assert.equal(first.narrowing.widen(), true);
  assert.equal(first.view.words, "");
});

test("a deferred direct Thread landing reports cancellation after newer user focus", async (t) => {
  t.after(() => window.happyDOM.cancelAsync());
  const { createThreadLanding } = await import("/runtime/thread/landing.js");
  const list = document.createElement("section");
  const thread = document.createElement("section");
  thread.className = "lf-thread";
  thread.dataset.id = "held-direct-arrival";
  thread.hidden = true;
  list.append(thread);
  list.keepsForWords = () => false;
  list.revealNavigation = () => {};
  const source = document.createElement("button");
  const newer = document.createElement("button");
  document.body.append(list, source, newer);
  const held = Promise.withResolvers();
  let reveals = 0;
  const landing = createThreadLanding({
    setPanel() {},
    threadsBox: list,
    revealThread: () => {
      reveals++;
      return held.promise.then(() => {
        thread.hidden = false;
      });
    },
  });
  try {
    source.focus();
    const arriving = landing.showThread(thread.dataset.id);
    assert.equal(reveals, 1);
    newer.focus();
    held.resolve();
    assert.equal(await arriving, null);
    assert.equal(document.activeElement, newer);
    assert.equal(thread.classList.contains("flash"), false);
  } finally {
    held.resolve();
    list.remove();
    source.remove();
    newer.remove();
  }
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
      const router = createThreadDestinations({
        panelIsOpen: () => true,
        showThread: () => null,
      });
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
