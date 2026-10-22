import assert from "node:assert/strict";
import test from "node:test";
import { effect } from "@preact/signals-core";
import { createApplicationPublisher, outsideReading } from "./snapshot.ts";
import { createPresentationCoordinator } from "./presentation.ts";

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
    const stop = effect(() => {
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
