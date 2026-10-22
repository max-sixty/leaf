import assert from "node:assert/strict";
import test from "node:test";
import { createSignal } from "@solidjs/signals";
import { watchEffect } from "./observe.ts";
import { createApplicationPublisher } from "./snapshot.ts";
import { createPresentationCoordinator } from "./presentation.ts";

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
    const [clock] = createSignal(7);
    const coordinator = createPresentationCoordinator({
      reportFailure: (reason) => {
        throw reason;
      },
    });
    coordinator.begin({}, 0);
    const selected = app.select((root) => {
      part.read();
      clock();
      return root.effective.count;
    });
    const source = kind === "semantic" ? selected : coordinator;
    const ownReads = [];
    const observe = () => {
      // The observer can read the whole root outside its own paint collection.
      assert.equal(app.read().document, initial.document);
      part.read();
      clock();
      ownReads.push([part.read(), clock()]);
    };
    let subscriptions = 0;
    let stopSource;
    const stop = watchEffect(() => {
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
