/* An agent's message holding HTML prepares once, from its rendered Markdown, before
   joining any thread surface, and keeps that preparation when its original nodes
   move out of the inert fragment. */
import assert from "node:assert/strict";
import test from "node:test";
import { registerHooks } from "node:module";
import { loadMarkdown } from "/runtime/markdown.js";
import { adoptRegistry } from "/runtime/registry.js";
import { prepareAuthoredMessage } from "/runtime/thread/messages.js";

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
    /changed its frozen document identity/,
  );
  original.remove();
  delete globalThis.messagePreparation;
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
        'Pick one:\n\n<lf-options id="worded-choice">' +
        '<lf-option id="worded-now"><strong>Open it now</strong></lf-option>' +
        '<lf-option id="worded-hold"><strong>Hold</strong> <em>it</em></lf-option>' +
        "</lf-options>",
    },
    "worded-thread",
  );
  assert.equal(prepared.body.text, "Pick one: Open it now Hold it");
});

// An option's title is its label, which the message writes as words where it draws, so
// the message's words hold it too.
test("a message's words hold its options' labels", async () => {
  adoptRegistry({
    $layer: { generation: "message-labels" },
    "lf-options": {},
    "lf-option": { says: { label: "before" } },
  });
  assert.equal(await loadMarkdown(), true);
  const prepared = await prepareAuthoredMessage(
    {
      id: "labelled-message",
      text:
        'Pick one:\n\n<lf-options id="labelled-choice">\n' +
        '<lf-option id="labelled-now" label="Open it now">Today.</lf-option>\n' +
        '<lf-option id="labelled-hold" label="Hold it"></lf-option>\n' +
        "</lf-options>",
    },
    "labelled-thread",
  );
  assert.equal(prepared.body.text, "Pick one: Open it now Today. Hold it");
});

// A drawing that doesn't hold the message's widgets, such as a margin card while the
// panel holds them, draws the message less its widgets. The named group round a widget
// that asks is that widget's question and goes with it; an element round a widget that
// asks nothing, as a figure round a chart, keeps its caption.
test("a drawing that doesn't hold a message's widgets drops only a question's group", async () => {
  adoptRegistry({
    $layer: { generation: "message-held-elsewhere" },
    "lf-options": { awaits: { value: "choose" } },
    "lf-option": {},
    "lf-chart": {},
    "lf-group": { "reading-role": "group" },
  });
  assert.equal(await loadMarkdown(), true);
  const prepared = await prepareAuthoredMessage(
    {
      id: "held-message",
      text:
        '<figure id="held-latency">' +
        '<lf-chart id="held-chart"></lf-chart>' +
        '<figcaption id="held-latency-caption">Latency by day</figcaption></figure>\n\n' +
        '<lf-group id="held-ask" label="Roll back now?">' +
        '<lf-options id="held-choice"><lf-option id="held-yes">Yes</lf-option>' +
        "</lf-options></lf-group>",
    },
    "held-thread",
  );
  const drawn = document.createElement("div");
  drawn.innerHTML = prepared.body.heldElsewhere;
  assert.equal(drawn.querySelector("figure figcaption")?.textContent, "Latency by day");
  assert.equal(drawn.querySelector("lf-chart, lf-options, [id]"), null);
  assert.equal(drawn.textContent.includes("Roll back now?"), false);
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
