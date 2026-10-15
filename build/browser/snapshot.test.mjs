import assert from "node:assert/strict";
import test from "node:test";
import {
  collectOutside,
  collectReads,
  createApplicationPublisher,
  outsideReading,
} from "./snapshot.ts";
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
    const clock = outsideReading(
      () => 7,
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
      ownReads.push(collectReads(() => [part.read(), clock.read()]));
    };
    const registration = collectReads(() => source.subscribe(observe));
    assert.ok("value" in registration, String(registration.error));
    assert.equal(registration.reads.size, 0);
    const delivered = collectOutside(() => {
      if (kind === "semantic") {
        app.publish({ ...initial, effective: { count: 1 }, semanticEpoch: 1 });
      } else if (kind === "outside") {
        notify({});
      } else {
        coordinator.attach("unrelated", {});
      }
    });
    assert.ok("value" in delivered, String(delivered.error));
    assert.equal(delivered.reads.size, 0);
    assert.ok(ownReads.length >= 2);
    for (const reading of ownReads) {
      assert.deepEqual([...reading.reads.values()], [null, 7]);
      assert.deepEqual(reading.value, [null, 7]);
    }
    registration.value();
  });
}
