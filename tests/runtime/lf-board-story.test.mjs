/* The board's update as a story (`Story`, @effect/ui/testing): what a grab, its steps,
   a drop, a drag and a phone's button ask of Leaf and of the widget a card shows, with
   no page, element or Leaf behind them. Placing the cards, Sortable and the keys on a
   page are the browser suite's. */
import assert from "node:assert/strict";
import test from "node:test";
import { Story } from "@effect/ui/testing";
import { Component, Effect } from "/vendor/effect-ui.js";
import { Announce, RecordAction } from "/runtime/widget-services.js";
import {
  AskOwner,
  Board,
  BoardMessage,
} from "../../packages/default/widgets/lf-board.js";

const host = { id: "sprint" };

/** @param {Record<string, string[]>} value */
const reading = (value) => ({
  move: {
    available: true,
    value,
    ranks: Object.fromEntries(
      Object.values(value).flatMap((cards) => cards.map((id, i) => [id, "abc"[i]])),
    ),
  },
});

/** @param {string} id @param {object} [more] */
const card = (id, more = {}) => ({ id, title: id, shows: null, choice: null, ...more });

const props = {
  host,
  exhibit: false,
  columns: [
    { id: "todo", label: "Todo", value: "" },
    { id: "doing", label: "Doing", value: "next" },
    { id: "done", label: "Done", value: "later" },
  ],
  cards: [card("heater"), card("baffle"), card("camera")],
  state: reading({ todo: ["heater", "baffle"], doing: ["camera"], done: [] }),
};

/** @param {object} given @param {(s: any) => void} story */
const tell = (given, story) =>
  Effect.gen(function* () {
    story(yield* Story.make(Board, { ...props, ...given }));
  }).pipe(Effect.scoped, Effect.runSync);

const said = (/** @type {string} */ words) => Announce.make({ words });

test("a keyboard grab carried to the next column records one ranked move", () =>
  tell({}, (s) => {
    s.send({ _tag: "Grabbed", card: "baffle" });
    s.send({ _tag: "Stepped", column: 1, row: 0, crosses: false })
      .expectExact(said("baffle — Doing, position 2 of 2"))
      .resolve(Announce, Component.noop);
    assert.deepEqual(s.model.held.doing, ["camera", "baffle"]);
    s.send({ _tag: "Dropped" })
      .expectExact(
        RecordAction.make({
          verb: "move",
          detail: { unit: "baffle", value: "doing", rank: "b" },
          says: "Moved to Doing",
        }),
      )
      .resolve(RecordAction, Component.noop);
    assert.equal(s.model.held, null);
    assert.equal(s.model.grab, null);
  }));

test("a card dropped where it was grabbed records nothing", () =>
  tell({}, (s) => {
    s.send({ _tag: "Grabbed", card: "heater" });
    s.send({ _tag: "Stepped", column: 0, row: 1, crosses: false })
      .expectExact(said("heater — Todo, position 2 of 2"))
      .resolve(Announce, Component.noop);
    s.send({ _tag: "Stepped", column: 0, row: -1, crosses: false })
      .expectExact(said("heater — Todo, position 1 of 2"))
      .resolve(Announce, Component.noop);
    s.send({ _tag: "Dropped" });
    assert.equal(s.model.held, null);
  }));

test("a row step past a column's end enters the next column only where it stands there", () =>
  tell({}, (s) => {
    s.send({ _tag: "Grabbed", card: "camera" });
    s.send({ _tag: "Stepped", column: 0, row: 1, crosses: false });
    assert.deepEqual(s.model.held.doing, ["camera"]);
    s.send({ _tag: "Stepped", column: 0, row: 1, crosses: true })
      .expectExact(said("camera — Done, position 1 of 1"))
      .resolve(Announce, Component.noop);
    s.send({ _tag: "Stepped", column: 0, row: -1, crosses: true })
      .expectExact(said("camera — Doing, position 1 of 1"))
      .resolve(Announce, Component.noop);
    s.send({ _tag: "Stepped", column: 0, row: -1, crosses: true })
      .expectExact(said("camera — Todo, position 3 of 3"))
      .resolve(Announce, Component.noop);
  }));

test("Escape puts the card back and keeps the user on it", () =>
  tell({}, (s) => {
    s.send({ _tag: "Grabbed", card: "heater" });
    s.send({ _tag: "Stepped", column: 1, row: 0, crosses: false })
      .expectExact(said("heater — Doing, position 1 of 2"))
      .resolve(Announce, Component.noop);
    s.send({ _tag: "Cancelled", refocus: true })
      .expectExact(said("heater — move cancelled"))
      .resolve(Announce, Component.noop);
    assert.equal(s.model.held, null);
    assert.equal(s.model.reveal.card, "heater");
  }));

test("nothing grabs while the board's move is unavailable", () =>
  tell(
    {
      state: {
        move: {
          ...reading({ todo: ["heater"], doing: [], done: [] }).move,
          available: false,
        },
      },
    },
    (s) => {
      s.send({ _tag: "Grabbed", card: "heater" });
      assert.equal(s.model.grab, null);
    },
  ));

test("a pointer drag records where it ends, and nothing where it began", () =>
  tell({}, (s) => {
    s.send({ _tag: "DragStarted", card: "heater" });
    assert.notEqual(s.model.held, null);
    s.send({ _tag: "DragEnded", to: "todo", index: 0 });
    assert.equal(s.model.held, null);
    s.send({ _tag: "DragStarted", card: "heater" });
    s.send({ _tag: "DragEnded", to: "done", index: 0 })
      .expectExact(
        RecordAction.make({
          verb: "move",
          detail: { unit: "heater", value: "done", rank: "i" },
          says: "Moved to Done",
        }),
      )
      .resolve(RecordAction, Component.noop);
  }));

test("a phone's button moves the card to the end of its column, and the user with it", () =>
  tell({}, (s) => {
    const sent = s
      .send({ _tag: "MovedTo", card: "heater", column: "doing" })
      .expectExact(
        RecordAction.make({
          verb: "move",
          detail: { unit: "heater", value: "doing", rank: "b" },
          says: "Moved to Doing",
        }),
      );
    assert.equal(s.model.reveal.card, "heater");
    // Until the record settles, a `state` that still places the cards as they stood
    // draws where the move lands.
    assert.deepEqual(s.model.landed, {
      placement: { todo: ["baffle"], doing: ["camera", "heater"], done: [] },
      from: { todo: ["heater", "baffle"], doing: ["camera"], done: [] },
    });
    sent.resolve(RecordAction, BoardMessage.Settled());
    assert.equal(s.model.landed, null);
  }));

const choice = (/** @type {string} */ value) => ({
  value,
  options: [
    { value: "next", label: "Next" },
    { value: "soon", label: "Soon" },
    { value: "soon", label: "Sooner" },
  ],
  disabled: false,
});

test("a card showing a choice asks its owner for the column's value, past a column two options name", () =>
  tell(
    {
      columns: [
        { id: "todo", label: "Todo", value: "" },
        { id: "soon", label: "Soon", value: "soon" },
        { id: "doing", label: "Doing", value: "next" },
      ],
      cards: [card("rail", { shows: "rail-choice", choice: choice("") })],
      state: reading({ todo: ["rail"], soon: [], doing: [] }),
    },
    (s) => {
      s.send({ _tag: "Grabbed", card: "rail" });
      s.send({ _tag: "Stepped", column: 1, row: 0, crosses: false })
        .expectExact(said("rail — Doing, position 1 of 1"))
        .resolve(Announce, Component.noop);
      s.send({ _tag: "Dropped" })
        .expectExact(
          AskOwner.make({
            host,
            card: "rail",
            value: "next",
            says: "Moved “rail” to Doing",
          }),
        )
        .resolve(AskOwner, Component.noop);
    },
  ));

test("a card showing a choice stands where the choice puts it, whatever the board's moves say", () =>
  tell(
    {
      cards: [card("rail", { shows: "rail-choice", choice: choice("next") })],
      state: reading({ todo: ["rail"], doing: [], done: [] }),
    },
    (s) => {
      s.send({ _tag: "Grabbed", card: "rail" });
      assert.deepEqual(s.model.held, { todo: [], doing: ["rail"], done: [] });
    },
  ));
