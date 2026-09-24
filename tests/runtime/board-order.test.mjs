/* A position record places its unit on a coordinate of its own.

   Each card's latest move stands at its own fold coordinate, and undo withdraws one of
   them. The container order has to come out of those standing moves alone, whichever
   others stand beside them: an index counted the siblings another move had left, so
   withdrawing that move re-read the index against a different column. Each gesture here
   is dispatched the way lf-board does it, as `rankAt` over the state the user was
   looking at. */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { authoredRank, foldWidgetStates, rankAt } from "/runtime/projection/model.js";

// The rank cases `test_interact_document.py` holds `projection.py` to, so the append
// door admits what this module computes and both runtimes rank authored units alike.
const cases = JSON.parse(readFileSync(new URL("../rank_cases.json", import.meta.url)));
const RANK = new RegExp(`^(?:${cases.pattern})$`);

test("authored ranks and computed keys follow the rules the append door reads", () => {
  for (const [index, rank] of cases.authored) assert.equal(authoredRank(index), rank);
  for (const rank of cases.invalid) assert.doesNotMatch(rank, RANK);
  // A key between every two valid neighbours, and past either end, is itself valid.
  const valid = [...cases.valid].sort();
  for (const rank of valid) assert.match(rank, RANK);
  for (let i = 0; i <= valid.length; i += 1) {
    const [before, after] = [valid[i - 1], valid[i]];
    const ranks = { ...(before && { b: before }), ...(after && { a: after }) };
    const units = [...(before ? ["b"] : []), ...(after ? ["a"] : [])];
    const key = rankAt({ value: { c: units }, ranks }, "c", before ? 1 : 0, "u");
    assert.match(key, RANK);
    if (before) assert.ok(before < key, `${before} < ${key}`);
    if (after) assert.ok(key < after, `${key} < ${after}`);
  }
});

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

// A column that only grows at one end, as a swipe pile does: each key sorts past the
// last and stays short, since an open end steps a digit rather than halving the gap.
for (const end of ["tail", "head"]) {
  test(`two thousand drops at the ${end} keep their keys ordered and short`, () => {
    const state = { value: { pile: [] }, ranks: {} };
    for (let i = 0; i < 2000; i += 1) {
      const unit = `u${i}`;
      const at = end === "tail" ? state.value.pile.length : 0;
      state.ranks[unit] = rankAt(state, "pile", at, unit);
      state.value.pile.splice(at, 0, unit);
    }
    const keys = state.value.pile.map((unit) => state.ranks[unit]);
    for (const key of keys) assert.match(key, RANK);
    for (let i = 1; i < keys.length; i += 1) assert.ok(keys[i - 1] < keys[i], keys[i]);
    assert.ok(Math.max(...keys.map((key) => key.length)) <= 60);
  });
}

// v1 lists todo `a b c`, and the user drops x between a and b at "1i". v2 writes the
// move and adds n above it, so its authored ranks shift by one: carried onto v2, "1i"
// is the gap between n and a. v2's markup places x from then on, and the server marks
// the move absorbed.
const v2 = new Map([
  [
    "board",
    {
      state: {
        move: {
          value: { todo: ["n", "a", "x", "b", "c"], done: [] },
          ranks: { n: "1", a: "2", x: "3", b: "4", c: "5" },
          units: {},
        },
      },
      specs: new Map([["move", spec]]),
    },
  ],
]);
const dropX = {
  id: "m0",
  seq: 0,
  widget: "board",
  action: "move",
  detail: { card: "x", to: "todo", rank: "1i" },
};
const foldV2 = (entry) =>
  foldWidgetStates(v2, {
    desired: new Map([[JSON.stringify(["board", "x", "move"]), entry]]),
  }).get("board").state.move;

test("a move a later revision absorbed leaves the order that revision wrote", () => {
  const move = foldV2({ unit: "x", spec, e: dropX, absorbed: true });
  assert.deepEqual(move.value.todo, ["n", "a", "x", "b", "c"]);
  // The move still stands on its unit, as a written-back pick does.
  assert.equal(move.units.x.value, "todo");
});

test("a move no revision has absorbed still places its card by its rank", () => {
  // The reading a revision written after the move has to record, which is why the
  // door takes a move only on the newest revision.
  assert.deepEqual(foldV2({ unit: "x", spec, e: dropX }).value.todo, [
    "n",
    "x",
    "a",
    "b",
    "c",
  ]);
});
