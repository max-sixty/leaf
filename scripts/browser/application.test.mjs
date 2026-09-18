import assert from "node:assert/strict";
import test from "node:test";
import { createSemanticApplication } from "./application.ts";
import { createPresentationCoordinator } from "./presentation.ts";

const spec = { unit: "widget", facet: "decision" };
const descriptor = {
  id: "choice",
  tag: "lf-choice",
  document: { kind: "page", revision: 1 },
  declaration: { "x-state": { accept: spec, reject: spec } },
  parent: null,
  ancestors: [],
  quoted: false,
  bindings: {},
  offers: [],
};
const empty = () => ({ entries: [], actions: [], reports: [], desired: [] });
const coordinate = ["choice", "choice", "decision"];
const action = (attempt, action = "accept") => ({
  kind: "action",
  widget: "choice",
  action,
  detail: {},
  revision: 1,
  attempt,
});
const state = (taken, events = []) => ({
  taken,
  layer: { generation: "test" },
  active: { revision: 1 },
  events,
  activity: { phase: "reader", held: false },
  reading: `reading-${taken}`,
  browser: {
    basis: { through_seq: events.length },
    receipts: events,
    conversation: { threads: [], projection: empty() },
    views: {
      1: {
        basis: { revision: 1, through_seq: events.length },
        coverage: [],
        document: {
          projection: {
            entries: events.map((event) => ({
              event,
              coordinate: [event.widget, event.widget, "decision"],
              spec,
              scope: "page",
              value: event.action,
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
const capture = (extraDescriptors = [], extraAuthored = []) => {
  const app = createSemanticApplication();
  app.identify(1);
  app.captureDocument({
    ...app.read().document,
    registry: Object.fromEntries([
      ["lf-choice", { "x-state": { accept: spec, reject: spec } }],
      ...extraDescriptors.map(([, captured]) => [captured.tag, captured.declaration]),
    ]),
    authored: new Map([
      [
        "choice",
        {
          tag: "lf-choice",
          specs: new Map([["decision", spec]]),
          positions: {},
          state: { decision: { action: null, value: null, detail: {} } },
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
const decision = (app) =>
  app.read().effective.widgets.get("choice").state.decision.action;

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
      app.acceptData({ revision: 0, sources: {} });
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
    .select((root) => root.effective.widgets.get("choice").state.decision.action)
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
    app.read().unresolved[1].event.action = "accept";
  }, TypeError);
  app.reject("later");
  assert.equal(decision(app), "accept");
});

test("one widget selection publishes optimistic state and delivery without writable access", () => {
  const app = setup();
  const selected = app.selectWidget(descriptor);
  const seen = [];
  const stop = selected.subscribe((reading) => seen.push(reading));
  assert.equal(selected.read().actions.accept.available, true);
  assert.equal(selected.read().authored.decision.action, null);
  app.enqueue(action("first"), "now");
  assert.equal(selected.read().authored.decision.action, null);
  assert.equal(selected.read().state.decision.action, "accept");
  assert.deepEqual(selected.read().delivery, [
    {
      attempt: "first",
      kind: "action",
      verb: "accept",
      answered: false,
      rejected: false,
    },
  ]);
  assert.equal(seen.at(-1).actions.accept.standing[0].event.attempt, "first");
  assert.throws(() => {
    selected.read().actions.accept.available = false;
  }, TypeError);
  assert.throws(() => {
    selected.read().authored.decision.value = "corrupt";
  }, TypeError);
  const beforeUnrelated = seen.length;
  app.acceptData({ revision: 0, sources: { unrelated: { value: true } } });
  assert.equal(seen.length, beforeUnrelated);
  app.reject("first");
  assert.equal(selected.read().state.decision.action, null);
  stop();
});

test("an offline document publishes every host command as unavailable", () => {
  const commands = {
    ...descriptor,
    declaration: {
      ...descriptor.declaration,
      "x-request": { verbs: { run: {} } },
    },
    offers: [{ tag: "lf-command", attribute: "verb", verb: "run" }],
  };
  const app = setup([[commands.id, commands]]);
  const pending = app.enqueue(action("first"), "now");
  assert.equal(app.selectWidget(commands).read().actions.accept.available, true);
  assert.equal(app.selectWidget(commands).read().requests.run.available, true);
  assert.equal(
    app.selectWidget(commands).read().actions.accept.undo[0].id,
    pending.localId,
  );

  app.setHostAvailable(false);
  const reading = app.selectWidget(commands).read();
  assert.equal(reading.actions.accept.available, false);
  assert.equal(reading.actions.accept.unavailable, "no agent or server is available");
  assert.equal(reading.requests.run.available, false);
  assert.equal(reading.requests.run.unavailable, "no agent or server is available");
  assert.deepEqual(reading.actions.accept.undo, []);
  assert.equal(reading.state.decision.action, "accept");
});

test("an owner requirement follows publisher-projected position with authored fallback", () => {
  const oldOwner = {
    ...descriptor,
    id: "old-column",
    tag: "lf-column",
    declaration: { "x-awaits": { rollup: true } },
  };
  const newOwner = { ...oldOwner, id: "new-column" };
  const required = {
    ...descriptor,
    id: "required-choice",
    parent: { id: newOwner.id, tag: newOwner.tag },
    ancestors: [{ id: newOwner.id, tag: newOwner.tag }],
    declaration: {
      ...descriptor.declaration,
      "x-awaits": { answers: ["accept", "reject"] },
    },
    ask: { answers: ["accept", "reject"], empty: {} },
  };
  const child = {
    ...descriptor,
    id: "card",
    tag: "lf-card",
    parent: { id: oldOwner.id, tag: oldOwner.tag },
    ancestors: [{ id: oldOwner.id, tag: oldOwner.tag }],
    declaration: {
      "x-owners": ["lf-column"],
      "x-state": {
        choose: {
          ...spec,
          requires: { target: "owner", awaiting: true },
        },
      },
    },
  };
  const app = setup([
    [oldOwner.id, oldOwner],
    [newOwner.id, newOwner],
    [required.id, required],
    [child.id, child],
  ]);
  const moved = {
    ...action("move", "move"),
    id: "e-move",
    seq: 1,
    widget: child.id,
    detail: { parent: newOwner.id },
  };
  const position = {
    unit: "widget",
    facet: "position",
    record: { kind: "position", value: "parent" },
  };
  const read = state(2, [moved]);
  read.browser.views[1].document.projection = {
    entries: [
      {
        event: moved,
        coordinate: [child.id, child.id, position.facet],
        spec: position,
        scope: "page",
        value: newOwner.id,
      },
    ],
    actions: [moved.id],
    reports: [],
    desired: [moved.id],
  };
  app.adopt(read);
  assert.equal(app.selectWidget(child).read().actions.choose.available, true);
});

test("widget undo candidates name only exact currently standing attempts", () => {
  const app = setup();
  const selected = app.selectWidget(descriptor);
  const pending = app.enqueue(action("first"), "now");
  assert.equal(selected.read().actions.accept.undo[0].attempt, "first");
  assert.equal(selected.read().actions.accept.undo[0].id, pending.localId);
  app.enqueue({ kind: "undo", undoes: pending.localId, attempt: "undo" }, "now");
  assert.deepEqual(selected.read().actions.accept.undo, []);
});

test("widget action history excludes terminal coverage records", () => {
  const app = setup();
  const terminal = { ...action("old"), id: "e-old", seq: 1 };
  const read = state(2);
  read.browser.views[1].coverage = [{ event: terminal, coordinate: null }];
  app.adopt(read);
  assert.deepEqual(app.selectWidget(descriptor).read().actions.accept.history, []);
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
      .actions.accept.history.map(({ id }) => id),
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

test("document capture and its matching admitted reading publish atomically", () => {
  const app = setup();
  const seen = [];
  app
    .select((root) => [
      root.document.revision,
      root.authoritative?.active.revision ?? null,
      root.document.descriptors.get("next")?.document.revision ?? null,
      root.document.authored.has("next"),
      root.effective.widgets.get("next")?.state.decision.action ?? null,
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
          specs: new Map([["decision", spec]]),
          positions: {},
          state: { decision: { action: null, value: null, detail: {} } },
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

test("accepted reading order includes non-event activity and independent source revisions", () => {
  const app = setup();
  const newer = { ...state(3), activity: { phase: "agent", held: true } };
  assert.equal(app.adopt(newer), true);
  assert.equal(app.adopt(state(2)), false);
  assert.equal(app.read().authoritative.reading, "reading-3");
  assert.deepEqual(app.read().effective.activity, newer.activity);
  const before = app.read().semanticEpoch;
  assert.equal(app.acceptData({ revision: 2, sources: { input: { value: 5 } } }), true);
  assert.equal(app.acceptData({ revision: 1, sources: {} }), false);
  assert.ok(app.read().semanticEpoch > before);
  assert.equal(app.read().data.sources.input.value, 5);
});

test("semantic epochs include visible revision facts but not transport metadata", () => {
  const app = setup();
  const lifecycle = state(2);
  lifecycle.browser.views[1].document.requests = [
    {
      seat: { document: { kind: "page", revision: 1 }, widget: "choice" },
      phase: "failed",
    },
  ];
  const before = app.read().semanticEpoch;
  app.adopt(lifecycle);
  assert.ok(app.read().semanticEpoch > before);

  const beforeRevisionFacts = app.read().semanticEpoch;
  const revisionFacts = structuredClone(lifecycle);
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
  assert.equal(
    app.read().effective.publishedAt,
    revisionFacts.browser.views[1].published_at,
  );
  assert.deepEqual(
    app.read().effective.updates,
    revisionFacts.browser.views[1].updates,
  );

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
    historical.browser.conversation,
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
  assert.equal(app.selectWidgets([]).get("choice").state.decision.action, null);
  assert.equal(app.selectWidgets(["e1"]).get("choice").state.decision.action, "accept");
  assert.equal(app.selectWidgets(null).get("choice").state.decision.action, "accept");
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
  app.accountPresented([accepted]);
  app.remove(new Set(["first"]));
  assert.equal(decision(app), null);
  assert.equal(app.nameUndo("undo", [accepted]), true);
  assert.equal(app.entry("undo").event.undoes, "e1");
});

test("conversation acceptance is semantic before presentation can retire its local handle", () => {
  const app = setup();
  const comment = {
    kind: "comment",
    attempt: "comment",
    text: "Keep this",
    revision: 1,
  };
  app.enqueue(comment, "now");
  assert.equal(app.read().effective.conversation.all[0].root.text, "Keep this");
  const accepted = { ...comment, id: "e1", author: "user", ts: "now" };
  const read = state(2);
  read.browser.receipts = [accepted];
  read.browser.conversation.threads = [{ root: accepted, msgs: [], resolved: false }];
  app.adopt(read);
  app.accept("comment", accepted);
  assert.equal(app.read().effective.conversation.all.length, 1);
  assert.equal(app.read().unresolved.length, 1);
  app.accountPresented([accepted]);
  assert.equal(app.read().unresolved.length, 0);
  assert.equal(app.read().effective.conversation.all[0].root.id, "e1");
});

test("widget selections publish the canonical held conversation", () => {
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
  accepted.browser.conversation.threads = [
    {
      root,
      anchor: null,
      msgs: [root],
      resolved: null,
      awaits_agent: true,
      awaits_reader: false,
      bare_reaction: false,
      seat: descriptor.id,
    },
  ];
  app.adopt(accepted);
  assert.equal(selected.read().conversation.heldBy, root.id);

  const released = state(3);
  released.browser.conversation.threads = [
    { ...accepted.browser.conversation.threads[0], resolved: { author: "user" } },
  ];
  app.adopt(released);
  assert.equal(selected.read().conversation.heldBy, null);
});

test("a pending reader reply hands an accepted question to the agent until it leaves", () => {
  const app = setup();
  const root = {
    kind: "comment",
    id: "question",
    author: "agent",
    text: "Which one?",
    ts: "now",
  };
  const accepted = state(2);
  accepted.browser.conversation.threads = [
    {
      root,
      anchor: null,
      msgs: [root],
      resolved: null,
      awaits_agent: false,
      awaits_reader: true,
      bare_reaction: false,
      seat: null,
    },
  ];
  app.adopt(accepted);
  const turn = () => {
    const thread = app.read().effective.conversation.all[0];
    return [thread.awaits_agent, thread.awaits_reader];
  };
  assert.deepEqual(turn(), [false, true]);

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
  assert.deepEqual(turn(), [true, false]);
  app.remove(new Set(["answer"]));
  assert.deepEqual(turn(), [false, true]);

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
  assert.deepEqual(turn(), [true, false]);
  app.reject("retry");
  assert.deepEqual(turn(), [false, true]);
});

test("a pending prose reply preserves a frozen structural Ask", () => {
  const root = {
    kind: "comment",
    id: "question",
    author: "agent",
    text: "Choose in the options below.",
    ts: "now",
  };
  const frozenChoice = {
    ...descriptor,
    id: "frozen-choice",
    document: { kind: "thread", thread: root.id, message: root.id },
    declaration: {
      ...descriptor.declaration,
      "x-awaits": { answers: ["accept", "reject"] },
    },
    ask: { answers: ["accept", "reject"], empty: {} },
  };
  const app = setup([[frozenChoice.id, frozenChoice]]);
  const accepted = state(2);
  accepted.browser.conversation.threads = [
    {
      root,
      anchor: null,
      msgs: [root],
      resolved: null,
      awaits_agent: false,
      awaits_reader: true,
      bare_reaction: false,
      seat: null,
    },
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
  const thread = app.read().effective.conversation.all[0];
  assert.deepEqual([thread.awaits_agent, thread.awaits_reader], [true, true]);
});

test("one publisher reading owns Ask inventory, source identity, and pending answers", () => {
  const surface = {
    ...descriptor,
    id: "question",
    tag: "lf-ask",
    declaration: { "x-ask-surface": true },
  };
  const source = {
    ...descriptor,
    parent: { id: surface.id, tag: surface.tag },
    ancestors: [{ id: surface.id, tag: surface.tag }],
    declaration: {
      ...descriptor.declaration,
      "x-awaits": { answers: ["accept", "reject"], all: "accept" },
    },
    ask: { answers: ["accept", "reject"], empty: {} },
  };
  const app = capture([
    [surface.id, surface],
    [source.id, source],
  ]);
  // The authored document names the Ask, but only the log's reading says whether it
  // still stands, so neither the wait for that reading nor an offline page lists it.
  for (const phase of ["waiting", "offline"]) {
    app.setPhase(phase);
    assert.deepEqual(app.read().effective.asks.all, []);
    assert.deepEqual(app.read().effective.asks.awaiting, {});
  }
  app.adopt(state(2));
  assert.deepEqual(app.read().effective.asks, {
    all: [
      {
        id: surface.id,
        tag: surface.tag,
        sourceId: source.id,
        sourceTag: source.tag,
        thread: null,
      },
    ],
    reader: [
      {
        id: surface.id,
        tag: surface.tag,
        sourceId: source.id,
        sourceTag: source.tag,
        thread: null,
      },
    ],
    unanswered: [
      {
        id: surface.id,
        tag: surface.tag,
        sourceId: source.id,
        sourceTag: source.tag,
        thread: null,
      },
    ],
    awaiting: { [source.id]: true },
    unansweredAwaiting: { [source.id]: true },
  });

  const pending = app.enqueue(action("answer"), "now");
  assert.deepEqual(app.read().effective.asks.reader, []);
  assert.deepEqual(app.read().effective.asks.unanswered, []);
  assert.equal(app.read().effective.admittedUnansweredAsks[0].sourceId, source.id);
  assert.equal(app.read().effective.asks.unansweredAwaiting[source.id], false);
  assert.throws(() => {
    app.read().effective.asks.all[0].sourceId = "other";
  }, TypeError);

  app.enqueue({ kind: "undo", undoes: pending.localId, attempt: "undo-answer" }, "now");
  assert.equal(app.read().effective.asks.reader[0].sourceId, source.id);
  assert.equal(app.read().effective.asks.unansweredAwaiting[source.id], true);
});

test("request Asks cross local Ask ancestors into their nearest rollup", () => {
  const plan = {
    ...descriptor,
    id: "plan",
    tag: "lf-plan",
    declaration: { "x-awaits": { rollup: true } },
  };
  const local = {
    ...descriptor,
    id: "local-choice",
    parent: { id: plan.id, tag: plan.tag },
    ancestors: [{ id: plan.id, tag: plan.tag }],
    declaration: {
      ...descriptor.declaration,
      "x-awaits": { answers: ["accept", "reject"] },
    },
    ask: { answers: ["accept", "reject"], empty: {} },
  };
  const request = {
    ...descriptor,
    id: "run-request",
    tag: "lf-request",
    parent: { id: local.id, tag: local.tag },
    ancestors: [
      { id: local.id, tag: local.tag },
      { id: plan.id, tag: plan.tag },
    ],
    declaration: { "x-request": { ask: true, verbs: { run: {} } } },
    ask: null,
  };
  const app = setup(
    [
      [plan.id, plan],
      [local.id, local],
      [request.id, request],
    ],
    [
      [
        local.id,
        {
          tag: local.tag,
          specs: new Map([["decision", spec]]),
          positions: {},
          state: { decision: { action: null, value: null, detail: {} } },
        },
      ],
    ],
  );

  app.enqueue({ ...action("answer-local"), widget: local.id }, "now");
  assert.deepEqual(
    app.read().effective.asks.reader.map(({ sourceId }) => sourceId),
    [request.id],
  );
  assert.equal(app.read().effective.asks.awaiting[local.id], false);
  assert.equal(app.read().effective.asks.awaiting[plan.id], true);
});

test("quoted and retired Asks are absent from their rollup's effective reading", () => {
  const plan = {
    ...descriptor,
    id: "plan",
    tag: "lf-plan",
    declaration: { "x-awaits": { rollup: true } },
  };
  const ask = (id, extra = {}) => ({
    ...descriptor,
    id,
    parent: { id: plan.id, tag: plan.tag },
    ancestors: [{ id: plan.id, tag: plan.tag }],
    declaration: {
      ...descriptor.declaration,
      "x-awaits": { answers: ["accept", "reject"] },
    },
    ask: { answers: ["accept", "reject"], empty: {} },
    ...extra,
  });
  const quoted = ask("quoted-choice", { quoted: true });
  const retired = ask("retired-choice", {
    retiredBy: [{ ownerId: descriptor.id, outcome: "accept" }],
  });
  const app = setup([
    [plan.id, plan],
    [quoted.id, quoted],
    [retired.id, retired],
  ]);
  app.enqueue(action("retire-child"), "now");

  assert.deepEqual(app.read().effective.asks.all, []);
  assert.equal(app.read().effective.asks.awaiting[quoted.id], false);
  assert.equal(app.read().effective.asks.awaiting[retired.id], false);
  assert.equal(app.read().effective.asks.awaiting[plan.id], false);
});

test("a pending frozen-widget answer updates its thread obligation immediately", () => {
  const root = {
    kind: "comment",
    id: "thread-root",
    author: "user",
    text: "Please propose a choice.",
    ts: "now",
  };
  const reply = {
    kind: "reply",
    id: "choice-reply",
    parent: root.id,
    author: "agent",
    text: "Choose one.",
    ts: "now",
  };
  const frozen = {
    ...descriptor,
    id: "frozen-choice",
    document: { kind: "thread", thread: root.id, message: reply.id },
    declaration: {
      ...descriptor.declaration,
      "x-awaits": { answers: ["accept", "reject"] },
    },
    ask: { answers: ["accept", "reject"], empty: {} },
  };
  const authored = {
    tag: "lf-choice",
    specs: new Map([["decision", spec]]),
    positions: {},
    state: { decision: { action: null, value: null, detail: {} } },
  };
  const app = setup([[frozen.id, frozen]], [[frozen.id, authored]]);
  const accepted = state(2);
  accepted.browser.conversation.threads = [
    {
      root,
      anchor: null,
      msgs: [root, reply],
      resolved: null,
      awaits_agent: false,
      awaits_reader: true,
      bare_reaction: false,
      seat: null,
    },
  ];
  app.adopt(accepted);
  assert.equal(app.read().effective.conversation.all[0].awaits_reader, true);

  app.enqueue({ ...action("answer-frozen"), widget: frozen.id }, "now");
  assert.deepEqual(app.read().effective.asks.reader, []);
  assert.equal(app.read().effective.conversation.all[0].awaits_reader, false);
});

test("a reaction root is not a spoken turn awaiting the reader", () => {
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
  accepted.browser.conversation.threads = [
    {
      root,
      anchor: null,
      msgs: [root],
      resolved: null,
      awaits_agent: false,
      awaits_reader: false,
      bare_reaction: true,
      seat: null,
    },
  ];

  app.adopt(accepted);
  assert.equal(app.read().effective.conversation.all[0].awaits_reader, false);
});

test("projected value records open and restore a conditional Ask", () => {
  const phaseSpec = {
    unit: "widget",
    facet: "phase",
    record: { kind: "value", attr: "phase", value: "phase" },
  };
  const closeSpec = { unit: "widget", facet: "decision" };
  const conditional = {
    ...descriptor,
    id: "conditional-choice",
    tag: "lf-conditional-choice",
    declaration: {
      "x-state": { open: phaseSpec, close: closeSpec },
      "x-awaits": { when: { phase: ["open"] }, answers: ["close"] },
    },
    ask: {
      authored: { phase: "closed" },
      when: { phase: ["open"] },
      answers: ["close"],
      until: null,
      empty: {},
    },
  };
  const authored = {
    tag: conditional.tag,
    specs: new Map([
      ["phase", phaseSpec],
      ["decision", closeSpec],
    ]),
    positions: {},
    state: {
      phase: { action: null, value: "closed", detail: {} },
      decision: { action: null, value: null, detail: {} },
    },
  };
  const app = setup([[conditional.id, conditional]], [[conditional.id, authored]]);
  const sources = () =>
    app.read().effective.asks.reader.map(({ sourceId }) => sourceId);
  const event = (attempt) => ({
    kind: "action",
    widget: conditional.id,
    action: "open",
    detail: { phase: "open" },
    revision: 1,
    attempt,
  });

  assert.deepEqual(sources(), []);
  app.enqueue(event("open"), "now");
  assert.deepEqual(sources(), [conditional.id]);
  app.reject("open");
  assert.deepEqual(sources(), []);

  const pending = app.enqueue(event("open-again"), "now");
  assert.deepEqual(sources(), [conditional.id]);
  app.enqueue({ kind: "undo", undoes: pending.localId, attempt: "undo" }, "now");
  assert.deepEqual(sources(), []);
  app.reject("undo");
  assert.deepEqual(sources(), [conditional.id]);
});

test("a live revision's authored conversation predicate controls Ask handoff", () => {
  const decisionSpec = { unit: "widget", facet: "decision" };
  const source = {
    ...descriptor,
    id: "conditional-seat",
    tag: "lf-conditional-seat",
    declaration: {
      "x-state": { settle: decisionSpec },
      "x-awaits": { when: { asks: [true] }, answers: ["settle"] },
      "x-conversation": { when: { talk: [true] } },
    },
    ask: {
      authored: { asks: "" },
      when: { asks: [true] },
      answers: ["settle"],
      until: null,
      empty: {},
    },
    conversation: {
      authored: { talk: "" },
      when: { talk: [true] },
    },
  };
  const app = setup([[source.id, source]]);
  const accepted = state(2);
  accepted.browser.conversation.threads = [
    {
      root: { kind: "comment", id: "seated", author: "user", text: "Why?" },
      anchor: null,
      msgs: [],
      resolved: null,
      awaits_agent: true,
      awaits_reader: false,
      bare_reaction: false,
      seat: source.id,
    },
  ];
  app.adopt(accepted);
  const readerSources = () =>
    app.read().effective.asks.reader.map(({ sourceId }) => sourceId);

  assert.deepEqual(readerSources(), []);
  const revised = {
    ...source,
    document: { kind: "page", revision: 2 },
    conversation: {
      authored: { talk: null },
      when: { talk: [true] },
    },
  };
  const revisedState = structuredClone(accepted);
  revisedState.taken = 3;
  revisedState.active.revision = 2;
  revisedState.browser.views[2] = structuredClone(revisedState.browser.views[1]);
  revisedState.browser.views[2].basis.revision = 2;
  app.adopt(revisedState, {
    ...app.read().document,
    revision: 2,
    descriptors: new Map([[revised.id, revised]]),
  });
  assert.deepEqual(readerSources(), [source.id]);
});

test("a frozen Ask selects its completion verb from projected values", () => {
  const phaseSpec = {
    unit: "widget",
    facet: "phase",
    record: { kind: "value", attr: "phase", value: "phase" },
  };
  const chooseSpec = { unit: "widget", facet: "decision" };
  const finishSpec = {
    unit: "widget",
    facet: "completion",
    record: { kind: "value", attr: "choice", value: "choice" },
  };
  const root = {
    kind: "comment",
    id: "batch-question",
    author: "agent",
    text: "Choose the batch.",
    ts: "now",
  };
  const frozen = {
    ...descriptor,
    id: "batch-choice",
    tag: "lf-batch-choice",
    document: { kind: "thread", thread: root.id, message: root.id },
    declaration: {
      "x-state": {
        batch: phaseSpec,
        choose: chooseSpec,
        finish: finishSpec,
      },
      "x-awaits": {
        answers: ["choose"],
        until: { verb: "finish", when: { phase: ["batch"] } },
      },
    },
    ask: {
      authored: { phase: "single" },
      when: {},
      answers: ["choose"],
      until: { verb: "finish", when: { phase: ["batch"] } },
      empty: {},
    },
  };
  const authored = {
    tag: frozen.tag,
    specs: new Map([
      ["phase", phaseSpec],
      ["decision", chooseSpec],
      ["completion", finishSpec],
    ]),
    positions: {},
    state: {
      phase: { action: null, value: "single", detail: {} },
      decision: { action: null, value: null, detail: {} },
      completion: { action: null, value: "already", detail: { choice: "already" } },
    },
  };
  const app = setup([[frozen.id, frozen]], [[frozen.id, authored]]);
  const accepted = state(2);
  accepted.browser.conversation.threads = [
    {
      root,
      anchor: null,
      msgs: [root],
      resolved: null,
      awaits_agent: false,
      awaits_reader: true,
      bare_reaction: false,
      seat: null,
    },
  ];
  app.adopt(accepted);
  const isOpen = () =>
    app.read().effective.asks.reader.some(({ sourceId }) => sourceId === frozen.id);
  const send = (attempt, action, detail = {}) =>
    app.enqueue(
      {
        kind: "action",
        widget: frozen.id,
        action,
        detail,
        revision: 1,
        attempt,
      },
      "now",
    );

  assert.equal(isOpen(), true);
  send("batch", "batch", { phase: "batch" });
  send("choose", "choose");
  assert.equal(isOpen(), true);
  send("finish", "finish", { choice: "" });
  assert.equal(isOpen(), false);
});

test("a report on an answer facet does not answer an Ask", () => {
  const valueSpec = {
    unit: "widget",
    facet: "decision",
    record: { kind: "value", attr: "choice", value: "choice" },
  };
  const source = {
    ...descriptor,
    declaration: {
      "x-state": { accept: valueSpec },
      "x-report": { preview: valueSpec },
      "x-awaits": { answers: ["accept"] },
    },
    ask: { answers: ["accept"], empty: {} },
  };
  const app = setup([[source.id, source]]);
  const accepted = state(2);
  const report = {
    kind: "report",
    widget: source.id,
    action: "preview",
    detail: { choice: "reported" },
    revision: 1,
    id: "report-1",
    seq: 1,
  };
  accepted.events = [report];
  accepted.browser.basis.through_seq = 1;
  accepted.browser.receipts = [report];
  accepted.browser.views[1].basis.through_seq = 1;
  accepted.browser.views[1].document.projection = {
    entries: [
      {
        event: report,
        coordinate,
        spec: valueSpec,
        scope: "page",
        value: "reported",
      },
    ],
    actions: [],
    reports: [report.id],
    desired: [report.id],
  };

  app.adopt(accepted);
  assert.equal(
    app.read().effective.widgets.get(source.id).state.decision.action,
    "preview",
  );
  assert.deepEqual(
    app.read().effective.asks.reader.map(({ id }) => id),
    [source.id],
  );
  assert.deepEqual(
    app.read().effective.asks.unanswered.map(({ id }) => id),
    [source.id],
  );
});

test("superseding an outer settlement restores a nested Ask from captured ancestry", () => {
  const source = {
    ...descriptor,
    id: "nested-choice",
    declaration: {
      ...descriptor.declaration,
      "x-awaits": { answers: ["accept", "reject"] },
    },
    retiredBy: [{ ownerId: descriptor.id, outcome: "accept" }],
    ask: { answers: ["accept", "reject"], empty: {} },
  };
  const app = setup([[source.id, source]]);
  const settlement = { ...action("settle"), id: "settled", seq: 1 };
  const accepted = state(2, [settlement]);
  app.adopt(accepted);
  assert.deepEqual(app.read().effective.asks.all, []);

  app.enqueue(action("choose-other", "reject"), "now");
  assert.deepEqual(
    app.read().effective.asks.all.map(({ id }) => id),
    [source.id],
  );
  app.remove(new Set(["choose-other"]));
  assert.deepEqual(app.read().effective.asks.all, []);

  app.enqueue(
    { kind: "undo", undoes: settlement.id, attempt: "restore-nested" },
    "now",
  );
  assert.deepEqual(
    app.read().effective.asks.all.map(({ id }) => id),
    [source.id],
  );
  assert.deepEqual(
    app.read().effective.asks.reader.map(({ id }) => id),
    [source.id],
  );
});

test("a pending reply moves the Ask worklist in the same publication as its thread", () => {
  const source = {
    ...descriptor,
    declaration: {
      ...descriptor.declaration,
      "x-awaits": { answers: ["accept", "reject"] },
      "x-conversation": { when: {} },
    },
    ask: { answers: ["accept", "reject"], empty: {} },
    conversation: { authored: {}, when: {} },
  };
  const app = setup([[source.id, source]]);
  const root = {
    kind: "comment",
    id: "question",
    author: "agent",
    text: "Which one?",
    ts: "now",
  };
  const accepted = state(2);
  accepted.browser.conversation.threads = [
    {
      root,
      anchor: null,
      msgs: [root],
      resolved: null,
      awaits_agent: false,
      awaits_reader: true,
      bare_reaction: false,
      seat: source.id,
    },
  ];
  app.adopt(accepted);
  assert.equal(app.read().effective.asks.reader.length, 1);

  app.enqueue(
    {
      kind: "reply",
      parent: root.id,
      attempt: "answer-in-words",
      text: "The first one.",
      revision: 1,
    },
    "now",
  );
  assert.equal(app.read().effective.conversation.all[0].awaits_agent, true);
  assert.deepEqual(app.read().effective.asks.reader, []);
  assert.equal(app.read().effective.asks.unanswered.length, 1);
});
