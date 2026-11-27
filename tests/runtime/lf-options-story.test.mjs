/* The options group's update as a story (`Story`, @effect/ui/testing): what a pick,
   an asked pick, Done and the settled disclosure ask of Leaf, with no page, element or
   Leaf behind them. The drawing on a page is the browser suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { Story } from "@effect/ui/testing";
import { Component, Effect } from "/vendor/effect-ui.js";
import { RecordAction, KeepInTab, TakeBack } from "/runtime/widget-services.js";
import { Options } from "../../packages/default/widgets/lf-options.js";

/** @param {string} id @param {string} label */
const option = (id, label, value = id) => ({
  id,
  label,
  value,
  recommended: false,
  selected: false,
  ref: null,
});

/** @param {string[]} picked @param {object} [more] */
const reading = (picked, more = {}) => ({
  choose: { available: true, detail: { value: picked } },
  add: { available: true, units: {} },
  answer: { available: true },
  ...more,
});

const props = {
  id: "choice",
  multiple: false,
  settled: false,
  choosable: true,
  offered: true,
  card: false,
  options: [option("ship", "Ship it"), option("hold", "Hold it", "wait")],
  remembered: false,
  changes: 0,
  state: reading([]),
};

/** @param {object} given @param {(s: any) => void} story */
const tell = (given, story) =>
  Effect.gen(function* () {
    story(yield* Story.make(Options, { ...props, ...given }));
  }).pipe(Effect.scoped, Effect.runSync);

/** @param {string[]} value @param {string} says */
const chose = (value, says) =>
  RecordAction.make({ verb: "choose", detail: { value }, says });

test("a pick in a group taking one replaces the pick in force", () =>
  tell({ state: reading(["ship"]) }, (s) => {
    s.send({ _tag: "Picked", id: "hold" })
      .expectExact(chose(["hold"], "Chose “Hold it”"))
      .resolve(RecordAction, Component.noop);
    // The add field's words remember the pick the user made beside them.
    assert.deepEqual(s.model.chose, ["hold"]);
  }));

test("picking the one option in force again clears the pick", () =>
  tell({ state: reading(["ship"]) }, (s) =>
    s
      .send({ _tag: "Picked", id: "ship" })
      .expectExact(chose([], "Cleared selection"))
      .resolve(RecordAction, Component.noop),
  ));

test("a group taking several adds a pick after those in force, and drops one", () =>
  tell({ multiple: true, state: reading(["hold"]) }, (s) =>
    s
      .send({ _tag: "Picked", id: "ship" })
      .expectExact(chose(["hold", "ship"], "Chose “Ship it”"))
      .resolve(RecordAction, Component.noop),
  ));

test("dropping one of several names the option dropped", () =>
  tell({ multiple: true, state: reading(["hold", "ship"]) }, (s) =>
    s
      .send({ _tag: "Picked", id: "hold" })
      .expectExact(chose(["ship"], "Dropped “Hold it”"))
      .resolve(RecordAction, Component.noop),
  ));

test("a pick of an option the user added names it by its words", () =>
  tell(
    {
      state: reading([], {
        add: {
          available: true,
          units: { "choice-option-1": { detail: { text: "Ship half" } } },
        },
      }),
    },
    (s) =>
      s
        .send({ _tag: "Picked", id: "choice-option-1" })
        .expectExact(chose(["choice-option-1"], "Chose “Ship half”"))
        .resolve(RecordAction, Component.noop),
  ));

test("a group that takes no pick now asks nothing", () => {
  tell({ choosable: false }, (s) =>
    s.send({ _tag: "Picked", id: "ship" }).expectNone(),
  );
  tell({ state: { ...reading([]), choose: { available: false } } }, (s) =>
    s.send({ _tag: "Picked", id: "ship" }).expectNone(),
  );
  tell({}, (s) => s.send({ _tag: "Picked", id: "nowhere" }).expectNone());
});

test("an asked pick takes the options answering with its value, in the asker's words", () => {
  tell({}, (s) =>
    s
      .send({ _tag: "Asked", value: "wait", words: "Wait a week" })
      .expectExact(chose(["hold"], "Wait a week"))
      .resolve(RecordAction, Component.noop),
  );
  tell({ state: reading(["ship"]) }, (s) =>
    s
      .send({ _tag: "Asked", value: "", words: "Clear" })
      .expectExact(chose([], "Clear"))
      .resolve(RecordAction, Component.noop),
  );
});

/** @param {string[]} options @param {string[]} picked */
const done = (options, picked) =>
  RecordAction.make({
    verb: "answer",
    detail: { options, picked },
    says: "Marked answered",
  });

// Done in force, pressed on `options` with none of them picked.
/** @param {string[]} options @param {object} [more] */
const pressed = (options, more = {}) => ({
  answer: {
    available: true,
    action: "a1",
    detail: { options, picked: [] },
    undoable: true,
    ...more,
  },
});

test("Done marks the set answered, and a second press takes that answer back", () => {
  tell({ multiple: true }, (s) =>
    s
      .send({ _tag: "PressedDone" })
      .expectExact(done(["hold", "ship"], []))
      .resolve(RecordAction, Component.noop),
  );
  tell({ multiple: true, state: reading([], pressed(["hold", "ship"])) }, (s) =>
    s
      .send({ _tag: "PressedDone" })
      .expectExact(TakeBack.make({ verb: "answer" }))
      .resolve(TakeBack, Component.noop),
  );
  tell(
    {
      multiple: true,
      state: reading([], pressed(["hold", "ship"], { undoable: false })),
    },
    (s) => s.send({ _tag: "PressedDone" }).expectNone(),
  );
});

test("Done pressed on a set the group has since grown answers the set it shows now", () =>
  tell({ multiple: true, state: reading([], pressed(["ship"])) }, (s) =>
    s
      .send({ _tag: "PressedDone" })
      .expectExact(done(["hold", "ship"], []))
      .resolve(RecordAction, Component.noop),
  ));

test("the settled disclosure opens from where this tab left it, and remembers", () => {
  tell({ settled: true, remembered: true }, (s) => {
    s.send({ _tag: "ToggledSettled" })
      .expectExact(KeepInTab.make({ key: "lf-settled:choice", value: "0" }))
      .resolve(KeepInTab, Component.noop);
    assert.deepEqual(s.model, { open: false, chose: null });
  });
  tell({ settled: true }, (s) => {
    s.send({ _tag: "Revealed" })
      .expectExact(KeepInTab.make({ key: "lf-settled:choice", value: "1" }))
      .resolve(KeepInTab, Component.noop);
    assert.deepEqual(s.model, { open: true, chose: null });
    // A reveal inside an open group leaves it as it stands.
    s.send({ _tag: "Revealed" }).expectNone();
  });
});
