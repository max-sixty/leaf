import assert from "node:assert/strict";
import test from "node:test";
import { effect } from "/runtime/framework.js";
import { ThreadView } from "/runtime/thread/thread-card.js";
import { commandDeclarationsWithin } from "/runtime/keyboard/scopes.js";

// Every card draws its reply box; this stands in for the box's input wiring, which
// composing-input.test.mjs covers.
const wireInput = () =>
  Object.assign(() => {}, {
    value: () => "",
    button: null,
    load() {},
    cancelDictation() {},
  });

test("a thread card's output updates its commands without invalidating its presenter", () => {
  const model = {
    key: "card-presentation",
    id: "card-presentation",
    summary: { topic: "A thread" },
    surface: "margin",
    messages: [],
    summaries: [],
    todos: [],
    working: null,
    news: null,
    settlement: { kind: "resolve", label: "Resolve", word: "Resolve" },
  };
  const view = new ThreadView({ reply: { wireInput }, reaction: {} }, model);
  let paints = 0;
  const stopPaint = effect(() => {
    paints++;
    view.present(model);
  });
  document.body.append(view.node);
  const button = view.node.querySelector("button");
  button.focus();
  try {
    assert.equal(paints, 1);
    view.present({
      ...model,
      resolved: true,
      settlement: { kind: "unresolve", label: "Reopen" },
    });
    assert.equal(paints, 1);
    assert.equal(view.node.querySelector("button"), button);
    assert.equal(document.activeElement, button);
    assert.equal(button.getAttribute("aria-label"), "Reopen");
    assert.deepEqual(
      commandDeclarationsWithin(view.node).flatMap(({ scope }) =>
        scope.rows.map(({ id }) => id),
      ),
      ["thread.reopen"],
    );
  } finally {
    stopPaint();
    view.dispose();
    view.node.remove();
  }
});

test("a primary reply forwards the field's live hint and accessible name callbacks", async () => {
  const { createReplyView } = await import("/runtime/thread/replies.js");
  const home = document.createElement("section");
  const hintParts = () => ["Waiting on the agent"];
  const hintLead = () => ["Reply"];
  const accessibleName = () => "Reply to this thread";
  let inputOptions;
  const view = createReplyView(
    "hint-forwarding",
    home,
    {
      wireInput: (_input, options) => {
        inputOptions = options;
        return wireInput();
      },
    },
    () => {},
    { hintParts, hintLead, accessibleName },
  );
  try {
    assert.equal(inputOptions.hintParts, hintParts);
    assert.equal(inputOptions.hintLead, hintLead);
    assert.equal(inputOptions.accessibleName, accessibleName);
  } finally {
    view.dispose();
  }
});

test("a thread preview registers its keyboard routes before any conversation is selected", async () => {
  const { createThreadPreview } =
    await import("/runtime/annotation-overlay/thread-preview.js");
  const preview = createThreadPreview({
    inventory: {
      targetFor: () => null,
      entryPoint: () => null,
      entryPlace: () => null,
    },
    renderMarginThread: () => [],
    placedAt: () => undefined,
    scrollThreadIntoView() {},
    scrollToElement() {},
    openPageThread() {},
    openInPanel() {},
    onClose() {},
  });
  assert.equal(preview.isOpen(), false);
  assert.equal(preview.selection(), null);
  assert.deepEqual(
    commandDeclarationsWithin(preview.element).flatMap(({ scope }) =>
      scope.rows.map(({ id }) => id),
    ),
    [],
  );
});
