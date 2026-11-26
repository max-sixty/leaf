/* A reply's reaction strip asks for the state its press means: off for a reaction the
   user already has on the reply, on for one they don't. The choices come from the
   thread model's `emojiChoices`, so the strip reads the field that model writes. */

import assert from "node:assert/strict";
import test from "node:test";

const { ReactionStripView } =
  await import("/runtime/records/thread/reaction-strips.js");
const { emojiChoices } = await import("/runtime/state/thread/model.js");

function strip(inForce) {
  const asked = [];
  const view = new ReactionStripView({
    registerSurface: () => ({ close() {}, toggle() {} }),
    actions: { setReaction: (...args) => asked.push(args) },
    pressed() {},
  });
  document.body.replaceChildren(view.node);
  view.present({
    thread: "t1",
    message: "m1",
    latest: true,
    choices: emojiChoices(["👍", "👎"], inForce),
  });
  const press = (emoji) =>
    view.node.querySelector(`[data-lf-emoji="${emoji}"]`).click();
  return { asked, press, view };
}

test("pressing a reaction the user has takes it back", () => {
  const { asked, press, view } = strip([{ id: "r1", emoji: "👍" }]);
  assert.equal(
    view.node.querySelector('[data-lf-emoji="👍"]').getAttribute("aria-pressed"),
    "true",
  );
  press("👍");
  assert.deepEqual(asked, [["t1", "m1", "👍", false]]);
});

test("pressing a reaction the user does not have puts it on", () => {
  const { asked, press } = strip([{ id: "r1", emoji: "👍" }]);
  press("👎");
  assert.deepEqual(asked, [["t1", "m1", "👎", true]]);
});

test("a trigger drawn again is the one the picker opens from", async () => {
  const { html, nothing, render } = await import("/vendor/lit.js");
  const registered = [];
  const view = new ReactionStripView({
    registerSurface: (_surface, { trigger }) => {
      registered.push(trigger);
      return { close() {}, toggle() {} };
    },
  });
  view.present({ thread: "t1", message: "m1", latest: true, choices: [] });
  const head = document.createElement("div");
  document.body.replaceChildren(head, view.node);
  const draw = (shown) => render(html`${shown ? view.trigger : nothing}`, head);
  draw(true);
  draw(false);
  draw(true);
  assert.equal(registered.at(-1), head.querySelector(".lf-react-trigger"));
});

test("a mounted reaction sends before closing the picker and revealing held news", async () => {
  const { html, render } = await import("/vendor/lit.js");
  const order = [];
  const view = new ReactionStripView({
    registerSurface: () => ({ close: () => order.push("close"), toggle() {} }),
    actions: { setReaction: () => order.push("send") },
    pressed: () => order.push("news"),
  });
  const head = document.createElement("div");
  view.present({
    thread: "t1",
    message: "m1",
    latest: true,
    choices: emojiChoices(["👍"], []),
  });
  document.body.replaceChildren(head, view.node);
  render(html`${view.trigger}`, head);
  view.node.querySelector('[data-lf-emoji="👍"]').click();
  assert.deepEqual(order, ["send", "close", "news"]);
});
