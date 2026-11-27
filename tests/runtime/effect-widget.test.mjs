/* An Effect UI component on the widget protocol (lib/effect-widget.js): when it mounts,
   what a set of `state` draws and when, and what its events say to the host. A Leaf
   page's own answers to the protocol, such as recording an `lf-action`, are the
   browser suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { Html, Schema, UiSchema } from "/vendor/effect-ui.js";
import { signal } from "/vendor/signals-core.js";
import { defineWidget, WidgetEvents, widgetProps } from "/runtime/lib/effect-widget.js";

let tags = 0;

const Message = UiSchema.TaggedEnum({ ClickedShip: {} });

// A widget that shows its `state.decide.value` and a `note` its inputs read, and
// records "ship" when its button is pressed.
const Verdict = Html.component({
  name: "Verdict",
  props: Schema.Struct({ ...widgetProps, note: Schema.optional(Schema.String) }),
  model: Schema.Struct({}),
  message: Message,
  events: WidgetEvents,
}).make({
  init: () => ({}),
  update: {
    ClickedShip: ($) =>
      $.emit(
        WidgetEvents.Recorded({
          verb: "decide",
          detail: { value: "ship" },
          says: "Chose Ship",
        }),
      ),
  },
  view: (h) =>
    h.div.children(
      h.output.children(
        String(/** @type {any} */ (h.props.state)?.decide?.value ?? "none"),
      ),
      h.span.class("note").children(h.props.note ?? ""),
      h.button.on("click", Message.ClickedShip()).children("Ship"),
    ),
});

/** @param {Parameters<typeof defineWidget>[2]} [options] */
function widget(options) {
  const tag = `lf-effect-${++tags}`;
  defineWidget(tag, Verdict, options);
  return /** @type {HTMLElement & {state: unknown}} */ (document.createElement(tag));
}

const shown = (/** @type {HTMLElement} */ el) =>
  (el.shadowRoot ?? el).querySelector("output")?.textContent;

test("an element no host answers draws as it connects, and a set draws by the time its pending task settles", async () => {
  const el = widget();
  document.body.append(el);
  assert.equal(shown(el), "none");
  /** @type {PromiseLike<unknown>[]} */
  const pending = [];
  el.addEventListener("pending-task", (event) =>
    pending.push(/** @type {any} */ (event).complete),
  );
  el.state = { decide: { value: "hold" } };
  assert.equal(pending.length, 1);
  await pending[0];
  assert.equal(shown(el), "hold");
  el.remove();
});

test("an element whose lf-connect a host cancels mounts once state is set", () => {
  const el = widget({ shadow: true });
  const answer = (/** @type {Event} */ event) => event.preventDefault();
  document.addEventListener("lf-connect", answer);
  try {
    document.body.append(el);
    assert.equal(shown(el), undefined);
    el.state = { decide: { value: "ship" } };
    assert.equal(shown(el), "ship");
  } finally {
    document.removeEventListener("lf-connect", answer);
    el.remove();
  }
});

test("a Recorded event is an lf-action on the element, in the protocol's shape", () => {
  const el = widget();
  document.body.append(el);
  /** @type {unknown[]} */
  const actions = [];
  el.addEventListener("lf-action", (event) =>
    actions.push(/** @type {CustomEvent} */ (event).detail),
  );
  /** @type {HTMLButtonElement} */ (el.querySelector("button")).click();
  assert.deepEqual(actions, [
    { verb: "decide", detail: { value: "ship" }, says: "Chose Ship" },
  ]);
  el.remove();
});

test("what its inputs read gives it new props when a signal they read moves", async () => {
  const note = signal("first");
  const el = widget({ inputs: () => ({ note: note.value }) });
  document.body.append(el);
  const text = () => el.querySelector(".note")?.textContent;
  assert.equal(text(), "first");
  /** @type {PromiseLike<unknown>[]} */
  const pending = [];
  el.addEventListener("pending-task", (event) =>
    pending.push(/** @type {any} */ (event).complete),
  );
  note.value = "second";
  await Promise.all(pending);
  assert.equal(text(), "second");
  el.remove();
});
