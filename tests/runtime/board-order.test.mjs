/* A position record places its unit on a coordinate of its own.

   Each card's latest move stands at its own fold coordinate, and undo withdraws one of
   them. The container order has to come out of those standing moves alone, whichever
   others stand beside them: an index counted the siblings another move had left, so
   withdrawing that move re-read the index against a different column. Each gesture here
   is dispatched the way lf-board does it, as `rankAt` over the state the user was
   looking at. */

import assert from "node:assert/strict";
import test from "node:test";

import { foldWidgetStates, rankAt } from "/runtime/projection/model.js";

const record = { kind: "position", within: "lf-column", value: "to", rank: "rank" };
const spec = { unit: "card", record };
const authored = new Map([
  [
    "board",
    {
      state: {
        move: {
          value: { todo: ["a", "b", "c", "d"], done: [] },
          ranks: { a: "1", b: "2", c: "3", d: "4" },
          units: {},
        },
      },
      specs: new Map([["move", spec]]),
      positions: {},
    },
  ],
]);

// A board the user drives: each move lands where the column shows it, and undo
// withdraws that one move.
function board() {
  const moves = [];
  const state = () =>
    foldWidgetStates(authored, {
      desired: new Map(
        moves
          .filter((m) => !m.undone)
          .map((m) => [JSON.stringify(["board", m.unit, "move"]), m]),
      ),
    }).get("board").state.move;
  return {
    move(card, to, index) {
      const detail = { card, to, rank: rankAt(state(), to, index, card) };
      const e = {
        id: `m${moves.length}`,
        seq: moves.length,
        widget: "board",
        action: "move",
        detail,
      };
      moves.push({ unit: card, spec, e });
      return moves.at(-1);
    },
    undo(move) {
      move.undone = true;
    },
    order: () => state().value,
  };
}

test("undoing one card's move leaves another card where its own move put it", () => {
  const b = board();
  const d = b.move("d", "todo", 0);
  b.move("c", "todo", 1);
  assert.deepEqual(b.order().todo, ["d", "c", "a", "b"]);
  b.undo(d);
  assert.deepEqual(b.order().todo, ["c", "a", "b", "d"]);
});

test("moving a card again leaves the cards placed against it as the user saw them", () => {
  const b = board();
  b.move("d", "todo", 0);
  b.move("c", "todo", 1);
  b.move("d", "todo", 3);
  assert.deepEqual(b.order().todo, ["c", "a", "b", "d"]);
});

test("two cards moved to the top keep their order when the first is undone", () => {
  const b = board();
  const c = b.move("c", "todo", 0);
  b.move("b", "todo", 0);
  assert.deepEqual(b.order().todo, ["b", "c", "a", "d"]);
  b.undo(c);
  assert.deepEqual(b.order().todo, ["b", "a", "c", "d"]);
});

test("a card moved across columns keeps its place when its neighbour returns", () => {
  const b = board();
  const a = b.move("a", "done", 0);
  b.move("c", "done", 1);
  assert.deepEqual(b.order(), { todo: ["b", "d"], done: ["a", "c"] });
  b.undo(a);
  assert.deepEqual(b.order(), { todo: ["a", "b", "d"], done: ["c"] });
});

test("repeated drops at one place keep finding a rank between their neighbours", () => {
  const b = board();
  for (let i = 0; i < 40; i += 1) b.move(i % 2 ? "b" : "c", "todo", 1);
  // Forty alternating drops between a and whatever sits second.
  assert.deepEqual(b.order().todo, ["a", "b", "c", "d"]);
});
