import assert from "node:assert/strict";
import test from "node:test";
import { effect } from "/vendor/signals-core.js";
import {
  createPresentationCoordinator,
  createPresentationSchedule,
  describeFailure,
} from "../../browser/runtime/framework/presentation.js";

// Complete a region immediately.
const presented = (handle) => {
  const presentation = handle.present();
  presentation.resolve();
  return presentation.ready;
};

const setup = () => {
  const failures = [];
  const coordinator = createPresentationCoordinator({
    reportFailure: (reason) => failures.push(reason),
  });
  return { coordinator, failures };
};

test("a superseded value cannot complete the current region", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin();
  const handle = coordinator.attach("widget");
  const olderPresentation = handle.present();
  const newerPresentation = handle.present();
  coordinator.seal(publication);

  olderPresentation.resolve();
  await olderPresentation.ready;
  assert.equal(coordinator.currentPresented(), false);

  newerPresentation.resolve();
  await newerPresentation.ready;
  assert.equal(coordinator.currentPresented(), true);
});

test("a handle releases the holds it supersedes and leaves running paints to report", async () => {
  const { coordinator, failures } = setup();
  const publication = coordinator.begin();
  const handle = coordinator.attach("widget");
  const hold = handle.present();
  const running = handle.present();
  const paint = Promise.withResolvers();
  running.resolve(paint.promise);
  // The newer presentation settled the hold its renderer left open.
  await hold.ready;

  const latest = handle.present();
  coordinator.seal(publication);
  const error = new Error("superseded paint failed");
  paint.reject(error);
  await running.ready;
  assert.deepEqual(failures, [error]);

  // So does disconnecting the renderer.
  handle.disconnect();
  await latest.ready;
  assert.equal(await coordinator.whenCurrentPresented(), "presented");
});

test("a paint that claims its own region again still reports its own failure", async () => {
  const { coordinator, failures } = setup();
  const publication = coordinator.begin();
  const schedule = createPresentationSchedule((callback) => callback);
  const error = new Error("first paint failed");
  let first = true;
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("thread"),
    paint: (value) => {
      if (!first) return value;
      first = false;
      void presenter.sync("again");
      return Promise.reject(error);
    },
  });
  void presenter.sync("first");
  coordinator.seal(publication);
  await schedule.passed().catch(() => {});
  assert.deepEqual(failures, [error]);
});

test("a disconnected renderer retires its work and ignores a late completion", async () => {
  const { coordinator, failures } = setup();
  const publication = coordinator.begin();
  const handle = coordinator.attach("widget");
  const presentation = handle.present();
  coordinator.seal(publication);
  handle.disconnect();

  await new Promise(queueMicrotask);
  assert.equal(await coordinator.whenCurrentPresented(), "presented");
  presentation.resolve();
  await presentation.ready;

  assert.deepEqual(failures, []);
});

test("a replacement renderer must complete in place of the retired instance", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin();
  const oldHandle = coordinator.attach("widget");
  const oldPresentation = oldHandle.present();
  coordinator.seal(publication);

  oldHandle.disconnect();
  const newHandle = coordinator.attach("widget");
  const newPresentation = newHandle.present();
  await new Promise(queueMicrotask);
  oldPresentation.resolve();
  await oldPresentation.ready;
  assert.equal(coordinator.currentPresented(), false);

  newPresentation.resolve();
  await newPresentation.ready;
  assert.equal(coordinator.currentPresented(), true);
});

test("a required replacement reopens readiness after its predecessor retires", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin();
  const oldHandle = coordinator.attach("widget");
  const oldPresentation = oldHandle.present();
  coordinator.seal(publication);

  oldHandle.disconnect();
  await new Promise(queueMicrotask);
  assert.equal(await coordinator.whenCurrentPresented(), "presented");
  assert.equal(coordinator.currentPresented(), true);

  const replacement = coordinator.attach("widget");
  const replacementPresentation = replacement.present();
  const readiness = coordinator.whenCurrentPresented();
  let ready = false;
  void readiness.then(() => {
    ready = true;
  });
  await Promise.resolve();
  assert.equal(ready, false);
  assert.deepEqual(coordinator.read().pending, ["widget"]);

  oldPresentation.resolve();
  await oldPresentation.ready;
  assert.equal(ready, false);

  replacementPresentation.resolve();
  await replacementPresentation.ready;
  assert.equal(await readiness, "presented");
  assert.equal(coordinator.currentPresented(), true);
});

test("a replacement repairs an already presented publication", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin();
  const oldHandle = coordinator.attach("widget");
  await presented(oldHandle);
  coordinator.seal(publication);
  assert.equal(await coordinator.whenCurrentPresented(), "presented");

  oldHandle.disconnect();
  const obsoletePresentation = oldHandle.present();
  const replacement = coordinator.attach("widget");
  const replacementPresentation = replacement.present();
  const readiness = coordinator.whenCurrentPresented();
  let ready = false;
  void readiness.then(() => {
    ready = true;
  });
  await Promise.resolve();
  assert.equal(ready, false);
  assert.deepEqual(coordinator.read().pending, ["widget"]);

  obsoletePresentation.resolve();
  await obsoletePresentation.ready;
  assert.equal(ready, false);

  replacementPresentation.resolve();
  await replacementPresentation.ready;
  assert.equal(await readiness, "presented");
  assert.equal(coordinator.currentPresented(), true);
});

test("an asynchronous descendant joins a sealed barrier", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin();
  const parent = coordinator.attach("parent");
  const parentPresentation = parent.present();
  coordinator.seal(publication);

  const child = coordinator.attach("child");
  const childPresentation = child.present();
  parentPresentation.resolve();
  await parentPresentation.ready;
  assert.deepEqual(coordinator.read().pending, ["child"]);

  childPresentation.resolve();
  await childPresentation.ready;
  assert.equal(coordinator.currentPresented(), true);
});

test("a new publication carries unchanged work and supersedes changed work", async () => {
  const { coordinator } = setup();
  const first = coordinator.begin();
  const stable = coordinator.attach("stable");
  const changed = coordinator.attach("changed");
  const stablePresentation = stable.present();
  const oldChangedPresentation = changed.present();
  coordinator.seal(first);

  const second = coordinator.begin();
  const newChangedPresentation = changed.present();
  coordinator.seal(second);
  stablePresentation.resolve();
  await stablePresentation.ready;
  oldChangedPresentation.resolve();
  await oldChangedPresentation.ready;
  assert.deepEqual(coordinator.read().pending, ["changed"]);

  newChangedPresentation.resolve();
  await newChangedPresentation.ready;
  assert.equal(await coordinator.whenCurrentPresented(), "presented");
});

test("only the current publication seal can present work completed before sealing", async () => {
  const { coordinator } = setup();
  const older = coordinator.begin();
  const current = coordinator.begin();
  const handle = coordinator.attach("widget");
  await presented(handle);

  assert.equal(coordinator.currentPresented(), false);
  assert.equal(coordinator.seal(older), false);
  assert.equal(coordinator.currentPresented(), false);
  assert.equal(coordinator.seal(current), true);
  assert.equal(coordinator.currentPresented(), true);
});

test("a failed presentation reports once, installs its fallback, and settles", async () => {
  const { coordinator, failures } = setup();
  const publication = coordinator.begin();
  const handle = coordinator.attach("widget");
  const fallback = [];
  const presentation = handle.present((reason) => {
    fallback.push(reason);
    return "fallback completion";
  });
  coordinator.seal(publication);
  const error = new Error("renderer failed");
  presentation.reject(error);
  await presentation.ready;

  assert.deepEqual(fallback, [error]);
  assert.deepEqual(failures, [error]);
  assert.equal(coordinator.currentPresented(), true);
});

test("a failed presentation and fail-soft report both failures", async () => {
  const { coordinator, failures } = setup();
  const publication = coordinator.begin();
  const handle = coordinator.attach("widget");
  const rendering = new AggregateError(
    [new Error("widget named its failure")],
    "widget presentation failed",
  );
  const retaining = new Error("committed view could not be restored");
  const presentation = handle.present(() => {
    throw retaining;
  });
  presentation.reject(rendering);
  coordinator.seal(publication);
  await assert.rejects(presentation.ready, (error) => {
    assert.equal(error, failures[0]);
    return true;
  });

  assert.equal(failures.length, 1);
  assert(failures[0] instanceof AggregateError);
  assert.deepEqual(failures[0].errors, [rendering, retaining]);
  assert.equal(failures[0].message, "presentation and fail-soft failed");
  assert.equal(
    describeFailure(failures[0]),
    "presentation and fail-soft failed: widget presentation failed: " +
      "widget named its failure; committed view could not be restored",
  );
  assert.deepEqual(coordinator.read().pending, ["widget"]);
});

test("an unhandled presentation failure keeps its region pending", async () => {
  const { coordinator, failures } = setup();
  const publication = coordinator.begin();
  const handle = coordinator.attach("document");
  const error = new Error("document rendering failed");
  const presentation = handle.present();
  presentation.reject(error);
  coordinator.seal(publication);
  await assert.rejects(presentation.ready, error);

  assert.deepEqual(failures, [error]);
  assert.equal(coordinator.currentPresented(), false);
  assert.deepEqual(coordinator.read().pending, ["document"]);
});

test("scoped readiness does not wait for an unrelated deferred region", async () => {
  const coordinator = createPresentationCoordinator({ reportFailure: assert.fail });
  const publication = coordinator.begin();
  const page = coordinator.attach("page-widget");
  const thread = coordinator.attach("thread-widget");
  const pagePresentation = page.present();
  const threadPresentation = thread.present();
  coordinator.seal(publication);

  let ready = false;
  const readiness = coordinator
    .whenCurrentRegionsPresented(["thread-widget"])
    .then((outcome) => {
      ready = true;
      return outcome;
    });
  threadPresentation.resolve();
  await threadPresentation.ready;
  assert.equal(await readiness, "presented");
  assert.equal(ready, true);
  assert.deepEqual(coordinator.read().pending, ["page-widget"]);
  pagePresentation.resolve();
  await pagePresentation.ready;
});

test("a domain-scoped wait retires when its value is superseded in the same publication", async () => {
  const coordinator = createPresentationCoordinator({ reportFailure: assert.fail });
  const publication = coordinator.begin();
  const data = coordinator.attach("data:feed:rows");
  const older = data.present();
  coordinator.seal(publication);

  let wanted = true;
  const readiness = coordinator.whenCurrentRegionsPresented(
    ["data:feed:rows"],
    () => wanted,
  );
  wanted = false;
  const newer = data.present();
  newer.resolve();

  assert.equal(await readiness, "superseded");
  await newer.ready;
  older.resolve();
  await older.ready;
});

const flushed = () => new Promise((resolve) => setTimeout(resolve, 0));

test("explicit DOM dependencies ignore registration order and coalesce claims", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin();
  const schedule = createPresentationSchedule((callback) => callback);
  const painted = [];
  const late = schedule.presenter({
    attach: () => coordinator.attach("thread"),
    after: () => [early.committed()],
    paint: (value) => painted.push(`thread:${value}`),
  });
  const early = schedule.presenter({
    attach: () => coordinator.attach("projection"),
    paint: (value) => painted.push(`projection:${value}`),
  });
  void late.sync("first");
  void early.sync("only");
  const ready = late.sync("second");
  coordinator.seal(publication);
  assert.deepEqual(painted, []);
  await ready;
  assert.deepEqual(painted, ["projection:only", "thread:second"]);
  assert.equal(coordinator.currentPresented(), true);
});

test("a reading held open does not keep the next one off the page", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin();
  const schedule = createPresentationSchedule((callback) => callback);
  const painted = [];
  const { promise: held, resolve: release } = Promise.withResolvers();
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("thread"),
    paint: async (value, current) => {
      painted.push(value);
      // The first reading waits on something that has not arrived — a widget that has
      // not prepared. A newer reading must still reach the page.
      if (value === "held") await held;
      return current() ? value : undefined;
    },
  });
  void presenter.sync("held");
  await flushed();
  assert.deepEqual(painted, ["held"]);

  const ready = presenter.sync("newer");
  coordinator.seal(publication);
  await flushed();
  assert.deepEqual(painted, ["held", "newer"]);
  release();
  await ready;

  assert.equal(coordinator.currentPresented(), true);
});

test("a superseded claim releases its hold without painting", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin();
  const schedule = createPresentationSchedule((callback) => callback);
  const painted = [];
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("obligations"),
    paint: (value) => {
      painted.push(value);
      return value;
    },
  });
  const stale = presenter.sync("stale");
  const current = presenter.sync("current");
  coordinator.seal(publication);

  await Promise.all([stale, current]);
  assert.deepEqual(painted, ["current"]);
  assert.equal(coordinator.currentPresented(), true);
});

test("a failing paint reports through the region and fails the pass it was in", async () => {
  const { coordinator, failures } = setup();
  const publication = coordinator.begin();
  const schedule = createPresentationSchedule((callback) => callback);
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("thread"),
    paint: () => {
      throw new Error("paint failed");
    },
  });
  const ready = presenter.sync("value");
  coordinator.seal(publication);

  await assert.rejects(ready, /paint failed/);
  assert.equal(failures.length, 1);
  assert.deepEqual(coordinator.read().pending, ["thread"]);
  assert.equal(coordinator.currentPresented(), false);
});

test("a failure reported for one region does not withhold the others' readings", async () => {
  const { coordinator, failures } = setup();
  const publication = coordinator.begin();
  const schedule = createPresentationSchedule((callback) => callback);
  const painted = [];
  const failing = schedule.presenter({
    attach: () => coordinator.attach("projection:chrome"),
    paint: () => {
      throw new Error("projection failed");
    },
  });
  const following = schedule.presenter({
    attach: () => coordinator.attach("thread"),
    after: () => [failing.committed()],
    paint: (value) => {
      painted.push(value);
      return value;
    },
  });
  void failing.sync("chrome");
  const ready = following.sync("threads");
  coordinator.seal(publication);

  await assert.rejects(ready, /projection failed/);
  assert.deepEqual(painted, ["threads"]);
  assert.equal(failures.length, 1);
  assert.deepEqual(coordinator.read().pending, ["projection:chrome"]);
});

test("a fail-soft paint commits an explicit failure state", async () => {
  const { coordinator, failures } = setup();
  const publication = coordinator.begin();
  const schedule = createPresentationSchedule((callback) => callback);
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("thread"),
    failSoft: () => "retained",
    paint: () => Promise.reject(new Error("list failed")),
  });
  // Fail-soft completion is a committed reading, so the pass carrying it succeeds; the
  // failure reaches the user through the coordinator's report instead.
  const ready = presenter.sync("value");
  coordinator.seal(publication);
  await ready;

  assert.equal(failures.length, 1);
  assert.equal(coordinator.currentPresented(), true);
});

test("a paint that claims another region joins the same pass", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin();
  const painted = [];
  const schedule = createPresentationSchedule((callback) => callback);
  const following = schedule.presenter({
    attach: () => coordinator.attach("thread"),
    paint: (value) => {
      painted.push(`thread:${value}`);
      return value;
    },
  });
  let again = true;
  const leading = schedule.presenter({
    attach: () => coordinator.attach("projection:chrome"),
    paint: (value) => {
      painted.push(`projection:${value}`);
      if (again) {
        again = false;
        void following.sync("mounted");
      }
      return value;
    },
  });
  const ready = leading.sync("first");
  coordinator.seal(publication);
  await ready;

  // The claim a paint makes belongs to the same pass, so the promise the pass hands
  // back is completion that the page caught up rather than that one renderer ran.
  assert.deepEqual(painted, ["projection:first", "thread:mounted"]);
  assert.equal(coordinator.currentPresented(), true);
});

test("a reading claimed mid-paint is installed before the finished one settles", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin();
  const schedule = createPresentationSchedule((callback) => callback);
  let claimDuringPaint = null;
  const readings = [];
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("thread"),
    paint: async (value) => {
      claimDuringPaint?.();
      claimDuringPaint = null;
      await flushed();
      // The region is never presented on the older value while a newer one is owed.
      readings.push(coordinator.currentPresented());
      return value;
    },
  });
  claimDuringPaint = () => void presenter.sync("second");
  const ready = presenter.sync("first");
  coordinator.seal(publication);
  await ready;

  assert.deepEqual(readings, [false, false]);
  assert.equal(coordinator.currentPresented(), true);
});

test("a paint that fails after a newer claim supersedes it still reports", async () => {
  const { coordinator, failures } = setup();
  const publication = coordinator.begin();
  const schedule = createPresentationSchedule((callback) => callback);
  const slow = Promise.withResolvers();
  let first = true;
  const started = Promise.withResolvers();
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("thread"),
    paint: (value) => {
      started.resolve();
      if (!first) return value;
      first = false;
      return slow.promise;
    },
  });
  const stale = presenter.sync("stale");
  coordinator.seal(publication);
  await started.promise;

  const current = presenter.sync("current");
  slow.reject(new Error("the superseded paint failed"));
  await Promise.allSettled([stale, current]);

  assert.deepEqual(
    failures.map((reason) => reason.message),
    ["the superseded paint failed"],
  );

  assert.equal(coordinator.currentPresented(), true);
});

for (const order of ["passive-first", "input-first"]) {
  test(`coalesced presenters retain each claim's context: ${order}`, async () => {
    let context = null;
    const schedule = createPresentationSchedule((callback) => {
      const captured = context;
      return () => {
        const prior = context;
        context = captured;
        try {
          return callback();
        } finally {
          context = prior;
        }
      };
    });
    const { coordinator } = setup();
    coordinator.begin();
    const painted = [];
    const presenter = (name) =>
      schedule.presenter({
        attach: () => coordinator.attach(name),
        paint: () => painted.push([name, context]),
      });
    const passive = presenter("passive");
    const input = presenter("input");
    const claimPassive = () => {
      context = null;
      void passive.sync(1);
    };
    const claimInput = () => {
      context = "press";
      void input.sync(1);
    };
    if (order === "passive-first") {
      claimPassive();
      claimInput();
    } else {
      claimInput();
      claimPassive();
    }
    context = "unrelated";
    await schedule.passed();
    assert.deepEqual(
      painted,
      order === "passive-first"
        ? [
            ["passive", null],
            ["input", "press"],
          ]
        : [
            ["input", "press"],
            ["passive", null],
          ],
    );
    assert.equal(context, "unrelated");
  });
}

test("region readiness observes completion and same-publication replacement without other domains", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin();
  const first = coordinator.attach("widget");
  const other = coordinator.attach("data");
  const painting = first.present();
  other.present();
  const seen = [];
  const stop = coordinator.subscribe(() => {
    seen.push(coordinator.currentRegionsPresented(["widget"]));
  });
  assert.equal(coordinator.currentRegionsPresented(["widget"]), false);
  coordinator.seal(publication);
  painting.resolve();
  await painting.ready;
  assert.equal(coordinator.currentRegionsPresented(["widget"]), true);
  assert.equal(coordinator.currentPresented(), false);
  assert.equal(seen.at(-1), true);

  const replacement = coordinator.attach("widget");
  assert.equal(coordinator.currentRegionsPresented(["widget"]), false);
  assert.equal(seen.at(-1), false);
  const replacementPaint = replacement.present();
  first.disconnect();
  assert.equal(coordinator.currentRegionsPresented(["widget"]), false);
  replacementPaint.resolve();
  await replacementPaint.ready;
  assert.equal(coordinator.currentRegionsPresented(["widget"]), true);
  assert.equal(seen.at(-1), true);

  replacement.present();
  assert.equal(coordinator.currentRegionsPresented(["widget"]), false);
  replacement.disconnect();
  assert.equal(coordinator.currentRegionsPresented(["widget"]), false);
  await Promise.resolve();
  assert.equal(coordinator.currentRegionsPresented(["widget"]), true);
  assert.equal(seen.at(-1), true);
  const observations = seen.length;
  stop();
  other.disconnect();
  await Promise.resolve();
  assert.equal(seen.length, observations);
});

test("a failing completion observer cannot fail or starve renderer completion", async () => {
  const { coordinator, failures } = setup();
  const publication = coordinator.begin();
  const handle = coordinator.attach("widget");
  const stopFailed = coordinator.subscribe(() => {
    throw new Error("observer broke");
  });
  let observed = false;
  const stopHealthy = coordinator.subscribe(() => {
    observed = coordinator.currentRegionsPresented(["widget"]);
  });
  coordinator.seal(publication);
  await presented(handle);
  assert.equal(observed, true);
  assert.equal(coordinator.currentPresented(), true);
  assert.ok(failures.every((reason) => reason.message === "observer broke"));
  assert.ok(failures.length > 0);
  stopFailed();
  stopHealthy();
});

test("a paint creating a child presentation does not subscribe to completion changes", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin();
  let paints = 0;
  let child;
  const stop = effect(() => {
    paints += 1;
    // A widget can connect while its containing region paints. Its own presentation
    // belongs to that widget, and resolving it must not repaint the containing region.
    if (paints === 1) child = coordinator.attach("child").present();
  });
  try {
    coordinator.seal(publication);
    child.resolve();
    await child.ready;
    assert.equal(paints, 1);
  } finally {
    stop();
  }
});

test("dependent DOM waits for native commit, independently of semantic completion", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin();
  const schedule = createPresentationSchedule((callback) => callback);
  const committed = Promise.withResolvers();
  const held = Promise.withResolvers();
  const drawn = [];
  const widget = coordinator.attach("widget").present();
  widget.resolve(held.promise);
  const producer = schedule.enqueue(
    () => [],
    () => {
      drawn.push("widget");
    },
    () => committed.promise,
  );
  const consumer = schedule.presenter({
    attach: () => coordinator.attach("projection"),
    after: () => [producer.committed],
    paint: () => drawn.push("projection"),
  });
  const unrelated = schedule.presenter({
    attach: () => coordinator.attach("independent"),
    paint: () => drawn.push("independent"),
  });
  void consumer.sync(1);
  void unrelated.sync(1);
  coordinator.seal(publication);
  await producer.ready;
  assert.deepEqual(drawn, ["widget", "independent"]);
  committed.resolve();
  await schedule.passed();
  assert.deepEqual(drawn, ["widget", "independent", "projection"]);
  assert.deepEqual(coordinator.read().pending, ["widget"]);
  held.resolve();
  await widget.ready;
  assert.equal(coordinator.currentPresented(), true);
});

test("DOM dependents follow replacement and disconnect releases an obsolete wait", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin();
  const schedule = createPresentationSchedule((callback) => callback);
  const first = Promise.withResolvers();
  const second = Promise.withResolvers();
  let drawn = "nothing";
  const seen = [];
  let producer = schedule.enqueue(
    () => [],
    () => {
      drawn = "first";
    },
    () => first.promise,
  );
  const consumer = schedule.presenter({
    attach: () => coordinator.attach("consumer"),
    after: () => [producer.committed],
    paint: () => seen.push(drawn),
  });
  void consumer.sync(1);
  await producer.ready;
  producer = schedule.enqueue(
    () => [],
    () => {
      drawn = "second";
    },
    () => second.promise,
  );
  first.resolve();
  await producer.ready;
  assert.deepEqual(seen, [], "the predecessor is not the replacement's DOM commit");
  second.resolve();
  await consumer.committed();
  assert.deepEqual(seen, ["second"]);
  await schedule.passed();

  const never = Promise.withResolvers();
  const departed = schedule.presenter({
    attach: () => coordinator.attach("departed"),
    after: () => [never.promise],
    paint: () => assert.fail("disconnected owner must not paint"),
  });
  void departed.sync(1);
  await flushed();
  departed.disconnect();
  coordinator.seal(publication);
  await schedule.passed();
});

test("a departure cannot briefly complete an unfinished publication", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin();
  const leaving = coordinator.attach("leaving");
  await presented(leaving);
  const remaining = coordinator.attach("remaining").present();
  coordinator.seal(publication);
  const readings = [];
  const stop = coordinator.subscribe(() => readings.push(coordinator.read()));
  readings.length = 0;

  // Completion runs first in the microtask queue, before retirement removes the
  // departed region. A replacement can still take its seat until retirement runs.
  remaining.resolve();
  leaving.disconnect();
  await remaining.ready;
  stop();

  assert.deepEqual(readings[0].pending, ["leaving"]);
  assert.equal(readings[0].sealed && readings[0].pending.length === 0, false);
  assert.deepEqual(coordinator.read().pending, []);
  assert.equal(coordinator.currentPresented(), true);
});

test("a new publication excludes a region already departing", async () => {
  const { coordinator } = setup();
  const first = coordinator.begin();
  const leaving = coordinator.attach("leaving");
  leaving.present();
  coordinator.seal(first);

  leaving.disconnect();
  const next = coordinator.begin();
  assert.deepEqual(coordinator.read().pending, []);
  coordinator.seal(next);
  assert.equal(await coordinator.whenCurrentPresented(), "presented");
});
