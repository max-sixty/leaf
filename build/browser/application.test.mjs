import assert from "node:assert/strict";
import test from "node:test";
import { createSemanticApplication } from "./application.ts";
import { createPresentationCoordinator } from "./presentation.ts";
import { stateDefinition } from "../../skills/leaf/assets/runtime/registry-contract.js";
import {
  servedGestureSequence,
  servedReading,
  servedThread,
  servedWorkflow,
} from "../../tests/served.mjs";

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
// The Question reading `served_state` sends, in its own wire spelling.
const noQuestions = () => ({
  all: [],
  user: [],
  unanswered: [],
});
const wireQuestion = (
  target,
  tag,
  source = target,
  sourceTag = tag,
  thread = null,
) => ({
  id: `widget:${source}`,
  source: { kind: "widget", id: source, tag: sourceTag },
  thread,
  prompt: { text: null, target },
  answer: null,
  status: "open",
  next_actor: "user",
});
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
  events,
  workflows: [],
  activity: { phase: "user", held: false },
  reading: `reading-${taken}`,
  browser: {
    basis: { through_seq: events.length },
    receipts: events,
    thread: { threads: [], projection: empty(), questions: noQuestions() },
    views: {
      1: {
        basis: { revision: 1, through_seq: events.length },
        coverage: [],
        document: {
          questions: noQuestions(),
          projection: {
            entries: events.map((event) => ({
              event: {
                ...event,
                meaning: {
                  ...event.meaning,
                  state:
                    event.meaning?.state ??
                    stateDefinition("lf-choice", descriptor.declaration, spec),
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
    registry: Object.fromEntries([
      ["lf-choice", { "x-state": { decide: { ...spec, writer: "user" } } }],
      ...extraDescriptors.map(([, captured]) => [captured.tag, captured.declaration]),
    ]),
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

  let release;
  const held = new Promise((resolve) => {
    release = resolve;
  });
  let presentation;
  let nested = false;
  app
    .select((root) => root.phase)
    .subscribe((phase) => {
      if (phase !== "offline" || nested) return;
      nested = true;
      assert.equal(coordinator.read().semanticEpoch, 1);
      const renderer = coordinator.attach("widget", {});
      presentation = renderer.present("offline", held);
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
  release("proof");
  await presentation;
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
  const question = servedReading("approval").views["1"].document.questions.all[0];
  reading.browser.views[1].document.questions = {
    all: [question],
    user: [question],
    unanswered: [question],
  };
  app.adopt(reading);

  const effective = app.read().effective;
  assert.deepEqual(Object.keys(effective.thread.collection), ["phase", "threads"]);
  assert.deepEqual(effective.questions.all, [question]);
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
  reading.browser.thread.threads = [
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
      { attention: { kind: "needs_user", reason: "question", workflow: null } },
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
    reason: "question",
    workflow: null,
  });
  assert.equal(thread.workflows.length, 2);
  app.enqueue(
    { kind: "reply", parent: "root", attempt: "local", text: "Third", revision: 1 },
    "2026-09-22T10:02:00-07:00",
  );
  // The user's own send hands the thread to the agent until the log answers it.
  assert.deepEqual(app.read().effective.thread.all[0].attention, {
    kind: "waiting",
    reason: "workflow",
    workflow: "pending:local",
  });
});

test("local delivery supplies and can override non-Ask thread attention", () => {
  const app = setup();
  const reading = state(2);
  reading.browser.thread.threads = [
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
  assert.deepEqual(app.read().effective.thread.all[0].attention, {
    kind: "waiting",
    reason: "workflow",
    workflow: "pending:local",
  });
  app.refuse("local");
  assert.deepEqual(app.read().effective.thread.all[0].attention, {
    kind: "needs_user",
    reason: "recovery",
    workflow: "rejected:local",
  });

  const acceptedApp = setup();
  const acceptedReading = structuredClone(reading);
  acceptedReading.workflows = [threadWorkflow("accepted-send")];
  acceptedReading.browser.thread.threads[0].attention = {
    kind: "waiting",
    reason: "workflow",
    workflow: "accepted-send",
  };
  acceptedApp.adopt(acceptedReading);
  acceptedApp.enqueue(
    { kind: "reply", parent: "root", attempt: "next", text: "Third", revision: 1 },
    "2026-09-22T10:02:00-07:00",
  );
  assert.deepEqual(acceptedApp.read().effective.thread.all[0].attention, {
    kind: "waiting",
    reason: "workflow",
    workflow: "pending:next",
  });
  acceptedApp.refuse("next");
  assert.deepEqual(acceptedApp.read().effective.thread.all[0].attention, {
    kind: "needs_user",
    reason: "recovery",
    workflow: "rejected:next",
  });
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
  reading.browser.thread.threads = [
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
  edited.browser.thread.threads[0].unread = [
    { message: "agent-root", version: "edit-2" },
  ];
  app.adopt(edited);
  app.markRead(original);
  assert.equal(thread().msgs[0].unread, true);
});

test("semantic epochs include visible revision facts but not transport metadata", () => {
  const app = setup();
  const asked = state(2);
  const choice = wireQuestion("choice", "lf-choice");
  asked.browser.views[1].document.questions = {
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
  revisionFacts.browser.views[1].updates = [
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
  const projection = app.projectView(
    historical.browser.views[1],
    historical.browser.thread,
  );
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
      registry: { "lf-draft": declaration },
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
  assert.equal(app.nameUndo("undo", [accepted]), true);
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
      reading.browser.thread.threads = [servedThread([logged])];
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
  const app = setup();
  const comment = {
    kind: "comment",
    attempt: "comment",
    text: "Keep this",
    revision: 1,
  };
  app.enqueue(comment, "now");
  assert.equal(app.read().effective.thread.all[0].root.text, "Keep this");
  const accepted = { ...comment, id: "e1", author: "user", ts: "now" };
  const read = state(2);
  read.browser.receipts = [accepted];
  read.browser.thread.threads = [servedThread([accepted])];
  app.adopt(read);
  app.accept("comment", accepted);
  assert.equal(app.read().effective.thread.all.length, 1);
  assert.equal(app.read().unresolved.length, 1);
  app.present([accepted]);
  assert.equal(app.read().unresolved.length, 0);
  assert.equal(app.read().effective.thread.all[0].root.id, "e1");
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
  accepted.browser.thread.threads = [servedThread([root], { seat: descriptor.id })];
  app.adopt(accepted);
  assert.equal(selected.read().thread.heldBy, accepted.browser.thread.threads[0].id);

  const released = state(3);
  released.browser.thread.threads = [
    { ...accepted.browser.thread.threads[0], resolved: { author: "user" } },
  ];
  app.adopt(released);
  assert.equal(selected.read().thread.heldBy, null);
});

for (const resolved of [null, { author: "user" }]) {
  test(`a pending user reply hands ${resolved ? "a resolved" : "an open"} question to the agent until it leaves`, () => {
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
    const standing = resolved ? null : "needs_user";
    const accepted = state(2);
    accepted.browser.thread.threads = [
      servedThread([root], {
        resolved,
        user_prompt: resolved ? null : { message: root.id, version: root.id },
        attention: resolved
          ? null
          : { kind: "needs_user", reason: "question", workflow: null },
      }),
    ];
    app.adopt(accepted);
    const turn = () => {
      const thread = app.read().effective.thread.all[0];
      return [thread.attention?.kind ?? null, thread.resolved];
    };
    assert.deepEqual(turn(), [standing, resolved]);

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
    assert.deepEqual(turn(), ["waiting", null]);
    const answer = { kind: "reply", attempt: "answer", id: "e-answer" };
    app.accept("answer", answer);
    app.present([answer]);
    assert.deepEqual(app.read().unresolved, []);
    assert.deepEqual(turn(), [standing, resolved]);

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
    assert.deepEqual(turn(), ["waiting", null]);
    app.refuse("retry");
    assert.deepEqual(turn(), ["needs_user", resolved]);
  });
}

test("a pending prose reply does not hide a frozen structural Ask", () => {
  const root = {
    kind: "comment",
    id: "question",
    author: "agent",
    text: "Choose in the options below.",
    ts: "now",
  };
  const app = setup();
  const accepted = state(2);
  const frozen = wireQuestion(
    "frozen-ask",
    "lf-ask",
    "frozen-choice",
    "lf-choice",
    root.id,
  );
  accepted.browser.thread.questions = {
    all: [frozen],
    user: [frozen],
    unanswered: [frozen],
  };
  accepted.browser.thread.threads = [
    servedThread([root], {
      attention: { kind: "needs_user", reason: "question", workflow: null },
    }),
  ];
  app.adopt(accepted);

  app.enqueue(
    {
      kind: "reply",
      parent: root.id,
      attempt: "context",
      text: "One more detail before I choose.",
      revision: 1,
    },
    "now",
  );
  // The Ask the thread carries is still the user's, so the obligation does not turn
  // over and back when the reply lands.
  const thread = app.read().effective.thread.all[0];
  assert.deepEqual(thread.attention, {
    kind: "needs_user",
    reason: "question",
    workflow: null,
  });
});

test("a thread whose opening message the log lost is known by its id, not its root", () => {
  // `build_threads` keeps such a thread under the lost id and gives it the surviving
  // reply as its root, which is the message a reply to it names.
  const kept = {
    kind: "reply",
    id: "kept",
    parent: "lost",
    author: "agent",
    text: "Which repair?",
    ts: "now",
  };
  const served = (asks) => {
    const reading = state(2);
    reading.browser.thread.questions = { all: asks, user: asks, unanswered: asks };
    reading.browser.thread.threads = [
      servedThread([kept], {
        id: "lost",
        attention: asks.length
          ? { kind: "needs_user", reason: "question", workflow: null }
          : null,
      }),
    ];
    return reading;
  };
  const app = setup();
  const thread = () => app.read().effective.thread.all[0];
  app.adopt(served([wireQuestion("repair", "lf-ask", "pick", "lf-choice", "lost")]));
  assert.deepEqual([thread().id, thread().root.id], ["lost", "kept"]);
  assert.deepEqual(thread().attention, {
    kind: "needs_user",
    reason: "question",
    workflow: null,
  });

  app.adopt(served([]));
  app.enqueue(
    { kind: "reply", parent: "kept", attempt: "answer", text: "Retry.", revision: 1 },
    "now",
  );
  assert.deepEqual(
    thread().workflows.map((workflow) => [workflow.id, workflow.subject.id]),
    [["pending:answer", "lost"]],
  );
  app.refuse("answer");
  assert.deepEqual(thread().attention, {
    kind: "needs_user",
    reason: "recovery",
    workflow: "rejected:answer",
  });
});

test("a pending resend replaces accepted recovery until refusal", () => {
  const app = setup();
  const root = {
    kind: "comment",
    id: "question",
    author: "user",
    text: "Try this?",
    ts: "now",
  };
  const accepted = state(2);
  accepted.browser.thread.threads = [
    servedThread([root], {
      attention: {
        kind: "needs_user",
        reason: "recovery",
        workflow: "failed-response",
      },
    }),
  ];
  accepted.workflows = [
    threadWorkflow("failed-response", {
      thread: root.id,
      stage: "answered",
      condition: { kind: "failed", operation: "response" },
      next_actor: "user",
    }),
  ];
  app.adopt(accepted);

  app.enqueue(
    {
      kind: "reply",
      parent: root.id,
      attempt: "retry",
      text: "Try it again.",
      revision: 1,
    },
    "now",
  );
  assert.deepEqual(app.read().effective.thread.all[0].attention, {
    kind: "waiting",
    reason: "workflow",
    workflow: "pending:retry",
  });
  app.refuse("retry");
  assert.deepEqual(app.read().effective.thread.all[0].attention, {
    kind: "needs_user",
    reason: "recovery",
    workflow: "failed-response",
  });
});

test("the publisher carries the server's Ask reading, page asks before thread asks", () => {
  const app = capture();
  // The authored document names the Ask, but only the log's reading says whether it
  // still stands, so neither the wait for that reading nor an offline page lists it.
  for (const phase of ["waiting", "offline"]) {
    app.setPhase(phase);
    assert.deepEqual(app.read().effective.questions.all, []);
  }

  const read = state(2);
  const page = wireQuestion("question", "lf-ask", "choice", "lf-choice");
  const frozen = wireQuestion(
    "frozen-ask",
    "lf-ask",
    "frozen-choice",
    "lf-choice",
    "root-1",
  );
  read.browser.views[1].document.questions = {
    all: [page],
    user: [page],
    unanswered: [page],
  };
  read.browser.thread.questions = {
    all: [frozen],
    user: [],
    unanswered: [],
  };
  app.adopt(read);

  const record = page;
  assert.deepEqual(app.read().effective.questions, {
    phase: "ready",
    all: [record, frozen],
    user: [record],
    unanswered: [record],
  });
  assert.throws(() => {
    app.read().effective.questions.all[0].source.id = "other";
  }, TypeError);

  // A local gesture does not edit the reading: the user sees their answer in the
  // widget's own state at once, while the log answers which Asks still stand in the
  // state this POST returns.
  app.enqueue(action("answer"), "now");
  assert.deepEqual(
    app.read().effective.questions.user.map(({ source }) => source.id),
    ["choice"],
  );
  assert.equal(decision(app), "accept");
});

test("a standing report supplies desired widget state", () => {
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
    state: stateDefinition(source.tag, source.declaration, valueSpec),
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
  accepted.browser.thread.threads = [servedThread([root], { bare_reaction: true })];

  app.adopt(accepted);
  assert.equal(app.read().effective.thread.all[0].attention, null);
});

test("a Done this tab sends ends its task at once, and its undo puts the task back", () => {
  // The task the agent put on the user, as the server serves it.
  const task = servedReading("queues on both sides").tasks.find(
    (candidate) => candidate.ends === "done",
  );
  const onYou = (app) => app.read().effective.queues.onYou.map(({ id }) => id);
  const done = (app) =>
    app.read().effective.queues.done.map(({ id, state }) => [id, state]);

  const app = setup();
  const open = state(2);
  open.browser.tasks = [task];
  open.browser.ended_tasks = [];
  app.adopt(open);
  assert.deepEqual(onYou(app), [task.id]);
  app.enqueue(
    { kind: "task_end", task: task.id, outcome: "done", attempt: "done" },
    "now",
  );
  assert.deepEqual(onYou(app), []);
  assert.deepEqual(done(app), [[task.id, "done"]]);
  // A refused Done puts the task back as the log has it.
  app.refuse("done");
  assert.equal(onYou(app)[0], task.id);
  assert.deepEqual(done(app), []);

  const later = setup();
  const ended = state(2);
  ended.browser.tasks = [];
  ended.browser.ended_tasks = [
    { ...task, state: "done", outcome: { ...task.outcome, id: "e20", ts: "now" } },
  ];
  later.adopt(ended);
  assert.deepEqual(onYou(later), []);
  later.enqueue({ kind: "undo", undoes: "e20", attempt: "undo" }, "now");
  assert.deepEqual(onYou(later), [task.id]);
  assert.deepEqual(done(later), []);
});

test("approval leaves Questions in its sending turn and undo restores the exact version", () => {
  const wire = servedReading("approval");
  const question = wire.views["1"].document.questions.all.find(
    (candidate) => candidate.source.kind === "approval",
  );
  const app = setup();
  const reading = state(2);
  reading.browser.views[1].document.questions = {
    all: [question],
    user: [question],
    unanswered: [question],
  };
  app.adopt(reading);
  const questions = () => app.read().effective.queues.onYou;
  const record = () => app.read().effective.questions.all[0];
  assert.equal(questions()[0].id, question.id);
  assert.equal(questions()[0].kind, "question");
  assert.equal(questions()[0].offers.done, false);
  app.enqueue({ kind: "done", version: 2, attempt: "other-version" }, "now");
  assert.equal(questions().length, 1);
  app.enqueue({ kind: "done", version: 1, attempt: "approve" }, "now");
  assert.equal(questions().length, 0);
  assert.deepEqual(record().answer, { value: true, event: null });
  assert.equal(record().status, "answered");
  app.refuse("approve");
  assert.equal(questions().length, 1);
  assert.equal(record().answer, null);
  const accepted = state(3);
  accepted.browser.views[1].document.questions = {
    all: [
      {
        ...question,
        status: "answered",
        next_actor: null,
        answer: {
          value: true,
          event: {
            id: "approval-event",
            kind: "done",
            seq: 3,
            ts: "now",
            author: "user",
          },
        },
      },
    ],
    user: [],
    unanswered: [],
  };
  const previousApproval = {
    id: "previous-approval",
    kind: "done",
    version: 0,
    ts: "before",
  };
  const currentApproval =
    accepted.browser.views[1].document.questions.all[0].answer.event;
  accepted.browser.thread.approval_history = [previousApproval, currentApproval];
  app.adopt(accepted);
  assert.deepEqual(app.read().effective.thread.approvalHistory, [
    previousApproval,
    currentApproval,
  ]);
  assert.equal(questions().length, 0);
  app.enqueue({ kind: "undo", undoes: "approval-event", attempt: "undo" }, "now");
  assert.equal(questions()[0].id, question.id);
  assert.equal(record().answer, null);
  assert.equal(record().status, "open");
  assert.deepEqual(app.read().effective.thread.approvalHistory, [previousApproval]);
});

test("a revision preserves pending delivery while replacing incompatible speculative state", () => {
  const app = setup();
  const pending = app.enqueue(action("old"), "now");
  app.enqueue({ kind: "undo", undoes: pending.localId, attempt: "undo-old" }, "now");
  const document = structuredClone(app.read().document);
  document.revision = 2;
  const revisedSpec = { ...spec, record: { kind: "value", attr: "status" } };
  const declaration = {
    properties: { status: { type: "integer" } },
    "x-state": { decide: revisedSpec },
  };
  document.registry["lf-choice"] = declaration;
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

test("a revision changing a verb's writer retains delivery without drawing the old user gesture", () => {
  const app = setup();
  app.enqueue(action("old-user"), "now");
  assert.equal(decision(app), "accept");
  const document = structuredClone(app.read().document);
  document.revision = 2;
  const agentSpec = { ...spec, writer: "agent" };
  const declaration = { "x-state": { decide: agentSpec } };
  document.registry["lf-choice"] = declaration;
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

test("Question contains the local typed answer while completion waits for admission", () => {
  const declared = {
    ...descriptor,
    declaration: {
      ...descriptor.declaration,
      "x-awaits": { value: "decide", answered: { decide: {} } },
    },
  };
  const app = capture([[declared.id, declared]]);
  const reading = state(2);
  const question = wireQuestion("choice-context", "lf-context", "choice", "lf-choice");
  reading.browser.views[1].document.questions = {
    all: [question],
    user: [question],
    unanswered: [question],
  };
  app.adopt(reading);
  assert.equal(app.read().effective.questions.all[0].answer, null);
  app.enqueue(action("typed"), "now");
  const pending = app.read().effective.questions;
  assert.deepEqual(pending.all[0].answer, {
    value: { outcome: "accept" },
    event: null,
  });
  assert.equal(pending.all[0].status, "open");
  assert.equal(pending.all[0], pending.user[0]);
  assert.equal(pending.all[0], pending.unanswered[0]);
  assert.equal(app.read().effective.queues.onYou[0].kind, "question");
  app.refuse("typed");
  assert.equal(app.read().effective.questions.all[0].answer, null);
});

test("empty completed answer and wrapper changes preserve Question identity", () => {
  const choose = { unit: "widget", record: { kind: "attribute", attr: "chosen" } };
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
  const question = {
    ...wireQuestion("choice", "lf-choice"),
    status: "answered",
    next_actor: null,
    answer: { value: [], event: null },
  };
  reading.browser.views[1].document.questions = {
    all: [question],
    user: [],
    unanswered: [],
  };
  app.adopt(reading);
  assert.deepEqual(app.read().effective.questions.all[0].answer.value, []);
  assert.equal(app.read().effective.queues.onYou.length, 0);
  assert.equal(app.read().effective.queues.done[0].kind, "question");
  const wrapped = structuredClone(reading);
  wrapped.taken = 3;
  wrapped.browser.views[1].document.questions.all[0].prompt.target = "new-context";
  app.adopt(wrapped);
  assert.equal(app.read().effective.questions.all[0].id, "widget:choice");
  assert.equal(app.read().effective.questions.all[0].prompt.target, "new-context");
});

test("pending undo removes a custom Question answer before authoritative completion changes", () => {
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
  const question = {
    ...wireQuestion("choice", "lf-choice"),
    status: "answered",
    next_actor: null,
    answer: { value: { outcome: "accept" }, event: accepted },
  };
  reading.browser.views[1].document.questions = {
    all: [question],
    user: [],
    unanswered: [],
  };
  app.adopt(reading);
  assert.deepEqual(app.read().effective.questions.all[0].answer.value, {
    outcome: "accept",
  });
  app.enqueue({ kind: "undo", undoes: accepted.id, attempt: "undo-answer" }, "now");
  const pending = app.read().effective.questions.all[0];
  assert.equal(pending.status, "answered");
  assert.equal(pending.answer, null);
  assert.equal(app.read().effective.queues.done[0].question.answer, null);
  app.refuse("undo-answer");
  assert.deepEqual(app.read().effective.questions.all[0].answer.value, {
    outcome: "accept",
  });
  app.enqueue(action("re-pick", "reject"), "now");
  assert.deepEqual(app.read().effective.questions.all[0].answer, {
    value: { outcome: "reject" },
    event: null,
  });
  app.refuse("re-pick");
  assert.equal(app.read().effective.questions.all[0].answer.event.id, accepted.id);
});

test("pending prose answer changes next actor without suppressing inventory or settling", () => {
  const root = {
    kind: "comment",
    id: "prose",
    author: "agent",
    text: "Which?",
    ts: "now",
  };
  const earlier = { ...root, id: "earlier" };
  const app = setup();
  const reading = state(2);
  const prose = (message, actor) => ({
    id: `reply:${message.id}`,
    source: { kind: "reply", id: message.id },
    thread: root.id,
    prompt: { text: message.text, target: message.id },
    answer: null,
    status: "open",
    next_actor: actor,
  });
  const current = prose(root, "user");
  const suppressed = prose(earlier, null);
  reading.browser.thread.questions = {
    all: [suppressed, current],
    user: [current],
    unanswered: [suppressed, current],
  };
  reading.browser.thread.threads = [
    servedThread([root], {
      attention: { kind: "needs_user", reason: "question", workflow: null },
    }),
  ];
  app.adopt(reading);
  app.enqueue(
    {
      kind: "reply",
      parent: root.id,
      attempt: "prose-answer",
      text: "First.",
      revision: 1,
    },
    "now",
  );
  const pending = app.read().effective.questions;
  assert.equal(pending.all.length, 2);
  assert.equal(pending.all[1].status, "open");
  assert.equal(pending.all[1].next_actor, "agent");
  assert.deepEqual(pending.user, []);
  assert.equal(app.read().effective.queues.onYou.length, 0);
  app.refuse("prose-answer");
  assert.equal(app.read().effective.questions.user[0].id, "reply:prose");
});
