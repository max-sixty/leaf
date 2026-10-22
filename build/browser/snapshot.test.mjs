import assert from "node:assert/strict";
import test from "node:test";
import { watchEffect } from "./observe.ts";
import { createApplicationPublisher, outsideReading } from "./snapshot.ts";
import { createPresentationCoordinator } from "./presentation.ts";

test("outside readings subscribe only while observed and release their source", () => {
  let value = 0;
  let starts = 0;
  let stops = 0;
  let notify;
  const outside = outsideReading(
    () => value,
    (moved) => {
      starts++;
      notify = moved;
      return () => {
        stops++;
      };
    },
  );
  assert.equal(outside.read(), 0);
  value = 1;
  assert.equal(outside.read(), 1);
  assert.equal(starts, 0);
  const seen = [];
  const stop = outside.subscribe((value) => {
    seen.push(value);
  });
  assert.equal(starts, 1);
  value = 2;
  outside.read();
  notify({});
  assert.deepEqual(seen, [1, 2], "a plain read cannot swallow a later notification");
  stop();
  assert.equal(stops, 1);
  value = 3;
  assert.equal(outside.read(), 3);
  assert.equal(starts, 1);
});

for (const kind of ["semantic", "outside", "presentation"]) {
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
    let notify;
    let now = 7;
    const clock = outsideReading(
      () => now,
      (moved) => {
        notify = moved;
        return () => {};
      },
    );
    const coordinator = createPresentationCoordinator({
      reportFailure: (reason) => {
        throw reason;
      },
    });
    coordinator.begin({}, 0);
    const selected = app.select((root) => {
      part.read();
      clock.read();
      return root.effective.count;
    });
    const source =
      kind === "semantic" ? selected : kind === "outside" ? clock : coordinator;
    const ownReads = [];
    const observe = () => {
      // The observer can read the whole root outside its own paint collection.
      assert.equal(app.read().document, initial.document);
      part.read();
      clock.read();
      ownReads.push([part.read(), clock.read()]);
    };
    let subscriptions = 0;
    let stopSource;
    const stop = watchEffect(() => {
      subscriptions++;
      stopSource = source.subscribe(observe);
    });
    if (kind === "semantic") {
      app.publish({ ...initial, effective: { count: 1 }, semanticEpoch: 1 });
    } else if (kind === "outside") {
      now = 8;
      notify({});
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
      [null, kind === "outside" ? 8 : 7],
    ]);
    stopSource();
    stop();
  });
}
