import assert from "node:assert/strict";
import test from "node:test";
import { createSemanticApplication } from "../../browser/runtime/framework/application.js";
import { createPresentationCoordinator } from "../../browser/runtime/framework/presentation.js";
import {
  servedGestureSequence,
  servedObligationRow,
  servedReading,
  servedThread,
  servedWorkflow,
} from "../served.mjs";

// An operation definition as composition stamps one into `$states`. The browser only
// compares definitions, so a fixture's need only differ where the operations do.
const definition = (tag, spec) => ({
  origin: tag,
  unit: spec.unit,
  record: spec.record ?? null,
  creates: spec.creates ?? null,
  decides: spec.decides ?? false,
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
const spec = {
  unit: "widget",
  detail: {
    type: "object",
    properties: { outcome: { enum: ["accept", "reject"] } },
    required: ["outcome"],
    additionalProperties: false,
  },
};
const descriptor = {
  id: "choice",
  tag: "lf-choice",
  document: { kind: "page", revision: 1 },
  declaration: { "x-state": { decide: { ...spec, writer: "user" } } },
  parent: null,
  ancestors: [],
  quoted: false,
};
const empty = () => ({ entries: [], actions: [], reports: [], desired: [] });
const wireObligation = (
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
// A view's obligations as the served lists hold them: each the user owes on their list, On me,
// and each that is no longer open, done.
const obligationQueues = (records) => {
  const item = (record) =>
    servedObligationRow(record, {
      subject: { kind: "widget", id: record.source.id },
    });
  return {
    on_user: records.filter((record) => record.next_actor === "user").map(item),
    on_agent: [],
    done: records
      .filter((record) => record.status !== "open")
      .map((record) => ({ ...item(record), state: "done", ended: null, detail: null })),
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
    views: {
      1: {
        basis: { revision: 1, through_seq: events.length },
        thread: { threads: [], projection: empty() },
        items: [],
        coverage: [],
        undo: [],
        reports: [],
        published_at: null,
        queues: { on_user: [], on_agent: [], done: [] },
        document: {
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
    obligation: `update:${input}`,
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
// The outcome of the decision in force, or null while the widget is undecided.
const outcomeOf = (state) => state?.decide.detail.outcome ?? null;
const decision = (app) => outcomeOf(app.read().effective.widgets.get("choice").state);

test("semantic publication opens before subscribers and seals the newest nested epoch", async () => {
  const coordinator = createPresentationCoordinator({ reportFailure: assert.fail });
  const lifecycle = [];
  const publications = [];
  const app = createSemanticApplication({
    presentation: {
      begin() {
        const publication = coordinator.begin();
        publications.push(publication);
        lifecycle.push(["begin", publications.indexOf(publication)]);
        return publication;
      },
      seal(publication) {
        lifecycle.push(["seal", publications.indexOf(publication)]);
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
      assert.equal(coordinator.read().sealed, false);
      const renderer = coordinator.attach("widget");
      presentation = renderer.present();
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
  const readiness = coordinator.whenCurrentPresented().then((outcome) => {
    ready = true;
    return outcome;
  });
  await Promise.resolve();
  assert.equal(ready, false);
  presentation.resolve();
  await presentation.ready;
  assert.equal(await readiness, "presented");

  // Transport-only adoption still opens and seals a fresh presentation boundary;
  // coordinator readiness needs no second copy of the application's semantic epoch.
  const epoch = app.read().semanticEpoch;
  lifecycle.length = 0;
  app.setReach({ reach: "unreachable" });
  assert.equal(app.read().semanticEpoch, epoch);
  assert.deepEqual(lifecycle, [
    ["begin", 3],
    ["seal", 3],
  ]);
  assert.equal(coordinator.currentPresented(), true);
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

test("the public Thread collection contains conversations while page widgets stay page-wide", () => {
  const app = capture();
  const reading = state(1);
  const item = servedReading("suggestion accepted").browser.views["1"].obligations[0];
  reading.browser.views[1].obligations = [item];
  app.adopt(reading);

  const effective = app.read().effective;
  assert.deepEqual(Object.keys(effective.thread.collection), ["phase", "threads"]);
  assert.deepEqual(effective.obligations.all, [item]);
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
  assert.equal(seen.at(-1).actions.decide.inForce[0].event.attempt, "first");
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

test("widget undo candidates name only exact attempts currently in force", () => {
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
    assert.throws(() => {
      body.text = "Changed after transfer";
    }, TypeError);
    assert.throws(() => messageBodies.clear(), /read-only/);
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
      { attention: { kind: "needs_user", reason: "obligation", workflow: null } },
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
    reason: "obligation",
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
  // It serves the record of the resend it leaves, which is the user's.
  const resend = app
    .read()
    .effective.obligations.all.find((item) => item.id === failed.obligation);
  assert.equal(resend.next_actor, "user");
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
    [move.subject, move.thread, move.obligation, move.coordinate],
    [{ kind: "widget", id: "choice" }, null, "update:rejected:move", coordinate],
  );
  app.release(new Set(["move"]));
  for (const event of [{ kind: "resolve", parent: "root" }]) {
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
  const choice = wireObligation("choice", "lf-choice");
  asked.browser.views[1].obligations = [choice];
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
    name: "a comment accepted and then logged",
    event: { kind: "comment", attempt: "gesture", text: "Note", revision: 1 },
    steps: [
      ["accept", "accepted", "gesture"],
      ["log", null, "log"],
    ],
  },
  {
    name: "a comment logged before its POST answers",
    event: { kind: "comment", attempt: "gesture", text: "Note", revision: 1 },
    steps: [
      ["log", "sending:logged", "log"],
      ["present", "sending:logged", "log"],
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

test("a comment the log holds leaves the ledger once its POST accepts it", () => {
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
  assert.equal(app.read().effective.thread.all.length, 1);
  assert.equal(app.read().unresolved.length, 1);
  app.accept("comment", accepted);
  assert.equal(app.read().unresolved.length, 0);
  assert.equal(app.read().effective.thread.all.length, 1);
  assert.equal(app.read().effective.thread.all[0].root.id, "e1");
});

test("the reading that logs an accepted comment retires it in its own publication", () => {
  const app = setup();
  const comment = { kind: "comment", attempt: "note", text: "Note", revision: 1 };
  app.enqueue(comment, "now");
  const logged = { ...comment, id: "e1", seq: 1, author: "user", ts: "now" };
  app.accept("note", logged);
  const reading = state(2);
  reading.browser.receipts = [logged];
  reading.browser.views[1].thread.threads = [servedThread([logged])];
  app.adopt(reading);
  assert.deepEqual(app.read().unresolved, []);
  // The pass drawing that reading still reads the thread as the user's gesture, and
  // its proof moves nothing a paint reads.
  assert.deepEqual(app.read().effective.thread.gestured, ["e1"]);
  const adopted = app.read();
  app.present([logged]);
  assert.equal(app.read(), adopted);
  // The next reading is news like any other.
  app.adopt(state(3));
  assert.deepEqual(app.read().effective.thread.gestured, []);
});

// Whether the user's comment still counts as their gesture in its thread, after each
// step: held news shows in that thread until a pass has drawn the reading logging it.
const settling = [
  {
    name: "a reading the page failed to draw, and its retry",
    steps: ["accept", "log", "log", "present", "log"],
    gestured: [true, true, true, true, false],
  },
  {
    name: "an acceptance after a reading logged it, before the pass",
    steps: ["log", "accept", "present", "log"],
    gestured: [true, true, true, false],
  },
  {
    name: "an acceptance after the pass drew the reading logging it",
    steps: ["log", "present", "accept"],
    gestured: [true, true, false],
  },
];
for (const { name, steps, gestured } of settling)
  test(`a settled comment's thread stays gestured until it is drawn: ${name}`, () => {
    const app = setup();
    const comment = { kind: "comment", attempt: "note", text: "Note", revision: 1 };
    app.enqueue(comment, "now");
    const logged = { ...comment, id: "e1", seq: 1, author: "user", ts: "now" };
    let taken = 1;
    const signals = {
      accept: () => app.accept("note", logged),
      log: () => {
        const reading = state(++taken);
        reading.browser.receipts = [logged];
        reading.browser.views[1].thread.threads = [servedThread([logged])];
        app.adopt(reading);
      },
      present: () => app.present([logged]),
    };
    steps.forEach((signal, index) => {
      signals[signal]();
      assert.equal(
        app.read().effective.thread.gestured.length > 0,
        gestured[index],
        `after ${steps.slice(0, index + 1).join(", ")}`,
      );
    });
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
  test(`a pending user reply leaves ${resolved ? "a resolved" : "an open"} question's turn to the log`, () => {
    const app = setup();
    const root = {
      kind: "comment",
      id: "question",
      author: "agent",
      text: "Which one?",
      ts: "now",
    };
    // The server owes nobody a turn in a resolved thread; an open one waits on the
    // user's answer.
    const owed = resolved ? null : "needs_user";
    const accepted = state(2);
    accepted.browser.views[1].thread.threads = [
      servedThread([root], {
        resolved,
        attention: resolved
          ? null
          : { kind: "needs_user", reason: "obligation", workflow: null },
      }),
    ];
    app.adopt(accepted);
    const turn = () => {
      const thread = app.read().effective.thread.all[0];
      return [thread.attention?.kind ?? null, thread.resolved];
    };
    assert.deepEqual(turn(), [owed, resolved]);

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
    assert.deepEqual(turn(), [owed, null]);
    const answer = { kind: "reply", attempt: "answer", id: "e-answer" };
    app.accept("answer", answer);
    const logged = state(3);
    logged.browser.receipts = [answer];
    logged.browser.views[1].thread.threads = accepted.browser.views[1].thread.threads;
    app.adopt(logged);
    assert.deepEqual(app.read().unresolved, []);
    assert.deepEqual(turn(), [owed, resolved]);

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

test("a pending gesture leaves obligations and On me as served until the log answers", () => {
  // A settling reaction answered the agent's question, so the server lists the obligation as
  // done. Which obligations taking it back reopens is the log's reading, so On me moves
  // when the server answers the undo, not before.
  const item = {
    kind: "comment",
    id: "question",
    author: "agent",
    text: "Keep this chart?",
    ts: "now",
  };
  const kept = {
    kind: "reply",
    id: "kept",
    parent: item.id,
    author: "user",
    token: "keep",
    ts: "now",
  };
  const app = setup();
  const accepted = state(2, [kept]);
  const answered = {
    id: `message:${item.id}`,
    source: { kind: "message", id: item.id },
    thread: item.id,
    message: item.id,
    prompt: { text: item.text, target: null },
    answer: { value: { token: "keep" }, event: kept },
    status: "answered",
    next_actor: null,
  };
  accepted.browser.views[1].obligations = [answered];
  const done = {
    ...servedObligationRow(answered, {
      kind: "message",
      subject: { kind: "thread", id: item.id },
    }),
    state: "done",
    ended: null,
    detail: null,
  };
  accepted.browser.views[1].queues = { ...obligationQueues([]), done: [done] };
  accepted.browser.views[1].thread.threads = [servedThread([item, kept])];
  app.adopt(accepted);

  app.enqueue({ kind: "undo", undoes: kept.id, attempt: "take-back" }, "now");
  const pending = app.read().effective;
  assert.deepEqual(pending.obligations.user, []);
  assert.deepEqual(pending.queues.on_user, []);
  assert.deepEqual(
    pending.queues.done.map(({ kind, id }) => [kind, id]),
    [["message", answered.id]],
  );

  const reopened = { ...answered, answer: null, status: "open", next_actor: "user" };
  const undo = { kind: "undo", id: "e-undo", undoes: kept.id, attempt: "take-back" };
  const answeredUndo = state(3, [kept, undo]);
  answeredUndo.browser.views[1].obligations = [reopened];
  answeredUndo.browser.views[1].queues = {
    ...obligationQueues([]),
    on_user: [
      servedObligationRow(reopened, {
        kind: "message",
        subject: { kind: "thread", id: item.id },
      }),
    ],
  };
  answeredUndo.browser.views[1].thread.threads = [
    servedThread([item], {
      attention: { kind: "needs_user", reason: "obligation", workflow: null },
    }),
  ];
  app.adopt(answeredUndo);
  const { thread, queues } = app.read().effective;
  assert.equal(thread.all[0].attention.kind, "needs_user");
  assert.deepEqual(
    queues.on_user.map(({ kind, id }) => [kind, id]),
    [["message", answered.id]],
  );
});

test("the publisher carries the server's obligation reading, page obligations before thread obligations", () => {
  const app = capture();
  // The authored document names the obligation, but only the log's reading says whether it
  // still stands, so neither the wait for that reading nor an offline page lists it.
  for (const phase of ["waiting", "offline"]) {
    app.setPhase(phase);
    assert.deepEqual(app.read().effective.obligations.all, []);
  }

  const read = state(2);
  const page = wireObligation("question", "lf-ask", "choice", "lf-choice");
  const frozen = {
    ...wireObligation("frozen-ask", "lf-ask", "frozen-choice", "lf-choice", "root-1"),
    status: "withdrawn",
    next_actor: null,
  };
  read.browser.views[1].obligations = [page, frozen];
  app.adopt(read);

  const record = page;
  assert.deepEqual(app.read().effective.obligations, {
    phase: "ready",
    all: [record, frozen],
    user: [record],
    unanswered: [record],
  });
  assert.throws(() => {
    app.read().effective.obligations.all[0].source.id = "other";
  }, TypeError);

  // A local gesture does not edit the reading: the user sees their answer in the
  // widget's own state at once, while the log answers which obligations still stand in the
  // state this POST returns.
  app.enqueue(action("answer"), "now");
  assert.deepEqual(
    app.read().effective.obligations.user.map(({ source }) => source.id),
    ["choice"],
  );
  assert.equal(decision(app), "accept");
});

test("an unsettled report supplies desired widget state", () => {
  const valueSpec = {
    unit: "widget",
    record: { kind: "value", attr: "choice" },
  };
  const source = {
    ...descriptor,
    declaration: {
      properties: { choice: { type: "string" } },
      "x-state": { preview: { ...valueSpec, writer: "agent" } },
    },
  };
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
  document.descriptors.set("choice", {
    ...descriptor,
    declaration,
    document: { kind: "page", revision: 2 },
  });
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
  document.descriptors.set("choice", {
    ...descriptor,
    declaration: document.registry["lf-choice"],
    document: { kind: "page", revision: 2 },
  });
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
  document.descriptors.set("choice", {
    ...descriptor,
    declaration,
    document: { kind: "page", revision: 2 },
  });
  document.authored.get("choice").specs.set("decide", agentSpec);
  const reading = state(2);
  reading.active.revision = 2;
  reading.browser.views[2] = reading.browser.views[1];
  reading.browser.views[2].basis.revision = 2;
  assert.equal(app.adopt(reading, document), true);
  assert.equal(decision(app), null);
  assert.equal(app.read().unresolved.length, 1);
});

test("An obligation contains the local typed answer while completion waits for admission", () => {
  const declared = {
    ...descriptor,
    declaration: {
      ...descriptor.declaration,
      "x-awaits": { value: "decide", answered: { decide: {} } },
    },
  };
  const app = capture([[declared.id, declared]]);
  const reading = state(2);
  const item = wireObligation("choice-context", "lf-context", "choice", "lf-choice");
  reading.browser.views[1].obligations = [item];
  reading.browser.views[1].queues = obligationQueues([item]);
  app.adopt(reading);
  assert.equal(app.read().effective.obligations.all[0].answer, null);
  app.enqueue(action("typed"), "now");
  const pending = app.read().effective.obligations;
  assert.deepEqual(pending.all[0].answer, {
    value: { outcome: "accept" },
    event: null,
  });
  assert.equal(pending.all[0].status, "open");
  assert.equal(pending.all[0], pending.user[0]);
  assert.equal(pending.all[0], pending.unanswered[0]);
  assert.equal(app.read().effective.queues.on_user[0].kind, "widget");
  app.refuse("typed");
  assert.equal(app.read().effective.obligations.all[0].answer, null);
});

test("empty completed answer and wrapper changes preserve obligation identity", () => {
  const choose = {
    unit: "widget",
    writer: "user",
    record: { kind: "attribute", attr: "chosen" },
  };
  const declared = {
    ...descriptor,
    declaration: {
      "x-state": { choose },
      "x-awaits": { value: "choose", answered: { choose: {} } },
    },
  };
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
  const item = {
    ...wireObligation("choice", "lf-choice"),
    status: "answered",
    next_actor: null,
    answer: { value: [], event: null },
  };
  reading.browser.views[1].obligations = [item];
  reading.browser.views[1].queues = obligationQueues([item]);
  app.adopt(reading);
  assert.deepEqual(app.read().effective.obligations.all[0].answer.value, []);
  assert.equal(app.read().effective.queues.on_user.length, 0);
  assert.equal(app.read().effective.queues.done[0].kind, "widget");
  const wrapped = structuredClone(reading);
  wrapped.taken = 3;
  wrapped.browser.views[1].obligations[0].prompt.target = "new-context";
  app.adopt(wrapped);
  assert.equal(app.read().effective.obligations.all[0].id, "widget:choice");
  assert.equal(app.read().effective.obligations.all[0].prompt.target, "new-context");
});

test("pending undo removes completed empty obligation values and refusal restores them", () => {
  for (const [record, value] of [
    [{ kind: "attribute", attr: "chosen" }, []],
    [{ kind: "body" }, ""],
  ]) {
    const choose = { unit: "widget", writer: "user", record };
    const answer = { unit: "widget", writer: "user" };
    const declared = {
      ...descriptor,
      declaration: {
        "x-state": { choose, answer },
        "x-awaits": { value: "choose", answered: { answer: {} } },
      },
    };
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
    const item = {
      ...wireObligation("choice", "lf-choice"),
      status: "answered",
      next_actor: null,
      answer: { value, event: accepted },
    };
    reading.browser.views[1].obligations = [item];
    reading.browser.views[1].queues = obligationQueues([item]);
    app.adopt(reading);
    assert.deepEqual(app.read().effective.obligations.all[0].answer.value, value);
    app.enqueue({ kind: "undo", undoes: accepted.id, attempt: "undo-empty" }, "now");
    assert.equal(app.read().effective.obligations.all[0].status, "answered");
    assert.equal(app.read().effective.obligations.all[0].answer, null);
    assert.equal(app.read().effective.queues.done[0].obligation.answer, null);
    app.refuse("undo-empty");
    assert.deepEqual(app.read().effective.obligations.all[0].answer.value, value);
  }
});

test("pending undo withdraws a decision an earlier Leaf recorded with another field", () => {
  const declared = {
    ...descriptor,
    declaration: {
      ...descriptor.declaration,
      "x-awaits": { value: "decide", answered: { decide: {} } },
    },
  };
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
  reading.browser.views[1].obligations = [
    {
      ...wireObligation("choice", "lf-choice"),
      status: "answered",
      next_actor: null,
      answer: { value: { outcome: "accept" }, event: accepted },
    },
  ];
  app.adopt(reading);
  app.enqueue({ kind: "undo", undoes: accepted.id, attempt: "undo-earlier" }, "now");
  assert.equal(app.read().effective.obligations.all[0].answer, null);
});

test("pending undo removes a custom obligation answer before authoritative completion changes", () => {
  const declared = {
    ...descriptor,
    declaration: {
      ...descriptor.declaration,
      "x-awaits": { value: "decide", answered: { decide: {} } },
    },
  };
  const app = capture([[declared.id, declared]]);
  const accepted = { ...action("decided"), id: "e1", seq: 1 };
  const reading = state(2, [accepted]);
  const item = {
    ...wireObligation("choice", "lf-choice"),
    status: "answered",
    next_actor: null,
    answer: { value: { outcome: "accept" }, event: accepted },
  };
  reading.browser.views[1].obligations = [item];
  reading.browser.views[1].queues = obligationQueues([item]);
  app.adopt(reading);
  assert.deepEqual(app.read().effective.obligations.all[0].answer.value, {
    outcome: "accept",
  });
  app.enqueue({ kind: "undo", undoes: accepted.id, attempt: "undo-answer" }, "now");
  const pending = app.read().effective.obligations.all[0];
  assert.equal(pending.status, "answered");
  assert.equal(pending.answer, null);
  assert.equal(app.read().effective.queues.done[0].obligation.answer, null);
  app.refuse("undo-answer");
  assert.deepEqual(app.read().effective.obligations.all[0].answer.value, {
    outcome: "accept",
  });
  app.enqueue(action("re-pick", "reject"), "now");
  assert.deepEqual(app.read().effective.obligations.all[0].answer, {
    value: { outcome: "reject" },
    event: null,
  });
  app.refuse("re-pick");
  assert.equal(app.read().effective.obligations.all[0].answer.event.id, accepted.id);
});

test("unchanged selection republishes when a move changes its members", () => {
  const move = {
    unit: "unit",
    writer: "user",
    record: { kind: "position", within: "lf-audit-lane" },
  };
  const choose = {
    unit: "widget",
    writer: "user",
    record: { kind: "attribute", attr: "selected" },
  };
  const declared = (id, tag, verbs, parent = null) => ({
    ...descriptor,
    id,
    tag,
    declaration: { "x-state": verbs },
    parent: parent && { id: parent, tag: "lf-audit-manifest" },
    ancestors: [],
  });
  const board = declared("manifest", "lf-audit-manifest", { move });
  const north = declared("north", "lf-audit-lane", { choose }, "manifest");
  const south = declared("south", "lf-audit-lane", { choose }, "manifest");
  const cargo = declared("cargo", "lf-audit-cargo", {}, "north");
  const baseline = (owner, value) => [
    owner.id,
    {
      tag: owner.tag,
      specs: new Map([["choose", choose]]),
      state: { choose: { action: null, value, detail: { value } } },
    },
  ];
  const app = setup(
    [board, north, south, cargo].map((owner) => [owner.id, owner]),
    [
      [
        board.id,
        {
          tag: board.tag,
          specs: new Map([["move", move]]),
          state: {
            move: {
              value: { north: ["cargo"], south: [] },
              units: {},
              ranks: { cargo: "1" },
            },
          },
        },
      ],
      baseline(north, ["cargo"]),
      baseline(south, []),
    ],
  );
  const destination = app.selectWidget(south);
  const before = destination.read().state;
  let paints = 0;
  const stop = destination.subscribe(() => paints++);
  const placed = app.enqueue(
    {
      kind: "action",
      widget: "manifest",
      action: "move",
      detail: { unit: "cargo", value: "south", rank: "1" },
      revision: 1,
      attempt: "move",
    },
    "now",
  );
  assert.equal(paints, 2);
  assert.deepEqual(destination.read().memberships, { selected: ["cargo"] });
  assert.deepEqual(destination.read().state, before);
  app.enqueue({ kind: "undo", undoes: placed.localId, attempt: "undo" }, "now");
  assert.equal(paints, 3);
  assert.deepEqual(destination.read().memberships, { selected: [] });
  stop();
});

test("parent memberships include flat creations until undone", () => {
  const sow = {
    unit: "seed",
    writer: "user",
    creates: { child: "lf-seedling", words: "label" },
  };
  const choose = {
    unit: "widget",
    writer: "user",
    record: { kind: "attribute", attr: "chosen" },
  };
  const tray = {
    ...descriptor,
    id: "tray",
    tag: "lf-tray",
    declaration: { "x-state": { sow, choose } },
  };
  const app = setup(
    [[tray.id, tray]],
    [
      [
        tray.id,
        {
          tag: tray.tag,
          specs: new Map([
            ["sow", sow],
            ["choose", choose],
          ]),
          state: {
            sow: { value: {}, units: {} },
            choose: { action: null, value: [], detail: { value: [] } },
          },
        },
      ],
    ],
  );
  const selected = app.selectWidget(tray);
  const created = app.enqueue(
    {
      kind: "action",
      revision: 1,
      widget: "tray",
      action: "sow",
      detail: { seed: "elm", label: "Elm" },
      attempt: "sow-elm",
    },
    "now",
  );
  assert.deepEqual(selected.read().memberships.chosen, ["elm"]);
  app.enqueue({ kind: "undo", undoes: created.localId, attempt: "undo-sow" }, "now");
  assert.deepEqual(selected.read().memberships.chosen, []);
});
