/* A reply's reaction strip asks for the state its press means: off for a reaction the
   user already has on the reply, on for one they don't. The choices come from the
   thread model's `tokenChoices`, so the strip reads the field that model writes. */

import assert from "node:assert/strict";
import test from "node:test";

const { ReactionStripView } = await import("/runtime/thread/reaction-strips.js");
const { tokenChoices } = await import("/runtime/thread/model.js");

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
    choices: tokenChoices({ ok: { glyph: "👍" }, no: { glyph: "👎" } }, inForce),
  });
  const press = (token) => view.node.querySelector(`[data-token="${token}"]`).click();
  return { asked, press, view };
}

test("pressing a reaction the user has takes it back", () => {
  const { asked, press, view } = strip([{ id: "r1", token: "ok" }]);
  assert.equal(
    view.node.querySelector('[data-token="ok"]').getAttribute("aria-pressed"),
    "true",
  );
  press("ok");
  assert.deepEqual(asked, [["t1", "m1", "ok", false]]);
});

test("pressing a reaction the user does not have puts it on", () => {
  const { asked, press } = strip([{ id: "r1", token: "ok" }]);
  press("no");
  assert.deepEqual(asked, [["t1", "m1", "no", true]]);
});

test("a trigger drawn again is the one the picker opens from", async () => {
  const { html, nothing, render } = await import("/runtime/framework.js");
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
