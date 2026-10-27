import assert from "node:assert/strict";
import test from "node:test";
import { effect, signal } from "/vendor/signals-core.js";
import {
  createApplicationPublisher,
  share,
} from "../../browser/runtime/framework/snapshot.js";
import { createPresentationCoordinator } from "../../browser/runtime/framework/presentation.js";

for (const kind of ["semantic", "presentation"]) {
  test(`${kind} observers own their reads during registration and notification`, () => {
    const initial = {
      document: {},
      authoritative: null,
      unresolved: [],
      effective: { count: 0 },
      semanticEpoch: 0,
    };
    const app = createApplicationPublisher(initial);
    const part = app.select((root) => root.authoritative);
    const clock = signal(7);
    const coordinator = createPresentationCoordinator({
      reportFailure: (reason) => {
        throw reason;
      },
    });
    coordinator.begin({}, 0);
    const selected = app.select((root) => {
      part.read();
      clock.value;
      return root.effective.count;
    });
    const source = kind === "semantic" ? selected : coordinator;
    const ownReads = [];
    const observe = () => {
      // The observer can read the whole root outside its own paint collection.
      assert.equal(app.read().document, initial.document);
      part.read();
      clock.value;
      ownReads.push([part.read(), clock.value]);
    };
    let subscriptions = 0;
    let stopSource;
    const stop = effect(() => {
      subscriptions++;
      stopSource = source.subscribe(observe);
    });
    if (kind === "semantic") {
      app.publish({ ...initial, effective: { count: 1 }, semanticEpoch: 1 });
    } else {
      coordinator.attach("unrelated", {});
    }
    assert.equal(
      subscriptions,
      1,
      "observer reads do not subscribe the registering effect",
    );
    assert.ok(ownReads.length >= 2);
    assert.deepEqual(ownReads, [
      [null, 7],
      [null, 7],
    ]);
    stopSource();
    stop();
  });
}

test("publisher replaces one immutable reading before subscribers run", () => {
  const activity = { state: "waiting" };
  const initial = {
    document: { revision: 1 },
    authoritative: { activity, through: 0 },
    unresolved: [],
    effective: { decision: "open" },
    semanticEpoch: 0,
  };
  const publisher = createApplicationPublisher(initial);
  const decision = publisher.select((state) => state.effective.decision);
  const delivery = publisher.select((state) => state.unresolved.length);
  const seen = [];
  const dispose = decision.subscribe((value) =>
    seen.push([value, delivery.read(), publisher.read().semanticEpoch]),
  );
  const pending = {
    ...initial,
    unresolved: [{ attempt: "choose-a" }],
    effective: { decision: "a" },
    semanticEpoch: 1,
  };

  assert.equal(publisher.publish(pending), pending);
  assert.deepEqual(seen, [
    ["open", 0, 0],
    ["a", 1, 1],
  ]);
  assert.equal(publisher.read().authoritative.activity, activity);
  assert.throws(() => {
    publisher.read().unresolved[0].attempt = "corrupt";
  }, TypeError);
  assert.throws(() => {
    publisher.read().effective.decision = "corrupt";
  }, TypeError);
  publisher.publish({
    ...pending,
    unresolved: [],
    authoritative: { activity, through: 1 },
  });
  assert.equal(seen.length, 2);
  assert.equal(delivery.read(), 0);
  dispose();
  publisher.publish({ ...initial, semanticEpoch: 2 });
  assert.equal(seen.length, 2);
  assert.equal(decision.read(), "open");
});

test("publisher shares unchanged subtrees, so a selection hears only its own part move", () => {
  const initial = {
    document: { revision: 1 },
    authoritative: {},
    unresolved: [],
    effective: {
      thread: { all: [{ id: "t1", words: ["hello"] }] },
      widgets: new Map([["board", { state: { column: "todo" } }]]),
    },
    semanticEpoch: 0,
  };
  const publisher = createApplicationPublisher(initial);
  const thread = publisher.select((root) => root.effective.thread);
  const pair = publisher.select((root) => [
    root.effective.thread.all[0],
    root.document.revision,
  ]);
  const heard = [];
  thread.subscribe((value) => heard.push(["thread", value]));
  pair.subscribe((value) => heard.push(["pair", value]));
  const initialThread = thread.read();
  const initialPair = pair.read();
  publisher.publish({
    ...initial,
    effective: {
      thread: { all: [{ id: "t1", words: ["hello"] }] },
      widgets: new Map([["board", { state: { column: "done" } }]]),
    },
  });
  assert.equal(thread.read(), initialThread);
  assert.equal(pair.read(), initialPair);
  assert.equal(heard.length, 2);
  publisher.publish({
    ...initial,
    effective: {
      thread: { all: [{ id: "t1", words: ["hello", "again"] }] },
      widgets: new Map([["board", { state: { column: "done" } }]]),
    },
  });
  assert.notEqual(thread.read(), initialThread);
  assert.deepEqual(
    heard.slice(2).map(([name]) => name),
    ["thread", "pair"],
  );
});

test("sharing keeps a JSON field named __proto__ an own field", () => {
  const prior = JSON.parse('{"kept": {"a": 1}, "__proto__": {"x": 1}}');
  const next = JSON.parse('{"kept": {"a": 1}, "__proto__": {"x": 2}}');
  const shared = share(prior, next);
  assert.equal(Object.getPrototypeOf(shared), Object.prototype);
  assert.ok(Object.hasOwn(shared, "__proto__"));
  assert.deepEqual(Object.getOwnPropertyDescriptor(shared, "__proto__").value, {
    x: 2,
  });
  assert.equal(shared.kept, prior.kept);
});

test("publisher secures collection keys, members and selected descendants", () => {
  const key = { id: "thread" };
  const collection = new Map([[key, { words: ["kept"] }]]);
  const document = Object.freeze({ collection });
  const publisher = createApplicationPublisher({
    document,
    authoritative: {},
    unresolved: [],
    effective: {},
    semanticEpoch: 0,
  });
  const selected = publisher
    .select(() =>
      Object.freeze({
        nested: { count: 1 },
        members: new Set([{ id: "message" }]),
      }),
    )
    .read();
  assert.throws(() => {
    selected.nested.count = 2;
  }, TypeError);
  assert.throws(() => {
    selected.members.add("extra");
  }, TypeError);
  assert.throws(() => {
    [...selected.members][0].id = "changed";
  }, TypeError);
  const reading = publisher.read();
  assert.throws(() => {
    [...reading.document.collection.keys()][0].id = "changed";
  }, TypeError);
  assert.throws(() => {
    reading.document.collection.get(key).words.push("changed");
  }, TypeError);
  assert.throws(() => {
    reading.document.collection.set("extra", {});
  }, TypeError);
});
