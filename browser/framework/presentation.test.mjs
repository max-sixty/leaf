import assert from "node:assert/strict";
import test from "node:test";
import { createSignal, flush } from "@solidjs/signals";
import { watchReaction } from "./observe.ts";
import { afterRender, renderCommit } from "./rendering.ts";
import {
  createPresentationCoordinator,
  createPresentationFlow,
  describeFailure,
} from "./presentation.ts";

// Present `value` and settle its ticket with `proof` at once.
const presented = (handle, value, proof) => {
  const presentation = handle.present(value);
  presentation.resolve(proof);
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
  const document = {};
  const renderer = {};
  const publication = coordinator.begin(document, 0);
  const handle = coordinator.attach("widget", renderer);
  const olderPresentation = handle.present("older");
  const newerPresentation = handle.present("newer");
  coordinator.seal(publication);

  olderPresentation.resolve("older proof");
  await olderPresentation.ready;
  assert.equal(coordinator.read().presentedEpoch, -1);
  assert.equal(coordinator.committed("widget", renderer, "older"), null);

  newerPresentation.resolve("newer proof");
  await newerPresentation.ready;
  assert.equal(coordinator.read().presentedEpoch, 0);
  assert.deepEqual(coordinator.committed("widget", renderer, "newer"), {
    document,
    semanticEpoch: 0,
    region: "widget",
    renderer,
    rendererGeneration: 1,
    ticketGeneration: 2,
    value: "newer",
    status: "committed",
    proof: "newer proof",
  });
});

test("a handle releases the holds it supersedes and leaves running paints to report", async () => {
  const { coordinator, failures } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const handle = coordinator.attach("widget", {});
  const hold = handle.present("held");
  const running = handle.present("painting");
  const paint = Promise.withResolvers();
  running.resolve(paint.promise);
  // The newer presentation settled the hold its renderer left open.
  await hold.ready;

  const latest = handle.present("latest");
  coordinator.seal(publication);
  const error = new Error("superseded paint failed");
  paint.reject(error);
  await running.ready;
  assert.deepEqual(failures, [error]);

  // So does disconnecting the renderer.
  handle.disconnect();
  await latest.ready;
  assert.equal(await coordinator.whenPresented(document, 0), "presented");
});

test("a paint that claims its own region again still reports its own failure", async () => {
  const { coordinator, failures } = setup();
  const publication = coordinator.begin({}, 0);
  const schedule = createPresentationFlow((callback) => callback);
  const error = new Error("first paint failed");
  let first = true;
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("thread", {}),
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
  const document = {};
  const renderer = {};
  const publication = coordinator.begin(document, 0);
  const handle = coordinator.attach("widget", renderer);
  const presentation = handle.present("value");
  coordinator.seal(publication);
  handle.disconnect();

  await new Promise(queueMicrotask);
  assert.equal(await coordinator.whenPresented(document, 0), "presented");
  presentation.resolve("obsolete proof");
  await presentation.ready;
  assert.equal(coordinator.committed("widget", renderer, "value"), null);
  assert.deepEqual(failures, []);
});

test("a replacement renderer must complete in place of the retired instance", async () => {
  const { coordinator } = setup();
  const document = {};
  const oldRenderer = {};
  const newRenderer = {};
  const publication = coordinator.begin(document, 0);
  const oldHandle = coordinator.attach("widget", oldRenderer);
  const oldPresentation = oldHandle.present("value");
  coordinator.seal(publication);

  oldHandle.disconnect();
  const newHandle = coordinator.attach("widget", newRenderer);
  const newPresentation = newHandle.present("value");
  await new Promise(queueMicrotask);
  oldPresentation.resolve("old proof");
  await oldPresentation.ready;
  assert.equal(coordinator.read().presentedEpoch, -1);

  newPresentation.resolve("new proof");
  await newPresentation.ready;
  assert.equal(coordinator.read().presentedEpoch, 0);
  assert.equal(coordinator.committed("widget", oldRenderer, "value"), null);
  assert.equal(
    coordinator.committed("widget", newRenderer, "value")?.rendererGeneration,
    2,
  );
});

test("a required replacement reopens readiness after its predecessor retires", async () => {
  const { coordinator } = setup();
  const document = {};
  const oldRenderer = {};
  const publication = coordinator.begin(document, 0);
  const oldHandle = coordinator.attach("widget", oldRenderer);
  const oldPresentation = oldHandle.present("same");
  coordinator.seal(publication);

  oldHandle.disconnect();
  await new Promise(queueMicrotask);
  assert.equal(await coordinator.whenPresented(document, 0), "presented");
  assert.equal(coordinator.read().presentedEpoch, 0);

  const newRenderer = {};
  const replacement = coordinator.attach("widget", newRenderer);
  const replacementPresentation = replacement.present("same");
  const readiness = coordinator.whenPresented(document, 0);
  let ready = false;
  void readiness.then(() => {
    ready = true;
  });
  await Promise.resolve();
  assert.equal(ready, false);
  assert.deepEqual(coordinator.read().pending, ["widget"]);

  oldPresentation.resolve("obsolete proof");
  await oldPresentation.ready;
  assert.equal(ready, false);
  assert.equal(coordinator.committed("widget", oldRenderer, "same"), null);

  replacementPresentation.resolve("replacement proof");
  await replacementPresentation.ready;
  assert.equal(await readiness, "presented");
  assert.equal(coordinator.read().presentedEpoch, 0);
  assert.equal(
    coordinator.committed("widget", newRenderer, "same")?.proof,
    "replacement proof",
  );
});

test("an equal-value replacement repairs an already presented epoch", async () => {
  const { coordinator } = setup();
  const document = {};
  const oldRenderer = {};
  const publication = coordinator.begin(document, 0);
  const oldHandle = coordinator.attach("widget", oldRenderer);
  await presented(oldHandle, "same", "old proof");
  coordinator.seal(publication);
  assert.equal(await coordinator.whenPresented(document, 0), "presented");

  oldHandle.disconnect();
  const obsoletePresentation = oldHandle.present("same");
  const newRenderer = {};
  const replacement = coordinator.attach("widget", newRenderer);
  const replacementPresentation = replacement.present("same");
  const readiness = coordinator.whenPresented(document, 0);
  let ready = false;
  void readiness.then(() => {
    ready = true;
  });
  await Promise.resolve();
  assert.equal(ready, false);
  assert.deepEqual(coordinator.read().pending, ["widget"]);

  obsoletePresentation.resolve("obsolete proof");
  await obsoletePresentation.ready;
  assert.equal(ready, false);
  assert.equal(coordinator.committed("widget", oldRenderer, "same"), null);

  replacementPresentation.resolve("replacement proof");
  await replacementPresentation.ready;
  assert.equal(await readiness, "presented");
  assert.equal(coordinator.read().presentedEpoch, 0);
  assert.equal(
    coordinator.committed("widget", newRenderer, "same")?.proof,
    "replacement proof",
  );
});

test("begin reuses the active publication when the semantic epoch is unchanged", async () => {
  const { coordinator } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const handle = coordinator.attach("widget", {});
  await presented(handle, "value", "proof");
  coordinator.seal(publication);

  assert.equal(coordinator.begin(document, 0), publication);
  assert.equal(await coordinator.whenPresented(document, 0), "presented");
  assert.deepEqual(coordinator.read().pending, []);
});

test("an asynchronous descendant joins a sealed barrier", async () => {
  const { coordinator } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const parent = coordinator.attach("parent", {});
  const parentPresentation = parent.present("parent value");
  coordinator.seal(publication);

  const child = coordinator.attach("child", {});
  const childPresentation = child.present("child value");
  parentPresentation.resolve("parent proof");
  await parentPresentation.ready;
  assert.deepEqual(coordinator.read().pending, ["child"]);

  childPresentation.resolve("child proof");
  await childPresentation.ready;
  assert.equal(coordinator.read().presentedEpoch, 0);
});

test("a newer epoch carries unchanged work and supersedes changed work", async () => {
  const { coordinator } = setup();
  const document = {};
  const stableRenderer = {};
  const changedRenderer = {};
  const first = coordinator.begin(document, 0);
  const stable = coordinator.attach("stable", stableRenderer);
  const changed = coordinator.attach("changed", changedRenderer);
  const stablePresentation = stable.present("same");
  const oldChangedPresentation = changed.present("old");
  coordinator.seal(first);

  const second = coordinator.begin(document, 1);
  const newChangedPresentation = changed.present("new");
  coordinator.seal(second);
  stablePresentation.resolve("stable proof");
  await stablePresentation.ready;
  oldChangedPresentation.resolve("old proof");
  await oldChangedPresentation.ready;
  assert.deepEqual(coordinator.read().pending, ["changed"]);
  assert.equal(coordinator.committed("changed", changedRenderer, "old"), null);

  newChangedPresentation.resolve("new proof");
  await newChangedPresentation.ready;
  assert.equal(await coordinator.whenPresented(document, 1), "presented");
  assert.equal(
    coordinator.committed("stable", stableRenderer, "same")?.semanticEpoch,
    1,
  );
  assert.equal(
    coordinator.committed("changed", changedRenderer, "new")?.semanticEpoch,
    1,
  );
});

test("only the current publication seal can present work completed before sealing", async () => {
  const { coordinator } = setup();
  const document = {};
  const older = coordinator.begin(document, 0);
  const current = coordinator.begin(document, 1);
  const renderer = {};
  const handle = coordinator.attach("widget", renderer);
  await presented(handle, "value", "proof");

  assert.equal(coordinator.read().presentedEpoch, -1);
  assert.equal(coordinator.seal(older), false);
  assert.equal(coordinator.read().presentedEpoch, -1);
  assert.equal(coordinator.seal(current), true);
  assert.equal(coordinator.read().presentedEpoch, 1);
});

test("a prior document cannot complete or retain waiters in its replacement", async () => {
  const { coordinator } = setup();
  const oldDocument = {};
  const oldPublication = coordinator.begin(oldDocument, 4);
  const renderer = {};
  const handle = coordinator.attach("widget", renderer);
  const oldPresentation = handle.present("old");
  coordinator.seal(oldPublication);
  const oldWait = coordinator.whenPresented(oldDocument, 4);

  const newDocument = {};
  const newPublication = coordinator.begin(newDocument, 0);
  coordinator.seal(newPublication);
  assert.equal(await oldWait, "superseded");
  assert.equal(await coordinator.whenPresented(newDocument, 0), "presented");
  oldPresentation.resolve("old proof");
  await oldPresentation.ready;
  assert.equal(coordinator.committed("widget", renderer, "old"), null);
  assert.equal(coordinator.read().document, newDocument);
});

test("a failed presentation reports once, installs fail-soft proof, and settles", async () => {
  const { coordinator, failures } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const renderer = {};
  const handle = coordinator.attach("widget", renderer);
  const fallback = [];
  const presentation = handle.present("value", (reason) => {
    fallback.push(reason);
    return "fallback proof";
  });
  coordinator.seal(publication);
  const error = new Error("renderer failed");
  presentation.reject(error);
  await presentation.ready;

  assert.deepEqual(fallback, [error]);
  assert.deepEqual(failures, [error]);
  assert.equal(coordinator.read().presentedEpoch, 0);
  assert.deepEqual(coordinator.committed("widget", renderer, "value"), {
    document,
    semanticEpoch: 0,
    region: "widget",
    renderer,
    rendererGeneration: 1,
    ticketGeneration: 1,
    value: "value",
    status: "failed",
    proof: "fallback proof",
  });
});

test("a failed presentation and fail-soft report both failures", async () => {
  const { coordinator, failures } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const handle = coordinator.attach("widget", {});
  const rendering = new AggregateError(
    [new Error("widget named its failure")],
    "widget presentation failed",
  );
  const retaining = new Error("committed view could not be restored");
  const presentation = handle.present("value", () => {
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
  const document = {};
  const publication = coordinator.begin(document, 0);
  const renderer = {};
  const handle = coordinator.attach("document", renderer);
  const error = new Error("document rendering failed");
  const presentation = handle.present("value");
  presentation.reject(error);
  coordinator.seal(publication);
  await assert.rejects(presentation.ready, error);

  assert.deepEqual(failures, [error]);
  assert.equal(coordinator.read().presentedEpoch, -1);
  assert.deepEqual(coordinator.read().pending, ["document"]);
  assert.equal(coordinator.committed("document", renderer, "value"), null);
});

test("current readiness follows a publication opened before its continuation", async () => {
  const document = {};
  const coordinator = createPresentationCoordinator({ reportFailure: assert.fail });
  let current = { document, semanticEpoch: 0 };
  const firstPublication = coordinator.begin(document, 0);
  const renderer = coordinator.attach("widget", {});
  const first = renderer.present("first");
  coordinator.seal(firstPublication);

  const stale = coordinator.whenPresented(document, 0);
  let second;
  stale.then(() => {
    current = { document, semanticEpoch: 1 };
    const secondPublication = coordinator.begin(document, 1);
    second = renderer.present("second");
    coordinator.seal(secondPublication);
  });
  let ready = false;
  const readiness = coordinator
    .whenCurrentPresented(() => current)
    .then((outcome) => {
      ready = true;
      return outcome;
    });
  assert.equal(
    coordinator.currentPresented(() => current),
    false,
  );

  first.resolve();
  await first.ready;
  await Promise.resolve();
  assert.equal(ready, false);
  assert.equal(
    coordinator.currentPresented(() => current),
    false,
  );
  assert.deepEqual(coordinator.read().pending, ["widget"]);
  second.resolve();
  await second.ready;
  assert.equal(await readiness, "presented");
});

test("current readiness follows a same-epoch renderer replacement", async () => {
  const document = {};
  const coordinator = createPresentationCoordinator({ reportFailure: assert.fail });
  const current = { document, semanticEpoch: 0 };
  const publication = coordinator.begin(document, 0);
  const firstRenderer = coordinator.attach("widget", {});
  const first = firstRenderer.present("value");
  coordinator.seal(publication);

  const stale = coordinator.whenPresented(document, 0);
  let replacement;
  stale.then(() => {
    firstRenderer.disconnect();
    const nextRenderer = coordinator.attach("widget", {});
    replacement = nextRenderer.present("value");
  });
  let ready = false;
  const readiness = coordinator
    .whenCurrentPresented(() => current)
    .then((outcome) => {
      ready = true;
      return outcome;
    });

  first.resolve();
  await first.ready;
  await Promise.resolve();
  assert.equal(ready, false);
  assert.deepEqual(coordinator.read().pending, ["widget"]);
  replacement.resolve();
  await replacement.ready;
  assert.equal(await readiness, "presented");
  assert.equal(
    coordinator.currentPresented(() => current),
    true,
  );
});

test("scoped readiness does not wait for an unrelated deferred region", async () => {
  const document = {};
  const coordinator = createPresentationCoordinator({ reportFailure: assert.fail });
  const current = { document, semanticEpoch: 0 };
  const publication = coordinator.begin(document, 0);
  const page = coordinator.attach("page-widget", {});
  const thread = coordinator.attach("thread-widget", {});
  const pagePresentation = page.present("page");
  const threadPresentation = thread.present("thread");
  coordinator.seal(publication);

  let ready = false;
  const readiness = coordinator
    .whenCurrentRegionsPresented(() => current, ["thread-widget"])
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

test("a domain-scoped wait retires when its value is superseded in the same epoch", async () => {
  const document = {};
  const coordinator = createPresentationCoordinator({ reportFailure: assert.fail });
  const current = { document, semanticEpoch: 0 };
  const publication = coordinator.begin(document, 0);
  const data = coordinator.attach("data:feed:rows", {});
  const older = data.present(1);
  coordinator.seal(publication);

  let wanted = true;
  const readiness = coordinator.whenCurrentRegionsPresented(
    () => (wanted ? current : null),
    ["data:feed:rows"],
  );
  wanted = false;
  const newer = data.present(2);
  newer.resolve();

  assert.equal(await readiness, "superseded");
  await newer.ready;
  older.resolve();
  await older.ready;
});

const flushed = () => new Promise((resolve) => setTimeout(resolve, 0));

test("render dependencies follow current parentage and coalesce repeated claims", async () => {
  const { coordinator } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const schedule = createPresentationFlow((callback) => callback);
  const painted = [];
  const projection = schedule.group();
  const thread = schedule.group();
  const [parent, setParent] = createSignal("projection");
  const presenter = (region, group, after) =>
    schedule.presenter({
      attach: () => coordinator.attach(region, {}),
      group,
      after,
      paint: (value) => {
        painted.push(`${region}:${value}`);
        return `${region} proof`;
      },
    });
  // The child is registered and claimed first; only the current dependency decides
  // which DOM must be committed before its consumer can render.
  const late = presenter("thread", thread, () =>
    parent() === "projection" ? [projection] : [],
  );
  const early = presenter("projection", projection, () =>
    parent() === "thread" ? [thread] : [],
  );
  void late.sync("first");
  void early.sync("only");
  const ready = late.sync("second");
  coordinator.seal(publication);

  await ready;
  assert.deepEqual(painted, ["projection:only", "thread:second"]);
  assert.equal(coordinator.read().presentedEpoch, 0);

  flush(() => setParent("thread"));
  const next = coordinator.begin(document, 1);
  void early.sync("next");
  const reordered = late.sync("next");
  coordinator.seal(next);
  await reordered;
  assert.deepEqual(painted.slice(2), ["thread:next", "projection:next"]);
});

test("a reading held open does not keep the next one off the page", async () => {
  const { coordinator } = setup();
  const document = {};
  const renderer = {};
  const publication = coordinator.begin(document, 0);
  const schedule = createPresentationFlow((callback) => callback);
  const painted = [];
  const { promise: held, resolve: release } = Promise.withResolvers();
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("thread", renderer),
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

  assert.equal(coordinator.committed("thread", renderer, "newer").status, "committed");
  assert.equal(coordinator.read().presentedEpoch, 0);
});

test("dependent DOM waits for post-commit work but not asynchronous preparation", async () => {
  const flow = createPresentationFlow((callback) => callback);
  const widgets = flow.group();
  const projection = flow.group([widgets]);
  const child = flow.task({ group: projection });
  const parent = flow.task({ group: widgets });
  const held = Promise.withResolvers();
  const painted = [];
  let projected;
  try {
    flush(() => {
      projected = child.enqueue(() => {
        painted.push("projection");
      });
      void parent.enqueue(() => {
        painted.push("widget");
        afterRender(() => {
          painted.push("widget measured");
        });
        return held.promise;
      });
    });
    await projected;
    assert.deepEqual(painted, ["widget", "widget measured", "projection"]);
    held.resolve();
    await flow.passed();
  } finally {
    held.resolve();
    parent.disconnect();
    child.disconnect();
  }
});

test("a native flow paint cannot inherit a stale caller's cancellation or tracking", async () => {
  const { coordinator, failures } = setup();
  const publication = coordinator.begin({}, 0);
  const renderer = {};
  const events = [];
  const schedule = createPresentationFlow((callback) => {
    events.push("enqueue");
    return () => {
      events.push("run");
      try {
        return callback();
      } finally {
        events.push("finish");
      }
    };
  });
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("independent", renderer),
    paint(value) {
      events.push(`paint:${value}`);
      afterRender(() => {
        events.push("measured");
      });
      return `${value} proof`;
    },
  });
  let current = true;
  let stretches = 0;
  try {
    const caller = renderCommit(
      () => {
        current = false;
        // An eager publication can run independent native effects while this
        // obsolete caller's render frame remains on the JavaScript stack.
        flush(() => presenter.sync("latest"));
      },
      {
        current: () => current,
        run(callback) {
          stretches++;
          return callback();
        },
      },
    );
    coordinator.seal(publication);
    await Promise.all([caller.ready, schedule.passed()]);
    assert.equal(stretches, 1, "the independent paint owns its reactive reads");
    assert.deepEqual(events, [
      "enqueue",
      "run",
      "paint:latest",
      "enqueue",
      "finish",
      "run",
      "measured",
      "finish",
    ]);
    assert.equal(
      coordinator.committed("independent", renderer, "latest").proof,
      "latest proof",
    );
    assert.equal(coordinator.read().presentedEpoch, 0);
    assert.deepEqual(failures, []);
  } finally {
    presenter.disconnect();
  }
});

test("a superseded claim releases its hold without painting", async () => {
  const { coordinator } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const schedule = createPresentationFlow((callback) => callback);
  const painted = [];
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("obligations", {}),
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
  assert.equal(coordinator.read().presentedEpoch, 0);
});

test("a later failure remains in the pass while an earlier owner is held", async () => {
  const flow = createPresentationFlow((callback) => callback);
  const held = Promise.withResolvers();
  const slow = flow.task();
  const failed = flow.task();
  try {
    const first = slow.enqueue(() => held.promise);
    flush();
    const passed = flow.passed();
    const second = failed.enqueue(() => {
      throw new Error("later owner failed");
    });
    flush();
    await assert.rejects(second, /later owner failed/);
    held.resolve();
    await first;
    await assert.rejects(passed, /later owner failed/);
    await failed.enqueue(() => "a new pass can succeed");
    await flow.passed();
  } finally {
    held.resolve();
    slow.disconnect();
    failed.disconnect();
  }
});

test("a failing paint reports through the region and fails the pass it was in", async () => {
  const { coordinator, failures } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const schedule = createPresentationFlow((callback) => callback);
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("thread", {}),
    paint: () => {
      throw new Error("paint failed");
    },
  });
  const ready = presenter.sync("value");
  coordinator.seal(publication);

  await assert.rejects(ready, /paint failed/);
  assert.equal(failures.length, 1);
  assert.deepEqual(coordinator.read().pending, ["thread"]);
  assert.equal(coordinator.read().presentedEpoch, -1);
});

test("a failure reported for one region does not withhold the others' readings", async () => {
  const { coordinator, failures } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const schedule = createPresentationFlow((callback) => callback);
  const painted = [];
  const projection = schedule.group();
  const failing = schedule.presenter({
    attach: () => coordinator.attach("projection:chrome", {}),
    group: projection,
    paint: () => {
      throw new Error("projection failed");
    },
  });
  const following = schedule.presenter({
    attach: () => coordinator.attach("thread", {}),
    after: () => [projection],
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

for (const failureAt of ["preparation", "measurement"])
  test(`a fail-soft paint commits an explicit failure state: ${failureAt}`, async () => {
    const { coordinator, failures } = setup();
    const document = {};
    const renderer = {};
    const publication = coordinator.begin(document, 0);
    const schedule = createPresentationFlow((callback) => callback);
    const presenter = schedule.presenter({
      attach: () => coordinator.attach("thread", renderer),
      failSoft: () => "retained",
      paint: () => {
        const error = new Error("list failed");
        if (failureAt === "preparation") return Promise.reject(error);
        afterRender(() => {
          throw error;
        });
      },
    });
    // Fail-soft proof is a committed reading, so the pass carrying it succeeds; the
    // failure reaches the user through the coordinator's report instead.
    const ready = presenter.sync("value");
    coordinator.seal(publication);
    await ready;

    assert.equal(failures.length, 1);
    assert.equal(coordinator.read().presentedEpoch, 0);
    assert.equal(coordinator.committed("thread", renderer, "value").status, "failed");
  });

test("a paint that claims another region joins the same pass", async () => {
  const { coordinator } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const painted = [];
  const schedule = createPresentationFlow((callback) => callback);
  const projection = schedule.group();
  const following = schedule.presenter({
    attach: () => coordinator.attach("thread", {}),
    after: () => [projection],
    paint: (value) => {
      painted.push(`thread:${value}`);
      return value;
    },
  });
  let again = true;
  const leading = schedule.presenter({
    attach: () => coordinator.attach("projection:chrome", {}),
    group: projection,
    paint: (value) => {
      painted.push(`projection:${value}`);
      if (again) {
        again = false;
        afterRender(() => {
          void following.sync("mounted");
        });
      }
      return value;
    },
  });
  const ready = leading.sync("first");
  coordinator.seal(publication);
  await ready;

  // The claim a paint makes belongs to the same pass, so the promise the pass hands
  // back is proof that the page caught up rather than that one renderer ran.
  assert.deepEqual(painted, ["projection:first", "thread:mounted"]);
  assert.equal(coordinator.read().presentedEpoch, 0);
});

test("a reading claimed mid-paint is installed before the finished one settles", async () => {
  const { coordinator } = setup();
  const document = {};
  const renderer = {};
  const publication = coordinator.begin(document, 0);
  const schedule = createPresentationFlow((callback) => callback);
  let claimDuringPaint = null;
  const readings = [];
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("thread", renderer),
    paint: async (value) => {
      claimDuringPaint?.();
      claimDuringPaint = null;
      await flushed();
      // The region is never presented on the older value while a newer one is owed.
      readings.push(coordinator.read().presentedEpoch);
      return value;
    },
  });
  claimDuringPaint = () => void presenter.sync("second");
  const ready = presenter.sync("first");
  coordinator.seal(publication);
  await ready;

  assert.deepEqual(readings, [-1, -1]);
  assert.equal(coordinator.read().presentedEpoch, 0);
  assert.equal(coordinator.committed("thread", renderer, "second").status, "committed");
});

test("a paint that fails after a newer claim supersedes it still reports", async () => {
  const { coordinator, failures } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const schedule = createPresentationFlow((callback) => callback);
  const slow = Promise.withResolvers();
  const renderer = {};
  let first = true;
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("thread", renderer),
    paint: (value) => {
      if (!first) return value;
      first = false;
      return slow.promise;
    },
  });
  const stale = presenter.sync("stale");
  coordinator.seal(publication);
  await Promise.resolve();

  const current = presenter.sync("current");
  slow.reject(new Error("the superseded paint failed"));
  await Promise.allSettled([stale, current]);

  assert.deepEqual(
    failures.map((reason) => reason.message),
    ["the superseded paint failed"],
  );
  assert.equal(
    coordinator.committed("thread", renderer, "current").status,
    "committed",
    "the reading that superseded it still commits",
  );
  assert.equal(
    coordinator.committed("thread", renderer, "stale"),
    null,
    "the failed reading commits nothing",
  );
  assert.equal(coordinator.read().presentedEpoch, 0);
});

for (const order of ["passive-first", "input-first"]) {
  test(`coalesced presenters retain each claim's context: ${order}`, async () => {
    let context = null;
    let bound = 0;
    let retired = 0;
    const schedule = createPresentationFlow((callback) => {
      bound++;
      const captured = context;
      return () => {
        const prior = context;
        context = captured;
        try {
          return callback();
        } finally {
          context = prior;
          retired++;
        }
      };
    });
    const { coordinator } = setup();
    coordinator.begin({}, 0);
    const painted = [];
    const presenter = (name) =>
      schedule.presenter({
        attach: () => coordinator.attach(name, {}),
        paint: () => {
          painted.push([name, context]);
          afterRender(() => {
            assert.equal(context, name === "input" ? "press" : null);
          });
        },
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
      new Map(painted),
      new Map([
        ["passive", null],
        ["input", "press"],
      ]),
    );
    assert.equal(context, "unrelated");
    assert.equal(bound, retired, "every captured job retired in its own context");
  });
}

test("region readiness observes completion and same-epoch replacement without other domains", async () => {
  const { coordinator } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const current = () => publication;
  const first = coordinator.attach("widget", {});
  const other = coordinator.attach("data", {});
  const painting = first.present("initial");
  other.present("data");
  const seen = [];
  const stop = coordinator.subscribe(() => {
    seen.push(coordinator.currentRegionsPresented(current, ["widget"]));
  });
  assert.equal(coordinator.currentRegionsPresented(current, ["widget"]), false);
  coordinator.seal(publication);
  painting.resolve();
  await painting.ready;
  assert.equal(coordinator.currentRegionsPresented(current, ["widget"]), true);
  assert.equal(coordinator.currentPresented(current), false);
  assert.equal(seen.at(-1), true);

  const replacement = coordinator.attach("widget", {});
  assert.equal(coordinator.currentRegionsPresented(current, ["widget"]), false);
  flush();
  assert.equal(seen.at(-1), false);
  const replacementPaint = replacement.present("replacement");
  first.disconnect();
  assert.equal(coordinator.currentRegionsPresented(current, ["widget"]), false);
  replacementPaint.resolve();
  await replacementPaint.ready;
  assert.equal(coordinator.currentRegionsPresented(current, ["widget"]), true);
  assert.equal(seen.at(-1), true);

  replacement.present("reopened");
  assert.equal(coordinator.currentRegionsPresented(current, ["widget"]), false);
  replacement.disconnect();
  assert.equal(coordinator.currentRegionsPresented(current, ["widget"]), false);
  await Promise.resolve();
  assert.equal(coordinator.currentRegionsPresented(current, ["widget"]), true);
  flush();
  assert.equal(seen.at(-1), true);
  const observations = seen.length;
  stop();
  other.disconnect();
  await Promise.resolve();
  assert.equal(seen.length, observations);
  assert.equal(
    coordinator.currentRegionsPresented(() => null, ["widget"]),
    false,
  );
});

test("a failing proof observer cannot fail or starve renderer completion", async () => {
  const { coordinator, failures } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const current = () => publication;
  const handle = coordinator.attach("widget", {});
  const stopFailed = coordinator.subscribe(() => {
    throw new Error("observer broke");
  });
  let observed = false;
  const stopHealthy = coordinator.subscribe(() => {
    observed = coordinator.currentRegionsPresented(current, ["widget"]);
  });
  coordinator.seal(publication);
  await presented(handle, "visible", undefined);
  assert.equal(observed, true);
  assert.equal(coordinator.currentPresented(current), true);
  assert.ok(failures.every((reason) => reason.message === "observer broke"));
  assert.ok(failures.length > 0);
  stopFailed();
  stopHealthy();
});

test("a paint creating a child presentation does not subscribe to proof changes", async () => {
  const { coordinator } = setup();
  const publication = coordinator.begin({}, 0);
  let paints = 0;
  let child;
  const stop = watchReaction(
    () => {
      paints += 1;
      // A widget can connect while its containing region paints. Its own presentation
      // belongs to that widget, and resolving it must not repaint the containing region.
      if (paints === 1) child = coordinator.attach("child", {}).present("drawn");
    },
    () => paints++,
  );
  try {
    coordinator.seal(publication);
    child.resolve("ready");
    await child.ready;
    assert.equal(paints, 1);
  } finally {
    stop();
  }
});

test("retiring a queued draw can reenter without running a job twice or losing its successor", async () => {
  let reenter = () => {};
  const flow = createPresentationFlow((callback) => {
    let invoked = false;
    return () => {
      assert.equal(invoked, false, "each attributed invocation runs once");
      invoked = true;
      reenter();
      return callback();
    };
  });
  const task = flow.task();
  const painted = [];
  const first = task.enqueue(() => painted.push("first"));
  let nested;
  reenter = () => {
    reenter = () => {};
    nested = task.enqueue(() => painted.push("nested"));
  };
  try {
    const superseded = task.enqueue(() => painted.push("superseded"));
    flush();
    await Promise.all([first, superseded, nested, flow.passed()]);
    assert.deepEqual(painted, ["nested"]);
  } finally {
    task.disconnect();
  }
});
