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
              coordinate,
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
const setup = () => {
  const app = createSemanticApplication();
  app.identify(1);
  app.captureAuthored(
    new Map([
      [
        "choice",
        {
          tag: "lf-choice",
          specs: new Map([["decision", spec]]),
          positions: {},
          state: { decision: { action: null, value: null, detail: {} } },
        },
      ],
    ]),
    { "lf-choice": { "x-state": { accept: spec, reject: spec } } },
  );
  app.captureDescriptors(new Map([[descriptor.id, descriptor]]));
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
  app.enqueue(action("first"), "now");
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
  const beforeUnrelated = seen.length;
  app.captureDescriptors(
    new Map([
      [
        "other",
        {
          ...descriptor,
          id: "other",
          tag: "lf-other",
          declaration: {},
        },
      ],
    ]),
  );
  assert.equal(seen.length, beforeUnrelated);
  app.reject("first");
  assert.equal(selected.read().state.decision.action, null);
  stop();
});

test("an offline document publishes every host command as unavailable", () => {
  const app = setup();
  const commands = {
    ...descriptor,
    declaration: {
      ...descriptor.declaration,
      "x-request": { verbs: { run: {} } },
    },
    offers: [{ tag: "lf-command", attribute: "verb", verb: "run" }],
  };
  app.captureDescriptors(new Map([[commands.id, commands]]));
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
  const app = setup();
  const oldOwner = {
    ...descriptor,
    id: "old-column",
    tag: "lf-column",
    declaration: {},
  };
  const newOwner = { ...oldOwner, id: "new-column" };
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
  app.captureDescriptors(
    new Map([
      [oldOwner.id, oldOwner],
      [newOwner.id, newOwner],
      [child.id, child],
    ]),
  );
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
  read.browser.views[1].document.asks = {
    unanswered_awaiting: { [oldOwner.id]: false, [newOwner.id]: true },
  };
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
  app.identify(2);
  app.captureDescriptors(new Map([[current.id, current]]));
  const carried = { ...action("old"), id: "e-old", seq: 1, revision: 1 };
  const read = state(2, [carried]);
  read.active.revision = 2;
  read.browser.views[2] = read.browser.views[1];
  read.browser.views[2].basis.revision = 2;
  delete read.browser.views[1];
  app.adopt(read);
  assert.deepEqual(
    app
      .selectWidget(current)
      .read()
      .actions.accept.history.map(({ id }) => id),
    ["e-old"],
  );
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
  assert.equal(app.read().effective.publishedAt, revisionFacts.browser.views[1].published_at);
  assert.deepEqual(app.read().effective.updates, revisionFacts.browser.views[1].updates);

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
