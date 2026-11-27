/* An Effect UI component on the widget protocol (runtime/effect-widget.js): when it mounts,
   what a set of `state` draws and when, and what its events say to the host. A Leaf
   page's own answers to the protocol, such as recording an `lf-action`, are the
   browser suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import {
  Command,
  Component,
  Effect,
  Html,
  Mount,
  Schema,
  Stream,
  UiSchema,
} from "/vendor/effect-ui.js";
import { signal } from "/vendor/signals-core.js";
import { declare, defineWidget, widgetProps } from "/runtime/effect-widget.js";
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

test("a property its host sets reaches the component as a prop of that name", async () => {
  const el = /** @type {HTMLElement & {note: unknown}} */ (
    /** @type {unknown} */ (widget({ properties: ["note"] }))
  );
  el.note = "told before it connects";
  document.body.append(el);
  const text = () => el.querySelector(".note")?.textContent;
  assert.equal(text(), "told before it connects");
  /** @type {PromiseLike<unknown>[]} */
  const pending = [];
  el.addEventListener("pending-task", (event) =>
    pending.push(/** @type {any} */ (event).complete),
  );
  el.note = "told again";
  assert.equal(el.note, "told again");
  await Promise.all(pending);
  assert.equal(text(), "told again");
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

const DialMessage = UiSchema.TaggedEnum({ Set: { at: Schema.Number } });

// A widget whose Model holds a number that a member reads and sets.
const Dial = Html.component({
  name: "Dial",
  props: Schema.Struct({ ...widgetProps }),
  model: Schema.Struct({ at: Schema.Number }),
  message: DialMessage,
}).make({
  init: () => ({ at: 0 }),
  update: (_$, /** @type {{at: number}} */ message) => ({ at: message.at }),
  view: (h, /** @type {{at: number}} */ model) => h.output.children(String(model.at)),
});

const dialMembers = {
  at: {
    get: (/** @type {{at: number}} */ model) => model.at,
    set: (/** @type {number} */ at) => DialMessage.Set({ at }),
  },
};

test("a member set before the element connects reaches its root, and draws before lf-commands", async () => {
  const tag = `lf-effect-${++tags}`;
  defineWidget(tag, Dial, { members: dialMembers });
  const el = /** @type {HTMLElement & {at: number}} */ (document.createElement(tag));
  el.at = 3;
  /** @type {PromiseLike<unknown>[]} */
  const pending = [];
  /** @type {(string | null | undefined)[]} */
  const announced = [];
  el.addEventListener("pending-task", (event) =>
    pending.push(/** @type {any} */ (event).complete),
  );
  el.addEventListener("lf-commands", () => announced.push(shown(el)));
  document.body.append(el);
  try {
    assert.equal(el.at, 3);
    assert.equal(pending.length, 1);
    await pending[0];
    assert.equal(shown(el), "3");
    assert.equal(announced.at(-1), "3");
  } finally {
    el.remove();
  }
});

test("a member the page set before the tag was defined reaches the Model once it mounts", () => {
  const tag = `lf-effect-${++tags}`;
  const el = /** @type {HTMLElement & {at?: number}} */ (document.createElement(tag));
  el.at = 7;
  document.body.append(el);
  defineWidget(tag, Dial, { members: dialMembers });
  try {
    assert.equal(Object.hasOwn(el, "at"), false);
    assert.equal(el.at, 7);
  } finally {
    el.remove();
  }
});

// A widget whose view throws, so its root fails as it mounts.
const Broken = Html.component({
  name: "Broken",
  props: Schema.Struct({ ...widgetProps }),
  model: Schema.Struct({}),
  message: Schema.Never,
}).make({
  init: () => ({}),
  update: {},
  view: () => {
    throw new Error("cannot draw");
  },
});

for (const shadow of [false, true])
  test(`a ${shadow ? "shadow" : "light"} widget whose root fails keeps its authored children in view`, async () => {
    const tag = `lf-effect-${++tags}`;
    defineWidget(tag, Broken, { shadow });
    const el = document.createElement(tag);
    el.innerHTML = "<p>authored</p>";
    /** @type {unknown[]} */
    const errors = [];
    el.addEventListener("error", (event) =>
      errors.push(/** @type {ErrorEvent} */ (event).error),
    );
    document.body.append(el);
    try {
      await Promise.resolve();
      assert.match(String(errors[0]), /cannot draw/);
      assert.equal(el.querySelector("p")?.textContent, "authored");
      assert.match(el.querySelector(".lf-error")?.textContent ?? "", /cannot draw/);
      // A shadow root shows the authored children, and the box among them, through a
      // bare slot.
      if (shadow) assert.ok(el.shadowRoot?.querySelector("slot:not([name])"));
    } finally {
      el.remove();
    }
  });

test("inputs that throw show the box beside the authored children until they read again", () => {
  const note = signal("first");
  const el = widget({
    inputs: () => {
      if (note.value === "bad") throw new Error("cannot read");
      return { note: note.value };
    },
  });
  el.innerHTML = "<p>authored</p>";
  document.body.append(el);
  el.addEventListener("error", () => {});
  try {
    note.value = "bad";
    assert.equal(el.querySelector("p")?.textContent, "authored");
    assert.ok(el.querySelector(".lf-error"));
    note.value = "good";
    assert.equal(el.querySelector(".lf-error"), null);
  } finally {
    el.remove();
  }
});

const Stepped = UiSchema.TaggedEnum({ ClickedStep: {} });

// A row that reads the step as last drawn, as lf-timeline's First row does, declared
// on each draw that moves it.
const DeclareStep = Mount.make(
  "DeclareStep",
  { args: { step: Schema.Number } },
  (/** @type {HTMLElement} */ node, _args, changes) => {
    let drawn = 0;
    const lfCommands = {
      title: "Here",
      rows: [{ id: "first", title: "First step", when: () => drawn > 0 }],
    };
    return Stream.runForEach(changes, ({ step }) =>
      Effect.sync(() => {
        drawn = step;
        declare(node, { lfCommands });
      }),
    ).pipe(Effect.as(Component.noop));
  },
);

const Stepping = Html.component({
  name: "Stepping",
  props: Schema.Struct({ ...widgetProps }),
  model: Schema.Struct({ step: Schema.Number }),
  message: Stepped,
}).make({
  init: () => ({ step: 0 }),
  update: { ClickedStep: ($) => ({ step: $.model.step + 1 }) },
  view: (h, /** @type {{step: number}} */ model) =>
    h.button
      .on("click", Stepped.ClickedStep())
      .onMount(DeclareStep({ step: model.step }))
      .children("Next"),
});

test("what a widget declares stands on its element, said again on a draw its own message starts, until its root closes", async () => {
  const tag = `lf-effect-${++tags}`;
  defineWidget(tag, Stepping, { shadow: true });
  const el = document.createElement(tag);
  /** @type {unknown[]} */
  const said = [];
  el.addEventListener("lf-commands", () => said.push(el.lfCommands?.rows[0].when?.()));
  document.body.append(el);
  await new Promise((resolve) => setTimeout(resolve));
  assert.equal(el.lfCommands?.title, "Here");
  assert.equal(said.at(-1), false);
  said.length = 0;
  el.shadowRoot?.querySelector("button")?.click();
  await new Promise((resolve) => setTimeout(resolve));
  assert.deepEqual(said, [true]);
  el.remove();
  await Promise.resolve();
  assert.equal(el.lfCommands, undefined);
});
