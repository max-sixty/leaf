import assert from "node:assert/strict";
import test from "node:test";
import { watchReaction, subscribe } from "/vendor/browser-runtime.js";
import { ThreadView } from "/runtime/thread/thread-card.js";
import { commandDeclarationsWithin } from "/runtime/keyboard/scopes.js";

test("a thread card's output updates its commands without invalidating its presenter", () => {
  const view = new ThreadView({ reply: {}, reaction: {} });
  const model = {
    key: "card-presentation",
    id: "card-presentation",
    summary: { topic: "A thread" },
    surface: "margin",
    messages: [],
    summaries: [],
    reply: false,
    working: null,
    news: null,
    settlement: { kind: "resolve", pending: false, label: "Resolve", word: "Resolve" },
  };
  let paints = 0;
  const stopPaint = watchReaction(
    () => {
      paints++;
      view.present(model);
    },
    () => paints++,
  );
  document.body.append(view.node);
  const command = commandDeclarationsWithin(view.node)
    .flatMap(({ scope }) => scope.rows)
    .find(({ id }) => id === "thread.resolve");
  const availability = [];
  const stopCommand = subscribe(
    () => command.when(),
    (value) => availability.push(value),
  );
  try {
    assert.equal(paints, 1);
    view.present({ ...model, settlement: { ...model.settlement, pending: true } });
    assert.equal(paints, 1);
    assert.deepEqual(availability, [true, false]);
    assert.equal(view.node.querySelector("button").getAttribute("aria-busy"), "true");
  } finally {
    stopPaint();
    stopCommand();
    view.dispose();
    view.node.remove();
  }
});
