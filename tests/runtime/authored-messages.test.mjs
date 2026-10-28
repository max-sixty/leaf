/* Frozen message documents prepare once before joining any thread surface, and
   keep that preparation when their original nodes move out of the inert fragment. */
import assert from "node:assert/strict";
import test from "node:test";
import { adoptRegistry } from "/runtime/registry.js";
import { prepareAuthoredMessage } from "/runtime/thread/messages.js";

test("overlapping message reads share preparation and retain it through surface moves", async () => {
  const started = Promise.withResolvers();
  const released = Promise.withResolvers();
  globalThis.messagePreparation = { started, released };
  // A real declared lazy initializer, held at its module evaluation boundary.
  const initializer = `data:text/javascript,${encodeURIComponent(`
    globalThis.messagePreparation.started.resolve();
    await globalThis.messagePreparation.released.promise;
  `)}`;
  adoptRegistry({
    $layer: { generation: "frozen-message-preparation" },
    "lf-message-preparation": { "x-initial": initializer },
  });
  const message = {
    id: "prepared-message",
    markup:
      '<lf-message-preparation id="prepared-widget">Original words</lf-message-preparation>',
  };
  const first = prepareAuthoredMessage(message, "prepared-thread");
  const overlap = prepareAuthoredMessage(message, "prepared-thread");
  assert.equal(overlap, first);
  await started.promise;
  let complete = false;
  first.then(() => {
    complete = true;
  });
  assert.equal(complete, false);
  released.resolve();
  const prepared = await first;
  assert.equal(prepared.body.text, "Original words");
  const original = prepared.nodes[0];
  document.body.append(original);
  original.textContent = "Drawn words";
  assert.equal(prepared.root.childNodes.length, 0);
  assert.equal(prepareAuthoredMessage(message, "prepared-thread"), first);
  assert.equal((await overlap).nodes[0], original);
  assert.equal(prepared.body.text, "Original words");
  assert.throws(
    () => prepareAuthoredMessage(message, "another-thread"),
    /changed its frozen document identity/,
  );
  original.remove();
  delete globalThis.messagePreparation;
});

test("failed message preparation reaches every waiting state read and later reads", async () => {
  const initializer = `data:text/javascript,${encodeURIComponent(
    'throw new Error("message initializer failed");',
  )}`;
  adoptRegistry({
    $layer: { generation: "failed-frozen-message-preparation" },
    "lf-message-failure": { "x-initial": initializer },
  });
  const message = {
    id: "failed-prepared-message",
    markup: '<lf-message-failure id="failed-prepared-widget"></lf-message-failure>',
  };
  const first = prepareAuthoredMessage(message, "failed-prepared-thread");
  const overlap = prepareAuthoredMessage(message, "failed-prepared-thread");
  await Promise.all(
    [first, overlap].map((read) => assert.rejects(read, /message initializer failed/)),
  );
  await assert.rejects(
    prepareAuthoredMessage(message, "failed-prepared-thread"),
    /message initializer failed/,
  );
});
