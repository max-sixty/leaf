import assert from "node:assert/strict";
import test from "node:test";
import { effect } from "/vendor/signals-core.js";
import { ThreadView } from "/runtime/records/thread/thread-card.js";
import { commandDeclarationsWithin } from "/runtime/dom/keyboard/scopes.js";

// Every card draws its reply box; this stands in for the box's input wiring, which
// composing-input.test.mjs covers.
const wireInput = () =>
  Object.assign(() => {}, {
    value: () => "",
    button: null,
    load() {},
    cancelDictation() {},
  });

/** A card's model with no messages, named `name`. */
const cardModel = (name = "A thread") => ({
  key: "card-presentation",
  id: "card-presentation",
  name,
  surface: "margin",
  messages: [],
  summaries: [],
  todos: [],
  working: null,
  news: null,
  settlement: { kind: "resolve", label: "Resolve", word: "Resolve" },
  source: { id: "card-presentation", anchor: null, root: {} },
});

test("a thread card's output updates its commands without invalidating its presenter", () => {
  const model = cardModel();
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

test("a thread card names its thread by the opening of its name, not its whole first message", () => {
  // An untitled thread's name is its first message, which the card reads next.
  const opening =
    "The CLI exiting does not mean its background children have stopped. They could " +
    "still replace an output while we read it. Make an empty sandbox a precondition.";
  for (const [name, said] of [
    ["Sandbox export", "Thread, Sandbox export"],
    [opening, "Thread, The CLI exiting does not mean its background children have…"],
  ]) {
    const view = new ThreadView(
      { reply: { wireInput }, reaction: {} },
      cardModel(name),
    );
    try {
      view.present(cardModel(name));
      assert.equal(view.node.getAttribute("role"), "group");
      assert.equal(view.node.getAttribute("aria-label"), said);
    } finally {
      view.dispose();
    }
  }
});

test("a primary reply forwards the field's live hint and accessible name callbacks", async () => {
  const { createReplyView } = await import("/runtime/records/thread/replies.js");
  const hintParts = () => ["Waiting on the agent"];
  const hintLead = () => ["Reply"];
  const accessibleName = () => "Reply to this thread";
  let inputOptions;
  const view = createReplyView(
    "hint-forwarding",
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
    assert.deepEqual(inputOptions.hintParts(), hintParts());
    assert.deepEqual(inputOptions.hintLead(), hintLead());
    assert.equal(inputOptions.accessibleName(), accessibleName());
  } finally {
    view.dispose();
  }
});

test("a thread preview registers its keyboard routes before any conversation is selected", async () => {
  const { createThreadPreview } =
    await import("/runtime/annotations/annotation-overlay/thread-preview.js");
  const preview = createThreadPreview({
    inventory: {
      targetFor: () => null,
      entryPoint: () => null,
      entryPlace: () => null,
    },
    renderMarginThread: () => ({ drawn: [], stop: () => {} }),
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
