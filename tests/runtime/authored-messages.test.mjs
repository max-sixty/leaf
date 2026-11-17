/* An agent's message holding HTML prepares once for each wording, from its rendered
   Markdown, before joining any thread surface, and keeps that preparation when its
   original nodes move out of the inert fragment. */
import assert from "node:assert/strict";
import test from "node:test";
import { registerHooks } from "node:module";
import { loadMarkdown } from "/runtime/markdown.js";
import { adoptRegistry } from "/runtime/registry.js";
import {
  islandChange,
  messageHolding,
  prepareAuthoredMessage,
} from "/runtime/thread/messages.js";

// Keep the browser loader's real import boundary without putting fixture modules in
// the shipped widget tree. Every test removes its resolver after the import settles.
function widgetModule(t, tag, url) {
  const hooks = registerHooks({
    resolve(specifier, context, next) {
      if (specifier.endsWith(`/widgets/${tag}.js`)) return { url, shortCircuit: true };
      return next(specifier, context);
    },
  });
  t.after(() => hooks.deregister());
}

test("overlapping message reads share preparation and retain it through surface moves", async (t) => {
  const started = Promise.withResolvers();
  const released = Promise.withResolvers();
  globalThis.messagePreparation = { started, released };
  // A real widget module, held at its evaluation boundary.
  const initializer = `data:text/javascript,${encodeURIComponent(`
    globalThis.messagePreparation.started.resolve();
    await globalThis.messagePreparation.released.promise;
  `)}`;
  adoptRegistry({
    $layer: { generation: "frozen-message-preparation" },
    "lf-message-preparation": {},
    $modules: { "lf-message-preparation": "widgets/lf-message-preparation.js" },
  });
  widgetModule(t, "lf-message-preparation", initializer);
  assert.equal(await loadMarkdown(), true);
  const message = {
    id: "prepared-message",
    text: '<lf-message-preparation id="prepared-widget">Original words</lf-message-preparation>',
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
  assert.equal(prepared.body.text.trim(), "Original words");
  const original = prepared.nodes[0];
  document.body.append(original);
  original.textContent = "Drawn words";
  assert.equal(prepared.root.contains(original), false);
  assert.equal(prepareAuthoredMessage(message, "prepared-thread"), first);
  assert.equal((await overlap).nodes[0], original);
  assert.equal(prepared.body.text.trim(), "Original words");
  assert.throws(
    () => prepareAuthoredMessage(message, "another-thread"),
    /changed its document identity/,
  );
  original.remove();
  delete globalThis.messagePreparation;
});

// An agent's edit gives the message new words, each wording an island of its own. The
// reading the page adopts decides which island its widgets answer for: the ids the
// adopted island held and the new one doesn't leave, and an edit leaving no HTML
// takes them all.
test("adopting an edit's island retires the widgets the wording before it held", async () => {
  adoptRegistry({
    $layer: { generation: "edited-message" },
    "lf-options": {},
    "lf-option": {},
  });
  assert.equal(await loadMarkdown(), true);
  const choice = (id, label) =>
    `<lf-options id="${id}" choose><lf-option id="${id}-a">${label}</lf-option></lf-options>`;
  const message = { id: "edited-message" };
  const sentText = `Pick:\n\n${choice("edited-first", "First")}`;
  const sent = await prepareAuthoredMessage(
    { ...message, text: sentText },
    "edited-thread",
  );
  islandChange([{ message, frozen: sent }]).commit();
  assert.equal(messageHolding("edited-first-a")?.message, "edited-message");

  const rewritten = await prepareAuthoredMessage(
    { ...message, text: `Pick again:\n\n${choice("edited-second", "Second")}` },
    "edited-thread",
  );
  assert.notEqual(rewritten, sent);
  assert.equal(rewritten.body.text, "Pick again: Second");
  // The wording a held drawing still shows keeps its own island.
  assert.equal(
    await prepareAuthoredMessage({ ...message, text: sentText }, "edited-thread"),
    sent,
  );
  const edit = islandChange([{ message, frozen: rewritten }]);
  assert.deepEqual(edit.retired, ["edited-first", "edited-first-a"]);
  assert.equal(messageHolding("edited-first-a")?.message, "edited-message");
  edit.commit();
  assert.equal(messageHolding("edited-first-a"), null);
  assert.equal(messageHolding("edited-second-a")?.message, "edited-message");
  assert.deepEqual(islandChange([{ message, frozen: rewritten }]).retired, []);

  const withdrawn = islandChange([{ message, frozen: null }]);
  assert.deepEqual(withdrawn.retired, ["edited-second", "edited-second-a"]);
  withdrawn.commit();
  assert.equal(messageHolding("edited-second-a"), null);
});

// A thread named by its opening message, and On Me's row for a reply, read these words
// on one line: a choice's options read apart, as its accessible name and page search
// read them, not run together as "Open it nowHold it".
test("a message's words part its blocks, as the page reading does", async () => {
  adoptRegistry({
    $layer: { generation: "message-words" },
    "lf-options": {},
    "lf-option": {},
  });
  assert.equal(await loadMarkdown(), true);
  const prepared = await prepareAuthoredMessage(
    {
      id: "worded-message",
      text:
        'Pick one:\n\n<lf-options id="worded-choice" choose>' +
        '<lf-option id="worded-now"><strong>Open it now</strong></lf-option>' +
        '<lf-option id="worded-hold"><strong>Hold</strong> <em>it</em></lf-option>' +
        "</lf-options>",
    },
    "worded-thread",
  );
  assert.equal(prepared.body.text, "Pick one: Open it now Hold it");
});

test("failed message preparation reaches every waiting state read and later reads", async (t) => {
  const initializer = `data:text/javascript,${encodeURIComponent(
    'throw new Error("message initializer failed");',
  )}`;
  adoptRegistry({
    $layer: { generation: "failed-frozen-message-preparation" },
    "lf-message-failure": {},
    $modules: { "lf-message-failure": "widgets/lf-message-failure.js" },
  });
  widgetModule(t, "lf-message-failure", initializer);
  assert.equal(await loadMarkdown(), true);
  const message = {
    id: "failed-prepared-message",
    text: '<lf-message-failure id="failed-prepared-widget"></lf-message-failure>',
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
