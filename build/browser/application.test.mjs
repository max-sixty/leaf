import assert from "node:assert/strict";
import test from "node:test";
import { createSemanticApplication } from "./application.ts";
import { createPresentationCoordinator } from "./presentation.ts";
import {
  servedGestureSequence,
  servedAskItem,
  servedReading,
  servedThread,
  servedWorkflow,
} from "../../tests/served.mjs";

// An operation definition as composition stamps one into `$states`. The browser only
// compares definitions, so a fixture's need only differ where the operations do.
const definition = (tag, spec) => ({
  origin: tag,
  unit: spec.unit,
  record: spec.record ?? null,
  creates: spec.creates ?? null,
  detail: spec.detail ?? null,
});
// A registry with `$states` stamped from its declarations, each verb's writer as stated.
const stamped = (registry) => ({
  ...registry,
  $states: Object.fromEntries(
    Object.entries(registry)
      .filter(([tag]) => !tag.startsWith("$"))
      .map(([tag, entry]) => [
        tag,
        Object.fromEntries(
          Object.entries(entry["x-state"] ?? {}).map(([verb, verbSpec]) => [
            verb,
            { writer: verbSpec.writer, definition: definition(tag, verbSpec) },
          ]),
        ),
      ]),
  ),
});
const capturedDescriptor = (value) => ({
  ...value,
  states: stamped({ [value.tag]: value.declaration }).$states[value.tag],
});
const spec = {
  unit: "widget",
  detail: {
    type: "object",
    properties: { outcome: { enum: ["accept", "reject"] } },
    required: ["outcome"],
    additionalProperties: false,
  },
};
const descriptor = capturedDescriptor({
  id: "choice",
  tag: "lf-choice",
  document: { kind: "page", revision: 1 },
  declaration: { "x-state": { decide: { ...spec, writer: "user" } } },
  parent: null,
  ancestors: [],
  quoted: false,
});
const empty = () => ({ entries: [], actions: [], reports: [], desired: [] });
// The ask reading `served_state` sends, in its own wire spelling.
const noAsks = () => ({
  all: [],
  user: [],
  unanswered: [],
});
const wireAsk = (
  target,
  tag,
  source = target,
  sourceTag = tag,
  thread = null,
  message = thread,
) => ({
  id: `widget:${source}`,
  source: { kind: "widget", id: source, tag: sourceTag },
  thread,
  message,
  prompt: { text: null, target },
  answer: null,
  status: "open",
  next_actor: "user",
});
// A view's asks as the served lists hold them: each the user owes on Questions, and
// each that is no longer open, done.
const askQueues = (asks) => {
  const item = (ask) =>
    servedAskItem(ask, {
      subject: { kind: "widget", id: ask.source.id },
    });
  return {
    questions: asks.filter((ask) => ask.next_actor === "user").map(item),
    tasks: [],
    done: asks
      .filter((ask) => ask.status !== "open")
      .map((ask) => ({ ...item(ask), state: "done", ended: null, detail: null })),
  };
};
const coordinate = ["choice", "choice", "decide"];
const action = (attempt, outcome = "accept") => ({
  kind: "action",
  widget: "choice",
  action: "decide",
  detail: { outcome },
  revision: 1,
  attempt,
});
const state = (taken, events = []) => ({
  taken,
  layer: { generation: "test" },
  active: { revision: 1 },
  revision_labels: {},
  events,
  workflows: [],
  activity: { phase: "user", held: false },
  reading: `reading-${taken}`,
  browser: {
    basis: { through_seq: events.length },
    receipts: events,
    thread_memberships: {},
    todos: [],
    ended_todos: [],
    approval_history: [],
    views: {
      1: {
        basis: { revision: 1, through_seq: events.length },
        thread: { threads: [], projection: empty(), asks: noAsks() },
        coverage: [],
        undo: [],
        reports: [],
        published_at: null,
        queues: { questions: [], tasks: [], done: [] },
        approval_blocking: [],
        document: {
          asks: noAsks(),
          projection: {
            entries: events.map((event) => ({
              event: {
                ...event,
                meaning: {
                  ...event.meaning,
                  state: event.meaning?.state ?? definition("lf-choice", spec),
                },
              },
              coordinate: [event.widget, event.widget, event.action],
              spec,
              scope: "page",
              value: event.action,
              restated: [],
              absorbed: false,
              stands: true,
            })),
            actions: events.map((event) => event.id),
            reports: [],
            desired: events.slice(-1).map((event) => event.id),
          },
        },
      },
    },
  },
});
// A served workflow for one input to `thread`, its opening message unless named.
const threadWorkflow = (id, { thread = "root", input = thread, ...changes } = {}) =>
  servedWorkflow({
    id,
    input,
    message: input,
    subject: { kind: "thread", id: thread },
    thread,
    coordinate: ["thread", thread],
    answer: { kind: "reply", to: input, for: input },
    ...changes,
  });
const capture = (extraDescriptors = [], extraAuthored = []) => {
  const app = createSemanticApplication();
  app.identify(1);
  app.captureDocument({
    ...app.read().document,
    registry: stamped(
      Object.fromEntries([
        ["lf-choice", { "x-state": { decide: { ...spec, writer: "user" } } }],
        ...extraDescriptors.map(([, captured]) => [captured.tag, captured.declaration]),
      ]),
    ),
    authored: new Map([
      [
        "choice",
        {
          tag: "lf-choice",
          specs: new Map([["decide", spec]]),
          positions: {},
          state: { decide: { action: null, value: null, detail: {} } },
        },
      ],
      ...extraAuthored,
    ]),
    descriptors: new Map([[descriptor.id, descriptor], ...extraDescriptors]),
  });
  return app;
};
const setup = (extraDescriptors = [], extraAuthored = []) => {
  const app = capture(extraDescriptors, extraAuthored);
  app.adopt(state(1));
  return app;
};
// The standing decision's outcome, or null while the widget is undecided.
const outcomeOf = (state) => state?.decide.detail.outcome ?? null;
const decision = (app) => outcomeOf(app.read().effective.widgets.get("choice").state);

test("semantic publication opens before subscribers and seals the newest nested epoch", async () => {
  const document = {};
  const coordinator = createPresentationCoordinator({ reportFailure: assert.fail });
  const lifecycle = [];
  const app = createSemanticApplication({
    presentation: {
      begin(epoch) {
        lifecycle.push(["begin", epoch]);
        return coordinator.begin(document, epoch);
      },
      seal(publication) {
        lifecycle.push(["seal", publication.semanticEpoch]);
        return coordinator.seal(publication);
      },
    },
  });
  assert.deepEqual(lifecycle, [
    ["begin", 0],
    ["seal", 0],
  ]);

  let presentation;
  let nested = false;
  app
    .select((root) => root.phase)
    .subscribe((phase) => {
      if (phase !== "offline" || nested) return;
      nested = true;
      assert.equal(coordinator.read().semanticEpoch, 1);
      const renderer = coordinator.attach("widget", {});
      presentation = renderer.present("offline");
      app.acceptData({ version: "empty", sources: {} }, 1);
    });

  lifecycle.length = 0;
  app.setPhase("offline");
  assert.deepEqual(lifecycle, [
    ["begin", 1],
    ["begin", 2],
    ["seal", 2],
  ]);
  assert.deepEqual(coordinator.read().pending, ["widget"]);
  let ready = false;
  const readiness = coordinator.whenPresented(document, 2).then((outcome) => {
    ready = true;
    return outcome;
  });
  await Promise.resolve();
  assert.equal(ready, false);
  presentation.resolve("proof");
  await presentation.ready;
  assert.equal(await readiness, "presented");
});

test("one synchronous immutable reading combines authored, accepted, and later pending gestures", () => {
  const app = setup();
  const seen = [];
  app
    .select((root) => outcomeOf(root.effective.widgets.get("choice").state))
    .subscribe((value) => seen.push([value, app.read().unresolved.length]));
  const prepared = state(2, [{ ...action("first"), id: "e1", seq: 1 }]);
  app.enqueue(action("first"), "now");
  app.enqueue(action("later", "reject"), "now");
  app.adopt(prepared);
  assert.equal(decision(app), "reject");
  assert.deepEqual(seen, [
    [null, 0],
    ["accept", 1],
    ["reject", 2],
  ]);
  assert.equal(app.read().authoritative.events[0].id, "e1");
  assert.equal(app.read().unresolved.length, 2);
  assert.throws(() => app.read().effective.widgets.set("wrong", {}), TypeError);
  assert.throws(() => {
    app.read().unresolved[1].event.action = "other";
  }, TypeError);
  app.refuse("later");
  assert.equal(decision(app), "accept");
});

test("the public Thread collection contains conversations while approvals stay page-wide", () => {
  const app = capture();
  const reading = state(1);
  const ask = servedReading("approval").browser.views["1"].document.asks.all[0];
  reading.browser.views[1].document.asks = {
    all: [ask],
    user: [ask],
    unanswered: [ask],
  };
  app.adopt(reading);

  const effective = app.read().effective;
  assert.deepEqual(Object.keys(effective.thread.collection), ["phase", "threads"]);
  assert.deepEqual(effective.asks.all, [ask]);
});

test("one widget selection publishes optimistic state without writable access", () => {
  const app = setup();
  const selected = app.selectWidget(descriptor);
  const seen = [];
  const stop = selected.subscribe((reading) => seen.push(reading));
  assert.equal(selected.read().actions.decide.available, true);
  assert.equal(selected.read().authored.decide.action, null);
  app.enqueue(action("first"), "now");
  assert.equal(selected.read().authored.decide.action, null);
  assert.equal(outcomeOf(selected.read().state), "accept");
  assert.equal(seen.at(-1).actions.decide.standing[0].event.attempt, "first");
  assert.throws(() => {
    selected.read().actions.decide.available = false;
  }, TypeError);
  assert.throws(() => {
    selected.read().authored.decide.value = "corrupt";
  }, TypeError);
  const beforeUnrelated = seen.length;
  app.acceptData({ version: "unrelated", sources: { unrelated: { value: true } } }, 1);
  assert.equal(seen.length, beforeUnrelated);
  app.refuse("first");
  assert.equal(outcomeOf(selected.read().state), null);
  stop();
});

test("page and frozen widgets keep their own verb writers and pending definitions", () => {
  for (const [pageWriter, replyWriter, replyVerb] of [
    ["user", "user", "pick"],
    ["agent", "user", "decide"],
    ["user", "agent", "decide"],
  ]) {
    const page = capturedDescriptor({
      ...descriptor,
      declaration: { "x-state": { decide: { ...spec, writer: pageWriter } } },
    });
    const replySpec = {
      ...spec,
      writer: replyWriter,
      detail: { type: "object", properties: { outcome: { enum: ["defer"] } } },
    };
    const reply = capturedDescriptor({
      ...descriptor,
      id: "reply-choice",
      document: { kind: "thread", revision: 2, thread: "root", message: "reply" },
      declaration: { "x-state": { [replyVerb]: replySpec } },
    });
    const app = createSemanticApplication();
    app.identify(1);
    app.captureDocument({
      ...app.read().document,
      registry: stamped({ [page.tag]: page.declaration }),
      descriptors: new Map([
        [page.id, page],
        [reply.id, reply],
      ]),
      authored: new Map(
        [page, reply].map((widget) => [
          widget.id,
          {
            tag: widget.tag,
            specs: new Map(Object.entries(widget.declaration["x-state"])),
            positions: {},
            state: Object.fromEntries(
              Object.keys(widget.states).map((verb) => [
                verb,
                { action: null, value: null, detail: {} },
              ]),
            ),
          },
        ]),
      ),
    });
    app.adopt(state(1));
    for (const [widget, verb, writer, outcome] of [
      [page, "decide", pageWriter, "accept"],
      [reply, replyVerb, replyWriter, "defer"],
    ]) {
      const selected = app.selectWidget(widget);
      assert.deepEqual(
        Object.keys(selected.read().actions),
        writer === "user" ? [verb] : [],
      );
      if (writer !== "user") continue;
      assert.equal(selected.read().actions[verb].available, true);
      const pending = app.enqueue(
        {
          ...action(widget.id, outcome),
          widget: widget.id,
          action: verb,
          revision: widget.document.revision,
        },
        "now",
      );
      assert.deepEqual(
        pending.projection.e.meaning.state,
        widget.states[verb].definition,
      );
      assert.equal(selected.read().state[verb].detail.outcome, outcome);
      assert.equal(selected.read().actions[verb].undo[0].id, pending.localId);
      app.refuse(widget.id);
      assert.equal(selected.read().state[verb].action, null);
    }
  }
});

test("widget actions await a complete reading after loading or failed history", () => {
  const app = setup();
  const selected = app.selectWidget(descriptor);
  for (const phase of ["waiting", "offline", "ready"]) {
    app.setPhase(phase);
    assert.equal(selected.read().actions.decide.available, phase === "ready", phase);
  }
});

test("an offline document publishes every host command as unavailable", () => {
  const app = setup();
  const pending = app.enqueue(action("first"), "now");
  assert.equal(app.selectWidget(descriptor).read().actions.decide.available, true);
  assert.equal(
    app.selectWidget(descriptor).read().actions.decide.undo[0].id,
    pending.localId,
  );

  app.setHostAvailable(false);
  const reading = app.selectWidget(descriptor).read();
  assert.equal(reading.actions.decide.available, false);
  assert.equal(reading.actions.decide.unavailable, "no agent or server is available");
  assert.deepEqual(reading.actions.decide.undo, []);
  assert.equal(outcomeOf(reading.state), "accept");
});

test("widget undo candidates name only exact currently standing attempts", () => {
  const app = setup();
  const selected = app.selectWidget(descriptor);
  const pending = app.enqueue(action("first"), "now");
  assert.equal(selected.read().actions.decide.undo[0].attempt, "first");
  assert.equal(selected.read().actions.decide.undo[0].id, pending.localId);
  app.enqueue({ kind: "undo", undoes: pending.localId, attempt: "undo" }, "now");
  assert.deepEqual(selected.read().actions.decide.undo, []);
});

test("widget action history excludes terminal coverage records", () => {
  const app = setup();
  const terminal = { ...action("old"), id: "e-old", seq: 1 };
  const read = state(2);
  read.browser.views[1].coverage = [{ event: terminal, coordinate: null }];
  app.adopt(read);
  assert.deepEqual(app.selectWidget(descriptor).read().actions.decide.history, []);
});

test("the selected revision keeps carried action history from earlier revisions", () => {
  const app = setup();
  const current = {
    ...descriptor,
    document: { kind: "page", revision: 2 },
  };
  const nextDocument = {
    ...app.read().document,
    revision: 2,
    descriptors: new Map([[current.id, current]]),
  };
  const carried = { ...action("old"), id: "e-old", seq: 1, revision: 1 };
  const read = state(2, [carried]);
  read.active.revision = 2;
  read.browser.views[2] = read.browser.views[1];
  read.browser.views[2].basis.revision = 2;
  delete read.browser.views[1];
  app.adopt(read, nextDocument);
  assert.deepEqual(
    app
      .selectWidget(current)
      .read()
      .actions.decide.history.map(({ id }) => id),
    ["e-old"],
  );
});

test("an adopted live revision retains its stamp while a newer revision waits", () => {
  const app = createSemanticApplication();
  app.identify(1, 1, true);
  const nextDocument = {
    ...app.read().document,
    revision: 2,
    stamp: 2,
    descriptors: new Map([
      [descriptor.id, { ...descriptor, document: { kind: "page", revision: 2 } }],
    ]),
  };
  const read = state(2);
  read.active = { revision: 2, version: 2 };
  read.browser.views[2] = read.browser.views[1];
  read.browser.views[2].basis.revision = 2;
  delete read.browser.views[1];

  assert.equal(app.adopt(read, nextDocument), true);
  assert.equal(app.read().document.revision, 2);
  assert.equal(app.read().document.stamp, 2);
});

test("a frozen descriptor capture cannot relabel the shown document", () => {
  const app = createSemanticApplication();
  app.identify(1, 1, true);
  const capture = {
    ...app.read().document,
    descriptors: new Map([[descriptor.id, descriptor]]),
  };
  const read = state(2);
  read.active = { revision: 1, version: 2 };

  assert.equal(app.adopt(read, capture), true);
  assert.equal(app.read().document.revision, 1);
  assert.equal(app.read().document.stamp, 1);
});

test("message capture preserves a deferred document's identity and immutable fields", () => {
  for (const stamp of [null, 1]) {
    const app = capture();
    app.identify(1, stamp, true);
    const shown = app.read().document;
    const body = { text: "A newly read message" };
    const messageBodies = new Map([["message", body]]);
    const read = state(2);
    read.active = { revision: 2, version: 2 };

    assert.equal(app.adopt(read, { ...shown, messageBodies }), true);
    const admitted = app.read().document;
    assert.equal(admitted.revision, 1);
    assert.equal(admitted.stamp, stamp);
    assert.equal(admitted.registry, shown.registry);
    assert.equal(admitted.authored, shown.authored);
    assert.equal(admitted.descriptors, shown.descriptors);
    body.text = "Changed outside the application";
    messageBodies.clear();
    assert.equal(admitted.messageBodies.get("message").text, "A newly read message");
    assert.throws(() => admitted.authored.clear(), /read-only/);
  }
});

test("document capture and its matching admitted reading publish atomically", () => {
  const app = setup();
  const seen = [];
  app
    .select((root) => [
      root.document.revision,
      root.authoritative?.active.revision ?? null,
      root.document.descriptors.get("next")?.document.revision ?? null,
      root.document.authored.has("next"),
      outcomeOf(root.effective.widgets.get("next")?.state),
    ])
    .subscribe((tuple) => seen.push(tuple));
  const nextDescriptor = {
    ...descriptor,
    id: "next",
    document: { kind: "page", revision: 2 },
  };
  const nextDocument = {
    ...app.read().document,
    revision: 2,
    authored: new Map([
      [
        "next",
        {
          tag: "lf-choice",
          specs: new Map([["decide", spec]]),
          positions: {},
          state: { decide: { action: null, value: null, detail: {} } },
        },
      ],
    ]),
    descriptors: new Map([[nextDescriptor.id, nextDescriptor]]),
  };
  const read = state(2, [
    {
      ...action("next-action"),
      id: "e-next",
      seq: 1,
      revision: 2,
      widget: "next",
    },
  ]);
  read.active = { revision: 2, version: 2 };
  read.browser.views[2] = read.browser.views[1];
  read.browser.views[2].basis.revision = 2;
  delete read.browser.views[1];

  assert.equal(app.canAdopt(read, nextDocument), true);
  assert.equal(app.adopt(read, nextDocument), true);
  assert.deepEqual(seen, [
    [1, 1, null, false, null],
    [2, 2, 2, true, "accept"],
  ]);

  const staleDocument = { ...nextDocument, revision: 3 };
  assert.equal(app.adopt(read, staleDocument), false);
  assert.deepEqual(seen.at(-1), [2, 2, 2, true, "accept"]);
});

test("accepted reading order includes non-event activity and data taken in order", () => {
  const app = setup();
  const newer = { ...state(3), activity: { phase: "agent", held: true } };
  assert.equal(app.adopt(newer), true);
  // Transport asks the same question before preparing anything for an answer.
  assert.equal(app.overtaken(state(2)), true);
  assert.equal(app.overtaken(state(3)), false);
  assert.equal(app.adopt(state(2)), false);
  assert.equal(app.read().authoritative.reading, "reading-3");
  assert.deepEqual(app.read().effective.activity, newer.activity);
  const before = app.read().semanticEpoch;
  assert.equal(
    app.acceptData({ version: "b", sources: { input: { value: 5 } } }, 2),
    true,
  );
  assert.equal(app.acceptData({ version: "a", sources: {} }, 1), false);
  assert.ok(app.read().semanticEpoch > before);
  assert.equal(app.read().data.sources.input.value, 5);
});

test("one publication keeps per-input workflows and user-first thread attention", () => {
  const app = setup();
  const reading = state(2);
  reading.browser.views[1].thread.threads = [
    servedThread(
      [
        {
          id: "root",
          kind: "comment",
          author: "user",
          ts: "2026-09-22T10:00:00-07:00",
          text: "First",
        },
        {
          id: "newer",
          kind: "reply",
          parent: "root",
          author: "user",
          ts: "2026-09-22T10:01:00-07:00",
          text: "Second",
        },
      ],
      { attention: { kind: "needs_user", reason: "ask", workflow: null } },
    ),
  ];
  reading.workflows = [
    threadWorkflow("first-work", { stage: "replying", seq: 1 }),
    threadWorkflow("second-work", { input: "newer", stage: "queued", seq: 2 }),
  ];
  app.adopt(reading);
  const thread = app.read().effective.thread.all[0];
  assert.deepEqual(
    thread.msgs.map((message) => [message.id, message.workflows[0]?.stage]),
    [
      ["root", "replying"],
      ["newer", "queued"],
    ],
  );
  assert.deepEqual(thread.attention, {
    kind: "needs_user",
    reason: "ask",
    workflow: null,
  });
  assert.equal(thread.workflows.length, 2);
  app.enqueue(
    { kind: "reply", parent: "root", attempt: "local", text: "Third", revision: 1 },
    "2026-09-22T10:02:00-07:00",
  );
  // The user's own send shows on its message at once; whose turn the thread is then
  // waits for the log's reading of it.
  const sent = app.read().effective.thread.all[0];
  assert.deepEqual(
    sent.msgs.map((message) => [message.id, message.workflows[0]?.stage]),
    [
      ["root", "replying"],
      ["newer", "queued"],
      ["pending:local", "sending"],
    ],
  );
  assert.deepEqual(sent.attention, thread.attention);
});

test("a refused send hands its thread to the user to send again", () => {
  const app = setup();
  const reading = state(2);
  reading.browser.views[1].thread.threads = [
    servedThread([
      {
        id: "root",
        kind: "comment",
        author: "user",
        ts: "2026-09-22T10:00:00-07:00",
        text: "First",
      },
    ]),
  ];
  app.adopt(reading);
  app.enqueue(
    { kind: "reply", parent: "root", attempt: "local", text: "Second", revision: 1 },
    "2026-09-22T10:01:00-07:00",
  );
  assert.equal(app.read().effective.thread.all[0].attention, null);
  app.refuse("local");
  assert.deepEqual(app.read().effective.thread.all[0].attention, {
    kind: "needs_user",
    reason: "resend",
    workflow: "rejected:local",
  });

  const acceptedApp = setup();
  const acceptedReading = structuredClone(reading);
  acceptedReading.workflows = [threadWorkflow("accepted-send")];
  acceptedReading.browser.views[1].thread.threads[0].attention = {
    kind: "waiting",
    reason: "workflow",
    workflow: "accepted-send",
  };
  acceptedApp.adopt(acceptedReading);
  acceptedApp.enqueue(
    { kind: "reply", parent: "root", attempt: "next", text: "Third", revision: 1 },
    "2026-09-22T10:02:00-07:00",
  );
  acceptedApp.refuse("next");
  assert.deepEqual(acceptedApp.read().effective.thread.all[0].attention, {
    kind: "needs_user",
    reason: "resend",
    workflow: "rejected:next",
  });
});

test("every thread gesture the ledger holds names the thread it stands in", () => {
  const gestured = (...events) => {
    const app = setup();
    const reading = state(2);
    reading.browser.views[1].thread.threads = [
      servedThread([
        {
          id: "root",
          kind: "comment",
          author: "user",
          ts: "2026-09-22T10:00:00-07:00",
          text: "First",
        },
      ]),
    ];
    app.adopt(reading);
    for (const event of events) app.enqueue(event, "2026-09-22T10:01:00-07:00");
    return app.read().effective.thread.gestured;
  };
  const reaction = { kind: "reply", parent: "root", attempt: "mark", token: "keep" };
  for (const gesture of [
    { kind: "reply", parent: "root", attempt: "say", text: "Second", revision: 1 },
    reaction,
    { kind: "edit", message: "root", attempt: "rewrite", text: "First, again" },
    { kind: "resolve", parent: "root", attempt: "close" },
  ])
    assert.deepEqual(gestured(gesture), ["root"], gesture.kind);
  assert.deepEqual(
    gestured(reaction, { kind: "undo", undoes: "pending:mark", attempt: "unmark" }),
    ["root"],
  );
  assert.deepEqual(gestured(action("move")), []);
});

test("an answer concerns the thread it closes from the reading that logs it", () => {
  // A page suggestion that answers a thread stands in no thread, so accepting it draws
  // nothing there until the log closes the thread. The reading that does files the
  // acceptance under that thread, and the news the thread holds back shows with it.
  const app = createSemanticApplication();
  app.identify(1);
  app.adopt(servedReading("suggestion closes a thread"));
  app.enqueue(
    {
      kind: "action",
      widget: "sug-refill",
      action: "decide",
      detail: { outcome: "accept" },
      revision: 1,
      attempt: "accept",
    },
    "now",
  );
  assert.deepEqual(app.read().effective.thread.gestured, []);
  const logged = servedReading("suggestion accepted");
  const accepted = logged.events.at(-1);
  app.accept("accept", accepted);
  app.adopt(logged);
  assert.deepEqual(app.read().effective.thread.gestured, ["e1"]);

  // Taking the acceptance back concerns the thread it closed, which the undo reopens.
  const undoing = createSemanticApplication();
  undoing.identify(1);
  undoing.adopt(logged);
  undoing.enqueue({ kind: "undo", undoes: accepted.id, attempt: "take-back" }, "now");
  assert.deepEqual(undoing.read().effective.thread.gestured, ["e1"]);
});

test("a refused local message publishes one failed workflow before retirement", () => {
  const app = setup();
  const event = {
    kind: "comment",
    attempt: "refused",
    text: "Please try this",
    revision: 1,
  };
  app.enqueue(event, "2026-09-22T10:00:00-07:00");
  assert.equal(app.read().effective.workflows.at(-1).stage, "sending");
  app.refuse("refused");
  const failed = app.read().effective.workflows.at(-1);
  assert.deepEqual(failed.condition, { kind: "failed", operation: "delivery" });
  assert.equal(failed.next_actor, "user");
  assert.equal(app.read().effective.thread.all.length, 0);
  app.release(new Set(["refused"]));
  assert.equal(app.read().effective.workflows.length, 0);
});

test("a local send's workflow takes the served workflow's shape", () => {
  const app = setup();
  app.enqueue(action("move"), "now");
  app.refuse("move");
  const [move] = app.read().effective.workflows;
  assert.deepEqual(
    [move.subject, move.thread, move.holds_thread, move.coordinate],
    [{ kind: "widget", id: "choice" }, null, false, coordinate],
  );
  app.release(new Set(["move"]));
  for (const event of [
    { kind: "done", version: 1 },
    { kind: "resolve", parent: "root" },
  ]) {
    app.enqueue({ ...event, attempt: "other" }, "now");
    app.refuse("other");
    assert.deepEqual(app.read().effective.workflows, []);
    app.release(new Set(["other"]));
  }
  // Every field the server sends but the undelivered-only ones it has no reading of.
  const { quiet: _quiet, dropped: _dropped, ...served } = servedWorkflow();
  assert.deepEqual(Object.keys(move).sort(), Object.keys(served).sort());
});

test("a version being marked read reads read, outside the gesture ledger", () => {
  const app = setup();
  const reading = state(2);
  const root = {
    id: "agent-root",
    kind: "comment",
    author: "agent",
    agent: "Agent",
    ts: "2026-09-22T10:00:00-07:00",
    seq: 1,
    text: "Answer",
  };
  reading.browser.views[1].thread.threads = [
    servedThread([root], {
      unread: [{ message: "agent-root", version: "agent-root" }],
    }),
  ];
  app.adopt(reading);
  const thread = () => app.read().effective.thread.all[0];
  assert.equal(thread().msgs[0].unread, true);
  assert.deepEqual(thread().unread, [{ message: "agent-root", version: "agent-root" }]);

  const original = [{ message: "agent-root", version: "agent-root" }];
  app.markRead(original);
  assert.equal(thread().msgs[0].unread, false);
  assert.deepEqual(thread().unread, []);
  assert.deepEqual(app.read().unresolved, []);
  assert.deepEqual(app.read().effective.sending, []);
  assert.deepEqual(app.read().effective.workflows, []);
  app.settleMarkRead(original);
  assert.equal(thread().msgs[0].unread, true);

  // Marking read names one exact version; an edit's version is not it.
  const edited = structuredClone(reading);
  edited.browser.views[1].thread.threads[0].unread = [
    { message: "agent-root", version: "edit-2" },
  ];
  app.adopt(edited);
  app.markRead(original);
  assert.equal(thread().msgs[0].unread, true);
});

test("semantic epochs include visible revision facts but not transport metadata", () => {
  const app = setup();
  const asked = state(2);
  const choice = wireAsk("choice", "lf-choice");
  asked.browser.views[1].document.asks = {
    all: [choice],
    user: [choice],
    unanswered: [choice],
  };
  const before = app.read().semanticEpoch;
  app.adopt(asked);
  assert.ok(app.read().semanticEpoch > before);

  const beforeRevisionFacts = app.read().semanticEpoch;
  const revisionFacts = structuredClone(asked);
  revisionFacts.taken = 3;
  revisionFacts.browser.views[1].published_at = "2026-09-12T10:00:00-07:00";
  revisionFacts.browser.views[1].reports = [
    {
      id: "report-1",
      target: { kind: "widget", id: "choice" },
      source: "report",
      action: "state",
      detail: { state: "working" },
      text: "working",
      ts: "2026-09-12T09:00:00-07:00",
      disposition: "effective",
      seq: 1,
    },
  ];
  app.adopt(revisionFacts);
  assert.ok(app.read().semanticEpoch > beforeRevisionFacts);
  const { basis: _basis, ...published } = revisionFacts.browser.views[1];
  assert.deepEqual(app.read().effective.view, published);

  const stable = app.read().semanticEpoch;
  const metadata = structuredClone(revisionFacts);
  metadata.taken = 4;
  metadata.browser.basis.through_seq = 7;
  metadata.browser.views[1].basis.through_seq = 7;
  app.adopt(metadata);
  assert.equal(app.read().semanticEpoch, stable);
});

test("historical view projection uses the publisher's captured document contract", () => {
  const app = setup();
  const accepted = { ...action("first"), id: "e1", seq: 1 };
  const historical = state(2, [accepted]);
  const historicalSpec = { ...spec, historical: true };
  historical.browser.views[1].document.projection.entries[0].spec = historicalSpec;
  const projection = app.projectView(historical.browser.views[1]);
  assert.equal(projection.desired.get(JSON.stringify(coordinate)).e.id, "e1");
  assert.deepEqual(
    projection.desired.get(JSON.stringify(coordinate)).spec,
    historicalSpec,
  );
});

test("filtered widget state is selected inside the publisher", () => {
  const app = setup();
  const accepted = { ...action("first"), id: "e1", seq: 1 };
  app.adopt(state(2, [accepted]));
  assert.equal(outcomeOf(app.selectWidgets([]).get("choice").state), null);
  assert.equal(outcomeOf(app.selectWidgets(["e1"]).get("choice").state), "accept");
  assert.equal(outcomeOf(app.selectWidgets(null).get("choice").state), "accept");
});

test("admitted edits, a raced undo refusal, and revisions share one sequence", () => {
  const sequence = servedGestureSequence();
  for (const refusalFirst of [false, true]) {
    const app = createSemanticApplication();
    app.identify(1);
    const declaration = sequence.declaration;
    const specs = new Map(Object.entries(declaration["x-state"]));
    const document = (revision) => ({
      ...app.read().document,
      revision,
      registry: { "lf-draft": declaration, $states: { "lf-draft": sequence.stamped } },
      authored: new Map([
        [
          "draft-ops",
          {
            tag: "lf-draft",
            specs,
            positions: {},
            state: {
              edit: {
                action: null,
                value: sequence.authored[revision],
                detail: { value: sequence.authored[revision] },
              },
            },
          },
        ],
      ]),
      descriptors: new Map([
        [
          "draft-ops",
          {
            id: "draft-ops",
            tag: "lf-draft",
            declaration,
            states: sequence.stamped,
            document: { kind: "page", revision },
            parent: null,
            ancestors: [],
            quoted: false,
          },
        ],
      ]),
    });
    app.captureDocument(document(1));
    const adopt = (index) =>
      assert.equal(
        app.adopt(
          sequence.states[index],
          document(sequence.states[index].active.revision),
        ),
        true,
      );
    const value = () => app.read().effective.widgets.get("draft-ops").state.edit.value;
    adopt(0);
    assert.equal(value(), "Authored words.");
    for (const [index, expected] of [
      [1, "First edit."],
      [2, "Second edit."],
      [3, "Authored words."],
    ]) {
      adopt(index);
      assert.equal(value(), expected);
      assert.deepEqual(
        [...app.read().effective.projection.desired.keys()],
        [JSON.stringify(["draft-ops", "draft-ops", "edit"])],
        "the wire and local gestures share the declared coordinate",
      );
    }

    // The other tab's accepted undo arrives while this tab is still sending its own.
    const undo = sequence.refused;
    app.enqueue(undo, "now");
    assert.equal(value(), "Second edit.");
    if (!refusalFirst)
      assert.equal(
        app.adopt(
          { ...sequence.states[4], taken: sequence.states[4].taken + 0.5 },
          document(1),
        ),
        true,
      );
    assert.equal(value(), "Second edit.");
    const publications = [];
    const stop = app.select((root) => root).subscribe(() => publications.push(value()));
    if (refusalFirst) adopt(4);
    else assert.equal(app.adopt(sequence.states[4], document(1)), false);
    app.refuse(undo.attempt);
    stop();
    assert.ok(publications.length > 1);
    assert.ok(
      publications.every((value) => value === "Second edit."),
      "fresh state and refusal never expose stale e3",
    );
    assert.equal(value(), "Second edit.");
    assert.equal(app.entry(undo.attempt).state, "refused");
    app.release(new Set([undo.attempt]));
    assert.ok(!app.entry(undo.attempt));

    adopt(5);
    assert.equal(value(), "Rewritten words.");
    const edit = app.enqueue(
      {
        ...sequence.commands[0],
        revision: 2,
        attempt: "sequence-new-edit",
        detail: { value: "Pending words." },
      },
      "now",
    );
    assert.equal(value(), "Pending words.");
    app.enqueue(
      { kind: "undo", undoes: edit.localId, attempt: "sequence-new-undo" },
      "now",
    );
    assert.equal(
      value(),
      "Rewritten words.",
      "undo cannot revive a retracted older edit",
    );
    const refusedPublications = [];
    const stopRefused = app
      .select((root) => root)
      .subscribe(() => refusedPublications.push(value()));
    adopt(5);
    assert.deepEqual(app.refuse("sequence-new-edit"), ["sequence-new-undo"]);
    stopRefused();
    assert.ok(refusedPublications.length > 1);
    assert.ok(refusedPublications.every((value) => value === "Rewritten words."));
    assert.equal(value(), "Rewritten words.", "refusal restores state before release");
    app.release(new Set(["sequence-new-edit"]));
    assert.equal(value(), "Rewritten words.");
    adopt(6);
    assert.equal(
      value(),
      "Rewritten words.",
      "a later revision inherits the retraction",
    );
  }
});

test("receipt adoption keeps attempts until presentation proof and preserves dependent undo", () => {
  const app = setup();
  const first = app.enqueue(action("first"), "now");
  app.enqueue({ kind: "undo", undoes: first.localId, attempt: "undo" }, "now");
  assert.equal(decision(app), null);
  const accepted = { ...action("first"), id: "e1", seq: 1 };
  app.adopt(state(2, [accepted]));
  app.accept("first", accepted);
  assert.equal(app.read().unresolved.length, 2);
  assert.equal(decision(app), null);
  app.present([accepted]);
  app.release(new Set(["first"]));
  assert.equal(decision(app), null);
  assert.equal(app.nameEvents("undo"), true);
  assert.equal(app.entry("undo").event.undoes, "e1");
});

// Each step is a signal and the entry's state after it: `null` once it has left. What
// the page draws follows the state: the gesture until a reading logs it, the log's
// event after, and neither once refused.
const lifecycle = [
  {
    name: "an action accepted before any reading holds it",
    event: action("gesture"),
    steps: [
      ["accept", "accepted", "gesture"],
      ["log", "accepted:logged", "log"],
      ["present", "accepted:presented", "log"],
      ["release", null, "log"],
    ],
  },
  {
    name: "an action a reading presents before its POST answers",
    event: action("gesture"),
    steps: [
      ["log", "sending:logged", "log"],
      ["present", "sending:presented", "log"],
      ["release", "sending:presented", "log"],
      ["accept", "accepted:presented", "log"],
      ["release", null, "log"],
    ],
  },
  {
    name: "a refused action",
    event: action("gesture"),
    steps: [
      ["refuse", "refused", null],
      ["release", null, null],
    ],
  },
  {
    name: "a comment accepted and then presented",
    event: { kind: "comment", attempt: "gesture", text: "Note", revision: 1 },
    steps: [
      ["accept", "accepted", "gesture"],
      ["log", "accepted:logged", "log"],
      ["present", null, "log"],
    ],
  },
  {
    name: "a comment presented before its POST answers",
    event: { kind: "comment", attempt: "gesture", text: "Note", revision: 1 },
    steps: [
      ["log", "sending:logged", "log"],
      ["present", "sending:presented", "log"],
      ["accept", null, "log"],
    ],
  },
];
for (const { name, event, steps } of lifecycle)
  test(`the ledger carries ${name} through one lifecycle`, () => {
    const app = setup();
    const logged = { ...event, id: "e1", seq: 1, author: "user", ts: "now" };
    const reading = state(2, event.kind === "action" ? [logged] : []);
    reading.browser.receipts = [logged];
    if (event.kind === "comment")
      reading.browser.views[1].thread.threads = [servedThread([logged])];
    // Where the page draws the gesture from: its own entry, the log, or nowhere.
    const drawn = () => {
      if (event.kind === "action")
        return app.read().effective.projection.desired.get(JSON.stringify(coordinate))
          ?.e.id === "e1"
          ? "log"
          : decision(app) === "accept"
            ? "gesture"
            : null;
      const [thread] = app.read().effective.thread.all;
      return thread?.root.id === "e1" ? "log" : thread ? "gesture" : null;
    };
    const signals = {
      accept: () => app.accept("gesture", logged),
      refuse: () => app.refuse("gesture"),
      log: () => app.adopt(reading),
      present: () => app.present([logged]),
      release: () => app.release(new Set(["gesture"])),
    };
    app.enqueue(event, "now");
    assert.equal(app.entry("gesture").state, "sending");
    assert.deepEqual(app.read().effective.sending, ["gesture"]);
    assert.equal(drawn(), "gesture");
    for (const [signal, next, from] of steps) {
      signals[signal]();
      assert.equal(app.entry("gesture")?.state ?? null, next, `after ${signal}`);
      assert.deepEqual(
        app.read().effective.sending,
        next?.startsWith("sending") ? ["gesture"] : [],
        `sending after ${signal}`,
      );
      assert.equal(drawn(), from, `drawn after ${signal}`);
    }
  });

test("refusal takes the gestures that depend on the refused one with it", () => {
  const app = setup();
  const first = app.enqueue(action("first"), "now");
  app.enqueue({ kind: "undo", undoes: first.localId, attempt: "undo" }, "now");
  const comment = app.enqueue(
    { kind: "comment", attempt: "comment", text: "Note", revision: 1 },
    "now",
  );
  app.enqueue(
    {
      kind: "reply",
      parent: comment.localId,
      attempt: "reply",
      text: "More",
      revision: 1,
    },
    "now",
  );
  assert.deepEqual(app.refuse("first"), ["undo"]);
  assert.deepEqual(app.refuse("comment"), ["reply"]);
  assert.deepEqual(
    app.read().unresolved.map((entry) => [entry.event.attempt, entry.state]),
    [
      ["first", "refused"],
      ["comment", "refused"],
    ],
  );
  assert.deepEqual(
    app.releasable().map((entry) => entry.event.attempt),
    ["first", "comment"],
  );
});

test("thread acceptance is semantic before presentation can retire its local handle", () => {
  const app = capture();
  const comment = {
    kind: "comment",
    attempt: "comment",
    text: "Keep this",
    revision: 1,
  };
  app.enqueue(comment, "now");
  assert.equal(app.read().phase, "waiting");
  assert.equal(app.read().effective.thread.all[0].root.text, "Keep this");
  assert.equal(app.read().effective.thread.collection.phase, "waiting");
  assert.equal(app.read().effective.thread.collection.threads.length, 1);
  const accepted = { ...comment, id: "e1", author: "user", ts: "now" };
  const read = state(2);
  read.browser.receipts = [accepted];
  read.browser.views[1].thread.threads = [servedThread([accepted])];
  app.adopt(read);
  app.accept("comment", accepted);
  assert.equal(app.read().effective.thread.all.length, 1);
  assert.equal(app.read().unresolved.length, 1);
  app.present([accepted]);
  assert.equal(app.read().unresolved.length, 0);
  assert.equal(app.read().effective.thread.all[0].root.id, "e1");
});

test("refusal removes a local thread without requiring a saved reading", () => {
  const app = capture();
  app.enqueue(
    { kind: "comment", attempt: "early", text: "Keep my words", revision: 1 },
    "now",
  );
  assert.equal(app.read().effective.thread.collection.threads.length, 1);
  app.refuse("early");
  assert.equal(app.read().phase, "waiting");
  assert.deepEqual(app.read().effective.thread.collection.threads, []);
});

test("widget selections publish the canonical held thread", () => {
  const app = setup();
  const selected = app.selectWidget(descriptor);
  const root = {
    kind: "comment",
    id: "hold-choice",
    author: "user",
    text: "Pause here.",
    holds: descriptor.id,
    ts: "now",
  };
  const accepted = state(2);
  accepted.browser.views[1].thread.threads = [
    servedThread([root], { seat: descriptor.id }),
  ];
  app.adopt(accepted);
  assert.equal(
    selected.read().thread.heldBy,
    accepted.browser.views[1].thread.threads[0].id,
  );

  const released = state(3);
  released.browser.views[1].thread.threads = [
    { ...accepted.browser.views[1].thread.threads[0], resolved: { author: "user" } },
  ];
  app.adopt(released);
  assert.equal(selected.read().thread.heldBy, null);
});

for (const resolved of [null, { author: "user" }]) {
  test(`a pending user reply leaves ${resolved ? "a resolved" : "an open"} ask's turn to the log`, () => {
    const app = setup();
    const root = {
      kind: "comment",
      id: "ask",
      author: "agent",
      text: "Which one?",
      ts: "now",
    };
    // The server owes nobody a turn in a resolved thread; an open one waits on the
    // user's answer.
    const standing = resolved ? null : "needs_user";
    const accepted = state(2);
    accepted.browser.views[1].thread.threads = [
      servedThread([root], {
        resolved,
        user_prompt: resolved ? null : { message: root.id, version: root.id },
        attention: resolved
          ? null
          : { kind: "needs_user", reason: "ask", workflow: null },
      }),
    ];
    app.adopt(accepted);
    const turn = () => {
      const thread = app.read().effective.thread.all[0];
      return [thread.attention?.kind ?? null, thread.resolved];
    };
    assert.deepEqual(turn(), [standing, resolved]);

    // The reply reopens the thread it joins, which the gesture settles by itself; whose
    // turn the thread is then waits for the log's reading.
    app.enqueue(
      {
        kind: "reply",
        parent: root.id,
        attempt: "answer",
        text: "The first one.",
        revision: 1,
      },
      "now",
    );
    assert.deepEqual(turn(), [standing, null]);
    const answer = { kind: "reply", attempt: "answer", id: "e-answer" };
    app.accept("answer", answer);
    app.present([answer]);
    assert.deepEqual(app.read().unresolved, []);
    assert.deepEqual(turn(), [standing, resolved]);

    // A refused reply is the user's to send again.
    app.enqueue(
      {
        kind: "reply",
        parent: root.id,
        attempt: "retry",
        text: "Still the first one.",
        revision: 1,
      },
      "now",
    );
    app.refuse("retry");
    assert.deepEqual(turn(), ["needs_user", resolved]);
  });
}

test("a pending gesture leaves asks and Questions as served until the log answers", () => {
  // A settling reaction answered the agent's ask, so the server lists the ask as
  // done. Which asks taking it back reopens is the log's reading, so Questions moves
  // when the server answers the undo, not before.
  const ask = {
    kind: "comment",
    id: "ask",
    author: "agent",
    text: "Keep this chart?",
    ts: "now",
  };
  const kept = {
    kind: "reply",
    id: "kept",
    parent: ask.id,
    author: "user",
    token: "keep",
    ts: "now",
  };
  const app = setup();
  const accepted = state(2, [kept]);
  const answered = {
    id: `reply:${ask.id}`,
    source: { kind: "reply", id: ask.id },
    thread: ask.id,
    message: ask.id,
    prompt: { text: ask.text, target: ask.id },
    answer: { value: { token: "keep" }, event: kept },
    status: "answered",
    next_actor: null,
  };
  accepted.browser.views[1].thread.asks = { all: [answered], user: [], unanswered: [] };
  const done = {
    ...servedAskItem(answered, { subject: { kind: "thread", id: ask.id } }),
    state: "done",
    ended: null,
    detail: null,
  };
  accepted.browser.views[1].queues = { ...askQueues([]), done: [done] };
  accepted.browser.views[1].thread.threads = [servedThread([ask, kept])];
  app.adopt(accepted);

  app.enqueue({ kind: "undo", undoes: kept.id, attempt: "take-back" }, "now");
  const pending = app.read().effective;
  assert.deepEqual(pending.asks.user, []);
  assert.deepEqual(pending.queues.questions, []);
  assert.deepEqual(
    pending.queues.done.map(({ kind, id }) => [kind, id]),
    [["ask", answered.id]],
  );

  const reopened = { ...answered, answer: null, status: "open", next_actor: "user" };
  const undo = { kind: "undo", id: "e-undo", undoes: kept.id, attempt: "take-back" };
  const answeredUndo = state(3, [kept, undo]);
  answeredUndo.browser.views[1].thread.asks = {
    all: [reopened],
    user: [reopened],
    unanswered: [reopened],
  };
  answeredUndo.browser.views[1].queues = askQueues([reopened]);
  answeredUndo.browser.views[1].thread.threads = [
    servedThread([ask], {
      attention: { kind: "needs_user", reason: "ask", workflow: null },
    }),
  ];
  app.adopt(answeredUndo);
  const { thread, queues } = app.read().effective;
  assert.equal(thread.all[0].attention.kind, "needs_user");
  assert.deepEqual(
    queues.questions.map(({ kind, id }) => [kind, id]),
    [["ask", answered.id]],
  );
});

test("the publisher carries the server's Ask reading, page asks before thread asks", () => {
  const app = capture();
  // The authored document names the Ask, but only the log's reading says whether it
  // still stands, so neither the wait for that reading nor an offline page lists it.
  for (const phase of ["waiting", "offline"]) {
    app.setPhase(phase);
    assert.deepEqual(app.read().effective.asks.all, []);
  }

  const read = state(2);
  const page = wireAsk("ask", "lf-ask", "choice", "lf-choice");
  const frozen = wireAsk(
    "frozen-ask",
    "lf-ask",
    "frozen-choice",
    "lf-choice",
    "root-1",
  );
  read.browser.views[1].document.asks = {
    all: [page],
    user: [page],
    unanswered: [page],
  };
  read.browser.views[1].thread.asks = {
    all: [frozen],
    user: [],
    unanswered: [],
  };
  app.adopt(read);

  const record = page;
  assert.deepEqual(app.read().effective.asks, {
    phase: "ready",
    all: [record, frozen],
    user: [record],
    unanswered: [record],
  });
  assert.throws(() => {
    app.read().effective.asks.all[0].source.id = "other";
  }, TypeError);

  // A local gesture does not edit the reading: the user sees their answer in the
  // widget's own state at once, while the log answers which Asks still stand in the
  // state this POST returns.
  app.enqueue(action("answer"), "now");
  assert.deepEqual(
    app.read().effective.asks.user.map(({ source }) => source.id),
    ["choice"],
  );
  assert.equal(decision(app), "accept");
});

test("an unsettled report supplies desired widget state", () => {
  const valueSpec = {
    unit: "widget",
    record: { kind: "value", attr: "choice" },
  };
  const source = capturedDescriptor({
    ...descriptor,
    declaration: {
      properties: { choice: { type: "string" } },
      "x-state": { preview: { ...valueSpec, writer: "agent" } },
    },
  });
  const app = setup([[source.id, source]]);
  const accepted = state(2);
  const report = {
    kind: "report",
    widget: source.id,
    action: "preview",
    detail: { value: "reported" },
    revision: 1,
    id: "report-1",
    seq: 1,
  };
  report.meaning = {
    state: definition(source.tag, valueSpec),
  };
  accepted.events = [report];
  accepted.browser.basis.through_seq = 1;
  accepted.browser.receipts = [report];
  accepted.browser.views[1].basis.through_seq = 1;
  accepted.browser.views[1].document.projection = {
    entries: [
      {
        event: report,
        coordinate: [source.id, source.id, "preview"],
        spec: valueSpec,
        scope: "page",
        value: "reported",
        restated: [],
        absorbed: false,
        stands: false,
      },
    ],
    actions: [],
    reports: [report.id],
    desired: [report.id],
  };

  app.adopt(accepted);
  assert.equal(
    app.read().effective.widgets.get(source.id).state.preview.action,
    "preview",
  );
  assert.equal(
    app.read().effective.widgets.get(source.id).state.preview.value,
    "reported",
  );
});

test("a reaction root is not a spoken turn awaiting the user", () => {
  const app = setup();
  const root = {
    kind: "comment",
    id: "reaction-root",
    author: "agent",
    token: "ack",
    parent: "passage",
    ts: "now",
  };
  const accepted = state(2);
  accepted.browser.views[1].thread.threads = [
    servedThread([root], { bare_reaction: true }),
  ];

  app.adopt(accepted);
  assert.equal(app.read().effective.thread.all[0].attention, null);
});

test("approval leaves Questions in its sending turn and undo restores the exact version", () => {
  const adopt = (name) => {
    const app = createSemanticApplication();
    app.identify(1);
    app.adopt(servedReading(name));
    return app;
  };
  const app = adopt("approval");
  const asks = () => app.read().effective.queues.questions;
  const record = () => app.read().effective.asks.all[0];
  const ask = record();
  assert.equal(ask.source.kind, "approval");
  assert.equal(asks()[0].id, ask.id);
  assert.equal(asks()[0].kind, "ask");
  assert.equal(asks()[0].offers.done, false);
  app.enqueue({ kind: "done", version: 2, attempt: "other-version" }, "now");
  assert.equal(asks().length, 1);
  app.refuse("other-version");
  const pending = app.enqueue(
    { kind: "done", version: 1, attempt: "approve" },
    "queued-at",
  );
  assert.equal(asks().length, 0);
  assert.equal(app.read().effective.queues.done[0].id, ask.id);
  assert.deepEqual(record().answer, { value: true, event: null });
  assert.equal(record().status, "answered");
  assert.deepEqual(app.read().effective.thread.approvalHistory, [
    {
      kind: "done",
      version: 1,
      attempt: "approve",
      id: pending.localId,
      ts: "queued-at",
    },
  ]);
  app.refuse("approve");
  assert.deepEqual(app.read().effective.thread.approvalHistory, []);
  assert.equal(asks().length, 1);
  assert.equal(record().answer, null);

  const approved = adopt("approved");
  const approval = approved.read().effective.asks.all[0].answer.event;
  assert.deepEqual(
    approved.read().effective.thread.approvalHistory.map(({ id }) => id),
    [approval.id],
  );
  assert.equal(approved.read().effective.queues.questions.length, 0);
  approved.enqueue({ kind: "undo", undoes: approval.id, attempt: "undo" }, "now");
  assert.equal(approved.read().effective.queues.questions[0].id, ask.id);
  assert.equal(approved.read().effective.queues.done.length, 0);
  assert.equal(approved.read().effective.asks.all[0].answer, null);
  assert.equal(approved.read().effective.asks.all[0].status, "open");
  assert.deepEqual(approved.read().effective.thread.approvalHistory, []);
});

test("a revision preserves pending delivery while replacing incompatible speculative state", () => {
  const app = setup();
  const pending = app.enqueue(action("old"), "now");
  app.enqueue({ kind: "undo", undoes: pending.localId, attempt: "undo-old" }, "now");
  const document = structuredClone(app.read().document);
  document.revision = 2;
  const revisedSpec = {
    ...spec,
    writer: "user",
    record: { kind: "value", attr: "status" },
  };
  const declaration = {
    properties: { status: { type: "integer" } },
    "x-state": { decide: revisedSpec },
  };
  document.registry = stamped({ ...document.registry, "lf-choice": declaration });
  document.descriptors.set(
    "choice",
    capturedDescriptor({
      ...descriptor,
      declaration,
      document: { kind: "page", revision: 2 },
    }),
  );
  document.authored.set("choice", {
    tag: "lf-choice",
    specs: new Map([["decide", revisedSpec]]),
    positions: {},
    state: { decide: { action: null, value: 5, detail: { value: 5 } } },
  });
  const reading = state(2);
  reading.active.revision = 2;
  reading.browser.views[2] = reading.browser.views[1];
  reading.browser.views[2].basis.revision = 2;
  assert.equal(app.adopt(reading, document), true);
  assert.equal(app.read().effective.widgets.get("choice").state.decide.value, 5);
  assert.equal(app.read().unresolved.length, 2);
  const newAttempt = { ...action("new"), revision: 2, detail: { value: 7 } };
  app.enqueue(newAttempt, "now");
  assert.equal(app.read().effective.widgets.get("choice").state.decide.value, 7);
  assert.equal(app.read().unresolved.length, 3);
});

test("a pending undo keeps withdrawing its target once the log admits it under a revision", () => {
  const app = setup();
  const pending = app.enqueue(action("decided"), "now");
  app.enqueue(
    { kind: "undo", undoes: pending.localId, attempt: "undo-decided" },
    "now",
  );
  assert.equal(decision(app), null);
  // Revision 2 broadens the domain: the server keeps the admitted decision, while the
  // definition this tab recorded no longer equals the shown one.
  const broadened = {
    ...spec,
    writer: "user",
    detail: {
      ...spec.detail,
      properties: { outcome: { enum: ["accept", "reject", "defer"] } },
    },
  };
  const document = structuredClone(app.read().document);
  document.revision = 2;
  document.registry = stamped({
    ...document.registry,
    "lf-choice": { "x-state": { decide: broadened } },
  });
  document.descriptors.set(
    "choice",
    capturedDescriptor({
      ...descriptor,
      declaration: document.registry["lf-choice"],
      document: { kind: "page", revision: 2 },
    }),
  );
  const reading = state(2, [{ ...action("decided"), id: "e1", seq: 1 }]);
  reading.active.revision = 2;
  reading.browser.views[2] = reading.browser.views[1];
  reading.browser.views[2].basis.revision = 2;
  assert.equal(app.adopt(reading, document), true);
  assert.equal(decision(app), null);
});

test("a revision changing a verb's writer retains delivery without drawing the old user gesture", () => {
  const app = setup();
  app.enqueue(action("old-user"), "now");
  assert.equal(decision(app), "accept");
  const document = structuredClone(app.read().document);
  document.revision = 2;
  const agentSpec = { ...spec, writer: "agent" };
  const declaration = { "x-state": { decide: agentSpec } };
  document.registry = stamped({ ...document.registry, "lf-choice": declaration });
  document.descriptors.set(
    "choice",
    capturedDescriptor({
      ...descriptor,
      declaration,
      document: { kind: "page", revision: 2 },
    }),
  );
  document.authored.get("choice").specs.set("decide", agentSpec);
  const reading = state(2);
  reading.active.revision = 2;
  reading.browser.views[2] = reading.browser.views[1];
  reading.browser.views[2].basis.revision = 2;
  assert.equal(app.adopt(reading, document), true);
  assert.equal(decision(app), null);
  assert.equal(app.read().unresolved.length, 1);
});

test("An ask contains the local typed answer while completion waits for admission", () => {
  const declared = capturedDescriptor({
    ...descriptor,
    declaration: {
      ...descriptor.declaration,
      "x-awaits": { value: "decide", answered: { decide: {} } },
    },
  });
  const app = capture([[declared.id, declared]]);
  const reading = state(2);
  const ask = wireAsk("choice-context", "lf-context", "choice", "lf-choice");
  reading.browser.views[1].document.asks = {
    all: [ask],
    user: [ask],
    unanswered: [ask],
  };
  reading.browser.views[1].queues = askQueues([ask]);
  app.adopt(reading);
  assert.equal(app.read().effective.asks.all[0].answer, null);
  app.enqueue(action("typed"), "now");
  const pending = app.read().effective.asks;
  assert.deepEqual(pending.all[0].answer, {
    value: { outcome: "accept" },
    event: null,
  });
  assert.equal(pending.all[0].status, "open");
  assert.equal(pending.all[0], pending.user[0]);
  assert.equal(pending.all[0], pending.unanswered[0]);
  assert.equal(app.read().effective.queues.questions[0].kind, "ask");
  app.refuse("typed");
  assert.equal(app.read().effective.asks.all[0].answer, null);
});

test("empty completed answer and wrapper changes preserve ask identity", () => {
  const choose = {
    unit: "widget",
    writer: "user",
    record: { kind: "attribute", attr: "chosen" },
  };
  const declared = capturedDescriptor({
    ...descriptor,
    declaration: {
      "x-state": { choose },
      "x-awaits": { value: "choose", answered: { choose: {} } },
    },
  });
  const app = capture(
    [[declared.id, declared]],
    [
      [
        declared.id,
        {
          tag: declared.tag,
          specs: new Map([["choose", choose]]),
          state: { choose: { action: null, value: [], detail: { value: [] } } },
        },
      ],
    ],
  );
  const reading = state(2);
  const ask = {
    ...wireAsk("choice", "lf-choice"),
    status: "answered",
    next_actor: null,
    answer: { value: [], event: null },
  };
  reading.browser.views[1].document.asks = {
    all: [ask],
    user: [],
    unanswered: [],
  };
  reading.browser.views[1].queues = askQueues([ask]);
  app.adopt(reading);
  assert.deepEqual(app.read().effective.asks.all[0].answer.value, []);
  assert.equal(app.read().effective.queues.questions.length, 0);
  assert.equal(app.read().effective.queues.done[0].kind, "ask");
  const wrapped = structuredClone(reading);
  wrapped.taken = 3;
  wrapped.browser.views[1].document.asks.all[0].prompt.target = "new-context";
  app.adopt(wrapped);
  assert.equal(app.read().effective.asks.all[0].id, "widget:choice");
  assert.equal(app.read().effective.asks.all[0].prompt.target, "new-context");
});

test("pending undo removes completed empty ask values and refusal restores them", () => {
  for (const [record, value] of [
    [{ kind: "attribute", attr: "chosen" }, []],
    [{ kind: "body" }, ""],
  ]) {
    const choose = { unit: "widget", writer: "user", record };
    const answer = { unit: "widget", writer: "user" };
    const declared = capturedDescriptor({
      ...descriptor,
      declaration: {
        "x-state": { choose, answer },
        "x-awaits": { value: "choose", answered: { answer: {} } },
      },
    });
    const app = capture(
      [[declared.id, declared]],
      [
        [
          declared.id,
          {
            tag: declared.tag,
            specs: new Map([
              ["choose", choose],
              ["answer", answer],
            ]),
            state: {
              choose: { action: null, value, detail: { value } },
              answer: { action: null, value: null, detail: {} },
            },
          },
        ],
      ],
    );
    const accepted = {
      ...action("empty-answer"),
      action: "answer",
      detail: {},
      id: "e1",
      seq: 1,
    };
    const reading = state(2, [accepted]);
    const entry = reading.browser.views[1].document.projection.entries[0];
    entry.spec = answer;
    entry.event.meaning.state = definition(declared.tag, answer);
    const ask = {
      ...wireAsk("choice", "lf-choice"),
      status: "answered",
      next_actor: null,
      answer: { value, event: accepted },
    };
    reading.browser.views[1].document.asks = {
      all: [ask],
      user: [],
      unanswered: [],
    };
    reading.browser.views[1].queues = askQueues([ask]);
    app.adopt(reading);
    assert.deepEqual(app.read().effective.asks.all[0].answer.value, value);
    app.enqueue({ kind: "undo", undoes: accepted.id, attempt: "undo-empty" }, "now");
    assert.equal(app.read().effective.asks.all[0].status, "answered");
    assert.equal(app.read().effective.asks.all[0].answer, null);
    assert.equal(app.read().effective.queues.done[0].ask.answer, null);
    app.refuse("undo-empty");
    assert.deepEqual(app.read().effective.asks.all[0].answer.value, value);
  }
});

test("pending undo withdraws a decision an earlier Leaf recorded with another field", () => {
  const declared = capturedDescriptor({
    ...descriptor,
    declaration: {
      ...descriptor.declaration,
      "x-awaits": { value: "decide", answered: { decide: {} } },
    },
  });
  const app = capture([[declared.id, declared]]);
  // Before #2329 the recorded definition carried the verb flag as `update`.
  const accepted = {
    ...action("decided"),
    id: "e1",
    seq: 1,
    meaning: {
      state: {
        ...definition("lf-choice", spec),
        update: false,
      },
    },
  };
  const reading = state(2, [accepted]);
  reading.browser.views[1].document.asks = {
    all: [
      {
        ...wireAsk("choice", "lf-choice"),
        status: "answered",
        next_actor: null,
        answer: { value: { outcome: "accept" }, event: accepted },
      },
    ],
    user: [],
    unanswered: [],
  };
  app.adopt(reading);
  app.enqueue({ kind: "undo", undoes: accepted.id, attempt: "undo-earlier" }, "now");
  assert.equal(app.read().effective.asks.all[0].answer, null);
});

test("pending undo removes a custom ask answer before authoritative completion changes", () => {
  const declared = capturedDescriptor({
    ...descriptor,
    declaration: {
      ...descriptor.declaration,
      "x-awaits": { value: "decide", answered: { decide: {} } },
    },
  });
  const app = capture([[declared.id, declared]]);
  const accepted = { ...action("decided"), id: "e1", seq: 1 };
  const reading = state(2, [accepted]);
  const ask = {
    ...wireAsk("choice", "lf-choice"),
    status: "answered",
    next_actor: null,
    answer: { value: { outcome: "accept" }, event: accepted },
  };
  reading.browser.views[1].document.asks = {
    all: [ask],
    user: [],
    unanswered: [],
  };
  reading.browser.views[1].queues = askQueues([ask]);
  app.adopt(reading);
  assert.deepEqual(app.read().effective.asks.all[0].answer.value, {
    outcome: "accept",
  });
  app.enqueue({ kind: "undo", undoes: accepted.id, attempt: "undo-answer" }, "now");
  const pending = app.read().effective.asks.all[0];
  assert.equal(pending.status, "answered");
  assert.equal(pending.answer, null);
  assert.equal(app.read().effective.queues.done[0].ask.answer, null);
  app.refuse("undo-answer");
  assert.deepEqual(app.read().effective.asks.all[0].answer.value, {
    outcome: "accept",
  });
  app.enqueue(action("re-pick", "reject"), "now");
  assert.deepEqual(app.read().effective.asks.all[0].answer, {
    value: { outcome: "reject" },
    event: null,
  });
  app.refuse("re-pick");
  assert.equal(app.read().effective.asks.all[0].answer.event.id, accepted.id);
});
