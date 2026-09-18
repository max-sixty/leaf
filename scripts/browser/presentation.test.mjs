import assert from "node:assert/strict";
import test from "node:test";
import {
  createPresentationCoordinator,
  createPresentationSchedule,
  describeFailure,
  PRESENTATION_HELD,
} from "./presentation.ts";

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((accept, refuse) => {
    resolve = accept;
    reject = refuse;
  });
  return { promise, resolve, reject };
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
  const older = deferred();
  const newer = deferred();
  const olderPresentation = handle.present("older", older.promise);
  const newerPresentation = handle.present("newer", newer.promise);
  coordinator.seal(publication);

  older.resolve("older proof");
  await olderPresentation;
  assert.equal(coordinator.read().presentedEpoch, -1);
  assert.equal(coordinator.committed("widget", renderer, "older"), null);

  newer.resolve("newer proof");
  await newerPresentation;
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

test("a disconnected renderer retires its work and ignores a late completion", async () => {
  const { coordinator, failures } = setup();
  const document = {};
  const renderer = {};
  const publication = coordinator.begin(document, 0);
  const handle = coordinator.attach("widget", renderer);
  const work = deferred();
  const presentation = handle.present("value", work.promise);
  coordinator.seal(publication);
  handle.disconnect();

  await new Promise(queueMicrotask);
  assert.equal(await coordinator.whenPresented(document, 0), "presented");
  work.resolve("obsolete proof");
  await presentation;
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
  const oldWork = deferred();
  const oldPresentation = oldHandle.present("value", oldWork.promise);
  coordinator.seal(publication);

  oldHandle.disconnect();
  const newHandle = coordinator.attach("widget", newRenderer);
  const newWork = deferred();
  const newPresentation = newHandle.present("value", newWork.promise);
  await new Promise(queueMicrotask);
  oldWork.resolve("old proof");
  await oldPresentation;
  assert.equal(coordinator.read().presentedEpoch, -1);

  newWork.resolve("new proof");
  await newPresentation;
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
  const oldWork = deferred();
  const oldPresentation = oldHandle.present("same", oldWork.promise);
  coordinator.seal(publication);

  oldHandle.disconnect();
  await new Promise(queueMicrotask);
  assert.equal(await coordinator.whenPresented(document, 0), "presented");
  assert.equal(coordinator.read().presentedEpoch, 0);

  const newRenderer = {};
  const replacement = coordinator.attach("widget", newRenderer);
  const replacementWork = deferred();
  const replacementPresentation = replacement.present("same", replacementWork.promise);
  const readiness = coordinator.whenPresented(document, 0);
  let ready = false;
  void readiness.then(() => {
    ready = true;
  });
  await Promise.resolve();
  assert.equal(ready, false);
  assert.deepEqual(coordinator.read().pending, ["widget"]);

  oldWork.resolve("obsolete proof");
  await oldPresentation;
  assert.equal(ready, false);
  assert.equal(coordinator.committed("widget", oldRenderer, "same"), null);

  replacementWork.resolve("replacement proof");
  await replacementPresentation;
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
  await oldHandle.present("same", "old proof");
  coordinator.seal(publication);
  assert.equal(await coordinator.whenPresented(document, 0), "presented");

  oldHandle.disconnect();
  const obsoleteWork = deferred();
  const obsoletePresentation = oldHandle.present("same", obsoleteWork.promise);
  const newRenderer = {};
  const replacement = coordinator.attach("widget", newRenderer);
  const replacementWork = deferred();
  const replacementPresentation = replacement.present("same", replacementWork.promise);
  const readiness = coordinator.whenPresented(document, 0);
  let ready = false;
  void readiness.then(() => {
    ready = true;
  });
  await Promise.resolve();
  assert.equal(ready, false);
  assert.deepEqual(coordinator.read().pending, ["widget"]);

  obsoleteWork.resolve("obsolete proof");
  await obsoletePresentation;
  assert.equal(ready, false);
  assert.equal(coordinator.committed("widget", oldRenderer, "same"), null);

  replacementWork.resolve("replacement proof");
  await replacementPresentation;
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
  await handle.present("value", "proof");
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
  const parentWork = deferred();
  const parentPresentation = parent.present("parent value", parentWork.promise);
  coordinator.seal(publication);

  const child = coordinator.attach("child", {});
  const childWork = deferred();
  const childPresentation = child.present("child value", childWork.promise);
  parentWork.resolve("parent proof");
  await parentPresentation;
  assert.deepEqual(coordinator.read().pending, ["child"]);

  childWork.resolve("child proof");
  await childPresentation;
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
  const stableWork = deferred();
  const oldChangedWork = deferred();
  const stablePresentation = stable.present("same", stableWork.promise);
  const oldChangedPresentation = changed.present("old", oldChangedWork.promise);
  coordinator.seal(first);

  const second = coordinator.begin(document, 1);
  const newChangedWork = deferred();
  const newChangedPresentation = changed.present("new", newChangedWork.promise);
  coordinator.seal(second);
  stableWork.resolve("stable proof");
  await stablePresentation;
  oldChangedWork.resolve("old proof");
  await oldChangedPresentation;
  assert.deepEqual(coordinator.read().pending, ["changed"]);
  assert.equal(coordinator.committed("changed", changedRenderer, "old"), null);

  newChangedWork.resolve("new proof");
  await newChangedPresentation;
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
  await handle.present("value", "proof");

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
  const oldWork = deferred();
  const oldPresentation = handle.present("old", oldWork.promise);
  coordinator.seal(oldPublication);
  const oldWait = coordinator.whenPresented(oldDocument, 4);

  const newDocument = {};
  const newPublication = coordinator.begin(newDocument, 0);
  coordinator.seal(newPublication);
  assert.equal(await oldWait, "superseded");
  assert.equal(await coordinator.whenPresented(newDocument, 0), "presented");
  oldWork.resolve("old proof");
  await oldPresentation;
  assert.equal(coordinator.committed("widget", renderer, "old"), null);
  assert.equal(coordinator.read().document, newDocument);
});

test("a failed presentation reports once, installs fail-soft proof, and settles", async () => {
  const { coordinator, failures } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const renderer = {};
  const handle = coordinator.attach("widget", renderer);
  const work = deferred();
  const fallback = [];
  const presentation = handle.present("value", work.promise, (reason) => {
    fallback.push(reason);
    return "fallback proof";
  });
  coordinator.seal(publication);
  const error = new Error("renderer failed");
  work.reject(error);
  await presentation;

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
  const presentation = handle.present("value", Promise.reject(rendering), () => {
    throw retaining;
  });
  coordinator.seal(publication);
  await assert.rejects(presentation, (error) => {
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
  const presentation = handle.present("value", Promise.reject(error));
  coordinator.seal(publication);
  await assert.rejects(presentation, error);

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
  let releaseFirst;
  const first = renderer.present(
    "first",
    new Promise((resolve) => {
      releaseFirst = resolve;
    }),
  );
  coordinator.seal(firstPublication);

  const stale = coordinator.whenPresented(document, 0);
  let releaseSecond;
  let second;
  stale.then(() => {
    current = { document, semanticEpoch: 1 };
    const secondPublication = coordinator.begin(document, 1);
    second = renderer.present(
      "second",
      new Promise((resolve) => {
        releaseSecond = resolve;
      }),
    );
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

  releaseFirst();
  await first;
  await Promise.resolve();
  assert.equal(ready, false);
  assert.equal(
    coordinator.currentPresented(() => current),
    false,
  );
  assert.deepEqual(coordinator.read().pending, ["widget"]);
  releaseSecond();
  await second;
  assert.equal(await readiness, "presented");
});

test("current readiness follows a same-epoch renderer replacement", async () => {
  const document = {};
  const coordinator = createPresentationCoordinator({ reportFailure: assert.fail });
  const current = { document, semanticEpoch: 0 };
  const publication = coordinator.begin(document, 0);
  const firstRenderer = coordinator.attach("widget", {});
  let releaseFirst;
  const first = firstRenderer.present(
    "value",
    new Promise((resolve) => {
      releaseFirst = resolve;
    }),
  );
  coordinator.seal(publication);

  const stale = coordinator.whenPresented(document, 0);
  let releaseReplacement;
  let replacement;
  stale.then(() => {
    firstRenderer.disconnect();
    const nextRenderer = coordinator.attach("widget", {});
    replacement = nextRenderer.present(
      "value",
      new Promise((resolve) => {
        releaseReplacement = resolve;
      }),
    );
  });
  let ready = false;
  const readiness = coordinator
    .whenCurrentPresented(() => current)
    .then((outcome) => {
      ready = true;
      return outcome;
    });

  releaseFirst();
  await first;
  await Promise.resolve();
  assert.equal(ready, false);
  assert.deepEqual(coordinator.read().pending, ["widget"]);
  releaseReplacement();
  await replacement;
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
  let releasePage;
  const pagePresentation = page.present(
    "page",
    new Promise((resolve) => {
      releasePage = resolve;
    }),
  );
  let releaseThread;
  const threadPresentation = thread.present(
    "thread",
    new Promise((resolve) => {
      releaseThread = resolve;
    }),
  );
  coordinator.seal(publication);

  let ready = false;
  const readiness = coordinator
    .whenCurrentRegionsPresented(() => current, ["thread-widget"])
    .then((outcome) => {
      ready = true;
      return outcome;
    });
  releaseThread();
  await threadPresentation;
  assert.equal(await readiness, "presented");
  assert.equal(ready, true);
  assert.deepEqual(coordinator.read().pending, ["page-widget"]);
  releasePage();
  await pagePresentation;
});

test("a domain-scoped wait retires when its value is superseded in the same epoch", async () => {
  const document = {};
  const coordinator = createPresentationCoordinator({ reportFailure: assert.fail });
  const current = { document, semanticEpoch: 0 };
  const publication = coordinator.begin(document, 0);
  const data = coordinator.attach("data:feed:rows", {});
  let releaseOlder;
  const older = data.present(
    1,
    new Promise((resolve) => {
      releaseOlder = resolve;
    }),
  );
  coordinator.seal(publication);

  let wanted = true;
  const readiness = coordinator.whenCurrentRegionsPresented(
    () => (wanted ? current : null),
    ["data:feed:rows"],
  );
  wanted = false;
  const newer = data.present(2, undefined);

  assert.equal(await readiness, "superseded");
  await newer;
  releaseOlder();
  await older;
});

const flushed = () => new Promise((resolve) => setTimeout(resolve, 0));

test("one pass paints its presenters in declared order and coalesces repeated claims", async () => {
  const { coordinator } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const schedule = createPresentationSchedule();
  const painted = [];
  const presenter = (region, order) =>
    schedule.presenter({
      attach: () => coordinator.attach(region, {}),
      order,
      paint: (value) => {
        painted.push(`${region}:${value}`);
        return `${region} proof`;
      },
    });
  // Registered out of order, claimed out of order: the pass still runs them by rank.
  const late = presenter("conversation", 1);
  const early = presenter("projection", 0);
  void late.sync("first");
  void early.sync("only");
  const ready = late.sync("second");
  coordinator.seal(publication);

  assert.deepEqual(painted, []);
  await ready;
  assert.deepEqual(painted, ["projection:only", "conversation:second"]);
  assert.equal(coordinator.read().presentedEpoch, 0);
});

test("a reading held open does not keep the next one off the page", async () => {
  const { coordinator } = setup();
  const document = {};
  const renderer = {};
  const publication = coordinator.begin(document, 0);
  const schedule = createPresentationSchedule();
  const painted = [];
  let release;
  const held = new Promise((resolve) => {
    release = resolve;
  });
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("conversation", renderer),
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

  assert.equal(coordinator.committed("conversation", renderer, "newer").status, "committed");
  assert.equal(coordinator.read().presentedEpoch, 0);
});

test("a superseded claim releases its hold without painting", async () => {
  const { coordinator } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const schedule = createPresentationSchedule();
  const painted = [];
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("asks", {}),
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

test("a held reading keeps its region pending until the next claim supersedes it", async () => {
  const { coordinator } = setup();
  const document = {};
  const renderer = {};
  const publication = coordinator.begin(document, 0);
  const schedule = createPresentationSchedule();
  let hold = true;
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("projection:chrome", renderer),
    paint: (value) => (hold ? PRESENTATION_HELD : value),
  });
  const deferred = presenter.sync("deferred");
  coordinator.seal(publication);
  await deferred;
  assert.deepEqual(coordinator.read().pending, ["projection:chrome"]);

  hold = false;
  await presenter.sync("resumed");
  assert.deepEqual(coordinator.read().pending, []);
  assert.equal(coordinator.read().presentedEpoch, 0);
});

test("a failing paint reports through the region and fails the pass it was in", async () => {
  const { coordinator, failures } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const schedule = createPresentationSchedule();
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("conversation", {}),
    paint: () => {
      throw new Error("paint failed");
    },
  });
  const ready = presenter.sync("value");
  coordinator.seal(publication);

  await assert.rejects(ready, /paint failed/);
  assert.equal(failures.length, 1);
  assert.deepEqual(coordinator.read().pending, ["conversation"]);
  assert.equal(coordinator.read().presentedEpoch, -1);
});

test("a failure reported for one region does not withhold the others' readings", async () => {
  const { coordinator, failures } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const schedule = createPresentationSchedule();
  const painted = [];
  const failing = schedule.presenter({
    attach: () => coordinator.attach("projection:chrome", {}),
    order: 0,
    paint: () => {
      throw new Error("projection failed");
    },
  });
  const following = schedule.presenter({
    attach: () => coordinator.attach("conversation", {}),
    order: 1,
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
  const document = {};
  const renderer = {};
  const publication = coordinator.begin(document, 0);
  const schedule = createPresentationSchedule();
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("conversation", renderer),
    failSoft: () => "retained",
    paint: () => Promise.reject(new Error("list failed")),
  });
  // Fail-soft proof is a committed reading, so the pass carrying it succeeds; the
  // failure reaches the reader through the coordinator's report instead.
  const ready = presenter.sync("value");
  coordinator.seal(publication);
  await ready;

  assert.equal(failures.length, 1);
  assert.equal(coordinator.read().presentedEpoch, 0);
  assert.equal(coordinator.committed("conversation", renderer, "value").status, "failed");
});

test("a paint that claims another region joins the same pass", async () => {
  const { coordinator } = setup();
  const document = {};
  const publication = coordinator.begin(document, 0);
  const painted = [];
  const schedule = createPresentationSchedule();
  const following = schedule.presenter({
    attach: () => coordinator.attach("conversation", {}),
    order: 1,
    paint: (value) => {
      painted.push(`conversation:${value}`);
      return value;
    },
  });
  let again = true;
  const leading = schedule.presenter({
    attach: () => coordinator.attach("projection:chrome", {}),
    order: 0,
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
  // back is proof that the page caught up rather than that one renderer ran.
  assert.deepEqual(painted, ["projection:first", "conversation:mounted"]);
  assert.equal(coordinator.read().presentedEpoch, 0);
});

test("a reading claimed mid-paint is installed before the finished one settles", async () => {
  const { coordinator } = setup();
  const document = {};
  const renderer = {};
  const publication = coordinator.begin(document, 0);
  const schedule = createPresentationSchedule();
  let claimDuringPaint = null;
  const readings = [];
  const presenter = schedule.presenter({
    attach: () => coordinator.attach("conversation", renderer),
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
  assert.equal(coordinator.committed("conversation", renderer, "second").status, "committed");
});
