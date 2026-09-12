import assert from "node:assert/strict";
import test from "node:test";
import { createSemanticApplication } from "./application.ts";

const spec = { unit: "widget", facet: "decision" };
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
  app.adopt(state(1));
  return app;
};
const decision = (app) =>
  app.read().effective.widgets.get("choice").state.decision.action;

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
