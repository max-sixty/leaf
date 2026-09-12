import assert from "node:assert/strict";
import test from "node:test";
import { createPresentationCoordinator } from "./presentation.ts";

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

  releaseFirst();
  await first;
  await Promise.resolve();
  assert.equal(ready, false);
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
});
