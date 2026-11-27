/* An Effect UI component on the widget protocol (runtime/effect-widget.js): when it mounts,
   what a set of `state` draws and when, and what its events say to the host. A Leaf
   page's own answers to the protocol, such as recording an `lf-action`, are the
   browser suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { Command, Component, Html, Schema, UiSchema } from "/vendor/effect-ui.js";
import { signal } from "/vendor/signals-core.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";
import { RecordAction } from "/runtime/widget-services.js";

let tags = 0;

const Message = UiSchema.TaggedEnum({ ClickedShip: {} });

// A widget that shows its `state.decide.value` and a `note` its inputs read, and
// records "ship" when its button is pressed.
const Verdict = Html.component({
  name: "Verdict",
  props: Schema.Struct({ ...widgetProps, note: Schema.optional(Schema.String) }),
  model: Schema.Struct({}),
  message: Message,
}).make({
  init: () => ({}),
  update: {
    ClickedShip: ($) =>
      $.run(
        RecordAction.make({
          verb: "decide",
          detail: { value: "ship" },
          says: "Chose Ship",
        }).pipe(Command.map(() => Component.noop)),
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

test("a RecordAction Command is an lf-action on the element, in the protocol's shape", async () => {
  const el = widget();
  document.body.append(el);
  /** @type {unknown[]} */
  const actions = [];
  el.addEventListener("lf-action", (event) =>
    actions.push(/** @type {CustomEvent} */ (event).detail),
  );
  /** @type {HTMLButtonElement} */ (el.querySelector("button")).click();
  // A Command runs in a microtask of the task that handled the click, so Leaf records
  // the gesture before the browser's next frame.
  await Promise.resolve();
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

test("inputs that throw when a signal moves fail the widget, not the code that moved it", () => {
  const note = signal("first");
  const el = widget({
    inputs: () => {
      if (note.value === "bad") throw new Error("cannot read");
      return { note: note.value };
    },
  });
  document.body.append(el);
  /** @type {unknown[]} */
  const errors = [];
  el.addEventListener("error", (event) =>
    errors.push(/** @type {ErrorEvent} */ (event).error),
  );
  note.value = "bad";
  assert.equal(errors.length, 1);
  assert.match(String(errors[0]), /cannot read/);
  el.remove();
});

test("a property the page set before the tag was defined is a prop once it upgrades", () => {
  const tag = `lf-effect-${++tags}`;
  const el = /** @type {HTMLElement & {note?: string}} */ (document.createElement(tag));
  el.note = "early";
  document.body.append(el);
  defineWidget(tag, Verdict, { properties: ["note"] });
  try {
    assert.equal(el.querySelector(".note")?.textContent, "early");
    assert.equal(Object.hasOwn(el, "note"), false);
  } finally {
    el.remove();
  }
});
